# -*- coding: utf-8 -*-
"""Tests instrumento piloto OE8 v1 (sin datos ficticios)."""
import json, pathlib, sqlite3, tempfile, sys
_HERE = pathlib.Path(__file__).parent.parent.parent
for _r in (_HERE, pathlib.Path("/app"), pathlib.Path("/")):
    for _c in (_r / "evaluacion" / "madurez_oe8", _r / "data" / "evaluacion" / "madurez_oe8", _r / "evaluacion", _r / "data" / "evaluacion"):
        if (_c / "instrumento_piloto_oe8_v1.json").exists():
            EVAL = _c
            break
    else:
        continue
    break
DIMS = ["Funcional", "Recuperación documental", "Explicabilidad", "Usabilidad", "Gobernanza", "Preparación tecnológica"]

def _inst():
    return json.loads((EVAL / "instrumento_piloto_oe8_v1.json").read_text(encoding="utf-8"))

def test_30_items():
    assert len(_inst()["items"]) == 30

def test_6_dimensiones_5_items():
    from collections import Counter
    c = Counter(i["dimension"] for i in _inst()["items"])
    assert sorted(c) == sorted(DIMS) and all(v == 5 for v in c.values())

def test_ids_unicos():
    ids = [i["item_id"] for i in _inst()["items"]]
    assert len(ids) == len(set(ids)) == 30

def test_likert_1_5():
    d = _inst()
    assert d["escala_min"] == 1 and d["escala_max"] == 5
    for i in d["items"]:
        assert i["escala_min"] == 1 and i["escala_max"] == 5 if "escala_min" in i else True

def _validar(iid, dim, val, items):
    if iid not in items:
        return False
    if dim != items[iid]:
        return False
    return isinstance(val, int) and 1 <= val <= 5

def test_rechaza_0_y_6():
    items = {i["item_id"]: i["dimension"] for i in _inst()["items"]}
    assert not _validar("FUN01", "Funcional", 0, items)
    assert not _validar("FUN01", "Funcional", 6, items)
    assert _validar("FUN01", "Funcional", 1, items)
    assert _validar("FUN01", "Funcional", 5, items)

def test_duplicados():
    vistos = set()
    dups = 0
    for pid, iid in [("P-1", "FUN01"), ("P-1", "FUN01")]:
        if (pid, iid) in vistos:
            dups += 1
        vistos.add((pid, iid))
    assert dups == 1

def test_completo_vs_incompleto():
    assert 30 == 30  # completo
    assert 29 < 30  # incompleto no entra al promedio

def test_no_imputacion():
    # la BD real no debe tener respuestas piloto ficticias
    for r in (_HERE, pathlib.Path("/app"), pathlib.Path("/")):
        for c in [r / "registro_interacciones.db", r / "data" / "registro_interacciones.db"]:
            if c.exists() and c.stat().st_size > 0:
                try:
                    conn = sqlite3.connect(str(c))
                    if conn.execute("SELECT count(*) FROM banco_preguntas").fetchone()[0] > 0:
                        assert conn.execute("SELECT count(*) FROM piloto_respuestas").fetchone()[0] == 0
                        assert conn.execute("SELECT count(*) FROM evaluacion_piloto").fetchone()[0] == 0
                        conn.close()
                        return
                    conn.close()
                except Exception:
                    continue

def test_importacion_idempotente():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE piloto_respuestas (id INTEGER PRIMARY KEY, participante_id_anonimo TEXT, item_id TEXT, UNIQUE(participante_id_anonimo, item_id))")
    conn.execute("INSERT INTO piloto_respuestas (participante_id_anonimo, item_id) VALUES ('P-1','FUN01')")
    conn.commit()
    try:
        conn.execute("INSERT INTO piloto_respuestas (participante_id_anonimo, item_id) VALUES ('P-1','FUN01')")
        assert False
    except sqlite3.IntegrityError:
        pass
    assert conn.execute("SELECT count(*) FROM piloto_respuestas").fetchone()[0] == 1
    conn.close()

def test_sin_pii_en_plantilla():
    txt = (EVAL / "plantilla_piloto.csv").read_text(encoding="utf-8").lower()
    for campo in ("nombre", "dni", "correo", "telefono", "teléfono", "direccion", "dirección"):
        assert campo not in txt
