"""Pruebas de parcelas y siembras: propiedad, validaciones y cascadas."""

from datetime import date, timedelta

CARGA_PARCELA = {
    "nombre": "Parcela Sur",
    "latitud": 19.22,
    "longitud": -97.85,
    "altitud_msnm": 2000,
    "area_m2": 300,
    "textura_suelo": "franco_arcilloso",
}


def _fecha(dias_atras: int) -> str:
    return (date.today() - timedelta(days=dias_atras)).isoformat()


# ---------------------------------------------------------------------------
# Parcelas
# ---------------------------------------------------------------------------

def test_crear_parcela_requiere_token(client):
    r = client.post("/api/v1/parcelas/", json=CARGA_PARCELA)
    assert r.status_code == 401


def test_crear_parcela(client, headers):
    r = client.post("/api/v1/parcelas/", json=CARGA_PARCELA, headers=headers)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nombre"] == "Parcela Sur"
    assert cuerpo["textura_suelo"] == "franco_arcilloso"
    assert cuerpo["activa"] is True
    assert cuerpo["usuario_id"] > 0


def test_crear_parcela_latitud_invalida(client, headers):
    carga = dict(CARGA_PARCELA, latitud=120)
    r = client.post("/api/v1/parcelas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_crear_parcela_area_negativa(client, headers):
    carga = dict(CARGA_PARCELA, area_m2=-5)
    r = client.post("/api/v1/parcelas/", json=carga, headers=headers)
    assert r.status_code == 422


def test_altitud_automatica_si_no_se_envia(client, headers, monkeypatch):
    from app.modules.parcels import services

    monkeypatch.setattr(
        services.weather_client,
        "obtener_altitud",
        lambda lat, lon: 1947.5,
    )
    carga = {k: v for k, v in CARGA_PARCELA.items() if k != "altitud_msnm"}
    r = client.post("/api/v1/parcelas/", json=carga, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["altitud_msnm"] == 1947.5


def test_altitud_no_bloquea_el_alta_si_open_meteo_falla(
    client, headers, monkeypatch
):
    from app.modules.ai_advisor.weather_client import ErrorClima
    from app.modules.parcels import services

    def _falla(lat, lon):
        raise ErrorClima("sin conexion")

    monkeypatch.setattr(services.weather_client, "obtener_altitud", _falla)
    carga = {k: v for k, v in CARGA_PARCELA.items() if k != "altitud_msnm"}
    r = client.post("/api/v1/parcelas/", json=carga, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["altitud_msnm"] is None


def test_listar_solo_parcelas_propias(client, headers, headers_otro, parcela):
    propias = client.get("/api/v1/parcelas/", headers=headers)
    assert propias.status_code == 200
    assert [p["id"] for p in propias.json()] == [parcela["id"]]

    ajenas = client.get("/api/v1/parcelas/", headers=headers_otro)
    assert ajenas.status_code == 200
    assert ajenas.json() == []


def test_no_puede_leer_parcela_ajena(client, headers_otro, parcela):
    r = client.get(f"/api/v1/parcelas/{parcela['id']}", headers=headers_otro)
    assert r.status_code == 404


def test_no_puede_borrar_parcela_ajena(client, headers_otro, parcela):
    r = client.delete(f"/api/v1/parcelas/{parcela['id']}", headers=headers_otro)
    assert r.status_code == 404


def test_actualizar_parcela(client, headers, parcela):
    carga = dict(CARGA_PARCELA, nombre="Parcela Renombrada")
    r = client.put(
        f"/api/v1/parcelas/{parcela['id']}", json=carga, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Parcela Renombrada"


def test_eliminar_parcela(client, headers, parcela):
    assert (
        client.delete(
            f"/api/v1/parcelas/{parcela['id']}", headers=headers
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/parcelas/{parcela['id']}", headers=headers
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Siembras
# ---------------------------------------------------------------------------

def test_crear_siembra(client, headers, parcela, hortaliza):
    r = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": _fecha(30)},
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nombre_hortaliza"] == "Lechuga"
    assert cuerpo["dias_desde_siembra"] == 30
    assert cuerpo["activa"] is True


def test_siembra_en_futuro_rechazada(client, headers, parcela, hortaliza):
    manana = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": manana},
    )
    assert r.status_code == 422


def test_siembra_cosecha_anterior_a_siembra(client, headers, parcela, hortaliza):
    r = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={
            "hortaliza_id": hortaliza["id"],
            "fecha_siembra": _fecha(10),
            "fecha_cosecha": _fecha(20),
        },
    )
    assert r.status_code == 422


def test_siembra_hortaliza_inexistente(client, headers, parcela):
    r = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": 9999, "fecha_siembra": _fecha(10)},
    )
    assert r.status_code == 400


def test_siembras_solapadas_rechazadas(client, headers, parcela, hortaliza):
    primera = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={
            "hortaliza_id": hortaliza["id"],
            "fecha_siembra": _fecha(100),
            "fecha_cosecha": _fecha(60),
        },
    )
    assert primera.status_code == 201, primera.text

    solapada = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={
            "hortaliza_id": hortaliza["id"],
            "fecha_siembra": _fecha(80),
            "fecha_cosecha": _fecha(20),
        },
    )
    assert solapada.status_code == 409

    contigua = client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={
            "hortaliza_id": hortaliza["id"],
            "fecha_siembra": _fecha(60),
            "fecha_cosecha": _fecha(10),
        },
    )
    assert contigua.status_code == 201, contigua.text


def test_siembra_vigente(client, headers, parcela, hortaliza):
    client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": _fecha(25)},
    )
    r = client.get(
        f"/api/v1/parcelas/{parcela['id']}/siembra-vigente", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["dias_desde_siembra"] == 25


def test_siembra_vigente_sin_ciclos(client, headers, parcela):
    r = client.get(
        f"/api/v1/parcelas/{parcela['id']}/siembra-vigente", headers=headers
    )
    assert r.status_code == 200
    assert r.json() is None


def test_eliminar_parcela_arrastra_siembras(client, headers, parcela, hortaliza, db):
    from app.modules.parcels.models import Siembra

    client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": _fecha(20)},
    )
    assert db.query(Siembra).count() == 1

    assert (
        client.delete(
            f"/api/v1/parcelas/{parcela['id']}", headers=headers
        ).status_code
        == 204
    )
    db.expire_all()
    assert db.query(Siembra).count() == 0


def test_no_elimina_hortaliza_con_siembras(
    client, headers, parcela, hortaliza
):
    client.post(
        f"/api/v1/parcelas/{parcela['id']}/siembras",
        headers=headers,
        json={"hortaliza_id": hortaliza["id"], "fecha_siembra": _fecha(20)},
    )
    r = client.delete(f"/api/v1/hortalizas/{hortaliza['id']}", headers=headers)
    assert r.status_code == 409
    assert "siembra" in r.json()["detail"]
