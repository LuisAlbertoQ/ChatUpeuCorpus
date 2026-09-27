"""Pipeline RAG del sistema conversacional UPeU.

Implementa las reglas del documento OE4 v2.0:
  - T01: filtro por umbral de similitud (vía distancia coseno).
  - T03: truncado de respuesta a MAX_PALABRAS_RESPUESTA.
  - T04: timeout de TIMEOUT_RESPUESTA segundos sobre la llamada al LLM → M06.
  - T05: generación condicional (solo si hay fragmentos válidos).
  - T06: detección heurística de preguntas multi-intención → M05.
  - T08: formato enriquecido de fuentes (documento + sección + versión/año).
  - R04 / RF02 / M03: validador de dominio basado en keywords + embeddings.
  - R07: filtrado de términos sensibles → M03.
  - Validación de ambigüedad → M05.
  - try/except global → M06.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from urllib import request as _urlreq
from urllib.error import HTTPError, URLError

import chromadb
from langchain.prompts import PromptTemplate
from sentence_transformers import SentenceTransformer

from config import (
    CORPUS_VERSION,
    DEBUG_LOG,
    DOMINIO_CATEGORIAS,
    EMBEDDING_MODEL,
    KEYWORDS_DOMINIO,
    KEYWORDS_ETICA,
    KEYWORDS_FUERA_DOMINIO,
    MAPEO_CATEGORIAS,
    MARGEN_FUERA_DOMINIO,
    MAX_PALABRAS_RESPUESTA,
    MENSAJES,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    PROMPT_VERSION,
    RAG_DISTANCE_THRESHOLD,
    RAG_TOP_K_FINAL,
    RAG_TOP_K_RAW,
    RANKING_METHOD,
    RANKING_VERSION,
    TIMEOUT_RESPUESTA,
    # Alias por compatibilidad — no usar directamente, preferir RAG_*
    TOP_K_FRAGMENTOS,
    UMBRAL_DISTANCIA_COSENO,
)
from context_builder import construir_contexto, construir_fuentes
from logger import registrar_interaccion

log = logging.getLogger("rag")

# -----------------------------------------------------------------------------
# Recursos globales (inicializados en startup)
# -----------------------------------------------------------------------------
client = None
collection = None
model = None
_executor = ThreadPoolExecutor(max_workers=2)

# -----------------------------------------------------------------------------
# Prompt del sistema (alineado a T05: solo desde fragmentos)
# -----------------------------------------------------------------------------
PROMPT = PromptTemplate(
    template=(
        "Eres un asistente académico de la Universidad Peruana Unión (UPeU).\n"
        "Respondes basándote ESTRICTAMENTE en los fragmentos del corpus proporcionados abajo.\n\n"
        "Da la respuesta en el formato que mejor encaje: texto directo breve, "
        "lista con viñetas (•) o tabla markdown. Cada dato factual termina "
        "con su cita: (Documento, Artículo X°), por ejemplo: "
        "• Recibir formación de calidad (ESTATUTO 2024, Artículo 112°).\n\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. USA solo las fuentes con información directamente relevante (ignora las tangenciales).\n"
        "2. NO inventes información que no esté en los fragmentos. Si los fragmentos no "
        "mencionan algo, di 'El corpus no contiene información sobre X'.\n"
        "3. Copia el nombre del documento literalmente desde el fragmento; "
        "jamás inventes ni completes nombres de documentos.\n"
        "4. NO atribuyas un artículo al documento equivocado.\n"
        "5. No incluyas 'Fuentes', 'Referencias', 'Notas' ni 'Bibliografía' al final; "
        "el sistema agregará las fuentes automáticamente.\n\n"
        "Fragmentos del corpus (usa solo estos):\n{context}\n\n"
        "Pregunta del estudiante: {question}\n\n"
        "Respuesta (en español):"
    ),
    input_variables=["context", "question"],
)

# -----------------------------------------------------------------------------
# Expresiones regulares auxiliares
# -----------------------------------------------------------------------------
_RE_ARTICULO = re.compile(
    r"(art[íi]culo\s*\d+[ºo°]?|cap[íi]tulo\s+[ivxlcdm\d]+|secci[óo]n\s+\d+)",
    re.IGNORECASE,
)
_RE_VERSION = re.compile(r"v\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_RE_ANIO = re.compile(r"\b(20\d{2})\b")

# Stopwords simples para extraer keywords de la query (re-ranking)
_STOPWORDS_ES = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "u", "e", "que", "qué", "cual", "cuál", "como", "cómo", "donde",
    "dónde", "cuando", "cuándo", "quien", "quién", "por", "para", "con", "sin",
    "a", "en", "es", "son", "se", "su", "sus", "le", "les", "lo", "me", "te",
    "nos", "os", "mi", "ti", "si", "no", "ya", "ha", "han", "he", "hay",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel",
    "del", "más", "mas", "menos", "sobre", "entre", "hasta", "desde", "ante",
})
_BOOST_KEYWORD_POR_MATCH = 0.07  # descuento de distancia por keyword match
_PALABRAS_INTERROGATIVAS = {
    "qué", "que", "cómo", "como", "cuándo", "cuando",
    "dónde", "donde", "quién", "quien", "cuál", "cual",
    "cuánto", "cuanto", "por qué", "porque",
}
_CONECTORES_MULTI = re.compile(
    # El \b solo aplica a las frases verbales; [;/] va fuera del grupo
    # porque un boundary nunca colinda con puntuación (bug hallado por
    # tests: "¿X?; ¿Y?" no se detectaba como multi-intención).
    r"\b(y\s+adem[áa]s|tambi[ée]n\s+(?:quiero|me)|y\s+por\s+otra\s+parte|"
    r"adem[áa]s\s+de\s+eso|y\s+tambi[ée]n)\b|[;/]",
    re.IGNORECASE,
)


# =============================================================================
# Inicialización
# =============================================================================
def inicializar():
    """Carga la base vectorial y el modelo de embeddings (llamada en startup)."""
    global client, collection, model
    client = chromadb.PersistentClient(path="/data/vector_store")
    #collection = client.get_collection("corpus_upeu")
    collection = client.get_collection("corpus_upeu_v2")
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    log.info("Recursos RAG inicializados.")
    print("Recursos RAG inicializados correctamente.")


# =============================================================================
# Validaciones previas (sección 2 OE4)
# =============================================================================
def _pregunta_es_ambigua(pregunta: str) -> bool:
    """Heurística simple para M05.

    Considera ambiguas las preguntas demasiado cortas, sin palabras de contenido,
    o que son solo signos de puntuación.
    """
    texto = pregunta.strip()
    if len(texto) < 5:
        return True
    palabras = re.findall(r"\w+", texto.lower())
    if len(palabras) < 3:
        return True
    # Si la única palabra "significativa" es una interrogativa, es ambigua.
    contenido = [p for p in palabras if p not in _PALABRAS_INTERROGATIVAS and len(p) > 2]
    # Basta UNA palabra de contenido: preguntas válidas del tipo
    # "¿qué es la matrícula?" tienen solo un término de fondo y antes
    # se marcaban como ambiguas (falso M05; hallado por tests Tier 3).
    return not contenido


def _es_multi_intencion(pregunta: str) -> bool:
    """T06: heurística para preguntas con múltiples intenciones."""
    if _CONECTORES_MULTI.search(pregunta):
        # Además, debe haber al menos dos signos de interrogación o dos verbos
        if pregunta.count("?") >= 2:
            return True
        # Dos palabras interrogativas distintas también lo evidencian
        encontradas = {
            p for p in _PALABRAS_INTERROGATIVAS
            if re.search(rf"\b{p}\b", pregunta, re.IGNORECASE)
        }
        return len(encontradas) >= 2
    return False


def _es_etica_sensible(pregunta: str) -> bool:
    """R07: detecta términos manifiestamente sensibles."""
    texto = pregunta.lower()
    return any(k in texto for k in KEYWORDS_ETICA)


def _es_fuera_dominio_por_keywords(pregunta: str) -> bool | None:
    """Validador rápido por keywords (R04 / RF02 / M03).

    Returns:
        True  → claramente fuera de dominio.
        False → claramente dentro del dominio.
        None  → indeterminado, hay que validar por embeddings.
    """
    texto = pregunta.lower()
    fuera = any(k in texto for k in KEYWORDS_FUERA_DOMINIO)
    dentro = any(k in texto for k in KEYWORDS_DOMINIO)
    if fuera and not dentro:
        return True
    if dentro:
        return False
    return None


def _clasificar_validacion_m05(pregunta: str) -> str:
    """Clasifica M05 en subtipos Fase 5 §4.3 sin cambiar semántica.

    too_short: <5 chars o <3 palabras
    ambiguous: sin palabra de contenido
    multi_intent: por conectores (se determina fuera de esta función)
    """
    texto = pregunta.strip()
    if len(texto) < 5:
        return "too_short"
    palabras = re.findall(r"\w+", texto.lower())
    if len(palabras) < 3:
        return "too_short"
    contenido = [p for p in palabras if p not in _PALABRAS_INTERROGATIVAS and len(p) > 2]
    if not contenido:
        return "ambiguous"
    return "ambiguous"  # fallback, multi_intent se detecta por _es_multi_intencion


# =============================================================================
# Utilidades de presentación
# =============================================================================
_RE_ENCUADRE = re.compile(r"^\s*Según el (.+?)[:,]\s*", re.IGNORECASE)


def _normalizar_nombre(texto: str) -> str:
    """Minúsculas, sin tildes, espacios colapsados (para comparar nombres)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texto or "").lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def _validar_encuadre(respuesta: str, fuentes: list) -> str:
    """Elimina la línea de encuadre si cita un documento ausente en fuentes.

    Guardrail determinístico contra alucinación de nombres (hallazgo banco
    17Q prompt-v2: el LLM repetía 'REGLAMENTO ADMISION 2025.v7' como encuadre
    en todas las preguntas, e inventó 'Reglamento Académico 2025.v7').

    Se conserva si hay coincidencia por subcadena O solapamiento de
    tokens >= 50% (tolera "DE"/tildes: 'REGLAMENTO DE ADMISIÓN' vs
    'REGLAMENTO ADMISION 2025.v7'). Solo se elimina el encuadre, nunca
    el contenido de la respuesta.
    """
    m = _RE_ENCUADRE.match(respuesta or "")
    if not m:
        return respuesta
    citado = _normalizar_nombre(m.group(1))
    if not citado:
        return respuesta
    toks_citado = set(citado.split())
    for f in fuentes or []:
        parte = (f.split("·")[0] if "·" in f else f)
        doc = _normalizar_nombre(parte)
        if not doc:
            continue
        if citado in doc or doc in citado:
            return respuesta
        toks_doc = set(doc.split())
        solape = len(toks_citado & toks_doc) / max(len(toks_citado), 1)
        if solape >= 0.5:
            return respuesta
    return (respuesta or "")[m.end():].lstrip()


_RE_CITA = re.compile(
    r"\(([^()]{3,80}?),\s*"
    r"((?:Art[íi]culo|Cap[íi]tulo|Secci[óo]n|T[íi]tulo)[^()]{0,40}?)\)"
)
_RE_NUMERO = re.compile(r"\d+")


def _reparar_citas(respuesta: str, fuentes: list) -> tuple[str, int]:
    """Repara citas `(DOC, Artículo NN)` con documento ausente en fuentes.

    Caso real banco 17Q: el LLM citaba bien los números de artículo pero
    con nombres inventados ("REGLAMENTO ADMISION..." en todas, e incluso
    "REGLAMENTO UNIVERSITARIO 2024" que no existe).
      - Si el artículo NN coincide con el de alguna fuente → sustituye DOC
        por el nombre real de esa fuente.
      - Si ni documento ni artículo existen → elimina el paréntesis.
    Retorna (texto, nº de reparaciones). Solo toca citas, nunca contenido.
    """
    refs = []
    for f in fuentes or []:
        partes = (f or "").split("·")
        doc_orig = partes[0].strip() if partes else ""
        doc_norm = _normalizar_nombre(doc_orig)
        art_num = None
        for p in partes[1:]:
            m = _RE_NUMERO.search(p)
            if m and re.search(
                    r"art[íi]culo|cap[íi]tulo|secci[óo]n|t[íi]tulo",
                    p, re.IGNORECASE):
                art_num = m.group(0)
                break
        if doc_norm:
            refs.append((doc_norm, art_num, doc_orig))

    reparaciones = [0]

    def _arreglar(m):
        doc_citado = _normalizar_nombre(m.group(1))
        art_m = _RE_NUMERO.search(m.group(2) or "")
        art_citado = art_m.group(0) if art_m else None
        if doc_citado and any(
                doc_citado in d or d in doc_citado for d, _, _ in refs):
            return m.group(0)
        if art_citado:
            for d_norm, a_num, d_orig in refs:
                if a_num and a_num == art_citado:
                    reparaciones[0] += 1
                    return f"({d_orig}, {m.group(2).strip()})"
        reparaciones[0] += 1
        return ""

    texto = _RE_CITA.sub(_arreglar, respuesta or "")
    texto = re.sub(r"\s+([.,;:])", r"\1", texto)
    return texto, reparaciones[0]


def _truncar_palabras(texto: str, maximo: int) -> tuple[str, bool]:
    """T03: trunca a `maximo` palabras y agrega indicador."""
    palabras = texto.split()
    if len(palabras) <= maximo:
        return texto, False
    cortado = " ".join(palabras[:maximo]).rstrip(",.;:") + " (…)"
    return cortado, True


def _formatear_fuente(documento: str, categoria: str, texto_chunk: str) -> str:
    """T08: nombre + sección/artículo + versión/año + categoría."""
    partes = [documento]

    # Extraer artículo / capítulo / sección del propio chunk
    m_art = _RE_ARTICULO.search(texto_chunk or "")
    if m_art:
        partes.append(m_art.group(1).strip().capitalize())

    # Versión y año del nombre del documento (ej. "REGLAMENTO ADMISION 2025.v7")
    m_ver = _RE_VERSION.search(documento)
    m_anio = _RE_ANIO.search(documento)
    extras = []
    if m_ver:
        extras.append(f"v{m_ver.group(1)}")
    if m_anio:
        extras.append(m_anio.group(1))
    if extras:
        partes.append(" ".join(extras))

    # Categoría legible
    if categoria and categoria in MAPEO_CATEGORIAS:
        partes.append(f"[{categoria} – {MAPEO_CATEGORIAS[categoria]['nombre']}]")
    elif categoria:
        partes.append(f"[{categoria}]")

    return " · ".join(partes)


def _invocar_llm_con_timeout(prompt: str) -> str:
    """T04: ejecuta Ollama vía API HTTP directa con timeout estricto.

    Bypasea `langchain_community.llms.Ollama` porque su wrapper de
    Pydantic v1 rechaza `num_predict` en versiones recientes del
    paquete.  Hablar directo a `/api/generate` es más simple y
    compatible con cualquier versión del servidor Ollama.

    Política de reintentos:
      - Intento 1: timeout estándar.
      - `FutTimeout`: NO se reintenta. El modelo es lento, reintentar
        solo acumula tiempo (25s × 3 = 75s y vuelve a fallar). Se
        levanta inmediatamente para devolver M06.
      - `HTTPError` 5xx: se reintenta hasta 3 veces con backoff
        (intentos 1, 2 inmediato + intento 3 con espera 2 s). El
        500 de Ollama suele ser transitorio (pico de GPU / modelo
        en warm-up).
      - `HTTPError` 4xx: NO se reintenta (prompt inválido, etc.).
    Levanta `FutTimeout` o `HTTPError` si los intentos fallan.
    Acota `num_predict` para que el LLM no genere respuestas tan
    largas que se salgan del timeout.
    """
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 1024,
            "temperature": 0.2,
        },
    }).encode("utf-8")

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    headers = {"Content-Type": "application/json"}

    def _post() -> str:
        req = _urlreq.Request(url, data=payload, headers=headers, method="POST")
        with _urlreq.urlopen(req, timeout=TIMEOUT_RESPUESTA) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        texto = body.get("response", "").strip()
        if not texto:
            raise RuntimeError(f"Ollama devolvió respuesta vacía: {body!r}")
        return texto

    last_err: Exception | None = None
    # Reintentos solo para HTTP 5xx (transitorio). Timeout NO se reintenta:
    # el modelo es lento y reintentar acumula tiempo sin mejorar la tasa
    # de éxito (el siguiente intento tardará >= lo mismo).
    for intento, espera in ((1, 0), (2, 0), (3, 2)):
        if espera:
            time.sleep(espera)
        future = _executor.submit(_post)
        try:
            return future.result(timeout=TIMEOUT_RESPUESTA)
        except FutTimeout as exc:
            # Modelo lento: NO reintentar, devolver M06 inmediatamente.
            log.warning(
                "Timeout T04 intento %d (%ss); modelo lento, sin reintento",
                intento, TIMEOUT_RESPUESTA,
            )
            raise
        except HTTPError as exc:
            last_err = exc
            # 5xx es transitorio: reintento con backoff.
            # 4xx (prompt inválido, etc.) NO reintentar.
            if 500 <= exc.code < 600 and intento < 3:
                log.warning(
                    "Ollama HTTP %d intento %d/3; reintentando en %ds…",
                    exc.code, intento, espera,
                )
                continue
            raise
    raise last_err  # type: ignore[misc]


# =============================================================================
# Pipeline principal
# =============================================================================
def generar_respuesta(pregunta: str, sesion_id: str = "") -> dict:
    """Orquesta el pipeline RAG y devuelve un dict serializable a JSON."""
    inicio = time.time()
    inicio_perf = time.perf_counter()
    pregunta_limpia = (pregunta or "").strip()
    pregunta_normalizada = pregunta_limpia
    embedding_latency_ms: float | None = None
    retrieval_latency_ms: float | None = None
    llm_latency_ms: float | None = None
    http_status: int | None = None
    citation_validation: str | None = None
    citation_repairs: int | None = None
    # Para metadata de retrieval (se rellenan tras filtering)
    _retrieved_chunk_ids: list | None = None
    _retrieved_document_ids: list | None = None
    _retrieved_articles: list | None = None
    _retrieved_distances: list | None = None
    _num_valid_chunks: int | None = None
    _sources_for_log: list | None = None

    # --- Validaciones previas (no requieren LLM ni embeddings) ---------------
    if _pregunta_es_ambigua(pregunta_limpia):
        vr = _clasificar_validacion_m05(pregunta_limpia)
        return _responder_simple(
            pregunta_limpia, MENSAJES["M05"], "M05", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=0,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            validation_reason=vr,
        )

    if _es_etica_sensible(pregunta_limpia):
        return _responder_simple(
            pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            failure_reason="sensitive_request",
        )

    if _es_multi_intencion(pregunta_limpia):
        return _responder_simple(
            pregunta_limpia, MENSAJES["M05"], "M05", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            validation_reason="multi_intent",
        )

    dominio_kw = _es_fuera_dominio_por_keywords(pregunta_limpia)
    if dominio_kw is True:
        return _responder_simple(
            pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            failure_reason="out_of_domain",
        )

    # --- Recuperación RAG -----------------------------------------------------
    # Recuperamos más chunks (RAG_TOP_K_RAW) que los que mostraremos al LLM
    # (RAG_TOP_K_FINAL), para dar oportunidad a documentos pequeños
    # (p.ej. la "Politica Institucional de trabajo digno y protección de
    # la persona v.1" tiene solo 3 chunks) de aparecer en el ranking
    # antes del re-ranking con boost por keywords.
    # RAG_TOP_K_RAW es configurable por env (default 15) — FASE 4.
    TOP_K_RAW = RAG_TOP_K_RAW
    try:
        t0_emb = time.perf_counter()
        embedding = model.encode([pregunta_limpia])[0].tolist()
        embedding_latency_ms = round((time.perf_counter() - t0_emb) * 1000, 2)
        t0_ret = time.perf_counter()
        resultados = collection.query(
            query_embeddings=[embedding],
            n_results=TOP_K_RAW,
        )
        retrieval_latency_ms = round((time.perf_counter() - t0_ret) * 1000, 2)
    except Exception as exc:  # pragma: no cover
        log.exception("Fallo en retrieval")
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            error=str(exc), error_type="exception",
        )

    docs = resultados["documents"][0]
    metas = resultados["metadatas"][0]
    distancias = list(resultados["distances"][0])

    # --- Re-ranking con boost por keywords -----------------------------------
    # Si la query contiene palabras clave (no stopwords) que también
    # aparecen en el nombre del documento, restamos un pequeño valor a
    # la distancia. Esto prioriza documentos cuyo nombre matchea con
    # la intención explícita de la query (p.ej. "política" en la query
    # debe boost el doc "Politica Institucional X").
    keywords_query = [
        w.lower() for w in re.findall(r"\b[a-záéíóúñü]{4,}\b", pregunta_limpia.lower())
        if w.lower() not in _STOPWORDS_ES
    ]
    if keywords_query:
        distancias_boosted = []
        for d, m in zip(distancias, metas):
            doc_norm = (m.get("documento", "") or "").lower()
            matches = sum(1 for kw in keywords_query if kw in doc_norm)
            boost = matches * _BOOST_KEYWORD_POR_MATCH
            distancias_boosted.append(max(0.0, d - boost))
        # Ordenar TODO el pool (TOP_K_RAW) por distancia boosted. NUNCA
        # recortar aquí a TOP_K_FRAGMENTOS: el filtro de UMBRAL (T01) se
        # aplica después sobre el pool completo. Recortar antes hacía que
        # un chunk relevante rankeado #4+ se descartara aunque pasara el
        # umbral (p.ej. "constancia de estudios" → falso M04 con top_k=3).
        orden = sorted(
            range(len(distancias)),
            key=lambda i: distancias_boosted[i],
        )
        docs = [docs[i] for i in orden]
        metas = [metas[i] for i in orden]
        distancias = [distancias_boosted[i] for i in orden]
        log.info(
            "Re-ranking: keywords=%s top_%s=%s",
            keywords_query,
            RAG_TOP_K_FINAL,
            [(metas[i].get("documento", "")[:40], round(distancias[i], 3))
             for i in range(min(len(orden), RAG_TOP_K_FINAL))],
        )
    else:
        # Sin keywords: el pool ya viene ordenado por distancia (sin recorte).
        pass

    # Distancias ORIGINALES para debug (antes del boost)
    distancias_debug = [round(d, 4) for d in distancias]

    # Validación de dominio por embeddings: si NADA está cerca, fuera de dominio
    if dominio_kw is None and distancias:
        min_dist = min(distancias)
        if min_dist > RAG_DISTANCE_THRESHOLD + MARGEN_FUERA_DOMINIO:
            return _responder_simple(
                pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id,
                pregunta_normalizada=pregunta_normalizada,
                latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
                embedding_latency_ms=embedding_latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
                threshold_used=RAG_DISTANCE_THRESHOLD,
                num_valid_chunks=0,
                embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
                prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
                ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
                debug_distancias=distancias_debug,
                failure_reason="out_of_domain",
            )

    # --- Filtro por umbral T01 / T05 + Construcción determinística (Fase 2) ---
    # T01 se aplica sobre el pool completo (no se recortó antes a TOP_K).
    # Fase 2 §12 y §15: el contexto y las fuentes se construyen vía
    # funciones puras construir_contexto() / construir_fuentes() a partir
    # de metadatos recuperados, nunca del texto generado por el LLM.
    # Cada fragmento conserva cabecera+cola si excede 700 chars.
    MAX_CHARS_POR_FRAGMENTO = 700
    fragmentos_struct: list[dict] = []
    doc_sugerido = None
    for doc, meta, dist in zip(docs, metas, distancias):
        if len(fragmentos_struct) >= RAG_TOP_K_FINAL:
            break
        if dist < RAG_DISTANCE_THRESHOLD:
            texto = doc if len(doc) <= MAX_CHARS_POR_FRAGMENTO else (
                doc[: MAX_CHARS_POR_FRAGMENTO // 2]
                + "\n[…]\n"
                + doc[-MAX_CHARS_POR_FRAGMENTO // 2 :]
            )
            frag = {
                "documento": meta.get("documento", "Documento sin nombre"),
                "categoria": meta.get("categoria", "") or meta.get("categoria_tematica", ""),
                "categoria_tematica": meta.get("categoria_tematica", "") or meta.get("categoria", ""),
                "articulo": meta.get("articulo", "") or "",
                "chunk_id": meta.get("chunk_id", ""),
                "text": texto,
                "texto": texto,  # alias para compatibilidad del builder
                "distance": dist,
                "num_chars": len(texto),
                "page": meta.get("page", "") or meta.get("pagina", ""),
            }
            if not frag["articulo"]:
                m_art = _RE_ARTICULO.search(doc or "")
                if m_art:
                    frag["articulo"] = m_art.group(1).strip().capitalize()
                    frag["article"] = frag["articulo"]
            fragmentos_struct.append(frag)
            if doc_sugerido is None:
                doc_sugerido = frag["documento"]

    # --- Sin fragmentos válidos → M04 ----------------------------------------
    if not fragmentos_struct:
        tipo_mensaje = "M04"
        doc_sugerido = metas[0]["documento"] if metas else "documentos generales de la UPeU"
        respuesta_final = MENSAJES["M04"].replace(
            "[nombre del documento relacionado más cercano]", doc_sugerido
        )
        return _empaquetar(
            pregunta_limpia, respuesta_final, [], tipo_mensaje,
            inicio, sesion_id, distancias_debug,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=0,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            failure_reason="retrieval_no_coverage",
        )

    # Construcción determinística (Fase 2 §12 y §15)
    fuentes = construir_fuentes(fragmentos_struct)
    distancias_validas = [round(f["distance"], 4) for f in fragmentos_struct]
    contexto = construir_contexto(fragmentos_struct)

    # --- Generación condicionada (T05) ---------------------------------------
    prompt = PROMPT.format(context=contexto, question=pregunta_limpia)

    # Metadatos de retrieval para logging Fase 5 §9 (1:1 y orden)
    _retrieved_chunk_ids = [f.get("chunk_id", "") for f in fragmentos_struct]
    _retrieved_document_ids = [f.get("documento", "") for f in fragmentos_struct]
    _retrieved_articles = [f.get("articulo", "") for f in fragmentos_struct]
    _retrieved_distances = [round(f.get("distance", 0), 4) for f in fragmentos_struct]
    _num_valid_chunks = len(fragmentos_struct)
    _sources_for_log = list(fuentes)

    t0_llm = time.perf_counter()
    try:
        respuesta_generada = _invocar_llm_con_timeout(prompt)
        llm_latency_ms = round((time.perf_counter() - t0_llm) * 1000, 2)
        http_status = 200
    except FutTimeout as exc:
        llm_latency_ms = round((time.perf_counter() - t0_llm) * 1000, 2)
        log.warning("Timeout T04 (%ss) excedido", TIMEOUT_RESPUESTA)
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=_num_valid_chunks,
            retrieved_chunk_ids=_retrieved_chunk_ids,
            retrieved_document_ids=_retrieved_document_ids,
            retrieved_articles=_retrieved_articles,
            retrieved_distances=_retrieved_distances,
            sources=_sources_for_log,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            debug_distancias=distancias_debug,
            error=f"timeout_{TIMEOUT_RESPUESTA}s",
            error_type="timeout",
            http_status=None,
        )
    except HTTPError as exc:
        llm_latency_ms = round((time.perf_counter() - t0_llm) * 1000, 2)
        log.error("Ollama HTTP/URL error: %s", exc)
        # Distinguir 5xx vs 4xx para error_type
        code = getattr(exc, "code", None)
        if isinstance(code, int) and 500 <= code < 600:
            err_type = "http_5xx"
        else:
            err_type = "exception"
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=_num_valid_chunks,
            retrieved_chunk_ids=_retrieved_chunk_ids,
            retrieved_document_ids=_retrieved_document_ids,
            retrieved_articles=_retrieved_articles,
            retrieved_distances=_retrieved_distances,
            sources=_sources_for_log,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            debug_distancias=distancias_debug,
            error=f"ollama_{type(exc).__name__}: {exc}",
            error_type=err_type,
            http_status=code if isinstance(code, int) else None,
        )
    except URLError as exc:
        llm_latency_ms = round((time.perf_counter() - t0_llm) * 1000, 2)
        log.error("Ollama URL error: %s", exc)
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=_num_valid_chunks,
            retrieved_chunk_ids=_retrieved_chunk_ids,
            retrieved_document_ids=_retrieved_document_ids,
            retrieved_articles=_retrieved_articles,
            retrieved_distances=_retrieved_distances,
            sources=_sources_for_log,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            debug_distancias=distancias_debug,
            error=f"ollama_URLError: {exc}",
            error_type="exception",
            http_status=None,
        )
    except Exception as exc:
        llm_latency_ms = round((time.perf_counter() - t0_llm) * 1000, 2)
        log.exception("Fallo en llamada al LLM")
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=_num_valid_chunks,
            retrieved_chunk_ids=_retrieved_chunk_ids,
            retrieved_document_ids=_retrieved_document_ids,
            retrieved_articles=_retrieved_articles,
            retrieved_distances=_retrieved_distances,
            sources=_sources_for_log,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            debug_distancias=distancias_debug,
            error=str(exc),
            error_type="exception",
            http_status=None,
        )

    # --- Sanear respuesta del LLM --------------------------------------------
    # Corta cualquier bloque final del tipo "Fuentes:", "**Fuentes**",
    # "Fuentes consultadas:", "Referencias:", "Bibliografía:", "Notas:".
    # Captura markdown (**), saltos de línea y cualquier cosa después.
    respuesta_generada = re.split(
        r"(?im)^[\s>\-]*\*?\*?(?:fuentes?|referencias?|bibliograf[íi]a|notas?)"
        r"(?:\s+consultadas?|\s+verificables?|\s+utilizadas?)?\*?\*?\s*[:—\-]\s*.*$",
        respuesta_generada,
    )[0].rstrip()

    # Convertir viñetas Unicode (•) a markdown estándar (- ). El LLM
    # emite U+2022 BULLET que NO es markdown, así que ReactMarkdown
    # no lo renderiza como lista. Reemplazamos `•` por `- ` solo al
    # inicio de cada viñeta (después de \n o al inicio del texto).
    respuesta_generada = re.sub(
        r"(?m)^(\s*)•\s+",
        r"\1- ",
        respuesta_generada,
    )
    # También capturar `•` que aparezca precedido de \n sin espacio
    respuesta_generada = re.sub(r"\n•\s+", "\n- ", respuesta_generada)
    # Y al inicio absoluto del texto (por si el LLM no pone \n antes)
    if respuesta_generada.lstrip().startswith("•"):
        respuesta_generada = respuesta_generada.replace("•", "- ", 1)

    # Eliminar frases meta que el LLM agrega cuando encuentra info parcial
    # o cree que no tiene datos. Son jerga tecnica que confunde al usuario
    # ("corpus", "fragmentos proporcionados", "los documentos no contienen").
    # Variantes observadas:
    #   "No hay información específica sobre X en los fragmentos proporcionados."
    #   "El corpus no contiene información sobre este tema."
    #   "Los documentos no incluyen/proporcionan información sobre X."
    #   "(El corpus no contiene información sobre X.)"
    respuesta_generada = re.sub(
        r"(?i)\s*(?:\(\s*)?(?:El corpus no contiene|N[o\u00f3] hay informaci[o\u00f3]n"
        r"|No se encontr[o\u00f3] informaci[o\u00f3]n|"
        r"El fragmento no (?:lo )?menciona|"
        r"Los documentos (?:no|tampoco) (?:incluyen|proporcionan|"
        r"contienen|abordan|cubren)|"
        r"En los fragmentos proporcionados)[^.)]*(?:\.|\)?\s*\.?)\s*$",
        "",
        respuesta_generada,
    ).rstrip()

    # Guardrail de encuadre: si la línea "Según el X:" cita un documento
    # que NO está entre las fuentes, se elimina (alucinación de nombre).
    antes_encuadre = respuesta_generada
    respuesta_generada = _validar_encuadre(respuesta_generada, fuentes)
    if respuesta_generada != antes_encuadre:
        log.info(
            "Encuadre con documento no citado eliminado. pregunta=%r",
            pregunta_limpia,
        )

    # Reparación de citas: si una cita (DOC, Artículo NN) usa un documento
    # ausente en fuentes pero el artículo coincide, se sustituye por el
    # nombre real; si ni el artículo existe, se elimina el paréntesis.
    respuesta_generada, n_rep = _reparar_citas(respuesta_generada, fuentes)
    if n_rep:
        log.info(
            "Citas reparadas=%d. pregunta=%r", n_rep, pregunta_limpia,
        )

    # Citation validation Fase 5 §6: estado semántico
    has_citations_final = bool(_RE_CITA.search(respuesta_generada))
    if not has_citations_final and n_rep == 0:
        citation_validation = "not_applicable"
    elif n_rep == 0 and has_citations_final:
        citation_validation = "valid"
    elif n_rep > 0 and has_citations_final:
        citation_validation = "repaired"
    elif n_rep > 0 and not has_citations_final:
        citation_validation = "failed"
    else:
        citation_validation = "not_applicable"
    citation_repairs = n_rep if n_rep > 0 else 0

    # T03: truncar a MAX_PALABRAS_RESPUESTA
    respuesta_generada, fue_truncada = _truncar_palabras(
        respuesta_generada, MAX_PALABRAS_RESPUESTA
    )
    if fue_truncada:
        respuesta_generada += "\n\n_Puedes consultar la fuente completa para más detalle._"

    # Las fuentes NO se concatenan al cuerpo: se devuelven en el JSON
    # (`fuentes`) y el frontend las renderiza como footer profesional.
    # Concatenarlas aquí producía duplicación visual ("Fuentes consultadas:"
    # en el cuerpo + "Fuentes verificables" en el footer).

    # Si despues del post-proceso la respuesta quedo vacia o muy corta
    # (porque el LLM solo emitio meta-frases tipo "no hay informacion"),
    # el LLM esencialmente dijo "no se". En ese caso usamos M04 (mensaje
    # oficial de "sin cobertura" en config.py) y cambiamos el tipo de
    # mensaje. Asi el usuario ve un mensaje consistente del sistema,
    # no jerga tecnica del LLM.
    if not respuesta_generada.strip() or len(respuesta_generada.strip()) < 30:
        log.info(
            "Respuesta del LLM quedo vacia/corta tras post-proceso; "
            "sustituyendo por M04 (sin_cobertura). pregunta=%r",
            pregunta_limpia,
        )
        respuesta_final = MENSAJES["M04"].replace(
            "[nombre del documento relacionado más cercano]",
            doc_sugerido or "documentos generales de la UPeU",
        )
        return _empaquetar(
            pregunta_limpia, respuesta_final, fuentes, "M04",
            inicio, sesion_id, distancias_validas,
            pregunta_normalizada=pregunta_normalizada,
            latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
            threshold_used=RAG_DISTANCE_THRESHOLD,
            num_valid_chunks=_num_valid_chunks,
            retrieved_chunk_ids=_retrieved_chunk_ids,
            retrieved_document_ids=_retrieved_document_ids,
            retrieved_articles=_retrieved_articles,
            retrieved_distances=_retrieved_distances,
            sources=_sources_for_log,
            citation_validation=citation_validation,
            citation_repairs=citation_repairs,
            embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
            prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
            ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
            http_status=200,
            failure_reason="generation_empty",
        )

    respuesta_final = respuesta_generada

    return _empaquetar(
        pregunta_limpia, respuesta_final, fuentes, "M02",
        inicio, sesion_id, distancias_validas,
        pregunta_normalizada=pregunta_normalizada,
        latency_total_ms=round((time.perf_counter() - inicio_perf) * 1000, 2),
        embedding_latency_ms=embedding_latency_ms,
        retrieval_latency_ms=retrieval_latency_ms,
        llm_latency_ms=llm_latency_ms,
        top_k_raw=RAG_TOP_K_RAW, top_k_final=RAG_TOP_K_FINAL,
        threshold_used=RAG_DISTANCE_THRESHOLD,
        num_valid_chunks=_num_valid_chunks,
        retrieved_chunk_ids=_retrieved_chunk_ids,
        retrieved_document_ids=_retrieved_document_ids,
        retrieved_articles=_retrieved_articles,
        retrieved_distances=_retrieved_distances,
        sources=_sources_for_log,
        citation_validation=citation_validation,
        citation_repairs=citation_repairs,
        embedding_model=EMBEDDING_MODEL, llm_model=OLLAMA_MODEL,
        prompt_version=PROMPT_VERSION, corpus_version=CORPUS_VERSION,
        ranking_method=RANKING_METHOD, ranking_version=RANKING_VERSION,
        http_status=200,
    )


# =============================================================================
# Helpers de empaquetado y respuesta corta (Fase 5: aceptan campos internos)
# =============================================================================
def _responder_simple(
    pregunta: str,
    respuesta: str,
    tipo_mensaje: str,
    inicio: float,
    sesion_id: str,
    debug_distancias: list | None = None,
    error: str = "",
    **kwargs,
) -> dict:
    return _empaquetar(
        pregunta, respuesta, [], tipo_mensaje,
        inicio, sesion_id, debug_distancias or [], error,
        **kwargs,
    )


def _empaquetar(
    pregunta: str,
    respuesta: str,
    fuentes: list,
    tipo_mensaje: str,
    inicio: float,
    sesion_id: str,
    debug_distancias: list,
    error: str = "",
    pregunta_normalizada: str | None = None,
    latency_total_ms: float | None = None,
    embedding_latency_ms: float | None = None,
    retrieval_latency_ms: float | None = None,
    llm_latency_ms: float | None = None,
    top_k_raw: int | None = None,
    top_k_final: int | None = None,
    threshold_used: float | None = None,
    num_valid_chunks: int | None = None,
    retrieved_chunk_ids: list | None = None,
    retrieved_document_ids: list | None = None,
    retrieved_articles: list | None = None,
    retrieved_distances: list | None = None,
    sources: list | None = None,
    citation_validation: str | None = None,
    citation_repairs: int | None = None,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
    corpus_version: str | None = None,
    ranking_method: str | None = None,
    ranking_version: str | None = None,
    http_status: int | None = None,
    failure_reason: str | None = None,
    validation_reason: str | None = None,
    error_type: str | None = None,
) -> dict:
    tiempo_total = time.time() - inicio
    # latency_total_ms: si el caller ya midió con perf_counter, úsalo; si no, deriva de tiempo_total
    if latency_total_ms is None:
        latency_total_ms = round(tiempo_total * 1000.0, 2)
    # threshold_used por defecto es el configurado
    if threshold_used is None:
        threshold_used = RAG_DISTANCE_THRESHOLD
    # versionado por defecto desde config
    if embedding_model is None:
        embedding_model = EMBEDDING_MODEL
    if llm_model is None:
        llm_model = OLLAMA_MODEL
    if prompt_version is None:
        prompt_version = PROMPT_VERSION
    if corpus_version is None:
        corpus_version = CORPUS_VERSION
    if ranking_method is None:
        ranking_method = RANKING_METHOD
    if ranking_version is None:
        ranking_version = RANKING_VERSION
    if top_k_raw is None:
        top_k_raw = RAG_TOP_K_RAW
    if top_k_final is None:
        top_k_final = RAG_TOP_K_FINAL
    # sources JSON por defecto es copia de fuentes si no se provee
    if sources is None:
        sources = list(fuentes) if fuentes else None
    try:
        registrar_interaccion(
            pregunta=pregunta,
            respuesta=respuesta,
            fuentes=fuentes,
            tiempo_respuesta=tiempo_total,
            umbral=threshold_used,
            tipo_mensaje=tipo_mensaje,
            sesion_id=sesion_id,
            error=error,
            pregunta_normalizada=pregunta_normalizada if pregunta_normalizada is not None else pregunta,
            latency_total_ms=latency_total_ms,
            embedding_latency_ms=embedding_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            top_k_raw=top_k_raw,
            top_k_final=top_k_final,
            threshold_used=threshold_used,
            num_valid_chunks=num_valid_chunks,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_document_ids=retrieved_document_ids,
            retrieved_articles=retrieved_articles,
            retrieved_distances=retrieved_distances,
            sources=sources,
            citation_validation=citation_validation,
            citation_repairs=citation_repairs,
            embedding_model=embedding_model,
            llm_model=llm_model,
            prompt_version=prompt_version,
            corpus_version=corpus_version,
            ranking_method=ranking_method,
            ranking_version=ranking_version,
            http_status=http_status,
            failure_reason=failure_reason,
            validation_reason=validation_reason,
            error_type=error_type,
        )
    except Exception:  # pragma: no cover
        log.exception("Fallo al registrar interacción (no bloqueante)")

    salida = {
        "respuesta": respuesta,
        "fuentes": fuentes,
        "tipo_mensaje": tipo_mensaje,
        "tiempo_respuesta": round(tiempo_total, 3),
    }
    if DEBUG_LOG:
        salida["debug_distancias"] = debug_distancias
    return salida
