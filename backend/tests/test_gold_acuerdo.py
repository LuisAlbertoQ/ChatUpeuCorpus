# -*- coding: utf-8 -*-
"""Tests de evaluacion/banco/gold/ (fichas del gold set, κ y consolidación) con datos sintéticos."""
import importlib
import sys
from pathlib import Path

import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "banco" / "gold",
              Path("/data/evaluacion/banco/gold")]:
    if (_cand / "acuerdo_gold.py").exists():
        sys.path.insert(0, str(_cand))
        break
else:
    pytest.skip("evaluacion/banco/gold no encontrado", allow_module_level=True)

xlsx = importlib.import_module("xlsx_simple")
ag = importlib.import_module("acuerdo_gold")


def _r(tipo, doc="", arts="", cat="B", resp="", puntos=""):
    return {"pregunta": "p", "tipo": tipo, "documento": doc, "articulos": arts, "documento_2": "", "articulos_2": "",
            "categoria": cat, "respuesta_referencia": resp, "puntos_clave": puntos, "confianza": "", "notas": ""}


class TestXlsx:
    def test_ida_y_vuelta_con_tildes_y_vacios(self, tmp_path):
        p = tmp_path / "t.xlsx"
        filas = [["id", "texto", "n"], ["Q1", "¿Qué es <esto> & \"aquello\"?", 3], ["Q2", "", ""], ["Q3", "fin", 1.5]]
        xlsx.escribir(p, [{"nombre": "Hoja", "filas": filas, "validaciones": [(1, 2, 4, '"a,b"')]}])
        leido = xlsx.leer(p, "Hoja")
        assert leido[0] == ["id", "texto", "n"]
        assert leido[1] == ["Q1", "¿Qué es <esto> & \"aquello\"?", "3"]
        assert leido[2] == ["Q2", "", ""] and leido[3] == ["Q3", "fin", "1.5"]

    def test_hoja_inexistente(self, tmp_path):
        p = tmp_path / "t.xlsx"
        xlsx.escribir(p, [{"nombre": "A", "filas": [["x"]]}])
        with pytest.raises(KeyError):
            xlsx.leer(p, "B")

    def test_letras_de_columna(self):
        assert [xlsx.col_letra(i) for i in (0, 25, 26, 27)] == ["A", "Z", "AA", "AB"]
        assert xlsx.col_indice("AB") == 27

    def test_lee_ficha_xlsx(self, tmp_path):
        p = tmp_path / "f.xlsx"
        enc = ["pregunta_id", "pregunta", "tipo", "documento", "articulos", "documento_2", "articulos_2",
               "categoria", "respuesta_referencia", "puntos_clave", "confianza", "notas"]
        xlsx.escribir(p, [{"nombre": "Anotacion", "filas": [enc, ["G1", "x", "directa", "Doc A.pdf", "Art 3", "",
                                                                  "", "b", "r", "p1; p2", "", ""],
                                                             ["G2", "y", "SIN_COBERTURA", "(ninguno)"]]}])
        f = ag.leer_ficha(p)
        assert f["G1"]["tipo"] == "DIRECTA" and f["G1"]["documento"] == "Doc A" and f["G1"]["categoria"] == "B"
        assert f["G2"]["documento"] == ""


class TestAcuerdo:
    def test_articulos_por_numero(self):
        assert ag.arts_set("Artículo 12°; Art. 18") == ag.arts_set("18, 12") == {"12", "18"}

    def test_validacion_detecta_errores(self):
        ficha = {"G1": _r("DIRECTA", "Doc X"), "G2": _r("REQUISITOS", "", cat=""), "G3": _r("??")}
        err = ag.validar_ficha("A", ficha, {"Doc A"}, ["G1", "G2", "G3", "G4"])
        texto = " ".join(err)
        assert "faltan 1" in texto and "no está en el corpus" in texto and "sin documento" in texto
        assert "tipo vacío o inválido" in texto

    def test_comparar_y_kappa(self):
        a = {"G1": _r("DIRECTA", "Doc A", "3"), "G2": _r("SIN_COBERTURA"), "G3": _r("REQUISITOS", "Doc B", "5; 6")}
        b = {"G1": _r("DIRECTA", "Doc A", "Artículo 3°"), "G2": _r("SIN_COBERTURA"), "G3": _r("PROCEDIMIENTO", "Doc B", "5")}
        filas = ag.comparar(a, b, ["G1", "G2", "G3"])
        por = {f["pregunta_id"]: f for f in filas}
        assert por["G1"]["conflicto"] == 0 and por["G2"]["conflicto"] == 0
        assert por["G3"]["conflicto"] == 1 and por["G3"]["articulos_jaccard"] == 0.5
        res = {r["medida"]: r for r in ag.resumen_kappa(filas)}
        assert res["kappa_documento"]["valor"] == 1.0 and res["kappa_bloque"]["valor"] == 1.0
        assert res["kappa_tipo"]["valor"] < 1.0 and res["preguntas_en_conflicto"]["valor"] == 1


class TestDecision:
    def test_acuerdo_une_puntos_sin_duplicar(self):
        a = {"G1": _r("DIRECTA", "Doc A", "3", resp="RA", puntos="Promedio 14; sin deudas")}
        b = {"G1": _r("DIRECTA", "Doc A", "3", resp="RB", puntos="sin deudas; matrícula vigente")}
        d = ag.decision_final("G1", a, b, {})
        assert d["resuelto_por"] == "acuerdo" and d["respuesta_referencia"] == "RA"
        assert d["puntos"] == ["Promedio 14", "sin deudas", "matrícula vigente"]

    def test_conflicto_sin_juez_queda_pendiente(self):
        a, b = {"G1": _r("DIRECTA", "Doc A")}, {"G1": _r("DIRECTA", "Doc B")}
        assert ag.decision_final("G1", a, b, {}) is None

    def test_juez_elige_y_hereda_respuesta_del_anotador_coincidente(self):
        a = {"G1": _r("DIRECTA", "Doc A", "3", resp="RA", puntos="pa")}
        b = {"G1": _r("DIRECTA", "Doc B", "7", resp="RB", puntos="pb")}
        juez = {"G1": {"juez_tipo": "directa", "juez_documento": "Doc B", "juez_articulos": "7"}}
        d = ag.decision_final("G1", a, b, juez)
        assert d["resuelto_por"] == "juez" and d["documento"] == "Doc B" and d["respuesta_referencia"] == "RB"
        assert d["puntos"] == ["pb"]
