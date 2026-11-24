# -*- coding: utf-8 -*-
"""Tests de evaluacion/tablas/generar_tablas.py (Revisión 3, tablas 1–6 y figuras)."""
import importlib.util
import json
from pathlib import Path

import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "tablas" / "generar_tablas.py",
              Path("/data/evaluacion/tablas/generar_tablas.py")]:
    if _cand.exists():
        _spec = importlib.util.spec_from_file_location("generar_tablas", _cand)
        gt = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(gt)
        break
else:
    pytest.skip("generar_tablas.py no encontrado", allow_module_level=True)

BANCO = {"version": "test", "preguntas": [
    {"id": f"Q{i}", "pregunta": f"p{i}", "categoria": "A", "tipo_pregunta": "DIRECTA",
     "documentos_esperados": ["REGLAMENTO X"], "articulos_esperados": [{"articulo": "Artículo 5°"}]}
    for i in range(1, 6)], "negativas": [{"id": "N1", "bloque": "ood", "vista_en_desarrollo": False}]}


def _corrida(tmp_path):
    res = [
        {"id": "Q1", "tipo_mensaje": "M02", "hit_documento_top4": "True", "respuesta": "Sí (REGLAMENTO X, Artículo 5°)."},
        {"id": "Q2", "tipo_mensaje": "M02", "hit_documento_top4": "False", "respuesta": "otra cosa"},
        {"id": "Q3", "tipo_mensaje": "M04", "hit_documento_top4": "True", "respuesta": "No encontré información"},
        {"id": "Q4", "tipo_mensaje": "M06", "hit_documento_top4": "True", "respuesta": ""},
        {"id": "Q5", "tipo_mensaje": "M02", "hit_documento_top4": "True", "respuesta": "Según el Reglamento X, sí."},
    ]
    p = tmp_path / "E2E_final_s42_1.json"
    p.write_text(json.dumps({"meta": {}, "resultados": res}), encoding="utf-8")
    return p


def test_errores_clasifica_cada_respuesta(tmp_path):
    filas, detalle = gt.errores_corrida(str(_corrida(tmp_path)), BANCO, tmp_path / "sin_fidelidad")
    clases = {d["id"]: d["clase"] for d in detalle}
    assert clases == {"Q1": "correcta y sustentada", "Q2": "recuperación fallida", "Q3": "falsa abstención",
                      "Q4": "error técnico", "Q5": "atribución parcial"}
    infiel = next(f for f in filas if f["tipo"] == "generación infiel")
    assert infiel["n"] == "pendiente"


def test_errores_usa_la_fidelidad_humana(tmp_path):
    fid = tmp_path / "fid"
    fid.mkdir()
    gt.escribir_csv(fid / "detalle_fidelidad.csv", [
        {"item": "R001", "sistema": "qwen", "pregunta_id": "Q1", "fidelidad_E1": "0", "fidelidad_E2": "2"},
        {"item": "R002", "sistema": "otro", "pregunta_id": "Q5", "fidelidad_E1": "0", "fidelidad_E2": "0"}])
    _, detalle = gt.errores_corrida(str(_corrida(tmp_path)), BANCO, fid, "qwen")
    clases = {d["id"]: d["clase"] for d in detalle}
    assert clases["Q1"] == "generación infiel" and clases["Q5"] == "atribución parcial"


def test_composicion_y_md():
    comp = gt.composicion(BANCO)
    assert comp[0]["n"] == 5 and comp[1]["grupo"] == "Fuera de dominio"
    assert "no vistas en desarrollo: 1" in comp[1]["detalle"]
    md = gt.md_tabla([{"a": 1, "b": 2}])
    assert md.splitlines()[0] == "| a | b |"
    assert gt.md_tabla([]) == "_(sin datos todavía)_"


def test_main_genera_salida_con_resultados_del_repo(tmp_path):
    if not (gt.EVAL / "retrieval" / "exp_a").exists():
        pytest.skip("sin resultados del Exp. A")
    gt.main(["--salida", str(tmp_path), "--n-boot", "200"])
    md = (tmp_path / "TABLAS.md").read_text(encoding="utf-8")
    assert "PRELIMINAR" in md and "Tabla 6" in md
    for f in ("tabla2_recuperacion.csv", "tabla6_errores.csv", "figura3_ejemplos.md"):
        assert (tmp_path / f).exists()
