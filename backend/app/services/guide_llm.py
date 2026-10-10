import logging

from pydantic import ValidationError

from app.config import get_settings
from app.schemas.city import CityOut
from app.schemas.guide import GuideOutput, GuideRequest, GuideResponse
from app.schemas.weather import DailyWeather
from app.services import llm_client, weather
from app.services.city_store import TAG_LABELS
from app.services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位轻松友好的中文旅行向导,为用户生成实用、可执行的旅行攻略。

写作要求:
- 语言口语化、简洁,每条内容不超过 2 句,像朋友聊天一样轻松
- attractions 提供 3-5 个最值得去的景点
- daily_plan 的天数必须正好等于行程天数,每天一个主题、3-5 个行程点,安排要地理上顺路、可执行
- tips 中的「穿衣」和「雨具」建议必须基于用户提供的真实逐日天气预报,不得虚构天气
- 不要编造精确价格、营业时间、「必须预约」等容易过期的信息
- 严格只输出 JSON,不要输出任何其他内容"""

SEASON_BY_MONTH = {
    12: "冬季", 1: "冬季", 2: "冬季",
    3: "春季", 4: "春季", 5: "春季",
    6: "夏季", 7: "夏季", 8: "夏季",
    9: "秋季", 10: "秋季", 11: "秋季",
}

GUIDE_JSON_TEMPLATE = """{{"overview": "2-3 句轻松的开场总览",
 "attractions": [{{"name": "景点名", "highlight": "一句话亮点", "duration": "如「半天」", "tip": "一条实用小贴士"}}],
 "daily_plan": [{{"day": 1, "date": "MM-DD", "title": "当天主题", "items": ["行程点1", "行程点2", "行程点3"]}}],
 "food": [{{"name": "美食名", "desc": "一句话介绍"}}],
 "tips": [{{"category": "穿衣、雨具、交通、门票、其他 之一", "text": "建议内容"}}]}}"""


def _build_user_prompt(city: CityOut, req: GuideRequest, days: list[DailyWeather], trip_days: int) -> str:
    weather_lines = []
    for d in days:
        prob = f"{d.rain_prob}%" if d.rain_prob is not None else "未知"
        weather_lines.append(f"- {d.date}:{d.desc} {d.t_min:.0f}~{d.t_max:.0f}°C,降水概率 {prob}")

    tag_names = "、".join(TAG_LABELS[t] for t in req.user_tags if t in TAG_LABELS) or "无"
    season = SEASON_BY_MONTH[req.start_date.month]

    return f"""请为下面的旅行需求生成一份景点攻略。

【目的地】{city.name_zh}({city.name_en}),{city.country}
【城市简介】{city.summary}
【行程日期】{req.start_date} 至 {req.end_date},共 {trip_days} 天({season})
【逐日天气预报】
{chr(10).join(weather_lines)}
【用户偏好】{tag_names}

要求:
- attractions 提供 3-5 个最值得去的景点
- daily_plan 必须正好 {trip_days} 天,每天给出主题和 3-5 个行程点
- tips 中「穿衣」和「雨具」建议必须基于上面的真实天气预报

严格按以下 JSON 结构输出:
{GUIDE_JSON_TEMPLATE}"""


_cache_by_ttl: dict[int, TTLCache] = {}


def _guide_cache(ttl: int) -> TTLCache:
    if ttl not in _cache_by_ttl:
        _cache_by_ttl[ttl] = TTLCache(maxsize=100, ttl=float(ttl))
    return _cache_by_ttl[ttl]


async def generate_guide(city: CityOut, req: GuideRequest, http, llm) -> GuideResponse:
    """生成单城市攻略(带缓存)。天气失败抛 WeatherServiceError,LLM 失败抛 LLMError。"""
    settings = get_settings()
    cache = _guide_cache(settings.guide_cache_ttl_seconds)
    start, end = req.start_date.isoformat(), req.end_date.isoformat()
    key = (city.id, start, end, tuple(sorted(req.user_tags)))

    async def _produce() -> GuideResponse:
        days = await weather.get_daily_weather(http, city.lat, city.lon, start, end)
        trip_days = (req.end_date - req.start_date).days + 1
        user_prompt = _build_user_prompt(city, req, days, trip_days)

        guide: GuideOutput | None = None
        last_error: Exception | None = None
        for _ in range(2):  # 格式校验失败重试一次
            try:
                data = await llm_client.chat_json(SYSTEM_PROMPT, user_prompt, client=llm)
                guide = GuideOutput.model_validate(data)
                if len(guide.daily_plan) != trip_days:
                    # 防止模型在长行程上偷懒少排天数
                    raise ValueError(f"行程共 {trip_days} 天,但攻略只排了 {len(guide.daily_plan)} 天")
                break
            except (ValidationError, ValueError) as e:
                last_error = e
                guide = None
                logger.warning("攻略校验失败,重试中: %s", str(e)[:300])
        if guide is None:
            raise llm_client.LLMError(f"攻略格式校验失败: {last_error}") from last_error

        return GuideResponse(
            city_id=city.id,
            city_name_zh=city.name_zh,
            start_date=req.start_date,
            end_date=req.end_date,
            weather_brief=weather.build_weather_summary(days).summary_text,
            guide=guide,
        )

    return await cache.get_or_set(key, _produce)
