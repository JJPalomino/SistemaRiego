"""Pruebas de sensores y de la ingesta idempotente de lecturas."""

from datetime import datetime, timedelta, timezone


def _crear_sensor(client, headers, parcela, **cambios):
    carga = {
        "parcela_id": parcela["id"],
        "codigo": "HS-10",
        "tipo": "humedad_suelo",
        "profundidad_cm": 10,
    }
    carga.update(cambios)
    return client.post("/api/v1/telemetria/sensores", headers=headers, json=carga)


def _lote(sensor_id: int, horas: int = 3, valor: float = 40.5, base=None) -> dict:
    ahora = base or datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "lecturas": [
            {
                "sensor_id": sensor_id,
                "timestamp": (ahora - timedelta(hours=h)).isoformat(),
                "valor": valor,
            }
            for h in range(horas)
        ]
    }


# ---------------------------------------------------------------------------
# Sensores
# ---------------------------------------------------------------------------

def test_registrar_sensor_humedad(client, headers, parcela):
    r = _crear_sensor(client, headers, parcela)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["tipo"] == "humedad_suelo"
    assert cuerpo["unidad"] == "%"
    assert cuerpo["profundidad_cm"] == 10
    assert cuerpo["activo"] is True


def test_sensor_suelo_sin_profundidad_rechazado(client, headers, parcela):
    r = _crear_sensor(client, headers, parcela, profundidad_cm=None)
    assert r.status_code == 422


def test_sensor_de_aire_con_profundidad_rechazado(client, headers, parcela):
    r = _crear_sensor(
        client,
        headers,
        parcela,
        codigo="TA-01",
        tipo="temperatura_aire",
        profundidad_cm=10,
    )
    assert r.status_code == 422


def test_sensor_de_aire_sin_profundidad_aceptado(client, headers, parcela):
    r = _crear_sensor(
        client,
        headers,
        parcela,
        codigo="TA-01",
        tipo="temperatura_aire",
        profundidad_cm=None,
    )
    assert r.status_code == 201, r.text
    assert r.json()["unidad"] == "C"


def test_codigo_de_sensor_duplicado(client, headers, parcela):
    assert _crear_sensor(client, headers, parcela).status_code == 201
    r = _crear_sensor(client, headers, parcela, profundidad_cm=30)
    assert r.status_code == 409


def test_sensor_en_parcela_ajena(client, headers_otro, parcela):
    r = _crear_sensor(client, headers_otro, parcela)
    assert r.status_code == 404


def test_listar_sensores_de_parcela(client, headers, parcela):
    _crear_sensor(client, headers, parcela)
    _crear_sensor(client, headers, parcela, codigo="HS-30", profundidad_cm=30)

    r = client.get(
        "/api/v1/telemetria/sensores",
        params={"parcela_id": parcela["id"]},
        headers=headers,
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# Ingesta de lecturas
# ---------------------------------------------------------------------------

def test_ingesta_de_lote(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()

    r = client.post(
        "/api/v1/telemetria/lecturas", headers=headers, json=_lote(sensor["id"])
    )
    assert r.status_code == 201, r.text
    assert r.json() == {
        "recibidas": 3,
        "unicas": 3,
        "insertadas": 3,
        "duplicadas": 0,
    }


def test_ingesta_es_idempotente(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    lote = _lote(sensor["id"])

    assert (
        client.post(
            "/api/v1/telemetria/lecturas", headers=headers, json=lote
        ).json()["insertadas"]
        == 3
    )

    repetido = client.post(
        "/api/v1/telemetria/lecturas", headers=headers, json=lote
    )
    assert repetido.status_code == 201
    assert repetido.json() == {
        "recibidas": 3,
        "unicas": 3,
        "insertadas": 0,
        "duplicadas": 3,
    }


def test_ingesta_descarta_repetidos_del_mismo_lote(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    ahora = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lote = {
        "lecturas": [
            {"sensor_id": sensor["id"], "timestamp": ahora, "valor": 40.0},
            {"sensor_id": sensor["id"], "timestamp": ahora, "valor": 41.0},
        ]
    }

    r = client.post("/api/v1/telemetria/lecturas", headers=headers, json=lote)
    assert r.status_code == 201, r.text
    assert r.json()["recibidas"] == 2
    assert r.json()["unicas"] == 1
    assert r.json()["insertadas"] == 1


def test_lectura_fuera_de_rango_rechazada(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()

    otra = _crear_sensor(
        client, headers, parcela, codigo="HS-30", profundidad_cm=30
    ).json()

    lote = _lote(sensor["id"], horas=1, valor=150.0)
    # Mezcla una lectura valida de otro sensor: si se rechaza el lote, ninguna
    # debe guardarse.
    lote["lecturas"].append(
        {
            "sensor_id": otra["id"],
            "timestamp": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "valor": 35.0,
        }
    )

    r = client.post("/api/v1/telemetria/lecturas", headers=headers, json=lote)
    assert r.status_code == 422

    consulta = client.get(
        "/api/v1/telemetria/lecturas",
        params={"sensor_id": otra["id"]},
        headers=headers,
    )
    assert consulta.json() == []


def test_lectura_de_sensor_ajeno(client, headers_otro, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    r = client.post(
        "/api/v1/telemetria/lecturas", headers=headers_otro, json=_lote(sensor["id"])
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Consulta y resumen
# ---------------------------------------------------------------------------

def test_consultar_lecturas_por_rango(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    base = datetime.now(timezone.utc).replace(microsecond=0)
    client.post(
        "/api/v1/telemetria/lecturas",
        headers=headers,
        json=_lote(sensor["id"], horas=5, base=base),
    )

    r = client.get(
        "/api/v1/telemetria/lecturas",
        params={
            "sensor_id": sensor["id"],
            "desde": (base - timedelta(hours=2)).isoformat(),
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert len(r.json()) == 3
    # Orden ascendente por timestamp.
    sellos = [lectura["timestamp"] for lectura in r.json()]
    assert sellos == sorted(sellos)


def test_consultar_lecturas_de_sensor_ajeno(client, headers, headers_otro, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    r = client.get(
        "/api/v1/telemetria/lecturas",
        params={"sensor_id": sensor["id"]},
        headers=headers_otro,
    )
    assert r.status_code == 404


def test_resumen_devuelve_ultima_lectura(client, headers, parcela):
    sensor = _crear_sensor(client, headers, parcela).json()
    client.post(
        "/api/v1/telemetria/lecturas", headers=headers, json=_lote(sensor["id"])
    )

    r = client.get(
        "/api/v1/telemetria/resumen",
        params={"parcela_id": parcela["id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert len(resumen) == 1
    assert resumen[0]["sensor_id"] == sensor["id"]
    assert resumen[0]["valor"] == 40.5
    assert resumen[0]["timestamp"] is not None
