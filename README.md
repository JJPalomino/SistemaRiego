# Sistema de Recomendaciones de Riego

API para recomendar riego y manejo agricola en microparcelas de
**Tlatlauquitepec, Puebla** (Sierra Nororiental, bosque de niebla,
1900-3000 msnm).

Combina tres fuentes:

| Fuente | Uso |
|---|---|
| **PostgreSQL** | Catalogo de cultures, etapas fenologicas y usuarios |
| **Open-Meteo** | Pronostico de 7 dias (temperatura, lluvia, ET0, radiacion, humedad de suelo) |
| **Gemini** | Redaccion de la recomendacion con el rol de agronomo experto |

---

## Puesta en marcha

```bash
# 1. Entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / macOS

# 2. Dependencias
pip install -r requirements.txt

# 3. Configuracion
copy .env.example .env           # Windows
cp .env.example .env             # Linux / macOS
# Editar .env con DATABASE_URL, SECRET_KEY y GEMINI_API_KEY

# 4. Esquema de la base de datos
alembic upgrade head

# 5. Servidor
uvicorn app.main:app --reload
```

Documentacion interactiva: <http://127.0.0.1:8000/docs>

---

## Endpoints

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/` | no | Estado del servicio |
| `GET` | `/health` | no | Sonda de salud |
| `POST` | `/api/v1/usuarios/registro` | no | Crear usuario |
| `POST` | `/api/v1/usuarios/login` | no | Iniciar sesion, devuelve JWT |
| `GET` | `/api/v1/usuarios/me` | **si** | Usuario del token Bearer |
| `GET` | `/api/v1/hortalizas/` | no | Catalogo de hortalizas |
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
| `GET` | `/api/v1/telemetria/lecturas?sensor_id=` | **si** | Historico de un sensor (con `desde`/`hasta`/`limite`) |
| `GET` | `/api/v1/telemetria/resumen?parcela_id=` | **si** | Ultima lectura de cada sensor |
| `POST` | `/api/v1/ai/recomendacion` | **si** | Recomendacion de riego para 7 dias |
| `GET` | `/api/v1/ai/clima?parcela_id=` | **si** | Consultas a Open-Meteo guardadas (sin JSON) |
| `GET` | `/api/v1/ai/clima/{id}` | **si** | Detalle climatico con el JSON original |
| `GET` | `/api/v1/ai/historial?siembra_id=` | **si** | Recomendaciones generadas para una siembra |
| `GET` | `/api/v1/ai/historial/{id}` | **si** | Detalle con prompt y respuesta integra |
| `GET` | `/api/v1/reportes/siembras/{id}.pdf` | **si** | PDF de la ultima recomendacion de la siembra |

### Autenticacion

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/usuarios/login \
  -H "Content-Type: application/json" \
  -d '{"email":"correo@ejemplo.mx","password":"contrasena123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://127.0.0.1:8000/api/v1/ai/recomendacion \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id_hortaliza": 1, "dias_siembra": 25}'

# Con una siembra registrada: toma cultivo, parcela, etapa y dias de la base,
# y deja la consulta en el historial reproducible.
curl -X POST http://127.0.0.1:8000/api/v1/ai/recomendacion \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"siembra_id": 1}'

# PDF de la ultima recomendacion de esa siembra.
curl -L -o reporte.pdf \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/reportes/siembras/1.pdf
```

El token expira en `ACCESS_TOKEN_EXPIRE_HOURS` (24 h por defecto) y se firma
con HS256 usando `SECRET_KEY`.

---

## Configuracion (`.env`)

| Variable | Default | Descripcion |
|---|---|---|
| `DATABASE_URL` | — | Cadena de conexion PostgreSQL |
| `SECRET_KEY` | — | Clave de firma de los JWT |
| `GEMINI_API_KEY` | — | API key de Google AI Studio |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Modelo de Gemini a usar |
| `DEMO_MODE` | `false` | `true` responde sin llamar a Gemini (ahorra cuota) |
| `ACCESS_TOKEN_EXPIRE_HOURS` | `24` | Vigencia del token |
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | Tope de tokens de salida |
| `GEMINI_MAX_RETRIES` | `3` | Reintentos ante 429/5xx |
| `CORS_ORIGINS` | `["*"]` | Origenes permitidos |

> `gemini-1.5-flash` fue **retirado** de la API. Para ver los modelos
> vigentes: `GET https://generativelanguage.googleapis.com/v1beta/models`

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
    ├── crops/               # catalogo de hortalizas y sus etapas
    ├── parcels/             # parcelas y siembras (ciclos de cultivo)
    ├── telemetry/           # sensores, lecturas e ingesta idempotente
    ├── ai_advisor/          # clima, LLM, historial reproducible
    ├── reports/             # PDF generado bajo demanda
    └── ml_models/           # (fase 4: entrenamiento e inferencia)
data/
└── catalogo_hortalizas.json # 9 cultivos con umbrales y etapas
scripts/
└── seed_catalogo.py         # carga idempotente del catalogo
```

Cada modulo sigue la misma cadena: **models** (SQLAlchemy) -> **schemas**
(Pydantic) -> **services** (reglas de negocio) -> **router** (HTTP).

Para cargar el catalogo agronomico:

```bash
python -m scripts.seed_catalogo            # crea o actualiza
python -m scripts.seed_catalogo --dry-run  # solo valida el JSON
```

---

## Pruebas

```bash
pytest                          # suite completa
pytest --cov=app --cov-report=term-missing
```

Las pruebas usan SQLite en memoria y sustituyen Open-Meteo y Gemini por
respuestas controladas, asi que **no consumen cuota ni requieren la base de
datos de desarrollo**.

---

## Migraciones

```bash
alembic revision --autogenerate -m "descripcion"
alembic upgrade head
alembic downgrade -1
alembic current
```

La URL de la base de datos se inyecta desde `.env` en `migrations/env.py`.

---

## Notas de dominio

- **Unidades**: la humedad de suelo se maneja en **porcentaje (0-100)** y la
  radiacion solar en **W/m2**. Open-Meteo entrega la humedad como fraccion
  (0-1) y la radiacion diaria en MJ/m2; `weather_client.py` normaliza ambas.
- **Etapas fenologicas**: `EtapaHortaliza` tiene `dia_inicio` y `dia_fin`.
  El dia de siembra se usa para ubicar la etapa vigente.
- **Integridad**: `etapas_hortaliza.hortaliza_id` referencia a
  `hortalizas.id` con `ON DELETE CASCADE`, en cascada con el
  `cascade="all, delete-orphan"` del ORM. `siembras.hortaliza_id` es
  `RESTRICT`: un cultivo con historico no se puede borrar (la API responde
  409).
- **Parcelas y siembras**: una parcela agrupa varios ciclos de cultivo. Dos
  ciclos de la misma parcela no pueden solaparse; cosechar y sembrar el mismo
  dia si es valido. Un ciclo sin `fecha_cosecha` se considera abierto.
- **Telemetria**: cada sensor tiene un `codigo` unico y declara `tipo`,
  `unidad` y (solo si esta enterrado) `profundidad_cm`. La unidad se deriva
  del tipo, no la envia el cliente.
- **Ingesta idempotente**: el indice unico `(sensor_id, timestamp)` hace que
  reenviar un lote no duplique datos. El endpoint devuelve `recibidas`,
  `unicas`, `insertadas` y `duplicadas`.
- **Rangos fisicos**: las lecturas fuera del rango plausible de su tipo se
  rechazan con 422 antes de entrar al historico de entrenamiento.
- **Aislamiento**: toda consulta de parcelas, siembras, sensores y lecturas se
  filtra por `usuario_id`. Un recurso ajeno responde 404, no 403, para no
  revelar su existencia.

### Historial reproducible

- **`lecturas_climaticas`** guarda cada consulta a Open-Meteo con el JSON
  completo de respaldo (`datos_json`) y los campos normalizados. El listado
  (`/api/v1/ai/clima`) omite el JSON; el detalle lo incluye.
- **`consultas_recomendaciones`** guarda la siembra, la lectura climatica, el
  cultivo, la etapa y los dias transcurridos, ademas del **prompt exacto** y la
  **respuesta integra** del modelo (`respuesta_json`). Las claves foraneas usan
  `ON DELETE SET NULL`: borrar una siembra no destruye el historial.
- **`reportes_generados`** solo registra metadatos (usuario, siembra, consulta
  y fecha). El PDF se arma al momento y no se almacena.
- **Altitud automatica**: al crear una parcela sin `altitud_msnm`, el backend
  la consulta a Open-Meteo. Si el servicio falla, la parcela se crea con
  `null`; la altitud no bloquea el registro.
- **Tabla de telemetria**: la tabla se llama `lecturas_sensor` para distinguirla
  de `lecturas_climaticas`. La ruta publica sigue siendo
  `/api/v1/telemetria/lecturas`.
