# Changelog Ground Truth — v3 → v3.1

## Congelación v3 histórico
- `v3_original_baseline`: 50 puntos, `banco_preguntas.banco_version='v3_curado'`, `preguntas_comparacion.json` 17 Q.
- Correcciones pre-auditoría (antes de congelación): Q02_P03 (evidencia Art38 elección 5 años), Q03_P03 (texto completo ley/SUNEDU/TUPA), Q04_P02 (carta poder), Q13_P02 (contrato + CTI Vitae), Q14_P03 (docentes por período), Q16_P03 (notifica 3 días). Aplicadas en `banco_preguntas` y snapshots `GEN_20260924_232127_8e01ef`; respuestas/contexto/métricas intactos.
- Desde v3.1: `banco_preguntas` v3 NO se modifica. v3.1 vive en `groundtruth_v31_preguntas` + `groundtruth_v31_puntos`. Snapshots históricos `evaluacion_generacion` conservados para reproducibilidad.

## Adjudicación POSIBLE → definitiva
- Q01 CONFIRMADA (parcial): +1 agrupado 19.4–19.7. Q05 DESCARTADA. Q07 CONFIRMADA: +2 (13.2–13.3, 13.4/13.6/13.7). Q08 CONFIRMADA: +2 (Art45–48 clases, Art49–50 tipos). Q13 CONFIRMADA: +1 (22.5–22.7). Q15 CONFIRMADA: +2 (49.5–49.6, 49.7–49.13). Q17 DESALINEACION_CONFIRMADA: reemplazo a Reglamento de seguimiento de egresados Art12/18.

## Regla de cobertura
Catálogos (`cuáles/qué`) deben representar el catálogo documental; si muchos elementos, agrupar solo con trazabilidad de numerales, sin ocultar importantes. No se reescribió ninguna pregunta.

## Cambios por Q (v3 → v3.1)
Q01 3→4, Q02 3→4 (+Rector Art34), Q03 3→6 (+Art41 ×3), Q07 3→5, Q08 3→5, Q13 3→4, Q14 3→6, Q15 4→6, Q17 2→3 (nuevo documento). Resto idénticos. Total 50→66.

## Multi-artículo
`groundtruth_v31_preguntas.articulos_esperados` JSON con pares documento|artículo (Q02: 34+38+42; Q03: 41+42; Q08: 45+50+55; Q17: Art12+18). Identidad `doc_norm|art_norm`.

## Impacto si se aprueba
Solo evaluación humana/completitud + versión. Retrieval: mismos 255 candidatos EXP_20260924_231553_2cd31b; reevaluación con métricas multi-relevancia (Hit=≥1, Recall=únicos/total, MRR primer relevante, NDCG binario). Generación GEN_20260924_232127_8e01ef intacta; nueva capa humana contra v3.1.
