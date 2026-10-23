from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.modules.users.models import Usuario

# `auto_error=False` para poder devolver un 401 con un mensaje propio en vez
# del 403 por defecto de FastAPI cuando falta la cabecera Authorization.
bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Valida el JWT emitido por /api/v1/usuarios/login y devuelve el usuario.

    Antes de este cambio el token se generaba pero nunca se verificaba en
    ningun endpoint, por lo que todas las rutas quedaban publicas.
    """
    credenciales_erroneas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticacion invalidas o ausentes",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise credenciales_erroneas

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
    except JWTError:
        # Incluye token expirado, firma invalida y token malformado.
        raise credenciales_erroneas

    subject = payload.get("sub")
    if subject is None:
        raise credenciales_erroneas

    try:
        usuario_id = int(subject)
    except (TypeError, ValueError):
        raise credenciales_erroneas

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        raise credenciales_erroneas

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario esta inactivo",
        )

    return usuario
