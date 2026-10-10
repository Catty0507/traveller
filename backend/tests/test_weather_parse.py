import pytest

from app.services.weather import (
    WeatherServiceError,
    build_weather_summary,
    describe_code,
    parse_forecast_json,
)

MOCK_FORECAST = {
    "daily": {
        "time": ["2026-10-10", "2026-10-11"],
        "weather_code": [0, 61],
        "temperature_2m_max": [24.1, 22.5],
        "temperature_2m_min": [16.3, 15.0],
        "precipitation_probability_max": [10, 80],
        "precipitation_sum": [0.0, 3.2],
    }
}


def test_parse_full_forecast():
    days = parse_forecast_json(MOCK_FORECAST)
    assert len(days) == 2
    assert days[0].date == "2026-10-10"
    assert days[0].desc == "晴"
    assert days[0].emoji == "☀️"
    assert days[0].t_max == 24.1
    assert days[0].rain_prob == 10
    assert days[1].desc == "小雨"


def test_parse_null_rain_prob():
    data = {
        "daily": {
            "time": ["2026-10-10"],
            "weather_code": [2],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [12.0],
            "precipitation_probability_max": [None],
            "precipitation_sum": [None],
        }
    }
    days = parse_forecast_json(data)
    assert days[0].rain_prob is None
    assert days[0].precip_mm == 0.0


def test_null_weather_code_tolerated():
    """远期日期或偏远点位 Open-Meteo 可能返回 null weather_code,不应崩溃。"""
    data = {
        "daily": {
            "time": ["2026-10-10", "2026-10-11"],
            "weather_code": [0, None],
            "temperature_2m_max": [24.1, 22.5],
            "temperature_2m_min": [16.3, 15.0],
            "precipitation_probability_max": [10, None],
            "precipitation_sum": [0.0, None],
        }
    }
    days = parse_forecast_json(data)
    assert days[1].weather_code == -1
    assert days[1].desc == "天气"
    assert days[1].emoji == "❓"


def test_unknown_weather_code():
    desc, emoji = describe_code(42)
    assert desc == "天气"
    assert emoji == "❓"


def test_error_payload_raises():
    with pytest.raises(WeatherServiceError):
        parse_forecast_json({"error": True, "reason": "Invalid coordinate"})


def test_build_weather_summary(make_day):
    days = [make_day(date="2026-10-10", code=0, t_max=24.0, t_min=16.0, rain_prob=10),
            make_day(date="2026-10-11", code=61, t_max=22.0, t_min=15.0, rain_prob=80, precip=3.0)]
    summary = build_weather_summary(days)
    assert summary.total_days == 2
    assert summary.rainy_days == 1
    assert "1 天可能有雨" in summary.summary_text
    assert "体感舒适" in summary.summary_text
