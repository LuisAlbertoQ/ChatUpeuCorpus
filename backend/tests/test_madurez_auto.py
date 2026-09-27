# -*- coding: utf-8 -*-
"""Tests FASE 5: métricas automáticas OE8 (aislados, DB temporal)."""
import sqlite3, pathlib, tempfile, sys
_HERE = pathlib.Path(__file__).parent.parent.parent
for _r in (_HERE, pathlib.Path("/app"), pathlib.Path("/")):
    for _c in (_r / "evaluacion" / "madurez_oe8", _r / "data" / "evaluacion" / "madurez_oe8", _r / "evaluacion", _r / "data" / "evaluacion"):
        if (_c / "calcular_madurez.py").exists() and str(_c) not in sys.path:
            sys.path.insert(0, str(_c))
import calcular_madurez as cm


def _temp_conn(rows):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE interacciones (id INTEGER PRIMARY KEY, tipo_mensaje TEXT, tiempo_respuesta REAL, fuentes TEXT)")
    for tipo, tiempo, fuentes in rows:
        conn.execute("INSERT INTO interacciones (tipo_mensaje, tiempo_respuesta, fuentes) VALUES (?,?,?)", (tipo, tiempo, fuentes))
    conn.execute("""CREATE TABLE evaluacion_automatica (id INTEGER PRIMARY KEY, periodo TEXT, fecha_calculo TEXT,
        total_interacciones INTEGER, pct_m02 REAL, pct_m03 REAL, pct_m04 REAL, pct_m05 REAL, pct_m06 REAL,
        pct_con_fuentes REAL, tiempo_promedio REAL, tiempo_p95 REAL, funcional_auto REAL, recuperacion_auto REAL,
        explicabilidad_auto REAL, usabilidad_auto REAL, gobernanza_auto REAL, preparacion_auto REAL,
        puntaje_global REAL, nivel TEXT, dimension_critica_minima REAL)""")
    conn.commit()
    return conn


def test_exclusion_m01_m07_m08():
    conn = _temp_conn([("M02", 2.0, "f"), ("M01", 1.0, ""), ("M07", 1.0, ""), ("M08", 1.0, "")])
    m = cm.calcular_metricas_automaticas(conn)
    assert m["total_interacciones"] == 1
    assert m["total_excluidos"] == 3
    conn.close()

def test_m06_no_es_retrieval_failure():
    conn = _temp_conn([("M06", 1.0, "")] * 4 + [("M02", 1.0, "f")] * 6)
    m = cm.calcular_metricas_automaticas(conn)
    assert abs(m["pct_m06"] - 40.0) < 1e-9
    d = cm.calcular_dimensiones_auto(m)
    assert d["Preparación tecnológica y mejora"] == 1.0  # 100-40=60 <80 -> 1.0
    conn.close()

def test_porcentajes_y_fuentes():
    conn = _temp_conn([("M02", 2.0, "doc · Art 1"), ("M02", 3.0, ""), ("M04", 1.0, "x"), ("M04", 1.0, "")])
    m = cm.calcular_metricas_automaticas(conn)
    assert abs(m["pct_m02"] - 50.0) < 1e-9
    assert abs(m["pct_con_fuentes"] - 50.0) < 1e-9
    conn.close()

def test_media_y_p95():
    rows = [("M02", float(i), "f") for i in range(1, 101)]
    conn = _temp_conn(rows)
    m = cm.calcular_metricas_automaticas(conn)
    assert abs(m["tiempo_promedio"] - 50.5) < 1e-9
    assert m["tiempo_p95"] == 96.0
    assert m["n_tiempos"] == 100 and m["tiempos_nulos"] == 0 and m["tiempos_negativos"] == 0
    conn.close()

def test_nulos_y_negativos():
    conn = _temp_conn([("M02", None, "f"), ("M02", -5.0, "f"), ("M02", 10.0, "f")])
    m = cm.calcular_metricas_automaticas(conn)
    assert m["tiempos_nulos"] == 1 and m["tiempos_negativos"] == 1 and m["n_tiempos"] == 1
    conn.close()

def _mk(pct_m02=0, fuentes=0, t=5.0, m03=0, m05=0, m06=0):
    return {"pct_m02": pct_m02, "pct_con_fuentes": fuentes, "tiempo_promedio": t,
            "pct_m03": m03, "pct_m05": m05, "pct_m06": m06}

def test_fronteras_funcional():
    f = lambda p: cm.calcular_dimensiones_auto(_mk(pct_m02=p))["Funcional"]
    assert f(24.99) == 1.0 and f(25) == 2.0 and f(49.99) == 2.0 and f(50) == 3.0
    assert f(74.99) == 3.0 and f(75) == 4.0 and f(89.99) == 4.0 and f(90) == 5.0

def test_fronteras_recuperacion():
    f = lambda p: cm.calcular_dimensiones_auto(_mk(fuentes=p))["Recuperación documental"]
    assert f(24.99) == 1.0 and f(25) == 2.0 and f(50) == 3.0 and f(75) == 4.0 and f(90) == 5.0

def test_fronteras_explicabilidad():
    f = lambda p: cm.calcular_dimensiones_auto(_mk(fuentes=p))["Explicabilidad y trazabilidad"]
    assert f(39.99) == 1.0 and f(40) == 2.0 and f(59.99) == 2.0 and f(60) == 3.0
    assert f(79.99) == 3.0 and f(80) == 4.0 and f(94.99) == 4.0 and f(95) == 5.0

def test_fronteras_usabilidad():
    f = lambda t: cm.calcular_dimensiones_auto(_mk(t=t))["Usabilidad"]
    assert f(10) == 5.0 and f(10.01) == 4.0 and f(20) == 4.0 and f(20.5) == 3.0
    assert f(30) == 3.0 and f(30.1) == 2.0 and f(40) == 2.0 and f(40.1) == 1.0

def test_gobernanza_band():
    f = lambda r: cm.calcular_dimensiones_auto(_mk(m03=r, m05=0))["Gobernanza y uso responsable"]
    assert f(4.99) == 3.0 and f(5) == 5.0 and f(30) == 5.0 and f(30.01) == 2.0

def test_gobernanza_suma_m03_m05():
    m = _mk(m03=3, m05=4)  # 7% -> 5
    assert cm.calcular_dimensiones_auto(m)["Gobernanza y uso responsable"] == 5.0

def test_preparacion():
    f = lambda p6: cm.calcular_dimensiones_auto(_mk(m06=p6))["Preparación tecnológica y mejora"]
    assert f(2) == 5.0 and abs(f(2.01) - 4.0) < 1e-9  # 97.99 <98 -> 4
    assert f(5) == 4.0 and f(10) == 3.0 and f(20) == 2.0 and f(20.01) == 1.0

def test_scores_1_5():
    import random
    random.seed(7)
    for _ in range(50):
        m = _mk(pct_m02=random.uniform(0, 100), fuentes=random.uniform(0, 100),
                t=random.uniform(0, 100), m03=random.uniform(0, 50),
                m05=random.uniform(0, 50), m06=random.uniform(0, 100))
        for v in cm.calcular_dimensiones_auto(m).values():
            assert v in (1.0, 2.0, 3.0, 4.0, 5.0)

def test_umbrales_centralizados():
    assert cm.UMBRALES_OE8["funcional"] == [(90, 5), (75, 4), (50, 3), (25, 2)]
    assert cm.UMBRALES_OE8["recuperacion"] == [(90, 5), (75, 4), (50, 3), (25, 2)]
    assert cm.UMBRALES_OE8["explicabilidad"] == [(95, 5), (80, 4), (60, 3), (40, 2)]
    assert cm.UMBRALES_OE8["usabilidad_tiempo"] == [(10, 5), (20, 4), (30, 3), (40, 2)]
    assert cm.UMBRALES_OE8["gobernanza_rango_optimo"] == (5.0, 30.0)
    assert cm.UMBRALES_OE8["preparacion"] == [(98, 5), (95, 4), (90, 3), (80, 2)]
    assert cm.TIPOS_EXCLUIDOS_OE8 == ("M01", "M07", "M08")

def test_no_usa_banco_tecnico():
    import inspect
    src = inspect.getsource(cm.calcular_metricas_automaticas)
    # ignorar docstring: solo el cuerpo con SQL
    body = src.split('"""', 2)[-1]
    for t in ("banco_preguntas", "groundtruth", "evaluacion_retrieval", "evaluacion_generacion", "banco_no_answer"):
        assert t not in body
    assert "FROM interacciones" in body

def test_snapshot_reproducible():
    conn = _temp_conn([("M02", 2.0, "f")] * 8 + [("M04", 1.0, "")] * 2)
    m = cm.calcular_metricas_automaticas(conn)
    d = cm.calcular_dimensiones_auto(m)
    cm.guardar_snapshot(conn, m, d, "X", 1.0, 1.0, etiqueta="T")
    cm.guardar_snapshot(conn, m, d, "X", 1.0, 1.0, etiqueta="T")
    rows = conn.execute("SELECT pct_m02, funcional_auto, etiqueta FROM evaluacion_automatica WHERE etiqueta='T'").fetchall()
    assert len(rows) == 2 and rows[0] == rows[1]
    conn.close()
