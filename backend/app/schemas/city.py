from pydantic import BaseModel


class CityOut(BaseModel):
    id: str
    name_zh: str
    name_en: str
    country: str
    region: str
    lat: float
    lon: float
    timezone: str
    summary: str
    suggested_days: int
    tags: list[str]
    cover_color: str


class CityListResponse(BaseModel):
    total: int
    cities: list[CityOut]


class TagOut(BaseModel):
    id: str
    label: str
    emoji: str


class TagsResponse(BaseModel):
    tags: list[TagOut]
