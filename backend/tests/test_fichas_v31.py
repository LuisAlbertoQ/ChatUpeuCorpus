# -*- coding: utf-8 -*-
"""Tests fichas humanas v3.1 — 17 fichas, 66 puntos, versionado, sin juicios."""
import json, pathlib, hashlib, sqlite3, importlib.util
_HERE = pathlib.Path(__file__).parent.parent.parent
_CANDIDATE_ROOTS = [_HERE, pathlib.Path("/app"), pathlib.Path("/")]
GEN = "GEN_20260924_232127_8e01ef"
GTV = "v3.1_curado"
EXPECTED = {"Q01": 4, "Q02": 4, "Q03": 6, "Q04": 3, "Q05": 3, "Q06": 3, "Q07": 5, "Q08": 5, "Q09": 3, "Q10": 3, "Q11": 2, "Q12": 3, "Q13": 4, "Q14": 6, "Q15": 6, "Q16": 3, "Q17": 3}

def _eval_dir():
    for r in _CANDIDATE_ROOTS:
        for c in [r / "evaluacion", r / "data" / "evaluacion"]:
            if (c / "banco" / "preguntas_comparacion.json").exists() or c.exists():
                # prefer dir containing humana/fichas_humanas_v31
                if (c / "humana" / "fichas_humanas_v31").exists():
                    return c
    for r in _CANDIDATE_ROOTS:
        for c in [r / "evaluacion", r / "data" / "evaluacion"]:
            if c.exists():
                return c
    raise FileNotFoundError("evaluacion dir")

def _db():
    for r in _CANDIDATE_ROOTS:
        for c in [r / "registro_interacciones.db", r / "data" / "registro_interacciones.db"]:
            if c.exists() and c.stat().st_size > 0:
                # verificar que tiene datos (evitar DB vacía autocreada)
                try:
                    conn = sqlite3.connect(str(c))
                    n = conn.execute("SELECT count(*) FROM banco_preguntas").fetchone()[0]
                    conn.close()
                    if n > 0:
                        return c
                except Exception:
                    continue
    raise FileNotFoundError("DB con datos")

def _fdir():
    return _eval_dir() / "humana" / "fichas_humanas_v31"

def _load(qid):
    return json.loads((_fdir() / f"ficha_{qid}_{GEN}_v31.json").read_text(encoding="utf-8"))

def _importer():
    spec = importlib.util.spec_from_file_location("importar_ficha_humana", str(_eval_dir() / "humana" / "importar_ficha_humana.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_17_fichas():
    assert len(list(_fdir().glob("ficha_Q*_v31.json"))) == 17

def test_66_puntos():
    total = sum(len(_load(q)["puntos_esperados"]) for q in EXPECTED)
    assert total == 66

def test_conteo_por_q():
    for qid, n in EXPECTED.items():
        assert len(_load(qid)["puntos_esperados"]) == n, qid

def test_groundtruth_version():
    for qid in EXPECTED:
        d = _load(qid)
        assert d["groundtruth_version"] == GTV
        assert d["generation_experiment_id"] == GEN

def test_ficha_v3_rechazada():
    imp = _importer()
    v3 = json.loads((_eval_dir() / "humana" / "fichas_humanas" / f"ficha_Q01_{GEN}.json").read_text(encoding="utf-8"))
    errs = imp.validar_ficha(v3, GEN)
    assert any("v3.1" in e for e in errs)

def test_punto_v3_inexistente_rechazado():
    imp = _importer()
    d = _load("Q01")
    d["puntos_esperados"][0]["punto_id"] = "Q01_P99"
    d["puntos_esperados"][0]["estado"] = "CUBIERTO"
    errs = imp.validar_ficha(d, GEN)
    assert any("Q01_P99" in e for e in errs)

def test_q17_sin_art421():
    d = _load("Q17")
    for p in d["puntos_esperados"]:
        assert "421" not in p["articulo"] and "421" not in p["evidencia"]
    assert d["puntos_esperados"][0]["documento"] == "Reglamento de seguimiento de egresados"

def test_respuestas_byte_identical():
    conn = sqlite3.connect(str(_db()))
    for qid in EXPECTED:
        v31 = _load(qid)["respuesta_congelada"]
        row = conn.execute("SELECT respuesta_generada FROM evaluacion_generacion WHERE generacion_experimento_id=? AND pregunta_id=?", (GEN, qid)).fetchone()
        assert hashlib.sha256(v31.encode()).hexdigest() == hashlib.sha256(row[0].encode()).hexdigest(), qid
    conn.close()

def test_claims_vacios_y_null():
    # FASE 4: las fichas ya fueron evaluadas; se verifica estructura válida de juicios
    for qid in EXPECTED:
        d = _load(qid)
        assert all(p["estado"] in ("CUBIERTO", "PARCIAL", "NO_CUBIERTO") for p in d["puntos_esperados"])
        assert all(c["estado"] in ("SOPORTADO", "PARCIALMENTE_SOPORTADO", "NO_SOPORTADO") for c in d["claims"])
        assert all(c["estado"] in ("CORRECTA", "PARCIAL", "INCORRECTA", "NO_ASOCIABLE") for c in d["citas"])
        assert d["relevancia"] in (1, 2, 3, 4, 5)

def test_tablas_versionadas():
    conn = sqlite3.connect(str(_db()))
    for tbl in ("evaluacion_completitud_detalle", "evaluacion_faithfulness_detalle", "evaluacion_citation_correctness_detalle", "evaluacion_generacion"):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        assert "groundtruth_version" in cols, tbl
    conn.close()

def test_calculo_filtra_v31():
    src = (_eval_dir() / "humana" / "calcular_metricas_humanas.py").read_text(encoding="utf-8")
    assert src.count("groundtruth_version") >= 4 and GTV in src
