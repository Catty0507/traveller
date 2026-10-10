from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import cities, guide, recommend
from app.services import llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    yield
    await app.state.http.aclose()


app = FastAPI(title="Traveller 旅行攻略", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cities.router)
app.include_router(recommend.router)
app.include_router(guide.router)


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
