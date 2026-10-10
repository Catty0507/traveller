from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.guide import DayPlan
from app.schemas.recommend import Origin, validate_trip_dates


class DriveRequest(BaseModel):
    """自驾规划请求:在用户的空闲时间窗口内,安排从出发地到目的地的自驾。

    出发地必须有(自驾没有起点就无从规划);原计划的游玩区间
    (推荐结果安排的 trip_start/trip_end)仅作参考传给大模型。
    """

    city_id: str
    start_date: date
    end_date: date
    origin: Origin | None = None
    trip_start: date | None = None
    trip_end: date | None = None
    user_tags: list[str] = []

    @model_validator(mode="after")
    def check(self) -> "DriveRequest":
        validate_trip_dates(self.start_date, self.end_date)
        if not self.city_id.strip():
            raise ValueError("city_id 不能为空")
        if self.origin is None:
            raise ValueError("自驾规划需要出发地,请先在输入区设置「出发地」再重新推荐")
        # 原计划区间缺一边或乱序时直接忽略,不影响规划
        if not (self.trip_start and self.trip_end) or self.trip_end < self.trip_start:
            self.trip_start = self.trip_end = None
        return self


# ---- LLM 结构化输出模型 ----


class RouteLeg(BaseModel):
    title: str = Field(description="如「去程」「返程」")
    desc: str = Field(description="路线走法:大方向、主要道路或途经城镇,1-2 句")


class Rental(BaseModel):
    name: str = Field(description="租车公司/平台名")
    desc: str = Field(description="一句话定位描述")


class DriveTipItem(BaseModel):
    category: Literal["路线", "驾驶", "天气", "费用", "其他"]
    text: str


class DrivePlan(BaseModel):
    """自驾方案:mode=drive 为往返自驾玩法,mode=rental 为目的地租车建议。"""

    mode: Literal["drive", "rental"]
    summary: str = Field(description="一句话结论,说清为什么这么安排")
    total_km: int | None = Field(None, description="往返总里程(drive 时提供)")
    total_drive_hours: float | None = Field(None, description="往返纯驾驶小时数(drive 时提供)")
    depart_date: str | None = Field(None, description="建议出发日,格式 MM-DD")
    return_date: str | None = Field(None, description="建议返程日,格式 MM-DD")
    route: list[RouteLeg] = []
    daily_plan: list[DayPlan] = Field(description="逐日安排(drive 覆盖整个窗口;rental 为当地自驾玩法)")
    rentals: list[Rental] = []
    tips: list[DriveTipItem] = []


class DriveResponse(BaseModel):
    city_id: str
    city_name_zh: str
    origin_name: str
    start_date: date
    end_date: date
    distance_km: int  # 出发地到目的地的直线距离
    est_drive_km: int  # 按公路系数估算的单程里程
    est_drive_hours: float  # 估算的单程纯驾驶小时数
    weather_brief: str
    plan: DrivePlan
