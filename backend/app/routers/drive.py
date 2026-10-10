from fastapi import APIRouter, HTTPException, Request

from app.schemas.drive import DriveRequest, DriveResponse
from app.services import drive_llm, llm_client
from app.services.city_store import get_city
from app.services.weather import WeatherServiceError

router = APIRouter(prefix="/api", tags=["drive"])


@router.post("/drive", response_model=DriveResponse)
async def drive(body: DriveRequest, request: Request):
    city = get_city(body.city_id)
    if city is None:
        raise HTTPException(status_code=422, detail=f"未知城市: {body.city_id}")

    try:
        return await drive_llm.generate_drive(city, body, request.app.state.http, None)
    except llm_client.LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except llm_client.LLMError:
        raise HTTPException(status_code=502, detail="自驾方案生成失败,请稍后重试")
    except WeatherServiceError:
        raise HTTPException(status_code=503, detail="天气服务暂不可用,请稍后再试")
