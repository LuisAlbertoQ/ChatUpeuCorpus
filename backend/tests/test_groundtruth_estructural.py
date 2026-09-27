# -*- coding: utf-8 -*-
"""
Tests estructurales para ground truth de generación (sin semántica, sin Qwen).
Verifica que la curación v3_curado sea completa y no inventada.
"""
import json
import sqlite3
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
# Soporta host (PROJECT_ROOT/evaluacion) y Docker (/data/evaluacion, /app)
_CANDIDATE_JSON = [
    PROJECT_ROOT / "evaluacion" / "banco" / "preguntas_comparacion.json",
    pathlib.Path("/data/evaluacion/banco/preguntas_comparacion.json"),
    pathlib.Path("/app/evaluacion/banco/preguntas_comparacion.json"),
    pathlib.Path("/app/../evaluacion/banco/preguntas_comparacion.json"),
]
JSON_PATH = next((p for p in _CANDIDATE_JSON if p.exists()), _CANDIDATE_JSON[0])
_CANDIDATE_DB = [
    PROJECT_ROOT / "registro_interacciones.db",
    pathlib.Path("/data/registro_interacciones.db"),
    pathlib.Path("/app/registro_interacciones.db"),
]
DB_PATH = next((p for p in _CANDIDATE_DB if p.exists()), _CANDIDATE_DB[0])

def _load_json():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))

def _db():
    # asegurar esquema – soporta /app (Docker monta ./backend como /app)
    import sys
    for cand in [PROJECT_ROOT / "backend", pathlib.Path("/app"), pathlib.Path("/app/backend")]:
        if cand.exists():
            sys.path.insert(0, str(cand))
            break
    import logger
    orig = logger.DB_PATH
    logger.DB_PATH = str(DB_PATH)
    logger.inicializar_bd()
    logger.DB_PATH = orig
    return sqlite3.connect(str(DB_PATH))

def test_json_valido_y_17_q():
    data = _load_json()
    assert isinstance(data, list)
    q_ids = [d["id"] for d in data if d["id"].startswith("Q")]
    assert len(q_ids) == 17, f"esperado 17 Q, hallado {len(q_ids)}"
    # IDs únicos
    assert len(set(q_ids)) == 17

def test_punto_id_unico():
    conn = _db()
    rows = conn.execute("SELECT puntos_esperados FROM banco_preguntas WHERE id LIKE 'Q%'").fetchall()
    pids = []
    for (j,) in rows:
        if not j:
            continue
        arr = json.loads(j)
        for p in arr:
            pids.append(p["punto_id"])
    assert len(pids) == len(set(pids)), f"punto_id duplicado: {pids}"
    # total 50 (variable, no 51)
    assert len(pids) == 50, f"esperado 50 puntos (variable), hallado {len(pids)}"
    conn.close()

def test_ningun_obligatorio_sin_evidencia():
    conn = _db()
    rows = conn.execute("SELECT id, puntos_esperados, evidencias_esperadas FROM banco_preguntas WHERE id LIKE 'Q%'").fetchall()
    for pid, puntos_j, ev_j in rows:
        puntos = json.loads(puntos_j) if puntos_j else []
        evs = json.loads(ev_j) if ev_j else []
        ev_map = {e["punto_id"] for e in evs}
        for p in puntos:
            if p.get("obligatorio"):
                assert p["punto_id"] in ev_map, f"{pid} punto {p['punto_id']} obligatorio sin evidencia"
                # evidencia debe tener texto_evidencia no vacío
                ev = next(e for e in evs if e["punto_id"] == p["punto_id"])
                assert ev.get("texto_evidencia") and len(ev["texto_evidencia"].strip()) > 20, f"{p['punto_id']} texto_evidencia vacío"
    conn.close()

def test_evidencias_punto_id_existe():
    conn = _db()
    rows = conn.execute("SELECT puntos_esperados, evidencias_esperadas FROM banco_preguntas WHERE id LIKE 'Q%'").fetchall()
    for puntos_j, ev_j in rows:
        puntos = {p["punto_id"] for p in json.loads(puntos_j)} if puntos_j else set()
        evs = json.loads(ev_j) if ev_j else []
        for e in evs:
            assert e["punto_id"] in puntos, f"evidencia {e['punto_id']} sin punto"
    conn.close()

def test_no_forzado_a_3_variable():
    conn = _db()
    rows = conn.execute("SELECT id, json_array_length(puntos_esperados) as n FROM banco_preguntas WHERE id LIKE 'Q%' ORDER BY id").fetchall()
    counts = {r[0]: r[1] for r in rows}
    # Q11 debe tener 2, Q15 4, Q17 2 (variable)
    assert counts["Q11"] == 2, f"Q11 esperado 2, hallado {counts['Q11']}"
    assert counts["Q15"] == 4, f"Q15 esperado 4 (split), hallado {counts['Q15']}"
    assert counts["Q17"] == 2, f"Q17 esperado 2, hallado {counts['Q17']}"
    # asegurar no todos 3
    assert len(set(counts.values())) > 1, "todos forzados a 3, debe ser variable"
    conn.close()

def test_curado_sin_pendiente():
    conn = _db()
    rows = conn.execute("SELECT id, puntos_esperados FROM banco_preguntas WHERE id LIKE 'Q%'").fetchall()
    for qid, j in rows:
        arr = json.loads(j) if j else []
        for p in arr:
            assert p.get("estado") == "CURADO", f"{qid} {p['punto_id']} estado {p.get('estado')} != CURADO"
            assert "PENDIENTE" not in p.get("estado", ""), f"{qid} aún pendiente"
    # Q09 debe estar curado aunque sin artículo
    row = conn.execute("SELECT puntos_esperados FROM banco_preguntas WHERE id='Q09'").fetchone()
    assert json.loads(row[0])[0]["estado"] == "CURADO"
    conn.close()

def test_q09_doc_correcto():
    conn = _db()
    row = conn.execute("SELECT documento_esperado FROM banco_preguntas WHERE id='Q09'").fetchone()
    assert row[0] == "Politica Institucional de trabajo digno y protección de la persona v.1", f"Q09 doc incorrecto: {row[0]}"
    assert "TUPA" not in row[0], "Q09 no debe ser TUPA"
    conn.close()
    data = _load_json()
    q09 = next(d for d in data if d["id"] == "Q09")
    assert q09["documento_esperado"] == "Politica Institucional de trabajo digno y protección de la persona v.1"
    assert q09["articulo_esperado"] == "", "Q09 sin artículo (document-level)"

def test_q11_articulo_null_permitido():
    conn = _db()
    row = conn.execute("SELECT articulo_esperado FROM banco_preguntas WHERE id='Q11'").fetchone()
    assert row[0] == "" or row[0] is None, f"Q11 articulo debe ser vacío/null, hallado {row[0]}"
    conn.close()

def test_q01_q04_q07_corregidos():
    conn = _db()
    q01 = conn.execute("SELECT documento_esperado, articulo_esperado FROM banco_preguntas WHERE id='Q01'").fetchone()
    assert q01[1] == "Artículo 19°", f"Q01 articulo corregido a 19°, hallado {q01[1]}"
    q04 = conn.execute("SELECT documento_esperado, articulo_esperado FROM banco_preguntas WHERE id='Q04'").fetchone()
    assert q04[0] == "REGLAMENTO DE ESTUDIOS V5_2025", f"Q04 doc corregido a DE ESTUDIOS, hallado {q04[0]}"
    assert q04[1] == "Artículo 70°", f"Q04 art 70°, hallado {q04[1]}"
    q07 = conn.execute("SELECT articulo_esperado FROM banco_preguntas WHERE id='Q07'").fetchone()
    assert q07[0] == "Artículo 13°", f"Q07 art 13°, hallado {q07[0]}"
    conn.close()

def test_metricas_humanas_null():
    # generación aún no evaluada -> evaluacion_generacion debe estar vacía o con humanas NULL
    conn = _db()
    rows = conn.execute("SELECT citation_correctness_humana FROM evaluacion_generacion").fetchall()
    for (v,) in rows:
        assert v is None, "métrica humana debe ser NULL antes de generación"
    conn.close()

def test_sincronizacion_idempotente():
    conn = _db()
    before = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    conn.close()
    import sys as _sys
    for cand in [PROJECT_ROOT / "evaluacion" / "banco", pathlib.Path("/data/evaluacion/banco"), pathlib.Path("/app/evaluacion/banco")]:
        if cand.exists():
            _sys.path.insert(0, str(cand))
            break
    import importlib
    mod = importlib.import_module("sincronizar_banco")
    import importlib as _imp
    _imp.reload(mod)
    mod.main()
    conn = _db()
    after = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    assert before == after, f"idempotencia falló {before} != {after}"
    _imp.reload(mod)
    mod.main()
    conn2 = _db()
    after2 = conn2.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    assert after == after2
    conn.close()
    conn2.close()

def test_banco_version_v3():
    conn = _db()
    rows = conn.execute("SELECT DISTINCT banco_version FROM banco_preguntas WHERE id LIKE 'Q%'").fetchall()
    versions = {r[0] for r in rows}
    assert versions == {"v3_curado"}, f"esperado v3_curado, hallado {versions}"
    # P01-P08 preservados sin versión
    prow = conn.execute("SELECT banco_version FROM banco_preguntas WHERE id='P01'").fetchone()
    assert prow[0] is None, "P01 debe preservar NULL"
    conn.close()
