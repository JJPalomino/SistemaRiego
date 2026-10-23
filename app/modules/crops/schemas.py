from typing import Optional

from pydantic import BaseModel, Field, model_validator

# Se importa el enum desde los modelos para tener una unica fuente de verdad.
# Antes estaba duplicado en models.py y schemas.py, lo que permitia que ambos
# se desincronizaran silenciosamente.
from app.modules.crops.models import SensibilidadNivel  # noqa: F401  (reexportado)


class EtapaHortalizaBase(BaseModel):
    nombre_etapa: str = Field(min_length=1, max_length=80)
    dia_inicio: int = Field(ge=1)
    dia_fin: int = Field(ge=1)
    temp_critica_etapa_c: Optional[float] = None
    riego_frecuencia_dias: Optional[int] = Field(default=None, ge=1)
    notas_etapa: Optional[str] = None

    @model_validator(mode="after")
    def validar_rango_dias(self):
        if self.dia_fin < self.dia_inicio:
            raise ValueError(
                f"dia_fin ({self.dia_fin}) no puede ser menor que "
                f"dia_inicio ({self.dia_inicio})"
            )
        return self


class EtapaHortalizaCreate(EtapaHortalizaBase):
    pass


class EtapaHortalizaResponse(EtapaHortalizaBase):
    id: int
    hortaliza_id: int

    model_config = {"from_attributes": True}


class HortalizaBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    nombre_cientifico: Optional[str] = Field(default=None, max_length=150)
    temp_min_c: float
    temp_max_c: float
    temp_ideal_c: float
    humedad_suelo_min_pct: float = Field(ge=0, le=100)
    humedad_suelo_max_pct: float = Field(ge=0, le=100)
    requerimiento_agua_semanal_mm: float = Field(ge=0)
    radiacion_solar_min_wm2: Optional[float] = Field(default=None, ge=0)
    radiacion_solar_max_wm2: Optional[float] = Field(default=None, ge=0)
    altitud_min_msnm: Optional[float] = Field(default=None, ge=0)
    altitud_max_msnm: Optional[float] = Field(default=None, ge=0)
    sensibilidad_heladas: SensibilidadNivel = SensibilidadNivel.media
    sensibilidad_humedad_excesiva: SensibilidadNivel = SensibilidadNivel.media
    sensibilidad_viento: SensibilidadNivel = SensibilidadNivel.baja
    duracion_total_dias: int = Field(ge=1)
    notas_generales: Optional[str] = None

    @model_validator(mode="after")
    def validar_consistencia_agronomica(self):
        if self.temp_min_c >= self.temp_max_c:
            raise ValueError(
                f"temp_min_c ({self.temp_min_c}) debe ser menor que "
                f"temp_max_c ({self.temp_max_c})"
            )
        if not (self.temp_min_c <= self.temp_ideal_c <= self.temp_max_c):
            raise ValueError(
                f"temp_ideal_c ({self.temp_ideal_c}) debe estar entre "
                f"temp_min_c ({self.temp_min_c}) y temp_max_c ({self.temp_max_c})"
            )
        if self.humedad_suelo_min_pct >= self.humedad_suelo_max_pct:
            raise ValueError(
                f"humedad_suelo_min_pct ({self.humedad_suelo_min_pct}) debe ser "
                f"menor que humedad_suelo_max_pct ({self.humedad_suelo_max_pct})"
            )
        if (
            self.radiacion_solar_min_wm2 is not None
            and self.radiacion_solar_max_wm2 is not None
            and self.radiacion_solar_min_wm2 >= self.radiacion_solar_max_wm2
        ):
            raise ValueError(
                "radiacion_solar_min_wm2 debe ser menor que radiacion_solar_max_wm2"
            )
        if (
            self.altitud_min_msnm is not None
            and self.altitud_max_msnm is not None
            and self.altitud_min_msnm >= self.altitud_max_msnm
        ):
            raise ValueError("altitud_min_msnm debe ser menor que altitud_max_msnm")
        return self


class HortalizaCreate(HortalizaBase):
    etapas: list[EtapaHortalizaCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_etapas_contra_ciclo(self):
        for etapa in self.etapas:
            if etapa.dia_fin > self.duracion_total_dias:
                raise ValueError(
                    f"La etapa '{etapa.nombre_etapa}' termina el dia "
                    f"{etapa.dia_fin} pero el ciclo de la hortaliza dura "
                    f"{self.duracion_total_dias} dias"
                )
        return self


class HortalizaUpdate(HortalizaBase):
    """Actualizacion completa de una hortaliza (PUT)."""

    etapas: list[EtapaHortalizaCreate] = Field(default_factory=list)


class HortalizaResponse(HortalizaBase):
    id: int
    etapas: list[EtapaHortalizaResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
