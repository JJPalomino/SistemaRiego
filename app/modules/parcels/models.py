import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class TexturaSuelo(str, enum.Enum):
    """Textura del suelo de la parcela.

    Determina la capacidad de campo y el punto de marchitez usados por el
    balance hidrico del generador de datos y, mas adelante, por el modelo.
    """

    arenoso = "arenoso"
    franco_arenoso = "franco_arenoso"
    franco = "franco"
    franco_arcilloso = "franco_arcilloso"
    arcilloso = "arcilloso"


class Parcela(Base):
    """Microparcela fisica de un productor.

    Es la unidad de monitoreo: agrupa siembras (ciclos de cultivo) y sensores.
    Las coordenadas viven aqui, no en la peticion, para que una recomendacion
    quede asociada a un lugar real y se pueda reproducir despues.
    """

    __tablename__ = "parcelas"

    id:             Mapped[int]            = mapped_column(primary_key=True, index=True)
    usuario_id:     Mapped[int]            = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre:         Mapped[str]            = mapped_column(String(120), nullable=False)
    latitud:        Mapped[float]          = mapped_column(Numeric(9, 6), nullable=False)
    longitud:       Mapped[float]          = mapped_column(Numeric(9, 6), nullable=False)
    altitud_msnm:   Mapped[float]          = mapped_column(Numeric(7, 2), nullable=True)
    area_m2:        Mapped[float]          = mapped_column(Numeric(10, 2), nullable=True)
    textura_suelo:  Mapped[TexturaSuelo]   = mapped_column(
        SAEnum(TexturaSuelo), nullable=False, default=TexturaSuelo.franco
    )
    activa:         Mapped[bool]           = mapped_column(Boolean, default=True, nullable=False)
    notas:          Mapped[str]            = mapped_column(Text, nullable=True)
    created_at:     Mapped[DateTime]       = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at:     Mapped[DateTime]       = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    siembras: Mapped[list["Siembra"]] = relationship(
        back_populates="parcela", cascade="all, delete-orphan"
    )
    sensores: Mapped[list["Sensor"]] = relationship(
        back_populates="parcela", cascade="all, delete-orphan"
    )


class Siembra(Base):
    """Ciclo de cultivo de una hortaliza dentro de una parcela.

    12 meses de historico con ciclos de 50-120 dias implican varios ciclos por
    parcela; por eso la siembra es una entidad propia y no un campo de
    `Parcela`.
    """

    __tablename__ = "siembras"

    __table_args__ = (
        CheckConstraint(
            "fecha_cosecha IS NULL OR fecha_cosecha >= fecha_siembra",
            name="ck_siembra_fechas_coherentes",
        ),
    )

    id:             Mapped[int]          = mapped_column(primary_key=True, index=True)
    parcela_id:     Mapped[int]          = mapped_column(
        ForeignKey("parcelas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hortaliza_id:   Mapped[int]          = mapped_column(
        # El catalogo es data de referencia: no se puede borrar una hortaliza
        # que ya tiene siembras asociadas (el router lo reporta como 409).
        ForeignKey("hortalizas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fecha_siembra:  Mapped[Date]         = mapped_column(Date, nullable=False)
    fecha_cosecha:  Mapped[Date]         = mapped_column(Date, nullable=True)
    activa:         Mapped[bool]         = mapped_column(Boolean, default=True, nullable=False)
    notas:          Mapped[str]          = mapped_column(Text, nullable=True)
    created_at:     Mapped[DateTime]     = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parcela: Mapped["Parcela"] = relationship(back_populates="siembras")
    hortaliza: Mapped["Hortaliza"] = relationship()

    @property
    def nombre_hortaliza(self) -> str | None:
        """Nombre del cultivo sembrado, para no obligar al cliente a cruzar ids."""
        return self.hortaliza.nombre if self.hortaliza is not None else None

    @property
    def dias_desde_siembra(self) -> int:
        """Dias transcurridos desde la siembra hasta hoy (o la cosecha).

        Se calcula aqui y no se almacena para que no quede desactualizado.
        """
        from datetime import date

        fin = self.fecha_cosecha or date.today()
        return max((fin - self.fecha_siembra).days, 0)
