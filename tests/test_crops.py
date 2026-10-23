"""Pruebas del modulo de cultivos: validaciones, proteccion por JWT y cascada."""

import pytest

CARGA_LECHUGA = {
    "nombre": "Lechuga",
    "nombre_cientifico": "Lactuca sativa",
    "temp_min_c": 4.0,
    "temp_max_c": 24.0,
    "temp_ideal_c": 15.0,
    "humedad_suelo_min_pct": 60.0,
    "humedad_suelo_max_pct": 85.0,
    "requerimiento_agua_semanal_mm": 25.0,
    "radiacion_solar_min_wm2": 200.0,
    "radiacion_solar_max_wm2": 800.0,
    "altitud_min_msnm": 1900.0,
    "altitud_max_msnm": 3000.0,
    "duracion_total_dias": 60,
    "etapas": [
        {
            "nombre_etapa": "Germinacion",
            "dia_inicio": 1,
            "dia_fin": 10,
            "riego_frecuencia_dias": 1,
        },
        {
            "nombre_etapa": "Crecimiento vegetativo",
            "dia_inicio": 11,
            "dia_fin": 40,
            "riego_frecuencia_dias": 2,
        },
    ],
}


@pytest.fixture
def culture(client, headers):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_hortaliza_con_etapas(client, headers):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nombre"] == "Lechuga"
    assert len(cuerpo["etapas"]) == 2
    assert cuerpo["etapas"][0]["hortaliza_id"] == cuerpo["id"]


def test_crear_hortaliza_sin_token(client):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA)
    assert r.status_code == 401


def test_crear_hortaliza_nombre_duplicado(client, headers, culture):
    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 400
    assert "Ya existe" in r.json()["detail"]


def test_validar_temp_ideal_fuera_de_rango(client, headers):
    carga = dict(CARGA_LECHUGA, temp_ideal_c=30.0)
    r = client.post("/api/v1/hortalizas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_validar_humedad_min_mayor_que_max(client, headers):
    carga = dict(CARGA_LECHUGA, humedad_suelo_min_pct=90.0, humedad_suelo_max_pct=50.0)
    r = client.post("/api/v1/hortalizas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_validar_etapa_rango_dias_invertido(client, headers):
    carga = dict(CARGA_LECHUGA)
    carga["etapas"] = [
        {"nombre_etapa": "Invertida", "dia_inicio": 30, "dia_fin": 10}
    ]
    r = client.post("/api/v1/hortalizas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_validar_etapa_mas_larga_que_ciclo(client, headers):
    carga = dict(CARGA_LECHUGA, duracion_total_dias=20)
    carga["etapas"] = [
        {"nombre_etapa": "Muy larga", "dia_inicio": 1, "dia_fin": 45}
    ]
    r = client.post("/api/v1/hortalizas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_listar_hortalizas_es_publico(client, culture):
    r = client.get("/api/v1/hortalizas/")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_obtener_hortaliza_inexistente(client):
    r = client.get("/api/v1/hortalizas/9999")
    assert r.status_code == 404


def test_actualizar_hortaliza(client, headers, culture):
    carga = dict(CARGA_LECHUGA, nombre="Lechuga troca")
    r = client.put(
        f"/api/v1/hortalizas/{culture['id']}", json=carga, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Lechuga troca"


def test_actualizar_hortaliza_sin_token(client, culture):
    carga = dict(CARGA_LECHUGA, nombre="Otra")
    r = client.put(f"/api/v1/hortalizas/{culture['id']}", json=carga)
    assert r.status_code == 401


def test_eliminar_hortaliza(client, headers, culture):
    r = client.delete(f"/api/v1/hortalizas/{culture['id']}", headers=headers)
    assert r.status_code == 204
    assert client.get(f"/api/v1/hortalizas/{culture['id']}").status_code == 404


def test_eliminar_cascada_a_etapas(client, headers, culture, db):
    """Al borrar la culture sus etapas deben desaparecer tambien."""
    from app.modules.crops.models import EtapaHortaliza

    assert db.query(EtapaHortaliza).count() == 2
    client.delete(f"/api/v1/hortalizas/{culture['id']}", headers=headers)
    db.expire_all()
    assert db.query(EtapaHortaliza).count() == 0


def test_obtener_etapa_actual_por_dia(client, headers, culture, db):
    from app.modules.crops.services import obtener_etapa_actual

    assert obtener_etapa_actual(db, culture["id"], 5).nombre_etapa == "Germinacion"
    assert (
        obtener_etapa_actual(db, culture["id"], 25).nombre_etapa
        == "Crecimiento vegetativo"
    )
    assert obtener_etapa_actual(db, culture["id"], 500) is None
