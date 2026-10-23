"""Historial climatico, historial de recomendaciones y reporte PDF."""

from datetime import date, timedelta

import pytest

from tests.test_ai_advisor import CLIMA_FALSO, RESPUESTA_LLM
from tests.test_crops import CARGA_LECHUGA


@pytest.fixture
def culture(client, headers):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def sin_servicios_externos(monkeypatch):
    """Open-Meteo y Gemini controlados, igual que en test_ai_advisor."""
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


def _crear_siembra(client, headers, parcela, hortaliza, dias_atras=20):
    inicio = (date.today() - timedelta(days=dias_atras)).isoformat()
    r = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": inicio},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _pedir_recomendacion(client, headers, siembra_id):
    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"siembra_id": siembra_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Persistencia del historial
# ---------------------------------------------------------------------------

def test_recomendacion_con_siembra_guarda_clima_y_consulta(
    client, headers, parcela, culture, sin_servicios_externos
):
    siembra = _crear_siembra(client, headers, parcela, culture)
    cuerpo = _pedir_recomendacion(client, headers, siembra["id"])

    assert cuerpo["id_consulta"] is not None
    assert cuerpo["nombre_hortaliza"] == "Lechuga"
    assert cuerpo["dias_siembra"] == 20

    historial = client.get(
        "/api/v1/ai/historial",
        headers=headers,
        params={"siembra_id": siembra["id"]},
    )
    assert historial.status_code == 200, historial.text
    items = historial.json()
    assert len(items) == 1
    assert items[0]["id"] == cuerpo["id_consulta"]
    assert items[0]["siembra_id"] == siembra["id"]
    assert items[0]["recomendacion_riego"] == RESPUESTA_LLM["recomendacion_riego"]

    detalle = client.get(
        f"/api/v1/ai/historial/{cuerpo['id_consulta']}", headers=headers
    )
    assert detalle.status_code == 200, detalle.text
    datos = detalle.json()
    assert datos["nombre_hortaliza"] == "Lechuga"
    assert "Lechuga" in datos["prompt"]
    assert datos["respuesta_json"]["nivel_urgencia_max"] == "precaucion"

    clima = client.get(
        "/api/v1/ai/clima",
        headers=headers,
        params={"parcela_id": parcela["id"]},
    )
    assert clima.status_code == 200, clima.text
    lecturas = clima.json()
    assert len(lecturas) == 1
    assert lecturas[0]["parcela_id"] == parcela["id"]
    assert "datos_json" not in lecturas[0]

    detalle_clima = client.get(
        f"/api/v1/ai/clima/{lecturas[0]['id']}", headers=headers
    )
    assert detalle_clima.status_code == 200, detalle_clima.text
    assert isinstance(detalle_clima.json()["datos_json"], dict)


def test_recomendacion_manual_no_genera_historial(
    client, headers, culture, sin_servicios_externos
):
    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"id_hortaliza": culture["id"], "dias_siembra": 12},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id_consulta"] is None


def test_historial_aislado_entre_usuarios(
    client, headers, headers_otro, parcela, culture, sin_servicios_externos
):
    siembra = _crear_siembra(client, headers, parcela, culture)
    cuerpo = _pedir_recomendacion(client, headers, siembra["id"])

    assert (
        client.get(
            "/api/v1/ai/historial",
            headers=headers_otro,
            params={"siembra_id": siembra["id"]},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/ai/historial/{cuerpo['id_consulta']}",
            headers=headers_otro,
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/ai/clima",
            headers=headers_otro,
            params={"parcela_id": parcela["id"]},
        ).status_code
        == 404
    )


def test_siembra_inexistente_devuelve_404(client, headers, sin_servicios_externos):
    r = client.post(
        "/api/v1/ai/recomendacion",
        headers=headers,
        json={"siembra_id": 9999},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Reporte PDF
# ---------------------------------------------------------------------------

def test_pdf_de_la_ultima_recomendacion(
    client, headers, db, parcela, culture, sin_servicios_externos
):
    from app.modules.ai_advisor.models import ReporteGenerado

    siembra = _crear_siembra(client, headers, parcela, culture)
    _pedir_recomendacion(client, headers, siembra["id"])

    r = client.get(
        f"/api/v1/reportes/siembras/{siembra['id']}.pdf", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 1000

    assert db.query(ReporteGenerado).count() == 1
    reporte = db.query(ReporteGenerado).one()
    assert reporte.siembra_id == siembra["id"]
    assert reporte.consulta_id is not None


def test_pdf_sin_recomendaciones(client, headers, parcela, culture):
    siembra = _crear_siembra(client, headers, parcela, culture)
    r = client.get(
        f"/api/v1/reportes/siembras/{siembra['id']}.pdf", headers=headers
    )
    assert r.status_code == 404


def test_pdf_aislado_entre_usuarios(
    client, headers, headers_otro, parcela, culture, sin_servicios_externos
):
    siembra = _crear_siembra(client, headers, parcela, culture)
    _pedir_recomendacion(client, headers, siembra["id"])

    r = client.get(
        f"/api/v1/reportes/siembras/{siembra['id']}.pdf", headers=headers_otro
    )
    assert r.status_code == 404
