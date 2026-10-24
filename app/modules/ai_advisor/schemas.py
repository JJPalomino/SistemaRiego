from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class NivelUrgencia(str, Enum):
    informativa = "informativa"
    precaucion = "precaucion"
    critica = "critica"


class Alerta(BaseModel):
    tipo: str = "alerta"
    descripcion: str = ""
    nivel: NivelUrgencia = NivelUrgencia.informativa

    model_config = {"from_attributes": True}

    @field_validator("nivel", mode="before")
    @classmethod
    def normalizar_nivel(cls, valor):
        if isinstance(valor, NivelUrgencia):
            return valor
        if isinstance(valor, str):
            normalizado = valor.strip().lower()
            if normalizado in {n.value for n in NivelUrgencia}:
                return normalizado
        return NivelUrgencia.informativa


class SolicitudRecomendacion(BaseModel):

    siembra_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Siembra registrada. Habilita el historial reproducible.",
    )
    parcela_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Parcela para asociar la lectura climatica y el historial.",
    )
    id_hortaliza: Optional[int] = Field(default=None, gt=0)
    dias_siembra: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Dias transcurridos desde la siembra. Se usa para ubicar la etapa "
            "fenologica actual del cultivo."
        ),
    )
    latitud: float = Field(
        default=19.2236,
        ge=-90,
        le=90,
        description="Latitud de la microparcela.",
    )
    longitud: float = Field(
        default=-97.8528,
        ge=-180,
        le=180,
        description="Longitud de la microparcela.",
    )
    dias_pronostico: int = Field(default=7, ge=1, le=16)

    @model_validator(mode="after")
    def validar_origen(self):
        if self.siembra_id is None and (
            self.id_hortaliza is None or self.dias_siembra is None
        ):
            raise ValueError(
                "Indica 'siembra_id', o bien 'id_hortaliza' y 'dias_siembra'"
            )
        return self


class ClimaPronostico(BaseModel):
    latitud: float
    longitud: float
    fecha_inicio_pronostico: Optional[str] = None
    fecha_fin_pronostico: Optional[str] = None
    dias_pronostico: int = 0
    precipitacion_mm: float = 0.0
    evapotranspiracion_ref_mm: float = 0.0
    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    temperatura_bulbo_seco_c: Optional[float] = None
    velocidad_viento_kmh: Optional[float] = None
    probabilidad_precipitacion_pct: Optional[float] = None
    radiacion_solar_wm2: Optional[float] = None
    radiacion_solar_mj_m2_dia: Optional[float] = None
    humedad_relativa_pct: Optional[float] = None
    punto_rocio_c: Optional[float] = None
    temperatura_suelo_c: Optional[float] = None
    humedad_suelo_pct: Optional[float] = None
    cobertura_nubes_pct: Optional[float] = None
    fuente: str = "open_meteo"


class RecomendacionResponse(BaseModel):
    id_hortaliza: int
    nombre_hortaliza: str
    etapa: Optional[str] = None
    dias_siembra: int
    clima: ClimaPronostico
    recomendacion_riego: str
    recomendacion_general: str
    alertas: list[Alerta] = Field(default_factory=list)
    nivel_urgencia_max: NivelUrgencia = NivelUrgencia.informativa
    modelo_llm: Optional[str] = None
    demo_mode: bool = False
    id_consulta: Optional[int] = None
    generado_en: datetime

    @field_validator("nivel_urgencia_max", mode="before")
    @classmethod
    def normalizar_urgencia(cls, valor):
        if isinstance(valor, str):
            normalizado = valor.strip().lower()
            if normalizado in {n.value for n in NivelUrgencia}:
                return normalizado
        return NivelUrgencia.informativa


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------

class LecturaClimaticaResumen(BaseModel):
    id: int
    parcela_id: int
    consultado_en: Optional[datetime] = None
    fecha_inicio_pronostico: Optional[str] = None
    fecha_fin_pronostico: Optional[str] = None
    dias_pronostico: int
    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    temperatura_bulbo_seco_c: Optional[float] = None
    punto_rocio_c: Optional[float] = None
    humedad_relativa_pct: Optional[float] = None
    velocidad_viento_kmh: Optional[float] = None
    temperatura_suelo_c: Optional[float] = None
    humedad_suelo_pct: Optional[float] = None
    precipitacion_mm: Optional[float] = None
    evapotranspiracion_ref_mm: Optional[float] = None
    probabilidad_precipitacion_pct: Optional[float] = None
    radiacion_solar_wm2: Optional[float] = None
    radiacion_solar_mj_m2_dia: Optional[float] = None
    cobertura_nubes_pct: Optional[float] = None
    fuente: str
    model_config = {"from_attributes": True}


class LecturaClimaticaDetalle(LecturaClimaticaResumen):
    datos_json: dict


class ConsultaRecomendacionResumen(BaseModel):
    id: int
    parcela_id: Optional[int] = None
    siembra_id: Optional[int] = None
    lectura_climatica_id: Optional[int] = None
    hortaliza_id: Optional[int] = None
    nombre_hortaliza: str
    etapa: Optional[str] = None
    dias_siembra: int
    recomendacion_riego: str
    recomendacion_general: str
    nivel_urgencia_max: NivelUrgencia = NivelUrgencia.informativa
    modelo_llm: Optional[str] = None
    demo_mode: bool = False
    consultado_en: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ConsultaRecomendacionDetalle(ConsultaRecomendacionResumen):
    prompt: str
    respuesta_json: dict
