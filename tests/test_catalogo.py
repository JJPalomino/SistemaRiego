"""Pruebas del catalogo agronomico base."""

from app.modules.crops.models import Hortaliza
from scripts.seed_catalogo import cargar_catalogo, sembrar

NOMBRES_ESPERADOS = {
    "Jitomate",
    "Lechuga",
    "Cilantro",
    "Calabaza",
    "Ajo",
    "Rabano",
    "Acelga",
    "Chile",
    "Zanahoria",
}


def test_catalogo_tiene_las_9_hortalizas():
    catalogo = cargar_catalogo()
    assert {hortaliza.nombre for hortaliza in catalogo} == NOMBRES_ESPERADOS


def test_etapas_cubren_el_ciclo_completo():
    for hortaliza in cargar_catalogo():
        assert hortaliza.etapas, f"{hortaliza.nombre} no tiene etapas"
        assert hortaliza.etapas[0].dia_inicio == 1
        assert (
            hortaliza.etapas[-1].dia_fin == hortaliza.duracion_total_dias
        ), f"Las etapas de {hortaliza.nombre} no cierran el ciclo"


def test_etapas_son_continuas():
    for hortaliza in cargar_catalogo():
        for anterior, siguiente in zip(
            hortaliza.etapas, hortaliza.etapas[1:]
        ):
            assert siguiente.dia_inicio == anterior.dia_fin + 1, (
                f"Hay un hueco o traslape entre las etapas de "
                f"{hortaliza.nombre}"
            )


def test_sembrar_es_idempotente(db):
    catalogo = cargar_catalogo()

    creadas, actualizadas = sembrar(db, catalogo)
    assert (creadas, actualizadas) == (len(catalogo), 0)
    assert db.query(Hortaliza).count() == len(catalogo)

    creadas, actualizadas = sembrar(db, catalogo)
    assert (creadas, actualizadas) == (0, len(catalogo))
    assert db.query(Hortaliza).count() == len(catalogo)
