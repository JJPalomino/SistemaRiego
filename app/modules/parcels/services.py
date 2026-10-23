from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.modules.ai_advisor import weather_client
from app.modules.crops.models import Hortaliza
from app.modules.parcels.models import Parcela, Siembra
from app.modules.parcels.schemas import (
    ParcelaCreate,
    ParcelaUpdate,
    SiembraCreate,
    SiembraUpdate,
)


class ParcelaNoEncontrada(Exception):
    """La parcela no existe o no pertenece al usuario."""


class SiembraNoEncontrada(Exception):
    """La siembra no existe o no pertenece al usuario."""


class HortalizaInvalida(Exception):
    """El cultivo indicado no existe en el catalogo."""


class SiembraTraslapada(Exception):
    """Ya hay un ciclo de cultivo que se solapa con el solicitado."""


# ---------------------------------------------------------------------------
# Parcelas
# ---------------------------------------------------------------------------

def listar_parcelas(db: Session, usuario_id: int) -> List[Parcela]:
    return (
        db.query(Parcela)
        .filter(Parcela.usuario_id == usuario_id)
        .order_by(Parcela.nombre)
        .all()
    )


def obtener_parcela(db: Session, usuario_id: int, parcela_id: int) -> Parcela:
    """Busca una parcela del usuario.

    Se filtra por `usuario_id` para que una parcela ajena responda 404 y no
    403: no conviene revelar que el id existe.
    """
    parcela = (
        db.query(Parcela)
        .filter(Parcela.id == parcela_id, Parcela.usuario_id == usuario_id)
        .first()
    )
    if parcela is None:
        raise ParcelaNoEncontrada(f"No existe la parcela {parcela_id}")
    return parcela


def crear_parcela(db: Session, usuario_id: int, datos: ParcelaCreate) -> Parcela:
    """Crea la parcela y completa la altitud si el cliente no la envio.

    Open-Meteo expone la elevacion del punto exacto. Se consulta en el alta
    porque el balance hidrico y la ET0 dependen de la altitud. Si el servicio
    falla, la parcela se crea igual con `altitud_msnm = None`: no se bloquea el
    registro por una dependencia externa.
    """
    valores = datos.model_dump()
    if valores.get("altitud_msnm") is None:
        try:
            valores["altitud_msnm"] = weather_client.obtener_altitud(
                valores["latitud"], valores["longitud"]
            )
        except weather_client.ErrorClima:
            pass

    parcela = Parcela(usuario_id=usuario_id, **valores)
    db.add(parcela)
    db.commit()
    db.refresh(parcela)
    return parcela


def actualizar_parcela(
    db: Session, usuario_id: int, parcela_id: int, datos: ParcelaUpdate
) -> Parcela:
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    for campo, valor in datos.model_dump().items():
        setattr(parcela, campo, valor)
    db.commit()
    db.refresh(parcela)
    return parcela


def eliminar_parcela(db: Session, usuario_id: int, parcela_id: int) -> None:
    """Elimina la parcela. Siembras y sensores se van en cascada."""
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    db.delete(parcela)
    db.commit()


# ---------------------------------------------------------------------------
# Siembras
# ---------------------------------------------------------------------------

def _validar_hortaliza(db: Session, hortaliza_id: int) -> Hortaliza:
    hortaliza = db.query(Hortaliza).filter(Hortaliza.id == hortaliza_id).first()
    if hortaliza is None:
        raise HortalizaInvalida(f"No existe la hortaliza {hortaliza_id}")
    return hortaliza


def _validar_traslape(
    db: Session,
    parcela_id: int,
    fecha_siembra: date,
    fecha_cosecha: Optional[date],
    excluir_siembra_id: Optional[int] = None,
) -> None:
    """Impide dos ciclos solapados en la misma parcela.

    Un ciclo sin cosecha se considera abierto hasta el infinito, de modo que
    no se puede sembrar encima de un ciclo vigente. La comparacion es estricta:
    cosechar y sembrar el mismo dia es valido (el nuevo ciclo empieza donde
    termina el anterior).
    """
    consulta = db.query(Siembra).filter(Siembra.parcela_id == parcela_id)
    if excluir_siembra_id is not None:
        consulta = consulta.filter(Siembra.id != excluir_siembra_id)

    inicio_nuevo = fecha_siembra
    fin_nuevo = fecha_cosecha or date.max

    for otra in consulta.all():
        inicio_otro = otra.fecha_siembra
        fin_otro = otra.fecha_cosecha or date.max
        if inicio_nuevo < fin_otro and fin_nuevo > inicio_otro:
            raise SiembraTraslapada(
                f"El ciclo {inicio_nuevo}..{fin_nuevo} se solapa con la siembra "
                f"{otra.id} ({inicio_otro}..{fin_otro}) de la misma parcela"
            )


def listar_siembras(
    db: Session, usuario_id: int, parcela_id: int
) -> List[Siembra]:
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    return (
        db.query(Siembra)
        .options(joinedload(Siembra.hortaliza))
        .filter(Siembra.parcela_id == parcela.id)
        .order_by(Siembra.fecha_siembra.desc())
        .all()
    )


def crear_siembra(
    db: Session, usuario_id: int, parcela_id: int, datos: SiembraCreate
) -> Siembra:
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    _validar_hortaliza(db, datos.hortaliza_id)
    _validar_traslape(
        db, parcela.id, datos.fecha_siembra, datos.fecha_cosecha
    )

    siembra = Siembra(parcela_id=parcela.id, **datos.model_dump())
    db.add(siembra)
    db.commit()
    db.refresh(siembra)
    return siembra


def obtener_siembra(
    db: Session, usuario_id: int, parcela_id: int, siembra_id: int
) -> Siembra:
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    siembra = (
        db.query(Siembra)
        .options(joinedload(Siembra.hortaliza))
        .filter(Siembra.id == siembra_id, Siembra.parcela_id == parcela.id)
        .first()
    )
    if siembra is None:
        raise SiembraNoEncontrada(f"No existe la siembra {siembra_id}")
    return siembra


def obtener_siembra_por_id(
    db: Session, usuario_id: int, siembra_id: int
) -> Siembra:
    """Busca una siembra por id sin exigir el id de la parcela.

    Lo usa el asesor para resolver `siembra_id` en la peticion. El filtro por
    `usuario_id` mantiene el aislamiento entre productores.
    """
    siembra = (
        db.query(Siembra)
        .join(Parcela, Siembra.parcela_id == Parcela.id)
        .options(joinedload(Siembra.hortaliza), joinedload(Siembra.parcela))
        .filter(Siembra.id == siembra_id, Parcela.usuario_id == usuario_id)
        .first()
    )
    if siembra is None:
        raise SiembraNoEncontrada(f"No existe la siembra {siembra_id}")
    return siembra


def actualizar_siembra(
    db: Session,
    usuario_id: int,
    parcela_id: int,
    siembra_id: int,
    datos: SiembraUpdate,
) -> Siembra:
    siembra = obtener_siembra(db, usuario_id, parcela_id, siembra_id)
    _validar_hortaliza(db, datos.hortaliza_id)
    _validar_traslape(
        db,
        siembra.parcela_id,
        datos.fecha_siembra,
        datos.fecha_cosecha,
        excluir_siembra_id=siembra.id,
    )

    for campo, valor in datos.model_dump().items():
        setattr(siembra, campo, valor)

    db.commit()
    db.refresh(siembra)
    return siembra


def eliminar_siembra(
    db: Session, usuario_id: int, parcela_id: int, siembra_id: int
) -> None:
    siembra = obtener_siembra(db, usuario_id, parcela_id, siembra_id)
    db.delete(siembra)
    db.commit()


def obtener_siembra_vigente(
    db: Session, usuario_id: int, parcela_id: int
) -> Optional[Siembra]:
    """Ciclo activo hoy: sembrado y aun sin cosechar."""
    parcela = obtener_parcela(db, usuario_id, parcela_id)
    hoy = date.today()
    return (
        db.query(Siembra)
        .options(joinedload(Siembra.hortaliza))
        .filter(
            Siembra.parcela_id == parcela.id,
            Siembra.fecha_siembra <= hoy,
            (Siembra.fecha_cosecha.is_(None)) | (Siembra.fecha_cosecha >= hoy),
        )
        .order_by(Siembra.fecha_siembra.desc())
        .first()
    )
