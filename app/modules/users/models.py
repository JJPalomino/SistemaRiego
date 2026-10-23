from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id:             Mapped[int]  = mapped_column(primary_key=True, index=True)
    nombre:         Mapped[str]  = mapped_column(String(120), nullable=False)
    email:          Mapped[str]  = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash:  Mapped[str]  = mapped_column(String(255), nullable=False)
    activo:         Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at:     Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())