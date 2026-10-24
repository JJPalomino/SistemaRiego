# Resumen de pruebas realizadas

**Fecha:** 2026-10-24  
**Proyecto:** Sistema de recomendaciones de riego (microparcelas Tlatlauquitepec, Puebla)  
**Rama:** main  
**Repositorio:** https://github.com/JJPalomino/SistemaRiego.git

## 1) Pruebas automatizadas con pytest

Se ejecutaron las pruebas enfocadas al asesor IA e historial, y posteriormente la suite completa para asegurar que los cambios no rompieran funcionalidades existentes.

| Comando | Resultado | Notas |
|---|---|---|
| `pytest tests/test_ai_advisor.py tests/test_history_reports.py -p no:warnings -v` | **19 passed** | Cubren el flujo de recomendación, historial, generación de PDF y las correcciones aplicadas (unidades normalizadas, truncado por tokens, saneo de alertas). |
| `pytest -p no:warnings -q` | **86 passed** | Suite completa sin fallos. Incluye `auth`, `crops/catalog`, `parcels/siembras`, `telemetry`, `ai_advisor`, `history/reports`. |

## 2) Verificaciones manuales

| Verificación | Resultado | Detalle |
|---|---|---|
| **Estado de la BD** | OK | `usuarios: 1`, `parcelas: 0`, `siembras: 0`, `hortalizas: 9` (únicamente las 9 del objetivo general de `SISTEMA DE RIEGO.pdf`). |
| **Catálogo agronómico** | OK | `data/catalogo_hortalizas.json` con **9 hortalizas / 32 etapas**. Carga idempotente con `scripts/seed_catalogo.py`. |
| **Flujo de recomendación** | OK | Revisado `app/modules/ai_advisor/services.py`, `router.py`, `llm_client.py` y `weather_client.py`. Con `siembra_id` se guarda historial (`lecturas_climaticas` y `consultas_recomendaciones`). Con solo `id_hortaliza + dias_siembra` no se genera `id_consulta`. |
| **PDF e historial** | OK | Comprobado `app/modules/reports/router.py` y `app/modules/reports/services.py`. PDF generado bajo demanda con ReportLab, registrado en `reportes_generados`. Historial reproducible con `prompt` y `respuesta_json`. |
| **Seguridad / manejo de errores** | OK | Se corrigió la exposición de `GEMINI_API_KEY`. Las alertas se normalizan antes de validar con Pydantic. Los endpoints con trabajo bloqueante usan `def` (threadpool) para evitar congelar el event loop. |

## 3) Correcciones validadas

| Corrección | Estado | Descripción |
|---|---|---|
| **Event loop / PDFs** | OK | `reports/router.py` usa `def`. `reportlab` se ejecuta en threadpool. |
| **Event loop / AI Advisor** | OK | Rutas en `ai_advisor/router.py` usan `def`. `httpx.Client` síncrono delegado al threadpool. |
| **Fuga de API Key** | OK | Eliminada exposición de URL con `?key=`. Errores de Gemini/Open-Meteo devuelven mensajes genéricos. |
| **Reintentos Gemini** | OK | Backoff con jitter para 429/500/502/503/504. `responseMimeType` en `generationConfig`. |
| **Saneo de alertas** | OK | `_sanear_alertas` normaliza `nivel` con `_normalizar_urgencia`. Respuesta guardada ya saneada en BD. |
| **Demo sin mutación** | OK | `copy.deepcopy` de `RESPUESTA_DEMO`. Typos corregidos. Modelo actualizado a `gemini-2.5-flash`. |
| **Extracción JSON segura** | OK | Protección del segundo `json.loads` ante JSON malformado. |

## 4) Herramientas utilizadas

| Herramienta | Uso |
|---|---|
| **Python 3.13.1 + venv** | Entorno de ejecución del backend. |
| **pytest / pytest-cov** | Ejecución y validation de pruebas. |
| **FastAPI TestClient** | App levantada en memoria para pruebas. |
| **SQLite en memoria** | Base de datos aislada para pruebas. |
| **pytest monkeypatch** | Mockeo de `weather_client.obtener_clima` y `llm_client.generar_recomendacion`. |
| **httpx (simulado)** | Captura de parámetros para validar prompt/generationConfig. |
| **PostgreSQL** | Verificación del estado real de la BD de desarrollo. |
| **PowerShell** | Ejecución de comandos en Windows. |
| **Git 2.55.0 + GitHub** | Control de versiones y push a `SistemaRiego.git`. |
| **VS Code** | Edición y terminal integrada. |

**Nota:** Las pruebas están completamente mockeadas para llamadas externas. No se consumieron tokens de Gemini ni se realizaron peticiones reales a Open-Meteo durante la ejecución de `pytest`.
