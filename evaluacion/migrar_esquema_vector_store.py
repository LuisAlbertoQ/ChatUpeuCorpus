"""
migrar_esquema_vector_store.py
==============================

ESTADO: ONE-SHOT YA EJECUTADO (junio 2026). NO requiere re-ejecución.
El vector_store actual ya tiene las columnas `topic` y el sistema
funciona correctamente con chromadb 0.4.22.

CONSERVADO POR: trazabilidad de auditoría (OE4) y reproducibilidad
(reinstalación con un vector_store antiguo).

PROPÓSITO ORIGINAL:
Migra el vector_store del esquema chromadb 1.x (config_json_str, schema_str)
de vuelta al esquema esperado por chromadb 0.4.22 (topic).

Sintomas:
  sqlite3.OperationalError: no such column: collections.topic
  sqlite3.OperationalError: no such column: segments.topic

Causa:
  El vector_store fue creado con chromadb 1.x, que migra el esquema al
  acceder. Al volver a chromadb 0.4.22, las queries fallan porque
  esperan columnas topic que ya no existen en el nuevo esquema.

Este script es IDEMPOTENTE: si las columnas ya existen, no hace nada.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "vector_store" / "chroma.sqlite3"
if not DB_PATH.exists():
    print(f"ERROR: {DB_PATH} no existe")
    sys.exit(1)

c = sqlite3.connect(str(DB_PATH))
cur = c.cursor()

def has_column(table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

migrations = [
    ("collections", "topic", "ALTER TABLE collections ADD COLUMN topic TEXT NOT NULL DEFAULT ''"),
    ("segments",    "topic", "ALTER TABLE segments    ADD COLUMN topic TEXT"),
]

applied = 0
for table, column, sql in migrations:
    if has_column(table, column):
        print(f"  [SKIP] {table}.{column} ya existe")
        continue
    print(f"  [APPLY] {table}.{column} ...")
    cur.execute(sql)
    applied += 1

c.commit()

print(f"\nMigraciones aplicadas: {applied}")
print("\n=== VERIFICACION ===")
for table, column, _ in migrations:
    print(f"  {table}.{column}: {'OK' if has_column(table, column) else 'FALTA'}")

c.close()
