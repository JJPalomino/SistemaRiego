from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.crops.models import EtapaHortaliza, Hortaliza
from app.modules.crops.schemas import HortalizaCreate, HortalizaUpdate


class HortalizaNoEncontrada(Exception):
    """La culture solicitada no existe."""


class HortalizaDuplicada(Exception):
    """Ya existe una hortaliza con el mismo nombre."""


class HortalizaEnUso(Exception):
    """No se puede eliminar: tiene siembras registradas en parcelas."""


def listar_hortalizas(db: Session) -> List[Hortaliza]:
    return db.query(Hortaliza).order_by(Hortaliza.nombre).all()


def obtener_hortaliza(db: Session, id_hortaliza: int) -> Hortaliza:
    result = db.query(Hortaliza).filter(Hortaliza.id == id_hortaliza).first()
    if result is None:
        raise HortalizaNoEncontrada(f"No existe la culture con id {id_hortaliza}")
    return result


def _reemplazar_etapas(db: Session, item: Hortaliza, etapas: list) -> None:
    """Sustituye el conjunto de etapas de una culture.

    Se borran y recrean porque el PUT es de reemplazo completo; la relacion
    tiene `cascade="all, delete-orphan"` asi que SQLAlchemy marca las etapas
    viejas para borrado automaticamente.
    """
    for etapa in list(item.etapas):
        db.delete(etapa)
    db.flush()

    for datos in etapas:
        db.add(EtapaHortaliza(hortaliza_id=item.id, **datos.model_dump()))


def crear_hortaliza(db: Session, datos: HortalizaCreate) -> Hortaliza:
    existente = (
        db.query(Hortaliza).filter(Hortaliza.nombre == datos.nombre).first()
    )
    if existente:
        raise HortalizaDuplicada(
            f"Ya existe una culture con el nombre '{datos.nombre}'"
        )

    item = Hortaliza(**datos.model_dump(exclude={"etapas"}))
    db.add(item)
    db.flush()

    _reemplazar_etapas(db, item, datos.etapas)

    db.commit()
    db.refresh(item)
    return item


def actualizar_hortaliza(
    db: Session, id_hortaliza: int, datos: HortalizaUpdate
) -> Hortaliza:
    item = obtener_hortaliza(db, id_hortaliza)

    duplicada = (
        db.query(Hortaliza)
        .filter(Hortaliza.nombre == datos.nombre, Hortaliza.id != id_hortaliza)
        .first()
    )
    if duplicada:
        raise HortalizaDuplicada(
            f"Ya existe otra culture con el nombre '{datos.nombre}'"
        )

    for campo, valor in datos.model_dump(exclude={"etapas"}).items():
        setattr(item, campo, valor)

    _reemplazar_etapas(db, item, datos.etapas)

    db.commit()
    db.refresh(item)
    return item


def eliminar_hortaliza(db: Session, id_hortaliza: int) -> None:
    item = obtener_hortaliza(db, id_hortaliza)

    # La FK de `siembras.hortaliza_id` es RESTRICT: borrar un cultivo con
    # historico dejaria siembras huerfanas. Se comprueba antes de intentarlo
    # para responder 409 en lugar de un error de integridad 500.
    from app.modules.parcels.models import Siembra

    siembras = (
        db.query(Siembra).filter(Siembra.hortaliza_id == item.id).count()
    )
    if siembras:
        raise HortalizaEnUso(
            f"No se puede eliminar '{item.nombre}': tiene {siembras} siembra(s) "
            "registrada(s)"
        )

    # Las etapas se van por `cascade="all, delete-orphan"` en la relacion y
    # en cascada a nivel de base de datos (ON DELETE CASCADE, ver migracion).
    db.delete(item)
    db.commit()


def obtener_etapa_actual(
    db: Session, id_hortaliza: int, dias_siembra: int
) -> Optional[EtapaHortaliza]:
    """Devuelve la etapa fenologica que corresponde al dia de siembra dado."""
    etapas = (
        db.query(EtapaHortaliza)
        .filter(
            EtapaHortaliza.hortaliza_id == id_hortaliza,
            EtapaHortaliza.dia_inicio <= dias_siembra,
            EtapaHortaliza.dia_fin >= dias_siembra,
        )
        .order_by(EtapaHortaliza.dia_inicio)
        .first()
    )
    return etapas
