from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime

class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validar_password(cls, v):
        if len(v.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede exceder 72 caracteres")
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    email: str
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse