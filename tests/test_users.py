"""Pruebas del modulo de usuarios y del flujo de autenticacion por JWT."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings


def test_registro_exitoso(client):
    r = client.post(
        "/api/v1/usuarios/registro",
        json={
            "nombre": "Jose Ramirez",
            "email": "jose@example.mx",
            "password": "contrasena123",
        },
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["email"] == "jose@example.mx"
    assert cuerpo["activo"] is True
    # La contraseña nunca debe devolverse en la respuesta.
    assert "password" not in cuerpo
    assert "password_hash" not in cuerpo


def test_registro_correo_duplicado(client, usuario):
    r = client.post(
        "/api/v1/usuarios/registro",
        json={
            "nombre": "Otro",
            "email": "demo@tlatlauquitepec.mx",
            "password": "contrasena123",
        },
    )
    assert r.status_code == 400
    assert "ya esta registrado" in r.json()["detail"]


def test_registro_password_corta(client):
    r = client.post(
        "/api/v1/usuarios/registro",
        json={"nombre": "X", "email": "x@example.mx", "password": "corta"},
    )
    assert r.status_code == 422


def test_registro_email_invalido(client):
    r = client.post(
        "/api/v1/usuarios/registro",
        json={"nombre": "X", "email": "no-es-un-email", "password": "contrasena123"},
    )
    assert r.status_code == 422


def test_login_exitoso(client, usuario):
    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "demo@tlatlauquitepec.mx", "password": "contrasena123"},
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["access_token"]
    assert cuerpo["usuario"]["email"] == "demo@tlatlauquitepec.mx"


def test_login_credenciales_incorrectas(client, usuario):
    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "demo@tlatlauquitepec.mx", "password": "mala123"},
    )
    assert r.status_code == 401


def test_login_usuario_inexistente(client):
    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "nadie@example.mx", "password": "contrasena123"},
    )
    assert r.status_code == 401
    # El mensaje no debe revelar si el correo existe.
    assert "Credenciales incorrectas" in r.json()["detail"]


def test_login_usuario_inactivo(client, usuario, db):
    usuario.activo = False
    db.commit()

    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "demo@tlatlauquitepec.mx", "password": "contrasena123"},
    )
    assert r.status_code == 401
    assert "inactivo" in r.json()["detail"]


def test_me_sin_token(client, usuario):
    r = client.get("/api/v1/usuarios/me")
    assert r.status_code == 401


def test_me_con_token_valido(client, headers, usuario):
    r = client.get("/api/v1/usuarios/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "demo@tlatlauquitepec.mx"


def test_me_con_token_invalido(client, usuario):
    r = client.get(
        "/api/v1/usuarios/me", headers={"Authorization": "Bearer no.es.valido"}
    )
    assert r.status_code == 401


def test_me_con_token_firmado_otro_secreto(client, usuario):
    token = jwt.encode(
        {"sub": str(usuario.id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "otro-secreto",
        algorithm="HS256",
    )
    r = client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_con_token_expirado(client, usuario):
    token = jwt.encode(
        {
            "sub": str(usuario.id),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    r = client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_incluye_sub_y_exp(usuario):
    from app.modules.users.services import crear_token

    token = crear_token({"sub": str(usuario.id), "email": usuario.email})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == str(usuario.id)
    assert "exp" in payload
    assert "iat" in payload
