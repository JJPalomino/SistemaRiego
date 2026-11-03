# Contexto del sistema

Documento de apoyo para quien trabaja en el código. Describe el propósito, la
arquitectura, las reglas de negocio y las convenciones del sistema.

## 1. Propósito

Plataforma de monitoreo y optimización del riego para microparcelas agrícolas de
Tlatlauquitepec y Teziutlán, Puebla. Combina un catálogo agronómico de nueve
hortalizas con el pronóstico meteorológico de Open-Meteo y un servicio de
redacción asistida por inteligencia artificial para producir recomendaciones de
riego y alertas de riesgo.

La aplicación de escritorio se usa en la computadora del productor; el servidor
concentra la lógica y el acceso a datos.

## 2. Componentes

| Componente | Tecnología | Función |
|---|---|---|
| Aplicación de escritorio | Flutter / Dart (Windows) | Interfaz del productor |
| Servidor | Python / FastAPI | Reglas de negocio, validación y orquestación |
| Base de datos | PostgreSQL | Persistencia e historial |
| Pronóstico | Open-Meteo | Clima de siete días de la parcela |
| Redacción | Google Gemini | Texto de la recomendación |

## 3. Flujo principal

1. El usuario se registra e inicia sesión; el servidor emite un token JWT.
2. Registra una parcela con sus coordenadas. Si no indica altitud, el servidor
   la obtiene de Open-Meteo.
3. Registra una siembra: parcela, hortaliza y fecha de siembra.
4. Solicita una recomendación para esa siembra.
5. El servidor calcula la etapa fenológica según los días transcurridos,
   consulta el pronóstico y arma el contexto del cultivo.
6. El servicio de inteligencia artificial redacta la recomendación; el servidor
   sanea y valida la respuesta.
7. La lectura climática y la consulta se guardan en una sola transacción.
8. El usuario consulta el historial o descarga el reporte PDF.

## 4. Modelo de datos

| Tabla | Contenido |
|---|---|
| `usuarios` | Credenciales y perfil |
| `hortalizas` | Catálogo con parámetros agronómicos |
| `etapas_hortaliza` | Etapas fenológicas por rango de días |
| `parcelas` | Microparcelas del usuario |
| `siembras` | Ciclos de cultivo |
| `sensores` | Dispositivos de medición de la parcela |
| `lecturas_sensor` | Mediciones registradas |
| `lecturas_climaticas` | Pronósticos consultados |
| `consultas_recomendaciones` | Recomendaciones con su contexto |
| `reportes_generados` | Metadatos de los PDF emitidos |

## 5. Reglas de negocio

- **Unidades:** la humedad del suelo se maneja en porcentaje (0-100) y la
  radiación solar en W/m2. Open-Meteo entrega la humedad como fracción (0-1) y
  la radiación diaria en MJ/m2; el cliente del clima normaliza ambas.
- **Etapas fenológicas:** cada etapa tiene día de inicio y día de fin; la etapa
  vigente se ubica con los días transcurridos desde la siembra.
- **Traslape:** dos ciclos de la misma parcela no pueden solaparse. Cosechar y
  sembrar el mismo día sí es válido. Un ciclo sin fecha de cosecha se considera
  abierto.
- **Integridad:** las etapas se eliminan en cascada con su hortaliza; una
  hortaliza con siembras registradas no se puede borrar (la API responde 409).
- **Aislamiento:** toda consulta se filtra por usuario. Un recurso ajeno
  responde 404, no 403, para no revelar su existencia.
- **Telemetría:** cada sensor declara tipo y unidad; la profundidad solo aplica
  a sensores enterrados. La ingesta es idempotente por la llave
  (sensor, marca de tiempo).
- **Rangos físicos:** las lecturas fuera del rango plausible de su tipo se
  rechazan antes de almacenarse.
- **Historial:** la consulta guarda el pronóstico completo, el prompt exacto y
  la respuesta íntegra, de modo que pueda reproducirse después.
- **Reportes:** el PDF se genera al momento y no se almacena; solo se registra
  quién lo pidió y cuándo.

## 6. Convenciones de código

- Cada módulo sigue la cadena `models` → `schemas` → `services` → `router`.
- Las rutas con trabajo bloqueante se declaran con `def` para ejecutarse en el
  threadpool y no detener el bucle de eventos.
- La sesión de base de datos se libera antes de llamadas externas o de trabajo
  intensivo, y se reabre solo para persistir.
- Los errores que llegan al cliente son genéricos: nunca exponen credenciales
  ni detalles internos.
- Las pruebas usan una base SQLite en memoria y sustituyen los servicios
  externos por respuestas controladas.

## 7. Configuración

| Parámetro | Uso |
|---|---|
| Conexión a la base de datos | Cadena de PostgreSQL |
| Clave de sesión | Firma de los tokens JWT |
| Clave de Google AI Studio | Acceso al servicio de redacción |
| Modelo de IA | Modelo principal y lista de respaldo |
| Modo de demostración | Responde sin consumir cuota del servicio |
| Vigencia de sesión | Horas que dura el token |
| Orígenes permitidos | Dominios autorizados por CORS |
