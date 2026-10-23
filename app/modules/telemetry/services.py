from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.modules.parcels import services as parcels_services
from app.modules.parcels.models import Parcela
from app.modules.telemetry.models import (
    UNIDAD_POR_TIPO,
    Lectura,
    Sensor,
    TipoSensor,
)
from app.modules.telemetry.schemas import (
    LoteLecturasCreate,
    ResultadoIngesta,
    SensorCreate,
)


class SensorNoEncontrado(Exception):
    """El sensor no existe o pertenece a una parcela de otro usuario."""


class SensorDuplicado(Exception):
    """Ya hay un sensor registrado con ese codigo."""


class LecturaInvalida(Exception):
    """El valor cae fuera del rango fisico esperado para ese tipo de sensor."""


# Rangos plausibles por tipo de sensor. No sustituyen la calibracion, pero
# frenan valores corruptos antes de que entren al historico de entrenamiento.
RANGOS_VALIDOS: dict[TipoSensor, tuple[float, float]] = {
    TipoSensor.humedad_suelo: (0.0, 100.0),
    TipoSensor.humedad_aire: (0.0, 100.0),
    TipoSensor.temperatura_aire: (-20.0, 60.0),
    TipoSensor.temperatura_suelo: (-5.0, 60.0),
    TipoSensor.lluvia: (0.0, 500.0),
    TipoSensor.radiacion: (0.0, 1500.0),
    TipoSensor.viento: (0.0, 250.0),
}


# ---------------------------------------------------------------------------
# Sensores
# ---------------------------------------------------------------------------

def obtener_sensor(db: Session, usuario_id: int, sensor_id: int) -> Sensor:
    sensor = (
        db.query(Sensor)
        .join(Parcela, Sensor.parcela_id == Parcela.id)
        .options(joinedload(Sensor.parcela))
        .filter(Sensor.id == sensor_id, Parcela.usuario_id == usuario_id)
        .first()
    )
    if sensor is None:
        raise SensorNoEncontrado(f"No existe el sensor {sensor_id}")
    return sensor


def crear_sensor(db: Session, usuario_id: int, datos: SensorCreate) -> Sensor:
    # Valida la pertenencia de la parcela antes de crear nada.
    parcels_services.obtener_parcela(db, usuario_id, datos.parcela_id)

    if db.query(Sensor).filter(Sensor.codigo == datos.codigo).first() is not None:
        raise SensorDuplicado(f"Ya existe un sensor con el codigo '{datos.codigo}'")

    sensor = Sensor(
        **datos.model_dump(),
        # La unidad se deriva del tipo para que no haya lecturas etiquetadas
        # como porcentaje cuando en realidad vienen en fraccion.
        unidad=UNIDAD_POR_TIPO[datos.tipo],
    )
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return sensor


def listar_sensores(
    db: Session, usuario_id: int, parcela_id: int
) -> List[Sensor]:
    parcela = parcels_services.obtener_parcela(db, usuario_id, parcela_id)
    return (
        db.query(Sensor)
        .filter(Sensor.parcela_id == parcela.id)
        .order_by(Sensor.tipo, Sensor.profundidad_cm)
        .all()
    )


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------

def _validar_rango(tipo: TipoSensor, valor: float) -> None:
    minimo, maximo = RANGOS_VALIDOS[tipo]
    if not (minimo <= valor <= maximo):
        raise LecturaInvalida(
            f"Valor {valor} fuera del rango plausible para '{tipo.value}' "
            f"({minimo}..{maximo})"
        )


def _insert_con_ignorar_duplicados(db: Session):
    """Devuelve el constructor `insert` del dialecto activo.

    `on_conflict_do_nothing` existe tanto en PostgreSQL como en SQLite, que es
    el motor que usan las pruebas.
    """
    nombre = db.get_bind().dialect.name
    if nombre == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif nombre == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise NotImplementedError(
            f"Ingesta de lecturas no soportada para el dialecto '{nombre}'"
        )
    return insert


def ingresar_lecturas(
    db: Session, usuario_id: int, lote: LoteLecturasCreate
) -> ResultadoIngesta:
    """Guarda un lote de lecturas de forma idempotente.

    Un dispositivo que reintenta el envio no debe duplicar el historico, asi
    que las filas cuyo (sensor_id, timestamp) ya existe se ignoran.
    """
    recibidas = len(lote.lecturas)

    # 1) Verificar que todos los sensores existen y son del usuario.
    ids_sensores = {lectura.sensor_id for lectura in lote.lecturas}
    sensores = {
        sensor.id: sensor
        for sensor in db.query(Sensor)
        .join(Parcela, Sensor.parcela_id == Parcela.id)
        .filter(Sensor.id.in_(ids_sensores), Parcela.usuario_id == usuario_id)
        .all()
    }
    faltantes = ids_sensores - sensores.keys()
    if faltantes:
        raise SensorNoEncontrado(
            f"Sensores inexistentes o ajenos: {sorted(faltantes)}"
        )

    # 2) Validar rangos fisicos.
    for lectura in lote.lecturas:
        _validar_rango(sensores[lectura.sensor_id].tipo, lectura.valor)

    # 3) Descartar repetidos dentro del mismo lote (el ultimo valor gana).
    unicas: dict[tuple[int, datetime], dict] = {}
    for lectura in lote.lecturas:
        unicas[(lectura.sensor_id, lectura.timestamp)] = {
            "sensor_id": lectura.sensor_id,
            "timestamp": lectura.timestamp,
            "valor": lectura.valor,
        }
    filas = list(unicas.values())

    # 4) Insertar ignorando lo que ya existia.
    insert = _insert_con_ignorar_duplicados(db)
    sentencia = (
        insert(Lectura)
        .values(filas)
        .on_conflict_do_nothing(index_elements=["sensor_id", "timestamp"])
    )
    resultado = db.execute(sentencia)
    db.commit()

    insertadas = max(resultado.rowcount or 0, 0)

    return ResultadoIngesta(
        recibidas=recibidas,
        unicas=len(filas),
        insertadas=insertadas,
        duplicadas=recibidas - insertadas,
    )


def consultar_lecturas(
    db: Session,
    usuario_id: int,
    sensor_id: int,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limite: int = 1000,
) -> List[Lectura]:
    sensor = obtener_sensor(db, usuario_id, sensor_id)

    consulta = db.query(Lectura).filter(Lectura.sensor_id == sensor.id)
    if desde is not None:
        consulta = consulta.filter(Lectura.timestamp >= desde)
    if hasta is not None:
        consulta = consulta.filter(Lectura.timestamp <= hasta)

    return consulta.order_by(Lectura.timestamp).limit(limite).all()


def ultimas_lecturas_por_sensor(
    db: Session, usuario_id: int, parcela_id: int
) -> List[dict]:
    """Ultima lectura de cada sensor de la parcela.

    Sirve para pintar el estado actual en el panel sin descargar el historico.
    """
    parcela = parcels_services.obtener_parcela(db, usuario_id, parcela_id)
    sensores = (
        db.query(Sensor).filter(Sensor.parcela_id == parcela.id).all()
    )

    resumen: List[dict] = []
    for sensor in sensores:
        ultima = (
            db.query(Lectura)
            .filter(Lectura.sensor_id == sensor.id)
            .order_by(Lectura.timestamp.desc())
            .first()
        )
        resumen.append(
            {
                "sensor_id": sensor.id,
                "codigo": sensor.codigo,
                "tipo": sensor.tipo,
                "unidad": sensor.unidad,
                "profundidad_cm": sensor.profundidad_cm,
                "timestamp": ultima.timestamp if ultima else None,
                "valor": ultima.valor if ultima else None,
            }
        )
    return resumen
