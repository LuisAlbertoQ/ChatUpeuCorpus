import sqlite3
import datetime

DB_PATH = "./registro_interacciones.db"

def inicializar_bd():
    """Crea la tabla de interacciones si no existe."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pregunta TEXT NOT NULL,
                respuesta TEXT NOT NULL,
                fuentes TEXT,
                tiempo_respuesta REAL,
                umbral_usado REAL,
                tipo_mensaje TEXT
            )
        """)
    print("Base de datos de registro inicializada.")

def registrar_interaccion(pregunta, respuesta, fuentes, tiempo_respuesta, umbral, tipo_mensaje):
    """Inserta un registro de interacción."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO interacciones (timestamp, pregunta, respuesta, fuentes, tiempo_respuesta, umbral_usado, tipo_mensaje) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.datetime.now().isoformat(),
                pregunta,
                respuesta,
                ", ".join(fuentes) if fuentes else "",
                tiempo_respuesta,
                umbral,
                tipo_mensaje
            )
        )