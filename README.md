# OE5 – Sistema Conversacional Universitario con IA Generativa Explicable

Este proyecto implementa el **Objetivo Específico 5** del PPI:
> *Implementar el sistema conversacional web integrando IA generativa con recuperación documental y presentación de fuentes verificables para explicabilidad y trazabilidad.*

El sistema permite a estudiantes y personal de la Universidad Peruana Unión (UPeU) realizar consultas en lenguaje natural sobre reglamentos, trámites y documentos institucionales, obteniendo respuestas fundamentadas en el corpus documental oficial con trazabilidad completa de las fuentes.

## Estado actual del proyecto

| Objetivo específico | Estado | Evidencia |
|---|---|---|
| **OE4** Reglas de transparencia y explicabilidad | ✅ 100 % (T01/T02 fijados por decisión del equipo) | `backend/config.py` + `rag_pipeline.py` |
| **OE5** Sistema conversacional con IA explicable | ✅ 100 % | Frontend + Backend + RAG + LLM + registro |
| **OE6** Instrumentos de evaluación de madurez | ✅ 100 % | `evaluacion/INSTRUMENTOS.md` (5 instrumentos) |
| **OE7** Validación por expertos (V de Aiken) | ⏳ Pendiente (proceso) | Ejecutar con 3-5 expertos externos |
| **OE8** Cálculo de madurez y piloto con usuarios | 🟡 En curso (infraestructura lista) | `evaluacion/reporte_madurez.md` (Básico – 2.83/5.00) |

## Estructura del proyecto

```
oe5_chatbot_upeu/
├── llm/                              # Servicio de IA generativa (Llama 3 con Ollama)
│   ├── Dockerfile
│   ├── entrypoint.sh                 # Pre-pull + warm-up del modelo en arranque
│   └── .gitignore
├── backend/                          # API REST (FastAPI) y pipeline RAG
│   ├── app.py                        # Endpoints: /consulta, /bienvenida, /historial,
│   │                                 #            /documentos, /politica-privacidad,
│   │                                 #            /salud, /config-publica
│   ├── config.py                     # Umbrales, mensajes M01-M08, dominios A-E,
│   │                                 # keywords, patrones PII, sesión y CORS
│   ├── logger.py                     # Registro ANONIMIZADO + seudonimización
│   │                                 # (Ley 29733) + 4 tablas de evaluación
│   ├── rag_pipeline.py               # Pipeline RAG: validador + retrieval + LLM
│   │                                 # (PROMPT v2) + truncado + retry policy
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
│   │       ├── Message.js            # Render por tipo M02-M08 con etiqueta visual
│   │       └── SourceBadge.js        # Sello editorial con doc + sección + versión
│   ├── nginx.conf
│   ├── package.json
│   ├── Dockerfile                    # Multi-stage (build + nginx)
│   └── .gitignore
├── evaluacion/                       # Instrumentos y cálculo de madurez (OE6/OE8)
│   ├── INSTRUMENTOS.md               # 5 instrumentos: ficha, cotejo funcional,
│   │                                 # gobernanza, rúbrica explicabilidad, SUS
│   ├── README_EVALUACION.md          # Flujo de trabajo de evaluación
│   ├── ficha_documental.md           # Auto-generada (corpus indexado)
│   ├── reporte_madurez.md            # Auto-generada (cálculo CMMI--TRL)
│   ├── resultados_madurez.csv        # Auto-generada (puntajes por dimensión)
│   ├── generar_ficha.py              # Auto-genera ficha_documental.md
│   ├── calcular_madurez.py           # Auto-genera reporte_madurez.md + CSV
│   ├── migrar_banco.py               # One-shot CSV → tabla `banco_preguntas`
│   └── migrar_esquema_vector_store.py # One-shot: arregla esquema chromadb
├── docs/
│   └── FLUJO_CONSULTA.txt            # Diagrama del flujo de una consulta
├── vector_store/                     # Base vectorial ChromaDB (corpus persiste aquí)
│   ├── chroma.sqlite3                # 48 documentos, 3886 chunks
│   └── [uuid]/
├── registro_interacciones.db         # 4 tablas: interacciones, banco_preguntas,
│                                     #   evaluacion_piloto, evaluacion_automatica
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
| **Modelo de embeddings** | Sentence-Transformers | `paraphrase-multilingual-MiniLM-L12-v2` (384 dims) |
| **Base vectorial** | ChromaDB | 0.4.22 (distancia coseno) |
| **Modelo LLM** | Llama 3 (8B) | Servido por Ollama, `num_predict=1024`, `temperature=0.2` |
| **Contenedor LLM** | Ollama | latest con CUDA v13 |
| **GPU (opcional)** | NVIDIA CUDA | v13 (RTX 4050 compatible) |
| **Registro de datos** | SQLite 3 | 4 tablas (ver `evaluacion/README_EVALUACION.md`) |
| **Frontend build tool** | Node.js + npm | 18-alpine en contenedor |

## Requisitos previos

1. **Docker Desktop** instalado y funcionando
   - Modo WSL 2 (recomendado) o Hyper-V
   - 20 GB de espacio libre (imágenes + modelo Llama 3 ~ 4-12 GB)
2. **(Recomendado) GPU NVIDIA** con drivers CUDA v13 instalados
   - Sin GPU: respuestas en ~30-60 s
   - Con GPU: respuestas en ~5-15 s
3. **Carpeta `vector_store/`** con el corpus indexado
   - Se obtiene del proyecto `oe1_arquitectura_corpus/vector_store/`
   - Tamaño: ~100-500 MB (48 documentos → 3886 chunks)
4. **Python 3.10+ y `chromadb==0.4.22`** (opcional, solo si quieres regenerar la ficha documental desde host — ver `evaluacion/README_EVALUACION.md`)

## Configuración

Parámetros editables en `backend/config.py`:

```python
UMBRAL_DISTANCIA_COSENO = 0.35     # Distancia máxima aceptable (T01)
TOP_K_FRAGMENTOS = 5               # Chunks a recuperar
MAX_PALABRAS_RESPUESTA = 500       # T03: truncado a 500 palabras
TIMEOUT_RESPUESTA = 50             # T04: segundos por intento del LLM
MODO_PILOTO = True                 # Activa T07 (límite 10 preguntas/sesión)
```

Parámetros específicos del LLM en `rag_pipeline.py`:

```python
MAX_CHARS_POR_FRAGMENTO = 700      # Tamaño máx. de cada chunk en el prompt
num_predict = 1024                 # Tokens máx. de respuesta generada
temperature = 0.2                  # Creatividad baja (factual)
```

**Variables de entorno (docker-compose.yml):**

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://llm:11434` | URL del servicio Ollama |
| `OLLAMA_MODEL` | `llama3` | Modelo a usar |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS (lista separada por comas) |
| `MODO_PILOTO` | `true` | Activa límite T07 y `debug_distancias` |
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

**Primera ejecución (10-30 min):** descarga imágenes base, modelo Llama 3, instala dependencias.

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
   - Embedding con `paraphrase-multilingual-MiniLM-L12-v2` (multilingüe, 384 dim)
   - Retrieval top-5 en ChromaDB
   - Filtro por umbral T01 (UMBRAL=0.35)
   - Truncado de cada chunk a 700 chars (evita prompts enormes)
   - LLM con PROMPT v2 (USA TODAS las fuentes + citas por viñeta + lista vertical)
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
| `interacciones` | Log de cada consulta (anonimizado) | Backend automático |
| `banco_preguntas` | Banco canónico de preguntas de prueba | `migrar_banco.py` (one-shot desde CSV) |
| `evaluacion_piloto` | Puntajes Likert 1-5 de usuarios reales | INSERT manual o formulario |
| `evaluacion_automatica` | Snapshots históricos de madurez | `calcular_madurez.py` (1 fila por ejecución) |

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
| **T01 Umbral similitud 0.70** | 🟡 Parcial | Se usa distancia 0.35 (≈ similitud 0.65) por decisión del equipo |
| **T02 Top-k 1–3** | 🟡 Parcial | Se mantiene k=5 por decisión del equipo |
| **T03 Máx 350 palabras** | ✅ | `_truncar_palabras` añade `(…)` (configurado a 500) |
| **T04 Timeout 15 s** | ✅ | `urllib.request` + `FutTimeout` → M06 (configurado a 40 s) |
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

## Evaluación de madurez (OE6 / OE8)

Para detalles completos ver `evaluacion/README_EVALUACION.md`. Resumen:

```powershell
# Desde el host (solo lee SQLite, no necesita chromadb en host)
python evaluacion/calcular_madurez.py

# Desde el contenedor (recomendado para generar_ficha.py)
docker compose run --rm backend python /data/evaluacion/generar_ficha.py
```

**Madurez actual** (149 interacciones, 0 evaluaciones de piloto, auto-calculada):

| Dimensión | Puntaje | Nivel |
|---|---:|---|
| Funcional | 2.00 | Inicial |
| Recuperación documental | 2.00 | Inicial |
| Explicabilidad y trazabilidad | 2.00 | Inicial |
| Usabilidad | 4.00 | Gestionado |
| Gobernanza y uso responsable | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 2.00 | Inicial |
| **Global** | **2.83** | **Básico** |

Próximos pasos: completar OE7 (validación de instrumentos con expertos, V de Aiken) y OE8 (piloto con usuarios reales, INSERT en `evaluacion_piloto`).

## Detener el sistema

```powershell
docker compose down              # detiene contenedores (conserva datos)
docker compose down -v           # elimina también el volumen de modelos Ollama
```

**Datos preservados entre reinicios:** `vector_store/`, `registro_interacciones.db`, `evaluacion/`. Solo se borra el volumen anónimo `llm_data` con `down -v` (los modelos se redescargan).

## Solución de problemas

| Error | Causa probable | Solución |
|-------|-----------------|----------|
| `sqlite3.OperationalError: no such column: collections.topic` | Vector store escrito con chromadb 1.x, contenedor con 0.4.22 | `python evaluacion/migrar_esquema_vector_store.py` (idempotente) |
| `Anterior: Error al conectar con el servidor` en frontend | Backend no inició o CORS | `docker compose logs backend` |
| `ModuleNotFoundError: chromadb` al ejecutar `generar_ficha.py` desde host | Host sin chromadb | Usar `docker compose run --rm backend python /data/evaluacion/generar_ficha.py` |
| **Respuesta muy lenta** (30+ s) | Llama 3 descargándose o GPU no disponible | Esperar warm-up (primeras 2-3 consultas). Sin GPU: normal. |
| **Backend no arranca** | `ImportError: sentence_transformers` | `docker compose build backend` (si cambió requirements.txt) |
| **Base vectorial no se encuentra** | `vector_store/` vacío | Copiar desde `oe1_arquitectura_corpus/vector_store/` |
| **Timeouts M06 (>30 s)** | LLM sobrecargado o CPU bajo | `docker compose down && docker compose up`. Reducir `TOP_K_FRAGMENTOS`. |
| **Frontend no carga en :3000** | Puerto ocupado | `netstat -ano \| findstr ":3000"` |

## Alineación con los Objetivos Educativos (PPI)

| Objetivo | Componente | Evidencia |
|----------|-----------|-----------|
| **OE4** (Reglas y transparencia) | `backend/config.py` + `rag_pipeline.py` | Umbrales, dominios, mensajes M01-M08 definidos y aplicados |
| **OE5** (Sistema conversacional) | Proyecto completo | Frontend + Backend + RAG + LLM + registro anonimizado |
| **OE6** (Instrumentos) | `evaluacion/INSTRUMENTOS.md` | 5 instrumentos (ficha, cotejo, gobernanza, rúbrica, SUS) |
| **OE7** (Validación por expertos) | _Pendiente_ | Ejecutar con 3-5 expertos, calcular V de Aiken |
| **OE8** (Madurez del sistema) | `evaluacion/calcular_madurez.py` + `reporte_madurez.md` | Modelo CMMI--TRL adaptado, 6 dimensiones, 4 niveles |

## Autores

- **David Robert Yucra Mamani**
- **Gladys Rosaura Yana Pari**
- **Luis Alberto Quilla López**

**Asesor:** Mg. Esteban Tocto Cano

**Institución:** Universidad Peruana Unión – Facultad de Ingeniería y Arquitectura
**Escuela:** Profesional de Ingeniería de Sistemas
**Ubicación:** Juliaca, Puno, Perú
**Ciclo:** IX (2025-I)

## Licencia

Proyecto académico y educativo. Contacta con los autores para cualquier uso comercial.

---

**Última actualización:** 3 de junio de 2026
**Estado:** OE4-5-6 completados · OE7 pendiente (proceso) · OE8 en curso (Básico – 2.83/5.00)
**Próximos pasos:** Validar instrumentos con expertos (OE7) y ejecutar piloto con usuarios (OE8)
