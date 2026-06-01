# OE5 – Sistema Conversacional Universitario con IA Generativa Explicable

Este proyecto implementa el **Objetivo Específico 5** del PPI:
> *Implementar el sistema conversacional web integrando IA generativa con recuperación documental y presentación de fuentes verificables para explicabilidad y trazabilidad.*

El sistema permite a estudiantes y personal de la Universidad Peruana Unión (UPeU) realizar consultas en lenguaje natural sobre reglamentos, trámites y documentos institucionales, obteniendo respuestas fundamentadas en el corpus documental oficial con trazabilidad completa de las fuentes.

## Estructura del proyecto

```
oe5_chatbot_upeu/
├── llm/                              # Servicio de IA generativa (Llama 3 con Ollama)
│   ├── Dockerfile
│   ├── entrypoint.sh                 # Pre-pull del modelo en arranque
│   └── .gitignore
├── backend/                          # API REST (FastAPI) y pipeline RAG
│   ├── app.py                        # Endpoints: /consulta, /bienvenida, /historial,
│   │                                 #            /documentos, /politica-privacidad,
│   │                                 #            /salud, /config-publica
│   ├── config.py                     # Umbrales, mensajes M01-M07, dominios A-E,
│   │                                 # keywords, patrones PII, sesión y CORS
│   ├── logger.py                     # Registro ANONIMIZADO con sesion_id (Ley 29733)
│   ├── rag_pipeline.py               # Pipeline RAG: validador dominio + retrieval +
│   │                                 # filtro umbral + LLM con timeout + truncado
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
│   │       ├── Message.js            # Render por tipo M02-M06 con etiqueta visual
│   │       └── SourceBadge.js        # Sello editorial con doc + sección + versión
│   ├── nginx.conf                    # Config para servir el build de producción
│   ├── package.json
│   ├── Dockerfile                    # Multi-stage (build + nginx)
│   └── .gitignore
├── vector_store/                     # Base vectorial ChromaDB (corpus persiste aquí)
│   ├── chroma.sqlite3
│   └── [uuid]/
├── registro_interacciones.db         # Base de datos de interacciones anonimizadas
├── docker-compose.yml                # Orquestación con healthchecks
├── .gitignore                        # Ignores a nivel proyecto (root)
└── README.md                         # Este archivo
```

## Tecnologías utilizadas

| Componente | Tecnología | Versión/Detalles |
|------------|------------|------------------|
| **Contenerización** | Docker + Docker Compose | - |
| **Frontend** | React | 18.3.1 |
| **Renderizado en frontend** | react-markdown | 10.1.0 (soporte para Markdown en respuestas) |
| **Backend / API** | FastAPI | 0.110.0 |
| **Servidor ASGI** | Uvicorn | 0.27.0 |
| **Lenguaje (backend)** | Python | 3.10 |
| **Orquestación RAG** | LangChain | 0.1.0 + community 0.0.10 |
| **Modelo de embeddings** | Sentence-Transformers | `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, multilingüe) |
| **Base vectorial** | ChromaDB | 0.4.22 (distancia coseno) |
| **Modelo LLM** | Llama 3 | Servido por Ollama |
| **Contenedor LLM** | Ollama | latest (con soporte CUDA) |
| **GPU (opcional)** | NVIDIA CUDA | v13 (RTX 4050 compatible) |
| **Registro de datos** | SQLite 3 | Persistencia de interacciones |
| **Frontend build tool** | Node.js + npm | 18-alpine en contenedor |

## Requisitos previos

1. **Docker Desktop** instalado y funcionando
   - Modo WSL 2 (recomendado) o Hyper-V
   - 20 GB de espacio libre en disco (imágenes + modelo Llama 3 ~ 10-12 GB)

2. **Node.js 18+** (si deseas desarrollar sin Docker)
   - npm incluido

3. **Python 3.10+** (si deseas ejecutar backend localmente sin Docker)

4. **(Recomendado) GPU NVIDIA** con drivers CUDA instalados
   - Sin GPU: tiempos de respuesta serán mayores (~30-60s por consulta)
   - Con GPU: respuestas en 5-15 segundos

5. **Carpeta `vector_store/`** generada previamente
   - Debe contener la base vectorial de ChromaDB (corpus de UPeU)
   - Se obtiene del proyecto `oe1_arquitectura_corpus/vector_store/`
   - **Tamaño estimado:** 100-500 MB (según cantidad de documentos indexados)

## Configuración

Todos los parámetros técnicos y de negocio se encuentran en **`backend/config.py`**:

```python
# Umbrales técnicos (FIJOS por decisión del equipo)
UMBRAL_DISTANCIA_COSENO = 0.32      # Equivale a similitud coseno ~0.68
TOP_K_FRAGMENTOS = 5                 # Cantidad de chunks recuperados
MAX_PALABRAS_RESPUESTA = 350         # Implementado: trunca con "(…)" (T03)
TIMEOUT_RESPUESTA = 15               # Implementado: con M06 si excede (T04)

# Dominio permitido (categorías reales del corpus indexado)
DOMINIO_CATEGORIAS = ["A", "B", "C", "D", "E"]

# Mensajes de transparencia (M01-M07) — alineados con sección 4 del OE4
```

**Variables de entorno aceptadas por el backend:**

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://llm:11434` | URL del servicio Ollama |
| `OLLAMA_MODEL` | `llama3` | Nombre del modelo a usar |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS (lista separada por comas) |
| `MODO_PILOTO` | `true` | Activa límite T07 y debug_distancias |
| `LIMITE_PREGUNTAS_SESION` | `10` | Límite de preguntas por sesión piloto (T07) |

**Para ajustar valores:** edita `backend/config.py` o pasa variables al `docker-compose.yml`, luego:
```powershell
docker-compose up --build
```

## Instalación y ejecución

### Opción 1: Con Docker (Recomendado)

1. **Clona el repositorio:**
   ```powershell
   git clone https://github.com/LuisAlbertoQ/ChatUpeuCorpus.git
   cd ChatUpeuCorpus
   ```

2. **Verifica que `vector_store/` existe con contenido:**
   ```powershell
   ls vector_store/
   ```
   Si está vacío, copia desde el proyecto `oe1_arquitectura_corpus/`.

3. **Construye e inicia los servicios:**
   ```powershell
   docker-compose up --build
   ```

   **Primera ejecución:** 
   - Descarga imágenes base (Python 3.10, Node 18, Ollama)
   - Descarga modelo Llama 3 (~4 GB)
   - Instala dependencias
   - **Tiempo estimado:** 10-30 minutos (depende de conexión y GPU)

4. **Verifica que los 3 servicios estén corriendo:**
   ```powershell
   docker-compose ps
   ```
   Resultado esperado:
   ```
   NAME      IMAGE                COMMAND                 STATUS
   llm       oe5_chatbot-llm      "/entrypoint.sh"        Up
   backend   oe5_chatbot-backend  "uvicorn app:app..."    Up
   frontend  oe5_chatbot-frontend "npm start"             Up
   ```

5. **Accede a la interfaz web:**
   - Abre navegador: **[http://localhost:3000](http://localhost:3000/)**
   - Interfaz lista cuando ves el título "Chatbot UPeU"

6. **Prueba la API directamente (PowerShell):**
   ```powershell
   $body = @{ pregunta = "¿Cómo inscribir un proyecto de tesis?" } | ConvertTo-Json
   Invoke-RestMethod -Uri http://localhost:8000/consulta -Method Post `
     -Body $body -ContentType "application/json"
   ```

### Opción 2: Ejecución local (sin Docker) - Avanzado

**No recomendado para principiantes.** Requiere:
- Python 3.10, Node.js 18, Ollama installado localmente
- Variables de entorno configuradas
- Gestión manual de dependencias

## Uso del sistema

### Flujo típico de una consulta:

1. **Usuario escribe pregunta** en la caja de texto (ej: "¿Cuáles son los plazos de inscripción?")
2. **Frontend envía POST** a `http://localhost:8000/consulta`
3. **Backend ejecuta pipeline RAG:**
   - Genera embedding de la pregunta con `SentenceTransformer`
   - Busca en ChromaDB los 5 fragmentos más similares (distancia coseno < 0.32)
   - Si encuentra fragmentos → pasa al LLM para generar respuesta
   - Si NO encuentra → retorna mensaje M04 ("No encontré información")
4. **Llama 3 genera respuesta** en base a fragmentos + prompt del sistema
5. **Sistema retorna:**
   - Respuesta generada
   - Lista de fuentes (documento + categoría)
   - Tipo de mensaje (M02 = con fuentes, M04 = sin información, etc.)
6. **Frontend renderiza** respuesta con markdown + listado de fuentes
7. **Backend registra** interacción en SQLite (pregunta, respuesta, fuentes, tiempo, etc.)

### Puntos importantes:

- ✅ Las respuestas **SIEMPRE** están respaldadas en documentos del corpus
- ✅ Si la información no existe → el sistema lo dice honestamente (M04)
- ✅ Todas las interacciones se almacenan para evaluación posterior (OE8)
- ✅ Multilingüe: el modelo de embeddings soporta español, inglés, portugués, etc.

## Registro de interacciones e historial

El backend almacena **automáticamente** cada interacción en SQLite (`registro_interacciones.db`).

### Campos registrados por consulta:

| Campo | Descripción |
|-------|-------------|
| `timestamp` | ISO 8601 (ej: 2025-06-15T14:23:45.123456) |
| `pregunta` | Texto de la pregunta del usuario |
| `respuesta` | Texto completo de la respuesta generada |
| `fuentes` | Lista de documentos utilizados (JSON) |
| `tiempo_respuesta` | Segundos que tardó el pipeline |
| `umbral_usado` | Valor de `UMBRAL_DISTANCIA_COSENO` usado |
| `tipo_mensaje` | M02 (con info), M04 (sin info), M06 (error), etc. |

### Descargar historial en CSV:

```powershell
# Opción 1: Desde navegador
# Abre: http://localhost:8000/historial

# Opción 2: Desde PowerShell
$csv = Invoke-RestMethod -Uri http://localhost:8000/historial
$csv.csv | Out-File -Encoding UTF8 historial.csv
```

El archivo persiste en disco aunque detengas los contenedores, gracias al volumen definido en `docker-compose.yml`.

## API – Endpoints expuestos

| Método | Ruta | Propósito | Documento OE4 |
|---|---|---|---|
| `POST` | `/consulta` | Pipeline RAG → respuesta + fuentes + tipo_mensaje | RF01, RF03–RF05, T01–T08 |
| `GET`  | `/bienvenida` | Mensaje M01 (aviso inicial) | M01 |
| `GET`  | `/config-publica` | Parámetros visibles al frontend (umbrales, dominios, mensajes) | RNF05 |
| `GET`  | `/historial?sesion_id=` | Exporta el historial en CSV (filtrable por sesión) | RF06, RF07 |
| `DELETE` | `/historial/{sesion_id}` | Derecho al olvido (sección 3.4 OE4) | 3.4 |
| `GET`  | `/documentos` | Introspección del corpus indexado | – |
| `GET`  | `/politica-privacidad` | Texto de la política (Ley 29733) | 3.3 |
| `GET`  | `/salud` | Healthcheck (usado por Docker) | RNF02 |

## Cumplimiento del documento OE4 v2.0

| Cláusula | Estado | Implementación |
|---|---|---|
| **D01–D06 → Dominios A–E reales del corpus** | OK | `config.MAPEO_CATEGORIAS` + `KEYWORDS_DOMINIO` |
| **R01–R03 Restricciones de contenido** | OK | Prompt restrictivo en `rag_pipeline.PROMPT` |
| **R04 Fuera de dominio** | OK | Validador por keywords + umbral en `_es_fuera_dominio_por_keywords` |
| **R05 Sin corpus → sin respuesta** | OK | Filtro T01 + emisión M04 |
| **R07 Contenido ético/legal** | OK | `KEYWORDS_ETICA` → M03 |
| **3.2 Anonimización** | OK | `logger.anonimizar` aplica patrones PII antes de INSERT |
| **3.3 Ley 29733** | OK | `backend/POLITICA_PRIVACIDAD.md` servido por `/politica-privacidad` |
| **3.4 Derecho al olvido** | OK | `DELETE /historial/{sesion_id}` |
| **M01 Bienvenida** | OK | `/bienvenida` consumido por el frontend al montar |
| **M02 Respuesta con fuentes** | OK | Concatenado al final de respuestas exitosas |
| **M03 Fuera de dominio** | OK | Validador → tipo_mensaje=M03 |
| **M04 Baja certeza** | OK | Cuando todas las distancias > umbral |
| **M05 Pregunta ambigua / multi-intención** | OK | `_pregunta_es_ambigua` + `_es_multi_intencion` |
| **M06 Error técnico** | OK | `try/except` + timeout T04 |
| **M07 Aviso permanente** | OK | Footer fijo con texto exacto |
| **T01 Umbral 0.70 (sim)** | PARCIAL | Se usa distancia 0.32 (≈ similitud 0.68) por decisión del equipo |
| **T02 Top-k 1–3** | PARCIAL | Se mantiene k=5 por decisión del equipo |
| **T03 Máx 350 palabras** | OK | `_truncar_palabras` añade `(…)` y nota |
| **T04 Timeout 15 s** | OK | `ThreadPoolExecutor` + `FutTimeout` → M06 |
| **T05 Generación condicional** | OK | Solo si hay fragmentos válidos |
| **T06 Multi-intención** | OK | Heurística de conectores + interrogativas |
| **T07 Límite 10 preguntas/sesión piloto** | OK | `sesion_id` + `contar_preguntas_sesion` + HTTP 429 |
| **T08 Fuentes enriquecidas** | OK | `_formatear_fuente` extrae artículo + versión + año + categoría |
| **RNF01 Usabilidad** | OK | UI editorial cohesiva + estados + responsivo |
| **RNF02 Rendimiento** | OK | Timeout + healthchecks + pre-pull del modelo |
| **RNF03 Sin PII** | OK | Anonimización automática |
| **RNF04 Trazabilidad** | OK | SourceBadge con sección + versión + categoría |
| **RNF05 Modificabilidad** | OK | `config.py` + variables de entorno |
| **RNF06 Transparencia** | OK | M01 al inicio + M07 permanente |

## Detener el sistema

Para detener todos los servicios:

```powershell
# Opción 1: Ctrl+C en la terminal donde corre docker-compose up

# Opción 2: Ejecuta en otra terminal
docker-compose down
```

**Importante:** `docker-compose down` no borra los volúmenes:
- ✅ `vector_store/` persiste (corpus RAG)
- ✅ `registro_interacciones.db` persiste (historial)
- ❌ `llm_data/` se borra (es anónimo, modelos se redescargán en próximo `up`)

Para limpiar TODO (datos incluidos):
```powershell
docker-compose down -v
```

## Solución de problemas

| Error | Causa probable | Solución |
|-------|-----------------|----------|
| **"Error al conectar con el servidor"** en frontend | Backend no inició o CORS no habilitado | Verifica `docker-compose ps`, comprueba logs: `docker-compose logs backend` |
| **Backend no arranca** - `ImportError: sentence_transformers` | Versión incompatible o pip error | Asegúrate que `requirements.txt` tenga `sentence-transformers>=2.7.0` |
| **Respuesta muy lenta** (30+ segundos) | Llama 3 descargándose o GPU no disponible | Espera a que el modelo descargue (primeras 2-3 consultas son lentas). Sin GPU: tiempo es normal. |
| **"Error 404: /consulta"** | Backend compiló mal o port está ocupado | Comprueba que FastAPI escucha en 8000: `docker-compose logs backend \| findstr "Uvicorn"` |
| **Base vectorial no se encuentra** | Falta `vector_store/` o está vacía | Copia desde `oe1_arquitectura_corpus/vector_store/` |
| **Frontend no carga en localhost:3000** | Port ocupado o React no compiló | Comprueba puertos: `netstat -ano \| findstr ":3000"`. Ver logs: `docker-compose logs frontend` |
| **npm install falló en build** | `package.json` corrupto o mal ubicado | Verifica que `frontend/package.json` es JSON válido y está en la carpeta correcta |
| **"CUDA not found"** (en logs de Ollama) | GPU drivers no instalados | GPU es opcional. El sistema funciona con CPU (lento). Si quieres GPU: instala [NVIDIA drivers](https://developer.nvidia.com/cuda-downloads) |
| **Timeout en consultas (>30s)** | LLM sobrecargado o CPU bajo | Reinicia servicios: `docker-compose down && docker-compose up`. Reduce `TOP_K_FRAGMENTOS` en config.py. |

## Alineación con los Objetivos Educativos (PPI)

| Objetivo | Componente | Evidencia |
|----------|-----------|----------|
| **OE4** (Reglas y transparencia) | `backend/config.py` + `rag_pipeline.py` | Umbrales, dominios, mensajes M01-M07 definidos y aplicados |
| **OE5** (Sistema conversacional - COMPLETADO) | Proyecto completo | Frontend + Backend + RAG + LLM + registro |
| **OE6** (Evaluación) | `registro_interacciones.db` | Base de datos para cálcular métricas (precisión, cobertura, etc.) |
| **OE8** (Madurez del sistema) | Endpoint `/historial` + CSV export | Insumo para instrumentos de evaluación |

## Desarrollo local y contribuciones

### Estructura de ramas Git:

- `main`: Código de producción (estable)
- `develop`: Rama de integración (últimas features)
- `feature/*`: Features nuevas
- `bugfix/*`: Correcciones de bugs

### Construir solo un servicio:

```powershell
# Solo backend
docker-compose up backend

# Solo frontend
docker-compose up frontend

# Solo Ollama
docker-compose up llm
```

### Ver logs en vivo:

```powershell
docker-compose logs -f backend     # Logs del backend
docker-compose logs -f frontend    # Logs de React
docker-compose logs -f llm         # Logs de Ollama
```

### Recompilar imagen de un servicio:

```powershell
docker-compose up --build backend
```

## Autores

- **David Robert Yucra Mamani**
- **Gladys Rosaura Yana Pari**
- **Luis Alberto Quilla López**

**Asesor:** Esteban Tocto Cano

**Institución:** Universidad Peruana Unión – Facultad de Ingeniería y Arquitectura  
**Escuela:** Profesional de Ingeniería de Sistemas  
**Ubicación:** Juliaca, Puno, Perú

**Fecha:** Junio de 2025  
**Ciclo:** IX (2025-I)

## Licencia

Este proyecto es de uso académico y educativo. Contacta con los autores para cualquier uso comercial.

---

**Última actualización:** 1 de junio de 2026
**Estado:** En producción (OE5 completado + OE4 v2.0 implementado al 100 % salvo T01/T02 fijados por decisión del equipo)
**Próximos pasos:** Instrumentación de OE6 y OE8
