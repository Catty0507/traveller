from fastapi.testclient import TestClient

from app.main import app
from app.schemas.city import CityOut
from app.services.city_store import load_cities


def client():
    return TestClient(app)


def test_cities_full_list():
    with client() as c:
        resp = c.get("/api/cities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(load_cities())
    assert body["total"] >= 60
    assert body["cities"][0]["id"]


def test_cities_search_by_chinese_name():
    with client() as c:
        resp = c.get("/api/cities", params={"q": "杭州"})
    assert resp.status_code == 200
    cities = resp.json()["cities"]
    assert len(cities) == 1
    assert cities[0]["id"] == "hangzhou"


def test_cities_search_by_english_name():
    with client() as c:
        resp = c.get("/api/cities", params={"q": "paris"})
    cities = resp.json()["cities"]
    assert cities[0]["id"] == "paris"


def test_cities_filter_by_tag():
    with client() as c:
        resp = c.get("/api/cities", params={"tag": "ski"})
    cities = resp.json()["cities"]
    assert len(cities) >= 4
    assert all("ski" in city["tags"] for city in cities)


def test_tags():
    with client() as c:
        resp = c.get("/api/tags")
    tags = resp.json()["tags"]
    assert len(tags) == 8
    labels = {t["id"] for t in tags}
    assert {"seaside", "ancient_town", "food", "nature", "family", "culture", "shopping", "ski"} == labels


def test_health():
    with client() as c:
        resp = c.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "llm_configured" in resp.json()


def _fake_geo_city(geo_id: int, name_zh: str) -> CityOut:
    return CityOut(
        id=f"om{geo_id}",
        name_zh=name_zh,
        name_en=f"Test{name_zh}",
        country="测试国",
        region="亚洲",
        lat=10.0,
        lon=20.0,
        timezone="Asia/Tokyo",
        summary="测试 · 人口约 100 万",
        suggested_days=3,
        tags=[],
        cover_color="sky",
    )


def test_cities_search_merges_global_results(monkeypatch):
    import app.services.geocode as geocode

    async def fake_search_global(http, keyword, limit=8):
        return [_fake_geo_city(999001, "测试城")]

    monkeypatch.setattr(geocode, "search_global", fake_search_global)
    with client() as c:
        resp = c.get("/api/cities/search", params={"q": "测试城XYZ"})
    assert resp.status_code == 200
    body = resp.json()
    assert [city["id"] for city in body["cities"] if city["id"] == "om999001"]
    # 精选库中已有的城市(如大阪)不应出现全球库的重复项
    dup = [city for city in body["cities"] if city["name_zh"] == "大阪" and city["country"] == "日本"]
    ids = {city["id"] for city in dup}
    assert ids == {"osaka"} or len(ids) <= 1


def test_normalize_admin_name():
    from app.services.geocode import normalize_admin_name

    assert normalize_admin_name("重庆市") == "重庆"
    assert normalize_admin_name("河南县") == "河南"
    assert normalize_admin_name("河南蒙古族自治县") == "河南蒙古族"
    assert normalize_admin_name("大阪市") == "大阪"
    assert normalize_admin_name("杭州") == "杭州"  # 无后缀不变


def test_cities_search_drops_curated_with_admin_suffix(monkeypatch):
    """搜索源返回「重庆市」,精选库已有「重庆」→ 不重复展示。"""
    import app.services.geocode as geocode

    async def fake_search_global(http, keyword, limit=8):
        cq = _fake_geo_city(999200, "重庆市")
        cq.country = "中国"  # 与精选库重庆同国,判重才生效
        return [
            cq,
            _fake_geo_city(999201, "重庆之窗"),  # 不同城市,应保留
        ]

    monkeypatch.setattr(geocode, "search_global", fake_search_global)
    with client() as c:
        resp = c.get("/api/cities/search", params={"q": "重庆"})
    cities = resp.json()["cities"]
    ids = [city["id"] for city in cities]
    assert "om999200" not in ids  # 重庆市被去掉后缀与精选库重庆判重
    assert "om999201" in ids


def test_cities_search_degrades_to_curated_on_failure(monkeypatch):
    import app.services.geocode as geocode

    async def fail_search(http, keyword, limit=8):
        raise RuntimeError("boom")

    monkeypatch.setattr(geocode, "search_global", fail_search)
    with client() as c:
        resp = c.get("/api/cities/search", params={"q": "杭州"})
    assert resp.status_code == 200  # 降级不报错
    assert resp.json()["cities"][0]["id"] == "hangzhou"


def test_discovered_city_registry(tmp_path, monkeypatch):
    from app.services import city_store

    monkeypatch.setattr(city_store, "DISCOVERED_PATH", tmp_path / "discovered.json")
    monkeypatch.setattr(city_store, "_discovered", {})
    monkeypatch.setattr(city_store, "_discovered_loaded", False)

    city = _fake_geo_city(999002, "登记城")
    city_store.record_discovered([city])
    assert (tmp_path / "discovered.json").exists()
    assert city_store.get_city("om999002") == city

    # 模拟重启:内存清空后从磁盘恢复
    monkeypatch.setattr(city_store, "_discovered", {})
    monkeypatch.setattr(city_store, "_discovered_loaded", False)
    city_store._load_discovered()
    assert city_store.get_city("om999002") is not None


def test_om_parse_normalization():
    from app.services.geocode import _om_parse

    zh = [
        {
            "id": 1855084,
            "name": "大阪",
            "latitude": 34.6937,
            "longitude": 135.5023,
            "feature_code": "PPLC",
            "country": "日本",
            "timezone": "Asia/Tokyo",
            "population": 2691185,
            "admin1": "大阪府",
        },
        {"id": 186, "name": "大阪府界", "feature_code": "ADM2"},  # 行政区,应被过滤
    ]
    en = [{"id": 1855084, "name": "Osaka", "country": "Japan"}]
    cities = _om_parse(zh, en)
    assert len(cities) == 1
    city = cities[0]
    assert city.id == "om1855084"
    assert city.name_zh == "大阪"
    assert city.name_en == "Osaka"
    assert city.region == "全球"
    assert city.suggested_days == 3  # 269 万人口
    assert city.summary == "大阪府 · 人口约 269 万"
    assert city.tags == []
    assert city.cover_color in {"emerald", "sky", "amber", "rose", "violet", "teal", "orange", "indigo"}


def test_photon_parse_normalization():
    from app.services.geocode import _photon_parse

    payload = {
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "osm_type": "R",
                    "osm_id": 358674,
                    "osm_key": "place",
                    "osm_value": "city",
                    "name": "Matera",
                    "country": "Italia",
                    "countrycode": "IT",
                    "state": "Basilicata",
                },
                "geometry": {"type": "Point", "coordinates": [16.8692, 40.6664]},
            },
            {  # 行政边界,应被过滤
                "properties": {"osm_key": "boundary", "osm_value": "administrative", "name": "马泰拉省"},
                "geometry": {"coordinates": [16.8, 40.6]},
            },
            {  # 无名条目,应被过滤
                "properties": {"osm_key": "place", "osm_value": "city"},
                "geometry": {"coordinates": [16.9, 40.7]},
            },
            {  # 景区型 place=region(如五渔村),应保留
                "properties": {
                    "osm_type": "N", "osm_id": 111,
                    "osm_key": "place", "osm_value": "region",
                    "name": "Cinque Terre", "country": "Italia",
                },
                "geometry": {"coordinates": [9.73, 44.15]},
            },
            {  # 国家公园(如九寨沟),应保留
                "properties": {
                    "osm_type": "R", "osm_id": 222,
                    "osm_key": "boundary", "osm_value": "national_park",
                    "name": "九寨沟", "country": "中国",
                },
                "geometry": {"coordinates": [103.9, 33.26]},
            },
            {  # 混排多语名(OSM 原始数据),清洗后应只留中文
                "properties": {
                    "osm_type": "R", "osm_id": 333,
                    "osm_key": "place", "osm_value": "city",
                    "name": "河南县 ᠾᠧᠨᠠᠨ རྨ་ལྷོ།",
                    "state": "青海省",
                    "country": "中国",
                },
                "geometry": {"coordinates": [101.6, 34.73]},
            },
        ]
    }
    cities = _photon_parse(payload)
    # city 类排最前(region/国家公园靠后)
    assert [c.id for c in cities] == ["nmR358674", "nmR333", "nmN111", "nmR222"]
    assert cities[1].name_zh == "河南县"
    city = cities[0]
    assert city.name_zh == "Matera"
    assert city.lat == 40.6664  # GeoJSON 是 [lon, lat],需翻转
    assert city.lon == 16.8692
    assert city.summary == "Basilicata"
    assert city.timezone == "auto"
    assert city.tags == []


def test_merge_dedupe_interleaves_sources():
    """合并时两源轮流取,避免单源占满 limit 截断另一源。"""
    from app.services.geocode import _merge_dedupe

    def city(geo_id, name, lat, lon):
        c = _fake_geo_city(geo_id, name)
        c.lat, c.lon = lat, lon
        return c

    om = [city(1, "甲城", 10.0, 20.0), city(2, "乙城", 11.0, 21.0), city(3, "丙城", 12.0, 22.0)]
    ph = [city(4, "丁城", 13.0, 23.0)]
    merged = _merge_dedupe([om, ph], limit=3)
    assert [c.id for c in merged] == ["om1", "om4", "om2"]


def test_merge_dedupe_tolerates_source_failure():
    from app.services.geocode import _merge_dedupe

    om = [_fake_geo_city(1, "甲城")]
    merged = _merge_dedupe([om, RuntimeError("photon down")], limit=8)
    assert [c.id for c in merged] == ["om1"]


def test_clean_text_strips_other_scripts():
    """OSM 民族自治地名常是「汉字+蒙文/藏文/维吾尔文」并排,只保留中文/拉丁。"""
    from app.services.geocode import _clean_text

    assert _clean_text("河南县 ᠾᠧᠨᠠᠨ རྨ་ལྷོ།") == "河南县"
    assert _clean_text("新疆维吾尔自治区 شىنجاڭ ئۇيغۇر ئاپتونوم رايونى") == "新疆维吾尔自治区"
    # 纯外文名不受影响
    assert _clean_text("Zürich") == "Zürich"
    assert _clean_text("ニセコ町") == "ニセコ町"
    assert _clean_text("青岛 Qingdao") == "青岛 Qingdao"
    assert _clean_text("") == ""


def test_search_global_llm_fallback(monkeypatch):
    """中文长尾地名(马泰拉)查不到时,走 LLM 翻译成 Matera 再查。"""
    import asyncio

    import httpx

    import app.services.geocode as geocode
    from app.services.ttl_cache import TTLCache

    async def fake_chat_json(system, user, client=None):
        assert "马泰拉" in user
        return {"candidates": ["Matera"]}

    async def fake_om(http, keyword, limit):
        return [_fake_geo_city(999100, "Matera")] if keyword == "Matera" else []

    async def fake_photon(http, keyword, limit):
        return []

    monkeypatch.setattr("app.services.llm_client.chat_json", fake_chat_json)
    monkeypatch.setattr(geocode, "_om_to_cities", fake_om)
    monkeypatch.setattr(geocode, "_photon_to_cities", fake_photon)
    monkeypatch.setattr(geocode, "_search_cache", TTLCache(maxsize=8, ttl=60))
    monkeypatch.setattr(geocode, "record_discovered", lambda cities: None)

    cities = asyncio.run(geocode.search_global(httpx.AsyncClient(), "马泰拉"))
    assert [c.id for c in cities] == ["om999100"]


def test_search_global_direct_hit_skips_translation(monkeypatch):
    """首查命中时不触发 LLM 翻译。"""
    import asyncio

    import httpx

    import app.services.geocode as geocode
    from app.services.ttl_cache import TTLCache

    async def fail_chat_json(system, user, client=None):
        raise AssertionError("不应调用翻译")

    async def fake_om(http, keyword, limit):
        return []

    async def fake_photon(http, keyword, limit):
        return [_fake_geo_city(999101, keyword.capitalize())]

    monkeypatch.setattr("app.services.llm_client.chat_json", fail_chat_json)
    monkeypatch.setattr(geocode, "_om_to_cities", fake_om)
    monkeypatch.setattr(geocode, "_photon_to_cities", fake_photon)
    monkeypatch.setattr(geocode, "_search_cache", TTLCache(maxsize=8, ttl=60))
    monkeypatch.setattr(geocode, "record_discovered", lambda cities: None)

    cities = asyncio.run(geocode.search_global(httpx.AsyncClient(), "osaka"))
    assert [c.id for c in cities] == ["om999101"]
