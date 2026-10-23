"""Armado del PDF de una recomendacion.

El PDF se construye en memoria con ReportLab y se devuelve como descarga. No se
guarda en disco ni en la base: solo se registran metadatos en
`reportes_generados`, tal como pide el documento del proyecto.
"""

from datetime import datetime
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.modules.ai_advisor.models import (
    ConsultaRecomendacion,
    LecturaClimatica,
    ReporteGenerado,
)
from app.modules.parcels.models import Siembra

AZUL = colors.HexColor("#1F4E79")
GRIS = colors.HexColor("#F2F2F2")
VERDE = colors.HexColor("#2E7D32")
NARANJA = colors.HexColor("#EF6C00")
ROJO = colors.HexColor("#C62828")


def _texto(valor) -> str:
    """Convierte cualquier valor a texto seguro para un Paragraph."""
    if valor is None:
        return "No disponible"
    return escape(str(valor))


def _numero(valor, sufijo: str = "") -> str:
    if valor is None:
        return "No disponible"
    try:
        return f"{float(valor):.2f}{sufijo}"
    except (TypeError, ValueError):
        return _texto(valor)


def _color_urgencia(nivel: str):
    return {
        "critica": ROJO,
        "precaucion": NARANJA,
        "informativa": VERDE,
    }.get(nivel, VERDE)


def _hex(color) -> str:
    """Devuelve un color en formato #RRGGBB aceptado por las etiquetas font."""
    return "#%02x%02x%02x" % (
        int(round(color.red * 255)),
        int(round(color.green * 255)),
        int(round(color.blue * 255)),
    )


def _tabla_datos(filas: list[tuple[str, str]], estilos) -> Table:
    tabla = Table(
        [[Paragraph(f"<b>{_texto(k)}</b>", estilos["celda"]),
          Paragraph(_texto(v), estilos["celda"])] for k, v in filas],
        colWidths=[4.2 * cm, 11.3 * cm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GRIS),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabla


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "Titulo",
            parent=base["Title"],
            fontSize=18,
            textColor=AZUL,
            spaceAfter=2,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "seccion": ParagraphStyle(
            "Seccion",
            parent=base["Heading2"],
            fontSize=12,
            textColor=AZUL,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "cuerpo": ParagraphStyle(
            "Cuerpo",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ),
        "celda": ParagraphStyle(
            "Celda",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
        ),
        "nota": ParagraphStyle(
            "Nota",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.grey,
            leading=10,
        ),
    }


def _fecha(valor) -> str:
    if valor is None:
        return "No disponible"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    return str(valor)


def generar_pdf(
    consulta: ConsultaRecomendacion,
    siembra: Siembra,
    lectura: Optional[LecturaClimatica] = None,
) -> bytes:
    """Construye el PDF y devuelve sus bytes."""
    estilos = _estilos()
    historia = []

    historia.append(Paragraph("Reporte de riego", estilos["titulo"]))
    historia.append(
        Paragraph(
            "Sistema de recomendaciones para microparcelas - "
            "Tlatlauquitepec, Puebla",
            estilos["subtitulo"],
        )
    )

    parcela = getattr(siembra, "parcela", None)
    historia.append(Paragraph("Datos de la siembra", estilos["seccion"]))
    historia.append(
        _tabla_datos(
            [
                ("Parcela", getattr(parcela, "nombre", "No disponible")),
                (
                    "Ubicacion",
                    (
                        f"{float(parcela.latitud):.4f}, "
                        f"{float(parcela.longitud):.4f}"
                        if parcela is not None
                        else "No disponible"
                    ),
                ),
                ("Cultivo", consulta.nombre_hortaliza),
                ("Etapa fenologica", consulta.etapa or "No determinada"),
                ("Dias desde la siembra", str(consulta.dias_siembra)),
                ("Fecha de la recomendacion", _fecha(consulta.consultado_en)),
            ],
            estilos,
        )
    )

    if lectura is not None:
        historia.append(Paragraph("Condiciones climaticas", estilos["seccion"]))
        historia.append(
            _tabla_datos(
                [
                    (
                        "Periodo pronosticado",
                        f"{lectura.fecha_inicio_pronostico or '?'} a "
                        f"{lectura.fecha_fin_pronostico or '?'}",
                    ),
                    (
                        "Temperatura maxima / minima",
                        f"{_numero(lectura.temp_max_c, ' C')} / "
                        f"{_numero(lectura.temp_min_c, ' C')}",
                    ),
                    (
                        "Precipitacion acumulada",
                        _numero(lectura.precipitacion_mm, " mm"),
                    ),
                    (
                        "Evapotranspiracion de referencia",
                        _numero(lectura.evapotranspiracion_ref_mm, " mm"),
                    ),
                    (
                        "Humedad relativa",
                        _numero(lectura.humedad_relativa_pct, " %"),
                    ),
                    (
                        "Humedad del suelo",
                        _numero(lectura.humedad_suelo_pct, " %"),
                    ),
                    (
                        "Viento",
                        _numero(lectura.velocidad_viento_kmh, " km/h"),
                    ),
                    (
                        "Radiacion solar",
                        _numero(lectura.radiacion_solar_wm2, " W/m2"),
                    ),
                ],
                estilos,
            )
        )

    historia.append(Paragraph("Recomendacion de riego", estilos["seccion"]))
    historia.append(
        Paragraph(_texto(consulta.recomendacion_riego), estilos["cuerpo"])
    )

    historia.append(Paragraph("Recomendacion general", estilos["seccion"]))
    historia.append(
        Paragraph(_texto(consulta.recomendacion_general), estilos["cuerpo"])
    )

    alertas = (consulta.respuesta_json or {}).get("alertas") or []
    if alertas:
        historia.append(Paragraph("Alertas", estilos["seccion"]))
        for alerta in alertas:
            if not isinstance(alerta, dict):
                continue
            nivel = str(alerta.get("nivel", "informativa")).lower()
            color = _hex(_color_urgencia(nivel))
            descripcion = _texto(alerta.get("descripcion", ""))
            historia.append(
                Paragraph(
                    f'<font color="{color}"><b>{_texto(nivel.capitalize())}'
                    f"</b></font>: {descripcion}",
                    estilos["cuerpo"],
                )
            )

    nivel = (consulta.nivel_urgencia_max or "informativa").lower()
    color_nivel = _hex(_color_urgencia(nivel))
    historia.append(Spacer(1, 8))
    historia.append(
        Paragraph(
            f'Nivel de urgencia general: <font color="{color_nivel}">'
            f"<b>{_texto(nivel.capitalize())}</b></font>",
            estilos["cuerpo"],
        )
    )

    historia.append(Spacer(1, 16))
    historia.append(
        Paragraph(
            "Documento generado automaticamente por el sistema de "
            "recomendaciones. La recomendacion combina el modelo de prediccion, "
            "el pronostico de Open-Meteo y la redaccion del asesor; debe "
            "validarse en campo antes de aplicarse.",
            estilos["nota"],
        )
    )

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Reporte de riego - {consulta.nombre_hortaliza}",
        author="Sistema de recomendaciones de riego",
    )
    documento.build(historia)
    return buffer.getvalue()


def registrar_reporte(
    db: Session,
    usuario_id: int,
    siembra_id: int,
    consulta_id: int,
) -> ReporteGenerado:
    """Deja rastro del PDF emitido (sin guardar el archivo)."""
    reporte = ReporteGenerado(
        usuario_id=usuario_id,
        siembra_id=siembra_id,
        consulta_id=consulta_id,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte
