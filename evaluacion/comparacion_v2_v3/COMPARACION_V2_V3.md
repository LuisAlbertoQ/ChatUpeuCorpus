# Comparación V2 (mpnet) vs V3 (bge-m3) — banco técnico 17 Q

**Fecha:** 2026-11-21 · **Objetivo:** medir el efecto de cambiar **solo la base vectorial y el modelo de
embeddings** (corpus V3 del OE1), con todas las demás variables del chatbot iguales.

## Condiciones (iguales en ambas corridas)

| Variable | Valor |
|---|---|
| LLM | `qwen2.5:7b`, temperatura 0.2, `num_predict` 1024, prompt `v2-adaptativo` |
| Umbral / margen fuera de dominio | 0.40 / 0.10 (**sin recalibrar para bge-m3**) |
| TOP_K raw / final | 15 / 4 · re-ranking por keyword (boost 0.07) |
| Recorte de contexto / respuesta | 700 caracteres por fragmento / 500 palabras |
| Banco | `banco_preguntas` `v3_curado` (17 Q), ground truth `documento | artículo` |
| Entorno | mismos contenedores, misma sesión, corridas consecutivas |

| | V2 | V3 |
|---|---|---|
| Colección | `corpus_upeu_v2` (5,126 chunks) | `corpus_upeu_v3_bgem3` (5,117 chunks) |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` (768) | `BAAI/bge-m3` rev. `5617a9f6…` (1024) |
| Retrieval (offline) | `EXP_20261122_000124_31a0b8` | `EXP_20261122_000747_ca18a6` |
| End-to-end (`/consulta`) | `E2E_V2_20261122_000148` | `E2E_V3_20261122_000804` |

Control: el retrieval V2 de hoy reproduce **exactamente** las métricas del baseline congelado
`EXP_20260924_231553_2cd31b` (mismo corpus y código).

## 1. Recuperación (offline, Top-15 + re-ranking)

| Métrica | V2 | V3 | Δ |
|---|---|---|---|
| Documento Hit@5 | 0.882 | **0.941** | +0.06 |
| Documento Hit@10 | 0.941 | **1.000** | +0.06 |
| Documento MRR@10 | 0.662 | **0.683** | +0.02 |
| Documento en Top-4 final | 0.706 | **0.765** | +0.06 |
| Artículo Hit@5 | **0.533** | 0.467 | −0.07 |
| Artículo Hit@10 | 0.533 | **0.733** | +0.20 |
| Artículo Hit@15 | 0.533 | **0.800** | +0.27 |
| Artículo MRR@5 | **0.336** | 0.261 | −0.08 |
| Artículo en Top-4 final | 0.400 | **0.467** | +0.07 |

Lectura: bge-m3 **encuentra más** (el artículo correcto aparece en el Top-15 en 12/15 frente a 8/15),
pero lo deja **más abajo** en el ranking. El re-ranking actual (boost por nombre de documento) no
lo sube; un re-ranker real (`bge-reranker-v2-m3`) es la mejora indicada.

## 2. End-to-end (chatbot real)

| Resultado | V2 | V3 |
|---|---|---|
| M02 (respondió) | 13 | 16 (15 reales, ver Q17) |
| M04 (sin información) | 4 | 1 |
| Artículo correcto entre los chunks del LLM | 6/15 | **7/15** |
| Documento correcto entre los chunks del LLM | 12/17 | **13/17** |
| Respondió con el documento correcto (OK_ARTICULO + OK_DOCUMENTO) | 12 | **13** |
| Respondió con otro documento | 1 | 3 |
| Algún fragmento recortado a 700 chars | 15/17 | 16/17 |
| Tiempo medio | 9.5 s | 10.0 s |

### Por pregunta

| Q | V2 | V3 | Cambio |
|---|---|---|---|
| Q01 | OK_DOCUMENTO | OK_DOCUMENTO | = |
| Q02 | OK_DOCUMENTO | OTRO_DOCUMENTO | ▼ responde desde el Reglamento del Comité Electoral (contenido plausible, no es el Estatuto Art. 42°) |
| Q03 | OK_ARTICULO | OK_ARTICULO | = |
| Q04 | M04 (doc. equivocado, se abstuvo) | OTRO_DOCUMENTO | ▼ **responde mal**: usa filas del TUPA sobre traslado de posgrado |
| Q05 | OK_DOCUMENTO | OK_DOCUMENTO | = |
| Q06 | OK_ARTICULO | OK_ARTICULO | = |
| Q07 | OK_DOCUMENTO | OK_ARTICULO | ▲ |
| Q08 | OK_ARTICULO | OK_ARTICULO | = |
| Q09 | M04 (doc. equivocado) | OK_DOCUMENTO | ▲ ahora encuentra la Política de trabajo digno |
| Q10 | OK_DOCUMENTO | OK_DOCUMENTO | = |
| Q11 | M04 (doc. equivocado) | M04 (doc. equivocado) | = el TUPA no sube para "constancia de estudios" |
| Q12 | OTRO_DOCUMENTO | OK_ARTICULO | ▲ |
| Q13 | OK_DOCUMENTO | OK_DOCUMENTO | = |
| Q14 | OK_ARTICULO | OK_ARTICULO | = |
| Q15 | OK_ARTICULO | OK_DOCUMENTO | ▼ leve (documento correcto, otro artículo) |
| Q16 | OK_ARTICULO | OK_ARTICULO | = |
| Q17 | M04 (doc. equivocado) | M02 aparente | = en V3 el LLM dice "el corpus no contiene información…": es una abstención que el filtro (<30 chars) no detecta |

**Balance:** 3 mejoras (Q07, Q09, Q12), 3 empeoramientos (Q02, Q04, Q15), 1 abstención mal etiquetada (Q17).

En la V2, las 4 M04 no eran fallos del LLM: la recuperación traía otro documento y el LLM se
abstenía correctamente.

## 3. Hallazgos

1. **El umbral 0.40 no sirve para bge-m3.** Las distancias del Top-1 pasan de 0.08–0.39 (V2) a
   0.14–0.36 (V3), con los 4 chunks finales casi pegados (p. ej. Q02: 0.305/0.306/0.306/0.346).
   Con 0.40 pasa casi todo y el umbral deja de filtrar: Q04 respondió con chunks irrelevantes a 0.25.
   El margen fuera de dominio (0.40 + 0.10) tampoco está calibrado → hay que recalibrar con el
   banco negativo antes de dar la V3 por buena (riesgo para H5).
2. **El recorte de 700 caracteres pesa más en V3**: los chunks V3 son artículos completos, así que
   16/17 respuestas se generan con algún fragmento mutilado (inicio + "[…]" + final).
3. **El ranking es el cuello de botella**, no la cobertura: el artículo correcto está en el Top-15
   en 80 % de los casos, pero solo en el Top-4 en 47 %.
4. **Abstenciones disfrazadas de M02** (Q17): el post-proceso solo convierte a M04 si la respuesta
   queda < 30 caracteres.
5. Latencia prácticamente igual (+0.5 s); bge-m3 corre en CPU en el backend sin problema.

## 4. Conclusión

Con las mismas variables, la V3 recupera mejor (documento Hit@10 = 1.0, artículo Hit@15 0.53 → 0.80)
y responde con el documento correcto en 13 vs 12 preguntas, pero **todavía no es claramente mejor
de punta a punta**, porque el umbral y el ranking siguen calibrados para mpnet. Las mejoras previstas
(recalibrar umbral, re-ranker, quitar el recorte de 700, contexto por artículo) atacan justamente
los fallos observados y ahora tienen una línea base medida contra la cual compararse.

## Archivos

- `correr_17q_e2e.py` — corre las 17 Q contra `/consulta` y clasifica cada resultado.
- `E2E_V2_20261122_000148.{json,csv}`, `E2E_V3_20261122_000804.{json,csv}` — resultados completos (respuestas incluidas).
- `../retrieval/metricas_EXP_20261122_000124_31a0b8.csv` (V2), `../retrieval/metricas_EXP_20261122_000747_ca18a6.csv` (V3).
- Rollback a V2: renombrar `vector_store_backup_v2_20261121` → `vector_store` y en `docker-compose.yml`
  `CORPUS_VERSION=corpus_upeu_v2`, `EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2`, `EMBEDDING_REVISION=""`.
