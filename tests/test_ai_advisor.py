"""Pruebas del asesor de IA.

Se aislan las dos dependencias externas (Open-Meteo y Gemini) para que la
suite sea determinista y no consuma cuota.
"""

import json

import pytest

from app.modules.ai_advisor import llm_client, weather_client
from app.modules.ai_advisor.schemas import SolicitudRecomendacion
from tests.test_crops import CARGA_LECHUGA

CLIMA_FALSO = {
    "latitud": 19.2236,
    "longitud": -97.8528,
    "fecha_inicio_pronostico": "2026-10-21",
    "fecha_fin_pronostico": "2026-10-27",
    "dias_pronostico": 7,
    "precipitacion_mm": 8.0,
    "evapotranspiracion_ref_mm": 24.03,
    "temp_max_c": 21.9,
    "temp_min_c": 7.0,
    "temperatura_bulbo_seco_c": 14.45,
    "velocidad_viento_kmh": 15.87,
    "probabilidad_precipitacion_pct": 24.57,
    "radiacion_solar_wm2": 234.85,
    "radiacion_solar_mj_m2_dia": 18.01,
    "humedad_relativa_pct": 65.9,
    "punto_rocio_c": 7.24,
    "temperatura_suelo_c": 16.2,
    # Porcentaje, no fraccion: el bug original enviaba 0.06 al prompt.
    "humedad_suelo_pct": 6.0,
    "cobertura_nubes_pct": 69.2,
    "fuente": "open_meteo",
}

RESPUESTA_LLM = {
    "recomendacion_riego": "Riego complementario de 16 mm en dos aplicaciones.",
    "recomendacion_general": "Revisar enfermedades foliares.",
    "alertas": [
        {
            "tipo": "viento",
            "descripcion": "Viento fuerte en la tarde.",
            "nivel": "precaucion",
        }
    ],
    "nivel_urgencia_max": "precaucion",
}


HORTALIZA_COMPLETA = {
    "nombre": "Lechuga",
    "temp_min_c": 4.0,
    "temp_max_c": 24.0,
    "temp_ideal_c": 15.0,
    "humedad_suelo_min_pct": 60.0,
    "humedad_suelo_max_pct": 85.0,
    "requerimiento_agua_semanal_mm": 25.0,
    "sensibilidad_heladas": "media",
    "sensibilidad_humedad_excesiva": "alta",
    "sensibilidad_viento": "baja",
}


class _FakeRespuesta:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "candidates": [
                {
                    "content": {"parts": [{"text": json.dumps(RESPUESTA_LLM)}]},
                    "finishReason": "STOP",
                }
            ]
        }


class _FakeClient:
    """Sustituye httpx.Client y captura el payload enviado a Gemini."""

    capturado = {}

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        _FakeClient.capturado["url"] = url
        _FakeClient.capturado["payload"] = kwargs["json"]
        return _FakeRespuesta()


@pytest.fixture
def culture(client, headers):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def sin_servicios_externos(monkeypatch):
    """Sustituye Open-Meteo y Gemini por respuestas controladas."""
    from app.modules.ai_advisor import services

    monkeypatch.setattr(
        services.weather_client,
        "obtener_clima",
        lambda *a, **k: dict(CLIMA_FALSO),
    )
    monkeypatch.setattr(
        services.llm_client,
        "generar_recomendacion",
        lambda *a, **k: dict(RESPUESTA_LLM),
    )
    return services


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


def test_endpoint_requiere_token(client, culture):
    r = client.post(
        "/api/v1/ai/recomendacion",
        json={"id_hortaliza": culture["id"], "dias_siembra": 25},
    )
    assert r.status_code == 401


def test_endpoint_hortaliza_inexistente(client, headers):
    r = client.post(
        "/api/v1/ai/recomendacion",
        json={"id_hortaliza": 9999, "dias_siembra": 10},
        headers=headers,
    )
    assert r.status_code == 404


def test_recomendacion_completa(
    client, headers, culture, sin_servicios_externos
):
    r = client.post(
        "/api/v1/ai/recomendacion",
        json={"id_hortaliza": culture["id"], "dias_siembra": 25},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["recomendacion_riego"] == RESPUESTA_LLM["recomendacion_riego"]
    assert cuerpo["etapa"] == "Crecimiento vegetativo"
    assert cuerpo["dias_siembra"] == 25
    assert cuerpo["alertas"][0]["nivel"] == "precaucion"
    assert cuerpo["nivel_urgencia_max"] == "precaucion"
    # El clima viaja con las unidades ya normalizadas.
    assert cuerpo["clima"]["humedad_suelo_pct"] == 6.0
    assert cuerpo["clima"]["radiacion_solar_wm2"] == 234.85


def test_etapa_segun_dia_siembra(client, headers, culture, sin_servicios_externos):
    r = client.post(
        "/api/v1/ai/recomendacion",
        json={"id_hortaliza": culture["id"], "dias_siembra": 5},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["etapa"] == "Germinacion"


# --------------------------------------------------------------------------
# Cliente LLM
# --------------------------------------------------------------------------


def test_demo_mode_no_llama_a_gemini(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", True)

    def _no_debe_llamar(*args, **kwargs):
        raise AssertionError("no se debio llamar a Gemini en modo demo")

    monkeypatch.setattr(llm_client.httpx, "Client", _no_debe_llamar)

    resultado = llm_client.generar_recomendacion(
        HORTALIZA_COMPLETA, CLIMA_FALSO, "Crecimiento", 25
    )
    assert resultado["nivel_urgencia_max"] == "informativa"
    assert resultado["alertas"][0]["tipo"] == "modo_demostracion"


def test_prompt_incluye_unidades_corregidas(monkeypatch):
    """La humedad del suelo debe viajar como porcentaje, no como fraccion."""
    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", False)
    _FakeClient.capturado = {}
    monkeypatch.setattr(llm_client.httpx, "Client", _FakeClient)

    resultado = llm_client.generar_recomendacion(
        HORTALIZA_COMPLETA,
        CLIMA_FALSO,
        "Crecimiento vegetativo",
        25,
    )

    assert resultado["nivel_urgencia_max"] == "precaucion"

    capturado = _FakeClient.capturado
    prompt = capturado["payload"]["contents"][0]["parts"][0]["text"]

    # Correccion 1: humedad del suelo en porcentaje.
    assert "Humedad del suelo: 6.0%" in prompt
    assert "0.06%" not in prompt

    # Correccion 2: radiacion solar en W/m2.
    assert "Radiacion solar media: 234.85 W/m2" in prompt

    # Correccion 3: modelo vigente, no el retirado.
    assert "gemini-1.5-flash" not in capturado["url"]
    assert capturado["url"].endswith(f"{llm_client.settings.GEMINI_MODEL}:generateContent")

    # Correccion 4: presupuesto de tokens suficiente y salida JSON forzada.
    config = capturado["payload"]["generationConfig"]
    assert config["maxOutputTokens"] >= 4096
    assert config["response_mime_type"] == "application/json"


def test_respuesta_truncada_lanza_error(monkeypatch):
    class _RespuestaTruncada(_FakeRespuesta):
        def json(self):
            return {
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"a": 1'}]},
                        "finishReason": "MAX_TOKENS",
                    }
                ]
            }

    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", False)
    monkeypatch.setattr(llm_client.httpx, "Client", _FakeClient)
    monkeypatch.setattr(
        _FakeClient, "post", lambda self, url, **kw: _RespuestaTruncada()
    )

    with pytest.raises(llm_client.ErrorLLM, match="truncada"):
        llm_client.generar_recomendacion(
            HORTALIZA_COMPLETA, CLIMA_FALSO, "Crecimiento", 25
        )


def test_extraer_json_con_markdown():
    assert llm_client._extraer_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extraer_json_con_texto_alrededor():
    assert llm_client._extraer_json('Aqui tienes: {"a": 1} listo') == {"a": 1}


def test_extraer_json_invalido_lanza_error():
    with pytest.raises(llm_client.ErrorLLM):
        llm_client._extraer_json("esto no es json")


def test_solicitud_rechaza_dias_negativos():
    with pytest.raises(Exception):
        SolicitudRecomendacion(id_hortaliza=1, dias_siembra=-5)

def test_nivel_invalido_del_llm_se_degrada(client, headers, culture, monkeypatch):
    """El LLM puede devolver niveles inventados: no deben romper la respuesta."""
    from app.modules.ai_advisor import services

    respuesta_loco = {
        "recomendacion_riego": "Riego normal.",
        "recomendacion_general": "Manejo normal.",
        "alertas": [
            {"tipo": "x", "descripcion": "y", "nivel": "CATASTROFICA"},
            {"nivel": "precaucion"},
            "no-es-un-objeto",
        ],
        "nivel_urgencia_max": "DESASTROSO",
    }

    monkeypatch.setattr(
        services.weather_client, "obtener_clima", lambda *a, **k: dict(CLIMA_FALSO)
    )
    monkeypatch.setattr(
        services.llm_client, "generar_recomendacion", lambda *a, **k: dict(respuesta_loco)
    )

    r = client.post(
        "/api/v1/ai/recomendacion",
        json={"id_hortaliza": culture["id"], "dias_siembra": 25},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["nivel_urgencia_max"] == "informativa"
    assert cuerpo["alertas"][0]["nivel"] == "informativa"
    assert cuerpo["alertas"][1]["nivel"] == "precaucion"

