from pydantic import BaseModel


class DailyWeather(BaseModel):
    date: str
    weather_code: int
    desc: str
    emoji: str
    t_max: float
    t_min: float
    rain_prob: int | None  # Open-Meteo 偶尔返回 null
    precip_mm: float


class WeatherSummary(BaseModel):
    summary_text: str
    avg_t_max: float
    avg_t_min: float
    rainy_days: int
    total_days: int
    days: list[DailyWeather]
