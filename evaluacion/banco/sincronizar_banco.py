#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronización idempotente JSON ↔ SQLite para banco_preguntas.

Lee evaluacion/banco/preguntas_comparacion.json (17 preguntas v2) y hace
upsert en registro_interacciones.db:banco_preguntas basado en id estable.

- No borra preguntas existentes (preserva P01-P08 históricos).
- No duplica en segunda ejecución (idempotente via INSERT OR REPLACE con
  preservación de campos ya curados).
- Campos nuevos (tipo_pregunta, cobertura_esperada, etc.) quedan NULL
  hasta curación manual; no se inventan.

Uso:
  python evaluacion/banco/sincronizar_banco.py
  docker compose run --rm backend python /data/evaluacion/banco/sincronizar_banco.py
"""

import json
import sqlite3
import sys
from pathlib import Path

# Rutas relativas al proyecto (funciona tanto en host como en contenedor)
EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent.parent.parent
JSON_PATH = EVAL_DIR / "preguntas_comparacion.json"
DB_PATHS = [
    PROJECT_ROOT / "registro_interacciones.db",
    Path("/data/registro_interacciones.db"),
]


def find_db() -> Path:
    for p in DB_PATHS:
        if p.exists():
            return p
    # Fallback al primero aunque no exista (será creado por inicializar_bd)
    return DB_PATHS[0]


def main() -> int:
    if not JSON_PATH.exists():
        print(f"ERROR: no existe {JSON_PATH}", file=sys.stderr)
        return 1

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print(f"Banco JSON: {len(data)} preguntas en {JSON_PATH.name}")

    db_path = find_db()
    print(f"DB: {db_path} (existe={db_path.exists()})")

    # Asegurar esquema actualizado
    # Importar logger para reutilizar inicializar_bd (que hace ALTER ADD COLUMN)
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    try:
        import logger
        # Si DB_PATH en logger apunta a otro lado, temporalmente ajustarlo
        orig_db = getattr(logger, "DB_PATH", None)
        logger.DB_PATH = str(db_path)
        logger.inicializar_bd()
        if orig_db:
            logger.DB_PATH = orig_db
    except Exception as e:
        print(f"WARN: no se pudo inicializar BD via logger: {e}", file=sys.stderr)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    # Contar antes
    before = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    print(f"Filas antes: {before}")

    # Upsert idempotente: INSERT OR REPLACE pero preservando campos curados
    # Estrategia: INSERT OR IGNORE para nuevas, luego UPDATE solo de campos provenientes de JSON
    # Para no sobrescribir campos ya curados manualmente (tipo_pregunta etc.), solo actualizamos
    # los campos que vienen de JSON y dejamos los nuevos como están si ya tienen valor.
    inserted = 0
    updated = 0
    for entry in data:
        pid = entry.get("id")
        if not pid:
            continue
        pregunta = entry.get("pregunta", "")
        categoria = entry.get("categoria_objetivo", "") or entry.get("categoria", "")
        documento = entry.get("documento_esperado", "")
        articulo = entry.get("articulo_esperado", "")
        tipo_pregunta = entry.get("tipo_pregunta")
        cobertura = entry.get("cobertura_esperada", "ANSWERABLE")
        tema = entry.get("tema", "")

        # Verificar si ya existe
        cur = conn.execute("SELECT id FROM banco_preguntas WHERE id = ?", (pid,))
        exists = cur.fetchone() is not None

        # Determinar banco_version para Q01-Q17 vs P01-P08
        # Q: v3_curado (ground truth con texto_evidencia literal), P: NULL/histórico (preservar)
        banco_version = "v3_curado" if pid.startswith("Q") else None

        if not exists:
            # Insertar nueva fila; nuevos campos con valores curados de JSON o NULL si no verificable
            conn.execute(
                """
                INSERT INTO banco_preguntas
                    (id, pregunta, tipo_consulta, documento_esperado, categoria_esperada, activa,
                     categoria, tipo_pregunta, cobertura_esperada, articulo_esperado,
                     documentos_esperados, articulos_esperados, banco_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    pregunta,
                    "dentro_dominio",
                    documento,
                    categoria,
                    1,
                    categoria,
                    tipo_pregunta,
                    cobertura,
                    articulo,
                    json.dumps([documento], ensure_ascii=False) if documento else None,
                    json.dumps([articulo], ensure_ascii=False) if articulo else None,
                    banco_version,
                ),
            )
            inserted += 1
        else:
            # Actualizar desde JSON canónico; para corrección taxonómica Q07/Q08/Q13/Q14/Q17
            # se sobrescribe tipo_pregunta/cobertura con valor curado de JSON (no COALESCE)
            # para aplicar la corrección metodológica; otros campos preservan curación si ya existe
            conn.execute(
                """
                UPDATE banco_preguntas
                SET pregunta = ?,
                    documento_esperado = ?,
                    categoria_esperada = ?,
                    categoria = COALESCE(categoria, ?),
                    tipo_pregunta = ?,
                    cobertura_esperada = ?,
                    articulo_esperado = ?,
                    documentos_esperados = COALESCE(documentos_esperados, ?),
                    articulos_esperados = COALESCE(articulos_esperados, ?),
                    banco_version = COALESCE(banco_version, ?)
                WHERE id = ?
                """,
                (
                    pregunta,
                    documento,
                    categoria,
                    categoria,
                    tipo_pregunta,
                    cobertura,
                    articulo,
                    json.dumps([documento], ensure_ascii=False) if documento else None,
                    json.dumps([articulo], ensure_ascii=False) if articulo else None,
                    banco_version,
                    pid,
                ),
            )
            if conn.total_changes > 0:
                updated += 1

    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    conn.close()

    print(f"Insertadas: {inserted}, actualizadas: {updated}")
    print(f"Filas después: {after} (esperado {before + inserted})")
    print(f"Idempotencia: segunda ejecución debe dar 0 insertadas y mismo total {after}")

    # Verificación
    if after != before + inserted:
        print(f"WARN: conteo inesperado", file=sys.stderr)
    print("Sincronización completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
