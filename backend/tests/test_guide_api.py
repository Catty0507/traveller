from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.weather import DailyWeather
from app.services.weather import describe_code


def make_days(start: str, count: int):
    desc, emoji = describe_code(0)
    base = date.fromisoformat(start)
    return [
        DailyWeather(
            date=(base + timedelta(days=i)).isoformat(),
            weather_code=0,
            desc=desc,
            emoji=emoji,
            t_max=24.0,
            t_min=16.0,
            rain_prob=10,
            precip_mm=0.0,
        )
        for i in range(count)
    ]


@pytest.fixture
def sunny_weather(monkeypatch):
    async def fake_weather(client, lat, lon, start, end):
        span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        return make_days(start, span)

    monkeypatch.setattr("app.services.weather.get_daily_weather", fake_weather)


GUIDE_JSON = {
    "overview": "三天正好把西湖和运河各安排一天。",
    "attractions": [
        {"name": "西湖", "highlight": "环湖步行", "duration": "半天", "tip": "清晨人少"}
    ],
    "daily_plan": [
        {"day": 1, "date": "10-10", "title": "湖滨线", "items": ["断桥", "白堤", "平湖秋月"]},
        {"day": 2, "date": "10-11", "title": "禅茶线", "items": ["灵隐寺", "飞来峰", "龙井村"]},
        {"day": 3, "date": "10-12", "title": "运河线", "items": ["拱宸桥", "小河直街", "桥西历史街区"]},
    ],
    "food": [{"name": "东坡肉", "desc": "浓油赤酱"}],
    "tips": [{"category": "穿衣", "text": "均温 16~24°C,带薄外套"}],
}


def trip_dates(days: int = 3, offset: int = 1):
    start = date.today() + timedelta(days=offset)
    return start.isoformat(), (start + timedelta(days=days - 1)).isoformat()


def test_guide_success(sunny_weather, monkeypatch):
    async def fake_chat_json(system, user, client=None):
        return GUIDE_JSON

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/guide",
            json={"city_id": "hangzhou", "start_date": start, "end_date": end, "user_tags": ["nature"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["city_id"] == "hangzhou"
    assert body["weather_brief"]
    assert body["guide"]["overview"]
    assert body["guide"]["daily_plan"][0]["day"] == 1


def test_guide_invalid_llm_format_retries_then_502(sunny_weather, monkeypatch):
    calls = {"n": 0}

    async def fake_chat_json(system, user, client=None):
        calls["n"] += 1
        return {"unexpected": "shape"}

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates(offset=2)  # 用不同日期避开缓存
    with TestClient(app) as c:
        resp = c.post("/api/guide", json={"city_id": "hangzhou", "start_date": start, "end_date": end})
    assert resp.status_code == 502
    assert calls["n"] == 2  # 校验失败重试了一次


def test_guide_unknown_city_422(sunny_weather, monkeypatch):
    start, end = trip_dates(offset=3)
    with TestClient(app) as c:
        resp = c.post("/api/guide", json={"city_id": "atlantis", "start_date": start, "end_date": end})
    assert resp.status_code == 422


def test_guide_llm_error_502(sunny_weather, monkeypatch):
    from app.services.llm_client import LLMError

    async def fake_chat_json(system, user, client=None):
        raise LLMError("大模型调用失败")

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates(offset=4)
    with TestClient(app) as c:
        resp = c.post("/api/guide", json={"city_id": "hangzhou", "start_date": start, "end_date": end})
    assert resp.status_code == 502
