from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.modules.telemetry.models import TipoSensor

# Solo los sensores enterrados llevan profundidad; los de aire y la radiacion
# van a una altura fija y no la necesitan.
TIPOS_CON_PROFUNDIDAD = frozenset(
    {TipoSensor.humedad_suelo, TipoSensor.temperatura_suelo}
)


class SensorBase(BaseModel):
    tipo: TipoSensor
    profundidad_cm: Optional[float] = Field(default=None, ge=0, le=200)
    activo: bool = True

    @model_validator(mode="after")
    def validar_profundidad(self):
        if self.tipo in TIPOS_CON_PROFUNDIDAD and self.profundidad_cm is None:
            raise ValueError(
                f"Un sensor de tipo '{self.tipo.value}' requiere profundidad_cm"
            )
        if (
            self.tipo not in TIPOS_CON_PROFUNDIDAD
            and self.profundidad_cm is not None
        ):
            raise ValueError(
                f"Un sensor de tipo '{self.tipo.value}' no lleva profundidad_cm"
            )
        return self


class SensorCreate(SensorBase):
    parcela_id: int = Field(gt=0)
    codigo: str = Field(
        min_length=1,
        max_length=60,
        description="Identificador fisico del dispositivo, unico en el sistema.",
    )


class SensorResponse(SensorBase):
    id: int
    parcela_id: int
    codigo: str
    unidad: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LecturaCreate(BaseModel):
    sensor_id: int = Field(gt=0)
    timestamp: datetime
    valor: float


class LecturaResponse(BaseModel):
    id: int
    sensor_id: int
    timestamp: datetime
    valor: float

    model_config = {"from_attributes": True}


class LoteLecturasCreate(BaseModel):
    """Lote de lecturas enviado por un dispositivo o por el generador."""

    lecturas: list[LecturaCreate] = Field(min_length=1, max_length=5000)


class ResultadoIngesta(BaseModel):
    recibidas: int = Field(description="Filas recibidas en la peticion.")
    unicas: int = Field(description="Filas tras descartar repetidas del mismo lote.")
    insertadas: int = Field(description="Filas nuevas guardadas en la base.")
    duplicadas: int = Field(description="Filas que ya existian y se ignoraron.")


class ResumenSensor(BaseModel):
    """Estado actual de un sensor, sin descargar su historico."""

    sensor_id: int
    codigo: str
    tipo: TipoSensor
    unidad: str
    profundidad_cm: Optional[float] = None
    timestamp: Optional[datetime] = None
    valor: Optional[float] = None

    model_config = {"from_attributes": True}

