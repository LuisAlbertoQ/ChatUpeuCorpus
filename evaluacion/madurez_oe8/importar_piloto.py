#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Importa respuestas reales del piloto OE8 (validación estricta, idempotente).
Uso: python evaluacion/madurez_oe8/importar_piloto.py evaluacion/madurez_oe8/respuestas_piloto.csv
NO genera datos ficticios. Solo participantes 30/30 entran al promedio oficial
(vía consolidar_piloto.py); incompletos se conservan para auditoría."""
import csv, json, sqlite3, sys, datetime
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB = PROJECT_ROOT / "registro_interacciones.db"
INSTRUMENTO = Path(__file__).parent / "instrumento_piloto_oe8_v1.json"

def cargar_instrumento():
    data = json.loads(INSTRUMENTO.read_text(encoding="utf-8"))
    return {i["item_id"]: i["dimension"] for i in data["items"]}, data["version"]

def validar_fila(row, items, n_linea):
    errs = []
    pid = (row.get("participante_id_anonimo") or "").strip()
    iid = (row.get("item_id") or "").strip()
    dim = (row.get("dimension") or "").strip()
    val = (row.get("respuesta_likert") or "").strip()
    if not pid:
        errs.append(f"línea {n_linea}: participante vacío")
    if iid not in items:
        errs.append(f"línea {n_linea}: item inexistente {iid!r}")
    elif dim != items[iid]:
        errs.append(f"línea {n_linea}: dimensión {dim!r} no corresponde a {iid}")
    try:
        v = int(val)
        if not 1 <= v <= 5:
            errs.append(f"línea {n_linea}: Likert fuera de rango {val!r}")
    except ValueError:
        errs.append(f"línea {n_linea}: Likert inválido {val!r}")
    return errs, (pid, iid, dim, int(val) if not errs else None)

def main():
    if len(sys.argv) < 2:
        print("Uso: python importar_piloto.py <respuestas.csv>")
        return 1
    items, version = cargar_instrumento()
    path = Path(sys.argv[1])
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    # omitir filas totalmente vacías o con likert en blanco (plantilla de ejemplo)
    rows = [r for r in rows if (r.get("respuesta_likert") or "").strip() != ""]
    errores, validas = [], []
    vistos = set()
    for i, r in enumerate(rows, 2):
        errs, parsed = validar_fila(r, items, i)
        errores.extend(errs)
        if errs:
            continue
        pid, iid, dim, v = parsed
        if len([x for x in validas if x[0] == pid]) >= 30 or (pid, iid) in vistos:
            if (pid, iid) in vistos:
                errores.append(f"línea {i}: duplicado {pid}/{iid}")
            else:
                errores.append(f"línea {i}: participante {pid} con más de 30 respuestas")
            continue
        vistos.add((pid, iid))
        validas.append((pid, iid, dim, v))
    if errores:
        print("ERRORES (no se importó nada):")
        for e in errores:
            print(" -", e)
        return 1
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    import logger
    logger.DB_PATH = str(DB)
    logger.inicializar_bd()
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS piloto_respuestas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participante_id_anonimo TEXT NOT NULL,
        fecha TEXT NOT NULL,
        item_id TEXT NOT NULL,
        dimension TEXT NOT NULL,
        respuesta_likert INTEGER NOT NULL,
        instrumento_version TEXT NOT NULL,
        UNIQUE(participante_id_anonimo, item_id))""")
    hoy = datetime.date.today().isoformat()
    nuevas = 0
    for pid, iid, dim, v in validas:
        try:
            conn.execute("INSERT INTO piloto_respuestas (participante_id_anonimo, fecha, item_id, dimension, respuesta_likert, instrumento_version) VALUES (?,?,?,?,?,?)",
                (pid, hoy, iid, dim, v, version))
            nuevas += 1
        except sqlite3.IntegrityError:
            print(f"duplicado histórico {pid}/{iid}: no overwrite")
    conn.commit()
    # estado por participante
    for (pid,) in conn.execute("SELECT DISTINCT participante_id_anonimo FROM piloto_respuestas"):
        n = conn.execute("SELECT count(*) FROM piloto_respuestas WHERE participante_id_anonimo=?", (pid,)).fetchone()[0]
        print(f"{pid}: {n}/30 {'COMPLETO' if n == 30 else 'INCOMPLETO (no entra al promedio oficial)'}")
    conn.close()
    print(f"Importadas {nuevas} respuestas nuevas (idempotente).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
