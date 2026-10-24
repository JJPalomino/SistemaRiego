# Resumen de pruebas de límites lógicos - Fase 3

**Archivo:** `tests/test_limits_fase3.py`  
**Fecha:** 2026-10-24  
**Resultado:** 4/4 passed  
**Suite completa:** 90 passed

## Objetivo
Estresar y validar los límites lógicos identificados en la Fase 3, aprovechando SQLite en memoria y los fixtures existentes.

## Pruebas implementadas

### 1) `test_doble_commit_huerfano_tras_fallo_gemini`
**Escenario:** Simulación de falla de red/transaccional tras guardar la lectura climática.

- **Flujo:** Se mockea `weather_client.obtener_clima` para devolver clima con `json_raw`. Se mockea `llm_client.generar_recomendacion` para lanzar `ErrorLLM` (falla de Gemini).
- **Validación:** Endpoint `POST /api/v1/ai/recomendacion` con `parcela_id` + `id_hortaliza` devuelve **502** (mensaje genérico). 
- **Comportamiento transaccional:** Se verifica que puede quedar registrada `lecturas_climaticas` (primer commit en `_guardar_lectura_climatica`) y **NO** se crea ningún registro en `consultas_recomendaciones` al fallar Gemini antes del segundo commit. Se documenta el comportamiento de **rollback parcial / registro huérfano**.

### 2) `test_sin_parcela_siembra_id_consulta_null_y_pdf_404`
**Escenario:** Petición anónima/sin parcela ni siembra.

- **Flujo:** `POST /api/v1/ai/recomendacion` con solo `id_hortaliza` + `dias_siembra` (sin `parcela_id` ni `siembra_id`).
- **Validación:** Respuesta **200** con `id_consulta: null`. Las tablas `lecturas_climaticas` y `consultas_recomendaciones` permanecen **vacías**.
- **PDF:** `GET /api/v1/reportes/siembras/9999.pdf` devuelve **404** (no existe historial almacenable).

### 3) `test_concurrencia_lenta_delegada_threadpool_no_bloquea_health`
**Escenario:** Sesión abierta ante timeouts externos / concurrencia lenta.

- **Flujo:** Se mockea `weather_client.obtener_clima` con `time.sleep(5)`. Se disparan **3 peticiones concurrentes** con `httpx.AsyncClient` + `ASGITransport`. Mientras se ejecutan, se consulta `/health`.
- **Validación:** `/health` responde **200** en **< 2 segundos**. Las rutas están declaradas con `def`, por lo que FastAPI delega el trabajo bloqueante al **threadpool** y el **event loop principal** no se congela. Las 3 peticiones lentas se atienden correctamente en paralelo.

### 4) `test_saneo_alertas_normaliza_y_guarda_limpio`
**Escenario:** Saneo lógico de alertas y validación con Pydantic.

- **Flujo:** Gemini devuelve alertas malformadas: niveles en mayúsculas (`"ALTA"`), mixtos (`"Precaucion"`), `null`, elementos basura y `nivel_urgencia_max: "CRITICA"`.
- **Validación respuesta:** `nivel_urgencia_max` normalizado a `"critica"`. Todas las alertas en respuesta tienen `nivel` dentro de `{"informativa", "precaucion", "critica"}`.
- **Validación BD:** En `consultas_recomendaciones.respuesta_json` se guarda la **versión ya saneada** (misma normalización). Se confirma consistencia entre respuesta HTTP, validación Pydantic y persistencia.

## Hallazgos documentados
- **Doble commit:** Existe riesgo de registros huérfanos si falla Gemini tras guardar `lecturas_climaticas`. Los tests lo validan y lo dejan documentado.
- **Historial obligatorio:** Solo con parcela/siembra se genera historial reproducible y PDF.
- **Threadpool efectivo:** Las rutas `def` evitan bloqueo del event loop con llamadas síncronas (Open-Meteo/Gemini).
- **Saneo robusto:** El flujo sanea alertas antes de persistir y validar, evitando `ResponseValidationError`.
