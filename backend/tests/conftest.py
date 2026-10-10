import pytest

from app.schemas.weather import DailyWeather
from app.services.guide_llm import _cache_by_ttl
from app.services.weather import _cache_instances, describe_code


@pytest.fixture
def make_day():
    """构造 DailyWeather 的工厂 fixture。"""

    def _make(
        date: str = "2026-10-10",
        code: int = 0,
        t_max: float = 24.0,
        t_min: float = 16.0,
        rain_prob: int | None = 10,
        precip: float = 0.0,
    ) -> DailyWeather:
        desc, emoji = describe_code(code)
        return DailyWeather(
            date=date,
            weather_code=code,
            desc=desc,
            emoji=emoji,
            t_max=t_max,
            t_min=t_min,
            rain_prob=rain_prob,
            precip_mm=precip,
        )

    return _make


@pytest.fixture(autouse=True)
def clear_caches():
    """每个测试前后清空模块级缓存,避免相互污染。"""
    _cache_instances.clear()
    _cache_by_ttl.clear()
    yield
    _cache_instances.clear()
    _cache_by_ttl.clear()
