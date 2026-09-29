from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.agent import routes as agent_routes
from app.ingest import email as ingest_email
from app.ingest import upload as ingest_upload
from app.ingest import whatsapp as ingest_whatsapp
from app.notifications import routes as notifications_routes
from app.reconciliation import routes as reconciliation_routes
from app.reports import routes as reports_routes
from app.tax import routes as tax_routes

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

app.include_router(ingest_upload.router)
app.include_router(ingest_email.router)
app.include_router(ingest_whatsapp.router)
app.include_router(reconciliation_routes.router)
app.include_router(tax_routes.router)
app.include_router(agent_routes.router)
app.include_router(notifications_routes.router)
app.include_router(reports_routes.router)


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
