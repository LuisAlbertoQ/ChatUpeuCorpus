import sqlite3
import datetime
from contextlib import contextmanager
from config import PII_PATTERNS

DB_PATH = "/data/registro_interacciones.db"


# -----------------------------------------------------------------------------
# Anonimización (sección 3.2 OE4 + Ley 29733)
# -----------------------------------------------------------------------------
def anonimizar(texto: str) -> str:
    """Aplica los patrones PII configurados sobre el texto.

    Reemplaza DNI, emails, teléfonos y códigos de estudiante por etiquetas
    no reversibles antes de persistir cualquier dato.
    """
    if not texto:
        return texto
    resultado = texto
    for patron, reemplazo in PII_PATTERNS:
        resultado = patron.sub(reemplazo, resultado)
    return resultado


# -----------------------------------------------------------------------------
# Conexión y esquema
# -----------------------------------------------------------------------------
@contextmanager
def _conn():
    """Context manager con foreign keys habilitadas."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columnas_existentes(conn, tabla: str) -> set:
    cur = conn.execute(f"PRAGMA table_info({tabla})")
    return {row[1] for row in cur.fetchall()}


def inicializar_bd():
    """Crea la tabla y aplica migraciones no destructivas si faltan columnas."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pregunta TEXT NOT NULL,
                respuesta TEXT NOT NULL,
                fuentes TEXT,
                tiempo_respuesta REAL,
                umbral_usado REAL,
                tipo_mensaje TEXT,
                sesion_id TEXT,
                error TEXT
            )
            """
        )
        # Migración para BDs antiguas que ya tengan datos
        existentes = _columnas_existentes(conn, "interacciones")
        if "sesion_id" not in existentes:
            conn.execute("ALTER TABLE interacciones ADD COLUMN sesion_id TEXT")
        if "error" not in existentes:
            conn.execute("ALTER TABLE interacciones ADD COLUMN error TEXT")
        if "anonimizado_en" not in existentes:
            conn.execute("ALTER TABLE interacciones ADD COLUMN anonimizado_en TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacciones_sesion ON interacciones(sesion_id)"
        )

        # ---------------------------------------------------------------------
        # Tablas para evaluación de madurez (OE8, modelo CMMI--TRL)
        # ---------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS banco_preguntas (
                id TEXT PRIMARY KEY,
                pregunta TEXT NOT NULL,
                tipo_consulta TEXT NOT NULL,
                documento_esperado TEXT,
                categoria_esperada TEXT,
                activa INTEGER DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_piloto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_id TEXT,
                pregunta_id TEXT,
                timestamp TEXT NOT NULL,
                funcional INTEGER,
                recuperacion INTEGER,
                explicabilidad INTEGER,
                usabilidad INTEGER,
                gobernanza INTEGER,
                preparacion INTEGER,
                observacion TEXT,
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_automatica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo TEXT NOT NULL,
                fecha_calculo TEXT NOT NULL,
                total_interacciones INTEGER,
                pct_m02 REAL,
                pct_m03 REAL,
                pct_m04 REAL,
                pct_m05 REAL,
                pct_m06 REAL,
                pct_con_fuentes REAL,
                tiempo_promedio REAL,
                tiempo_p95 REAL,
                funcional_auto REAL,
                recuperacion_auto REAL,
                explicabilidad_auto REAL,
                usabilidad_auto REAL,
                gobernanza_auto REAL,
                preparacion_auto REAL
            )
            """
        )
        # Migración no destructiva: añadir resumen si falta
        cols_auto = _columnas_existentes(conn, "evaluacion_automatica")
        if "puntaje_global" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN puntaje_global REAL")
        if "nivel" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN nivel TEXT")
        if "dimension_critica_minima" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN dimension_critica_minima REAL")
    print("Base de datos de registro inicializada.")


# -----------------------------------------------------------------------------
# Operaciones
# -----------------------------------------------------------------------------
def registrar_interaccion(
    pregunta: str,
    respuesta: str,
    fuentes,
    tiempo_respuesta: float,
    umbral: float,
    tipo_mensaje: str,
    sesion_id: str = "",
    error: str = "",
):
    """Inserta un registro de interacción ya anonimizado (sección 3.2)."""
    pregunta_anon = anonimizar(pregunta)
    respuesta_anon = anonimizar(respuesta)
    fuentes_txt = ", ".join(fuentes) if fuentes else ""

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO interacciones
                (timestamp, pregunta, respuesta, fuentes,
                 tiempo_respuesta, umbral_usado, tipo_mensaje,
                 sesion_id, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(),
                pregunta_anon,
                respuesta_anon,
                fuentes_txt,
                tiempo_respuesta,
                umbral,
                tipo_mensaje,
                sesion_id or "",
                error or "",
            ),
        )


def contar_preguntas_sesion(sesion_id: str) -> int:
    """Cuenta interacciones registradas para una sesión (T07 modo piloto)."""
    if not sesion_id:
        return 0
    with _conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM interacciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return cur.fetchone()[0]


def eliminar_por_sesion(sesion_id: str) -> int:
    """Borra físicamente las filas de una sesión (uso administrativo).

    El endpoint público usa `anonimizar_por_sesion` para preservar
    la data agregada (tipo_mensaje, tiempo, error) útil para
    evaluación (OE6) sin retener contenido personal.
    """
    if not sesion_id:
        return 0
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM interacciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return cur.rowcount


def anonimizar_por_sesion(sesion_id: str) -> int:
    """Sección 3.4 OE4 — derecho al olvido vía seudonimización.

    Cumple el derecho de supresión de la Ley 29733 eliminando el
    único nexo entre la fila y el usuario (`sesion_id`); preserva
    el contenido (pregunta, respuesta, fuentes) para evaluación y
    entrenamiento de madurez, ya que esos campos YA pasan por
    `anonimizar()` al insertarse (DNI/email/tel/cod_est →
    `[DNI]`/`[EMAIL]`/`[TEL]`/`[COD_EST]`).

    - `sesion_id`        → 'anonimizado'   (corte del nexo personal)
    - `error`            → ''              (limpia stack traces)
    - `anonimizado_en`   → timestamp       (auditoría)
    - `pregunta`, `respuesta`, `fuentes` → SE PRESERVAN
    - `tipo_mensaje`, `tiempo_respuesta`, `umbral_usado`, `timestamp` → SE PRESERVAN

    Retorna el número de filas seudonimizadas. Es idempotente.
    """
    if not sesion_id:
        return 0
    placeholder_sesion = "anonimizado"
    with _conn() as conn:
        cur = conn.execute(
            """
            UPDATE interacciones
               SET sesion_id      = ?,
                   error          = '',
                   anonimizado_en = ?
             WHERE sesion_id = ?
               AND anonimizado_en IS NULL
            """,
            (
                placeholder_sesion,
                datetime.datetime.now().isoformat(),
                sesion_id,
            ),
        )
        return cur.rowcount
