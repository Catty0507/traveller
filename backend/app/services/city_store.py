import json
import logging
from functools import lru_cache
from pathlib import Path

from app.schemas.city import CityOut

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cities.json"
# 全球搜索发现的动态城市(id 以 om/nm 开头)登记在这里,重启不丢
DISCOVERED_PATH = DATA_PATH.parent / "discovered_cities.json"

TAGS = [
    {"id": "seaside", "label": "海边", "emoji": "🏖️"},
    {"id": "ancient_town", "label": "古镇", "emoji": "🏮"},
    {"id": "food", "label": "美食", "emoji": "🍜"},
    {"id": "nature", "label": "自然", "emoji": "🌲"},
    {"id": "family", "label": "亲子", "emoji": "🎢"},
    {"id": "culture", "label": "文化", "emoji": "🏛️"},
    {"id": "shopping", "label": "购物", "emoji": "🛍️"},
    {"id": "ski", "label": "滑雪", "emoji": "⛷️"},
]

TAG_LABELS = {t["id"]: t["label"] for t in TAGS}
TAG_IDS = set(TAG_LABELS)

# 用户选择户外类标签时,降雨警示需要更具体的提示
OUTDOOR_TAGS = {"seaside", "nature", "ski"}


@lru_cache
def load_cities() -> tuple[CityOut, ...]:
    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return tuple(CityOut(**item) for item in raw)


@lru_cache
def _index() -> dict[str, CityOut]:
    return {c.id: c for c in load_cities()}


_discovered: dict[str, CityOut] = {}
_discovered_loaded = False


def _load_discovered() -> None:
    global _discovered_loaded
    if _discovered_loaded:
        return
    _discovered_loaded = True
    if not DISCOVERED_PATH.exists():
        return
    try:
        with open(DISCOVERED_PATH, encoding="utf-8") as f:
            for item in json.load(f):
                city = CityOut(**item)
                _discovered[city.id] = city
    except (OSError, ValueError) as e:
        logger.warning("动态城市库加载失败,按空库处理: %s", e)


def record_discovered(cities: list[CityOut]) -> None:
    """把全球搜索发现的动态城市登记进内存与磁盘(幂等)。"""
    global _discovered_loaded
    _load_discovered()
    new = [c for c in cities if c.id not in _discovered]
    if not new:
        return
    for c in new:
        _discovered[c.id] = c
    try:
        data = [json.loads(c.model_dump_json()) for c in _discovered.values()]
        tmp = DISCOVERED_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DISCOVERED_PATH)
    except OSError as e:
        logger.warning("动态城市库写入失败(不影响本次使用): %s", e)


def get_city(city_id: str) -> CityOut | None:
    _load_discovered()
    return _index().get(city_id) or _discovered.get(city_id)


def search_cities(q: str | None = None, tag: str | None = None, limit: int = 100) -> list[CityOut]:
    """按关键词(中文名/英文名/国家)与标签过滤城市。"""
    keyword = (q or "").strip().lower()
    result: list[CityOut] = []
    for c in load_cities():
        if keyword and keyword not in c.name_zh.lower() and keyword not in c.name_en.lower() and keyword not in c.country.lower():
            continue
        if tag and tag not in c.tags:
            continue
        result.append(c)
        if len(result) >= limit:
            break
    return result


def cities_by_ids(city_ids: list[str]) -> list[CityOut]:
    """按 id 取城市,去重且保持用户给定的顺序。"""
    seen: set[str] = set()
    result: list[CityOut] = []
    for cid in city_ids:
        if cid in seen:
            continue
        seen.add(cid)
        city = get_city(cid)
        if city is not None:
            result.append(city)
    return result


def cities_by_tags(tags: list[str]) -> list[CityOut]:
    """标签筛选:命中任一标签即入选,命中越多排越前。"""
    wanted = set(tags)
    scored = [(len(set(c.tags) & wanted), c) for c in load_cities()]
    matched = [(n, c) for n, c in scored if n > 0]
    matched.sort(key=lambda pair: -pair[0])
    return [c for _, c in matched]
