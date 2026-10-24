from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.modules.ai_advisor import services
from app.modules.ai_advisor.llm_client import ErrorLLM
from app.modules.ai_advisor.schemas import (
    ConsultaRecomendacionDetalle,
    ConsultaRecomendacionResumen,
    LecturaClimaticaDetalle,
    LecturaClimaticaResumen,
    RecomendacionResponse,
    SolicitudRecomendacion,
)
from app.modules.ai_advisor.weather_client import ErrorClima
from app.modules.parcels.services import ParcelaNoEncontrada, SiembraNoEncontrada
from app.modules.users.models import Usuario

router = APIRouter(prefix="/api/v1/ai", tags=["Asesor IA"])


# ---------------------------------------------------------------------------
# Generacion
# ---------------------------------------------------------------------------

@router.post("/recomendacion", response_model=RecomendacionResponse)
def obtener_recomendacion(
    solicitud: SolicitudRecomendacion,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Recomendacion de riego y manejo para los proximos 7 dias.

    Combina el catalogo de cultivos, el pronostico de Open-Meteo y el modelo
    de lenguaje (Gemini) como agronomo. Si se envia `siembra_id`, la consulta
    queda en el historial reproducible junto con el clima exacto usado.
    """
    try:
        return services.generar_recomendacion(db, usuario.id, solicitud)
    except (ParcelaNoEncontrada, SiembraNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.HortalizaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ErrorClima as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo obtener el pronostico climatico",
        )
    except ErrorLLM as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo generar la recomendacion",
        )


# ---------------------------------------------------------------------------
# Historial climatico
# ---------------------------------------------------------------------------

@router.get("/clima", response_model=list[LecturaClimaticaResumen])
def listar_clima(
    parcela_id: int = Query(..., gt=0),
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Consultas a Open-Meteo guardadas para una parcela (mas recientes primero).

    No incluye `datos_json` para no inflar la respuesta; el detalle esta en
    `/clima/{id}`.
    """
    try:
        return services.listar_lecturas_climaticas(
            db, usuario.id, parcela_id, limite
        )
    except ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/clima/{lectura_id}", response_model=LecturaClimaticaDetalle)
def obtener_clima(
    lectura_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Detalle de una consulta climatica, con el JSON original de Open-Meteo."""
    try:
        return services.obtener_lectura_climatica(db, usuario.id, lectura_id)
    except services.LecturaClimaticaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Historial de recomendaciones
# ---------------------------------------------------------------------------

@router.get("/historial", response_model=list[ConsultaRecomendacionResumen])
def listar_historial(
    siembra_id: int = Query(..., gt=0),
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Recomendaciones generadas para una siembra (mas recientes primero)."""
    try:
        return services.listar_consultas(db, usuario.id, siembra_id, limite)
    except SiembraNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/historial/{consulta_id}", response_model=ConsultaRecomendacionDetalle
)
def obtener_historial(
    consulta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Detalle de una recomendacion con el prompt y la respuesta integra.

    Es lo que permite reproducir la consulta meses despues: mismo clima,
    misma etapa del cultivo y misma salida del modelo.
    """
    try:
        return services.obtener_consulta(db, usuario.id, consulta_id)
    except services.ConsultaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
