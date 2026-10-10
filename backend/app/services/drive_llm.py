import logging

from pydantic import ValidationError

from app.config import get_settings
from app.schemas.city import CityOut
from app.schemas.drive import DrivePlan, DriveRequest, DriveResponse
from app.schemas.weather import DailyWeather
from app.services import llm_client, weather
from app.services.city_store import TAG_LABELS
from app.services.geo import haversine_km
from app.services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

# 公路里程通常比直线距离长,经验系数 1.25;均速按 75 km/h(含服务区,不含长时间休整)
ROAD_FACTOR = 1.25
AVG_SPEED = 75.0

SYSTEM_PROMPT = """你是一位经验实在的自驾旅行规划师,根据用户提供的真实条件,安排从出发地到目的地的自驾。

先做一个判断:往返纯驾驶时间 + 目的地游玩时间,能否装进用户的空闲时间窗口?
- 装得下 → mode="drive":给出精准的往返自驾玩法
- 装不下(比如单程就要开十几个小时、或往返路上会吃掉全部假期)→ mode="rental":建议飞机/高铁过去 + 当地租车,给租车建议

mode="drive" 时:
- route 给出去程/返程走法:大方向、主要高速或国道、顺路值得停一停的城镇,共 2-3 段
- daily_plan 必须覆盖整个空闲窗口(含往返驾驶日),每天一个主题、3-5 个 items;驾驶日写清大致出发时间、中途休息点、当晚落脚地
- 单日纯驾驶原则上不超过 8 小时,超过就拆成两天并安排中途住宿
- depart_date/return_date 在窗口内挑(优先天气好的日子出发),格式 MM-DD
- total_km/total_drive_hours 给出你估算的往返总量

mode="rental" 时:
- summary 说清为什么自驾往返不划算
- rentals 给 2-4 家真实存在的连锁租车公司或常用平台(如 神州租车、一嗨租车、携程租车、飞猪用车等),每家一句定位;不确定的信息不要编造
- daily_plan 给出目的地当地 2-3 天的租车自驾玩法(从机场/高铁站取车开始),数量不必覆盖整个窗口
- tips 覆盖取还车、证件、异地还车费等注意事项

通用要求:
- 语言口语化、具体、可执行;不编造精确价格、门店电话
- daily_plan 的日期必须来自用户空闲窗口内,格式 MM-DD
- tips 结合逐日天气(雨雪大风对山路/高速的影响等),3-6 条,category 取「路线、驾驶、天气、费用、其他」之一
- 严格只输出 JSON,不要输出任何其他内容"""

DRIVE_JSON_TEMPLATE = """{{"mode": "drive 或 rental",
 "summary": "一句话结论",
 "total_km": 1234,
 "total_drive_hours": 14.5,
 "depart_date": "MM-DD",
 "return_date": "MM-DD",
 "route": [{{"title": "去程", "desc": "路线走法"}}],
 "daily_plan": [{{"day": 1, "date": "MM-DD", "title": "当天主题", "items": ["行程点1", "行程点2", "行程点3"]}}],
 "rentals": [{{"name": "租车公司名", "desc": "一句话介绍"}}],
 "tips": [{{"category": "路线、驾驶、天气、费用、其他 之一", "text": "建议内容"}}]}}"""


def estimate_drive(origin_lat: float, origin_lon: float, city: CityOut) -> tuple[int, int, float]:
    """按直线距离估算:直线 km、公路 km、单程纯驾驶小时。"""
    straight = haversine_km(origin_lat, origin_lon, city.lat, city.lon)
    road = max(round(straight * ROAD_FACTOR / 10) * 10, 10)
    return straight, road, round(road / AVG_SPEED, 1)


def _build_user_prompt(
    city: CityOut,
    req: DriveRequest,
    days: list[DailyWeather],
    road_km: int,
    drive_hours: float,
) -> str:
    weather_lines = []
    for d in days:
        prob = f"{d.rain_prob}%" if d.rain_prob is not None else "未知"
        weather_lines.append(f"- {d.date}:{d.desc} {d.t_min:.0f}~{d.t_max:.0f}°C,降水概率 {prob}")

    origin_name = req.origin.name or "用户当前定位"
    window_days = (req.end_date - req.start_date).days + 1
    tag_names = "、".join(TAG_LABELS[t] for t in req.user_tags if t in TAG_LABELS) or "无"
    trip_hint = (
        f"\n【原计划的游玩区间】{req.trip_start} ~ {req.trip_end}(可按自驾节奏重排)"
        if req.trip_start and req.trip_end
        else ""
    )

    return f"""请为下面的需求规划自驾方案。

【出发地】{origin_name}
【目的地】{city.name_zh}({city.name_en}),{city.country}
【目的地简介】{city.summary}
【建议游玩天数】{city.suggested_days} 天
【用户空闲时间窗口】{req.start_date} 至 {req.end_date},共 {window_days} 天(往返驾驶和游玩都要安排在这段时间里){trip_hint}
【距离参考】直线距离约 {haversine_km(req.origin.lat, req.origin.lon, city.lat, city.lon)} km;按公路估算单程约 {road_km} km、纯驾驶约 {drive_hours} 小时(可按你对实际路况的经验修正)
【目的地逐日天气】(用来挑出发日、避开雨天走山路)
{chr(10).join(weather_lines)}
【用户偏好】{tag_names}

要求:
- 先判断时间是否装得下往返自驾 + 游玩:装得下用 mode="drive",装不下用 mode="rental"
- daily_plan 的日期都在窗口内,格式 MM-DD

严格按以下 JSON 结构输出:
{DRIVE_JSON_TEMPLATE}"""


_cache_by_ttl: dict[int, TTLCache] = {}


def _drive_cache(ttl: int) -> TTLCache:
    if ttl not in _cache_by_ttl:
        _cache_by_ttl[ttl] = TTLCache(maxsize=100, ttl=float(ttl))
    return _cache_by_ttl[ttl]


def _validate_plan(plan: DrivePlan) -> None:
    """核心板块缺失视为不合格,触发重试。"""
    if plan.mode == "drive" and not plan.daily_plan:
        raise ValueError("mode=drive 但没有给出 daily_plan")
    if plan.mode == "rental" and not plan.rentals:
        raise ValueError("mode=rental 但没有给出 rentals")


async def generate_drive(city: CityOut, req: DriveRequest, http, llm) -> DriveResponse:
    """生成自驾方案(带缓存)。天气失败抛 WeatherServiceError,LLM 失败抛 LLMError。"""
    settings = get_settings()
    cache = _drive_cache(settings.guide_cache_ttl_seconds)
    key = (
        city.id,
        req.start_date.isoformat(),
        req.end_date.isoformat(),
        round(req.origin.lat, 2),
        round(req.origin.lon, 2),
        tuple(sorted(req.user_tags)),
    )

    async def _produce() -> DriveResponse:
        start, end = req.start_date.isoformat(), req.end_date.isoformat()
        days = await weather.get_daily_weather(http, city.lat, city.lon, start, end)
        straight, road, hours = estimate_drive(req.origin.lat, req.origin.lon, city)
        user_prompt = _build_user_prompt(city, req, days, road, hours)

        plan: DrivePlan | None = None
        last_error: Exception | None = None
        for _ in range(2):  # 格式校验失败重试一次
            try:
                data = await llm_client.chat_json(SYSTEM_PROMPT, user_prompt, client=llm)
                plan = DrivePlan.model_validate(data)
                _validate_plan(plan)
                break
            except (ValidationError, ValueError) as e:
                last_error = e
                plan = None
                logger.warning("自驾方案校验失败,重试中: %s", str(e)[:300])
        if plan is None:
            raise llm_client.LLMError(f"自驾方案格式校验失败: {last_error}") from last_error

        origin_name = req.origin.name or "你所在的位置"
        return DriveResponse(
            city_id=city.id,
            city_name_zh=city.name_zh,
            origin_name=origin_name,
            start_date=req.start_date,
            end_date=req.end_date,
            distance_km=straight,
            est_drive_km=road,
            est_drive_hours=hours,
            weather_brief=weather.build_weather_summary(days).summary_text,
            plan=plan,
        )

    return await cache.get_or_set(key, _produce)
