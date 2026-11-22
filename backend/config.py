import logging
import os
import re

log = logging.getLogger("config")

# =============================================================================
# OE4 v2.0 — Configuración del sistema conversacional UPeU
# =============================================================================

# -----------------------------------------------------------------------------
# Umbrales RAG — configurables por entorno (Fase 4, §8/10/11)
# Defaults: threshold 0.41 (bge-m3), TOP_K_RAW 15, TOP_K_FINAL 4. Variables RAG_*
# son la fuente de verdad; los nombres antiguos se mantienen como alias
# por compatibilidad con código y tests existentes.
# -----------------------------------------------------------------------------
def _get_float_env(nombre: str, default: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    raw = os.getenv(nombre)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = float(raw)
        if not (minimo <= val <= maximo):
            log.warning("%s=%r fuera de rango [%s,%s], usando default %s", nombre, raw, minimo, maximo, default)
            return default
        return val
    except ValueError:
        log.warning("%s=%r inválido (no es número), usando default %s", nombre, raw, default)
        return default


def _get_int_env(nombre: str, default: int, minimo: int = 1) -> int:
    raw = os.getenv(nombre)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = int(raw)
        if val < minimo:
            log.warning("%s=%r < %s, usando default %s", nombre, raw, minimo, default)
            return default
        return val
    except ValueError:
        log.warning("%s=%r inválido (no es entero), usando default %s", nombre, raw, default)
        return default


# 2026-11-21: recalibrado para corpus V3 + bge-m3 (antes 0.40 con mpnet).
# Evidencia: evaluacion/retrieval/calibracion_v3_bgem3/ (325 positivas, 42 negativas):
# Top-1 positivas p95 = 0.368, negativas min = 0.418 → 0.41 = máxima abstención OOD
# con la menor falsa abstención (2.2 %).
RAG_DISTANCE_THRESHOLD = _get_float_env("RAG_DISTANCE_THRESHOLD", 0.41, 0.0, 1.0)
RAG_TOP_K_RAW = _get_int_env("RAG_TOP_K_RAW", 15, 1)
RAG_TOP_K_FINAL = _get_int_env("RAG_TOP_K_FINAL", 4, 1)

# Alias por compatibilidad — no duplicar fuente de verdad
UMBRAL_DISTANCIA_COSENO = RAG_DISTANCE_THRESHOLD
TOP_K_FRAGMENTOS = RAG_TOP_K_FINAL

MAX_PALABRAS_RESPUESTA = 500
# 2026-11-21 (mejora 1): 50 → 75 s. Medido en RTX 4050: ~17 tokens/s, así que
# num_predict 1024 puede tardar ~60 s + evaluación del prompt.
TIMEOUT_RESPUESTA = _get_int_env("TIMEOUT_RESPUESTA", 75, 10)

# Contexto para el LLM (mejora 1, 2026-11-21). Antes cada fragmento se recortaba
# a 700 caracteres (inicio + "[…]" + final) y el LLM no veía el medio del artículo.
# Ahora entran chunks completos hasta este presupuesto total de caracteres
# (~2.8 caracteres/token medido con Qwen2.5 → 9000 ≈ 3,200 tokens).
RAG_CONTEXT_MAX_CHARS = _get_int_env("RAG_CONTEXT_MAX_CHARS", 9000, 500)
# Mejora 3 (2026-11-21): contexto por artículo. En la V3, 514 artículos están
# partidos en varios chunks (35 % del corpus). Con "1": (a) los chunks del mismo
# artículo (grupo_articulo_id) cuentan como UNA fuente, liberando lugar para otra;
# (b) a cada fuente se le agregan las partes vecinas del artículo hasta
# RAG_ARTICULO_MAX_CHARS (mediana de un artículo completo: 2,558 chars; p90: 6,201).
RAG_CONTEXTO_ARTICULO = os.getenv("RAG_CONTEXTO_ARTICULO", "1").strip() == "1"
RAG_ARTICULO_MAX_CHARS = _get_int_env("RAG_ARTICULO_MAX_CHARS", 4000, 500)
# Solo para ablación/experimentos: "1" reproduce el recorte antiguo (700 chars).
RAG_RECORTE_LEGACY_700 = os.getenv("RAG_RECORTE_LEGACY_700", "0").strip() == "1"
# Ventana de Ollama: explícita para que el prompt nunca se recorte en silencio.
# 8192 cuesta +0.2 GB de VRAM frente a 4096, sin pérdida de velocidad (medido).
OLLAMA_NUM_CTX = _get_int_env("OLLAMA_NUM_CTX", 8192, 2048)
# Las respuestas reales usan 300–500 tokens; 500 palabras ≈ 750 tokens.
OLLAMA_NUM_PREDICT = _get_int_env("OLLAMA_NUM_PREDICT", 1024, 64)
# Semilla fija del LLM (2026-11-21): sin ella dos corridas con la misma recuperación
# variaron la completitud de 0.24 a 0.14 (temperatura 0.2). Reproducibilidad
# exigida por la Revisión 3 §10. 0 = sin semilla.
OLLAMA_SEED = _get_int_env("OLLAMA_SEED", 42, 0)

# Margen extra sobre UMBRAL para declarar una pregunta "fuera de dominio"
# por embeddings (R04): si TODAS las distancias superan UMBRAL + MARGEN → M03.
# 2026-11-21 (bge-m3): corte = 0.41 + 0.09 = 0.50, justo sobre la distancia Top-1
# máxima de las positivas (0.492): una pregunta del dominio nunca recibe M03.
MARGEN_FUERA_DOMINIO = _get_float_env("RAG_MARGEN_FUERA_DOMINIO", 0.09, 0.0, 1.0)

# Re-ranking: descuento de distancia por cada keyword de la pregunta presente en
# el nombre del documento. 2026-11-21 (bge-m3): 0.02 (antes 0.07 con mpnet). Con
# bge-m3 los 4 primeros chunks distan 0.01–0.04 entre sí y 0.07 se imponía al
# embedding: Top-4 documento 0.892 → 0.923, artículo 0.873 → 0.907.
RAG_KEYWORD_BOOST = _get_float_env("RAG_KEYWORD_BOOST", 0.02, 0.0, 0.5)

# -----------------------------------------------------------------------------
# Dominio de consulta (sección 1 OE4)
# Categorías REALES indexadas en el corpus (A, B, C, D, E)
# -----------------------------------------------------------------------------
DOMINIO_CATEGORIAS = ["A", "B", "C", "D", "E"]

# Mapeo descriptivo de cada categoría real (inferido a partir del corpus indexado)
MAPEO_CATEGORIAS = {
    "A": {
        "nombre": "Gobierno y estatuto institucional",
        "descripcion": "Estatuto, reglamento general y normas marco de la UPeU.",
    },
    "B": {
        "nombre": "Académico y estudios",
        "descripcion": "Reglamentos de estudios, admisión, grados y títulos, idiomas, movilidad académica, publicaciones y fondo, pago servicios académicos.",
    },
    "C": {
        "nombre": "Investigación",
        "descripcion": "Reglamentos de investigación, ética, propiedad intelectual, publicaciones e incentivos.",
    },
    "D": {
        "nombre": "Bienestar estudiantil",
        "descripcion": "Reglamento del estudiante, becas, residencias universitarias, defensoría y reconocimientos.",
    },
    "E": {
        "nombre": "Laboral, docencia y políticas",
        "descripcion": "Reglamento interno de trabajo, docencia ordinaria, identidad visual y políticas institucionales.",
    },
}

# Palabras clave del dominio universitario UPeU (sección 1, validador R04/RF02)
KEYWORDS_DOMINIO = [
    # Académico
    "matrícula", "matricula", "asignatura", "curso", "carrera", "facultad",
    "escuela", "examen", "evaluación", "evaluacion", "nota", "calificación",
    "calificacion", "convalidación", "convalidacion", "traslado", "titulación",
    "titulacion", "grado", "título", "titulo", "bachiller", "tesis", "pregrado",
    "posgrado", "maestría", "maestria", "doctorado", "syllabus", "silabo",
    "sílabo", "horario", "sección", "seccion", "ciclo", "semestre", "créditos",
    "creditos", "promedio", "récord", "record",
    # Admisión
    "admisión", "admision", "ingreso", "postulante", "postulación", "postulacion",
    "vacante", "inscripción", "inscripcion",
    # Bienestar
    "beca", "becas", "apoyo", "psicológico", "psicologico", "seguro", "comedor",
    "residencia", "internado", "deporte", "cultural", "estudiantil",
    # Trámites
    "constancia", "certificado", "carnet", "duplicado", "trámite", "tramite",
    "solicitud", "documento", "formulario",
    # Cronogramas
    "cronograma", "calendario", "plazo", "fecha", "vacaciones",
    # Disciplina
    "reglamento", "norma", "disciplina", "falta", "sanción", "sancion",
    "descargo", "derecho", "deber", "convivencia",
    # Investigación
    "investigación", "investigacion", "proyecto", "publicación", "publicacion",
    "artículo", "articulo", "revista", "ética", "etica",
    # Institucional
    "upeu", "unión", "union", "universidad", "estudiante", "docente", "profesor",
    "alumno", "campus", "filial", "juliaca", "lima", "tarapoto",
    # Laboral / docencia
    "contrato", "docencia", "carga", "lectiva", "legajo",
]

# Palabras clave claramente FUERA del dominio (sección 2, R04 / R07)
KEYWORDS_FUERA_DOMINIO = [
    # Política / actualidad
    "presidente", "congreso", "elecciones", "partido político", "partido politico",
    # Deportes externos
    "messi", "ronaldo", "mundial", "fifa", "nba", "champions",
    # Entretenimiento
    "película", "pelicula", "netflix", "spotify", "tiktok", "instagram",
    # Tecnología / programación general
    "javascript", "python", "react", "linux", "android", "ios",
    # Salud no institucional
    "covid", "diabetes", "cáncer", "cancer", "medicamento",
    # Receta / cocina
    "receta", "cocinar", "comida", "ingrediente",
    # Datos personales / financieros del usuario (pedir info privada → M03)
    "dni", "deuda",
]

# Términos sensibles / éticos (R07) — disparan M03
KEYWORDS_ETICA = [
    "matar", "asesinar", "suicidio", "suicidarme",
    "discrimin", "racis", "xenof",
    "acoso", "violar", "agredir",
    "droga", "marihuana", "cocaína", "cocaina",
    "arma", "pistola", "explosivo",
]

# -----------------------------------------------------------------------------
# Anonimización de PII (sección 3.2 OE4, Ley 29733)
# Orden importa: el primer patrón que matchee gana.
# -----------------------------------------------------------------------------
PII_PATTERNS = [
    # Email (el más específico, debe ir primero)
    (re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", re.IGNORECASE), "[EMAIL]"),
    # Código de estudiante UPeU (letras + 8-10 dígitos)
    (re.compile(r"\b[A-Za-z]{1,3}\d{8,10}\b"), "[COD_EST]"),
    # Teléfono peruano con prefijo internacional (+51 9XXXXXXXX)
    (re.compile(r"\+?51\s?9\d{8}\b"), "[TEL]"),
    # Teléfono peruano móvil (9 + 8 dígitos = 9 dígitos)
    (re.compile(r"\b9\d{8}\b"), "[TEL]"),
    # DNI peruano (8 dígitos exactos)
    (re.compile(r"\b\d{8}\b"), "[DNI]"),
    # Otros identificadores largos (10-12 dígitos)
    (re.compile(r"\b\d{10,12}\b"), "[ID]"),
]

# -----------------------------------------------------------------------------
# Sesión y modo piloto (T07 OE4)
# -----------------------------------------------------------------------------
MODO_PILOTO = os.getenv("MODO_PILOTO", "true").lower() == "true"
LIMITE_PREGUNTAS_SESION = int(os.getenv("LIMITE_PREGUNTAS_SESION", "10"))

# Depuración: expone `debug_distancias` (y metadatos internos) en la respuesta
# de /consulta. Es independiente de MODO_PILOTO: en el piloto va "true" (igual
# que hoy); en un despliegue real se apaga y el frontend degrada con gracia.
DEBUG_LOG = os.getenv("DEBUG_LOG", "false").lower() == "true"

# -----------------------------------------------------------------------------
# Infraestructura
# -----------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000"
    ).split(",") if o.strip()
]

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://llm:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# -----------------------------------------------------------------------------
# Versionado técnico (Fase 5, §20) — centralizado para trazabilidad
# -----------------------------------------------------------------------------
# 2026-11-21: migración a corpus V3 (OE1) + bge-m3. Configurables por entorno
# para poder volver a la V2 (S3 de la matriz de sistemas) sin tocar código:
#   EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2 EMBEDDING_REVISION=
#   CORPUS_VERSION=corpus_upeu_v2  (+ montar vector_store_backup_v2_20261121)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")  # 1024 dim
# Revisión fijada del modelo (la misma con la que OE1 indexó el corpus V3).
# Vacía → última versión del modelo (solo para mpnet/V2).
EMBEDDING_REVISION = os.getenv(
    "EMBEDDING_REVISION", "5617a9f61b028005a4858fdac845db406aefb181"
) or None
CORPUS_VERSION = os.getenv("CORPUS_VERSION", "corpus_upeu_v3_bgem3")  # colección ChromaDB vigente
PROMPT_VERSION = "v2-adaptativo"  # prompt con formato adaptativo y guardrails
RANKING_METHOD = "heuristic_keyword_boost"
RANKING_VERSION = "1.1"  # boost por keyword (RAG_KEYWORD_BOOST, 0.02) en nombre de documento; 1.0 = 0.07

# -----------------------------------------------------------------------------
# Mensajes de transparencia (sección 4 OE4) — M01 a M07
# -----------------------------------------------------------------------------
MENSAJES = {
    "M01": "Hola, soy un asistente basado en IA generativa. Mis respuestas se fundamentan en documentos institucionales oficiales de la Universidad Peruana Unión (reglamentos, instructivos, cronogramas y lineamientos vigentes). Recuerda que mi función es informativa y no reemplaza la validación administrativa oficial. Si necesitas resolver un trámite personal, contacta directamente con la oficina correspondiente.",
    # M02 ya no se concatena al cuerpo (lo renderiza el frontend).
    # Se conserva la clave para trazabilidad/telemetría.
    "M02": "",
    "M03": "Lo siento, solo puedo ayudarte con consultas sobre reglamentos académicos, procedimientos administrativos, cronogramas, bienestar estudiantil y normas de convivencia de la UPeU. Tu pregunta está fuera de mi alcance. Si necesitas información personalizada o confidencial, te recomiendo acudir a la oficina administrativa correspondiente.",
    "M04": "No encontré información suficiente en los documentos institucionales disponibles para responder tu pregunta con confianza. Te sugiero revisar directamente el documento [nombre del documento relacionado más cercano] o contactar con la oficina correspondiente para una respuesta precisa.",
    "M05": "No entendí claramente tu pregunta. ¿Podrías reformularla con más detalles? Por ejemplo, indica el tipo de trámite, el documento o el procedimiento específico que te interesa.",
    "M06": "Ocurrió un error al procesar tu consulta. Por favor, inténtalo de nuevo más tarde. Si el problema persiste, contacta con soporte técnico.",
    "M07": "Respuesta generada por inteligencia artificial. La UPeU no se hace responsable por el uso indebido de la información. Verifica con fuentes oficiales cuando sea necesario.",
    # Mensaje adicional para límite de sesión (T07)
    "M08_LIMITE": f"Has alcanzado el límite de {LIMITE_PREGUNTAS_SESION} preguntas para esta sesión (modo piloto OE8). Gracias por participar.",
}
