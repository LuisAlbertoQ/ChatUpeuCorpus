# Evaluación de retrieval

- `evaluar_rag.py`: harness offline (Top15 → rerank → Top4) + métricas Hit/Recall/MRR/NDCG.
- `evaluar_rag_v3.py`: variante fijada a `banco_version='v3_curado'`. Desde 2026-11-21 toma la colección, el modelo (con revisión) y el boost desde `config` (antes fijos a `corpus_upeu_v2` y 0.07); descripción del experimento con `EVAL_DESCRIPCION`.
- `calibrar_v3_bgem3.py` → `calibracion_v3_bgem3/` (2026-11-21): calibración de umbral, margen, boost y Top-K para bge-m3 con 325 positivas y 42 negativas distintas a las 17 de validación. Resultado: umbral 0.41, margen 0.09, boost 0.02, Top-K 15.
- `evaluar_reranker.py` → `reranker_v3_bgem3.json` (2026-11-21): boost vs `bge-reranker-v2-m3` (con y sin encabezado) sobre los mismos candidatos. Descartado: peor en las 17 Q; ~16 s/consulta en CPU.
- `calibrar_umbral.py`, `diagnostico_banco.py`, `sondeo_top3.py`: calibración y diagnóstico (históricos, mpnet/V2).
- `metricas_EXP_*.csv`, `resultados_calibracion.csv`, `calibracion_resumen.md`: resultados.
- `migrar_esquema_vector_store.py`: [YA EJECUTADO] fix esquema chromadb.

Baselines congelados: `EXP_20260924_222147_7329f6` (v2) y `EXP_20260924_231553_2cd31b` (v3) + reevaluación v3.1. No re-ejecutar sin aprobación.

Experimentos del 2026-11-21/22 (nuevos ID, no pisan los congelados): `EXP_20261122_000124_31a0b8` (V2 de control: idéntico al baseline de septiembre), `EXP_20261122_000747_ca18a6` (V3 sin calibrar) y `EXP_20261122_002703_fa93e2` (V3 calibrado). Ver `../comparacion_v2_v3/COMPARACION_V2_V3.md`.
