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

| Etiqueta | Banco | S1 BM25 | S2 MiniLM | S3 mpnet | S4 bge-m3 |
|---|---|---|---|---|---|
| `OE1_154_chunk350` | 154 preguntas del OE1 (sin revisión humana) | 0.675 | 0.526 | 0.617 | **0.916** |
| `B32_chunk350` | banco v3.2 (30) | 0.367 | 0.333 | 0.467 | **0.667** |

R@5 (artículo correcto entre los 5 primeros). Comparación contra BM25 con Holm sobre las 3 comparaciones:

| Banco | MiniLM − BM25 | mpnet − BM25 | bge-m3 − BM25 |
|---|---|---|---|
| 154 Q OE1 | −0.15 [−0.25, −0.05], p Holm 0.008 (**peor**) | −0.06 [−0.16, 0.04], p 0.23 (n.s.) | **+0.24 [0.16, 0.32], p < 0.001, r = 0.82** |
| 30 Q v3.2 | −0.03, p 0.98 (n.s.) | +0.10, p 0.98 (n.s.) | +0.30 [0.07, 0.53], p Holm 0.06 (n.s. con 30 preguntas) |

- bge-m3 con el banco del OE1 reproduce exactamente la cifra del OE1 (R@5 0.916, MRR 0.756): el
  script usa el mismo índice de producción (sha256 `585eda3b…`).
- **H1 no se cumple para todos los modelos:** solo bge-m3 supera a BM25. mpnet empata y MiniLM es peor.
  Ambos leen solo 128 tokens: con chunks de hasta 350 truncan el 71 % de los chunks (leen el 56 % del
  texto). Es un resultado para H1 y H2.
- Con 30 preguntas la ventaja de bge-m3 no alcanza significancia tras Holm: es justo lo que el .docx
  advierte sobre bancos pequeños; la conclusión sale del gold set.
- MiniLM descargado el 2026-11-22 (revisión `e8f8c211…`, 477 MB, en el volumen `hf_cache`).
- Tamaños de chunk 150/300/600 (H2): el OE1 los permite con `CHUNK_MAX_TOKENS` / `CHUNK_OVERLAP_TOKENS`;
  cada tamaño genera otro CSV de chunks que se pasa con `--chunks` (las etiquetas llevan el tamaño).

### H2: tamaños de chunk (2026-11-22, preliminar)

Chunks generados por el OE1 (`chunks_v3_bgem3_c150o50.csv`, `_c300o50`, `_c600o50`; sha256 verificados contra
sus MANIFEST, producción intacta) y evaluados aquí con `exp_a_recuperacion.py` (embeddings en la caché local,
nunca en la colección de producción). bge-m3 lee el chunk completo en todos los tamaños (max_seq 384, y 664
para los de 600); MiniLM y mpnet se quedan en su límite de 128 tokens. Análisis: `analisis_h2.py --banco OE1_154`
→ `exp_a/h2_<banco>/` (`tabla2.csv`, `figura1.csv`, `comparaciones.csv`).

R@5 con las 154 preguntas del OE1 (350 = producción, solape 40; el resto solape 50):

| Recuperador | 150 | 300 | 350 | 600 | Texto que lee (150 / 300 / 600) |
|---|---|---|---|---|---|
| BM25 | 0.617 | 0.662 | 0.675 | **0.695** | todo |
| MiniLM | 0.519 | 0.513 | 0.526 | 0.513 | 78 % / 58 % / 49 % |
| mpnet | 0.565 | **0.617** | 0.617 | 0.584 | 78 % / 58 % / 49 % |
| bge-m3 | 0.903 | **0.929** | 0.916 | 0.909 | 100 % |

- **Sin evidencia de un tamaño óptimo** para los recuperadores semánticos: bge-m3 y mpnet tienen su máximo en
  300, pero ninguna diferencia entre 150, 300 y 600 es significativa tras Holm.
- **BM25 mejora con chunks más grandes** (600 vs 150: +0.078 [0.026, 0.136], p Holm 0.02): más texto por chunk
  da más coincidencias de palabras.
- Aun con chunks de 150, MiniLM y mpnet truncan el 76 % de los chunks: el breadcrumb (hasta 60 tokens) más
  150 tokens ya supera sus 128. El truncamiento no se elimina achicando el chunk.
- Con el banco v3.2 (30 Q) todo es no significativo. Conclusión oficial: con el gold set.
