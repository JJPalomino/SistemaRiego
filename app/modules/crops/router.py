from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.modules.crops.schemas import (
    HortalizaCreate,
    HortalizaResponse,
    HortalizaUpdate,
)
from app.modules.crops import services

router = APIRouter(prefix="/api/v1/hortalizas", tags=["Hortalizas"])


@router.get("/", response_model=list[HortalizaResponse])
def listar_hortalizas(db: Session = Depends(get_db)):
    """Catalogo de cultures. Es data de referencia, se deja publica."""
    return services.listar_hortalizas(db)


@router.get("/{id}", response_model=HortalizaResponse)
def obtener_hortaliza(id: int, db: Session = Depends(get_db)):
    try:
        return services.obtener_hortaliza(db, id)
    except services.HortalizaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/", response_model=HortalizaResponse, status_code=201)
def crear_hortaliza(
    datos: HortalizaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return services.crear_hortaliza(db, datos)
    except services.HortalizaDuplicada as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{id}", response_model=HortalizaResponse)
def actualizar_hortaliza(
    id: int,
    datos: HortalizaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return services.actualizar_hortaliza(db, id, datos)
    except services.HortalizaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.HortalizaDuplicada as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_hortaliza(
    id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        services.eliminar_hortaliza(db, id)
    except services.HortalizaNoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except services.HortalizaEnUso as e:
        raise HTTPException(status_code=409, detail=str(e))
