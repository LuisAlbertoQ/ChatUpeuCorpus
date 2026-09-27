# Evaluación de retrieval

- `evaluar_rag.py`: harness offline (Top15 → rerank → Top4) + métricas Hit/Recall/MRR/NDCG.
- `evaluar_rag_v3.py`: variante fijada a `banco_version='v3_curado'`.
- `calibrar_umbral.py`, `diagnostico_banco.py`, `sondeo_top3.py`: calibración y diagnóstico.
- `metricas_EXP_*.csv`, `resultados_calibracion.csv`, `calibracion_resumen.md`: resultados.
- `migrar_esquema_vector_store.py`: [YA EJECUTADO] fix esquema chromadb.

Baselines congelados: `EXP_20260924_222147_7329f6` (v2) y `EXP_20260924_231553_2cd31b` (v3) + reevaluación v3.1. No re-ejecutar sin aprobación.
