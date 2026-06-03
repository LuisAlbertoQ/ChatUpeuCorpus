#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrar_banco.py

Migra el banco de preguntas desde CSV a la tabla `banco_preguntas`
de `registro_interacciones.db`. Operación idempotente (usa
INSERT OR IGNORE sobre la PK).

Uso:
    python migrar_banco.py

Después de una migración exitosa, el archivo `banco_preguntas.csv`
puede eliminarse de forma segura.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

EVAL_DIR = Path(__file__).parent
DB_PATH = EVAL_DIR.parent / "registro_interacciones.db"
CSV_PATH = EVAL_DIR / "banco_preguntas.csv"


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: no se encontró la base de datos en {DB_PATH}.")
        print("Inicia el backend al menos una vez para que se cree el esquema.")
        return 1

    if not CSV_PATH.exists():
        print(f"ERROR: no se encontró {CSV_PATH}.")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    insertados = 0
    saltados = 0
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO banco_preguntas
                    (id, pregunta, tipo_consulta, documento_esperado,
                     categoria_esperada, activa)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        fila["id"],
                        fila["pregunta"],
                        fila["tipo_consulta"],
                        fila.get("documento_esperado", ""),
                        fila.get("categoria_esperada"),
                    ),
                )
                if cur.rowcount > 0:
                    insertados += 1
                else:
                    saltados += 1
            except KeyError as exc:
                print(f"ERROR: columna faltante en CSV: {exc}")
                conn.close()
                return 1

    conn.commit()

    cur = conn.execute("SELECT COUNT(*) FROM banco_preguntas")
    total = cur.fetchone()[0]
    conn.close()

    print(f"Migración completada.")
    print(f"  Filas nuevas insertadas:  {insertados}")
    print(f"  Filas ya existentes:      {saltados}")
    print(f"  Total en banco_preguntas: {total}")
    print(f"\nEl archivo {CSV_PATH.name} ya no es necesario; puedes eliminarlo.")
    return 0


if __name__ == "__main__":
    exit(main())
