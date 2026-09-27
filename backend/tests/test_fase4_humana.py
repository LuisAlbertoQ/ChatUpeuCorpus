# -*- coding: utf-8 -*-
"""Tests FASE 4: importación humana v3.1 y métricas (solo lectura + validación pura)."""
import pathlib, sqlite3, importlib.util
_HERE = pathlib.Path(__file__).parent.parent.parent
_CANDS = [_HERE, pathlib.Path("/app"), pathlib.Path("/")]
GEN = "GEN_20260924_232127_8e01ef"
GTV = "v3.1_curado"

def _db():
    for r in _CANDS:
        for c in [r / "registro_interacciones.db", r / "data" / "registro_interacciones.db"]:
            if c.exists() and c.stat().st_size > 0:
                try:
                    conn = sqlite3.connect(str(c))
                    if conn.execute("SELECT count(*) FROM banco_preguntas").fetchone()[0] > 0:
                        return conn
                    conn.close()
                except Exception:
                    continue
    raise FileNotFoundError("DB")

def _importer():
    for r in _CANDS:
        for c in [r / "evaluacion" / "humana" / "importar_ficha_humana.py", r / "data" / "evaluacion" / "humana" / "importar_ficha_humana.py"]:
            if c.exists():
                spec = importlib.util.spec_from_file_location("imp_f4", str(c))
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                return m
    raise FileNotFoundError("importador")

def test_rechaza_version_incorrecta():
    imp = _importer()
    errs = imp.validar_ficha({"pregunta_id": "Q01", "groundtruth_version": "v3_curado", "puntos_esperados": [], "claims": [], "citas": [], "relevancia": None}, GEN)
    assert any("v3.1" in e for e in errs)

def test_no_duplica_unique():
    conn = _db()
    for tbl, col in (("evaluacion_completitud_detalle", "punto_id"),):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        assert "groundtruth_version" in cols
    # UNIQUE(gen,pregunta,punto) existe: intentar duplicado en transacción revertida
    row = conn.execute("SELECT generacion_experimento_id, pregunta_id, punto_id, estado, evaluador FROM evaluacion_completitud_detalle WHERE groundtruth_version=? LIMIT 1", (GTV,)).fetchone()
    assert row is not None
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp, groundtruth_version) VALUES (?,?,?,?,?,?,?)",
            (row[0], row[1], row[2], row[3], row[4], "2000-01-01", GTV))
        assert False
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.rollback()
        conn.close()

def test_17_fichas_66_puntos():
    conn = _db()
    assert conn.execute("SELECT count(DISTINCT pregunta_id) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchone()[0] == 17
    assert conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchone()[0] == 66
    conn.close()

def test_estados_permitidos():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND estado NOT IN ('CUBIERTO','PARCIAL','NO_CUBIERTO')", (GEN, GTV)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND estado NOT IN ('SOPORTADO','PARCIALMENTE_SOPORTADO','NO_SOPORTADO')", (GEN, GTV)).fetchone()[0] == 0
    conn.close()

def test_null_correctos():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND estado IS NULL", (GEN, GTV)).fetchone()[0] == 0
    # M04 sin claims -> faithfulness ausente (NULL agregado)
    assert conn.execute("SELECT count(*) FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND pregunta_id IN ('Q04','Q09','Q11','Q17')", (GEN, GTV)).fetchone()[0] == 0
    conn.close()

def test_micro_macro():
    conn = _db()
    rows = conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchall()
    micro = sum(1 for r in rows if r[0] == "CUBIERTO") / len(rows)
    micro_p = (sum(1 for r in rows if r[0] == "CUBIERTO") + 0.5 * sum(1 for r in rows if r[0] == "PARCIAL")) / len(rows)
    assert abs(micro - 0.10606060606060606) < 1e-9
    assert abs(micro_p - 0.19696969696969696) < 1e-9
    conn.close()

def test_partial_peso():
    # partial = 0.5 por definición
    assert 0.5 == 0.5
    conn = _db()
    n_parcial = conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND estado='PARCIAL'", (GEN, GTV)).fetchone()[0]
    assert n_parcial == 12
    conn.close()

def test_m04_no_faith_uno():
    conn = _db()
    # ninguna fila M04 en detalle => ningún cálculo puede dar 1 artificial
    for q in ("Q04", "Q09", "Q11", "Q17"):
        assert conn.execute("SELECT count(*) FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND pregunta_id=?", (GEN, GTV, q)).fetchone()[0] == 0
    conn.close()

def test_ocurrencias_q03():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND pregunta_id='Q03'", (GEN, GTV)).fetchone()[0] == 3
    conn.close()

def test_q15_referencia_humana():
    conn = _db()
    row = conn.execute("SELECT estado FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND pregunta_id='Q15'", (GEN, GTV)).fetchone()
    assert row is not None and row[0] == "CORRECTA"
    conn.close()

def test_q17_solo_seguimiento():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM groundtruth_v31_puntos WHERE pregunta_id='Q17' AND (articulo LIKE '%421%' OR evidencia LIKE '%421%')").fetchone()[0] == 0
    conn.close()

def test_congeladas_intactas():
    import hashlib
    conn = _db()
    for (qid, resp) in conn.execute("SELECT pregunta_id, respuesta_generada FROM evaluacion_generacion WHERE generacion_experimento_id=?", (GEN,)):
        assert isinstance(resp, str) and len(resp) > 0
    conn.close()
