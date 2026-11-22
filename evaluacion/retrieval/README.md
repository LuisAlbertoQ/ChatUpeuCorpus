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

## Experimento A de la Revisión 3 (2026-11-22)

`exp_a_recuperacion.py`: recuperación pura (sin LLM) de BM25 (S1), MiniLM (S2), mpnet (S3) y bge-m3 (S4)
sobre los **mismos** 5,117 chunks del corpus V3 y el mismo texto de entrada (breadcrumb + texto), con
búsqueda exacta. Métricas por pregunta: R@1/3/5/10, MRR@10, nDCG@5 (al nivel artículo si está anotado;
si no, documento) y Rdoc@1/5/10. Escribe en `exp_a/<etiqueta>/`: un CSV por recuperador (entrada de
`../estadistica/estadistica.py`), `resumen.csv` (IC95 bootstrap), `h1_vs_bm25.csv` (Wilcoxon + Holm) y
`meta.json` (versiones, hash de los chunks, % de tokens que cada modelo alcanza a leer).

Se corre en un contenedor temporal con GPU y sin internet (los modelos salen de las cachés locales):

```powershell
$oe1 = "C:\Users\lucho\Documents\Cliclo 9\Investigacion\oe1_arquitectura_corpus"
$eval = "C:\Users\lucho\Documents\Cliclo 9\Investigacion\oe5_chatbot_upeu\evaluacion"
$mp = "models--sentence-transformers--paraphrase-multilingual-mpnet-base-v2"
docker run --rm --gpus all -e HF_HUB_OFFLINE=1 -v "${eval}:/data/evaluacion" `
  -v "${oe1}\corpus_upeu\metadatos\v3:/oe1:ro" -v oe5_chatbot_upeu_hf_cache:/root/.cache/huggingface `
  -v "${oe1}\.hf_cache\hub\${mp}:/root/.cache/huggingface/hub/${mp}:ro" `
  --entrypoint python oe5_chatbot_upeu-backend /data/evaluacion/retrieval/exp_a_recuperacion.py `
  --banco /data/evaluacion/banco/banco_v32.json --chunks /oe1/chunks_v3_bgem3.csv `
  --emb-bgem3 /oe1/embeddings_v3_bgem3.npy --recuperadores bm25,mpnet,bgem3 --etiqueta B32_chunk350
```

Corridas preliminares (bancos de desarrollo, **no** son el resultado oficial; ese sale del gold set):

| Etiqueta | Banco | BM25 R@5 | mpnet R@5 | bge-m3 R@5 | bge-m3 vs BM25 (Holm) |
|---|---|---|---|---|---|
| `OE1_154_chunk350` | 154 preguntas del OE1 (sin revisión humana) | 0.675 | 0.617 | **0.916** | +0.24 [0.16, 0.32], p < 0.001, r = 0.82 |
| `B32_chunk350` | banco v3.2 (30) | 0.367 | 0.467 | **0.667** | +0.30 [0.07, 0.53], p = 0.04, r = 0.60 |

- bge-m3 con el banco del OE1 reproduce exactamente la cifra del OE1 (R@5 0.916, MRR 0.756): el
  script usa el mismo índice de producción (sha256 `585eda3b…`).
- mpnet **no** supera a BM25 (diferencia no significativa): lee solo 128 tokens y con chunks de hasta
  350 tokens trunca el 71 % de los chunks (lee el 56 % del texto). Es un resultado para H1 y H2.
- Falta MiniLM (S2): el modelo no está descargado (requiere ~470 MB de huggingface.co).
- Tamaños de chunk 150/300/600 (H2): el OE1 los permite con `CHUNK_MAX_TOKENS` / `CHUNK_OVERLAP_TOKENS`;
  cada tamaño genera otro CSV de chunks que se pasa con `--chunks` (las etiquetas llevan el tamaño).
