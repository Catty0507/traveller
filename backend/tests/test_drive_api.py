from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app


def make_days(start: str, count: int, code: int = 0, t_max: float = 24.0, t_min: float = 16.0):
    from app.schemas.weather import DailyWeather
    from app.services.weather import describe_code

    desc, emoji = describe_code(code)
    base = date.fromisoformat(start)
    return [
        DailyWeather(
            date=(base + timedelta(days=i)).isoformat(),
            weather_code=code,
            desc=desc,
            emoji=emoji,
            t_max=t_max,
            t_min=t_min,
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


def window(days: int = 5, offset: int = 1) -> tuple[str, str]:
    start = date.today() + timedelta(days=offset)
    return start.isoformat(), (start + timedelta(days=days - 1)).isoformat()


def test_drive_plan_ok(sunny_weather, monkeypatch):
    """出发地+时间充裕:返回往返自驾方案,提示词带上出发地与距离参考。"""
    captured = {}

    async def fake_chat_json(system, user, client=None):
        captured["prompt"] = user
        return {
            "mode": "drive",
            "summary": "时间宽裕,帮你安排往返自驾",
            "total_km": 500,
            "total_drive_hours": 7.0,
            "depart_date": "10-12",
            "return_date": "10-15",
            "route": [{"title": "去程", "desc": "走 G56 杭瑞高速,途经临安"}],
            "daily_plan": [
                {"day": 1, "date": "10-12", "title": "出发上山", "items": ["杭州出发", "服务区休息", "傍晚到汤口镇"]},
                {"day": 2, "date": "10-13", "title": "黄山一日", "items": ["云谷索道", "光明顶", "西海大峡谷"]},
            ],
            "rentals": [],
            "tips": [{"category": "天气", "text": "全程晴天,山路注意早晚温差"}],
        }

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = window()
    with TestClient(app) as c:
        resp = c.post(
            "/api/drive",
            json={
                "city_id": "huangshan",
                "start_date": start,
                "end_date": end,
                "origin": {"lat": 30.2741, "lon": 120.1551, "name": "杭州"},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["city_name_zh"] == "黄山"
    assert body["origin_name"] == "杭州"
    assert body["plan"]["mode"] == "drive"
    assert body["plan"]["total_km"] == 500
    assert body["distance_km"] > 0
    assert body["est_drive_km"] > body["distance_km"]  # 公路系数
    assert body["weather_brief"]
    # 出发地、距离参考、窗口天数都进入了提示词
    assert "【出发地】杭州" in captured["prompt"]
    assert "【距离参考】" in captured["prompt"]
    assert "共 5 天" in captured["prompt"]


def drive_request_body(start: str, end: str) -> dict:
    return {
        "city_id": "huangshan",
        "start_date": start,
        "end_date": end,
        "origin": {"lat": 18.25, "lon": 109.51, "name": "三亚"},
    }


def test_drive_rental_mode(sunny_weather, monkeypatch):
    """时间装不下往返自驾:改推目的地租车。"""

    async def fake_chat_json(system, user, client=None):
        return {
            "mode": "rental",
            "summary": "单程就要开 20 小时,建议飞过去租车",
            "daily_plan": [],
            "rentals": [
                {"name": "神州租车", "desc": "连锁网点多,机场取车方便"},
                {"name": "一嗨租车", "desc": "车型选择丰富,价格透明"},
            ],
            "tips": [{"category": "费用", "text": "异地还车费一般 300-500 元"}],
        }

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = window(days=2)
    with TestClient(app) as c:
        resp = c.post("/api/drive", json=drive_request_body(start, end))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["mode"] == "rental"
    assert len(body["plan"]["rentals"]) == 2
    assert body["plan"]["daily_plan"] == []


def test_drive_requires_origin(sunny_weather):
    """没给出发地 → 422,提示先设置出发地。"""
    start, end = window()
    with TestClient(app) as c:
        resp = c.post("/api/drive", json={"city_id": "huangshan", "start_date": start, "end_date": end})
    assert resp.status_code == 422
    assert "出发地" in resp.json()["detail"]


def test_drive_unknown_city_422(sunny_weather):
    start, end = window()
    with TestClient(app) as c:
        resp = c.post(
            "/api/drive",
            json={**drive_request_body(start, end), "city_id": "atlantis", "origin": {"lat": 30.0, "lon": 120.0, "name": "杭州"}},
        )
    assert resp.status_code == 422
    assert "atlantis" in resp.json()["detail"]


def test_drive_bad_mode_502(sunny_weather, monkeypatch):
    """LLM 返回非法 mode → 校验失败重试后 502。"""

    async def fake_chat_json(system, user, client=None):
        return {"mode": "boat", "summary": "坐船去"}

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = window()
    with TestClient(app) as c:
        resp = c.post("/api/drive", json=drive_request_body(start, end))
    assert resp.status_code == 502


def test_drive_drive_mode_without_daily_plan_502(sunny_weather, monkeypatch):
    """mode=drive 却没有 daily_plan → 重试后 502。"""

    async def fake_chat_json(system, user, client=None):
        return {"mode": "drive", "summary": "方案", "daily_plan": [], "rentals": [], "tips": []}

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = window()
    with TestClient(app) as c:
        resp = c.post("/api/drive", json=drive_request_body(start, end))
    assert resp.status_code == 502


def test_drive_past_date_422(sunny_weather):
    start = (date.today() - timedelta(days=1)).isoformat()
    end = date.today().isoformat()
    with TestClient(app) as c:
        resp = c.post("/api/drive", json=drive_request_body(start, end))
    assert resp.status_code == 422
    assert "不能早于今天" in resp.json()["detail"]
