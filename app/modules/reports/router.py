from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.dependencies import get_current_user, get_db
from app.database import SessionLocal
from app.modules.ai_advisor.models import LecturaClimatica
from app.modules.ai_advisor.services import (
    ConsultaNoEncontrada,
    obtener_ultima_consulta_de_siembra,
)
from app.modules.parcels.services import (
    SiembraNoEncontrada,
    obtener_siembra_por_id,
)
from app.modules.reports.services import generar_pdf, registrar_reporte
from app.modules.users.models import Usuario

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes"])


def _sesion_para_registro(db: Session) -> Session:
    """Sesion corta para registrar la descarga, atada al mismo motor.

    Se usa el 'bind' de la sesion de lectura para no depender del motor global:
    las pruebas trabajan con SQLite en memoria y un motor distinto al de
    produccion.
    """
    bind = db.get_bind()
    if bind is None:
        return SessionLocal()
    fabrica = sessionmaker(autocommit=False, autoflush=False, bind=bind)
    return fabrica()


@router.get(
    "/siembras/{siembra_id}.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def reporte_de_siembra(
    siembra_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """PDF de la recomendacion mas reciente de una siembra.

    El archivo se genera en el momento y no se almacena. Solo se registra en
    'reportes_generados' quien lo pidio, para que siembra y cuando.

    La ruta es 'def' para que FastAPI la ejecute en el threadpool y el event
    loop siga atendiendo peticiones. Antes de armar el PDF se libera la sesion
    de base de datos: la generacion no consulta nada y no debe retener una
    conexion del pool. El registro de la descarga se hace despues, en una
    transaccion corta.
    """
    try:
        siembra = obtener_siembra_por_id(db, usuario.id, siembra_id)
        consulta = obtener_ultima_consulta_de_siembra(db, usuario.id, siembra_id)
    except (SiembraNoEncontrada, ConsultaNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))

    lectura = None
    if consulta.lectura_climatica_id is not None:
        lectura = db.get(LecturaClimatica, consulta.lectura_climatica_id)

    # Se conservan los identificadores y el motor antes de soltar la sesion.
    usuario_id = usuario.id
    siembra_id_registro = siembra.id
    consulta_id_registro = consulta.id

    # Los objetos ya tienen cargadas sus columnas y 'siembra.parcela'.
    db.close()

    pdf = generar_pdf(consulta, siembra, lectura)

    db_registro = _sesion_para_registro(db)
    try:
        registrar_reporte(
            db_registro, usuario_id, siembra_id_registro, consulta_id_registro
        )
    finally:
        db_registro.close()

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="reporte_siembra_{siembra_id}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )
