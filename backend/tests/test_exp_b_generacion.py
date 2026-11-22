# -*- coding: utf-8 -*-
"""Tests de evaluacion/generacion/exp_b_generacion.py (Revisión 3, experimento B)."""
import importlib.util
from pathlib import Path

import pytest

for _cand in [Path(__file__).parent.parent.parent / "evaluacion" / "generacion" / "exp_b_generacion.py",
              Path("/data/evaluacion/generacion/exp_b_generacion.py")]:
    if _cand.exists():
        _spec = importlib.util.spec_from_file_location("exp_b", _cand)
        exp_b = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(exp_b)
        break
else:
    pytest.skip("exp_b_generacion.py no encontrado", allow_module_level=True)

DOCS = ["REGLAMENTO BECAS 2021 ACTUALIZADO"]
ARTS = ["Artículo 49°"]


@pytest.mark.parametrize("respuesta,esperado", [
    ("Debes presentar la solicitud (REGLAMENTO BECAS 2021 ACTUALIZADO, Artículo 49°).", "exacta"),
    ("Según el artículo 49 debes presentar la solicitud.", "exacta"),
    ("El reglamento de becas 2021 actualizado indica que debes postular en marzo.", "parcial"),
    ("Debes presentar la solicitud (Reglamento General UPeU, Artículo 12°).", "incorrecta"),
    ("Debes presentar la solicitud en la oficina de bienestar.", "ausente"),
])
def test_atribucion(respuesta, esperado):
    assert exp_b.atribucion(respuesta, DOCS, ARTS) == esperado


def test_articulo_490_no_cuenta_como_49():
    assert exp_b.atribucion("Ver Artículo 490°.", DOCS, ARTS) == "incorrecta"
