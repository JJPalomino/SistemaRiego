from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.modules.parcels.services import ParcelaNoEncontrada
from app.modules.telemetry import services
from app.modules.telemetry.schemas import (
    LecturaResponse,
    LoteLecturasCreate,
    ResultadoIngesta,
    ResumenSensor,
    SensorCreate,
    SensorResponse,
)
from app.modules.users.models import Usuario

router = APIRouter(prefix="/api/v1/telemetria", tags=["Telemetria"])


# ---------------------------------------------------------------------------
# Sensores
# ---------------------------------------------------------------------------

@router.post("/sensores", response_model=SensorResponse, status_code=201)
def registrar_sensor(
    datos: SensorCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra un sensor fisico en una parcela del usuario."""
    try:
        return services.crear_sensor(db, usuario.id, datos)
    except ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.SensorDuplicado as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/sensores", response_model=list[SensorResponse])
def listar_sensores(
    parcela_id: int = Query(gt=0),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.listar_sensores(db, usuario.id, parcela_id)
    except ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------

@router.post("/lecturas", response_model=ResultadoIngesta, status_code=201)
def ingresar_lecturas(
    lote: LoteLecturasCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingesta un lote de lecturas.

    Es idempotente: reenviar el mismo lote no duplica datos, porque se ignora
    cualquier par (sensor_id, timestamp) que ya exista. El generador de datos
    sinteticos y los dispositivos reales usan exactamente este endpoint.
    """
    try:
        return services.ingresar_lecturas(db, usuario.id, lote)
    except services.SensorNoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.LecturaInvalida as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.get("/lecturas", response_model=list[LecturaResponse])
def consultar_lecturas(
    sensor_id: int = Query(gt=0),
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limite: int = Query(default=1000, ge=1, le=10000),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.consultar_lecturas(
            db, usuario.id, sensor_id, desde, hasta, limite
        )
    except services.SensorNoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/resumen", response_model=list[ResumenSensor])
def resumen_sensores(
    parcela_id: int = Query(gt=0),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ultima lectura de cada sensor de la parcela."""
    try:
        return services.ultimas_lecturas_por_sensor(db, usuario.id, parcela_id)
    except ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
