# -*- coding: utf-8 -*-
"""Tests de evaluacion/humana/fichas_fidelidad.py (Revisión 3, evaluación humana ciega de fidelidad)."""
import importlib.util
import json
import random
from pathlib import Path

import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "humana" / "fichas_fidelidad.py",
              Path("/data/evaluacion/humana/fichas_fidelidad.py")]:
    if _cand.exists():
        _spec = importlib.util.spec_from_file_location("fichas_fidelidad", _cand)
        ff = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(ff)
        break
else:
    pytest.skip("fichas_fidelidad.py no encontrado", allow_module_level=True)


def _banco(tmp_path, n=10):
    preguntas = [{"id": f"Q{i:02d}", "pregunta": f"pregunta {i}", "categoria": "AB"[i % 2],
                  "respuesta_referencia": f"ref {i}", "puntos": [{"descripcion": f"punto {i}"}]} for i in range(1, n + 1)]
    p = tmp_path / "banco.json"
    p.write_text(json.dumps({"version": "test", "preguntas": preguntas}), encoding="utf-8")
    return p


def _corrida(tmp_path, nombre, n=10):
    res = [{"id": f"Q{i:02d}", "tipo_mensaje": "M02", "respuesta": f"respuesta de {nombre} a {i}",
            "documentos_llm": "['REGLAMENTO X.pdf', 'REGLAMENTO X.pdf']", "articulos_llm": "['Artículo 5°', '']"}
           for i in range(1, n + 1)]
    p = tmp_path / f"E2E_B_{nombre}_s42_1.json"
    p.write_text(json.dumps({"meta": {"llm_model": nombre}, "resultados": res}), encoding="utf-8")
    return p


def _chunks(tmp_path):
    p = tmp_path / "chunks.csv"
    p.write_text("nombre_documento,articulo,parte_num,texto\n"
                 "REGLAMENTO X,Artículo 5°,2,segunda parte\n"
                 "REGLAMENTO X,Artículo 5°,1,primera parte\n", encoding="utf-8")
    return p


def _preparar(tmp_path, n_preg=6):
    salida = tmp_path / "out"
    ff.main(["preparar", "--banco", str(_banco(tmp_path)), "--n-preguntas", str(n_preg), "--chunks",
             str(_chunks(tmp_path)), "--salida", str(salida),
             f"qwen={_corrida(tmp_path, 'qwen')}", f"qwen3={_corrida(tmp_path, 'qwen3')}"])
    return salida


def test_muestreo_estratificado_y_determinista():
    banco = {f"Q{i}": {"categoria": "A" if i < 8 else "B"} for i in range(10)}
    m1 = ff.muestrear(list(banco), banco, 5, 1)
    assert m1 == ff.muestrear(list(banco), banco, 5, 1)
    assert len(m1) == 5 and any(banco[q]["categoria"] == "B" for q in m1)


def test_fuentes_unen_partes_del_articulo_en_orden(tmp_path):
    textos = ff.cargar_textos(_chunks(tmp_path))
    fr = ff.fuentes_de({"documentos_llm": "['REGLAMENTO X.pdf', 'OTRO.pdf']", "articulos_llm": "['Art. 5', '']"}, textos)
    assert "primera parte\nsegunda parte" in fr[0]
    assert "no ubicado" in fr[1]


def test_preparar_es_ciego(tmp_path):
    salida = _preparar(tmp_path)
    filas = ff.xlsx_simple.leer(salida / "ficha_fidelidad_E1.xlsx", "Evaluacion")
    assert filas[0] == ff.COLUMNAS and len(filas) == 1 + 6 * 2
    texto = json.dumps(filas)
    assert "qwen3" not in texto.replace("respuesta de qwen3", "")  # el nombre del sistema solo aparece en la clave
    clave = json.loads((salida / "clave_NO_ENTREGAR.json").read_text(encoding="utf-8"))
    assert len(clave["items"]) == 12
    assert (salida / "ficha_fidelidad_E2.xlsx").exists()


def _llenar(salida, nombre, rng, sesgo_qwen3=0):
    clave = json.loads((salida / "clave_NO_ENTREGAR.json").read_text(encoding="utf-8"))
    filas = ff.xlsx_simple.leer(salida / "ficha_fidelidad_E1.xlsx", "Evaluacion")
    for f in filas[1:]:
        f += [""] * (len(ff.COLUMNAS) - len(f))
        alto = clave["items"][f[0]]["sistema"] == "qwen3" and sesgo_qwen3
        f[6] = "2" if alto else rng.choice("01")
        f[7] = "2" if alto else rng.choice("012")
        f[8] = "exacta" if alto else rng.choice(ff.ATRIBUCION)
        f[9] = "5" if alto else rng.choice("123")
    p = salida / nombre
    ff.xlsx_simple.escribir(p, [{"nombre": "Evaluacion", "filas": filas}])
    return p


def test_analizar_kappa_y_comparaciones(tmp_path):
    salida = _preparar(tmp_path)
    rng = random.Random(0)
    f1 = _llenar(salida, "E1.xlsx", rng, sesgo_qwen3=1)
    ff.main(["analizar", "--clave", str(salida / "clave_NO_ENTREGAR.json"), "--n-boot", "200", str(f1), str(f1)])
    acuerdo = (salida / "acuerdo_fidelidad.csv").read_text(encoding="utf-8")
    assert "1.0000" in acuerdo  # mismo evaluador dos veces → κ = 1
    resumen = (salida / "resumen_fidelidad.csv").read_text(encoding="utf-8")
    assert "qwen3" in resumen
    comps = (salida / "comparaciones_fidelidad.csv").read_text(encoding="utf-8")
    assert "qwen3 vs qwen" in comps


def test_analizar_rechaza_valores_invalidos(tmp_path):
    salida = _preparar(tmp_path, n_preg=2)
    filas = ff.xlsx_simple.leer(salida / "ficha_fidelidad_E1.xlsx", "Evaluacion")
    for f in filas[1:]:
        f += [""] * (len(ff.COLUMNAS) - len(f))
        f[6:10] = ["3", "2", "exacta", "5"]  # correccion 3 no existe
    p = salida / "malo.xlsx"
    ff.xlsx_simple.escribir(p, [{"nombre": "Evaluacion", "filas": filas}])
    with pytest.raises(SystemExit):
        ff.main(["analizar", "--clave", str(salida / "clave_NO_ENTREGAR.json"), str(p), str(p)])
