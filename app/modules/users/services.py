from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from jose import jwt
from passlib.context import CryptContext

from app.modules.users.models import Usuario
from app.modules.users.schemas import UsuarioCreate
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash fijo contra el que se compara cuando el correo no existe: iguala el
# tiempo de respuesta y evita enumerar usuarios.
DUMMY_HASH = "$2b$12$YYFPFQJQxI9XS809W/SVY.w82hkomdXV4kjNNVEwqP3Vz./6OvwfO"


def hashear_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)


def crear_token(data: dict) -> str:
    payload = data.copy()
    # 'datetime.utcnow()' esta deprecado desde Python 3.12 y emite aviso en 3.13.
    ahora = datetime.now(timezone.utc)
    payload["exp"] = ahora + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    payload["iat"] = ahora
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def registrar_usuario(db: Session, datos: UsuarioCreate) -> Usuario:
    existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if existente:
        raise ValueError("El correo ya está registrado")
    usuario = Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=hashear_password(datos.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def login_usuario(db: Session, email: str, password: str) -> dict:
    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if usuario is None:
        # Se ejecuta un bcrypt real contra un hash ficticio para que el tiempo
        # de respuesta no revele si el correo esta registrado.
        verificar_password(password, DUMMY_HASH)
        raise ValueError("Credenciales incorrectas")

    if not verificar_password(password, usuario.password_hash):
        raise ValueError("Credenciales incorrectas")

    if not usuario.activo:
        raise ValueError("Usuario inactivo")

    token = crear_token({"sub": str(usuario.id), "email": usuario.email})
    return {"token": token, "usuario": usuario}


def obtener_usuario_por_id(db: Session, usuario_id: int) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.id == usuario_id).first()
