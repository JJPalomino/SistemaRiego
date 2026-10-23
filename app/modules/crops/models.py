from sqlalchemy import String, Integer, Numeric, Text, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base
import enum

class SensibilidadNivel(str, enum.Enum):
    alta  = "alta"
    media = "media"
    baja  = "baja"

class Hortaliza(Base):
    __tablename__ = "hortalizas"

    id:                             Mapped[int]   = mapped_column(primary_key=True, index=True)
    nombre:                         Mapped[str]   = mapped_column(String(100), nullable=False, unique=True)
    nombre_cientifico:              Mapped[str]   = mapped_column(String(150), nullable=True)
    temp_min_c:                     Mapped[float] = mapped_column(Numeric(5,2), nullable=False)
    temp_max_c:                     Mapped[float] = mapped_column(Numeric(5,2), nullable=False)
    temp_ideal_c:                   Mapped[float] = mapped_column(Numeric(5,2), nullable=False)
    humedad_suelo_min_pct:          Mapped[float] = mapped_column(Numeric(5,2), nullable=False)
    humedad_suelo_max_pct:          Mapped[float] = mapped_column(Numeric(5,2), nullable=False)
    requerimiento_agua_semanal_mm:  Mapped[float] = mapped_column(Numeric(7,2), nullable=False)
    radiacion_solar_min_wm2:        Mapped[float] = mapped_column(Numeric(8,2), nullable=True)
    radiacion_solar_max_wm2:        Mapped[float] = mapped_column(Numeric(8,2), nullable=True)
    altitud_min_msnm:               Mapped[float] = mapped_column(Numeric(7,2), nullable=True)
    altitud_max_msnm:               Mapped[float] = mapped_column(Numeric(7,2), nullable=True)
    sensibilidad_heladas:           Mapped[SensibilidadNivel] = mapped_column(SAEnum(SensibilidadNivel), nullable=False, default=SensibilidadNivel.media)
    sensibilidad_humedad_excesiva:  Mapped[SensibilidadNivel] = mapped_column(SAEnum(SensibilidadNivel), nullable=False, default=SensibilidadNivel.media)
    sensibilidad_viento:            Mapped[SensibilidadNivel] = mapped_column(SAEnum(SensibilidadNivel), nullable=False, default=SensibilidadNivel.baja)
    duracion_total_dias:            Mapped[int]   = mapped_column(Integer, nullable=False)
    notas_generales:                Mapped[str]   = mapped_column(Text, nullable=True)
    created_at:                     Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    etapas:   Mapped[list["EtapaHortaliza"]] = relationship(back_populates="hortaliza", cascade="all, delete-orphan")

class EtapaHortaliza(Base):
    __tablename__ = "etapas_hortaliza"

    id:                    Mapped[int]   = mapped_column(primary_key=True, index=True)
    # `ondelete="CASCADE"` debe coincidir con la migracion d9072270ce8e; de lo
    # contrario `alembic check` reporta divergencia entre el modelo y el
    # esquema real de la base de datos.
    hortaliza_id:          Mapped[int]   = mapped_column(
        ForeignKey("hortalizas.id", ondelete="CASCADE"), nullable=False
    )
    nombre_etapa:          Mapped[str]   = mapped_column(String(80), nullable=False)
    dia_inicio:            Mapped[int]   = mapped_column(Integer, nullable=False)
    dia_fin:               Mapped[int]   = mapped_column(Integer, nullable=False)
    temp_critica_etapa_c:  Mapped[float] = mapped_column(Numeric(5,2), nullable=True)
    riego_frecuencia_dias: Mapped[int]   = mapped_column(Integer, nullable=True)
    notas_etapa:           Mapped[str]   = mapped_column(Text, nullable=True)

    hortaliza: Mapped["Hortaliza"] = relationship(back_populates="etapas")
