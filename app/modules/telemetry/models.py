import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class TipoSensor(str, enum.Enum):
    """Variables que puede medir un sensor en campo."""

    humedad_suelo = "humedad_suelo"
    temperatura_aire = "temperatura_aire"
    humedad_aire = "humedad_aire"
    temperatura_suelo = "temperatura_suelo"
    lluvia = "lluvia"
    radiacion = "radiacion"
    viento = "viento"


# Unidad canonica de cada tipo de sensor. Se guarda en `Sensor.unidad` para
# dejar explicito con que magnitud se esta alimentando el modelo.
UNIDAD_POR_TIPO: dict[TipoSensor, str] = {
    TipoSensor.humedad_suelo: "%",
    TipoSensor.temperatura_aire: "C",
    TipoSensor.humedad_aire: "%",
    TipoSensor.temperatura_suelo: "C",
    TipoSensor.lluvia: "mm",
    TipoSensor.radiacion: "W/m2",
    TipoSensor.viento: "km/h",
}


class Sensor(Base):
    """Sensor fisico instalado en una parcela.

    `profundidad_cm` solo aplica a los sensores enterrados (humedad y
    temperatura de suelo). Se deja en la tabla, y no como columnas fijas, para
    soportar 1, 2 o 3 profundidades sin cambiar el esquema cuando lleguen los
    sensores reales.
    """

    __tablename__ = "sensores"

    __table_args__ = (
        UniqueConstraint(
            "parcela_id",
            "tipo",
            "profundidad_cm",
            name="uq_sensor_parcela_tipo_profundidad",
        ),
    )

    id:             Mapped[int]        = mapped_column(primary_key=True, index=True)
    parcela_id:     Mapped[int]        = mapped_column(
        ForeignKey("parcelas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo:         Mapped[str]        = mapped_column(
        String(60), nullable=False, unique=True, index=True
    )
    tipo:           Mapped[TipoSensor] = mapped_column(SAEnum(TipoSensor), nullable=False)
    unidad:         Mapped[str]        = mapped_column(String(20), nullable=False)
    profundidad_cm: Mapped[float]      = mapped_column(Numeric(5, 1), nullable=True)
    activo:         Mapped[bool]       = mapped_column(Boolean, default=True, nullable=False)
    created_at:     Mapped[DateTime]   = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parcela: Mapped["Parcela"] = relationship(back_populates="sensores")
    lecturas: Mapped[list["Lectura"]] = relationship(
        back_populates="sensor", cascade="all, delete-orphan"
    )


class Lectura(Base):
    """Una medicion de un sensor en un instante.

    El indice unico (sensor_id, timestamp) hace la ingesta idempotente: si un
    dispositivo reenvia un lote, las filas repetidas se ignoran en lugar de
    duplicar el historico de entrenamiento.
    """

    __tablename__ = "lecturas_sensor"

    __table_args__ = (
        UniqueConstraint(
            "sensor_id", "timestamp", name="uq_lectura_sensor_timestamp"
        ),
    )

    id:         Mapped[int]      = mapped_column(primary_key=True, index=True)
    sensor_id:  Mapped[int]      = mapped_column(
        ForeignKey("sensores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp:  Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor:      Mapped[float]    = mapped_column(Numeric(10, 3), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sensor: Mapped["Sensor"] = relationship(back_populates="lecturas")
