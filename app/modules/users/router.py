from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.modules.users.models import Usuario
from app.modules.users.schemas import (
    UsuarioCreate,
    UsuarioResponse,
    LoginRequest,
    TokenResponse,
)
from app.modules.users import services

router = APIRouter(prefix="/api/v1/usuarios", tags=["Usuarios"])


@router.post("/registro", response_model=UsuarioResponse, status_code=201)
def registrar(datos: UsuarioCreate, db: Session = Depends(get_db)):
    try:
        return services.registrar_usuario(db, datos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    try:
        resultado = services.login_usuario(db, datos.email, datos.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {
        "access_token": resultado["token"],
        "token_type": "bearer",
        "usuario": resultado["usuario"],
    }


@router.get("/me", response_model=UsuarioResponse)
def mi_perfil(
    usuario: Usuario = Depends(get_current_user),
):
    """Devuelve el usuario autenticado. Requiere `Authorization: Bearer <token>`."""
    return usuario
