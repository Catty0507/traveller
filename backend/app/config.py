from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置,从环境变量 / backend/.env 读取。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # OpenAI 兼容接口配置(通义千问 / Kimi / 智谱 GLM / DeepSeek 等)
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # 允许跨域访问的前端来源,逗号分隔;部署后把线上前端域名加进来
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    weather_cache_ttl_seconds: int = 1800
    guide_cache_ttl_seconds: int = 3600
    # 流式调用下这是「块间超时」:两次 token 之间的最大等待,而非整个响应的时限
    llm_timeout_seconds: float = 180.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
