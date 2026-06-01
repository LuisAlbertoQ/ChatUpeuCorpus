import sqlite3
import datetime
from contextlib import contextmanager
from config import PII_PATTERNS

DB_PATH = "./registro_interacciones.db"


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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacciones_sesion ON interacciones(sesion_id)"
        )
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
    """Elimina todas las interacciones de una sesión (sección 3.4 OE4).

    Retorna el número de registros eliminados.
    """
    if not sesion_id:
        return 0
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM interacciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return cur.rowcount
