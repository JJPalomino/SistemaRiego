from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.modules.parcels import services
from app.modules.parcels.schemas import (
    ParcelaCreate,
    ParcelaResponse,
    ParcelaUpdate,
    SiembraCreate,
    SiembraResponse,
    SiembraUpdate,
)
from app.modules.users.models import Usuario

router = APIRouter(prefix="/api/v1/parcelas", tags=["Parcelas"])


# ---------------------------------------------------------------------------
# Parcelas
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ParcelaResponse])
def listar_parcelas(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parcelas del usuario autenticado."""
    return services.listar_parcelas(db, usuario.id)


@router.post("/", response_model=ParcelaResponse, status_code=201)
def crear_parcela(
    datos: ParcelaCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return services.crear_parcela(db, usuario.id, datos)


@router.get("/{parcela_id}", response_model=ParcelaResponse)
def obtener_parcela(
    parcela_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.obtener_parcela(db, usuario.id, parcela_id)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{parcela_id}", response_model=ParcelaResponse)
def actualizar_parcela(
    parcela_id: int,
    datos: ParcelaUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.actualizar_parcela(db, usuario.id, parcela_id, datos)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{parcela_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_parcela(
    parcela_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        services.eliminar_parcela(db, usuario.id, parcela_id)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Siembras
# ---------------------------------------------------------------------------

@router.get("/{parcela_id}/siembras", response_model=list[SiembraResponse])
def listar_siembras(
    parcela_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.listar_siembras(db, usuario.id, parcela_id)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{parcela_id}/siembras", response_model=SiembraResponse, status_code=201
)
def crear_siembra(
    parcela_id: int,
    datos: SiembraCreate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.crear_siembra(db, usuario.id, parcela_id, datos)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.HortalizaInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))
    except services.SiembraTraslapada as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{parcela_id}/siembra-vigente", response_model=Optional[SiembraResponse])
def obtener_siembra_vigente(
    parcela_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ciclo de cultivo vigente hoy, o `null` si la parcela esta en descanso."""
    try:
        return services.obtener_siembra_vigente(db, usuario.id, parcela_id)
    except services.ParcelaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{parcela_id}/siembras/{siembra_id}", response_model=SiembraResponse
)
def obtener_siembra(
    parcela_id: int,
    siembra_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.obtener_siembra(db, usuario.id, parcela_id, siembra_id)
    except (services.ParcelaNoEncontrada, services.SiembraNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/{parcela_id}/siembras/{siembra_id}", response_model=SiembraResponse
)
def actualizar_siembra(
    parcela_id: int,
    siembra_id: int,
    datos: SiembraUpdate,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return services.actualizar_siembra(
            db, usuario.id, parcela_id, siembra_id, datos
        )
    except (services.ParcelaNoEncontrada, services.SiembraNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.HortalizaInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))
    except services.SiembraTraslapada as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{parcela_id}/siembras/{siembra_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def eliminar_siembra(
    parcela_id: int,
    siembra_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        services.eliminar_siembra(db, usuario.id, parcela_id, siembra_id)
    except (services.ParcelaNoEncontrada, services.SiembraNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))
