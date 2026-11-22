# Ficha de reproducibilidad — Revisión 3 (§10)

Fecha de la ficha: **2026-11-22**. Esta es la configuración **congelada** para los experimentos A, B y C
del .docx (`docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx`). Cualquier cambio posterior al pipeline
se registra en la sección "Cambios después de congelar" con fecha y motivo.

## Código

| Elemento | Valor |
|---|---|
| Commit congelado | `c47d455a` ("Adopta corpus V3 y prompt completo"), rama `main` |
| Recomendación | crear un tag, por ejemplo `git tag rev3-congelado c47d455a` |

## Corpus

| Elemento | Valor |
|---|---|
| Documentos | 48 reglamentos/políticas institucionales UPeU |
| Versión | V3 (OE1), construida 2026-11-20/21; **fecha de corte del corpus: 2026-11-21** |
| Colección | `corpus_upeu_v3_bgem3`, 5,117 chunks, en `vector_store/` |
| Chunking | estructural por artículo, máx. 350 tokens, solape 40 (OE1 `CHUNK_MODE=articulo`) |
| Respaldo V2 | `vector_store_backup_v2_20261121/` (5,126 chunks, mpnet) |
| BM25 | `oe1_arquitectura_corpus/corpus_upeu/metadatos/v3/bm25_corpus_v3.json` |

## Modelos

| Rol | Modelo | Versión fijada |
|---|---|---|
| Embeddings (S4, vigente) | `BAAI/bge-m3`, 1024 dim | revisión `5617a9f61b028005a4858fdac845db406aefb181` |
| Embeddings (S3) | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, 768 dim | revisión `4328cf26390c98c5e3c738b4460a05b95f4911f5` |
| Embeddings (S2) | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dim | revisión registrada por `exp_a_recuperacion.py` en cada corrida |
| Generador (S0–S4, S6) | Ollama `qwen2.5:7b` | ID `845dbda0ea48` (Q4_K_M, 4.7 GB) |
| Generador (S5) | Ollama `llama3:latest` (Llama 3 8B Instruct) | ID `365c0bd3c000` (4.7 GB) |

## Parámetros del pipeline (variables de entorno en `docker-compose.yml`)

| Variable | Valor |
|---|---|
| `RAG_DISTANCE_THRESHOLD` | 0.41 |
| `RAG_MARGEN_FUERA_DOMINIO` | 0.09 (corte fuera de dominio 0.50) |
| `RAG_KEYWORD_BOOST` | 0.02 |
| `RAG_TOP_K_RAW` / `RAG_TOP_K_FINAL` | 15 / 4 |
| `RAG_CONTEXT_MAX_CHARS` | 9000 |
| `RAG_CONTEXTO_ARTICULO` | 0 (apagado) |
| `RAG_RECORTE_LEGACY_700` | 0 |
| `RAG_SIN_RECUPERACION` | 0 (1 = sistema S0) |
| `OLLAMA_MODEL` | `qwen2.5:7b` (`llama3:latest` = sistema S5) |
| `OLLAMA_NUM_CTX` / `OLLAMA_NUM_PREDICT` | 8192 / 1024 |
| `OLLAMA_SEED` | 42 (corridas repetidas con semilla 7) |
| temperatura | 0.2 |
| `PROMPT_VERSION` | `v3-completo` |
| `TIMEOUT_RESPUESTA` | 120 s |

Cada corrida de `comparacion_v2_v3/correr_17q_e2e.py` guarda en su JSON (`meta`) el banco usado y
estas variables leídas del backend, así que el valor exacto de cada experimento queda en su archivo.

## Software

| Componente | Versión |
|---|---|
| Python (backend) | 3.10.21 |
| torch | 2.14.0+cu130 (el backend corre en CPU; la GPU queda para el LLM) |
| chromadb | 0.4.22 |
| sentence-transformers | 6.0.1 |
| transformers | 5.17.0 |
| fastapi | 0.110.0 |
| numpy / scipy | 1.26.4 / 1.15.3 |
| Ollama | 0.30.0 |
| Docker Engine | 29.9.2 |

## Hardware

| Componente | Valor |
|---|---|
| CPU | Intel Core i7-13620H |
| RAM | 16 GB |
| GPU | NVIDIA GeForce RTX 4050 Laptop, 6 GB VRAM (driver 621.24) |
| Sistema operativo | Windows 11 Pro (26300) + Docker Desktop (contenedores Linux) |

## Conjuntos de preguntas

| Conjunto | Uso | Nota |
|---|---|---|
| Banco 17Q (v3.1, congelado) y banco v3.2 (30 + 6) | **Desarrollo**: se usaron para ajustar umbral, K y prompt | En el gold set se reportan también los resultados sin estas preguntas |
| Calibración del umbral (325 positivas / 42 negativas) | Desarrollo | 34 de las 42 negativas son preguntas fuera de dominio del pool de 260, y las otras 6 del pool son N01–N06 (ablaciones) → **las 40 fuera de dominio del pool ya se vieron**; la decisión oficial de H5 necesita 40 nuevas |
| Pool 260 → `banco_gold_260.json` | **Evaluación** | Pendiente de doble anotación |

## Cambios después de congelar

| Fecha | Cambio | Afecta a los resultados del sistema vigente |
|---|---|---|
| 2026-11-22 | Se agrega `RAG_SIN_RECUPERACION` (sistema S0); la limpieza de respuestas pasa a una función común (`_sanear_basico`), sin cambiar su comportamiento | No: por defecto vale 0 |
| 2026-11-22 | `OLLAMA_MODEL` del backend pasa a `${OLLAMA_MODEL:-qwen2.5:7b}` en `docker-compose.yml` (para S5) | No: el valor por defecto es el mismo |
