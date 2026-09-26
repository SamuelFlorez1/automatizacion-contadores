from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Despacho Contable API",
    version="0.1.0",
    description="Backend del despacho contable automatizado",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "timezone": settings.default_timezone,
    }


@app.get("/")
async def root() -> dict:
    return {"name": "despacho-contable-api", "version": "0.1.0"}
