from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import cities, drive, guide, recommend
from app.services import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    yield
    await app.state.http.aclose()


app = FastAPI(title="出逃计划 · 天气旅行推荐", version="0.1.0", lifespan=lifespan)

# 允许跨域的前端来源:默认本地开发,线上通过 CORS_ORIGINS 环境变量配置(逗号分隔)
_cors_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cities.router)
app.include_router(recommend.router)
app.include_router(guide.router)
app.include_router(drive.router)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    """把 Pydantic 校验错误转成单条中文信息,前端可直接展示。"""
    message = "输入有误"
    errors = exc.errors()
    if errors:
        msg = errors[0].get("msg", "")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        message = msg or message
    return JSONResponse(status_code=422, content={"detail": message})


@app.get("/api/health")
def health():
    return {"ok": True, "llm_configured": llm_client.is_configured()}
