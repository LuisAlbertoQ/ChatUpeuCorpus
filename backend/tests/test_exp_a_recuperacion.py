# -*- coding: utf-8 -*-
"""Tests de evaluacion/retrieval/exp_a_recuperacion.py (Revisión 3, experimento A) con datos sintéticos."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "retrieval" / "exp_a_recuperacion.py",
              Path("/data/evaluacion/retrieval/exp_a_recuperacion.py")]:
    if _cand.exists():
        _spec = importlib.util.spec_from_file_location("exp_a", _cand)
        exp_a = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(exp_a)
        break
else:
    pytest.skip("exp_a_recuperacion.py no encontrado", allow_module_level=True)


def _ch(doc, art=""):
    return {"_doc": exp_a.norm(doc), "_art": exp_a.num_art(art), "nombre_documento": doc, "articulo": art}


def _q(docs, arts=(), subcadena=False):
    return {"id": "Q", "categoria": "B", "dev": False, "subcadena": subcadena,
            "docs": {exp_a.norm(d) for d in docs}, "arts": {(exp_a.norm(d), exp_a.num_art(a)) for d, a in arts}}


class TestNormalizacion:
    def test_guion_bajo_y_pdf(self):
        assert exp_a.norm("REGLAMENTO DE ESTUDIOS V5_2025.pdf") == exp_a.norm("REGLAMENTO DE ESTUDIOS V5 2025")

    def test_tildes_y_signos(self):
        assert exp_a.norm("Reglamento Pago Servicios Educativos o Académicos") == \
            "reglamento pago servicios educativos o academicos"

    def test_num_articulo(self):
        assert exp_a.num_art("Artículo 283º") == "283" and exp_a.num_art("") == ""


class TestMetricas:
    chunks = [_ch("Otro"), _ch("Doc A", "Art. 5"), _ch("Doc A", "Art. 7"), _ch("Doc A", "Art. 7"), _ch("Doc B", "Art. 1")]

    def test_nivel_articulo(self):
        q = _q(["Doc A"], [("Doc A", "Artículo 7°")])
        f = exp_a.metricas_pregunta(np.arange(5), self.chunks, q)
        assert f["nivel"] == "articulo" and f["rank"] == 3 and f["rank_documento"] == 2
        assert f["recall@1"] == 0 and f["recall@3"] == 1 and f["mrr@10"] == pytest.approx(1 / 3)
        assert f["rdoc@1"] == 0 and f["rdoc@5"] == 1
        # una sola relevante en la posición 3; la parte repetida (pos. 4) no suma
        assert f["ndcg@5"] == pytest.approx(1 / np.log2(4))

    def test_nivel_documento(self):
        f = exp_a.metricas_pregunta(np.arange(5), self.chunks, _q(["Doc B"]))
        assert f["nivel"] == "documento" and f["rank"] == 5 and f["recall@5"] == 1 and f["recall@3"] == 0

    def test_dos_articulos_ndcg_perfecto(self):
        q = _q(["Doc A"], [("Doc A", "5"), ("Doc A", "7")])
        f = exp_a.metricas_pregunta(np.array([1, 2, 0, 3, 4]), self.chunks, q)
        assert f["ndcg@5"] == pytest.approx(1.0)

    def test_no_recuperado(self):
        f = exp_a.metricas_pregunta(np.arange(5), self.chunks, _q(["Doc Z"]))
        assert f["rank"] == "" and f["mrr@10"] == 0 and f["ndcg@5"] == 0

    def test_subcadena_banco_oe1(self):
        q = _q(["Doc"], [("Doc", "1")], subcadena=True)
        f = exp_a.metricas_pregunta(np.arange(5), self.chunks, q)
        assert f["rank"] == 5  # "doc b" contiene "doc" y tiene el artículo 1


class TestBM25:
    def test_prefiere_el_texto_con_los_terminos(self):
        bm = exp_a.BM25(["requisitos para la beca de estudios", "horario de la biblioteca", "pago de pensiones"])
        s = bm.puntajes("¿Cuáles son los requisitos de la beca?")
        assert int(np.argmax(s)) == 0 and s[1] == 0

    def test_stopwords_no_puntuan(self):
        bm = exp_a.BM25(["de la el", "beca"])
        assert bm.puntajes("de la")[0] == 0


class TestBanco:
    def test_json_solo_respondibles(self, tmp_path):
        p = tmp_path / "b.json"
        p.write_text(json.dumps({"preguntas": [
            {"id": "Q1", "pregunta": "x", "categoria": "A", "cobertura_esperada": "ANSWERABLE",
             "documentos_esperados": ["Doc A"], "articulos_esperados": [{"documento": "Doc A", "articulo": "Artículo 3°"}]},
            {"id": "N1", "pregunta": "y", "cobertura_esperada": "NO_ANSWER", "documentos_esperados": []},
        ]}), encoding="utf-8")
        b = exp_a.cargar_banco(p)
        assert [q["id"] for q in b] == ["Q1"] and b[0]["arts"] == {("doc a", "3")}

    def test_csv_oe1(self, tmp_path):
        p = tmp_path / "b.csv"
        p.write_text("id,pregunta,tipo,categoria_esperada,documento_esperado,articulo_esperado\n"
                     "Q1,x,positiva,B,REGLAMENTO X,12\nN1,y,negativa,,,\n", encoding="utf-8")
        b = exp_a.cargar_banco(p)
        assert len(b) == 1 and b[0]["subcadena"] and b[0]["arts"] == {("reglamento x", "12")}
