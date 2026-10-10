from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.recommend import validate_trip_dates


class GuideRequest(BaseModel):
    city_id: str
    start_date: date
    end_date: date
    user_tags: list[str] = []

    @model_validator(mode="after")
    def check(self) -> "GuideRequest":
        validate_trip_dates(self.start_date, self.end_date)
        if not self.city_id.strip():
            raise ValueError("city_id 不能为空")
        return self


# ---- LLM 结构化输出模型 ----


class Attraction(BaseModel):
    name: str = Field(description="景点名称")
    highlight: str = Field(description="一句话亮点介绍")
    duration: str = Field(description="建议游玩时长,如「半天」")
    tip: str = Field(description="一条实用小贴士")


class DayPlan(BaseModel):
    day: int = Field(description="第几天,从 1 开始")
    date: str = Field(description="日期,格式 MM-DD")
    title: str = Field(description="当天主题")
    items: list[str] = Field(description="当天行程点,3-5 个")


class FoodItem(BaseModel):
    name: str
    desc: str


class TipItem(BaseModel):
    category: Literal["穿衣", "雨具", "交通", "门票", "其他"]
    text: str


class GuideOutput(BaseModel):
    """LLM 攻略输出 schema(messages.parse 的 output_format)。"""

    overview: str = Field(description="2-3 句轻松的开场总览")
    attractions: list[Attraction] = Field(description="3-5 个推荐景点")
    daily_plan: list[DayPlan] = Field(description="逐日行程,天数必须等于行程天数")
    food: list[FoodItem] = Field(description="3-6 个必吃美食")
    tips: list[TipItem] = Field(description="3-6 条贴士,穿衣/雨具必须引用真实天气")


class GuideResponse(BaseModel):
    city_id: str
    city_name_zh: str
    start_date: date
    end_date: date
    weather_brief: str
    guide: GuideOutput
