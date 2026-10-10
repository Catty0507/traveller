from datetime import date, timedelta

from pydantic import BaseModel, Field, model_validator

from app.schemas.city import CityOut
from app.schemas.weather import WeatherSummary

# Open-Meteo 免费预报最多支持未来 16 天(今天 + 15)
MAX_FORECAST_OFFSET = 15


def validate_trip_dates(start: date, end: date) -> None:
    """行程日期公共校验,recommend 与 guide 共用。

    不单独限制行程跨度:结束日期被预报窗口封顶,跨度自然最多 16 天。
    """
    today = date.today()
    if start < today:
        raise ValueError("出发日期不能早于今天")
    if end < start:
        raise ValueError("结束日期不能早于出发日期")
    if end > today + timedelta(days=MAX_FORECAST_OFFSET):
        raise ValueError(f"日期最晚支持到 {today + timedelta(days=MAX_FORECAST_OFFSET)}(天气预报最多 16 天)")


class Origin(BaseModel):
    """用户当前所在地(浏览器定位或手动选择),用于把路程纳入推荐考量。"""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    name: str | None = Field(None, max_length=40)  # 定位失败时可为空,只按坐标算距离


class RecommendRequest(BaseModel):
    mode: str  # "cities" | "tags"
    start_date: date
    end_date: date
    city_ids: list[str] = []
    tags: list[str] = []
    origin: Origin | None = None

    @model_validator(mode="after")
    def check(self) -> "RecommendRequest":
        if self.mode not in ("cities", "tags"):
            raise ValueError("mode 必须是 cities 或 tags")
        validate_trip_dates(self.start_date, self.end_date)
        if self.mode == "cities" and not 1 <= len(self.city_ids) <= 10:
            raise ValueError("请选择 1-10 个候选城市")
        if self.mode == "tags" and not 1 <= len(self.tags) <= 4:
            raise ValueError("请选择 1-4 个偏好标签")
        return self


class RecommendationCard(BaseModel):
    rank: int
    city: CityOut
    weather: WeatherSummary
    reason: str
    warning: str | None
    matched_tags: list[str]
    distance_km: int | None = None  # 与用户出发地的直线距离,未提供出发地时为 null
    trip_start: date | None = None  # 实际安排的行程区间(窗口内的一段,不必填满窗口)
    trip_end: date | None = None


class LLMPick(BaseModel):
    """LLM 返回的单个推荐项。trip_start/trip_end 为窗口内安排的出发区间。"""

    city_id: str
    reason: str
    warning: str | None = None
    trip_start: date | None = None
    trip_end: date | None = None


class LLMPickResult(BaseModel):
    """LLM 推荐结果的解析目标。"""

    picks: list[LLMPick]
    note: str | None = None


class RecommendResponse(BaseModel):
    mode: str
    note: str | None
    recommendations: list[RecommendationCard]
