"""agregar_fk_etapas_hortaliza

Agrega la foreign key `etapas_hortaliza.hortaliza_id -> hortalizas.id`, que
faltaba en la migracion inicial `9d2a32684874` (el autogenerate de aquella vez no la
emitio). Sin ella la base de datos no garantizaba la integridad referencial:
las etapas podian quedar huerfanas sin que nada lo impidiera.

Revision ID: d9072270ce8e
Revises: 9d2a32684874
Create Date: 2026-10-21 22:56:46.649075

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9072270ce8e"
down_revision: Union[str, Sequence[Union[str, None]], None] = "9d2a32684874"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_CONSTRAINT = "fk_etapas_hortaliza_hortaliza_id"


def _huerfanos(conn) -> list:
    """Etapas cuyo id de culture no existe en `hortalizas`."""
    return list(
        conn.execute(
            sa.text(
                """
                SELECT e.id, e.hortaliza_id
                FROM etapas_hortaliza e
                LEFT JOIN hortalizas h ON e.hortaliza_id = h.id
                WHERE h.id IS NULL
                """
            )
        )
    )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    huerfanos = _huerfanos(conn)
    if huerfanos:
        # No se borra data de forma silenciosa: la migracion se detiene y el
        # problema se reporta para revisarlo a mano.
        raise RuntimeError(
            "No se puede crear la foreign key: hay etapas sin culture "
            f"correspondiente. Registros afectados: {huerfanos}"
        )

    op.create_foreign_key(
        NOMBRE_CONSTRAINT,
        "etapas_hortaliza",
        "hortalizas",
        ["hortaliza_id"],
        ["id"],
        # Coincide con `cascade="all, delete-orphan"` de la relacion ORM:
        # al borrar una culture se van sus etapas.
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(NOMBRE_CONSTRAINT, "etapas_hortaliza", type_="foreignkey")
