# -*- coding: utf-8 -*-
"""Tests reevaluación retrieval v3.1 — multi-relevancia sobre ranking congelado."""
import math

def _metrics(ranking, relevant, k):
    topk = ranking[:k]
    hit = 1 if any(r in topk for r in relevant) else 0
    rec = len(set(topk) & relevant) / len(relevant)
    rr = 0.0
    for i, r in enumerate(topk, 1):
        if r in relevant:
            rr = 1.0 / i
            break
    dcg = sum(1.0 / math.log2(i + 1) for i, r in enumerate(topk, 1) if r in relevant)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return hit, rec, rr, dcg / idcg if idcg else 0.0

def test_hit_difiere_recall_multi():
    h, r, _, _ = _metrics(["a", "x", "y"], {"a", "b", "c"}, 5)
    assert h == 1 and abs(r - 1 / 3) < 1e-9

def test_dos_de_tres():
    _, r, _, _ = _metrics(["a", "b", "x"], {"a", "b", "c"}, 5)
    assert abs(r - 2 / 3) < 1e-9

def test_duplicado_articulo_no_suma():
    # ranking deduplicado: mismo art dos veces cuenta una
    rank = ["d|41", "d|42"]
    _, r, _, _ = _metrics(rank, {"d|41", "d|42"}, 5)
    assert r == 1.0
    # sin dedup, duplicado inflaría conteo si se contara por ocurrencias
    assert len(set(["d|41", "d|41", "d|42"]) & {"d|41", "d|42"}) == 2

def test_duplicado_doc_no_suma():
    assert len(set(["d", "d", "x"]) & {"d"}) == 1

def test_ndcg_multi():
    _, _, _, n = _metrics(["a", "b", "x"], {"a", "b", "c"}, 3)
    assert 0 < n < 1

def test_q09_q11_excluidos_article():
    import pathlib, sqlite3
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT count(*) FROM groundtruth_v31_puntos WHERE pregunta_id IN ('Q09','Q11') AND articulo != ''").fetchone()[0]
    assert n == 0
    conn.close()

def test_final_multi():
    h, r, _, _ = _metrics(["a"], {"a", "b", "c"}, 4)
    assert h == 1 and abs(r - 1 / 3) < 1e-9

def test_ranking_congelado_no_cambia():
    import pathlib, sqlite3
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT count(*) FROM evaluacion_retrieval WHERE experimento_id='EXP_20260924_231553_2cd31b'").fetchone()[0] == 255
    conn.close()

def test_v3_no_sobrescrita():
    import pathlib, sqlite3
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT count(*) FROM metricas_retrieval_experimento WHERE experimento_id='EXP_20260924_231553_2cd31b'").fetchone()[0] == 28
    assert conn.execute("SELECT count(*) FROM metricas_retrieval_experimento WHERE experimento_id='EXP_20260924_231553_2cd31b_REEVAL_V31'").fetchone()[0] >= 28
    conn.close()

def test_version_persistida():
    import pathlib, sqlite3
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    row = conn.execute("SELECT estado, descripcion FROM experimentos_rag WHERE experimento_id='EXP_20260924_231553_2cd31b_REEVAL_V31'").fetchone()
    assert row is not None and "v3.1" in row[1]
    conn.close()


def _per_q_article():
    import pathlib, sqlite3, re, unicodedata, math
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    def nd(s):
        t = unicodedata.normalize("NFKD", (s or "")).lower()
        t = "".join(c for c in t if not unicodedata.combining(c))
        if t.endswith(".pdf"):
            t = t[:-4]
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()
    def na(s):
        if not s:
            return ""
        t0 = s.replace("º", "").replace("°", "").replace("ª", "")
        t = unicodedata.normalize("NFKD", t0).lower()
        t = "".join(c for c in t if not unicodedata.combining(c))
        m = re.search(r"(\d+(?:[.-][\w]+)?)", t)
        return m.group(1).lower() if m else t.strip()
    out = {}
    for (qid,) in conn.execute("SELECT pregunta_id FROM groundtruth_v31_preguntas ORDER BY pregunta_id"):
        pts = conn.execute("SELECT documento, articulo FROM groundtruth_v31_puntos WHERE pregunta_id=?", (qid,)).fetchall()
        rel = {f"{nd(d)}|{na(a)}" for d, a in pts if na(a)}
        rows = conn.execute("SELECT documento_recuperado, articulo_recuperado FROM evaluacion_retrieval WHERE pregunta_id=? AND experimento_id='EXP_20260924_231553_2cd31b' ORDER BY rank_reranked", (qid,)).fetchall()
        rk, seen = [], set()
        for d, a in rows:
            ka = f"{nd(d)}|{na(a)}" if na(a) else None
            if ka and ka not in seen:
                seen.add(ka)
                rk.append(ka)
        out[qid] = (rk, rel)
    conn.close()
    return out


def _m(ranking, rel, k):
    import math
    topk = ranking[:k]
    hit = 1 if any(r in topk for r in rel) else 0
    rec = len(set(topk) & rel) / len(rel)
    rr = 0.0
    for i, r in enumerate(topk, 1):
        if r in rel:
            rr = 1.0 / i
            break
    return hit, rec, rr


def test_mrr_implica_hit():
    for qid, (rk, rel) in _per_q_article().items():
        if not rel:
            continue
        for k in (5, 10, 15):
            h, _, m = _m(rk, rel, k)
            if m > 0:
                assert h == 1, qid


def test_hit_cero_implica_recall_cero():
    for qid, (rk, rel) in _per_q_article().items():
        if not rel:
            continue
        for k in (5, 10, 15):
            h, r, _ = _m(rk, rel, k)
            if h == 0:
                assert r == 0, qid


def test_hit_uno_implica_recall_positivo():
    for qid, (rk, rel) in _per_q_article().items():
        if not rel:
            continue
        for k in (5, 10, 15):
            h, r, _ = _m(rk, rel, k)
            if h == 1:
                assert r > 0, qid


def test_monotonicidad():
    for qid, (rk, rel) in _per_q_article().items():
        if not rel:
            continue
        hs = [_m(rk, rel, k)[0] for k in (5, 10, 15)]
        rs = [_m(rk, rel, k)[1] for k in (5, 10, 15)]
        assert hs[0] <= hs[1] <= hs[2], qid
        assert rs[0] <= rs[1] <= rs[2], qid


def test_agregados_igual_promedio():
    import pathlib, sqlite3
    PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
    for cand in [PROJECT_ROOT / "registro_interacciones.db", pathlib.Path("/data/registro_interacciones.db")]:
        if cand.exists():
            db = cand
            break
    conn = sqlite3.connect(str(db))
    per_q = _per_q_article()
    for met, idx in (("hit_rate", 0), ("recall", 1), ("mrr", 2)):
        for k in (5, 10, 15):
            vals = [_m(rk, rel, k)[idx] for rk, rel in per_q.values() if rel]
            mean = sum(vals) / len(vals)
            stored = conn.execute("SELECT valor FROM metricas_retrieval_experimento WHERE experimento_id='EXP_20260924_231553_2cd31b_REEVAL_V31' AND unidad='articulo' AND metrica=? AND k=?", (met, k)).fetchone()[0]
            assert abs(mean - stored) < 1e-9, (met, k)
    conn.close()
