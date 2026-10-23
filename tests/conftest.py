"""Configuracion compartida de la suite de pruebas.

Las pruebas usan SQLite en memoria para no depender del PostgreSQL de
desarrollo. Los modelos son portables: `Numeric`, `Enum` (como VARCHAR con
CHECK) y `DateTime(timezone=True)` funcionan igual en ambos motores.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Las variables de entorno deben existir antes de importar `app.core.config`.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-no-usar-en-produccion")
os.environ.setdefault("GEMINI_API_KEY", "dummy-para-pruebas")
os.environ.setdefault("DEMO_MODE", "true")

from app.core.config import settings  # noqa: E402
from app.core.dependencies import get_db  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.users.models import Usuario  # noqa: E402

engine_test = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine_test, "connect")
def _activar_foreign_keys(dbapi_connection, _connection_record):
    """SQLite ignora las FK por defecto; se activan para que las pruebas de
    cascada y RESTRICT reflejen el comportamiento de PostgreSQL."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine_test)
    session = SessionTest()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def usuario(db):
    from app.modules.users.services import hashear_password

    u = Usuario(
        nombre="Productor Demo",
        email="demo@tlatlauquitepec.mx",
        password_hash=hashear_password("contrasena123"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def token(client, usuario):
    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "demo@tlatlauquitepec.mx", "password": "contrasena123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def otro_usuario(db):
    """Segundo productor, para verificar el aislamiento entre usuarios."""
    from app.modules.users.services import hashear_password

    u = Usuario(
        nombre="Otro Productor",
        email="otro@tlatlauquitepec.mx",
        password_hash=hashear_password("contrasena123"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def headers_otro(client, otro_usuario):
    r = client.post(
        "/api/v1/usuarios/login",
        json={"email": "otro@tlatlauquitepec.mx", "password": "contrasena123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def hortaliza(client, headers):
    """Cultivo de prueba en el catalogo (la base de pruebas arranca vacia)."""
    from tests.test_crops import CARGA_LECHUGA

    r = client.post("/api/v1/hortalizas/", json=CARGA_LECHUGA, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def parcela(client, headers):
    r = client.post(
        "/api/v1/parcelas/",
        headers=headers,
        json={
            "nombre": "Parcela Norte",
            "latitud": 19.2236,
            "longitud": -97.8528,
            "altitud_msnm": 2100,
            "area_m2": 500,
            "textura_suelo": "franco",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()

