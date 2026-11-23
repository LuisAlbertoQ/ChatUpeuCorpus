# Evaluación de madurez del chatbot UPeU

Esta carpeta implementa la **evaluación automática de madurez** del
chatbot (OE8) según el modelo **CMMI--TRL adaptado** descrito en el
PPI. A partir de esta versión, el sistema **se conecta directamente
a `registro_interacciones.db`**; no utiliza puntajes manuales en CSV.

## Modelo de madurez

Seis dimensiones evaluadas en escala Likert 1--5:

1. **Funcional** — capacidad de responder consultas frecuentes.
2. **Recuperación documental** — uso del corpus institucional.
3. **Explicabilidad y trazabilidad** — presencia y claridad de fuentes.
4. **Usabilidad** — tiempo de respuesta, fluidez.
5. **Gobernanza y uso responsable** — delimitación de dominio, datos.
6. **Preparación tecnológica y mejora** — estabilidad, métricas, mejora.

Cuatro niveles posibles: **Inicial**, **Básico**, **Gestionado**,
**Optimizado**.

## Fuentes de datos

Toda la información proviene de `registro_interacciones.db` (SQLite):

| Tabla | Origen | Uso |
|---|---|---|
| `interacciones` | Log automático del chatbot (cada consulta) | Métricas base: % M02, % M06, tiempo, fuentes |
| `banco_preguntas` | Banco canónico de preguntas de prueba | Validar cobertura del banco |
| `evaluacion_piloto` | Puntajes Likert 1--5 de usuarios reales | Combinar con métricas automáticas |
| `evaluacion_automatica` | Snapshots históricos de madurez | Tendencia en el tiempo |

## Cálculo del puntaje final

Cada dimensión combina dos fuentes con pesos fijos:

```
P_final = 0.6 × P_automático + 0.4 × P_piloto
```

Si no hay datos de piloto, se usa solo el automático
(`P_final = P_automático`).

### Mapeo de métricas a puntajes automáticos

| Dimensión | Métrica base | Regla de mapeo a 1--5 |
|---|---|---|
| Funcional | % M02 | ≥90→5, ≥75→4, ≥50→3, ≥25→2, <25→1 |
| Recuperación documental | % con fuentes | ≥90→5, ≥75→4, ≥50→3, ≥25→2 |
| Explicabilidad | % con fuentes | ≥95→5, ≥80→4, ≥60→3, ≥40→2 |
| Usabilidad | Tiempo promedio (s) | ≤10→5, ≤20→4, ≤30→3, ≤40→2 |
| Gobernanza | % M03 + M05 | 5--30%→5 (detecta bien), <5%→3, >30%→2 |
| Preparación | 1 -- % M06 | ≥98%→5, ≥95%→4, ≥90%→3, ≥80%→2 |

## Regla de consistencia

El nivel global **no puede superar en más de un nivel** al valor
mínimo de las cinco dimensiones críticas: Funcional, Recuperación
documental, Explicabilidad y trazabilidad, Gobernanza, Preparación
tecnológica.

## Evaluación del 2026-11-21/22: corpus V3, calibración, mejoras y banco v3.2

El chatbot migró al corpus V3 del OE1 (`corpus_upeu_v3_bgem3`, bge-m3) y se evaluaron, una por una y con
2 semillas del LLM, la calibración de umbrales y las mejoras del chatbot. Todo está en
[`comparacion_v2_v3/COMPARACION_V2_V3.md`](comparacion_v2_v3/COMPARACION_V2_V3.md):

| Sección | Contenido |
|---|---|
| §1–4 | V2 (mpnet) vs V3 (bge-m3) con las mismas variables |
| §5 | Calibración para bge-m3: umbral 0.41, margen 0.09, boost 0.02 |
| §6 | Mejoras: contexto completo (activa), re-ranker (descartado), contexto por artículo (apagada), abstención disfrazada (activa) |
| §7 | TOP_K_FINAL 4/6/8 (se queda 4) y prompt v3-completo |
| §8 | Auditoría del banco de 17 preguntas |
| §9 | Banco técnico v3.2 (30 preguntas) y nueva línea base |
| §10 | Decisión: prompt v3-completo vigente (completitud 0.40 → 0.57) |

Herramientas nuevas: `comparacion_v2_v3/correr_17q_e2e.py` (banco end-to-end contra `/consulta`, acepta
`--banco-json`), `ablacion.ps1` (corre con un conjunto de variables y verifica que lleguen al contenedor),
`completitud_auto.py` (completitud automática validada contra el juicio humano, kappa 0.53),
`retrieval/calibrar_v3_bgem3.py`, `retrieval/evaluar_reranker.py`, `banco/construir_banco_v32.py` y
`banco/auditar_banco_17q.py`.

## Revisión 3 (.docx): avance del 2026-11-22

> Resumen de fase, resultados y decisiones: **[`ESTADO_REVISION_3.md`](ESTADO_REVISION_3.md)**. Qué entregar a los evaluadores: **[`ENTREGA_EVALUADORES.md`](ENTREGA_EVALUADORES.md)**.

Auditoría del .docx contra el sistema: hipótesis, corpus y pool de 260 ya estaban; faltaban la estadística,
S0/S1/S2, el experimento A sobre el corpus V3, el C completo, la anotación del gold set y las tablas.
Hecho el 2026-11-22 (todo con la configuración congelada en `REPRODUCIBILIDAD.md`, commit `c47d455a`):

| Pieza | Dónde | Estado |
|---|---|---|
| Ficha de reproducibilidad (§10) | `REPRODUCIBILIDAD.md` | lista |
| Estadística (§9): bootstrap, Wilson, Wilcoxon, Holm, efecto | `estadistica/estadistica.py` | lista, 18 tests (incluye κ de Cohen) |
| S0 sin recuperación | `RAG_SIN_RECUPERACION=1` (backend) | lista, 6 tests; falta correrla |
| Exp. B generación + S0 | `generacion/exp_b_generacion.py`, `generacion/exp_b/` | preliminar (banco v3.2): Qwen > Llama 3 8B en completitud y latencia; **Llama 3 8B descartado** (no cabe en la GPU, 17 % timeouts); modelos nuevos en `generacion/exp_b_nuevos/`: Modelos nuevos (2 semillas, 2026-11-23): completitud `qwen3:4b-instruct` 0.63, `gemma3:4b` 0.58, `llama3.2:3b` 0.51 vs Qwen2.5-7B 0.53, ninguna diferencia significativa con Holm; los tres más rápidos (p50 7 / 22 / 17 s vs 20 s; p95 18 / 26 / 34 s vs 58 s), 0 timeouts, 12/12 negativas; S0 completitud 0.03 |
| Exp. A recuperación (S1 BM25, S2 MiniLM, S3 mpnet, S4 bge-m3) | `retrieval/exp_a_recuperacion.py`, `retrieval/exp_a/` | preliminar con bancos de desarrollo: 4 recuperadores × 4 tamaños de chunk (150/300/350/600, chunks del OE1); H2 en `retrieval/analisis_h2.py` |
| Exp. C abstención | `exp_c/` | preliminar: 40/40 fuera de dominio (vistas en desarrollo), 14/20 ambiguas |
| Gold set 260: fichas, κ y consolidación | `banco/gold/` | **herramientas listas** (fichas Excel ciegas para A y B, plantilla de 40 fuera de dominio nuevas, κ, conflictos para el juez, consolidación); **pendiente: que el equipo anote** |

## Estructura (reorganizada 2026-09-27; actualizada 2026-11-22)

| Carpeta | Contenido |
|---|---|
| `banco/` | **`banco_v32.json` (30 Q + 6 negativas, vigente)** y `construir_banco_v32.py`; auditoría del banco de 17 Q; v3.1 congelada (`preguntas_comparacion.json`, `CHANGELOG_GROUNDTRUTH_V31.md`); pool Gold Set 260 (`cuotas_pool_260.json`, `draft/`, `generar_pool_260.py`); `banco_oe1_162.csv` (calibración) |
| `retrieval/` | `evaluar_rag_v3.py` (colección desde config), `calibrar_v3_bgem3.py` + `calibracion_v3_bgem3/`, `evaluar_reranker.py` + `reranker_v3_bgem3.json`; **`exp_a_recuperacion.py` + `exp_a/` (Exp. A Revisión 3)**; históricos `evaluar_rag.py`, `calibrar_umbral.py`, `diagnostico_banco.py`, `sondeo_top3.py`; métricas `EXP_*.csv` |
| `comparacion_v2_v3/` | `COMPARACION_V2_V3.md` (informe 2026-11-21/22), `correr_17q_e2e.py`, `ablacion.ps1`, `completitud_auto.py`, corridas `E2E_*.json/.csv` |
| `ESTADO_REVISION_3.md` | Resumen de la fase actual: qué se hizo, resultados, decisión sobre Llama 3, modelo del chatbot y próximos pasos |
| `ENTREGA_EVALUADORES.md` | Qué archivos recibe y devuelve cada evaluador: ronda 1 (gold set) y ronda 2 (fidelidad) |
| `REPRODUCIBILIDAD.md` | Configuración congelada (commit `c47d455a`) y cambios posteriores |
| `estadistica/` | `estadistica.py`: IC95 bootstrap, Wilson, Wilcoxon, Holm y tamaño de efecto (Revisión 3 §9) |
| `exp_c/` | Experimento C (abstención): `exp_c_abstencion.py`, `resumen_exp_c.csv`, `detalle_exp_c.csv` |
| `generacion/` | `baseline_generacion_v3_oficial.py`, harnesses, JSON/CSV de experimentos |
| `humana/` | Fichas Q01-Q17 (`fichas_humanas_v31/`, 66 puntos), `importar_ficha_humana.py`, `calcular_metricas_humanas.py`, guía |
| `madurez_oe8/` | `calcular_madurez.py`, instrumento piloto 30 ítems, `importar_piloto.py`, reportes |
| `legacy/` | Scripts/resultados históricos (`evaluar_modelo.ps1`, comparativas Qwen) |

## Archivos principales

| Archivo | Descripción | Origen |
|---|---|---|
| `madurez_oe8/INSTRUMENTOS.md` | 5 instrumentos del OE6 (ficha, cotejo, gobernanza, rúbrica, SUS) | Manual |
| `madurez_oe8/calcular_madurez.py` | Lee DB, calcula puntajes, genera reportes. Umbrales en `UMBRALES_OE8`; modo `--auto-only`. | Script |
| `legacy/generar_ficha.py` | Genera `ficha_documental.md` desde DB + ChromaDB. | Script |
| `retrieval/calibrar_umbral.py` | Grid search umbral × top_k sobre el banco (evidencia del 0.40). | Script |
| `retrieval/diagnostico_banco.py` / `sondeo_top3.py` | Diagnóstico por pregunta y sondeo de retrieval. | Script |
| `banco/preguntas_comparacion.json` | Banco v2: 17 preguntas con documento/artículo esperado. | Manual |
| `banco/CHANGELOG_GROUNDTRUTH_V31.md` | Trazabilidad v3 → v3.1 (66 puntos) + banco negativo N01-N06. | Manual |
| `legacy/evaluar_modelo.ps1` | Corre el banco end-to-end contra `/consulta` en vivo → JSON. | Script |
| `banco/migrar_banco.py` | [YA EJECUTADO] One-shot: importa `banco_preguntas.csv` a la DB. | Script (idempotente) |
| `retrieval/migrar_esquema_vector_store.py` | [YA EJECUTADO] One-shot: añade columnas `topic` si el vector store fue migrado a chromadb 1.x. | Script (idempotente) |
| `humana/GUIA_EVALUACION_HUMANA_V3.md` | Guía del evaluador + reglas de completitud/faithfulness/citas. | Manual |
| `madurez_oe8/PROCEDIMIENTO_PILOTO.md` | Procedimiento de campo del piloto OE8. | Manual |
| `legacy/ficha_documental.md` | Deliverable (corpus indexado). Se regenera con `generar_ficha.py`. | Auto-generado |
| `madurez_oe8/reporte_madurez.md` | Deliverable. Se regenera con `calcular_madurez.py`. | Auto-generado |
| `madurez_oe8/resultados_madurez.csv` | Deliverable. Se regenera con `calcular_madurez.py`. | Auto-generado |

## Gold Set 260 (OE8, en construcción)

> **Actualización 2026-11-22:** el pool se generó y verificó contra el corpus V2; hay que repetir `--check`
> contra `corpus_upeu_v3_bgem3`. Las 23 semillas curadas deberían reemplazarse por las del banco v3.2
> (Q05, Q16 y Q17 corregidas, categorías actualizadas). Ver `banco/README.md`.

El pool de 260 preguntas (200 dominio + 40 fuera de dominio + 20 ambiguas) se
genera con `banco/generar_pool_260.py` a partir de tres insumos: las cuotas por
documento (`banco/cuotas_pool_260.json`), los borradores de preguntas
(`banco/draft/draft_*.json`) y las semillas curadas de la DB (17 dominio de
`groundtruth_v31_preguntas` + 6 fuera de dominio de `banco_no_answer`).

| Capa | Archivo | Para quién | Contenido |
|---|---|---|---|
| 0 | `banco/pool_260_verificacion.json` | Investigador | Borrador completo: bloque, documento/artículo candidato, puntos candidatos (`CANDIDATO_NO_VALIDADO`) y semillas curadas |
| 1 | `banco/pool_260_preliminar.jsonl` / `.csv` | Anotadores | **Ciego**: solo `pregunta_id` y `texto`, en orden mezclado (semilla fija) |
| 2 | `banco/banco_gold_260.json` | Resultado | Consolidado tras doble anotación y consenso (pendiente) |

Regenerar y validar (dentro del contenedor):

```bash
docker compose exec backend python /data/evaluacion/banco/generar_pool_260.py --check
docker compose exec backend python /data/evaluacion/banco/generar_pool_260.py --guardar
```

`--check` valida cuotas, semillas, existencia de cada artículo en ChromaDB y
duplicados exactos; `--guardar` escribe las cuatro salidas (capa 0, capa 1 ×2 y
`banco/pool_260_resumen.md`). Los IDs `GOLD_NNN` se asignan **después** de
mezclar los bloques, para que el orden del pool ciego no revele el tipo.

> Los puntos candidatos de las preguntas nuevas **no son ground truth**: se
> extraen del texto real del artículo o, en documentos sin articulado, por
> solapamiento léxico con la pregunta. Los anotadores los verifican leyendo el
> documento.

## Flujo de trabajo

> **Importante:** este proyecto es **100% Docker**. Los scripts de
> evaluación que necesitan `chromadb` (`generar_ficha.py`) deben
> ejecutarse **dentro del contenedor backend**, no en el host.
> Los que solo usan `sqlite3` (`migrar_banco.py`,
> `calcular_madurez.py`) pueden correr en el host.

### 1. Inicialización (una sola vez)

Asegurarse de que las tablas existen en la DB. El backend las crea
automáticamente al arrancar, pero también pueden crearse manualmente:

```bash
docker compose restart backend
```

### 2. Migrar el banco de preguntas (ya ejecutado)

**Nota: este paso ya se ejecutó en junio 2026.** Si reinstalas el sistema
desde cero y tienes el CSV original, puedes migrarlo así:

```bash
cd evaluacion/banco
python migrar_banco.py
```

Esto inserta las preguntas en la tabla `banco_preguntas` de la DB.
Tras verificar la migración, `banco_preguntas.csv` puede eliminarse.

### 3. Cargar puntajes del piloto (cuando aplique)

Los puntajes Likert 1-5 de usuarios reales se insertan directamente
en `evaluacion_piloto`. Puede hacerse desde un formulario web, una
encuesta exportada a CSV, o directamente con SQL:

```sql
INSERT INTO evaluacion_piloto
(sesion_id, pregunta_id, timestamp_inicio, funcional, recuperacion,
 explicabilidad, usabilidad, gobernanza, preparacion, observacion)
VALUES
('anonimizado', 'P01', '2026-06-02T10:00:00', 5, 5, 4, 4, 5, 4,
 'Respuesta clara y con fuente');
```

### 4. Generar la ficha documental (dentro del contenedor)

```bash
docker compose run --rm backend python /data/evaluacion/legacy/generar_ficha.py
```

El script escribe `evaluacion/legacy/ficha_documental.md` en el host
(el volumen `./evaluacion:/data/evaluacion` propaga los cambios).

### 5. Calcular la madurez (host o contenedor)

En el host:

```bash
cd evaluacion/madurez_oe8
python calcular_madurez.py --auto-only   # solo métricas automáticas (FASE 5)
```

O dentro del contenedor:

```bash
docker compose run --rm backend python /data/evaluacion/madurez_oe8/calcular_madurez.py --auto-only
```

El script:

1. Lee `interacciones` y calcula métricas crudas.
2. Convierte métricas a puntajes 1--5 por dimensión.
3. Si hay datos de `evaluacion_piloto`, los promedia y combina
   (60% auto + 40% piloto).
4. Aplica la regla de consistencia (cap por dimensión crítica).
5. Guarda snapshot en `evaluacion_automatica`.
6. Genera `reporte_madurez.md` y `resultados_madurez.csv`.

## Salidas

### `reporte_madurez.md`

Reporte ejecutivo con:
- Resumen (interacciones, piloto, puntaje global, nivel)
- Métricas crudas (% M02, % M06, tiempo, fuentes)
- Tabla de puntajes por dimensión (auto, piloto, final, nivel)
- Cobertura por categoría del corpus A–E (qué categorías concentran
  más M04 = dónde falta o es débil el corpus; atribución por primera
  fuente citada, solo interacciones que llevan fuentes)
- Interpretación automática
- Regla de consistencia aplicada

### `resultados_madurez.csv`

Tabla plana con puntajes por dimensión y resumen global.
Apto para importar a Excel o alimentar análisis estadístico.

### Tabla `evaluacion_automatica`

Un INSERT por ejecución con `periodo = 'YYYY-MM'`. Permite ver
tendencia histórica:

```sql
SELECT periodo, total_interacciones, puntaje_global_calculado
FROM evaluacion_automatica
ORDER BY periodo;
```

## Escala usada

Cada criterio se evalúa de 1 a 5:

- 1 = Muy deficiente
- 2 = Deficiente
- 3 = Regular
- 4 = Bueno
- 5 = Muy bueno

## Niveles de madurez (rangos)

| Rango | Nivel | Interpretación |
|---|---|---|
| 1.00--2.00 | Inicial | Desarrollo incipiente, funcionamiento parcial. |
| 2.01--3.00 | Básico | Avances funcionales, limitaciones en cobertura. |
| 3.01--4.00 | Gestionado | Respuestas sustentadas, mecanismos de control. |
| 4.01--5.00 | Optimizado | Explicabilidad verificable, monitoreo, mejora continua. |

## Nota metodológica

El script no reemplaza el juicio metodológico ni el piloto. Solo
sistematiza los resultados de los instrumentos y ayuda a calcular
el nivel de madurez de manera reproducible, basándose en datos
reales de uso del chatbot.
