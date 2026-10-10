from fastapi import APIRouter, HTTPException, Request

from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services import llm_client, recommender
from app.services.city_store import TAG_IDS, get_city
from app.services.weather import WeatherServiceError

router = APIRouter(prefix="/api", tags=["recommend"])


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest, request: Request):
    # 候选合法性校验(城市/标签必须真实存在)
    if body.mode == "cities":
        unknown = [cid for cid in body.city_ids if get_city(cid) is None]
        if unknown:
            raise HTTPException(status_code=422, detail=f"包含未知城市: {', '.join(unknown)}")
    else:
        unknown = [t for t in body.tags if t not in TAG_IDS]
        if unknown:
            raise HTTPException(status_code=422, detail=f"包含未知标签: {', '.join(unknown)}")

    try:
        return await recommender.recommend(request.app.state.http, None, body)
    except llm_client.LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except llm_client.LLMError:
        raise HTTPException(status_code=502, detail="推荐生成失败,请稍后重试")
    except WeatherServiceError:
        raise HTTPException(status_code=503, detail="天气服务暂不可用,请稍后再试")
