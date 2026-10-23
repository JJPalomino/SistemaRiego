"""Carga el catalogo base de hortalizas en la base de datos.

Uso:
    python -m scripts.seed_catalogo             # aplica los cambios
    python -m scripts.seed_catalogo --dry-run   # solo valida el JSON

Es idempotente: si la hortaliza ya existe (por nombre), se actualizan sus
datos y se reemplazan sus etapas.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.modules.crops.models import EtapaHortaliza, Hortaliza
from app.modules.crops.schemas import HortalizaCreate

RUTA_CATALOGO = (
    Path(__file__).resolve().parent.parent / "data" / "catalogo_hortalizas.json"
)


def cargar_catalogo(ruta: Path = RUTA_CATALOGO) -> list[HortalizaCreate]:
    """Lee el JSON y lo valida con el mismo esquema que usa la API."""
    with ruta.open(encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    return [
        HortalizaCreate.model_validate(item) for item in contenido["hortalizas"]
    ]


def sembrar(db: Session, catalogo: list[HortalizaCreate]) -> tuple[int, int]:
    """Crea o actualiza cada hortaliza. Devuelve (creadas, actualizadas)."""
    creadas = 0
    actualizadas = 0

    for datos in catalogo:
        existente = (
            db.query(Hortaliza).filter(Hortaliza.nombre == datos.nombre).first()
        )
        campos = datos.model_dump(exclude={"etapas"})
        etapas = [EtapaHortaliza(**etapa.model_dump()) for etapa in datos.etapas]

        if existente is None:
            db.add(Hortaliza(**campos, etapas=etapas))
            creadas += 1
        else:
            for campo, valor in campos.items():
                setattr(existente, campo, valor)
            # `cascade="all, delete-orphan"` elimina las etapas anteriores.
            existente.etapas = etapas
            actualizadas += 1

    db.commit()
    return creadas, actualizadas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida el catalogo sin escribir en la base de datos.",
    )
    args = parser.parse_args()

    catalogo = cargar_catalogo()
    nombres = [hortaliza.nombre for hortaliza in catalogo]
    if len(nombres) != len(set(nombres)):
        raise SystemExit("El catalogo tiene nombres repetidos")

    total_etapas = sum(len(hortaliza.etapas) for hortaliza in catalogo)
    print(
        f"Catalogo valido: {len(catalogo)} hortalizas, {total_etapas} etapas."
    )

    if args.dry_run:
        return 0

    db = SessionLocal()
    try:
        creadas, actualizadas = sembrar(db, catalogo)
    finally:
        db.close()

    print(f"Creadas: {creadas}. Actualizadas: {actualizadas}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
