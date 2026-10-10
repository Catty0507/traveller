import logging

from fastapi import APIRouter, Query, Request

from app.schemas.city import CityListResponse, TagOut, TagsResponse
from app.services import geocode
from app.services.city_store import TAGS, load_cities, search_cities
from app.services.geocode import normalize_admin_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cities"])


@router.get("/cities", response_model=CityListResponse)
def list_cities(
    q: str | None = Query(default=None, description="按中文名/英文名/国家模糊搜索"),
    tag: str | None = Query(default=None, description="按标签 id 过滤"),
    limit: int = Query(default=500, ge=1, le=500),
):
    cities = search_cities(q=q, tag=tag, limit=limit)
    return CityListResponse(total=len(cities), cities=cities)


@router.get("/cities/search", response_model=CityListResponse)
async def search_global_cities(
    request: Request,
    q: str = Query(..., min_length=1, max_length=60, description="全球城市关键词"),
    limit: int = Query(default=8, ge=1, le=20),
):
    """全球城市搜索:精选库优先,再补双源全球库(Open-Meteo + Photon),中文查不到时由大模型翻译后复查;故障时降级为仅精选结果。"""
    q = q.strip()
    curated = search_cities(q=q, limit=5)
    try:
        found = await geocode.search_global(request.app.state.http, q, limit=limit)
    except Exception as e:  # noqa: BLE001 降级为精选结果,不让搜索整个失败
        logger.warning("全球城市搜索失败,降级为精选结果: %s: %s", type(e).__name__, e)
        found = []

    seen = {c.id for c in curated}
    known = {(c.name_zh, c.country) for c in load_cities()}  # 精选库已有的不再重复展示
    # 「重庆市」「大阪市」与精选库的「重庆」「大阪」是同一城市,去掉行政后缀再比一次
    known_norm = {(normalize_admin_name(c.name_zh), c.country) for c in load_cities()}
    merged = curated + [
        c
        for c in found
        if c.id not in seen
        and (c.name_zh, c.country) not in known
        and (normalize_admin_name(c.name_zh), c.country) not in known_norm
    ]
    return CityListResponse(total=len(merged), cities=merged)


@router.get("/tags", response_model=TagsResponse)
def list_tags():
    return TagsResponse(tags=[TagOut(**t) for t in TAGS])
