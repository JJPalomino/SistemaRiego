"""Historial reproducible de clima y recomendaciones.

El documento del proyecto exige dos cosas que no se pueden reconstruir despues:
guardar la respuesta completa de Open-Meteo (JSON de respaldo) ademas de los
campos normalizados, y guardar cada recomendacion con el prompt exacto, la
respuesta integra del modelo y una fotografia del estado del cultivo (etapa y
dias transcurridos).

`reportes_generados` solo guarda metadatos: el PDF no se almacena, se genera
en el momento de la descarga.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LecturaClimatica(Base):
    """Una consulta a Open-Meteo para una parcela.

    `datos_json` conserva el payload completo tal como lo devolvio la API. Las
    columnas normalizadas existen para poder consultar y graficar sin abrir el
    JSON, no para reemplazarlo.
    """

    __tablename__ = "lecturas_climaticas"

    id:          Mapped[int]      = mapped_column(primary_key=True, index=True)
    parcela_id:  Mapped[int]      = mapped_column(
        ForeignKey("parcelas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consultado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fecha_inicio_pronostico: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    fecha_fin_pronostico:    Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    dias_pronostico:         Mapped[int]           = mapped_column(Integer, nullable=False)

    # Respaldo integro de la respuesta de la API.
    datos_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Campos normalizados que usa el motor de recomendacion.
    temp_max_c:                    Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    temp_min_c:                    Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    temperatura_bulbo_seco_c:      Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    punto_rocio_c:                 Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    humedad_relativa_pct:          Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    velocidad_viento_kmh:          Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    temperatura_suelo_c:           Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    humedad_suelo_pct:             Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    precipitacion_mm:              Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    evapotranspiracion_ref_mm:     Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    probabilidad_precipitacion_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    radiacion_solar_wm2:           Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    radiacion_solar_mj_m2_dia:     Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    cobertura_nubes_pct:           Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    fuente:                        Mapped[str]           = mapped_column(
        String(30), nullable=False, default="open_meteo"
    )


class ConsultaRecomendacion(Base):
    """Fotografia completa de una recomendacion generada.

    Las claves foraneas usan `SET NULL` a proposito: si el productor borra una
    siembra o una parcela, el historial no debe desaparecer. Por eso tambien se
    guardan columnas de texto con el nombre del cultivo y la etapa calculada.
    """

    __tablename__ = "consultas_recomendaciones"

    id:                     Mapped[int] = mapped_column(primary_key=True, index=True)
    parcela_id:             Mapped[Optional[int]] = mapped_column(
        ForeignKey("parcelas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    siembra_id:             Mapped[Optional[int]] = mapped_column(
        ForeignKey("siembras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lectura_climatica_id:   Mapped[Optional[int]] = mapped_column(
        ForeignKey("lecturas_climaticas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hortaliza_id:           Mapped[Optional[int]] = mapped_column(
        ForeignKey("hortalizas.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Snapshot legible, independiente del catalogo actual.
    nombre_hortaliza:  Mapped[str] = mapped_column(String(100), nullable=False)
    etapa:             Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dias_siembra:      Mapped[int] = mapped_column(Integer, nullable=False)

    # Reproducibilidad exacta.
    prompt:            Mapped[str] = mapped_column(Text, nullable=False)
    respuesta_json:    Mapped[dict] = mapped_column(JSON, nullable=False)

    # Campos extraidos para consultar el historial sin abrir el JSON.
    recomendacion_riego:   Mapped[str] = mapped_column(Text, nullable=False)
    recomendacion_general: Mapped[str] = mapped_column(Text, nullable=False)
    nivel_urgencia_max:    Mapped[str] = mapped_column(String(20), nullable=False)
    modelo_llm:            Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    demo_mode:             Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    consultado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReporteGenerado(Base):
    """Metadatos de un PDF emitido.

    El archivo no se guarda en el servidor: se genera al momento y se descarga.
    Esta tabla solo deja rastro de que usuario lo pidio, para que siembra y
    cuando.
    """

    __tablename__ = "reportes_generados"

    id:           Mapped[int] = mapped_column(primary_key=True, index=True)
    usuario_id:   Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    siembra_id:   Mapped[Optional[int]] = mapped_column(
        ForeignKey("siembras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    consulta_id:  Mapped[Optional[int]] = mapped_column(
        ForeignKey("consultas_recomendaciones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generado_en:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
