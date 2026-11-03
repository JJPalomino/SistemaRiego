# GUÍA DE REQUISITOS DEL EXPEDIENTE
## Registro de programa de computación ante el INDAUTOR (México)

> **Nota importante:** Esta guía es orientativa y está basada en los requisitos generales del trámite de registro de programas de computación ante el INDAUTOR. Antes de presentar el expediente, verifique la lista de requisitos vigente en la oficina del INDAUTOR de su localidad o en www.indautor.gob.mx, ya que los formatos, montos de derechos y presentaciones pueden actualizarse.

## A. Documentación del expediente

1. **Formato RPDA-01** (solicitud de registro de programa de computación), debidamente llenado y firmado:
   - Título de la obra exactamente igual al que aparece en la carta de cesión y en el software.
   - Datos completos del autor (Juan José Palomino Jacobo).
   - Datos completos del cesionario/titular (Instituto Tecnológico Superior de Teziutlán, con RFC).
   - Descripción de la obra (usar el texto del entregable 01).
   - Fecha de publicación o de conclusión del desarrollo, si aplica.
2. **Carta de cesión de derechos patrimoniales** (entregable 02), firmada por el autor y, en su caso, por el representante del Instituto, con dos testigos si la oficina lo requiere.
3. **Identificaciones oficiales vigentes:**
   - Copia de identificación oficial del autor (credencial INE, pasaporte o cédula profesional).
   - Copia de identificación oficial y documento que acredite la personalidad del representante legal del Instituto (poder notarial o nombramiento).
   - RFC del Instituto (constancia de situación fiscal).
4. **Comprobante de pago de derechos** por el trámite de registro (verificar el monto vigente en la Tabla de Derechos del INDAUTOR; los pagos se realizan mediante línea de captura o formato universal de pago).
5. **Constancia o carta de liberación del servicio social**, si se acredita como contraprestación de la cesión.
6. **Carta de conformidad institucional**, si el Instituto solicita documento adicional de aval académico (según lineamientos internos del ITST).

## B. Material de depósito (CD/DVD o memoria USB)

El INDAUTOR generalmente acepta el depósito del código fuente o de una porción representativa del mismo. Se recomienda incluir:

1. **Código fuente completo del software**, organizado en carpetas:
   - `frontend/` — código Dart/Flutter de la aplicación de escritorio.
   - `backend/` — código Python/FastAPI del servidor.
   - `database/` — scripts de esquema y migraciones de la base de datos.
   - Excluir: entornos virtuales (`venv/`), dependencias de terceros (`node_modules`, paquetes compilados), archivos binarios grandes, credenciales reales (`.env`), bases de datos con información personal.
2. **Manual de usuario** (PDF): capturas de pantalla de las pantallas principales con descripción de cada funcionalidad.
3. **Manual técnico o de instalación** (PDF): requisitos de hardware y software, instrucciones de instalación y configuración del frontend y del backend.
4. **Documentación de diseño** (PDF): diagramas de casos de uso, diagramas de secuencia, diagrama de arquitectura y modelo entidad-relación de la base de datos.
5. **Identificación del soporte**: rótulo adherido al CD/DVD o USB con el título de la obra, nombre del autor, nombre del cesionario y fecha.

## C. Recomendaciones adicionales

1. **Coherencia del título:** el título de la obra debe ser idéntico en el formato RPDA-01, la carta de cesión, el rótulo del soporte y el software mismo (pantalla de inicio/acerca de).
2. **Depósito voluntario previo:** si el software ya funciona, considere realizar primero el depósito del código ante el Registro Público del Derecho de Autor para dejar constancia de la fecha de conclusión.
3. **Servicios de terceros:** el uso de APIs externas (Open-Meteo, servicios de modelo de lenguaje) no afecta la autoría sobre el código propio, pero la descripción debe dejar claro que la obra registrada es la plataforma desarrollada por el autor, no los servicios externos consumidos.
4. **Datos personales:** elimine del material de depósito cualquier clave de API real, contraseña o dato personal de usuarios de prueba.
5. **Duplicidad de firmas:** presente todos los documentos en original y copia; el INDAUTOR sella y devuelve la copia como acuse.
6. **Tiempos:** el trámite suele tardar varias semanas; consulte la opción de trámite urgente si su calendario institucional lo requiere.
