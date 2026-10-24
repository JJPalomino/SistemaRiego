from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.database import SessionLocal
from app.modules.ai_advisor import llm_client, weather_client
from app.modules.ai_advisor.models import (
    ConsultaRecomendacion,
    LecturaClimatica,
)
from app.modules.ai_advisor.schemas import (
    ClimaPronostico,
    RecomendacionResponse,
    SolicitudRecomendacion,
)
from app.modules.crops import services as crops_services
from app.modules.crops.models import Hortaliza
from app.modules.parcels import services as parcels_services
from app.modules.parcels.models import Parcela, Siembra

NIVELES_VALIDOS = {"informativa", "precaucion", "critica"}

class HortalizaNoEncontrada(Exception):
    """La culture solicitada no existe."""

class ConsultaNoEncontrada(Exception):
    """La consulta no existe."""

class LecturaClimaticaNoEncontrada(Exception):
    """La lectura climatica no existe."""

def _a_float(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return float(valor)
    return float(valor)


def _a_texto(valor: Any) -> Any:
    return getattr(valor, "value", valor)

def _hortaliza_para_prompt(hortaliza: Hortaliza) -> dict:
    return {
        "nombre": hortaliza.nombre,
        "temp_min_c": _a_float(hortaliza.temp_min_c),
        "temp_max_c": _a_float(hortaliza.temp_max_c),
        "temp_ideal_c": _a_float(hortaliza.temp_ideal_c),
        "humedad_suelo_min_pct": _a_float(hortaliza.humedad_suelo_min_pct),
        "humedad_suelo_max_pct": _a_float(hortaliza.humedad_suelo_max_pct),
        "requerimiento_agua_semanal_mm": _a_float(
            hortaliza.requerimiento_agua_semanal_mm
        ),
        "sensibilidad_heladas": _a_texto(hortaliza.sensibilidad_heladas),
        "sensibilidad_humedad_excesiva": _a_texto(
            hortaliza.sensibilidad_humedad_excesiva
        ),
        "sensibilidad_viento": _a_texto(hortaliza.sensibilidad_viento),
    }


def _sanear_alertas(alertas: Any) -> list:
    if not isinstance(alertas, list):
        return []
    limpias = []
    for alerta in alertas:
        if not isinstance(alerta, dict):
            continue
        nivel = _normalizar_urgencia(alerta.get("nivel"))
        limpias.append(
            {
                "tipo": str(alerta.get("tipo", "alerta")),
                "descripcion": str(alerta.get("descripcion", "")),
                "nivel": nivel,
            }
        )
    return limpias


def _normalizar_urgencia(valor: Any) -> str:
    if isinstance(valor, str):
        normalizado = valor.strip().lower()
        if normalizado in NIVELES_VALIDOS:
            return normalizado
    return "informativa"


# ---------------------------------------------------------------------------
# Persistencia del historial
# ---------------------------------------------------------------------------

def _guardar_lectura_climatica(
    db: Session, parcela_id: int, clima_raw: dict
) -> LecturaClimatica:
    """Guarda la consulta a Open-Meteo con su JSON integro de respaldo."""
    datos = {k: v for k, v in clima_raw.items() if k != "json_raw"}

    lectura = LecturaClimatica(
        parcela_id=parcela_id,
        fecha_inicio_pronostico=datos.get("fecha_inicio_pronostico"),
        fecha_fin_pronostico=datos.get("fecha_fin_pronostico"),
        dias_pronostico=datos.get("dias_pronostico") or 0,
        # Si el cliente no trajo el JSON crudo, se guarda un objeto vacio en
        # lugar de romper la insercion por un nulo.
        datos_json=clima_raw.get("json_raw") or {},
        temp_max_c=datos.get("temp_max_c"),
        temp_min_c=datos.get("temp_min_c"),
        temperatura_bulbo_seco_c=datos.get("temperatura_bulbo_seco_c"),
        punto_rocio_c=datos.get("punto_rocio_c"),
        humedad_relativa_pct=datos.get("humedad_relativa_pct"),
        velocidad_viento_kmh=datos.get("velocidad_viento_kmh"),
        temperatura_suelo_c=datos.get("temperatura_suelo_c"),
        humedad_suelo_pct=datos.get("humedad_suelo_pct"),
        precipitacion_mm=datos.get("precipitacion_mm"),
        evapotranspiracion_ref_mm=datos.get("evapotranspiracion_ref_mm"),
        probabilidad_precipitacion_pct=datos.get(
            "probabilidad_precipitacion_pct"
        ),
        radiacion_solar_wm2=datos.get("radiacion_solar_wm2"),
        radiacion_solar_mj_m2_dia=datos.get("radiacion_solar_mj_m2_dia"),
        cobertura_nubes_pct=datos.get("cobertura_nubes_pct"),
        fuente=datos.get("fuente") or "open_meteo",
    )
    db.add(lectura)
    db.commit()
    db.refresh(lectura)
    return lectura


def _guardar_consulta(
    db: Session,
    *,
    parcela: Optional[Parcela],
    siembra: Optional[Siembra],
    hortaliza: Hortaliza,
    etapa: str,
    dias: int,
    lectura: Optional[LecturaClimatica],
    prompt: str,
    recomendacion: dict,
    nivel: str,
) -> ConsultaRecomendacion:
    """Guarda la fotografia exacta de la recomendacion.

    'respuesta_json' conserva la salida integra del modelo; las columnas de
    texto son solo una copia comoda para listar el historial.
    """
    consulta = ConsultaRecomendacion(
        parcela_id=parcela.id if parcela is not None else None,
        siembra_id=siembra.id if siembra is not None else None,
        lectura_climatica_id=lectura.id if lectura is not None else None,
        hortaliza_id=hortaliza.id,
        nombre_hortaliza=hortaliza.nombre,
        etapa=etapa,
        dias_siembra=dias,
        prompt=prompt,
        respuesta_json=recomendacion,
        recomendacion_riego=str(
            recomendacion.get("recomendacion_riego", "")
        ).strip(),
        recomendacion_general=str(
            recomendacion.get("recomendacion_general", "")
        ).strip(),
        nivel_urgencia_max=nivel,
        modelo_llm=None if settings.DEMO_MODE else settings.GEMINI_MODEL,
        demo_mode=settings.DEMO_MODE,
    )
    db.add(consulta)
    db.commit()
    db.refresh(consulta)
    return consulta


def _guardar_lectura_climatica_tx(
    db: Session, parcela_id: int, clima_raw: dict
) -> LecturaClimatica:
    """Versión para transacción unificada (sin commit/refresh)."""
    datos = {k: v for k, v in clima_raw.items() if k != "json_raw"}

    lectura = LecturaClimatica(
        parcela_id=parcela_id,
        fecha_inicio_pronostico=datos.get("fecha_inicio_pronostico"),
        fecha_fin_pronostico=datos.get("fecha_fin_pronostico"),
        dias_pronostico=datos.get("dias_pronostico") or 0,
        datos_json=clima_raw.get("json_raw") or {},
        temp_max_c=datos.get("temp_max_c"),
        temp_min_c=datos.get("temp_min_c"),
        temperatura_bulbo_seco_c=datos.get("temperatura_bulbo_seco_c"),
        punto_rocio_c=datos.get("punto_rocio_c"),
        humedad_relativa_pct=datos.get("humedad_relativa_pct"),
        velocidad_viento_kmh=datos.get("velocidad_viento_kmh"),
        temperatura_suelo_c=datos.get("temperatura_suelo_c"),
        humedad_suelo_pct=datos.get("humedad_suelo_pct"),
        precipitacion_mm=datos.get("precipitacion_mm"),
        evapotranspiracion_ref_mm=datos.get("evapotranspiracion_ref_mm"),
        probabilidad_precipitacion_pct=datos.get(
            "probabilidad_precipitacion_pct"
        ),
        radiacion_solar_wm2=datos.get("radiacion_solar_wm2"),
        radiacion_solar_mj_m2_dia=datos.get("radiacion_solar_mj_m2_dia"),
        cobertura_nubes_pct=datos.get("cobertura_nubes_pct"),
        fuente=datos.get("fuente") or "open_meteo",
    )
    db.add(lectura)
    db.flush()
    return lectura


def _guardar_consulta_tx(
    db: Session,
    *,
    parcela_id: Optional[int],
    siembra_id: Optional[int],
    hortaliza_id: int,
    nombre_hortaliza: str,
    etapa: str,
    dias: int,
    lectura_id: Optional[int],
    prompt: str,
    recomendacion: dict,
    nivel: str,
) -> ConsultaRecomendacion:
    """Versión para transacción unificada (sin commit/refresh)."""
    consulta = ConsultaRecomendacion(
        parcela_id=parcela_id,
        siembra_id=siembra_id,
        lectura_climatica_id=lectura_id,
        hortaliza_id=hortaliza_id,
        nombre_hortaliza=nombre_hortaliza,
        etapa=etapa,
        dias_siembra=dias,
        prompt=prompt,
        respuesta_json=recomendacion,
        recomendacion_riego=str(
            recomendacion.get("recomendacion_riego", "")
        ).strip(),
        recomendacion_general=str(
            recomendacion.get("recomendacion_general", "")
        ).strip(),
        nivel_urgencia_max=nivel,
        modelo_llm=None if settings.DEMO_MODE else settings.GEMINI_MODEL,
        demo_mode=settings.DEMO_MODE,
    )
    db.add(consulta)
    db.flush()
    return consulta


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def generar_recomendacion(
    db: Session, usuario_id: int, solicitud: SolicitudRecomendacion
) -> RecomendacionResponse:
    """Orquesta el flujo: cultivo -> etapa -> clima -> LLM -> historial."""
    siembra: Optional[Siembra] = None
    parcela: Optional[Parcela] = None

    if solicitud.siembra_id is not None:
        siembra = parcels_services.obtener_siembra_por_id(
            db, usuario_id, solicitud.siembra_id
        )
        parcela = siembra.parcela
        hortaliza = siembra.hortaliza
        dias = siembra.dias_desde_siembra
    else:
        try:
            hortaliza = crops_services.obtener_hortaliza(
                db, solicitud.id_hortaliza
            )
        except crops_services.HortalizaNoEncontrada as e:
            raise HortalizaNoEncontrada(str(e)) from e

        dias = solicitud.dias_siembra
        if solicitud.parcela_id is not None:
            parcela = parcels_services.obtener_parcela(
                db, usuario_id, solicitud.parcela_id
            )

    latitud = float(parcela.latitud) if parcela is not None else solicitud.latitud
    longitud = (
        float(parcela.longitud) if parcela is not None else solicitud.longitud
    )

    etapa = crops_services.obtener_etapa_actual(db, hortaliza.id, dias)
    nombre_etapa = (
        etapa.nombre_etapa if etapa is not None else "Sin etapa definida"
    )

    parcela_id_ctx = parcela.id if parcela is not None else None
    siembra_id_ctx = siembra.id if siembra is not None else None
    hortaliza_id_ctx = hortaliza.id
    nombre_hortaliza_ctx = hortaliza.nombre
    hortaliza_prompt = _hortaliza_para_prompt(hortaliza)
    guardar_historial = parcela is not None or siembra is not None

    try:
        db.close()
    except Exception:
        pass

    clima_raw = weather_client.obtener_clima(
        latitud=latitud,
        longitud=longitud,
        dias_pronostico=solicitud.dias_pronostico,
        incluir_json_raw=parcela_id_ctx is not None,
    )
    clima_datos = {k: v for k, v in clima_raw.items() if k != "json_raw"}
    clima = ClimaPronostico(**clima_datos)

    prompt = llm_client.construir_prompt(
        hortaliza_prompt, clima_datos, nombre_etapa, dias
    )

    recomendacion = llm_client.generar_recomendacion(
        hortaliza_prompt, clima_datos, nombre_etapa, dias
    )

    alertas = _sanear_alertas(recomendacion.get("alertas"))
    nivel = _normalizar_urgencia(recomendacion.get("nivel_urgencia_max"))

    recomendacion_saneada = dict(recomendacion)
    recomendacion_saneada["alertas"] = alertas
    recomendacion_saneada["nivel_urgencia_max"] = nivel

    bind = getattr(db, "bind", None)
    if bind is not None:
        SessionTx = sessionmaker(autocommit=False, autoflush=False, bind=bind)
        db_tx = SessionTx()
    else:
        db_tx = SessionLocal()
    try:
        with db_tx.begin():
            lectura = None
            if parcela_id_ctx is not None:
                lectura = _guardar_lectura_climatica_tx(db_tx, parcela_id_ctx, clima_raw)
            consulta = None
            if guardar_historial:
                consulta = _guardar_consulta_tx(
                    db_tx,
                    parcela_id=parcela_id_ctx,
                    siembra_id=siembra_id_ctx,
                    hortaliza_id=hortaliza_id_ctx,
                    nombre_hortaliza=nombre_hortaliza_ctx,
                    etapa=nombre_etapa,
                    dias=dias,
                    lectura_id=lectura.id if lectura is not None else None,
                    prompt=prompt,
                    recomendacion=recomendacion_saneada,
                    nivel=nivel,
                )
        if consulta is not None:
            db_tx.refresh(consulta)
        if lectura is not None:
            db_tx.refresh(lectura)
    finally:
        try:
            db_tx.close()
        except Exception:
            pass

    return RecomendacionResponse(
        id_hortaliza=hortaliza_id_ctx,
        nombre_hortaliza=nombre_hortaliza_ctx,
        etapa=nombre_etapa,
        dias_siembra=dias,
        clima=clima,
        recomendacion_riego=str(
            recomendacion_saneada.get("recomendacion_riego", "")
        ).strip(),
        recomendacion_general=str(
            recomendacion_saneada.get("recomendacion_general", "")
        ).strip(),
        alertas=alertas,
        nivel_urgencia_max=nivel,
        modelo_llm=None if settings.DEMO_MODE else settings.GEMINI_MODEL,
        demo_mode=settings.DEMO_MODE,
        id_consulta=consulta.id if consulta is not None else None,
        generado_en=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Consulta del historial
# ---------------------------------------------------------------------------

def listar_lecturas_climaticas(
    db: Session, usuario_id: int, parcela_id: int, limite: int = 20
) -> List[LecturaClimatica]:
    parcels_services.obtener_parcela(db, usuario_id, parcela_id)
    return (
        db.query(LecturaClimatica)
        .filter(LecturaClimatica.parcela_id == parcela_id)
        .order_by(LecturaClimatica.consultado_en.desc())
        .limit(limite)
        .all()
    )


def obtener_lectura_climatica(
    db: Session, usuario_id: int, lectura_id: int
) -> LecturaClimatica:
    lectura = (
        db.query(LecturaClimatica)
        .join(Parcela, LecturaClimatica.parcela_id == Parcela.id)
        .filter(
            LecturaClimatica.id == lectura_id,
            Parcela.usuario_id == usuario_id,
        )
        .first()
    )
    if lectura is None:
        raise LecturaClimaticaNoEncontrada(
            f"No existe la lectura climatica {lectura_id}"
        )
    return lectura


def listar_consultas(
    db: Session, usuario_id: int, siembra_id: int, limite: int = 20
) -> List[ConsultaRecomendacion]:
    parcels_services.obtener_siembra_por_id(db, usuario_id, siembra_id)
    return (
        db.query(ConsultaRecomendacion)
        .filter(ConsultaRecomendacion.siembra_id == siembra_id)
        .order_by(ConsultaRecomendacion.consultado_en.desc())
        .limit(limite)
        .all()
    )


def obtener_consulta(
    db: Session, usuario_id: int, consulta_id: int
) -> ConsultaRecomendacion:
    consulta = (
        db.query(ConsultaRecomendacion)
        .join(Parcela, ConsultaRecomendacion.parcela_id == Parcela.id)
        .filter(
            ConsultaRecomendacion.id == consulta_id,
            Parcela.usuario_id == usuario_id,
        )
        .first()
    )
    if consulta is None:
        raise ConsultaNoEncontrada(f"No existe la consulta {consulta_id}")
    return consulta


def obtener_ultima_consulta_de_siembra(
    db: Session, usuario_id: int, siembra_id: int
) -> ConsultaRecomendacion:
    parcels_services.obtener_siembra_por_id(db, usuario_id, siembra_id)
    consulta = (
        db.query(ConsultaRecomendacion)
        .filter(ConsultaRecomendacion.siembra_id == siembra_id)
        .order_by(ConsultaRecomendacion.consultado_en.desc())
        .first()
    )
    if consulta is None:
        raise ConsultaNoEncontrada(
            f"La siembra {siembra_id} no tiene recomendaciones registradas"
        )
    return consulta
