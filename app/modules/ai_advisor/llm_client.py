import copy
import json
import random
import re
import time
from typing import Optional

import httpx

from app.core.config import settings

# La cadena de modelos se define en settings.GEMINI_MODEL y
# settings.GEMINI_MODELOS_RESPALDO.

# Respuesta de demostracion para operar sin consumir cuota de Gemini.
RESPUESTA_DEMO = {
    "recomendacion_riego": (
        "Modo demostracion: aplica riego complementario para mantener la "
        "humedad del suelo dentro del rango optimo del cultivo, con riegos "
        "preferentemente por la manana."
    ),
    "recomendacion_general": (
        "Modo demostracion: revisa el estado fenologico del cultivo y vigila "
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


class RecomendacionLLM(dict):
    """Recomendacion del modelo que recuerda cual la genero.

    Es un dict normal, pero conserva modelo_llm para guardar en el historial
    el modelo que respondio realmente.
    """

    modelo_llm: Optional[str] = None


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

    El modelo puede devolver el JSON envuelto en 'json ...' o con texto
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
        try:
            return json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError as e:
            raise ErrorLLM(
                f"El modelo no devolvio un JSON interpretable. Respuesta: {texto[:300]}"
            ) from e

    raise ErrorLLM(
        f"El modelo no devolvio un JSON interpretable. Respuesta: {texto[:300]}"
    )


def _parsear_respuesta(datos: dict, modelo: str) -> RecomendacionLLM:
    """Extrae el JSON de una respuesta 200 de Gemini."""
    try:
        candidatos = datos["candidates"]
        partes = candidatos[0]["content"]["parts"]
        texto = partes[0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ErrorLLM("Respuesta inesperada de Gemini") from None

    motivo_fin = (candidatos[0].get("finishReason") or "").upper()
    if motivo_fin == "MAX_TOKENS":
        raise ErrorLLM(
            "La respuesta del modelo fue truncada por limite de tokens "
            f"({settings.GEMINI_MAX_OUTPUT_TOKENS}). "
            "Aumenta GEMINI_MAX_OUTPUT_TOKENS."
        )

    recomendacion = RecomendacionLLM(_extraer_json(texto))
    recomendacion.modelo_llm = modelo
    return recomendacion


def generar_recomendacion(
    hortaliza: dict,
    clima: dict,
    etapa: str,
    dias_siembra: int,
) -> dict:
    """Genera la recomendacion de riego y manejo para los proximos 7 dias.

    Recorre settings.gemini_modelos (principal y respaldos): un 429 pasa al
    siguiente modelo, mientras que un 5xx o un fallo de red se reintenta con
    una espera corta. El recorrido respeta GEMINI_TOTAL_TIMEOUT_S.
    """
    if settings.DEMO_MODE:
        recomendacion = RecomendacionLLM(copy.deepcopy(RESPUESTA_DEMO))
        recomendacion.modelo_llm = None
        return recomendacion

    prompt = construir_prompt(hortaliza, clima, etapa, dias_siembra)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            # Permite que quepan completos los dos textos y las alertas.
            "maxOutputTokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
            # Obliga al modelo a responder JSON valido.
            "responseMimeType": "application/json",
        },
    }

    clave = (settings.GEMINI_API_KEY or "").strip()
    modelos = settings.gemini_modelos
    inicio = time.monotonic()
    errores: list[str] = []

    for modelo in modelos:
        url = settings.gemini_url_para(modelo)
        for intento in range(1, settings.GEMINI_MAX_RETRIES + 1):
            restante = settings.GEMINI_TOTAL_TIMEOUT_S - (time.monotonic() - inicio)
            if restante <= 1.0:
                errores.append("tiempo total agotado")
                break

            try:
                with httpx.Client(
                    timeout=min(settings.GEMINI_TIMEOUT_S, restante)
                ) as cliente:
                    respuesta = cliente.post(
                        url,
                        params={"key": clave},
                        json=payload,
                    )
                if respuesta.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"{modelo} respondio {respuesta.status_code}",
                        request=respuesta.request,
                        response=respuesta,
                    )
                respuesta.raise_for_status()
                datos = respuesta.json()
            except httpx.HTTPStatusError as e:
                codigo = (
                    e.response.status_code if e.response is not None else "desconocido"
                )
                errores.append(f"{modelo}: HTTP {codigo}")
                if codigo == 429:
                    # Cuota diaria agotada para este modelo: no se reintenta.
                    break
                if intento < settings.GEMINI_MAX_RETRIES:
                    time.sleep(min(0.5 * intento + random.uniform(0.0, 0.2), 3.0))
                    continue
                break
            except httpx.HTTPError as e:
                # No exponemos la URL con la API key.
                errores.append(f"{modelo}: {type(e).__name__}")
                if intento < settings.GEMINI_MAX_RETRIES:
                    time.sleep(min(0.5 * intento + random.uniform(0.0, 0.2), 3.0))
                    continue
                break

            # HTTP 200: si el contenido no sirve, se prueba el siguiente modelo.
            try:
                return _parsear_respuesta(datos, modelo)
            except ErrorLLM as e:
                errores.append(f"{modelo}: {e}")
                break

    detalle = "; ".join(errores) if errores else "sin intentos"
    raise ErrorLLM(
        "No se pudo generar la recomendacion con ninguno de los modelos "
        f"configurados ({', '.join(modelos)}). Intentos: {detalle}"
    )

