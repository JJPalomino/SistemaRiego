# -*- coding: utf-8 -*-
"""Genera los documentos Word del expediente INDAUTOR a partir de los textos
preparados. Formato sobrio y formal apto para presentación oficial."""

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

BASE = os.path.dirname(os.path.abspath(__file__))

TITULO = (
    "Integración de tecnologías de monitoreo para la optimización del riego "
    "en microparcelas agrícolas"
)
TITULO_MAYUS = TITULO.upper()


def _configurar(doc):
    for seccion in doc.sections:
        seccion.top_margin = Cm(2.5)
        seccion.bottom_margin = Cm(2.5)
        seccion.left_margin = Cm(3)
        seccion.right_margin = Cm(2.5)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(11)
    estilo.paragraph_format.space_after = Pt(10)
    estilo.paragraph_format.line_spacing = 1.5


def _titulo(doc, texto, nivel=1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(texto)
    run.bold = True
    run.font.size = Pt(14 if nivel == 1 else 12)
    run.font.name = "Arial"
    return p


def _subtitulo(doc, texto):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(texto)
    run.italic = True
    run.font.size = Pt(11)
    run.font.name = "Arial"
    return p


def _seccion(doc, texto):
    p = doc.add_paragraph()
    run = p.add_run(texto)
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = "Arial"
    return p


def _parrafo(doc, texto, justificado=True, sangria=False):
    p = doc.add_paragraph()
    if justificado:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if sangria:
        p.paragraph_format.left_indent = Cm(1)
    run = p.add_run(texto)
    run.font.size = Pt(11)
    run.font.name = "Arial"
    return p


def _parrafo_mixto(doc, partes):
    """partes: lista de (texto, negrita, cursiva)."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for texto, neg, cur in partes:
        run = p.add_run(texto)
        run.bold = neg
        run.italic = cur
        run.font.size = Pt(11)
        run.font.name = "Arial"
    return p


def _viñeta(doc, texto):
    p = doc.add_paragraph(style="List Bullet")
    run = p.add_run(texto)
    run.font.size = Pt(11)
    run.font.name = "Arial"
    return p


def _numerada(doc, texto):
    p = doc.add_paragraph(style="List Number")
    run = p.add_run(texto)
    run.font.size = Pt(11)
    run.font.name = "Arial"
    return p


def _firma(doc, nombre, cargo_lineas):
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph("_______________________________________")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(nombre)
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)
    for linea in cargo_lineas:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(linea)
        run.font.name = "Arial"
        run.font.size = Pt(11)


# ---------------------------------------------------------------------------
# 1) Descripción de la obra (RPDA-01)
# ---------------------------------------------------------------------------

def doc_descripcion():
    doc = Document()
    _configurar(doc)
    _titulo(doc, "DESCRIPCIÓN ESCRITA DE LA OBRA")
    _subtitulo(doc, "Formato RPDA-01 — Registro de Programa de Computación ante el INDAUTOR")
    doc.add_paragraph()
    _parrafo_mixto(doc, [
        ("Título de la obra: ", True, False),
        (TITULO, False, False),
    ])
    doc.add_paragraph()
    _parrafo(doc, (
        "La obra consiste en una plataforma digital para el monitoreo y la optimización del "
        "riego en microparcelas agrícolas de los municipios de Tlatlauquitepec y Teziutlán, en "
        "el Estado de Puebla, que apoya al productor en el seguimiento de las condiciones del "
        "suelo y del entorno y en la planeación del riego de nueve hortalizas de importancia "
        "regional (ajo, calabaza, jitomate, rábano, zanahoria, acelga, lechuga, cilantro y "
        "chile). El sistema se compone de tres elementos "
        "principales: (i) una aplicación de escritorio para Windows, programada en el lenguaje "
        "Dart con el marco de trabajo Flutter, que constituye la interfaz de usuario mediante la "
        "cual el productor administra sus parcelas, registra sus ciclos de siembra y cosecha, "
        "solicita recomendaciones agronómicas personalizadas y consulta o descarga reportes en "
        "formato PDF con el historial de recomendaciones; (ii) un servidor de aplicaciones "
        "backend desarrollado en el lenguaje Python sobre el marco de trabajo FastAPI, "
        "estructurado en módulos funcionales que gestionan el registro y autenticación de "
        "usuarios mediante tokens digitales (JWT), el catálogo agronómico de cultivos con sus "
        "etapas fenológicas y parámetros de requerimiento hídrico, el inventario de parcelas y "
        "siembras, la telemetría de sensores de campo, la generación de recomendaciones de riego "
        "y la emisión de reportes; y (iii) una base de datos relacional gestionada con "
        "PostgreSQL, cuyo modelo de datos conserva de manera reproducible la información "
        "agronómica, las lecturas de los sensores, las condiciones climáticas consultadas, las "
        "recomendaciones generadas con el contexto exacto en que fueron producidas y los "
        "metadatos de los reportes emitidos. Para "
        "la obtención de datos meteorológicos, el sistema consulta el servicio público "
        "Open-Meteo, del cual obtiene pronósticos de siete días —temperatura, precipitación, "
        "humedad, radiación solar, evapotranspiración de referencia y condiciones del suelo— que "
        "son normalizados e integrados al modelo agronómico propio de la obra; asimismo, se apoya "
        "en un servicio de inteligencia artificial que redacta en lenguaje natural las "
        "recomendaciones a partir del contexto calculado por el sistema, mientras que la lógica "
        "de decisión agronómica, los catálogos, las validaciones fenológicas y los cálculos "
        "numéricos son desarrollados íntegramente en la plataforma registrada. La utilidad "
        "práctica de la obra radica en que "
        "permite al productor de microparcela dar seguimiento a las condiciones del suelo y del "
        "entorno, decidir con oportunidad cuándo y cuánto regar conforme a la etapa de "
        "desarrollo del cultivo y al pronóstico meteorológico, y conservar un historial trazable "
        "y descargable de las recomendaciones recibidas, contribuyendo con ello al uso eficiente "
        "del agua y a la reducción de pérdidas de cosecha en la región."
    ))
    return os.path.join(BASE, "01_DESCRIPCION_OBRA_RPDA01.docx"), doc


# ---------------------------------------------------------------------------
# 2) Carta de cesión de derechos patrimoniales
# ---------------------------------------------------------------------------

def doc_carta():
    doc = Document()
    _configurar(doc)

    _parrafo(doc, "[Ciudad], Estado de Puebla, a [día] de [mes] de [año].", justificado=False)
    p = doc.add_paragraph()
    run = p.add_run("ASUNTO: Cesión de derechos patrimoniales de autor sobre programa de computación.")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)
    doc.add_paragraph()

    _parrafo(doc, "AL INSTITUTO TECNOLÓGICO SUPERIOR DE TEZIUTLÁN", justificado=False)
    _parrafo(doc, "PRESENTE.", justificado=False)
    doc.add_paragraph()

    _parrafo_mixto(doc, [
        ("Quien suscribe, ", False, False),
        ("JUAN JOSÉ PALOMINO JACOBO", True, False),
        (", por mi propio derecho, señalando como domicilio para oír y recibir notificaciones el "
         "ubicado en [calle, número, colonia, código postal, ciudad, estado], y exhibiendo como "
         "identificación oficial [tipo de identificación: credencial para votar INE / pasaporte / "
         "cédula profesional] con número [número de identificación], en mi carácter de ", False, False),
        ("autor material e intelectual", True, False),
        (" del programa de computación denominado:", False, False),
    ])

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'"{TITULO_MAYUS}"')
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)

    _parrafo(doc, "en adelante \u201Cla Obra\u201D, ante usted con el debido respeto comparezco para exponer:")

    _seccion(doc, "DECLARACIONES")

    _parrafo_mixto(doc, [
        ("PRIMERA. ", True, False),
        ("Que el suscrito es autor único y originario de la Obra, habiendo desarrollado "
         "íntegramente su código fuente, su arquitectura, su modelo de datos, su documentación "
         "técnica y sus elementos gráficos y de interfaz, de conformidad con lo establecido en "
         "los artículos 12 y 13, fracción IV, de la Ley Federal del Derecho de Autor (en lo "
         "sucesivo \u201Cla LFDA\u201D), que reconoce los programas de computación como obras "
         "protegidas por el derecho de autor.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("SEGUNDA. ", True, False),
        ("Que la Obra fue desarrollada por el suscrito en el marco de la prestación de su "
         "servicio social y de actividades académicas vinculadas con el Instituto Tecnológico "
         "Superior de Teziutlán, durante el período comprendido entre el [fecha de inicio] y el "
         "[fecha de término], bajo el programa o proyecto institucional denominado [nombre del "
         "programa o proyecto institucional], con número de control [número de control o "
         "matrícula].", False, False),
    ])
    _parrafo_mixto(doc, [
        ("TERCERA. ", True, False),
        ("Que el desarrollo de la Obra constituyó la contraprestación académica del servicio "
         "social prestado, el cual fue debidamente acreditado mediante [constancia de término de "
         "servicio social / carta de liberación] de fecha [fecha], por lo que la cesión que por "
         "este conducto se otorga se realiza en los términos de los artículos 83, 84 y 46 de la "
         "LFDA y demás disposiciones relativas y aplicables.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("CUARTA. ", True, False),
        ("Que la Obra es original, no se encuentra registrada previamente a nombre de tercero "
         "alguno y el suscrito ostenta la titularidad plena de los derechos patrimoniales que por "
         "este instrumento se ceden, libre de todo gravamen, limitación o afectación.", False, False),
    ])

    _seccion(doc, "CLÁUSULAS")

    _parrafo_mixto(doc, [
        ("PRIMERA. OBJETO DE LA CESIÓN. ", True, False),
        ("El suscrito, en su carácter de autor de la Obra, CEDE Y TRANSFIERE a favor del "
         "INSTITUTO TECNOLÓGICO SUPERIOR DE TEZIUTLÁN, de manera total, onerosa —teniendo por "
         "contraprestación la acreditación del servicio social y las actividades académicas "
         "señaladas en la Declaración Segunda— e irrevocable, la totalidad de los derechos "
         "patrimoniales de autor que le corresponden sobre la Obra, en los términos de los "
         "artículos 43, 44, 46, 83 y demás relativos y aplicables de la LFDA, comprendiendo de "
         "manera enunciativa y no limitativa:", False, False),
    ])
    for item in [
        "a) El derecho exclusivo de explotación de la Obra en cualquier forma y por cualquier "
        "medio o procedimiento conocido o por conocerse;",
        "b) Los derechos de reproducción total o parcial, permanente o provisional, por cualquier "
        "medio, incluido el almacenamiento electrónico y la distribución de copias;",
        "c) Los derechos de comunicación pública, puesta a disposición y transmisión por cualquier medio;",
        "d) El derecho de transformación, adaptación, modificación, actualización y generación de "
        "obras derivadas de la Obra;",
        "e) Los derechos de traducción a otros lenguajes de programación o idiomas; y",
        "f) El derecho de autorizar o prohibir a terceros el uso y explotación de la Obra en todo o en parte.",
    ]:
        _parrafo(doc, item, sangria=True)

    _parrafo_mixto(doc, [
        ("SEGUNDA. TITULARIDAD. ", True, False),
        ("Como consecuencia de la presente cesión, el Instituto Tecnológico Superior de "
         "Teziutlán se convierte en titular exclusivo de los derechos patrimoniales sobre la "
         "Obra, facultado para ejercerlos en los términos del artículo 46 de la LFDA, quedando el "
         "suscrito únicamente con la calidad de autor moral, conservando de manera perpetua, "
         "inalienable, imprescriptible e irrenunciable los derechos morales sobre la Obra, de "
         "conformidad con el artículo 21 de la LFDA, incluido el derecho a ser reconocido como "
         "autor de la misma.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("TERCERA. VIGENCIA. ", True, False),
        ("La presente cesión se otorga por la vigencia máxima permitida por la ley conforme al "
         "artículo 44 de la LFDA, esto es, durante toda la vida del autor y hasta cien años "
         "después de su muerte, o por el plazo que legalmente corresponda tratándose de la "
         "titularidad del cesionario persona moral, sin limitación temporal alguna dentro del "
         "marco legal aplicable.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("CUARTA. ÁMBITO GEOGRÁFICO Y MATERIAL. ", True, False),
        ("La cesión se otorga para todo el territorio de los Estados Unidos Mexicanos y, en "
         "cuanto a su alcance material, comprende todos los medios de explotación conocidos a la "
         "fecha y los que en el futuro lleguen a desarrollarse, sin restricción de plataforma, "
         "formato, lenguaje de programación, dispositivo o sistema operativo.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("QUINTA. INSCRIPCIÓN. ", True, False),
        ("El cesionario queda facultado para inscribir la presente cesión ante el Registro "
         "Público del Derecho de Autor y ante el Instituto Nacional del Derecho de Autor "
         "(INDAUTOR), así como para realizar todos los trámites de registro de la Obra que estime "
         "pertinentes, pudiendo utilizar el presente instrumento como título de propiedad "
         "suficiente.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("SEXTA. ENTREGA DE MATERIAL. ", True, False),
        ("El suscrito hace entrega material al cesionario del código fuente completo de la Obra, "
         "su documentación técnica, manuales de usuario y demás elementos que la integran, en "
         "soporte [disco compacto / memoria USB / repositorio digital], obligándose a no retener "
         "copia alguna con fines de explotación comercial.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("SÉPTIMA. NATURALEZA DEL ACTO. ", True, False),
        ("La presente cesión se celebra al amparo del artículo 83 de la LFDA, relativo a las "
         "obras desarrolladas en cumplimiento de una relación de servicio o de actividades "
         "académicas e institucionales, y no constituye contrato de trabajo ni genera relación "
         "laboral alguna entre las partes.", False, False),
    ])
    _parrafo_mixto(doc, [
        ("OCTAVA. JURISDICCIÓN. ", True, False),
        ("Para la interpretación y cumplimiento del presente instrumento, las partes se someten "
         "expresamente a la jurisdicción de los tribunales competentes con residencia en "
         "[ciudad], Puebla, y a la legislación federal mexicana aplicable, renunciando a "
         "cualquier otro fuero que pudiera corresponderles por razón de sus domicilios presentes "
         "o futuros.", False, False),
    ])

    _parrafo(doc, "Leído que fue el presente instrumento y enterado el suscrito de su contenido "
                  "y alcance legal, lo firma por duplicado en el lugar y fecha señalados al inicio.")
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("ATENTAMENTE")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)

    _firma(doc, "JUAN JOSÉ PALOMINO JACOBO", ["CEDENTE", "Identificación oficial: [tipo y número]"])
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("POR EL INSTITUTO TECNOLÓGICO SUPERIOR DE TEZIUTLÁN")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)
    _firma(doc, "[NOMBRE DEL REPRESENTANTE LEGAL O DIRECTOR(A)]",
           ["[CARGO]", "Instituto Tecnológico Superior de Teziutlán"])

    return os.path.join(BASE, "02_CARTA_CESION_DERECHOS.docx"), doc


# ---------------------------------------------------------------------------
# 3) Resumen de actividades técnicas
# ---------------------------------------------------------------------------

def doc_actividades():
    doc = Document()
    _configurar(doc)
    _titulo(doc, "RESUMEN DE ACTIVIDADES TÉCNICAS")
    _subtitulo(doc, "Informe de servicio social / actividad institucional")
    doc.add_paragraph()
    _parrafo(doc, (
        "Durante el período comprendido entre [fecha de inicio] y [fecha de término], se llevó a "
        "cabo el análisis, diseño y desarrollo del software denominado \u201CIntegración de "
        "tecnologías de monitoreo para la optimización del riego en microparcelas "
        "agrícolas\u201D, plataforma orientada al monitoreo agrícola y a la gestión del riego en "
        "microparcelas de los municipios de Tlatlauquitepec y Teziutlán, Puebla. Las actividades "
        "técnicas comprendieron: (i) el levantamiento de requisitos funcionales y no funcionales a "
        "partir del análisis del problema agrícola regional, con la elaboración de los diagramas "
        "de casos de uso conforme a la notación UML, identificando los actores del sistema "
        "(productor autenticado y servicios externos de datos climáticos y de redacción asistida) "
        "y los escenarios principales de gestión de parcelas, registro de ciclos de siembra, "
        "solicitud de recomendaciones de riego, consulta de historial y descarga de reportes; "
        "(ii) el diseño de los diagramas de secuencia UML correspondientes a los flujos críticos "
        "del sistema, documentando la interacción entre la interfaz de usuario, los módulos del "
        "servidor, la base de datos y los servicios externos, incluyendo los flujos de "
        "autenticación con tokens digitales, la generación de recomendaciones agronómicas y el "
        "proceso transaccional de persistencia del historial; (iii) el diseño de la arquitectura "
        "general del software bajo el estilo cliente-servidor de tres capas, con una aplicación "
        "de escritorio desarrollada en Dart sobre el marco Flutter como capa de presentación, un "
        "servidor de aplicaciones en Python sobre el marco FastAPI organizado en módulos por "
        "dominio funcional (usuarios, catálogo de cultivos, parcelas y siembras, telemetría, "
        "recomendaciones y reportes) como capa de lógica de negocio, y una base de datos "
        "relacional como capa de persistencia, complementada con patrones de diseño orientados a "
        "la robustez transaccional, la seguridad de la información y la integración controlada "
        "con APIs externas; y (iv) el desarrollo del modelo de datos de la base de datos "
        "relacional en PostgreSQL, que incluyó el diseño conceptual, lógico y físico de las "
        "entidades principales (usuarios, hortalizas con sus etapas fenológicas y parámetros "
        "hídricos, parcelas, siembras, sensores y lecturas de telemetría, lecturas climáticas, "
        "consultas de recomendación con trazabilidad del contexto de generación, y reportes "
        "emitidos), la definición de llaves primarias y foráneas con reglas de integridad "
        "referencial, restricciones de unicidad y validación de rangos físicos, así como la "
        "instrumentación de migraciones de esquema versionadas, garantizando con ello la "
        "reproducibilidad e integridad de la información agronómica e hidrometeorológica del "
        "sistema."
    ))
    return os.path.join(BASE, "03_RESUMEN_ACTIVIDADES_TECNICAS.docx"), doc


# ---------------------------------------------------------------------------
# 4) Guía de requisitos del expediente
# ---------------------------------------------------------------------------

def doc_guia():
    doc = Document()
    _configurar(doc)
    _titulo(doc, "GUÍA DE REQUISITOS DEL EXPEDIENTE")
    _subtitulo(doc, "Registro de programa de computación ante el INDAUTOR (México)")
    doc.add_paragraph()
    _parrafo(doc, (
        "Nota importante: Esta guía es orientativa y está basada en los requisitos generales del "
        "trámite de registro de programas de computación ante el INDAUTOR. Antes de presentar el "
        "expediente, verifique la lista de requisitos vigente en la oficina del INDAUTOR de su "
        "localidad o en www.indautor.gob.mx, ya que los formatos, montos de derechos y "
        "presentaciones pueden actualizarse."
    ))

    _seccion(doc, "A. Documentación del expediente")
    for item in [
        "Formato RPDA-01 (solicitud de registro de programa de computación), debidamente llenado "
        "y firmado. El título de la obra debe ser exactamente igual al que aparece en la carta de "
        "cesión y en el software. Debe incluir datos completos del autor (Juan José Palomino "
        "Jacobo) y del cesionario (Instituto Tecnológico Superior de Teziutlán, con RFC), la "
        "descripción de la obra y la fecha de publicación o de conclusión del desarrollo, si aplica.",
        "Carta de cesión de derechos patrimoniales, firmada por el autor y, en su caso, por el "
        "representante del Instituto, con dos testigos si la oficina lo requiere.",
        "Identificaciones oficiales vigentes: copia de identificación oficial del autor "
        "(credencial INE, pasaporte o cédula profesional); copia de identificación oficial y "
        "documento que acredite la personalidad del representante legal del Instituto (poder "
        "notarial o nombramiento); RFC del Instituto (constancia de situación fiscal).",
        "Comprobante de pago de derechos por el trámite de registro (verificar el monto vigente en "
        "la Tabla de Derechos del INDAUTOR; los pagos se realizan mediante línea de captura o "
        "formato universal de pago).",
        "Constancia o carta de liberación del servicio social, si se acredita como contraprestación "
        "de la cesión.",
        "Carta de conformidad institucional, si el Instituto solicita documento adicional de aval "
        "académico (según lineamientos internos del ITST).",
    ]:
        _numerada(doc, item)

    _seccion(doc, "B. Material de depósito (CD/DVD o memoria USB)")
    _parrafo(doc, (
        "El INDAUTOR generalmente acepta el depósito del código fuente o de una porción "
        "representativa del mismo. Se recomienda incluir:"
    ))
    for item in [
        "Código fuente completo del software, organizado en carpetas: frontend (código Dart/Flutter "
        "de la aplicación de escritorio), backend (código Python/FastAPI del servidor) y database "
        "(scripts de esquema y migraciones de la base de datos). Excluir: entornos virtuales "
        "(venv/), dependencias de terceros, archivos binarios grandes, credenciales reales (.env) y "
        "bases de datos con información personal.",
        "Manual de usuario (PDF): capturas de pantalla de las pantallas principales con descripción "
        "de cada funcionalidad.",
        "Manual técnico o de instalación (PDF): requisitos de hardware y software, instrucciones de "
        "instalación y configuración del frontend y del backend.",
        "Documentación de diseño (PDF): diagramas de casos de uso, diagramas de secuencia, diagrama "
        "de arquitectura y modelo entidad-relación de la base de datos.",
        "Identificación del soporte: rótulo adherido al CD/DVD o USB con el título de la obra, "
        "nombre del autor, nombre del cesionario y fecha.",
    ]:
        _numerada(doc, item)

    _seccion(doc, "C. Recomendaciones adicionales")
    for item in [
        "Coherencia del título: el título de la obra debe ser idéntico en el formato RPDA-01, la "
        "carta de cesión, el rótulo del soporte y el software mismo (pantalla de inicio o \u201Cacerca "
        "de\u201D).",
        "Depósito voluntario previo: si el software ya funciona, considere realizar primero el "
        "depósito del código ante el Registro Público del Derecho de Autor para dejar constancia de "
        "la fecha de conclusión.",
        "Servicios de terceros: el uso de APIs externas (Open-Meteo, servicios de modelo de "
        "lenguaje) no afecta la autoría sobre el código propio, pero la descripción debe dejar claro "
        "que la obra registrada es la plataforma desarrollada por el autor, no los servicios "
        "externos consumidos.",
        "Datos personales: elimine del material de depósito cualquier clave de API real, contraseña "
        "o dato personal de usuarios de prueba.",
        "Duplicidad de firmas: presente todos los documentos en original y copia; el INDAUTOR sella "
        "y devuelve la copia como acuse.",
        "Tiempos: el trámite suele tardar varias semanas; consulte la opción de trámite urgente si "
        "su calendario institucional lo requiere.",
    ]:
        _numerada(doc, item)

    return os.path.join(BASE, "04_GUIA_REQUISITOS_EXPEDIENTE.docx"), doc


if __name__ == "__main__":
    for generar in (doc_descripcion, doc_carta, doc_actividades, doc_guia):
        ruta, documento = generar()
        documento.save(ruta)
        print("Generado:", ruta)
