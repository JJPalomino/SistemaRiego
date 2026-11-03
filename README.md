# Integración de tecnologías de monitoreo para la optimización del riego en microparcelas agrícolas

Documentación técnica del servidor (backend). Aplicación: **Sistema de Riego**.

El sistema recomienda riego y manejo agrícola para microparcelas de
**Tlatlauquitepec, Puebla** (Sierra Nororiental, bosque de niebla,
1900-3000 msnm), a partir de tres fuentes:

| Fuente | Uso |
|---|---|
| **PostgreSQL** | Catálogo de cultivos, etapas fenológicas e historial |
| **Open-Meteo** | Pronóstico de 7 días (temperatura, lluvia, ET0, radiación, humedad de suelo) |
| **Gemini** | Redacción de la recomendación con el rol de agrónomo experto |

---

## Arquitectura

| Capa | Tecnología | Función |
|---|---|---|
| Presentación | Flutter / Dart (Windows) | Interfaz del productor |
| Aplicación | Python / FastAPI | Reglas de negocio y orquestación |
| Datos | PostgreSQL | Persistencia e historial |
| Servicios externos | Open-Meteo y Gemini | Pronóstico y redacción |

---

## Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/` | no | Estado del servicio |
| `GET` | `/health` | no | Sonda de salud |
| `POST` | `/api/v1/usuarios/registro` | no | Crear usuario |
| `POST` | `/api/v1/usuarios/login` | no | Iniciar sesión, devuelve JWT |
| `GET` | `/api/v1/usuarios/me` | **si** | Usuario del token Bearer |
| `GET` | `/api/v1/hortalizas/` | no | Catálogo de hortalizas |
| `GET` | `/api/v1/hortalizas/{id}` | no | Hortaliza con sus etapas |
| `POST` | `/api/v1/hortalizas/` | **si** | Crear hortaliza con etapas |
| `PUT` | `/api/v1/hortalizas/{id}` | **si** | Actualizar hortaliza (reemplazo completo) |
| `DELETE` | `/api/v1/hortalizas/{id}` | **si** | Eliminar hortaliza (409 si tiene siembras) |
| `GET` | `/api/v1/parcelas/` | **si** | Parcelas del usuario |
| `POST` | `/api/v1/parcelas/` | **si** | Crear parcela |
| `GET` | `/api/v1/parcelas/{id}` | **si** | Detalle de una parcela propia |
| `PUT` | `/api/v1/parcelas/{id}` | **si** | Actualizar parcela |
| `DELETE` | `/api/v1/parcelas/{id}` | **si** | Eliminar parcela (cascada a siembras y sensores) |
| `GET` | `/api/v1/parcelas/{id}/siembras` | **si** | Ciclos de cultivo de la parcela |
| `POST` | `/api/v1/parcelas/{id}/siembras` | **si** | Registrar un ciclo de cultivo |
| `PUT` | `/api/v1/parcelas/{id}/siembras/{sid}` | **si** | Actualizar un ciclo |
| `DELETE` | `/api/v1/parcelas/{id}/siembras/{sid}` | **si** | Eliminar un ciclo |
| `GET` | `/api/v1/parcelas/{id}/siembra-vigente` | **si** | Ciclo activo hoy (o `null`) |
| `POST` | `/api/v1/telemetria/sensores` | **si** | Registrar un sensor en una parcela |
| `GET` | `/api/v1/telemetria/sensores?parcela_id=` | **si** | Sensores de la parcela |
| `POST` | `/api/v1/telemetria/lecturas` | **si** | Ingesta idempotente de un lote de lecturas |
| `GET` | `/api/v1/telemetria/lecturas?sensor_id=` | **si** | Histórico de un sensor (con `desde`/`hasta`/`limite`) |
| `GET` | `/api/v1/telemetria/resumen?parcela_id=` | **si** | Última lectura de cada sensor |
| `POST` | `/api/v1/ai/recomendacion` | **si** | Recomendación de riego para 7 días |
| `GET` | `/api/v1/ai/clima?parcela_id=` | **si** | Consultas a Open-Meteo guardadas (sin JSON) |
| `GET` | `/api/v1/ai/clima/{id}` | **si** | Detalle climático con el JSON original |
| `GET` | `/api/v1/ai/historial?siembra_id=` | **si** | Recomendaciones generadas para una siembra |
| `GET` | `/api/v1/ai/historial/{id}` | **si** | Detalle con prompt y respuesta íntegra |
| `GET` | `/api/v1/reportes/siembras/{id}.pdf` | **si** | PDF de la última recomendación de la siembra |

### Autenticación

Cada usuario inicia sesión con correo y contraseña. El servidor entrega un token
JWT firmado que la aplicación envía en la cabecera `Authorization` de cada
solicitud protegida. El token expira transcurrido el tiempo de vigencia
configurado y, mientras está activo, toda consulta se limita a los datos del
usuario que lo posee.

---

## Estructura

```
app/
├── main.py                  # App FastAPI, middlewares y routers
├── database.py              # engine, SessionLocal, Base
├── core/
│   ├── config.py            # Settings (pydantic-settings)
│   └── dependencies.py      # get_db, get_current_user
└── modules/
    ├── users/               # models / schemas / services / router
    ├── crops/               # catálogo de hortalizas y sus etapas
    ├── parcels/             # parcelas y siembras (ciclos de cultivo)
    ├── telemetry/           # sensores, lecturas e ingesta idempotente
    ├── ai_advisor/          # clima, redacción, historial reproducible
    ├── reports/             # PDF generado bajo demanda
    └── ml_models/           # reservado para el modelo de predicción
data/
└── catalogo_hortalizas.json # 9 cultivos con umbrales y etapas
scripts/
└── seed_catalogo.py         # carga idempotente del catálogo
```

Cada módulo sigue la misma cadena: **models** (SQLAlchemy) → **schemas**
(Pydantic) → **services** (reglas de negocio) → **router** (HTTP).

---

## Configuración

Los parámetros de operación se concentran en un archivo de configuración que no
forma parte del código: conexión a la base de datos, clave de firma de sesiones,
acceso al servicio de redacción, modelo de lenguaje, modo de demostración,
vigencia de la sesión y orígenes permitidos por CORS.

---

## Notas de dominio

- **Unidades**: la humedad de suelo se maneja en **porcentaje (0-100)** y la
  radiación solar en **W/m2**. Open-Meteo entrega la humedad como fracción
  (0-1) y la radiación diaria en MJ/m2; `weather_client.py` normaliza ambas.
- **Etapas fenológicas**: `EtapaHortaliza` tiene `dia_inicio` y `dia_fin`.
  El día de siembra se usa para ubicar la etapa vigente.
- **Integridad**: `etapas_hortaliza.hortaliza_id` referencia a
  `hortalizas.id` con `ON DELETE CASCADE`, en cascada con el
  `cascade="all, delete-orphan"` del ORM. `siembras.hortaliza_id` es
  `RESTRICT`: un cultivo con histórico no se puede borrar (la API responde
  409).
- **Parcelas y siembras**: una parcela agrupa varios ciclos de cultivo. Dos
  ciclos de la misma parcela no pueden solaparse; cosechar y sembrar el mismo
  día sí es válido. Un ciclo sin `fecha_cosecha` se considera abierto.
- **Telemetría**: cada sensor tiene un `codigo` único y declara `tipo`,
  `unidad` y (solo si está enterrado) `profundidad_cm`. La unidad se deriva
  del tipo, no la envía el cliente.
- **Ingesta idempotente**: el índice único `(sensor_id, timestamp)` hace que
  reenviar un lote no duplique datos. El endpoint devuelve `recibidas`,
  `unicas`, `insertadas` y `duplicadas`.
- **Rangos físicos**: las lecturas fuera del rango plausible de su tipo se
  rechazan con 422 antes de entrar al histórico de entrenamiento.
- **Aislamiento**: toda consulta de parcelas, siembras, sensores y lecturas se
  filtra por `usuario_id`. Un recurso ajeno responde 404, no 403, para no
  revelar su existencia.

### Historial reproducible

- **`lecturas_climaticas`** guarda cada consulta a Open-Meteo con el JSON
  completo de respaldo (`datos_json`) y los campos normalizados. El listado
  (`/api/v1/ai/clima`) omite el JSON; el detalle lo incluye.
- **`consultas_recomendaciones`** guarda la siembra, la lectura climática, el
  cultivo, la etapa y los días transcurridos, además del **prompt exacto** y la
  **respuesta íntegra** del modelo (`respuesta_json`). Las claves foráneas usan
  `ON DELETE SET NULL`: borrar una siembra no destruye el historial.
- **`reportes_generados`** solo registra metadatos (usuario, siembra, consulta
  y fecha). El PDF se arma al momento y no se almacena.
- **Altitud automática**: al crear una parcela sin `altitud_msnm`, el backend
  la consulta a Open-Meteo. Si el servicio falla, la parcela se crea con
  `null`; la altitud no bloquea el registro.
- **Tabla de telemetría**: la tabla se llama `lecturas_sensor` para distinguirla
  de `lecturas_climaticas`. La ruta pública sigue siendo
  `/api/v1/telemetria/lecturas`.

---

## Estado legal

Obra: **Integración de tecnologías de monitoreo para la optimización del riego
en microparcelas agrícolas**.

Autor: **Juan José Palomino Jacobo**, quien conserva los derechos morales
irrenunciables sobre la obra.

Titular de los derechos patrimoniales: **Instituto Tecnológico Superior de
Teziutlán**, por cesión otorgada conforme a la Ley Federal del Derecho de Autor.

El detalle de la cesión se encuentra en el archivo `LICENCIA` de este
repositorio.
