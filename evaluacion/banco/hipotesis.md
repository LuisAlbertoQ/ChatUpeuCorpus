# Hipótesis del estudio — Revisión 3 (RAG 100 % local UPeU)

Fuente: `docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx`, § “Hipótesis contrastables”.
RQ principal: sobre el corpus de 48 documentos institucionales en español, ¿cómo afectan
la estrategia de recuperación, el tamaño de fragmentación, el modelo de embeddings y el
modelo generativo local a la recuperación documental, la calidad de las respuestas,
la fidelidad y la atribución verificable?

Regla de reporte (del documento): cada hipótesis debe producir al menos un resultado
específico. No se incorporarán resultados que no estén vinculados con una pregunta
o hipótesis del estudio.

| ID | Hipótesis | Experimento | Resultado que la responde |
|---|---|---|---|
| H1 | Los métodos de recuperación semántica basados en embeddings superan a BM25 en Recall@5 sobre el corpus institucional. | A | Tabla 2: Recall@5 por recuperador |
| H2 | Existe un tamaño de fragmento intermedio entre las configuraciones evaluadas que maximiza el desempeño de recuperación documental. | A | Tabla 2 + Figura 1: Recall@5 vs chunk por recuperador |
| H3 | Los modelos generativos locales evaluados presentan diferencias significativas en calidad de respuesta, fidelidad, atribución y latencia bajo las mismas condiciones. | B | Tabla 3: Qwen2.5-7B vs `llama3.2:3b`, `qwen3:4b` y `gemma3:4b` (Llama 3 8B evaluado y descartado, 2026-11-22) |
| H4 | El desempeño de recuperación varía entre categorías documentales y tiende a disminuir en las categorías con menor representación en el corpus. | A | Tabla 4 + Figura 2: Recall@5 por categoría con IC |
| H5 | El sistema RAG puede abstenerse correctamente ante consultas fuera de dominio y ambiguas, alcanzando una tasa de abstención correcta previamente definida. | C | Tabla 5: abstención correcta, falsa abstención (criterio de éxito H5: abstention_accuracy ≥ 0.90 con IC95%) |

Estado: H1–H5 aprobadas (cronograma 04-09). Criterio H5 propuesto; pendiente de ratificación del equipo/asesor.

## Estado preliminar (2026-11-22)

Resultados con bancos de desarrollo (154 preguntas del OE1 sin revisión humana y banco v3.2 de 30). **No son
los oficiales:** el .docx exige el gold set de 260 (`gold/`), que falta anotar.

| ID | Resultado preliminar | Fuente |
|---|---|---|
| H1 | Solo bge-m3 supera a BM25 en R@5 (0.916 vs 0.675; +0.24 [0.16, 0.32], p Holm < 0.001, r = 0.82). mpnet (0.617) empata y MiniLM (0.526) es peor (p Holm 0.008): ambos leen solo 128 tokens | `../retrieval/exp_a/OE1_154_chunk350/h1_vs_bm25.csv` |
| H2 | Sin tamaño óptimo significativo: bge-m3 0.903 / 0.929 / 0.909 con chunks de 150 / 300 / 600; mpnet también máximo en 300 (n.s.). BM25 mejora con chunks grandes (600 vs 150: +0.078, p Holm 0.02) | `../retrieval/exp_a/h2_OE1_154/` |
| H3 | Qwen2.5-7B supera a Llama 3 8B en completitud (0.53 vs 0.39, p Holm 0.03) y latencia (20 vs 39 s, p < 0.001), sin diferencia en atribución exacta. Llama 3 no cabe en la GPU de 6 GB: 17 % de timeouts y degradación con el uso → **descartado**; se compararán `llama3.2:3b`, `qwen3:4b` y `gemma3:4b`. S0 (sin recuperación): completitud 0.03 | `../generacion/exp_b/` |
| H4 | Sin datos suficientes: requiere el gold set (40 preguntas por categoría) | — |
| H5 | Fuera de dominio 40/40 (IC95 Wilson [0.91, 1.00]) pero con preguntas usadas en la calibración → no válido; ambiguas 14/20 (solo 4 piden aclaración) | `../exp_c/` |
