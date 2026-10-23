from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.modules.parcels.models import TexturaSuelo


class ParcelaBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    latitud: float = Field(
        ge=-90,
        le=90,
        description="Latitud en grados decimales.",
    )
    longitud: float = Field(
        ge=-180,
        le=180,
        description="Longitud en grados decimales.",
    )
    altitud_msnm: Optional[float] = Field(default=None, ge=0, le=6000)
    area_m2: Optional[float] = Field(default=None, gt=0)
    textura_suelo: TexturaSuelo = TexturaSuelo.franco
    activa: bool = True
    notas: Optional[str] = None


class ParcelaCreate(ParcelaBase):
    pass


class ParcelaUpdate(ParcelaBase):
    """Reemplazo completo de la parcela (PUT)."""


class ParcelaResponse(ParcelaBase):
    id: int
    usuario_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SiembraBase(BaseModel):
    hortaliza_id: int = Field(gt=0)
    fecha_siembra: date
    fecha_cosecha: Optional[date] = None
    activa: bool = True
    notas: Optional[str] = None

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_cosecha is not None and self.fecha_cosecha < self.fecha_siembra:
            raise ValueError(
                f"fecha_cosecha ({self.fecha_cosecha}) no puede ser anterior a "
                f"fecha_siembra ({self.fecha_siembra})"
            )
        if self.fecha_siembra > date.today():
            raise ValueError(
                "fecha_siembra no puede estar en el futuro: la etapa fenologica "
                "se calcula a partir de los dias transcurridos"
            )
        return self


class SiembraCreate(SiembraBase):
    pass


class SiembraUpdate(SiembraBase):
    """Reemplazo completo de la siembra (PUT)."""


class SiembraResponse(SiembraBase):
    id: int
    parcela_id: int
    nombre_hortaliza: Optional[str] = None
    dias_desde_siembra: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
