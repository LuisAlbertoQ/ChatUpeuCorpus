# -*- coding: utf-8 -*-
"""Tests de evaluacion/estadistica/estadistica.py (Revisión 3 §9) con valores de referencia conocidos."""
import importlib.util
from pathlib import Path

import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "estadistica" / "estadistica.py",
              Path("/data/evaluacion/estadistica/estadistica.py")]:
    if _cand.exists():
        _spec = importlib.util.spec_from_file_location("estadistica", _cand)
        est = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(est)
        break
else:
    pytest.skip("estadistica.py no encontrado", allow_module_level=True)


class TestWilson:
    def test_valor_de_referencia(self):
        # 38/40: Wilson 95 % = [0.8350, 0.9862] (calculado a mano / statsmodels)
        p, lo, hi = est.wilson_ic(38, 40)
        assert p == pytest.approx(0.95)
        assert lo == pytest.approx(0.8350, abs=1e-3)
        assert hi == pytest.approx(0.9862, abs=1e-3)

    def test_todo_correcto_no_da_intervalo_degenerado(self):
        p, lo, hi = est.wilson_ic(6, 6)
        assert p == 1.0 and hi == 1.0 and lo < 0.7  # 6/6 no basta para confirmar ≥ 0.90

    def test_n_cero(self):
        with pytest.raises(ValueError):
            est.wilson_ic(0, 0)


class TestBootstrap:
    def test_reproducible_y_contiene_media(self):
        v = [0, 1, 1, 0, 1, 1, 1, 0, 1, 1]
        r1 = est.bootstrap_ic(v, n_boot=2000)
        r2 = est.bootstrap_ic(v, n_boot=2000)
        assert r1 == r2
        m, lo, hi = r1
        assert m == pytest.approx(0.7) and lo <= m <= hi and 0 <= lo and hi <= 1

    def test_constante_da_intervalo_cero(self):
        assert est.bootstrap_ic([0.5] * 8, n_boot=500) == (0.5, 0.5, 0.5)

    def test_diferencia_pareada(self):
        a = [0.1, 0.2, 0.3, 0.4]
        b = [x + 0.1 for x in a]
        m, lo, hi = est.bootstrap_diferencia(a, b, n_boot=500)
        assert m == pytest.approx(0.1) and lo == pytest.approx(0.1) and hi == pytest.approx(0.1)

    def test_no_pareadas(self):
        with pytest.raises(ValueError):
            est.bootstrap_diferencia([1, 2], [1])


class TestWilcoxon:
    def test_exacto_referencia(self):
        # 10 diferencias sin empates, todas positivas menos una de rango 1: W- = 1
        a = [0] * 10
        b = [-1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        w = est.wilcoxon_pareado(a, b)
        assert w["metodo"] == "exacto"
        assert w["w_menos"] == 1 and w["w_mas"] == 54
        # P(W <= 1) = 2/1024 por cola -> p = 4/1024
        assert w["p"] == pytest.approx(4 / 1024)
        assert w["r_rango_biserial"] == pytest.approx(53 / 55)

    def test_coincide_con_scipy_si_esta(self):
        a = [0.2, 0.4, 0.4, 0.5, 0.1, 0.0, 0.3, 0.6, 0.6, 0.2, 0.3, 0.5, 0.4, 0.2, 0.1, 0.7, 0.3, 0.2, 0.5, 0.4,
             0.6, 0.3, 0.1, 0.2, 0.4]
        b = [0.5, 0.6, 0.4, 0.8, 0.3, 0.2, 0.3, 0.9, 0.7, 0.5, 0.2, 0.8, 0.6, 0.4, 0.4, 0.7, 0.6, 0.5, 0.6, 0.7,
             0.6, 0.5, 0.3, 0.1, 0.8]
        w = est.wilcoxon_pareado(a, b)
        assert w["metodo"] == "normal"  # hay empates y ceros
        if "p_scipy" in w:
            assert w["p"] == pytest.approx(w["p_scipy"], rel=0.05)
        assert w["p"] < 0.001 and w["r_rango_biserial"] > 0.8

    def test_sin_diferencias(self):
        w = est.wilcoxon_pareado([1, 2, 3], [1, 2, 3])
        assert w["p"] == 1.0 and w["n_no_cero"] == 0


class TestHolm:
    def test_referencia(self):
        aj = est.holm({"a": 0.01, "b": 0.04, "c": 0.03})
        assert aj == {"a": pytest.approx(0.03), "c": pytest.approx(0.06), "b": pytest.approx(0.06)}

    def test_tope_uno(self):
        assert est.holm({"a": 0.6, "b": 0.7})["b"] == 1.0


class TestComparar:
    def test_base_y_holm(self):
        ids = [f"Q{i}" for i in range(15)]
        base = {q: 0.0 for q in ids}
        mejor = {q: (1.0 if i % 5 else 0.0) for i, q in enumerate(ids)}
        igual = dict(base)
        filas = est.comparar_sistemas({"S1": base, "S4": mejor, "S0": igual}, base="S1", n_boot=500)
        por = {f["comparacion"]: f for f in filas}
        assert por["S4 vs S1"]["significativo"] and por["S4 vs S1"]["magnitud"] == "grande"
        assert not por["S0 vs S1"]["significativo"] and por["S0 vs S1"]["p_holm"] == 1.0

    def test_solo_preguntas_comunes(self):
        filas = est.comparar_sistemas({"A": {"q1": 0, "q2": 1}, "B": {"q2": 1, "q3": 0}}, n_boot=100)
        assert filas[0]["n"] == 1

    def test_cohen_dz(self):
        assert est.cohen_dz([0, 0, 0], [1, 2, 3]) == pytest.approx(2.0)
