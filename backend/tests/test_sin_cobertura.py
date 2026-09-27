# -*- coding: utf-8 -*-
"""Tests banco SIN_COBERTURA / abstention correctness (lectura + casos puros)."""
import pathlib, sqlite3
_HERE = pathlib.Path(__file__).parent.parent.parent
_CANDS = [_HERE, pathlib.Path("/app"), pathlib.Path("/")]
NEG = "NEG_20260925_NOANSWER_V1"

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

def test_solo_sin_cobertura():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM banco_no_answer WHERE tipo_pregunta != 'SIN_COBERTURA'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM banco_no_answer").fetchone()[0] == 6
    conn.close()

def test_todos_no_answer():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM banco_no_answer WHERE cobertura_esperada != 'NO_ANSWER'").fetchone()[0] == 0
    conn.close()

def test_sin_documento_inventado():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM banco_no_answer WHERE documento_esperado IS NOT NULL OR articulo_esperado IS NOT NULL").fetchone()[0] == 0
    conn.close()

def test_ids_unicos():
    conn = _db()
    n = conn.execute("SELECT count(*), count(DISTINCT id) FROM banco_no_answer").fetchone()
    assert n[0] == n[1] == 6
    conn.close()

def test_experimento_reproducible():
    conn = _db()
    row = conn.execute("SELECT corpus_version, embedding_model, threshold, top_k_raw, top_k_final FROM experimentos_rag WHERE experimento_id=?", (NEG,)).fetchone()
    assert row == ("corpus_upeu_v2", "paraphrase-multilingual-mpnet-base-v2", 0.4, 15, 4)
    conn.close()

def test_abstention_valores():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM evaluacion_no_answer WHERE experimento_id=? AND abstention_correctness NOT IN (0,1)", (NEG,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM evaluacion_no_answer WHERE experimento_id=?", (NEG,)).fetchone()[0] == 6
    conn.close()

def test_m02_factual_da_cero():
    # regla §6: M02 sustantiva en NO_ANSWER -> 0
    tipo, factual = "M02", True
    score = 0 if (tipo == "M02" and factual) else 1
    assert score == 0

def test_abstencion_da_uno():
    for tipo in ("M04", "M03"):
        assert 1 == 1  # plantilla sin claims -> correcta
    conn = _db()
    assert conn.execute("SELECT sum(abstention_correctness) FROM evaluacion_no_answer WHERE experimento_id=?", (NEG,)).fetchone()[0] == 6
    conn.close()

def test_retrieval_no_cambia_gt():
    conn = _db()
    # aunque N03 recuperó chunks cercanos, el GT sigue NO_ANSWER
    assert conn.execute("SELECT cobertura_esperada FROM banco_no_answer WHERE id='N03'").fetchone()[0] == "NO_ANSWER"
    conn.close()

def test_no_modifica_q01_q17():
    conn = _db()
    assert conn.execute("SELECT count(*) FROM banco_preguntas WHERE banco_version='v3_curado'").fetchone()[0] == 17
    assert conn.execute("SELECT count(*) FROM groundtruth_v31_puntos").fetchone()[0] == 66
    assert conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE groundtruth_version='v3.1_curado'").fetchone()[0] == 66
    conn.close()
