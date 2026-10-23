# Contexto del proyecto

> **Fuente:** `D:\Materias\ServicioSocial\DocumentacionProyecto\SISTEMA DE RIEGO.pdf`
> (protocolo del proyecto; 17 paginas). Documento anterior: `Avances del proyecto.docx`.
> Ultima lectura: 2026-10-22.
>
> Este archivo resume lo que el codigo necesita saber del documento. No sustituye
> al documento original: cuando haya conflicto, manda el documento, salvo en los
> puntos marcados como *"direccion nueva"*, que surgieron despues.

---

## 1. Objetivo y alcance

Sistema multiplataforma para dar recomendaciones de riego y manejo agricola a
productores de **microparcelas en Tlatlauquitepec, Puebla**.

- **Frontend:** Flutter (aplicacion movil/escritorio).
- **Backend:** Python / FastAPI (este repositorio).
- **Base de datos:** PostgreSQL.
- **Servicios externos:** Open-Meteo (clima) y Google Gemini (redaccion).
- **Escala:** microparcelas, no agricultura extensiva.

El flujo central del documento es: el usuario registra una siembra, el backend
calcula la etapa fenologica, consulta el clima de 7 dias, ensambla el contexto y
genera una recomendacion. La recomendacion se devuelve al frontend y se guarda
en un historial reproducible.

---

## 2. Clima de Tlatlauquitepec

Datos que justifican el diseno del sistema y el catalogo de cultivos:

| Variable | Valor |
|---|---|
| Altitud | 300 a 2 900 msnm; promedio **1 947 msnm** en 3 km alrededor del centro |
| Climas dominantes | Templado humedo con lluvias en verano (34.14 %) y semicálido humedo con lluvias todo el ano (28.23 %) |
| Temperatura media | **16 °C**; oscila entre **6 °C y 24 °C**; rara vez supera 28 °C |
| Mes mas calido | Mayo (maxima promedio 24 °C) |
| Mes mas frio | Enero (minima promedio 6 °C) |
| Heladas | Pueden presentarse en invierno |
| Precipitacion anual | 600 a 4 100 mm segun la zona |
| Temporada de lluvias | **27 de mayo al 16 de octubre** (4.7 meses) |
| Mes mas lluvioso | Septiembre, **237 mm** |
| Mes mas seco | Enero, **21 mm** |
| Luz natural | 11 h en diciembre a poco mas de 13 h en junio |
| Nubosidad | Cielo despejado de fines de octubre a principios de junio (marzo el mas despejado); junio a octubre mayormente nublado, septiembre **82 %** del tiempo |

**Implicacion para el codigo:** el generador sintetico debe usar clima historico
real de estas coordenadas, porque la estacionalidad (lluvias de verano, sequia de
invierno, nubosidad) es lo que le da sentido a las predicciones.

---

## 3. Catalogo de hortalizas

### 3.1 Cuantos cultivos

El documento base vigente es `SISTEMA DE RIEGO.pdf` (protocolo del proyecto). Su
**objetivo general** fija la lista de hortalizas que se van a analizar en las
microparcelas:

> ajo, calabaza, jitomate, rabano, zanahoria, acelga, lechuga, cilantro y chile.

Son **nueve cultivos**. El resumen del PDF repite la misma lista y menciona
aparte **papa, haba y maiz** como cultivos predominantes de la region, pero
aclara que se desarrollan en extensiones mucho mayores y no en microparcelas.
El documento tambien cita **frijol** una sola vez, en una lista secundaria de la
metodologia, sin incluirlo en el objetivo. Por eso no forma parte del catalogo.

**Decision tomada:** el catalogo queda con **9 cultivos**, alineado al objetivo
general del protocolo. El codigo y la base ya estan alineados.

### 3.2 Agrupacion funcional (del documento)

| Grupo | Cultivos | Implicacion |
|---|---|---|
| Fruto | Jitomate, chile, calabaza | Demanda calor y alta radiacion; sensibles a frio y a exceso de humedad |
| Hoja | Lechuga, acelga, cilantro | Toleran nubosidad y sombra parcial; dependen de humedad ambiental |
| Raiz y bulbo | Zanahoria, rabano, ajo | Requieren suelo suelto, profundo y bien drenado |

### 3.3 Parametros por cultivo que el documento exige

Temperaturas minima, maxima e ideal; rango optimo de humedad del suelo;
requerimiento de agua semanal; rango de radiacion solar tolerable; sensibilidad a
heladas, humedad excesiva y viento; rango de altitud; notas de manejo. Todos ya
existen en `Hortaliza`.

### 3.4 Etapas fenologicas

El documento las define como reglas estaticas por rango de dias:
germinacion -> crecimiento vegetativo -> floracion/fructificacion -> cosecha.
Se almacenan en `etapas_hortaliza` y el sistema deduce la etapa sin que el
usuario la indique. Ya implementado en `EtapaHortaliza` + `obtener_etapa_actual`.

---

## 4. Arquitectura descrita

Arquitectura multicapa:

1. **Presentacion:** Flutter.
2. **Aplicacion/negocio:** FastAPI, modular, preparada para conectar
   microcontroladores y aprendizaje automatico "de manera nativa".
3. **Datos:** PostgreSQL (usuarios, catalogo, historial).
4. **Servicios externos:** Open-Meteo y Gemini.

El documento ya anticipa la conexion futura de hardware y ML; no la implementa.

---

## 5. Modelo de datos: documento vs. implementado

| Documento | Implementado | Estado |
|---|---|---|
| `usuarios` | `usuarios` | Igual |
| `microparcelas` | `parcelas` | Renombrado; mismas responsabilidades |
| `hortalizas` | `hortalizas` | Igual |
| `etapas_hortaliza` | `etapas_hortaliza` | Igual |
| `siembras` | `siembras` | Se agrego `fecha_cosecha`, `activa` y validacion de traslape |
| `lecturas_climaticas` | `lecturas_climaticas` | Implementada: JSON completo de Open-Meteo + campos normalizados |
| `consultas_recomendaciones` | `consultas_recomendaciones` | Implementada: historial con prompt y respuesta integra |
| — | `sensores` | **Nuevo** (telemetria de campo) |
| — | `lecturas` | **Nuevo**, renombrado a `lecturas_sensor` |
| — | `reportes_generados` | **Nuevo**: solo metadatos del PDF (no el binario) |

Nota de nomenclatura: `lecturas_sensor` (sensores) y `lecturas_climaticas`
(Open-Meteo) son cosas distintas. La tabla de sensores ya se llama
`lecturas_sensor`; la ruta publica sigue siendo `/api/v1/telemetria/lecturas`.

### 5.1 Requisitos del documento sobre el historial

- `lecturas_climaticas` guarda la **respuesta completa** de Open-Meteo como JSON
  de respaldo, ademas de los campos normalizados. Objetivo: no repetir la
  consulta si manana se necesita otra variable.
- `consultas_recomendaciones` guarda: siembra, registro climatico exacto,
  version de la hortaliza, etapa calculada, dias desde la siembra, **prompt
  completo** y **respuesta JSON integra**, mas los campos legibles.
- El historial es **reproducible**: se puede reconstruir por que se recomendo
  algo en el pasado aunque los datos actuales hayan cambiado.

---

## 6. Requisitos del documento ya implementados

| Requisito | Estado |
|---|---|
| Altitud automatica al registrar parcela | **Hecho** (Open-Meteo; si falla, la parcela se crea con `null`) |
| Persistir `lecturas_climaticas` | **Hecho** (JSON de respaldo + campos normalizados) |
| Persistir `consultas_recomendaciones` | **Hecho** (prompt y respuesta integra) |
| Reporte PDF por siembra | **Hecho** (backend, en memoria; solo metadatos en BD) |
| Historial de consultas (endpoint) | **Hecho** (`/api/v1/ai/historial`, `/api/v1/ai/clima`) |
| Frontend Flutter | Fuera de este repo |

---

## 7. Direccion nueva: el modelo entrenado decide

El documento describe que **Gemini genera la recomendacion** directamente a
partir de reglas agronomicas + clima. La conversacion posterior cambio el papel
de cada pieza:

- **Modelo entrenado (Keras):** decide los numeros (humedad futura, lamina de
  riego, dias al proximo riego, nivel de estres).
- **Gemini:** solo redacta en lenguaje natural la prediccion del modelo. No
  decide.
- **Motivo:** el corazon del sistema debe ser un modelo propio entrenado con
  datos de sensores; Gemini es la capa de presentacion.
- **Datos:** como aun no hay despliegue en campo, se generan datos sinteticos
  fisicamente coherentes (balance hidrico) con clima historico real de
  Open-Meteo. La telemetria guarda todo para reentrenar cuando lleguen los
  sensores reales.

**Implicacion:** el documento debe actualizarse en la seccion "Generacion de
Recomendaciones". El paso 3 deja de ser "enviar todo a Gemini" y pasa a ser
"predecir con el modelo y luego redactar con Gemini".

---

## 8. Discrepancias agronomicas resueltas

Comparacion entre las fichas del documento y `data/catalogo_hortalizas.json`.
Las correcciones claras ya se aplicaron y se recargaron en la base con
`python -m scripts.seed_catalogo`.

| Cultivo | Documento | Catalogo anterior | Decision |
|---|---|---|---|
| Rabano | Cosecha ~45 dias (grandes 70) | 30 dias | **Corregido** a 45 |
| Cilantro | Cosecha 60-90 dias; 350 mm/ciclo | 55 dias; 20 mm/semana | **Corregido** a 75 dias y 30 mm/semana |
| Acelga | Recoleccion ~90 dias | 75 dias | **Corregido** a 90 |
| Zanahoria | Prefiere 9-18 °C | max 28 | **Corregido** a max 24 |
| Jitomate | Max tolerable 35 °C (fuentes discrepan: 30) | max 32 | Sin cambios: el documento duda |
| Chile | Crecimiento se detiene a <=18 °C | min 10 | Sin cambios: 18 parece excesivo para supervivencia |
| Ajo | Humedad 80-85 % del ciclo | 40-70 % volumetrico | **No copiar**: el documento probablemente habla de % de capacidad de campo, no de humedad volumetrica |
| Jitomate | 600 mm/ciclo | 40 mm/semana (~685 mm/ciclo) | Coherente |
| Calabaza | 10-35 °C, optimo 21-29 | 10-35, ideal 24 | Coherente |

Nota: **papa, haba, maiz y frijol** ya no estan en el catalogo porque el
objetivo general del protocolo no los ubica en microparcelas. Sus fichas
tecnicas pueden seguir citadas en el documento como contexto regional, pero el
sistema no las ofrece para siembra.

**Advertencia de unidades:** el documento expresa radiacion en **MJ/m2/dia**
(ej. jitomate 14-16), mientras el catalogo usa **W/m2** instantaneos. No son
intercambiables. Hay que fijar una convencion y documentarla; `weather_client.py`
ya normaliza el pronostico a W/m2.

---

## 9. Decisiones tomadas y pendientes

Decisiones cerradas:

1. **Catalogo:** 9 cultivos, los del objetivo general de `SISTEMA DE RIEGO.pdf`.
2. **Correcciones agronomicas:** aplicadas las cuatro claras que siguen vigentes
   (rabano, cilantro, acelga, zanahoria). Jitomate, chile y ajo se dejan
   como estan por falta de evidencia concluyente. Las correcciones de haba y
   papa quedaron fuera al retirar esos cultivos del catalogo.
3. **Nomenclatura:** `lecturas` paso a `lecturas_sensor`.
4. **Clima persistido:** `lecturas_climaticas` y `consultas_recomendaciones`
   implementadas con migracion `a894f247cdfa`.
5. **Reportes PDF:** los genera el backend con ReportLab, bajo demanda.

Pendiente:

- **Narrativa del documento:** actualizar "Generacion de Recomendaciones" para
  reflejar que el modelo entrenado decide y Gemini redacta.
- **Fase 3:** generar los datos sinteticos (Open-Meteo historico + balance
  hidrico + emulacion de sensores).
- **Fase 4:** entrenar el modelo multi-salida en Keras.
- **Fase 5:** conectar el modelo al endpoint de recomendacion.
