import json
import re
from typing import Optional

import httpx

from app.core.config import settings

# El modelo se define en `settings.GEMINI_MODEL` (por defecto `gemini-3.5-flash`).
# `gemini-1.5-flash`, que estaba antes hardcodeado, fue retirado de la API y
# devuelve 404. Para ver los modelos vigentes:
#   GET https://generativelanguage.googleapis.com/v1beta/models
GEMINI_URL = settings.gemini_generate_url

# Respuesta de demostracion: permite correr el sistema sin consumir cuota de
# Gemini (modo offline / sin conexion / pruebas).
RESPUESTA_DEMO = {
    "recomendacion_riego": (
        "Modo demostracion: aplica riego complementario para mantener la "
        "humedad del suelo dentro del rango optimo del cultivo, con riegos "
        "preferentemente por la manana."
    ),
    "recomendacion_general": (
        "Modo demostracion: revisa el estado fenologico de la culture y vigila "
        "la aparicion de enfermedades foliares asociadas a la humedad alta."
    ),
    "alertas": [
        {
            "tipo": "modo_demostracion",
            "descripcion": (
                "Respuesta generada localmente porque DEMO_MODE esta activo; "
                "no refleja un analisis del pronostico real."
            ),
            "nivel": "informativa",
        }
    ],
    "nivel_urgencia_max": "informativa",
}


class ErrorLLM(RuntimeError):
    """No se pudo obtener una recomendacion del modelo de lenguaje."""


def construir_prompt(
    hortaliza: dict, clima: dict, etapa: str, dias_siembra: int
) -> str:
    return f"""
Eres un agronomo experto en cultivos de hortalizas en la Sierra Nororiental de Puebla, Mexico.
Contexto: bosque de niebla, altitud 1900-3000 msnm, alta humedad ambiental, microparcelas a cielo abierto.

HORTALIZA: {hortaliza["nombre"]}
Etapa actual: {etapa} (dia {dias_siembra} desde la siembra)
Temp min tolerable: {hortaliza["temp_min_c"]} C
Temp max tolerable: {hortaliza["temp_max_c"]} C
Temp ideal: {hortaliza["temp_ideal_c"]} C
Humedad suelo optima: {hortaliza["humedad_suelo_min_pct"]}% - {hortaliza["humedad_suelo_max_pct"]}%
Requerimiento agua semanal: {hortaliza["requerimiento_agua_semanal_mm"]} mm
Sensibilidad heladas: {hortaliza["sensibilidad_heladas"]}
Sensibilidad humedad excesiva: {hortaliza["sensibilidad_humedad_excesiva"]}
Sensibilidad viento: {hortaliza["sensibilidad_viento"]}

PRONOSTICO CLIMATICO 7 DIAS:
Precipitacion total: {clima["precipitacion_mm"]} mm
Temperatura maxima: {clima["temp_max_c"]} C
Temperatura minima: {clima["temp_min_c"]} C
Humedad relativa promedio: {clima["humedad_relativa_pct"]}%
Punto de rocio: {clima["punto_rocio_c"]} C
Velocidad viento: {clima["velocidad_viento_kmh"]} km/h
Evapotranspiracion semanal: {clima["evapotranspiracion_ref_mm"]} mm
Humedad del suelo: {clima["humedad_suelo_pct"]}%
Radiacion solar media: {clima["radiacion_solar_wm2"]} W/m2
Cobertura nubes: {clima["cobertura_nubes_pct"]}%
Probabilidad lluvia: {clima["probabilidad_precipitacion_pct"]}%

Responde UNICAMENTE con un objeto JSON valido, sin markdown, sin explicaciones, con estas claves:
- "recomendacion_riego": instruccion concreta de riego para los proximos 7 dias
- "recomendacion_general": consejo de manejo agricola para esta semana
- "alertas": arreglo de objetos con las claves "tipo", "descripcion" y "nivel" (informativa, precaucion o critica)
- "nivel_urgencia_max": una de informativa, precaucion o critica
"""


def _extraer_json(texto: str) -> dict:
    """Saca el objeto JSON de la respuesta del modelo.

    El modelo puede devolver el JSON envuelto en ```json ... ``` o con texto
    alrededor; se recorta el bloque util antes de parsearlo.
    """
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\s*```$", "", limpio).strip()

    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        pass

    # Ultimo recurso: localizar el primer objeto JSON completo del texto.
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio != -1 and fin > inicio:
        return json.loads(limpio[inicio : fin + 1])

    raise ErrorLLM(
        f"El modelo no devolvio un JSON interpretable. Respuesta: {texto[:300]}"
    )


def generar_recomendacion(
    hortaliza: dict,
    clima: dict,
    etapa: str,
    dias_siembra: int,
) -> dict:
    """Genera la recomendacion de riego y manejo para los proximos 7 dias."""
    if settings.DEMO_MODE:
        return dict(RESPUESTA_DEMO)

    prompt = construir_prompt(hortaliza, clima, etapa, dias_siembra)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            # 1024 truncaba la respuesta a mitad de cadena y `json.loads`
            # fallaba con "Unterminated string". Con 4096 cabe completa.
            "maxOutputTokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
            # Obliga al modelo a responder JSON valido.
            "response_mime_type": "application/json",
        },
    }

    ultimo_error: Optional[Exception] = None

    for intento in range(1, settings.GEMINI_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=60.0) as client:
                respuesta = client.post(
                    GEMINI_URL,
                    params={"key": settings.GEMINI_API_KEY},
                    json=payload,
                )
                if respuesta.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"Gemini respondio {respuesta.status_code}",
                        request=respuesta.request,
                        response=respuesta,
                    )
                respuesta.raise_for_status()
                datos = respuesta.json()
                break
        except httpx.HTTPError as e:
            ultimo_error = e
            if intento < settings.GEMINI_MAX_RETRIES:
                continue
            raise ErrorLLM(
                f"No se pudo consultar Gemini tras "
                f"{settings.GEMINI_MAX_RETRIES} intentos: {e}"
            ) from e
    else:
        raise ErrorLLM(f"Fallo la consulta a Gemini: {ultimo_error}")

    try:
        candidatos = datos["candidates"]
        partes = candidatos[0]["content"]["parts"]
        texto = partes[0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise ErrorLLM(f"Respuesta inesperada de Gemini: {datos}") from e

    motivo_fin = (candidatos[0].get("finishReason") or "").upper()
    if motivo_fin == "MAX_TOKENS":
        raise ErrorLLM(
            "La respuesta del modelo fue truncada por limite de tokens "
            f"({settings.GEMINI_MAX_OUTPUT_TOKENS}). "
            "Aumenta GEMINI_MAX_OUTPUT_TOKENS."
        )

    return _extraer_json(texto)
