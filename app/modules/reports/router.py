from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
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
    `reportes_generados` quien lo pidio, para que siembra y cuando.
    """
    try:
        siembra = obtener_siembra_por_id(db, usuario.id, siembra_id)
        consulta = obtener_ultima_consulta_de_siembra(
            db, usuario.id, siembra_id
        )
    except (SiembraNoEncontrada, ConsultaNoEncontrada) as e:
        raise HTTPException(status_code=404, detail=str(e))

    lectura = None
    if consulta.lectura_climatica_id is not None:
        lectura = db.get(LecturaClimatica, consulta.lectura_climatica_id)

    pdf = generar_pdf(consulta, siembra, lectura)
    registrar_reporte(db, usuario.id, siembra.id, consulta.id)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="reporte_siembra_{siembra_id}.pdf"'
            )
        },
    )
