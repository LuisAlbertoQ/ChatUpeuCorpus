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
    DEBUG_LOG,
    DOMINIO_CATEGORIAS,
    KEYWORDS_DOMINIO,
    KEYWORDS_ETICA,
    KEYWORDS_FUERA_DOMINIO,
    MAPEO_CATEGORIAS,
    MARGEN_FUERA_DOMINIO,
    MAX_PALABRAS_RESPUESTA,
    MENSAJES,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    TIMEOUT_RESPUESTA,
    TOP_K_FRAGMENTOS,
    UMBRAL_DISTANCIA_COSENO,
)
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
        "REGLAS OBLIGATORIAS:\n"
        "1. USA TODAS las fuentes que contengan información relevante para la pregunta. "
        "Si una fuente tiene 5+ derechos, requisitos o numerales, enuméralos TODOS uno por uno.\n"
        "2. NO inventes información que no esté en los fragmentos. Si los fragmentos no "
        "mencionan algo, di 'El corpus no contiene información sobre X'.\n"
        "3. CADA bullet debe terminar con la cita entre paréntesis con el formato: "
        "(Documento, Artículo X°). Ejemplo: • Recibir formación académica de calidad "
        "(ESTATUTO 2024, Artículo 112°).\n"
        "4. Presenta los resultados como lista vertical con viñetas (•) o numerada, UN elemento por línea. Cada viñeta debe contener al menos un enunciado completo. No generes viñetas vacías."
        "(1., 2., 3., ...), UN elemento por línea. NUNCA juntes varios elementos en "
        "un solo párrafo separado solo por espacios.\n"
        "5. Si el usuario pregunta por derechos/deberes/procedimientos enumerados, "
        "SIEMPRE lista cada ítem por separado (uno por viñeta).\n"
        "6. NO agregues 'Introducción breve' ni prólogos: ve directo a la lista.\n"
        "7. NO atribuyas un artículo al documento equivocado. Cita SOLO lo que aparece "
        "literalmente en cada fragmento.\n"
        "8. No incluyas 'Fuentes', 'Referencias', 'Notas' ni 'Bibliografía' al final; "
        "el sistema agregará las fuentes automáticamente.\n\n"
        "Fragmentos del corpus (usa solo estos):\n{context}\n\n"
        "Pregunta del estudiante: {question}\n\n"
        "Respuesta (en español, formato lista vertical con citas):"
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
    collection = client.get_collection("corpus_upeu")
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


# =============================================================================
# Utilidades de presentación
# =============================================================================
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
    pregunta_limpia = (pregunta or "").strip()

    # --- Validaciones previas (no requieren LLM ni embeddings) ---------------
    if _pregunta_es_ambigua(pregunta_limpia):
        return _responder_simple(
            pregunta_limpia, MENSAJES["M05"], "M05", inicio, sesion_id
        )

    if _es_etica_sensible(pregunta_limpia):
        return _responder_simple(
            pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id
        )

    if _es_multi_intencion(pregunta_limpia):
        return _responder_simple(
            pregunta_limpia, MENSAJES["M05"], "M05", inicio, sesion_id
        )

    dominio_kw = _es_fuera_dominio_por_keywords(pregunta_limpia)
    if dominio_kw is True:
        return _responder_simple(
            pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id
        )

    # --- Recuperación RAG -----------------------------------------------------
    # Recuperamos más chunks (TOP_K_RAW) que los que mostraremos al LLM
    # (TOP_K_FRAGMENTOS), para dar oportunidad a documentos pequeños
    # (p.ej. la "Politica Institucional de trabajo digno y protección de
    # la persona v.1" tiene solo 3 chunks) de aparecer en el ranking
    # antes del re-ranking con boost por keywords.
    TOP_K_RAW = max(TOP_K_FRAGMENTOS * 3, 15)
    try:
        embedding = model.encode([pregunta_limpia])[0].tolist()
        resultados = collection.query(
            query_embeddings=[embedding],
            n_results=TOP_K_RAW,
        )
    except Exception as exc:  # pragma: no cover
        log.exception("Fallo en retrieval")
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id, error=str(exc)
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
            TOP_K_FRAGMENTOS,
            [(metas[i].get("documento", "")[:40], round(distancias[i], 3))
             for i in range(min(len(orden), TOP_K_FRAGMENTOS))],
        )
    else:
        # Sin keywords: el pool ya viene ordenado por distancia (sin recorte).
        pass

    # Distancias ORIGINALES para debug (antes del boost)
    distancias_debug = [round(d, 4) for d in distancias]

    # Validación de dominio por embeddings: si NADA está cerca, fuera de dominio
    if dominio_kw is None and distancias:
        min_dist = min(distancias)
        if min_dist > UMBRAL_DISTANCIA_COSENO + MARGEN_FUERA_DOMINIO:
            return _responder_simple(
                pregunta_limpia, MENSAJES["M03"], "M03", inicio, sesion_id,
                debug_distancias=distancias_debug,
            )

    # --- Filtro por umbral T01 / T05 -----------------------------------------
    # Cada fragmento se recorta a MAX_CHARS_POR_FRAGMENTO para evitar
    # prompts enormes que excedan el timeout con Llama 3 8B + 3 capas
    # en CPU. El recorte conserva la cabecera (donde está el artículo)
    # y el final (donde está el contenido relevante) del fragmento.
    # Valor agresivo (700) para garantizar <30s en hardware lento.
    MAX_CHARS_POR_FRAGMENTO = 700
    fragmentos_validos = []
    fuentes = []
    distancias_validas = []
    doc_sugerido = None
    for doc, meta, dist in zip(docs, metas, distancias):
        if len(fuentes) >= TOP_K_FRAGMENTOS:
            break
        if dist < UMBRAL_DISTANCIA_COSENO:
            texto = doc if len(doc) <= MAX_CHARS_POR_FRAGMENTO else (
                doc[: MAX_CHARS_POR_FRAGMENTO // 2]
                + "\n[…]\n"
                + doc[-MAX_CHARS_POR_FRAGMENTO // 2 :]
            )
            fragmentos_validos.append(texto)
            fuentes.append(
                _formatear_fuente(
                    meta.get("documento", "Documento sin nombre"),
                    meta.get("categoria", ""),
                    doc,
                )
            )
            # Distancia asociada a cada fuente (1:1 con `fuentes`) para que el
            # frontend muestre la similitud (%) de cada badge (ítem 7 Tier 2).
            distancias_validas.append(round(dist, 4))
            if doc_sugerido is None:
                doc_sugerido = meta.get("documento", "documentos generales de la UPeU")

    # --- Sin fragmentos válidos → M04 ----------------------------------------
    if not fragmentos_validos:
        tipo_mensaje = "M04"
        doc_sugerido = metas[0]["documento"] if metas else "documentos generales de la UPeU"
        respuesta_final = MENSAJES["M04"].replace(
            "[nombre del documento relacionado más cercano]", doc_sugerido
        )
        return _empaquetar(
            pregunta_limpia, respuesta_final, [], tipo_mensaje,
            inicio, sesion_id, distancias_debug,
        )

    # --- Generación condicionada (T05) ---------------------------------------
    contexto = "\n\n".join(fragmentos_validos)
    prompt = PROMPT.format(context=contexto, question=pregunta_limpia)

    try:
        respuesta_generada = _invocar_llm_con_timeout(prompt)
    except FutTimeout:
        log.warning("Timeout T04 (%ss) excedido", TIMEOUT_RESPUESTA)
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            error=f"timeout_{TIMEOUT_RESPUESTA}s",
            debug_distancias=distancias_debug,
        )
    except (HTTPError, URLError) as exc:
        log.error("Ollama HTTP/URL error: %s", exc)
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            error=f"ollama_{type(exc).__name__}: {exc}",
            debug_distancias=distancias_debug,
        )
    except Exception as exc:
        log.exception("Fallo en llamada al LLM")
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id,
            error=str(exc), debug_distancias=distancias_debug,
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
        )

    respuesta_final = respuesta_generada

    return _empaquetar(
        pregunta_limpia, respuesta_final, fuentes, "M02",
        inicio, sesion_id, distancias_validas,
    )


# =============================================================================
# Helpers de empaquetado y respuesta corta
# =============================================================================
def _responder_simple(
    pregunta: str,
    respuesta: str,
    tipo_mensaje: str,
    inicio: float,
    sesion_id: str,
    debug_distancias: list | None = None,
    error: str = "",
) -> dict:
    return _empaquetar(
        pregunta, respuesta, [], tipo_mensaje,
        inicio, sesion_id, debug_distancias or [], error,
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
) -> dict:
    tiempo_total = time.time() - inicio
    try:
        registrar_interaccion(
            pregunta=pregunta,
            respuesta=respuesta,
            fuentes=fuentes,
            tiempo_respuesta=tiempo_total,
            umbral=UMBRAL_DISTANCIA_COSENO,
            tipo_mensaje=tipo_mensaje,
            sesion_id=sesion_id,
            error=error,
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
