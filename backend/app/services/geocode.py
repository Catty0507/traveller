"""全球城市搜索(双源 + 中文兜底):

1. Open-Meteo Geocoding:结构化最好(人口/时区),中文只覆盖部分城市
2. Photon(Komoot, OSM 数据):本地名匹配,「大阪」这类汉字本地名可中搜
3. 两源都查不到的中文地名(如「马泰拉」),用 LLM 翻译成拉丁名再查一轮

动态城市 id 前缀 om/nm 与精选库区分,由 city_store 登记持久化。
"""

import asyncio
import logging
import re
import zlib

import httpx

from app.schemas.city import CityOut
from app.services import llm_client
from app.services.city_store import record_discovered
from app.services.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_OM_URL = "https://geocoding-api.open-meteo.com/v1/search"
_PHOTON_URL = "https://photon.komoot.io/api/"
# Photon 会封掉 python-httpx 等默认 UA(403),带上应用标识即可
_HEADERS = {"User-Agent": "traveller-app/1.0 (local travel guide)"}
_COVER_COLORS = ["emerald", "sky", "amber", "rose", "violet", "teal", "orange", "indigo"]
_PHOTON_PLACE_TYPES = {"city", "town", "village", "borough", "municipality", "region"}
_TYPE_RANK = {"city": 0, "town": 1, "municipality": 2, "borough": 2, "region": 3, "village": 4, "national_park": 5}

# 关键词级缓存:同一关键词(含兜底后的结果)一段时间内不打外部接口
_search_cache: TTLCache = TTLCache(maxsize=256, ttl=600.0)

_CJK = re.compile(r"[一-鿿]")
# 混排名中允许保留的字符:汉字/日文假名/拉丁字母(含重音)/数字/空格/常用连接符
_MIXED_KEEP = re.compile(r"[一-鿿ぁ-んァ-ヶÀ-ɏa-zA-Z0-9 ·\-']")
# 行政后缀(长词在前,保证「自治县」整体剥掉而不是只剥「县」)
_ADMIN_SUFFIX_RE = re.compile(r"(特别行政区|自治区|自治州|自治县|地区|省|市|县|区|镇|乡|村|町|盟)$")


def _clean_text(text: str) -> str:
    """清洗 OSM 混排地名。

    民族自治地方的 OSM name 常是「汉字 蒙文/藏文/维吾尔文」多语并排
    (如「河南县 ᠾᠧᠨᠠᠨ རྨ་ལྷོ།」),面向中文用户只保留汉字与拉丁部分;
    纯外文名(Zürich、ニセコ)原样保留,清洗后为空也原样兜底。
    """
    if not _CJK.search(text or ""):
        return (text or "").strip()
    kept = "".join(ch for ch in text if _MIXED_KEEP.fullmatch(ch))
    kept = re.sub(r"\s{2,}", " ", kept).strip()
    return kept or text.strip()


def normalize_admin_name(name: str) -> str:
    """去掉行政后缀用于去重比对:「重庆市」→「重庆」,「河南县」→「河南」。

    同一城市在精选库与搜索源里的叫法可能差一级行政后缀(重庆/重庆市、大阪/大阪市)。
    """
    stripped = _ADMIN_SUFFIX_RE.sub("", name)
    return stripped or name


def _cover_color(city_id: str) -> str:
    return _COVER_COLORS[zlib.crc32(city_id.encode()) % len(_COVER_COLORS)]


def _suggest_days(population: int | None) -> int:
    if population and population >= 5_000_000:
        return 4
    if population and population >= 1_000_000:
        return 3
    if population:
        return 2
    return 3


def _summary(admin1: str | None, population: int | None) -> str:
    bits = []
    if admin1:
        bits.append(admin1)
    if population and population >= 10000:
        bits.append(f"人口约 {population // 10000} 万")
    return " · ".join(bits) if bits else "来自全球城市库的旅行目的地"


def _om_parse(zh_results: list[dict], en_results: list[dict]) -> list[CityOut]:
    """Open-Meteo GeoNames 结果 → 城市列表(纯函数)。"""
    en_by_id = {r["id"]: r for r in en_results}
    cities = []
    for r in zh_results:
        if not str(r.get("feature_code", "")).startswith("P"):  # 只要人口聚居地
            continue
        en = en_by_id.get(r["id"])
        cid = f"om{r['id']}"
        cities.append(
            CityOut(
                id=cid,
                name_zh=r.get("name") or (en or {}).get("name") or cid,
                name_en=(en or {}).get("name") or r.get("name") or cid,
                country=r.get("country") or (en or {}).get("country") or "",
                region="全球",
                lat=r["latitude"],
                lon=r["longitude"],
                timezone=r.get("timezone") or "auto",
                summary=_summary(r.get("admin1"), r.get("population")),
                suggested_days=_suggest_days(r.get("population")),
                tags=[],  # 动态城市不参与标签推荐,只按用户主动选择进入候选
                cover_color=_cover_color(cid),
            )
        )
    return cities


def _photon_parse(payload: dict) -> list[CityOut]:
    """Photon GeoJSON 结果 → 城市列表(纯函数)。coordinates 为 [lon, lat]。"""
    scored: list[tuple[int, CityOut]] = []
    for f in payload.get("features") or []:
        p = f.get("properties") or {}
        osm_value = p.get("osm_value") or ""
        is_place = p.get("osm_key") == "place" and osm_value in _PHOTON_PLACE_TYPES
        # 国家公园(九寨沟/班夫等)与景区型 place=region(五渔村等)也是旅行目的地
        is_park = p.get("osm_key") == "boundary" and osm_value == "national_park"
        if not (is_place or is_park):
            continue  # 过滤车站/POI/街道等非目的地条目
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        name = _clean_text(p.get("name") or p.get("city") or "")
        if lat is None or lon is None or not name:
            continue
        cid = f"nm{p.get('osm_type', 'X')}{p.get('osm_id')}"
        state = _clean_text(p.get("state") or "")
        country = p.get("country") or ""
        city = CityOut(
            id=cid,
            name_zh=name,
            name_en=name,
            country=country,
            region="全球",
            lat=float(lat),
            lon=float(lon),
            timezone="auto",  # 天气服务按坐标用 timezone=auto 自解析
            summary=state if state and state != name else f"{country}的旅行目的地",
            suggested_days=3,
            tags=[],
            cover_color=_cover_color(cid),
        )
        # 同名条目里大城市(市/镇)排在村庄、保护区前面
        scored.append((_TYPE_RANK.get(osm_value, 9), city))
    scored.sort(key=lambda pair: pair[0])
    return [c for _, c in scored]


async def _om_to_cities(http: httpx.AsyncClient, keyword: str, limit: int) -> list[CityOut]:
    params = {"name": keyword, "count": limit, "format": "json"}
    zh_resp, en_resp = await asyncio.gather(
        http.get(_OM_URL, params={**params, "language": "zh"}),
        http.get(_OM_URL, params={**params, "language": "en"}),
    )
    zh_resp.raise_for_status()
    en_resp.raise_for_status()
    return _om_parse(
        zh_resp.json().get("results") or [],
        en_resp.json().get("results") or [],
    )


async def _photon_to_cities(http: httpx.AsyncClient, keyword: str, limit: int) -> list[CityOut]:
    resp = await http.get(_PHOTON_URL, params={"q": keyword, "limit": limit}, headers=_HEADERS)
    resp.raise_for_status()
    return _photon_parse(resp.json())


async def _translate_to_latin(keyword: str) -> list[str]:
    """中文地名 → 拉丁字母名(如 马泰拉 → Matera)。失败返回空。"""
    system = (
        "你是地名翻译助手。把用户输入的地名翻译成该地点最通用的拉丁字母名称"
        "(当地名或英文名,最多 2 个候选)。只输出 JSON:"
        '{"candidates": ["名称1", "名称2"]}'
    )
    try:
        data = await llm_client.chat_json(system, keyword)
        names = [str(n).strip() for n in data.get("candidates", [])]
        return [n for n in names if n and n.isascii()][:2]
    except Exception as e:  # noqa: BLE001 翻译只是兜底,失败按查不到处理
        logger.warning("地名翻译兜底失败: %s: %s", type(e).__name__, e)
        return []


def _merge_dedupe(sources: list[list[CityOut] | Exception], limit: int) -> list[CityOut]:
    """多源轮询交错合并,去重(0.1° 网格坐标为同一城市)。

    轮流取各源的结果,避免单源条目占满 limit 导致其他源被整体截断;
    单源失败不影响其他源。
    """
    from collections import deque

    merged: list[CityOut] = []
    seen: set[tuple[float, float]] = set()
    queues = [deque(s) for s in sources if not isinstance(s, Exception)]
    for source in sources:
        if isinstance(source, Exception):
            logger.warning("全球城市源查询失败: %s: %s", type(source).__name__, source)
    while len(merged) < limit and queues:
        for q in queues:
            if len(merged) >= limit:
                break
            if not q:
                continue
            c = q.popleft()
            key = (round(c.lat, 1), round(c.lon, 1))
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)
        queues = [q for q in queues if q]
    return merged


async def _fetch_merged(http: httpx.AsyncClient, keyword: str, limit: int) -> list[CityOut]:
    om, ph = await asyncio.gather(
        _om_to_cities(http, keyword, limit),
        _photon_to_cities(http, keyword, limit),
        return_exceptions=True,
    )
    return _merge_dedupe([om, ph], limit)


async def search_global(http: httpx.AsyncClient, keyword: str, limit: int = 8) -> list[CityOut]:
    """按关键词搜索全球城市。单源失败已在此降级,调用方仍可整体兜底。"""
    q = keyword.strip()
    if not q:
        return []

    async def _factory() -> list[CityOut]:
        cities = await _fetch_merged(http, q, limit)
        if not cities and _CJK.search(q):
            # 中文长尾地名:翻译成拉丁名再查一轮(如 马泰拉 → Matera)
            for latin in await _translate_to_latin(q):
                cities = await _fetch_merged(http, latin, limit)
                if cities:
                    break
        record_discovered(cities)
        return cities

    return await _search_cache.get_or_set(q.lower(), _factory)
