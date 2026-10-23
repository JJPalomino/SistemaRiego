import httpx
from typing import Optional

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

TIMEOUT_SEGUNDOS = 30.0
MAX_REINTENTOS = 3


class ErrorClima(RuntimeError):
    """No se pudo obtener el pronostico climatico."""


def _obtener_json(url: str, params: dict) -> dict:
    """GET con reintentos ante fallos transitorios de la API."""
    ultimo_error: Optional[Exception] = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEGUNDOS) as client:
                respuesta = client.get(url, params=params)
                if respuesta.status_code in (429, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"Open-Meteo respondio {respuesta.status_code}",
                        request=respuesta.request,
                        response=respuesta,
                    )
                respuesta.raise_for_status()
                return respuesta.json()
        except (httpx.HTTPError, httpx.InvalidURL) as e:
            ultimo_error = e
            if intento < MAX_REINTENTOS:
                continue

    raise ErrorClima(
        f"No se pudo consultar Open-Meteo tras {MAX_REINTENTOS} intentos: {ultimo_error}"
    )


def obtener_altitud(latitud: float, longitud: float) -> float:
    """Altitud en metros sobre el nivel del mar (msnm)."""
    data = _obtener_json(
        ELEVATION_URL, {"latitude": latitud, "longitude": longitud}
    )
    elevaciones = data.get("elevation") or []
    if not elevaciones or elevaciones[0] is None:
        raise ErrorClima("Open-Meteo no devolvio la altitud solicitada")
    return float(elevaciones[0])


def obtener_clima(
    latitud: float,
    longitud: float,
    dias_pronostico: int = 7,
    incluir_json_raw: bool = False,
) -> dict:
    """Pronostico de 7 dias desde Open-Meteo, normalizado a las unidades que
    usa el modelo de cultivos.

    Correcciones de unidades aplicadas (antes se mezclaban):
      - `soil_moisture_0_to_1cm` viene como fraccion 0-1. Se convierte a
        porcentaje (x100) porque el modelo `Hortaliza` define
        `humedad_suelo_min_pct` / `humedad_suelo_max_pct` en escala 0-100.
        Sin esta conversion el LLM recibia 0.06 contra umbrales de 60-85 y
        reportaba una alerta critica falsa.
      - `shortwave_radiation` por hora viene en W/m2 (instanteaneo). Se promedia
        para obtener radiacion solar media en W/m2, coherente con
        `radiacion_solar_min_wm2` / `radiacion_solar_max_wm2` del modelo.
        Antes se usaba `shortwave_radiation_sum` (MJ/m2/dia) etiquetado como
        W/m2, que es una comparacion sin sentido.
    """
    params = {
        "latitude": latitud,
        "longitude": longitud,
        "daily": [
            "precipitation_sum",
            "temperature_2m_max",
            "temperature_2m_min",
            "windspeed_10m_max",
            "et0_fao_evapotranspiration",
            "precipitation_probability_max",
            "shortwave_radiation_sum",
            "weathercode",
        ],
        "hourly": [
            "relativehumidity_2m",
            "dewpoint_2m",
            "soil_temperature_0cm",
            "soil_moisture_0_to_1cm",
            "shortwave_radiation",
            "cloudcover",
        ],
        "timezone": "America/Mexico_City",
        "forecast_days": dias_pronostico,
    }

    data = _obtener_json(OPEN_METEO_URL, params)

    daily = data.get("daily", {}) or {}
    hourly = data.get("hourly", {}) or {}

    def promedio(valores) -> Optional[float]:
        limpios = [x for x in (valores or []) if x is not None]
        return round(sum(limpios) / len(limpios), 2) if limpios else None

    def total(valores) -> float:
        return round(sum(x for x in (valores or []) if x is not None), 2)

    # Humedad del suelo: fraccion 0-1 -> porcentaje 0-100.
    humedad_suelo_fraccion = promedio(hourly.get("soil_moisture_0_to_1cm"))
    humedad_suelo_pct = (
        round(humedad_suelo_fraccion * 100, 2)
        if humedad_suelo_fraccion is not None
        else None
    )

    resultado = {
        "latitud": latitud,
        "longitud": longitud,
        "fecha_inicio_pronostico": (daily.get("time") or [None])[0],
        "fecha_fin_pronostico": (daily.get("time") or [None])[-1],
        "dias_pronostico": len(daily.get("time") or []),
        # Precipitacion acumulada y ET0 acumulada: ambas en mm/semana.
        "precipitacion_mm": total(daily.get("precipitation_sum")),
        "evapotranspiracion_ref_mm": total(
            daily.get("et0_fao_evapotranspiration")
        ),
        "temp_max_c": max(
            (x for x in (daily.get("temperature_2m_max") or []) if x is not None),
            default=None,
        ),
        "temp_min_c": min(
            (x for x in (daily.get("temperature_2m_min") or []) if x is not None),
            default=None,
        ),
        "temperatura_bulbo_seco_c": promedio(
            (daily.get("temperature_2m_max") or [])
            + (daily.get("temperature_2m_min") or [])
        ),
        "velocidad_viento_kmh": promedio(daily.get("windspeed_10m_max")),
        "probabilidad_precipitacion_pct": promedio(
            daily.get("precipitation_probability_max")
        ),
        # Radiacion solar media en W/m2 (promedio de la radiacion instantanea).
        "radiacion_solar_wm2": promedio(hourly.get("shortwave_radiation")),
        # Energia diaria acumulada en MJ/m2/dia, se conserva como referencia.
        "radiacion_solar_mj_m2_dia": promedio(daily.get("shortwave_radiation_sum")),
        "humedad_relativa_pct": promedio(hourly.get("relativehumidity_2m")),
        "punto_rocio_c": promedio(hourly.get("dewpoint_2m")),
        "temperatura_suelo_c": promedio(hourly.get("soil_temperature_0cm")),
        "humedad_suelo_pct": humedad_suelo_pct,
        "cobertura_nubes_pct": promedio(hourly.get("cloudcover")),
        "fuente": "open_meteo",
    }

    if incluir_json_raw:
        # El payload completo es voluminoso: nunca va al prompt del LLM, pero
        # el asesor lo guarda en `lecturas_climaticas` como respaldo
        # reproducible de la consulta (requisito del documento).
        resultado["json_raw"] = data

    return resultado
