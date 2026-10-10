import httpx
from statistics import mean

from app.config import get_settings
from app.schemas.weather import DailyWeather, WeatherSummary
from app.services.ttl_cache import TTLCache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_FIELDS = (
    "temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,precipitation_sum,weather_code"
)

# WMO weather interpretation codes → (中文描述, emoji)
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("晴", "☀️"),
    1: ("基本晴", "🌤️"),
    2: ("局部多云", "⛅"),
    3: ("阴", "☁️"),
    45: ("有雾", "🌫️"),
    48: ("雾凇", "🌫️"),
    51: ("毛毛雨", "🌦️"),
    53: ("毛毛雨", "🌦️"),
    55: ("浓毛毛雨", "🌦️"),
    56: ("冻毛毛雨", "🧊"),
    57: ("冻毛毛雨", "🧊"),
    61: ("小雨", "🌦️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("冻雨", "🧊"),
    67: ("冻雨", "🧊"),
    71: ("小雪", "🌨️"),
    73: ("中雪", "🌨️"),
    75: ("大雪", "❄️"),
    77: ("雪粒", "🌨️"),
    80: ("阵雨", "🌦️"),
    81: ("阵雨", "🌦️"),
    82: ("强阵雨", "🌧️"),
    85: ("阵雪", "🌨️"),
    86: ("阵雪", "❄️"),
    95: ("雷阵雨", "⛈️"),
    96: ("雷阵雨伴冰雹", "⛈️"),
    99: ("雷阵雨伴冰雹", "⛈️"),
}

THUNDERSTORM_CODES = {95, 96, 99}


def describe_code(code: int) -> tuple[str, str]:
    return WEATHER_CODES.get(code, ("天气", "❓"))


class WeatherServiceError(Exception):
    """天气服务不可用或返回异常。"""


def parse_forecast_json(data: dict) -> list[DailyWeather]:
    """解析 Open-Meteo forecast 响应中的 daily 部分(纯函数,便于单测)。"""
    if data.get("error"):
        raise WeatherServiceError(f"天气服务返回错误: {data.get('reason', '未知原因')}")

    daily = data.get("daily") or {}
    times = daily.get("time") or []
    codes = daily.get("weather_code") or []
    t_max_list = daily.get("temperature_2m_max") or []
    t_min_list = daily.get("temperature_2m_min") or []
    rain_prob_list = daily.get("precipitation_probability_max") or []
    precip_list = daily.get("precipitation_sum") or []

    result: list[DailyWeather] = []
    for i, day in enumerate(times):
        # Open-Meteo 对部分偏远点位/远期日期会返回 null,统一按未知天气处理
        code = int(codes[i]) if i < len(codes) and codes[i] is not None else -1
        desc, emoji = describe_code(code)
        rain_prob = rain_prob_list[i] if i < len(rain_prob_list) else None
        precip = precip_list[i] if i < len(precip_list) else None
        result.append(
            DailyWeather(
                date=day,
                weather_code=code,
                desc=desc,
                emoji=emoji,
                t_max=float(t_max_list[i]) if i < len(t_max_list) and t_max_list[i] is not None else 0.0,
                t_min=float(t_min_list[i]) if i < len(t_min_list) and t_min_list[i] is not None else 0.0,
                rain_prob=int(rain_prob) if rain_prob is not None else None,
                precip_mm=float(precip) if precip is not None else 0.0,
            )
        )
    return result


async def _fetch_daily(client: httpx.AsyncClient, lat: float, lon: float, start: str, end: str) -> list[DailyWeather]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
        "daily": DAILY_FIELDS,
    }
    last_error: Exception | None = None
    for _ in range(2):  # 简单重试一次
        try:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            return parse_forecast_json(resp.json())
        except WeatherServiceError:
            raise  # 业务错误(如坐标无效)重试无意义
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ValueError, TypeError) as e:
            last_error = e
    raise WeatherServiceError(f"天气请求失败: {last_error}") from last_error


async def get_daily_weather(
    client: httpx.AsyncClient, lat: float, lon: float, start: str, end: str
) -> list[DailyWeather]:
    """查询逐日天气,带 TTL 缓存。start/end 为 YYYY-MM-DD 字符串。"""
    settings = get_settings()
    cache = _weather_cache(settings.weather_cache_ttl_seconds)
    key = (round(lat, 3), round(lon, 3), start, end)
    return await cache.get_or_set(key, lambda: _fetch_daily(client, lat, lon, start, end))


_cache_instances: dict[int, TTLCache] = {}


def _weather_cache(ttl: int) -> TTLCache:
    if ttl not in _cache_instances:
        _cache_instances[ttl] = TTLCache(maxsize=500, ttl=float(ttl))
    return _cache_instances[ttl]


# ---- 天气摘要(推荐卡片与 LLM prompt 共用) ----


def _temp_comment(avg_mid: float) -> str:
    if avg_mid >= 30:
        return "气温偏高"
    if avg_mid < 10:
        return "气温偏低"
    if 16 <= avg_mid <= 26:
        return "体感舒适"
    return "温度尚可"


def build_weather_summary(days: list[DailyWeather]) -> WeatherSummary:
    """把逐日天气压缩成一句话摘要 + 逐日明细。"""
    total = len(days)
    rainy = sum(1 for d in days if (d.rain_prob is not None and d.rain_prob >= 50) or d.precip_mm >= 1.0)
    avg_t_max = round(mean(d.t_max for d in days), 1) if days else 0.0
    avg_t_min = round(mean(d.t_min for d in days), 1) if days else 0.0
    avg_mid = (avg_t_max + avg_t_min) / 2
    summary_text = (
        f"{total} 天中 {rainy} 天可能有雨,均温 {avg_t_min:.0f}~{avg_t_max:.0f}°C,{_temp_comment(avg_mid)}"
    )
    return WeatherSummary(
        summary_text=summary_text,
        avg_t_max=avg_t_max,
        avg_t_min=avg_t_min,
        rainy_days=rainy,
        total_days=total,
        days=days,
    )
