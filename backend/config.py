import logging
import os
import re

log = logging.getLogger("config")

# =============================================================================
# OE4 v2.0 — Configuración del sistema conversacional UPeU
# =============================================================================

# -----------------------------------------------------------------------------
# Umbrales RAG — configurables por entorno (Fase 4, §8/10/11)
# Defaults: threshold 0.40, TOP_K_RAW 15, TOP_K_FINAL 4. Variables RAG_*
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


RAG_DISTANCE_THRESHOLD = _get_float_env("RAG_DISTANCE_THRESHOLD", 0.40, 0.0, 1.0)
RAG_TOP_K_RAW = _get_int_env("RAG_TOP_K_RAW", 15, 1)
RAG_TOP_K_FINAL = _get_int_env("RAG_TOP_K_FINAL", 4, 1)

# Alias por compatibilidad — no duplicar fuente de verdad
UMBRAL_DISTANCIA_COSENO = RAG_DISTANCE_THRESHOLD
TOP_K_FRAGMENTOS = RAG_TOP_K_FINAL

MAX_PALABRAS_RESPUESTA = 500
TIMEOUT_RESPUESTA = 50  # segundos; holgura para qwen 2.5 en respuestas largas

# Margen extra sobre UMBRAL para declarar una pregunta "fuera de dominio"
# por embeddings (R04): si TODAS las distancias superan UMBRAL + MARGEN → M03.
MARGEN_FUERA_DOMINIO = 0.10

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
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"  # 768 dim, mpnet
CORPUS_VERSION = "corpus_upeu_v2"  # colección ChromaDB vigente
PROMPT_VERSION = "v2-adaptativo"  # prompt con formato adaptativo y guardrails
RANKING_METHOD = "heuristic_keyword_boost"
RANKING_VERSION = "1.0"  # boost +0.07 por keyword en nombre de documento

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
