# OE5 – Sistema Conversacional Universitario con IA Generativa Explicable

Este proyecto implementa el **Objetivo Específico 5** del PPI:
> *Implementar el sistema conversacional web integrando IA generativa con recuperación documental y presentación de fuentes verificables para explicabilidad y trazabilidad.*

El sistema permite a estudiantes y personal de la Universidad Peruana Unión (UPeU) realizar consultas en lenguaje natural sobre reglamentos, trámites y documentos institucionales, obteniendo respuestas fundamentadas en el corpus documental oficial con trazabilidad completa de las fuentes.

## Estado actual del proyecto

| Objetivo específico | Estado | Evidencia |
|---|---|---|
| **OE4** Reglas de transparencia y explicabilidad | ✅ 100 % (T01/T02 fijados por decisión del equipo) | `backend/config.py` + `rag_pipeline.py` |
| **OE5** Sistema conversacional con IA explicable | ✅ 100 % | Frontend + Backend + RAG + LLM + registro |
| **OE6** Instrumentos de evaluación de madurez | ✅ 100 % | `evaluacion/madurez_oe8/INSTRUMENTOS.md` (5 instrumentos) |
| **OE7** Validación por expertos (V de Aiken) | ⏳ Pendiente (proceso) | Ejecutar con 3-5 expertos externos |
| **OE8** Cálculo de madurez y piloto con usuarios | 🟡 FASE 5 cerrada (auto) · FASE 6 pendiente de datos | `evaluacion/madurez_oe8/reporte_madurez.md` · instrumento piloto 30 ítems listo, 0 respuestas reales |

## Cambios del 21–22 de noviembre de 2026: corpus V3 y mejoras del chatbot

Detalle completo (método, ablaciones, corridas y decisiones): [`evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md`](evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md).

| Qué | Antes (hasta 2026-11-20) | Ahora | Evidencia |
|---|---|---|---|
| Base vectorial | `corpus_upeu_v2`, 5,126 chunks | **`corpus_upeu_v3_bgem3`**, 5,117 chunks (OE1 V3) | V2 respaldada en `vector_store_backup_v2_20261121/` |
| Embeddings | mpnet, 768 dim | **`BAAI/bge-m3`** rev. `5617a9f6`, 1024 dim | Artículo correcto en el Top-15: 53 % → 80 % |
| Umbral de distancia | 0.40 | **0.41** | Calibrado con 325 positivas / 42 negativas |
| Margen fuera de dominio | 0.10 (corte 0.50) | **0.09** (corte 0.50) | Corte justo sobre la peor positiva (0.492) |
| Boost por keyword | 0.07 | **0.02** | Top-4 documento 0.892 → 0.923 |
| Recorte de cada fragmento | 700 caracteres (inicio + "[…]" + final) | **Ninguno**: chunks completos hasta 9,000 caracteres en total | El LLM no veía el medio de los artículos |
| `num_ctx` de Ollama | Valor por defecto | **8192** | El prompt nunca se recorta en silencio |
| Semilla del LLM | Ninguna | **42** | Reproducibilidad (Revisión 3 §10) |
| Prompt | `v2-adaptativo` ("texto directo breve") | **`v3-completo`** (todos los requisitos, pasos y condiciones) | Completitud 0.40 → 0.57 (p < 0.0001) |
| Timeout del LLM | 50 s | **120 s** | Respuestas ~2× más largas |
| Abstención disfrazada | Se colaba como M02 si la frase tenía paréntesis | **Detectada** (también dos frases encadenadas) | Casos reales de Q17 |
| Igual que antes | TOP_K 15/4, `num_predict` 1024, temperatura 0.2, 500 palabras, LLM Qwen2.5-7B | — | Probados K=6 y K=8: no mejoran |
| Probado y descartado | — | Re-ranker `bge-reranker-v2-m3` y reintento ante abstención | Peor en 17 Q; 0 de 11 abstenciones tenían el documento correcto |
| Implementado, apagado | — | Contexto por artículo (`RAG_CONTEXTO_ARTICULO=0`) | Sin efecto medible; evaluar con el gold set |
| Banco de evaluación | 17 Q (Q17 y 8 categorías desactualizadas) | **Banco v3.2: 30 Q + 6 negativas** (`evaluacion/banco/banco_v32.json`) | Validado contra el corpus V3 |

**Resultado con el banco v3.2** (30 preguntas, 2 semillas): documento correcto entre las fuentes 26/30,
artículo correcto 16/27, completitud ~0.57, 6/6 negativas abstenidas, tiempo típico ~23 s.
Todos los parámetros son variables de entorno (`docker-compose.yml`), así que cada cambio se puede revertir sin tocar código.

## Revisión 3 (.docx): avance al 23 de noviembre de 2026

> **Resumen de fase, resultados y decisiones en un solo lugar:** [`evaluacion/ESTADO_REVISION_3.md`](evaluacion/ESTADO_REVISION_3.md).
> **Qué entregar a los evaluadores (gold set y fidelidad):** [`evaluacion/ENTREGA_EVALUADORES.md`](evaluacion/ENTREGA_EVALUADORES.md).

El documento `docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx` (03-09-2026) define el estudio experimental:
H1–H5, gold set de 260 preguntas, sistemas S0–S6, experimentos A (recuperación), B (generación) y C
(abstención), evaluación humana, estadística y tablas 1–6. El 22 de noviembre se auditó contra el sistema y se
avanzó todo lo que no depende de la anotación humana. La configuración del chatbot quedó **congelada** en el
commit `c47d455a` ([`evaluacion/REPRODUCIBILIDAD.md`](evaluacion/REPRODUCIBILIDAD.md)).

| § del .docx | Estado | Dónde |
|---|---|---|
| 0 Hipótesis H1–H5 | ✅ aprobadas; criterio H5 ratificado (≥ 0.90 con IC95) | `evaluacion/banco/hipotesis.md`, `evaluacion/retrieval/criterio_h5.md` |
| 2 Corpus | ✅ V3, 48 documentos, 5,117 chunks; variantes de 150/300/600 tokens generadas por el OE1 | `REPRODUCIBILIDAD.md` |
| 3 Gold set 260 | 🟡 pool listo + fichas ciegas, κ y consolidación listas; **falta que el equipo anote** y redacte 40 preguntas fuera de dominio nuevas | `evaluacion/banco/gold/` |
| 4 Sistemas S0–S8 | ✅ S0 (`RAG_SIN_RECUPERACION=1`), S1 BM25, S2 MiniLM, S3 mpnet, S4 bge-m3, S6 Qwen2.5-7B; S5 Llama 3 8B **descartado**; S5b `llama3.2:3b`, S7 `qwen3:4b-instruct`, S8 `gemma3:4b` descargados 2026-11-22 | `evaluacion/retrieval/matriz_sistemas.md` |
| 5A Recuperación (H1, H2, H4) | 🟡 preliminar: 4 recuperadores × 4 tamaños de chunk con bancos de desarrollo | `evaluacion/retrieval/exp_a/` |
| 5B Generadores (H3) | 🟡 preliminar (banco v3.2): Qwen 0.53 vs Llama 3 8B 0.39 de completitud (p Holm 0.03), 20 vs 39 s; Llama 3 8B **descartado** (no cabe en la GPU, 17 % timeouts). Modelos nuevos (2 semillas, 2026-11-23): completitud `qwen3:4b-instruct` 0.63, `gemma3:4b` 0.58, `llama3.2:3b` 0.51 vs Qwen2.5-7B 0.53, ninguna diferencia significativa con Holm; los tres más rápidos (p50 7 / 22 / 17 s vs 20 s; p95 18 / 26 / 34 s vs 58 s), 0 timeouts, 12/12 negativas. S0: 0.03 | `evaluacion/generacion/` |
| 5C Abstención (H5) | 🟡 preliminar: 40/40 fuera de dominio (ya vistas en el desarrollo), 14/20 ambiguas | `evaluacion/exp_c/` |
| 7 Métricas | ✅ R@k, MRR, nDCG@5, atribución, abstención, latencia; ❌ falta medir la fidelidad | — |
| 8 Evaluación humana | 🟡 rúbrica fijada y generador de fichas ciegas listo (2026-11-23); falta que evalúe el equipo (ronda 2) | `evaluacion/humana/RUBRICA_FIDELIDAD_REV3.md`, `fichas_fidelidad.py` |
| 9 Estadística | ✅ bootstrap IC95, Wilson, Wilcoxon, Holm, tamaño de efecto, κ de Cohen | `evaluacion/estadistica/` |
| 10 Reproducibilidad | ✅ ficha con commit, versiones, revisiones, hardware y semillas | `evaluacion/REPRODUCIBILIDAD.md` |
| 11 Tablas 1–6 y figuras | 🟡 esqueleto con datos preliminares (2026-11-23); se regenera con el gold set | `evaluacion/tablas/` |

**Resultados preliminares** (bancos de desarrollo: 154 preguntas del OE1 y banco v3.2; no son los oficiales):

- **H1** (R@5, 154 Q): bge-m3 0.916 > BM25 0.675 (+0.24 [0.16, 0.32], p Holm < 0.001); mpnet 0.617 empata con
  BM25 y MiniLM 0.526 es peor (p Holm 0.008). Solo bge-m3 supera a BM25: mpnet y MiniLM leen 128 tokens.
- **H2** (R@5, 154 Q, chunks 150 / 300 / 600): bge-m3 0.903 / 0.929 / 0.909, sin diferencias significativas;
  BM25 mejora con chunks grandes (600 vs 150: +0.078, p Holm 0.02).
- **H5**: 40/40 fuera de dominio (IC95 [0.91, 1.00]), pero esas 40 se usaron al calibrar el umbral; ambiguas
  14/20, solo 4 reciben pregunta de aclaración (6 reciben una respuesta inventando el contexto).
- **H3** (banco v3.2): Qwen2.5-7B supera a Llama 3 8B en completitud (0.53 vs 0.39, p Holm 0.03) y latencia
  (p50 20 vs 39 s); atribución exacta igual. Llama 3 8B no cabe en la GPU de 6 GB (17 % de timeouts) → **descartado
  el 2026-11-22** (aprobado por el asesor). Con los reemplazos (2026-11-23): `qwen3:4b-instruct` 0.63, `gemma3:4b` 0.58,
  `llama3.2:3b` 0.51 de completitud vs 0.53 de Qwen, sin diferencias significativas tras Holm; los tres son más rápidos
  (p < 0.05) y no tienen timeouts. S0 (sin recuperación):
  completitud 0.03, lo que confirma el aporte del RAG.

**Modelo del chatbot:** sigue con Qwen2.5-7B (configuración congelada). Candidato: `qwen3:4b-instruct` (mejor en el
preliminar y más rápido, pero sin diferencia significativa con 30 preguntas); se decide con el Exp. B oficial y la
fidelidad humana (`evaluacion/ESTADO_REVISION_3.md` §5).

**Lo que falta:** anotación del gold set y 40 preguntas fuera de dominio nuevas (equipo, ronda 1) → experimentos A, B
y C oficiales sobre las 260 → evaluación humana ciega de la fidelidad (equipo, ronda 2) → decisión del generador →
tablas 1–6. Qué recibe y devuelve cada evaluador: `evaluacion/ENTREGA_EVALUADORES.md`.

## Estructura del proyecto

```
oe5_chatbot_upeu/
├── llm/                              # Servicio de IA generativa (Qwen2.5-7B con Ollama)
│   ├── Dockerfile
│   ├── entrypoint.sh                 # Pre-pull + warm-up del modelo en arranque
│   └── .gitignore
├── backend/                          # API REST (FastAPI) y pipeline RAG
│   ├── app.py                        # Endpoints: /consulta, /bienvenida, /historial,
│   │                                 #            /documentos, /politica-privacidad,
│   │                                 #            /salud, /config-publica
│   ├── config.py                     # RAG_DISTANCE_THRESHOLD=0.41, margen 0.09, boost 0.02 (bge-m3), TOP_K_RAW=15/FINAL=4,
│   │                                 # mensajes M01-M08, dominios A-E, keywords, PII, CORS
│   ├── logger.py                     # Registro ANONIMIZADO + seudonimización (Ley 29733)
│   │                                 # + migraciones de ~20 tablas de evaluación
│   ├── rag_pipeline.py               # Pipeline RAG: validadores + retrieval + re-ranking
│   │                                 # (boost keyword 0.02) + LLM (PROMPT v3-completo; v2-adaptativo seleccionable)
│   │                                 # + contexto completo (sin recorte 700) + retry policy + guardrails de citas
│   ├── context_builder.py            # Construcción determinística de contexto/fuentes (Fase 2)
│   ├── validators_evaluacion.py      # source_validity / citation_match determinísticos
│   ├── tests/                        # Suite pytest (403 tests en verde; test_mejoras_chatbot.py = mejoras 2026-11; test_estadistica, test_exp_a_recuperacion, test_gold_acuerdo, test_exp_b_generacion, test_fichas_fidelidad, test_generar_tablas = Revisión 3)
│   ├── POLITICA_PRIVACIDAD.md        # Política de privacidad (Ley 29733)
│   ├── requirements.txt
│   ├── Dockerfile                    # Con HEALTHCHECK
│   └── .gitignore
├── frontend/                         # Interfaz de usuario (React 18)
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js                    # Orquestador, sesion_id, banner privacidad,
│   │   │                             # footer M07, contador piloto, borrado historial
│   │   ├── App.css                   # Identidad visual UPeU (Fraunces + IBM Plex)
│   │   ├── index.js
│   │   └── components/
│   │       ├── ChatWindow.js         # Scroll auto + empty state + thinking
│   │       ├── Message.js            # Render por tipo M02-M08 + markdown (remark-gfm/tablas)
│   │       └── SourceBadge.js        # Chip "Relevancia %" (no probabilidad) + doc + sección
│   ├── nginx.conf
│   ├── package.json
│   ├── Dockerfile                    # Multi-stage (build + nginx)
│   └── .gitignore
├── evaluacion/                       # Evaluación técnica + madurez (ver README_EVALUACION.md)
│   ├── README_EVALUACION.md          # Flujo de trabajo de evaluación
│   ├── REPRODUCIBILIDAD.md           # Configuración congelada para la Revisión 3 (commit c47d455a)
│   ├── ESTADO_REVISION_3.md          # Fase actual, resultados preliminares y decisiones (Revisión 3)
│   ├── ENTREGA_EVALUADORES.md        # Qué archivos recibe y devuelve cada evaluador (gold set, fidelidad)
│   ├── banco/                        # banco_v32.json (30 Q + 6 negativas, VIGENTE) + construir_banco_v32.py,
│   │   │                             # auditoría del banco 17 Q, v3.1 (congelada), pool 260, banco_exp_c_pool.json
│   │   └── gold/                     # Gold set 260: fichas ciegas A/B (.xlsx), plantilla OOD nuevas, acuerdo_gold.py (κ)
│   ├── retrieval/                    # evaluar_rag_v3.py, calibrar_v3_bgem3.py, evaluar_reranker.py, métricas EXP_*.csv,
│   │                                 # exp_a_recuperacion.py + exp_a/ (Exp. A), analisis_h2.py
│   ├── estadistica/                  # estadistica.py: bootstrap, Wilson, Wilcoxon, Holm, κ (Revisión 3 §9)
│   ├── exp_c/                        # Experimento C (abstención): exp_c_abstencion.py + resultados
│   ├── comparacion_v2_v3/            # COMPARACION_V2_V3.md (informe 2026-11-21/22), correr_17q_e2e.py,
│   │                                 # ablacion.ps1, completitud_auto.py, corridas E2E_*
│   ├── generacion/                   # baseline_generacion_v3_oficial.py, harnesses, JSON/CSV
│   ├── humana/                       # Fichas Q01-Q17 (fichas_humanas_v31/, 66 puntos),
│   │                                 # importar_ficha_humana.py, calcular_metricas_humanas.py,
│   │                                 # GUIA_EVALUACION_HUMANA_V3.md; Rev. 3: RUBRICA_FIDELIDAD_REV3.md,
│   │                                 # fichas_fidelidad.py (fichas ciegas + κ + comparación)
│   ├── tablas/                       # generar_tablas.py → salida/TABLAS.md (tablas 1–6, figuras 1–3)
│   ├── madurez_oe8/                  # calcular_madurez.py, instrumento piloto 30 ítems,
│   │                                 # importar_piloto.py, reporte_madurez.md
│   └── legacy/                       # Scripts/resultados históricos (evaluar_modelo.ps1…)
├── docs/                             # Especificación del proyecto
│   ├── PARTE_2_CHATBOT_RAG.md        # Fases 1-7 del chatbot RAG
│   ├── PARTE_3_EVALUACION_MADUREZ.md # Fases 1-6 de evaluación y madurez OE8
│   └── FLUJO_CONSULTA.txt            # Diagrama del flujo de una consulta
├── vector_store/                     # Base vectorial ChromaDB (corpus persiste aquí)
│   ├── chroma.sqlite3                # corpus_upeu_v3_bgem3, 5117 chunks, bge-m3 1024 (desde 2026-11-21)
│   └── [uuid]/
├── vector_store_backup_v2_20261121/  # Respaldo de la V2 (corpus_upeu_v2, mpnet) para volver atrás
├── registro_interacciones.db         # DB oficial: interacciones, banco_preguntas,
│                                     # experimentos_rag, evaluacion_retrieval/generacion,
│                                     # groundtruth_v31_*, detalle humano, banco_no_answer…
├── backups/                          # Respaldos y snapshots corruptos (forense, no usar)
├── docker-compose.yml                # Orquestación con healthchecks y /data/...
├── .gitignore
├── debug.py                          # Script de diagnóstico manual
└── README.md                         # Este archivo
```

## Mapeo de volúmenes Docker

Para evitar anclas fantasma (`backend/<directorio>`), los volúmenes de datos
se montan en un path padre distinto al del código:

| Recurso en host              | Mount en contenedor backend | Descripción                          |
|---|---|---|
| `./backend`                  | `/app`                      | Código Python (live reload)          |
| `./evaluacion`               | `/data/evaluacion`          | Scripts de evaluación                |
| `./vector_store`             | `/data/vector_store`        | ChromaDB (corpus V3)                 |
| `./registro_interacciones.db`| `/data/registro_interacciones.db` | SQLite con log y evaluación   |
| (volumen anónimo)            | `/root/.ollama`             | Modelos LLM descargados              |
| volumen `hf_cache`           | `/root/.cache/huggingface`  | bge-m3 (~2.2 GB) persiste entre recreaciones del backend |

## Tecnologías utilizadas

| Componente | Tecnología | Versión/Detalles |
|------------|------------|------------------|
| **Contenerización** | Docker + Docker Compose | - |
| **Frontend** | React | 18.3.1 |
| **Renderizado en frontend** | react-markdown | 10.1.0 |
| **Backend / API** | FastAPI | 0.110.0 |
| **Servidor ASGI** | Uvicorn | 0.27.0 |
| **Lenguaje (backend)** | Python | 3.10 |
| **Orquestación RAG** | LangChain | 0.1.0 + community 0.0.10 |
| **Modelo de embeddings** | Sentence-Transformers | `BAAI/bge-m3` rev. `5617a9f6` (1024 dims, ganador OE1 V3, 2026-11-21). Antes: mpnet 768 (V2) |
| **Base vectorial** | ChromaDB | 0.4.22, colección `corpus_upeu_v3_bgem3` (configurable: `CORPUS_VERSION`), distancia coseno. Respaldo V2: `vector_store_backup_v2_20261121/` · comparación: `evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md` |
| **Modelo LLM** | Qwen2.5-7B | Servido por Ollama, `num_ctx=8192`, `num_predict=1024`, `temperature=0.2`, `seed=42`. Prompt **v3-completo** desde 2026-11-22 (respuestas completas; timeout 120 s; v2 disponible con `PROMPT_VERSION=v2-adaptativo`). Contexto: chunks completos hasta 9000 caracteres (sin recorte de 700 desde 2026-11-21; ver `evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md` §6) |
| **Contenedor LLM** | Ollama | latest con CUDA v13. Modelo por defecto: Qwen2.5-7B |
| **GPU (opcional)** | NVIDIA CUDA | v13 (RTX 4050 compatible) |
| **Comparativa LLM** | Llama 3 8B vs Qwen2.5-7B | `evaluacion/madurez_oe8/COMPARACION_LLMS.md` (junio) **→ Se adoptó Qwen2.5-7B**; confirmado en el Exp. B preliminar (2026-11-22), donde Llama 3 8B quedó descartado |
| **Registro de datos** | SQLite 3 | ~20 tablas (ver `evaluacion/README_EVALUACION.md`) |
| **Suite de tests** | pytest (Docker) | 403 passed (2026-11-23) |
| **Frontend build tool** | Node.js + npm | 18-alpine en contenedor |

## Requisitos previos

1. **Docker Desktop** instalado y funcionando
   - Modo WSL 2 (recomendado) o Hyper-V
    - 20 GB de espacio libre (imágenes + modelo Qwen2.5-7B ~ 4.7 GB)
2. **(Recomendado) GPU NVIDIA** con drivers CUDA v13 instalados
   - Sin GPU: respuestas en ~30-60 s
   - Con GPU: respuestas en ~5-15 s
3. **Carpeta `vector_store/`** con el corpus indexado
   - Se obtiene del proyecto `oe1_arquitectura_corpus/corpus_upeu/vector_store_v3_bgem3/`
   - Tamaño: ~81 MB (corpus_upeu_v3_bgem3 → 5117 chunks, bge-m3 1024 dim)
   - La primera vez el backend descarga bge-m3 (~2.2 GB) al volumen `hf_cache`
4. **Python 3.10+ y `chromadb==0.4.22`** (opcional, solo si quieres regenerar la ficha documental desde host — ver `evaluacion/README_EVALUACION.md`)

## Configuración

Parámetros en `backend/config.py`. **Todos se pueden cambiar por variable de entorno** en
`docker-compose.yml` (forma `${VAR:-valor}`), sin tocar código. Valores vigentes al 2026-11-22:

```python
# Recuperación (calibrado para bge-m3, 2026-11-21; evaluacion/retrieval/calibracion_v3_bgem3/)
RAG_DISTANCE_THRESHOLD = 0.41      # T01: distancia coseno máxima (sobre distancia con boost). V2: 0.40
RAG_MARGEN_FUERA_DOMINIO = 0.09    # R04: M03 si la mejor distancia > 0.41 + 0.09 = 0.50. V2: 0.10
RAG_KEYWORD_BOOST = 0.02           # descuento por keyword de la pregunta en el nombre del documento. V2: 0.07
RAG_TOP_K_RAW = 15                 # candidatos iniciales (probado 30/50: sin cambio)
RAG_TOP_K_FINAL = 4                # máx. fuentes al LLM (probado 6/8: el LLM cita menos el artículo correcto)

# Contexto y LLM (mejoras 2026-11-21/22)
RAG_CONTEXT_MAX_CHARS = 9000       # fragmentos COMPLETOS hasta este total (antes: recorte a 700 chars c/u)
OLLAMA_NUM_CTX = 8192              # ventana explícita de Ollama (antes: valor por defecto)
OLLAMA_NUM_PREDICT = 1024          # tokens máx. de respuesta (sin cambio; las respuestas usan 300-700)
OLLAMA_SEED = 42                   # semilla fija (antes: ninguna)
PROMPT_VERSION = "v3-completo"     # antes "v2-adaptativo" (pedía "texto directo breve")
TIMEOUT_RESPUESTA = 120            # T04: segundos (antes 50 → 75 → 120)
MAX_PALABRAS_RESPUESTA = 500       # T03 (sin cambio; ninguna respuesta lo alcanzó)
RAG_CONTEXTO_ARTICULO = False      # mejora 3 implementada pero APAGADA (sin efecto medible con 17 Q)

# Corpus y modelo de embeddings
CORPUS_VERSION = "corpus_upeu_v3_bgem3"
EMBEDDING_MODEL = "BAAI/bge-m3"    # revisión fijada: EMBEDDING_REVISION=5617a9f6…

MODO_PILOTO = True                 # T07 (límite 10 preguntas/sesión)
DEBUG_LOG = True                   # expone debug_distancias en /consulta
```

Selección de fragmentos (`rag_pipeline.py`):

```text
1. Recupera RAG_TOP_K_RAW=15 chunks por distancia coseno (bge-m3).
2. Resta 0.02 por cada keyword de la pregunta presente en el nombre del documento y reordena
   TODO el pool por esa distancia (no se recorta antes del umbral).
3. Si nada está a menos de 0.50 (y las keywords no deciden el dominio) → M03.
4. Toma hasta 4 chunks con distancia < 0.41, completos, mientras quepan en 9000 caracteres
   (si ninguno pasa → M04).
5. Genera con Qwen2.5-7B (prompt v3-completo, num_ctx 8192, semilla 42) y post-procesa:
   viñetas, reparación de citas, oraciones meta de "no hay información" (→ M04 si no queda nada útil).
```

Para volver a la configuración V2: renombrar `vector_store_backup_v2_20261121` → `vector_store` y fijar
`CORPUS_VERSION=corpus_upeu_v2`, `EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2`, `EMBEDDING_REVISION=""`,
`RAG_DISTANCE_THRESHOLD=0.40`, `RAG_MARGEN_FUERA_DOMINIO=0.10`, `RAG_KEYWORD_BOOST=0.07`,
`PROMPT_VERSION=v2-adaptativo` (y `RAG_RECORTE_LEGACY_700=1` para el recorte antiguo).

**Variables de entorno (docker-compose.yml):**

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://llm:11434` | URL del servicio Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Modelo a usar. En el Exp. B de la Revisión 3 se comparan `llama3.2:3b`, `qwen3:4b-instruct` y `gemma3:4b` (Llama 3 8B descartado) |
| `CORPUS_VERSION` / `EMBEDDING_MODEL` / `EMBEDDING_REVISION` | `corpus_upeu_v3_bgem3` / `BAAI/bge-m3` / `5617a9f6…` | Colección y modelo de embeddings (al arrancar se verifica que las dimensiones coincidan) |
| `RAG_DISTANCE_THRESHOLD` / `RAG_MARGEN_FUERA_DOMINIO` / `RAG_KEYWORD_BOOST` | `0.41` / `0.09` / `0.02` | Calibrados para bge-m3 (2026-11-21) |
| `RAG_TOP_K_RAW` / `RAG_TOP_K_FINAL` | `15` / `4` | Candidatos y fuentes al LLM |
| `RAG_CONTEXT_MAX_CHARS` | `9000` | Presupuesto de contexto (chunks completos) |
| `OLLAMA_NUM_CTX` / `OLLAMA_NUM_PREDICT` / `OLLAMA_SEED` | `8192` / `1024` / `42` | Ventana, tokens de salida y semilla del LLM |
| `PROMPT_VERSION` | `v3-completo` | `v2-adaptativo` = prompt anterior ("breve") |
| `TIMEOUT_RESPUESTA` | `120` | T04 en segundos |
| `RAG_CONTEXTO_ARTICULO` / `RAG_ARTICULO_MAX_CHARS` | `0` / `4000` | Mejora 3 (contexto por artículo), apagada |
| `RAG_RECORTE_LEGACY_700` | `0` | Solo para ablación: `1` reproduce el recorte antiguo |
| `RAG_SIN_RECUPERACION` | `0` | Solo experimentos: `1` = sistema S0 (responde sin documentos; prompt `s0-sin-rag`). Nunca en producción |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS (lista separada por comas) |
| `MODO_PILOTO` | `true` | Activa límite T07 (10 preguntas/sesión) |
| `DEBUG_LOG` | `false` | Expone `debug_distancias` en `/consulta` (el chip de afinidad % del frontend usa esos datos). En el piloto va `true`; en producción se apaga y el frontend degrada sin el porcentaje |
| `LIMITE_PREGUNTAS_SESION` | `10` | T07: tope de preguntas por sesión |

## Instalación y ejecución

```powershell
# 1. Clonar el repositorio
git clone https://github.com/LuisAlbertoQ/ChatUpeuCorpus.git
cd ChatUpeuCorpus

# 2. Verificar que vector_store/ contiene el corpus
ls vector_store/   # debe contener chroma.sqlite3

# 3. Levantar los servicios
docker compose up -d --build

# 4. Esperar a que los healthchecks estén verdes
docker compose ps

# 5. Abrir el chatbot
# http://localhost:3000
```

**Primera ejecución (10-30 min):** descarga imágenes base, modelo Qwen2.5-7B, instala dependencias.

**Recarga de código Python (después de editar *.py en backend/):**
```powershell
docker compose restart backend
```
Solo `build` si cambia `requirements.txt` o `Dockerfile`.

## Uso del sistema

### Flujo de una consulta

1. Usuario escribe pregunta → 2. Frontend envía `POST /consulta`
3. Backend valida sesión (T07) y ejecuta pipeline RAG:
   - Validaciones (ambigua M05, ética M03, multi-intención M05, fuera-dominio M03)
   - Embedding con `BAAI/bge-m3` (multilingüe, 1024 dim; `EMBEDDING_MODEL`)
   - Retrieval top-15 en ChromaDB (TOP_K_RAW=15)
   - Re-ranking por keywords: boost de 0.02 por match en `meta["documento"]`
   - Hasta 4 chunks con distancia boosted < 0.41, completos, hasta 9000 caracteres en total
   - LLM con PROMPT v3-completo (todos los requisitos/pasos de las fuentes + cita por dato), num_ctx 8192, semilla 42
   - Post-proceso: `•` → `- ` (markdown) + reparación de citas + eliminación de meta-frases
     ("el corpus no contiene…"; si no queda contenido útil → M04)
   - Sanear bloque "Fuentes:" final + truncado T03
4. Respuesta + fuentes + tipo_mensaje
5. Render en frontend (markdown + `SourceBadge`)
6. Registro anonimizado en SQLite (pregunta, respuesta, fuentes, tiempo, sesion_id)

Ver `docs/FLUJO_CONSULTA.txt` para el diagrama detallado.

## API – Endpoints expuestos

| Método | Ruta | Propósito | OE4 |
|---|---|---|---|
| `POST` | `/consulta` | Pipeline RAG → respuesta + fuentes + tipo_mensaje | RF01, RF03–RF05, T01–T08 |
| `GET`  | `/bienvenida` | Mensaje M01 (aviso inicial) | M01 |
| `GET`  | `/config-publica` | Parámetros visibles al frontend | RNF05 |
| `GET`  | `/historial?sesion_id=` | Exporta CSV (opcional filtrado por sesión) | RF06, RF07 |
| `DELETE` | `/historial/{sesion_id}` | **Seudonimiza** la sesión (derecho al olvido, Ley 29733) | 3.4 |
| `GET`  | `/documentos` | Introspección del corpus indexado | – |
| `GET`  | `/politica-privacidad` | Texto de la política (Ley 29733) | 3.3 |
| `GET`  | `/salud` | Healthcheck (usado por Docker) | RNF02 |

> ⚠️ El endpoint `DELETE /historial/{sesion_id}` aplica **seudonimización** (no eliminación física): sustituye `sesion_id` por `'anonimizado'` y limpia `error`, preservando `pregunta/respuesta/fuentes` (ya anonimizadas al insertarse) para fines de evaluación OE6/OE8. Para eliminación física, contactar al equipo (ver `POLITICA_PRIVACIDAD.md` §5).

## Tablas en `registro_interacciones.db`

| Tabla | Propósito | Quién la llena |
|---|---|---|
| `interacciones` | Log de cada consulta (anonimizado, 35 cols. Fase 5) | Backend automático |
| `banco_preguntas` | Banco 17 Q v3 + P01-P08 históricos (⚠️ Q17 y 8 categorías desactualizadas; usar `banco_v32.json`) | `evaluacion/banco/sincronizar_banco.py` |
| `groundtruth_v31_*` | Ground truth v3.1 (17 Q / 66 puntos) | Curación auditada (congelado). Su evolución, el **banco v3.2** (30 Q, 114 puntos), está en `evaluacion/banco/banco_v32.json` |
| `experimentos_rag` | Snapshots de experimentos retrieval/generación/negativo | Harnesses `evaluacion/` |
| `evaluacion_retrieval` | 255 candidatos Top15 del baseline + reevaluación | `evaluacion/retrieval/evaluar_rag*.py` |
| `evaluacion_generacion` | 17 respuestas oficiales + métricas determinísticas | `evaluacion/generacion/baseline_generacion_v3_oficial.py` |
| `evaluacion_*_detalle` | Juicios humanos (completitud/faithfulness/citas) | `evaluacion/humana/importar_ficha_humana.py` |
| `banco_no_answer` | Banco negativo N01-N06 (SIN_COBERTURA) | Curación (congelado) |
| `evaluacion_piloto` / `piloto_respuestas` | Piloto OE8 (0 respuestas reales aún) | `evaluacion/madurez_oe8/importar_piloto.py` |
| `evaluacion_automatica` | Snapshots OE8 (etiqueta `OE8_AUTO_PRE_PILOTO`) | `evaluacion/madurez_oe8/calcular_madurez.py --auto-only` |

## Cumplimiento del documento OE4 v2.0

| Cláusula | Estado | Implementación |
|---|---|---|
| **D01–D06 → Dominios A–E reales del corpus** | ✅ | `config.MAPEO_CATEGORIAS` + `KEYWORDS_DOMINIO` |
| **R01–R03 Restricciones de contenido** | ✅ | PROMPT restrictivo en `rag_pipeline.PROMPT` v2 |
| **R04 Fuera de dominio** | ✅ | Validador por keywords + umbral |
| **R05 Sin corpus → sin respuesta** | ✅ | Filtro T01 + emisión M04 |
| **R07 Contenido ético/legal** | ✅ | `KEYWORDS_ETICA` → M03 |
| **3.2 Anonimización** | ✅ | `logger.anonimizar` aplica patrones PII antes de INSERT |
| **3.3 Ley 29733** | ✅ | `backend/POLITICA_PRIVACIDAD.md` servido por `/politica-privacidad` |
| **3.4 Derecho al olvido** | ✅ | `DELETE /historial/{sesion_id}` (seudonimización) |
| **M01 Bienvenida** | ✅ | `/bienvenida` consumido por el frontend |
| **M02 Respuesta con fuentes** | ✅ | Renderizado por `SourceBadge` (sin duplicar en cuerpo) |
| **M03 Fuera de dominio** | ✅ | Validador → `tipo_mensaje=M03` |
| **M04 Baja certeza** | ✅ | Cuando todas las distancias > umbral |
| **M05 Pregunta ambigua / multi-intención** | ✅ | `_pregunta_es_ambigua` + `_es_multi_intencion` |
| **M06 Error técnico** | ✅ | `try/except` + timeout T04 |
| **M07 Aviso permanente** | ✅ | Footer fijo con texto exacto |
| **M08 Límite de sesión** | ✅ | HTTP 429 + `M08_LIMITE` en `MENSAJES` |
| **T01 Umbral similitud 0.70** | 🟡 Parcial | Se usa distancia 0.41 (≈ similitud 0.59), calibrada para bge-m3 el 2026-11-21 (antes 0.40 con mpnet) |
| **T02 Top-k 1–3** | 🟡 Parcial | Se mantiene k=3 por decisión del equipo |
| **T03 Máx 350 palabras** | ✅ | `_truncar_palabras` añade `(…)` (configurado a 500) |
| **T04 Timeout 15 s** | ✅ | `urllib.request` + `FutTimeout` → M06 (configurado a 120 s desde 2026-11-22 por el prompt v3; antes 50 s) |
| **T05 Generación condicional** | ✅ | Solo si hay fragmentos válidos |
| **T06 Multi-intención** | ✅ | Heurística de conectores + interrogativas |
| **T07 Límite 10 preguntas/sesión piloto** | ✅ | `sesion_id` + `contar_preguntas_sesion` + HTTP 429 |
| **T08 Fuentes enriquecidas** | ✅ | `_formatear_fuente` extrae artículo + versión + año + categoría |
| **RNF01 Usabilidad** | ✅ | UI editorial cohesiva + estados + responsivo |
| **RNF02 Rendimiento** | ✅ | Timeout + healthchecks + pre-pull + warm-up del modelo |
| **RNF03 Sin PII** | ✅ | Anonimización automática antes de INSERT |
| **RNF04 Trazabilidad** | ✅ | `SourceBadge` con sección + versión + categoría |
| **RNF05 Modificabilidad** | ✅ | `config.py` + variables de entorno |
| **RNF06 Transparencia** | ✅ | M01 al inicio + M07 permanente |

## Guía rápida de ejecución

### 1. Iniciar todo

```powershell
docker compose up -d
# Esperar ~35-40s para que el modelo LLM termine warm-up
```

Verificar que todo esté saludable:
```powershell
docker compose ps                     # los 3 contenedores deben mostrar "Up"
curl http://localhost:8000/salud      # debe responder {"status":"ok","modo_piloto":true,...}
curl http://localhost:3000            # frontend (puede tardar 10s en 1er carga)
```

### 2. Probar una consulta

```powershell
$body = @{ pregunta = "Cómo obtengo el título profesional"; sesion_id = "mi-prueba" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/consulta" -Method Post -Body $body -ContentType "application/json"
```

### 3. Después de cambiar código Python (backend/*.py)

```powershell
docker compose restart backend       # ~25s warm-up
```

### 4. Después de cambiar requirements.txt o Dockerfile

```powershell
docker compose build backend
docker compose up -d
```

### 5. Regenerar la evaluación

```powershell
# Ficha documental (necesita chromadb → contenedor)
docker compose run --rm backend python /data/evaluacion/legacy/generar_ficha.py

# Madurez automática OE8 pre-piloto (solo sqlite3 → host o contenedor)
docker compose run --rm backend python /data/evaluacion/madurez_oe8/calcular_madurez.py --auto-only

# Suite completa de tests
docker compose exec backend pytest tests -q   # 403 passed
```

### 6. Ver logs

```powershell
docker compose logs -f backend       # logs del pipeline RAG en vivo
docker compose logs -f llm           # logs de Ollama
docker compose logs -f frontend      # logs de nginx
```

### 7. Ver configuración vigente

```powershell
curl http://localhost:8000/config-publica   # umbral, timeout, modo piloto, etc.
```

### 8. Detener

```powershell
docker compose down                 # detiene contenedores (conserva datos)
docker compose down -v              # elimina también volumen de modelos Ollama
```

**Datos preservados entre reinicios:** `vector_store/`, `registro_interacciones.db`, `evaluacion/`.

## Evaluación de madurez (OE6 / OE8)

Para detalles completos ver `evaluacion/README_EVALUACION.md`.

**Madurez automática pre-piloto** (961 interacciones, 0 respuestas de piloto):

| Dimensión | Puntaje | Nivel |
|---|---:|---|
| Funcional | 2.00 | Inicial |
| Recuperación documental | 3.00 | Básico |
| Explicabilidad y trazabilidad | 2.00 | Inicial |
| Usabilidad | 5.00 | Optimizado |
| Gobernanza y uso responsable | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 2.00 | Inicial |

Métricas crudas: M02=42.7%, M04=22.5%, M06=10.5%, fuentes=56.3%, tiempo prom=5.95s.
Nivel final pendiente de piloto (FASE 6) y combinación 60/40.

> ⚠️ Las 1066 interacciones incluyen **492 filas sintéticas `t-*`** de `test_fase5_logging.py`/`test_config_rag.py` (46%, 2026-09-24–27), detectado en auditoría. No se eliminan (trazabilidad del snapshot FASE 5); los tests ya quedaron aislados a DB temporal para no seguir contaminando. Diagnóstico sin `t-*`: 549 filas, M02=69.9% (solo informativo, no oficial).

### Evaluación del 2026-11-21/22 (corpus V3 + mejoras) — vigente

Banco v3.2 (30 preguntas), 2 semillas. Detalle en `evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md`.

| Métrica | V2 + prompt v2 (antes, 17 Q) | **V3 + mejoras + prompt v3 (ahora, 30 Q)** |
|---|---|---|
| Documento correcto entre las fuentes | 12/17 | 26/30 |
| Artículo correcto entre las fuentes (GT v3.1) | 7/15 | 16/27 |
| Completitud (proxy automático, kappa 0.53 vs humano) | 0.121 | **~0.57** |
| Negativas abstenidas | 6/6 (sept.) | 6/6 |
| Tiempo típico | ~10 s | ~23 s (respuestas ~2× más largas) |

Pendiente: fidelidad de las respuestas largas con evaluación humana; Q02, Q04, Q11 y Q17 siguen recuperando otro documento.

### Banco end-to-end (17 preguntas, corpus v2) — histórico, septiembre 2026

Ejecutar con `powershell -ExecutionPolicy Bypass -File evaluacion/evaluar_modelo.ps1`
(requiere backend en vivo; guarda `evaluacion/resultados_<modelo>.json`):

| Métrica | Corpus v1 (3886 chunks) | Corpus v2 (5126 chunks) + prompt adaptativo |
|---|---|---|
| M02 (respuesta con fuentes) | 9/10* | **16/17** |
| M04 | — | 1/17 (Q04 matrícula: recupera 4 fuentes pero el LLM no redacta) |
| Tiempo promedio | — | 14.81s (máx 43.92s; respuestas más ricas) |
| Q12 "cambiar de carrera" | M04 (chunk a d=0.436) | **M02** (d=0.387) |
| Q11 "constancia de estudios" | M04 | **M02** (cita Art. 53° Admisión) + encuadre |
| Formato | Lista forzada, sin encuadre | Encuadre + directa/lista/tabla según pregunta |

*Bco anterior de 10 preguntas. El re-chunking 1-artículo-por-chunk resolvió
los falsos M04 de Q11 y Q12. Ver `evaluacion/retrieval/calibracion_resumen.md`.

### Evaluación técnica cerrada (PARTE_3, ground truth v3.1) — histórico, corpus V2 (septiembre 2026)

| Nivel | Métrica |
|---|---|
| Retrieval (mismo Top15, GT v3.1) | doc Hit@15 0.882 · art Hit@15 0.600 / Recall 0.489 · final art 0.467/0.400 |
| Generación oficial (17 respuestas congeladas) | completitud micro 0.106 · faithfulness micro 0.918 · citation micro 0.879 · relevancia 2.53 |
| Abstención (banco negativo N01-N06) | accuracy 1.0 (M04×4, M03×2, 0 alucinaciones) |

Próximos pasos: OE7 (validación con expertos), OE8 piloto con usuarios (instrumento 30 ítems listo).

## Solución de problemas

| Error | Causa probable | Solución |
|-------|-----------------|----------|
| `sqlite3.OperationalError: no such column: collections.topic` | Vector store escrito con chromadb 1.x, contenedor con 0.4.22 | `docker compose run --rm backend python /data/evaluacion/retrieval/migrar_esquema_vector_store.py` (ya ejecutado, solo si reinstalas con vector store viejo) |
| `database disk image is malformed` en SQLite | Escritura concurrente host↔backend sobre el bind-mount | **Nunca tocar el .db con el backend corriendo**; respaldos en `backups/` |
| `Anterior: Error al conectar con el servidor` en frontend | Backend no inició o CORS | `docker compose logs backend` |
| `ModuleNotFoundError: chromadb` al ejecutar `generar_ficha.py` desde host | Host sin chromadb | Usar `docker compose run --rm backend python /data/evaluacion/generar_ficha.py` |
| **Respuesta muy lenta** (30+ s) | Modelo descargándose o GPU no disponible | Esperar warm-up (primeras 2-3 consultas). Sin GPU: normal. |
| **Backend no arranca** | `ImportError: sentence_transformers` | `docker compose build backend` (si cambió requirements.txt) |
| **Base vectorial no se encuentra** | `vector_store/` vacío | Copiar desde `oe1_arquitectura_corpus/vector_store/` |
| **Timeouts M06 (> 120 s)** | LLM sobrecargado o CPU bajo | `docker compose down && docker compose up`. Volver a `PROMPT_VERSION=v2-adaptativo` (respuestas más cortas) o reducir `RAG_TOP_K_FINAL`. |
| **El backend no arranca: "Dimensión incompatible"** | `EMBEDDING_MODEL` no corresponde a la colección de `vector_store` | Usar bge-m3 con `corpus_upeu_v3_bgem3`, o mpnet con la V2 respaldada |
| **Frontend no carga en :3000** | Puerto ocupado | `netstat -ano \| findstr ":3000"` |

## Alineación con los Objetivos Educativos (PPI)

| Objetivo | Componente | Evidencia |
|----------|-----------|-----------|
| **OE4** (Reglas y transparencia) | `backend/config.py` + `rag_pipeline.py` | Umbrales, dominios, mensajes M01-M08 definidos y aplicados |
| **OE5** (Sistema conversacional) | Proyecto completo | Frontend + Backend + RAG + LLM + registro anonimizado |
| **OE6** (Instrumentos) | `evaluacion/madurez_oe8/INSTRUMENTOS.md` | 5 instrumentos (ficha, cotejo, gobernanza, rúbrica, SUS) |
| **OE7** (Validación por expertos) | _Pendiente_ | Ejecutar con 3-5 expertos, calcular V de Aiken |
| **OE8** (Madurez del sistema) | `evaluacion/madurez_oe8/calcular_madurez.py --auto-only` | Modelo CMMI--TRL adaptado, 6 dimensiones, 4 niveles, umbrales en `UMBRALES_OE8` |

## Autores

- **David Robert Yucra Mamani**
- **Luis Alberto Quilla López**
- **Gladys Rosaura Yana Pari**

**Asesor:** Mg. Esteban Tocto Cano

**Institución:** Universidad Peruana Unión – Facultad de Ingeniería y Arquitectura
**Escuela:** Profesional de Ingeniería de Sistemas
**Ubicación:** Juliaca, Puno, Perú
**Ciclo:** IX (2025-I)

## Licencia

Proyecto académico y educativo. Contacta con los autores para cualquier uso comercial.

---

**Última actualización:** 23 de noviembre de 2026 (Exp. B con `llama3.2:3b`, `qwen3:4b-instruct`, `gemma3:4b`; aprobación del asesor; guía de entrega a evaluadores). Antes, 22 de noviembre (migración a corpus V3 + bge-m3, calibración, mejoras del chatbot, prompt v3-completo, banco v3.2 y avance de la Revisión 3: estadística, S0, experimentos A y C preliminares, herramientas del gold set)
**Estado:** OE4-5-6 completados · PARTE_3 FASE 1-5 cerradas (retrieval/generación/humana/negativo/auto) · OE7 pendiente · OE8 FASE 6 pendiente de datos
**Próximos pasos:** Revisión 3: anotación del gold set por el equipo (`evaluacion/ENTREGA_EVALUADORES.md`); validar instrumentos con expertos (OE7) y ejecutar piloto con usuarios (OE8, instrumento v1 listo)
