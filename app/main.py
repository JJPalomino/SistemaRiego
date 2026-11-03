from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.users.router import router as users_router
from app.modules.crops.router import router as crops_router
from app.modules.parcels.router import router as parcels_router
from app.modules.telemetry.router import router as telemetry_router
from app.modules.ai_advisor.router import router as ai_advisor_router
from app.modules.reports.router import router as reports_router

app = FastAPI(
    title="Sistema de Recomendaciones de Riego",
    description="API para microparcelas agricolas - Tlatlauquitepec, Puebla",
    version="0.1.0",
)

# En produccion, CORS_ORIGINS debe listar los dominios reales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Con credenciales el comodin "*" no es valido: se refleja el origen.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(crops_router)
app.include_router(parcels_router)
app.include_router(telemetry_router)
app.include_router(ai_advisor_router)
app.include_router(reports_router)


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "Sistema de riego activo"}


@app.get("/health")
def health():
    return {"status": "ok"}
