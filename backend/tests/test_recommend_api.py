from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.weather import DailyWeather
from app.services.weather import describe_code


def make_days(start: str, count: int, code: int = 0, t_max: float = 24.0, t_min: float = 16.0):
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


@pytest.fixture
def fake_llm(monkeypatch):
    """返回一个安装函数,用于指定 LLM 应返回的 picks。"""

    def _install(picks: list[dict]):
        async def fake_chat_json(system, user, client=None):
            return {"picks": picks, "note": None}

        monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)

    return _install


def trip_dates(days: int = 3, offset: int = 1):
    start = date.today() + timedelta(days=offset)
    return start.isoformat(), (start + timedelta(days=days - 1)).isoformat()


def test_recommend_cities_mode(sunny_weather, fake_llm):
    fake_llm([{"city_id": "hangzhou", "reason": "天气晴朗,适合游西湖", "warning": None}])
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou", "chengdu"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 1
    card = body["recommendations"][0]
    assert card["rank"] == 1
    assert card["city"]["id"] == "hangzhou"
    assert card["reason"]
    assert card["warning"] is None
    assert card["weather"]["total_days"] == 3
    assert card["distance_km"] is None  # 未提供出发地时不返回距离


def test_haversine_known_distances():
    from app.services.geo import haversine_km

    hz = (30.2741, 120.1551)  # 杭州
    assert haversine_km(*hz, *hz) == 0
    d = haversine_km(*hz, 31.2304, 121.4737)  # 上海,实际约 165 km
    assert 140 <= d <= 190


def test_recommend_with_origin_distance(sunny_weather, monkeypatch):
    captured = {}

    async def fake_chat_json(system, user, client=None):
        captured["prompt"] = user
        return {"picks": [{"city_id": "hangzhou", "reason": "就在家门口", "warning": None}], "note": None}

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={
                "mode": "cities",
                "city_ids": ["hangzhou", "paris"],
                "start_date": start,
                "end_date": end,
                "origin": {"lat": 30.2741, "lon": 120.1551, "name": "杭州"},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    hang = next(r for r in body["recommendations"] if r["city"]["id"] == "hangzhou")
    assert hang["distance_km"] == 0
    # 出发地与距离标注都进入了 LLM 提示词
    assert "【用户出发地】杭州" in captured["prompt"]
    assert "用户就在此城市" in captured["prompt"]
    assert "距用户约" in captured["prompt"]  # 巴黎的距离标注


def test_recommend_tags_mode_returns_matched_tags(sunny_weather, fake_llm):
    fake_llm([{"city_id": "sanya", "reason": "阳光海滩", "warning": None}])
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "tags", "tags": ["seaside", "family"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 200
    card = resp.json()["recommendations"][0]
    assert card["city"]["id"] == "sanya"
    assert "海边" in card["matched_tags"]
    assert "亲子" in card["matched_tags"]


def test_recommend_llm_note_passed_through(sunny_weather, fake_llm, monkeypatch):
    async def fake_chat_json(system, user, client=None):
        return {
            "picks": [{"city_id": "hangzhou", "reason": "相对最好", "warning": "期间多雨"}],
            "note": "近期各候选天气都比较一般",
        }

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["note"] == "近期各候选天气都比较一般"
    assert body["recommendations"][0]["warning"] == "期间多雨"


def test_recommend_llm_hallucinated_city_dropped(sunny_weather, fake_llm):
    fake_llm([{"city_id": "atlantis2", "reason": "不存在", "warning": None}])
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 502


def test_recommend_unknown_city_422(sunny_weather, fake_llm):
    fake_llm([])
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou", "atlantis"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 422
    assert "atlantis" in resp.json()["detail"]


def test_recommend_past_date_422(sunny_weather, fake_llm):
    fake_llm([])
    start = (date.today() - timedelta(days=1)).isoformat()
    end = date.today().isoformat()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 422
    assert "不能早于今天" in resp.json()["detail"]


def test_recommend_beyond_forecast_window_422(sunny_weather, fake_llm):
    fake_llm([])
    start = (date.today() + timedelta(days=20)).isoformat()
    end = (date.today() + timedelta(days=22)).isoformat()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 422


def test_recommend_long_trip_ok(sunny_weather, fake_llm):
    """时间窗口只是「有空的时间」:10 天窗口里,按城市建议天数安排 3 天,不硬填满。"""
    fake_llm([{"city_id": "hangzhou", "reason": "天气晴朗", "warning": None}])
    start, end = trip_dates(days=10)
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 200
    card = resp.json()["recommendations"][0]
    assert card["weather"]["total_days"] == 3  # 杭州建议 3 天
    assert card["trip_start"] == start
    assert card["trip_end"] == (date.fromisoformat(start) + timedelta(days=2)).isoformat()


def test_recommend_arranges_llm_subwindow(sunny_weather, fake_llm):
    """LLM 在窗口内指定的出发区间被采用,天气与卡片只覆盖该区间。"""
    w_start, w_end = trip_dates(days=9)
    trip_start = (date.fromisoformat(w_start) + timedelta(days=1)).isoformat()
    trip_end = (date.fromisoformat(trip_start) + timedelta(days=2)).isoformat()
    fake_llm(
        [
            {
                "city_id": "hangzhou",
                "reason": "帮你挑了中间这段晴天",
                "warning": None,
                "trip_start": trip_start,
                "trip_end": trip_end,
            }
        ]
    )
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": w_start, "end_date": w_end},
        )
    assert resp.status_code == 200
    card = resp.json()["recommendations"][0]
    assert card["trip_start"] == trip_start
    assert card["trip_end"] == trip_end
    assert card["weather"]["total_days"] == 3
    assert card["weather"]["days"][0]["date"] == trip_start
    assert card["weather"]["days"][-1]["date"] == trip_end


def test_recommend_invalid_trip_window_falls_back(sunny_weather, fake_llm):
    """LLM 给的区间非法(结束早于开始 / 越出窗口)时回退为窗口起始 + 建议天数。"""
    w_start, w_end = trip_dates(days=9)
    fake_llm(
        [
            {"city_id": "hangzhou", "reason": "区间颠倒", "trip_start": w_end, "trip_end": w_start},
            {"city_id": "chengdu", "reason": "区间越界", "trip_start": "2000-01-01", "trip_end": "2000-01-03"},
        ]
    )
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou", "chengdu"], "start_date": w_start, "end_date": w_end},
        )
    assert resp.status_code == 200
    cards = resp.json()["recommendations"]
    assert len(cards) == 2
    for card in cards:
        assert card["trip_start"] == w_start
        assert card["trip_end"] == (date.fromisoformat(w_start) + timedelta(days=2)).isoformat()
        assert card["weather"]["total_days"] == 3


def test_cap_candidates_prefers_near_with_origin():
    """城市库变大后,标签模式候选截断且保证地理多样性;有出发地时最近的城市必须入选。"""
    from app.schemas.recommend import Origin
    from app.services.city_store import load_cities
    from app.services.recommender import _cap_candidates

    cities = list(load_cities())
    origin = Origin(lat=30.2741, lon=120.1551, name="杭州")
    capped = _cap_candidates(cities, origin)
    assert len(capped) == 16
    assert "hangzhou" in {c.id for c in capped}
    assert len({c.region for c in capped}) >= 2
    # 不带出发地时同样截断
    assert len(_cap_candidates(cities, None)) == 16


def test_recommend_tags_mode_caps_candidates(sunny_weather, monkeypatch):
    from app.services.city_store import load_cities

    all_cities = list(load_cities())
    monkeypatch.setattr("app.services.recommender.cities_by_tags", lambda tags: all_cities)

    async def fake_chat_json(system, user, client=None):
        first_id = user.split("- id: ")[1].split(" ")[0]
        return {"picks": [{"city_id": first_id, "reason": "不错", "warning": None}], "note": None}

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "tags", "tags": ["food"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 200


def test_recommend_weather_all_fail(monkeypatch):
    async def fail_weather(client, lat, lon, start, end):
        from app.services.weather import WeatherServiceError

        raise WeatherServiceError("boom")

    monkeypatch.setattr("app.services.weather.get_daily_weather", fail_weather)
    start, end = trip_dates()
    with TestClient(app) as c:
        resp = c.post(
            "/api/recommend",
            json={"mode": "cities", "city_ids": ["hangzhou"], "start_date": start, "end_date": end},
        )
    assert resp.status_code == 503
    assert "天气服务暂不可用" in resp.json()["detail"]
