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
│   ├── config.py                     # RAG_DISTANCE_THRESHOLD=0.40, TOP_K_RAW=15/FINAL=4,
│   │                                 # mensajes M01-M08, dominios A-E, keywords, PII, CORS
│   ├── logger.py                     # Registro ANONIMIZADO + seudonimización (Ley 29733)
│   │                                 # + migraciones de ~20 tablas de evaluación
│   ├── rag_pipeline.py               # Pipeline RAG: validadores + retrieval + re-ranking
│   │                                 # (boost keyword 0.07) + LLM (PROMPT v2-adaptativo)
│   │                                 # + truncado + retry policy + guardrails de citas
│   ├── context_builder.py            # Construcción determinística de contexto/fuentes (Fase 2)
│   ├── validators_evaluacion.py      # source_validity / citation_match determinísticos
│   ├── tests/                        # Suite pytest (312 tests en verde)
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
│   ├── banco/                        # Ground truth: preguntas_comparacion.json (17 Q),
│   │                                 # sincronizar_banco.py, CHANGELOG_GROUNDTRUTH_V31.md
│   ├── retrieval/                    # evaluar_rag.py, calibrar_umbral.py, métricas EXP_*.csv
│   ├── generacion/                   # baseline_generacion_v3_oficial.py, harnesses, JSON/CSV
│   ├── humana/                       # Fichas Q01-Q17 (fichas_humanas_v31/, 66 puntos),
│   │                                 # importar_ficha_humana.py, calcular_metricas_humanas.py,
│   │                                 # GUIA_EVALUACION_HUMANA_V3.md
│   ├── madurez_oe8/                  # calcular_madurez.py, instrumento piloto 30 ítems,
│   │                                 # importar_piloto.py, reporte_madurez.md
│   └── legacy/                       # Scripts/resultados históricos (evaluar_modelo.ps1…)
├── docs/                             # Especificación del proyecto
│   ├── PARTE_2_CHATBOT_RAG.md        # Fases 1-7 del chatbot RAG
│   ├── PARTE_3_EVALUACION_MADUREZ.md # Fases 1-6 de evaluación y madurez OE8
│   └── FLUJO_CONSULTA.txt            # Diagrama del flujo de una consulta
├── vector_store/                     # Base vectorial ChromaDB (corpus persiste aquí)
│   ├── chroma.sqlite3                # corpus_upeu_v2, 5126 chunks, mpnet-768
│   └── [uuid]/
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
| `./vector_store`             | `/data/vector_store`        | ChromaDB (corpus)                    |
| `./registro_interacciones.db`| `/data/registro_interacciones.db` | SQLite con log y evaluación   |
| (volumen anónimo)            | `/root/.ollama`             | Modelos LLM descargados              |

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
| **Modelo de embeddings** | Sentence-Transformers | `paraphrase-multilingual-mpnet-base-v2` (768 dims, ganador 10/10) |
| **Base vectorial** | ChromaDB | 0.4.22, colección `corpus_upeu_v2`, distancia coseno |
| **Modelo LLM** | Qwen2.5-7B | Servido por Ollama, `num_predict=1024`, `temperature=0.2` |
| **Contenedor LLM** | Ollama | latest con CUDA v13. Modelo por defecto: Qwen2.5-7B |
| **GPU (opcional)** | NVIDIA CUDA | v13 (RTX 4050 compatible) |
| **Comparativa LLM** | Llama 3 8B vs Qwen2.5-7B | `evaluacion/madurez_oe8/COMPARACION_LLMS.md` **→ Se adoptó Qwen2.5-7B** |
| **Registro de datos** | SQLite 3 | ~20 tablas (ver `evaluacion/README_EVALUACION.md`) |
| **Suite de tests** | pytest (Docker) | 312 passed |
| **Frontend build tool** | Node.js + npm | 18-alpine en contenedor |

## Requisitos previos

1. **Docker Desktop** instalado y funcionando
   - Modo WSL 2 (recomendado) o Hyper-V
    - 20 GB de espacio libre (imágenes + modelo Qwen2.5-7B ~ 4.7 GB)
2. **(Recomendado) GPU NVIDIA** con drivers CUDA v13 instalados
   - Sin GPU: respuestas en ~30-60 s
   - Con GPU: respuestas en ~5-15 s
3. **Carpeta `vector_store/`** con el corpus indexado
   - Se obtiene del proyecto `oe1_arquitectura_corpus/vector_store/`
   - Tamaño: ~100-500 MB (corpus_upeu_v2 → 5126 chunks, 1 artículo = 1 chunk)
4. **Python 3.10+ y `chromadb==0.4.22`** (opcional, solo si quieres regenerar la ficha documental desde host — ver `evaluacion/README_EVALUACION.md`)

## Configuración

Parámetros editables en `backend/config.py`:

```python
UMBRAL_DISTANCIA_COSENO = 0.40     # Distancia coseno máxima aceptable (boosted)
TOP_K_FRAGMENTOS = 4               # Máx. chunks que llegan al LLM (filtro por umbral primero)
TOP_K_RAW = 15                     # Chunks iniciales del retrieval (3x TOP_K)
_MAX_BOOST_POR_KEYWORD = 0.07      # Descuento de distancia por match keyword
MAX_PALABRAS_RESPUESTA = 500       # T03: truncado a 500 palabras
TIMEOUT_RESPUESTA = 50             # T04: segundos por intento del LLM
MODO_PILOTO = True                 # Activa T07 (límite 10 preguntas/sesión)
DEBUG_LOG = True                   # Expone debug_distancias en /consulta
MARGEN_FUERA_DOMINIO = 0.10        # R04: umbral extra para "fuera de dominio"
```

Parámetros específicos del LLM en `rag_pipeline.py`:

```python
MAX_CHARS_POR_FRAGMENTO = 700      # Tamaño máx. de cada chunk en el prompt
num_predict = 1024                 # Tokens máx. de respuesta generada
temperature = 0.2                  # Creatividad baja (factual)

# Re-ranking híbrido (rag_pipeline.py):
# - Recupera TOP_K_RAW=15 chunks por distancia coseno
# - Aplica boost de 0.07 por cada keyword de la query presente en
#   `meta["documento"]` (case-insensitive, substring)
# - Ordena TODO el pool por distancia boosted y aplica el filtro UMBRAL
#   sobre el pool completo (el umbral decide la relevancia, NO el recorte)
# - Entrega al LLM como máximo TOP_K_FRAGMENTOS=4 chunks que pasaron el umbral
# - Usa distancia boosted (no original) para el filtro UMBRAL:
#   si el sistema cree que un chunk es relevante por keywords,
#   no debe descartarlo por su distancia coseno.
# Esto resuelve el problema de documentos pequeños/poco frecuentes
# que pierden ante documentos con mucho vocabulario solapado, y evita
# que un chunk relevante rankeado #4+ se descarte antes del umbral.
```

**Variables de entorno (docker-compose.yml):**

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://llm:11434` | URL del servicio Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Modelo a usar (ver comparativa en `evaluacion/COMPARACION_LLMS.md`) |
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
   - Embedding con `paraphrase-multilingual-mpnet-base-v2` (multilingüe, 768 dim)
   - Retrieval top-15 en ChromaDB (TOP_K_RAW=15, 3x top-K final)
   - Re-ranking por keywords: boost de 0.07 por match en `meta["documento"]`
   - Selección top-3 por distancia boosted, filtro UMBRAL=0.40 (sobre boosted)
   - Truncado de cada chunk a 700 chars (evita prompts enormes)
   - LLM con PROMPT v2 (USA TODAS las fuentes + citas por viñeta + lista vertical)
   - Post-proceso: `•` → `- ` (markdown) + eliminación de meta-frases
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
| `banco_preguntas` | Banco 17 Q v3 + P01-P08 históricos | `evaluacion/banco/sincronizar_banco.py` |
| `groundtruth_v31_*` | Ground truth oficial v3.1 (17 Q / 66 puntos) | Curación auditada (congelado) |
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
| **T01 Umbral similitud 0.70** | 🟡 Parcial | Se usa distancia 0.40 (≈ similitud 0.60) por decisión del equipo |
| **T02 Top-k 1–3** | 🟡 Parcial | Se mantiene k=3 por decisión del equipo |
| **T03 Máx 350 palabras** | ✅ | `_truncar_palabras` añade `(…)` (configurado a 500) |
| **T04 Timeout 15 s** | ✅ | `urllib.request` + `FutTimeout` → M06 (configurado a 50 s) |
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
docker compose exec backend pytest tests -q   # 312 passed
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

### Banco end-to-end (17 preguntas, corpus v2)

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

### Evaluación técnica cerrada (PARTE_3, ground truth v3.1)

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
| **Timeouts M06 (>30 s)** | LLM sobrecargado o CPU bajo | `docker compose down && docker compose up`. Reducir `TOP_K_FRAGMENTOS`. |
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

**Última actualización:** 27 de septiembre de 2026
**Estado:** OE4-5-6 completados · PARTE_3 FASE 1-5 cerradas (retrieval/generación/humana/negativo/auto) · OE7 pendiente · OE8 FASE 6 pendiente de datos
**Próximos pasos:** Validar instrumentos con expertos (OE7) y ejecutar piloto con usuarios (OE8, instrumento v1 listo)
