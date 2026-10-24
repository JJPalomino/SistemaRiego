"""Casos de prueba críticos para estresar los límites lógicos de la Fase 3.

Estos tests se enfocan en:
1. Doble commit huérfano tras fallo de Gemini
2. Peticiones sin parcela/siembra (historial nulo)
3. Concurrencia lenta con trabajo bloqueante delegado al threadpool
4. Saneo lógico de alertas y validación con Pydantic
"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.ai_advisor import llm_client, services, weather_client
from app.modules.ai_advisor.models import ConsultaRecomendacion, LecturaClimatica


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clima_falso():
    return {
        "latitud": 19.2236,
        "longitud": -97.8528,
        "fecha_inicio_pronostico": "2026-10-24",
        "fecha_fin_pronostico": "2026-10-30",
        "dias_pronostico": 7,
        "precipitacion_mm": 12.5,
        "evapotranspiracion_ref_mm": 18.4,
        "temp_max_c": 24.0,
        "temp_min_c": 10.0,
        "temperatura_bulbo_seco_c": 17.0,
        "velocidad_viento_kmh": 8.2,
        "probabilidad_precipitacion_pct": 35.0,
        "radiacion_solar_wm2": 234.85,
        "radiacion_solar_mj_m2_dia": 20.28,
        "humedad_relativa_pct": 68.0,
        "punto_rocio_c": 11.2,
        "temperatura_suelo_c": 16.8,
        "humedad_suelo_pct": 6.0,
        "cobertura_nubes_pct": 42.0,
        "fuente": "open_meteo",
    }


def _recomendacion_valida():
    return {
        "recomendacion_riego": "Aplicar riego ligero por la mañana.",
        "recomendacion_general": "Vigilar aparición de hongos por alta humedad.",
        "alertas": [
            {"tipo": "humedad", "descripcion": "Humedad alta", "nivel": "informativa"}
        ],
        "nivel_urgencia_max": "informativa",
    }


# ---------------------------------------------------------------------------
# 1) Doble commit huérfano tras fallo de Gemini
# ---------------------------------------------------------------------------

def test_doble_commit_huerfano_tras_fallo_gemini(client, db, headers, parcela, hortaliza, monkeypatch):
    """Con transacción unificada (Unit of Work) y rollback total, si Gemini
    falla tras preparar todo, NO debe quedar ninguna lectura climática huérfana
    ni consulta registrada."""
    clima = _clima_falso()

    def _clima_ok(*args, **kwargs):
        return {**clima, "json_raw": {"dummy": True}}

    def _gemini_falla(*args, **kwargs):
        raise llm_client.ErrorLLM("Gemini fallo")

    monkeypatch.setattr(weather_client, "obtener_clima", _clima_ok)
    monkeypatch.setattr(llm_client, "generar_recomendacion", _gemini_falla)

    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"parcela_id": parcela["id"], "id_hortaliza": hortaliza["id"], "dias_siembra": 15},
    )
    # El router devuelve 502 genérico
    assert r.status_code == 502

    lecturas = db.query(LecturaClimatica).all()
    consultas = db.query(ConsultaRecomendacion).all()

    # Rollback total: sin registros huérfanos
    assert len(lecturas) == 0
    assert len(consultas) == 0


# ---------------------------------------------------------------------------
# 2) Petición sin parcela/siembra -> id_consulta null y PDF 404
# ---------------------------------------------------------------------------

def test_sin_parcela_siembra_id_consulta_null_y_pdf_404(client, db, headers, hortaliza, monkeypatch):
    """Sin parcela_id/siembra_id solo se usa id_hortaliza + dias_siembra.
    No se guarda en BD y id_consulta debe ser null. El PDF no debe generarse."""
    clima = _clima_falso()

    def _clima_ok(*args, **kwargs):
        return {**clima}

    def _gemini_ok(*args, **kwargs):
        return _recomendacion_valida()

    monkeypatch.setattr(weather_client, "obtener_clima", _clima_ok)
    monkeypatch.setattr(llm_client, "generar_recomendacion", _gemini_ok)
    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", False)

    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"id_hortaliza": hortaliza["id"], "dias_siembra": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id_consulta"] is None

    assert db.query(LecturaClimatica).count() == 0
    assert db.query(ConsultaRecomendacion).count() == 0

    # Intentar descargar PDF sin historial -> 404
    r_pdf = client.get("/api/v1/reportes/siembras/9999.pdf", headers=headers)
    assert r_pdf.status_code == 404


# ---------------------------------------------------------------------------
# 3) Concurrencia lenta con threadpool (rutas def)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrencia_lenta_delegada_threadpool_no_bloquea_health(client, monkeypatch):
    """Simula Open-Meteo lento (5s) con 3 peticiones concurrentes.
    Las rutas son def, por lo que FastAPI delega al threadpool y /health debe responder rápido."""
    clima = _clima_falso()

    def _clima_lento(*args, **kwargs):
        time.sleep(5)
        return {**clima}

    def _gemini_ok(*args, **kwargs):
        return _recomendacion_valida()

    monkeypatch.setattr(weather_client, "obtener_clima", _clima_lento)
    monkeypatch.setattr(llm_client, "generar_recomendacion", _gemini_ok)
    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", False)

    transport = ASGITransport(app=client.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Disparar 3 peticiones lentas concurrentes
        tareas = [
            ac.post("/api/v1/ai/recomendacion", json={"id_hortaliza": 1, "dias_siembra": 10}),
            ac.post("/api/v1/ai/recomendacion", json={"id_hortaliza": 1, "dias_siembra": 15}),
            ac.post("/api/v1/ai/recomendacion", json={"id_hortaliza": 1, "dias_siembra": 20}),
        ]
        inicio = time.perf_counter()
        lanzadas = [asyncio.create_task(t) for t in tareas]
        await asyncio.sleep(0.2)
        r_health = await ac.get("/health")
        elapsed_health = time.perf_counter() - inicio
        assert r_health.status_code == 200
        assert elapsed_health < 2.0
        await asyncio.gather(*lanzadas)


# ---------------------------------------------------------------------------
# 4) Saneo lógico de alertas y validación Pydantic
# ---------------------------------------------------------------------------

def test_saneo_alertas_normaliza_y_guarda_limpio(client, db, headers, parcela, hortaliza, monkeypatch):
    """Gemini devuelve alertas con nivel en mayúsculas, nulos y valores inválidos.
    _sanear_alertas debe normalizar a informativa/precaucion/critica y guardar limpio."""
    clima = _clima_falso()

    def _clima_ok(*args, **kwargs):
        return {**clima, "json_raw": {"dummy": True}}

    def _gemini_sucio(*args, **kwargs):
        return {
            "recomendacion_riego": "Regar con moderación",
            "recomendacion_general": "Revisar follaje",
            "alertas": [
                {"tipo": "helada", "descripcion": "Posible helada", "nivel": "ALTA"},  # inválido
                {"tipo": "lluvia", "descripcion": "Lluvia ligera", "nivel": "Precaucion"},  # mixto
                {"tipo": "viento", "descripcion": "Viento", "nivel": None},  # null
                "basura",  # elemento inválido
            ],
            "nivel_urgencia_max": "CRITICA",
        }

    monkeypatch.setattr(weather_client, "obtener_clima", _clima_ok)
    monkeypatch.setattr(llm_client, "generar_recomendacion", _gemini_sucio)
    monkeypatch.setattr(llm_client.settings, "DEMO_MODE", False)

    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"parcela_id": parcela["id"], "id_hortaliza": hortaliza["id"], "dias_siembra": 25},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Normalizado al enum esperado
    assert data["nivel_urgencia_max"] == "critica"
    for a in data["alertas"]:
        assert a["nivel"] in {"informativa", "precaucion", "critica"}

    # Guardado limpio en BD
    consulta = db.query(ConsultaRecomendacion).first()
    assert consulta is not None
    resp = consulta.respuesta_json
    assert resp["nivel_urgencia_max"] == "critica"
    for a in resp["alertas"]:
        assert a["nivel"] in {"informativa", "precaucion", "critica"}
