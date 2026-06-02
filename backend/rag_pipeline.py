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
    DOMINIO_CATEGORIAS,
    KEYWORDS_DOMINIO,
    KEYWORDS_ETICA,
    KEYWORDS_FUERA_DOMINIO,
    MAPEO_CATEGORIAS,
    MAX_PALABRAS_RESPUESTA,
    MENSAJES,
    MODO_PILOTO,
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

# Margen extra sobre el umbral: si TODAS las distancias superan
# UMBRAL + MARGEN, la pregunta se considera fuera de dominio.
MARGEN_FUERA_DOMINIO = 0.10

# -----------------------------------------------------------------------------
# Prompt del sistema (alineado a T05: solo desde fragmentos)
# -----------------------------------------------------------------------------
PROMPT = PromptTemplate(
    template=(
        "Eres un asistente universitario que responde preguntas sobre reglamentos, "
        "trámites y procedimientos para estudiantes de la Universidad Peruana Unión.\n\n"
        "Utiliza EXCLUSIVAMENTE los fragmentos proporcionados.\n"
        "Si los fragmentos contienen información relevante —aunque sea parcial— "
        "úsala para responder la pregunta, citando artículos cuando aparezcan.\n"
        "Responde EXACTAMENTE 'No encontré información suficiente en los documentos "
        "disponibles para responder tu pregunta con confianza.' SOLO cuando los "
        "fragmentos no mencionen el tema de la pregunta en absoluto.\n\n"
        "FORMATO OBLIGATORIO (respeta siempre estas reglas):\n"
        "- Si los fragmentos contienen derechos, requisitos, pasos, artículos, "
        "numerales o cualquier lista enumerada, DEBES presentarlos como lista "
        "vertical con viñetas (•) o números (1., 2., 3., ...), UN elemento por línea.\n"
        "- NUNCA juntes varios elementos en un solo párrafo separado solo por espacios.\n"
        "- Cada viñeta debe ir en su propia línea. Usa saltos de línea explícitos (\\n) "
        "entre viñetas, no espacios.\n"
        "- Si hay artículos o numerales (112.1, 112.2, Artículo 8, etc.), conserva el "
        "número junto a cada viñeta entre paréntesis.\n"
        "- Antes de la lista, una línea de introducción breve (una sola línea).\n"
        "- No agrupes ni resumas varios puntos en uno solo.\n\n"
        "Otras reglas:\n"
        "- No inventes información que no aparezca en los fragmentos.\n"
        "- Sé conciso: máximo 8 viñetas o 3 párrafos breves.\n"
        "- No incluyas 'Fuentes', 'Referencias', 'Notas' ni 'Bibliografía' al final; "
        "el sistema agregará las fuentes automáticamente.\n\n"
        "Fragmentos:\n{context}\n\n"
        "Pregunta:\n{question}\n\n"
        "Respuesta:"
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
_PALABRAS_INTERROGATIVAS = {
    "qué", "que", "cómo", "como", "cuándo", "cuando",
    "dónde", "donde", "quién", "quien", "cuál", "cual",
    "cuánto", "cuanto", "por qué", "porque",
}
_CONECTORES_MULTI = re.compile(
    r"\b(y\s+adem[áa]s|tambi[ée]n\s+(quiero|me)|y\s+por\s+otra\s+parte|"
    r"adem[áa]s\s+de\s+eso|y\s+tambi[ée]n|;|/)\b",
    re.IGNORECASE,
)


# =============================================================================
# Inicialización
# =============================================================================
def inicializar():
    """Carga la base vectorial y el modelo de embeddings (llamada en startup)."""
    global client, collection, model
    client = chromadb.PersistentClient(path="./vector_store")
    collection = client.get_collection("corpus_upeu")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
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
    return len(contenido) < 2


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

    Política de reintentos (no toca TIMEOUT_RESPUESTA):
      - Intento 1: timeout estándar
      - Intento 2: si fue `FutTimeout`, reintento inmediato
      - Intento 3: si fue HTTP 500 de Ollama (modelo en loop /
        pico de GPU), espera 2 s y reintenta — el error 500
        suele ser transitorio
    Levanta `FutTimeout` o `HTTPError` si todos los intentos fallan.
    Acota `num_predict` para que el LLM no genere respuestas tan
    largas que se salgan del timeout.
    """
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 768,
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
    # 3 intentos: 1 normal, 1 retry por timeout, 1 retry por 500
    for intento, espera in ((1, 0), (2, 0), (3, 2)):
        if espera:
            time.sleep(espera)
        future = _executor.submit(_post)
        try:
            return future.result(timeout=TIMEOUT_RESPUESTA)
        except FutTimeout as exc:
            last_err = exc
            log.warning(
                "Timeout T04 intento %d/3 (%ss); %s",
                intento, TIMEOUT_RESPUESTA,
                "reintentando…" if intento < 3 else "agotado",
            )
            continue
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
    try:
        embedding = model.encode([pregunta_limpia])[0].tolist()
        resultados = collection.query(
            query_embeddings=[embedding],
            n_results=TOP_K_FRAGMENTOS,
        )
    except Exception as exc:  # pragma: no cover
        log.exception("Fallo en retrieval")
        return _responder_simple(
            pregunta_limpia, MENSAJES["M06"], "M06", inicio, sesion_id, error=str(exc)
        )

    docs = resultados["documents"][0]
    metas = resultados["metadatas"][0]
    distancias = resultados["distances"][0]
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
    # prompts enormes (8000+ tokens) que hacen que el LLM entre en
    # loop o devuelva HTTP 500. El recorte conserva la cabecera
    # (donde suele estar el artículo/título) y el final (donde
    # suele estar el contenido relevante) del fragmento.
    MAX_CHARS_POR_FRAGMENTO = 1200
    fragmentos_validos = []
    fuentes = []
    for doc, meta, dist in zip(docs, metas, distancias):
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
    respuesta_final = respuesta_generada

    return _empaquetar(
        pregunta_limpia, respuesta_final, fuentes, "M02",
        inicio, sesion_id, distancias_debug,
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
    if MODO_PILOTO:
        salida["debug_distancias"] = debug_distancias
    return salida
