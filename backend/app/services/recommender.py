import asyncio
from collections import deque
from datetime import date, timedelta

import httpx

from app.schemas.city import CityOut
from app.schemas.recommend import (
    LLMPick,
    LLMPickResult,
    Origin,
    RecommendRequest,
    RecommendResponse,
    RecommendationCard,
)
from app.schemas.weather import DailyWeather
from app.services import llm_client, weather
from app.services.city_store import TAG_LABELS, cities_by_ids, cities_by_tags
from app.services.geo import haversine_km

# 标签模式候选过多时截断:天气请求与提示词长度都可控,LLM 也只需要精选名单
MAX_TAG_CANDIDATES = 16
NEAR_CANDIDATES = 10  # 提供出发地时,保证最近的城市入选,其余名额留给远方候选

PICK_SYSTEM_PROMPT = """你是轻松专业的旅行推荐助手,根据用户的时间与偏好,结合各候选城市的真实天气预报,挑选最值得去的目的地。

挑选原则:
- 行程安排:用户给出的日期只是「有空的时间窗口」,不是行程长度。为每个推荐城市在窗口内选定一段最合适的连续出发区间(trip_start/trip_end):天数以该城市的「建议游玩天数」为基准,可上下浮动 1 天,尽量不超过建议天数 +2;不必填满窗口,宁可持续合理也不硬凑天数
- 出发区间优先挑该城市天气预报更好的日子(比如避开连雨天、选晴好的一段),可在 reason 里自然带过(如「帮你挑了 10-11 到 10-13 这段晴天」)
- 天气优先:雨天多、气温极端(过冷/过热)、有雷阵雨的城市降级,并在 warning 中给出具体提示(如「期间多雨,建议备雨具」);天气好时 warning 为 null
- 若提供了用户出发地与各候选的距离:短行程(3 天以内)优先考虑较近的目的地,远途候选只在行程够长或理由足够充分时推荐;距离的取舍可在 reason 中自然提及
- 只能从候选列表中选,city_id 必须与候选完全一致;最多 3 个,按推荐度排序
- reason 用轻松口语化的中文,1-2 句,可提及温度、天气亮点或与偏好的契合点
- 若所有候选天气都很一般,仍挑出相对最好的,并在 note 里诚实说明;否则 note 为 null
- 严格只输出 JSON,不要输出任何其他内容"""


async def _safe_weather(
    client: httpx.AsyncClient, city: CityOut, start: str, end: str
) -> tuple[CityOut, list[DailyWeather] | None]:
    """单个城市的天气查询,失败时返回 (city, None) 而不中断整体流程。"""
    try:
        days = await weather.get_daily_weather(client, city.lat, city.lon, start, end)
        return city, days
    except weather.WeatherServiceError:
        return city, None


def _matched_tags(city: CityOut, user_tags: list[str]) -> list[str]:
    if not user_tags:
        return []
    hit = set(city.tags) & set(user_tags)
    return [TAG_LABELS[t] for t in TAG_LABELS if t in hit]


def _round_robin_by_region(cities: list[CityOut], limit: int) -> list[CityOut]:
    """按地区轮询取样,保证候选的地理多样性。"""
    by_region: dict[str, deque[CityOut]] = {}
    for c in cities:
        by_region.setdefault(c.region, deque()).append(c)
    picked: list[CityOut] = []
    while len(picked) < limit and any(by_region.values()):
        for group in by_region.values():
            if group and len(picked) < limit:
                picked.append(group.popleft())
    return picked


def _cap_candidates(
    cities: list[CityOut], origin: Origin | None, limit: int = MAX_TAG_CANDIDATES
) -> list[CityOut]:
    if len(cities) <= limit:
        return cities
    if origin:
        ranked = sorted(cities, key=lambda c: haversine_km(origin.lat, origin.lon, c.lat, c.lon))
        near = ranked[:NEAR_CANDIDATES]
        return near + _round_robin_by_region(ranked[NEAR_CANDIDATES:], limit - len(near))
    return _round_robin_by_region(cities, limit)


def _candidate_line(city: CityOut, days: list[DailyWeather], distance_km: int | None) -> str:
    summary = weather.build_weather_summary(days)
    tags = "、".join(TAG_LABELS[t] for t in TAG_LABELS if t in city.tags)
    line = f"- id: {city.id} | {city.name_zh}({city.country}) | 建议游玩 {city.suggested_days} 天"
    if tags:
        line += f" | 标签: {tags}"  # 全球搜索来的动态城市没有标签,略过
    line += f" | 天气: {summary.summary_text}"
    if distance_km is not None:
        line += " | 用户就在此城市" if distance_km == 0 else f" | 距用户约 {distance_km} km"
    # 逐日概览:日期+天况 emoji,降雨概率 ≥40% 才标注,供 LLM 挑天气好的出发区间
    daily = " ".join(
        f"{d.date[5:]}{d.emoji}" + (f"雨{d.rain_prob}%" if (d.rain_prob or 0) >= 40 else "")
        for d in days
    )
    return f"{line}\n  逐日: {daily}"


def _build_pick_prompt(
    body: RecommendRequest,
    candidates: list[tuple[CityOut, list[DailyWeather]]],
    distances: dict[str, int] | None = None,
) -> str:
    trip_days = (body.end_date - body.start_date).days + 1
    distances = distances or {}
    lines = [_candidate_line(c, d, distances.get(c.id)) for c, d in candidates]
    if body.mode == "cities":
        intent = "用户主动选定了以下候选城市,请结合天气挑选其中最值得去的 1-3 个"
    else:
        labels = "、".join(TAG_LABELS[t] for t in body.tags if t in TAG_LABELS)
        intent = f"用户没有想好具体城市,偏好标签为「{labels}」,请从候选中推荐 1-3 个契合偏好且天气合适的目的地"

    origin_section = ""
    if body.origin:
        where = body.origin.name or f"{body.origin.lat:.1f}, {body.origin.lon:.1f}"
        origin_section = f"""
【用户出发地】{where}(已标注各候选城市与出发地的距离,请把路程纳入考量:短行程优先近处,长行程可以考虑更远的目的地)"""

    return f"""【有空的时间窗口】{body.start_date} 至 {body.end_date},共 {trip_days} 天(这只是用户有空的时间,不是行程长度,请按各城市建议游玩天数在窗口内安排)
【用户意图】{intent}{origin_section}

【候选城市与真实天气预报】
{chr(10).join(lines)}

请从中挑选 1-3 个最值得去的目的地,为每个城市在窗口内安排一段合理的连续出发区间,严格按以下 JSON 格式输出:
{{"picks": [{{"city_id": "候选中的 id", "trip_start": "YYYY-MM-DD", "trip_end": "YYYY-MM-DD", "reason": "1-2 句轻松口语化的推荐理由", "warning": "天气不佳时的提示,天气好则为 null"}}], "note": "若所有候选天气都很一般,在这里诚实说明,否则为 null"}}"""


def _resolve_trip_window(pick: LLMPick, body: RecommendRequest, city: CityOut) -> tuple[date, date]:
    """校验 LLM 给出的出发区间;缺失或越界时回退为「窗口起始 + 建议游玩天数」。"""
    if pick.trip_start and pick.trip_end and pick.trip_start <= pick.trip_end:
        if body.start_date <= pick.trip_start and pick.trip_end <= body.end_date:
            return pick.trip_start, pick.trip_end
    span = min(city.suggested_days, (body.end_date - body.start_date).days + 1)
    return body.start_date, body.start_date + timedelta(days=span - 1)


async def recommend(http: httpx.AsyncClient, llm, body: RecommendRequest) -> RecommendResponse:
    """获取推荐:拉天气 → LLM 挑选 → 组装卡片。llm 参数为注入的客户端(便于测试)。"""
    if body.mode == "cities":
        candidates = cities_by_ids(body.city_ids)
    else:
        candidates = _cap_candidates(cities_by_tags(body.tags), body.origin)

    if not candidates:
        return RecommendResponse(
            mode=body.mode, note="没有符合这些标签的城市,试试放宽条件", recommendations=[]
        )

    start, end = body.start_date.isoformat(), body.end_date.isoformat()

    distances: dict[str, int] | None = None
    if body.origin:
        o = body.origin
        distances = {c.id: haversine_km(o.lat, o.lon, c.lat, c.lon) for c in candidates}

    pairs = await asyncio.gather(*(_safe_weather(http, c, start, end) for c in candidates))
    available = [(c, d) for c, d in pairs if d]
    failed = len(pairs) - len(available)
    if not available:
        raise weather.WeatherServiceError("所有候选城市天气查询失败")

    data = await llm_client.chat_json(
        PICK_SYSTEM_PROMPT, _build_pick_prompt(body, available, distances), client=llm
    )
    result = LLMPickResult.model_validate(data)

    by_id = {c.id: (c, d) for c, d in available}
    cards: list[RecommendationCard] = []
    for pick in result.picks:
        entry = by_id.get(pick.city_id)
        if entry is None:  # 模型偶尔会编造 id,直接丢弃
            continue
        city, days = entry
        trip_start, trip_end = _resolve_trip_window(pick, body, city)
        # 卡片与攻略只覆盖安排的行程区间,窗口里剩余的日子留给用户自由支配
        sub_days = [d for d in days if trip_start.isoformat() <= d.date <= trip_end.isoformat()]
        cards.append(
            RecommendationCard(
                rank=len(cards) + 1,
                city=city,
                weather=weather.build_weather_summary(sub_days or days),
                reason=pick.reason,
                warning=pick.warning,
                matched_tags=_matched_tags(city, body.tags) if body.mode == "tags" else [],
                distance_km=distances.get(city.id) if distances else None,
                trip_start=trip_start,
                trip_end=trip_end,
            )
        )
        if len(cards) >= 3:
            break

    if not cards:
        raise llm_client.LLMError("模型未返回有效的推荐城市,请重试")

    notes = [result.note] if result.note else []
    if failed:
        notes.append("部分候选城市天气查询失败,已按剩余城市推荐")

    return RecommendResponse(
        mode=body.mode, note="；".join(notes) or None, recommendations=cards
    )
