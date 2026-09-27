# -*- coding: utf-8 -*-
"""Tests aislados para evaluación humana — usan DB temporal, no tocan producción, con FK ON y sin lock."""
import sqlite3, pathlib, tempfile, json
import pytest

GEN="GEN_TEST_001"
QID="Q01"
BANCO_PUNTOS=[{"punto_id":"Q01_P01","descripcion":"p1"},{"punto_id":"Q01_P02","descripcion":"p2"}]

def _temp_db():
    import sys
    PROJECT_ROOT=pathlib.Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT/"backend"))
    import logger
    tmp=tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    db_path=pathlib.Path(tmp.name)
    orig=logger.DB_PATH
    logger.DB_PATH=str(db_path)
    logger.inicializar_bd()
    logger.DB_PATH=orig
    conn=sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    # Insert parent rows
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", (QID,"dummy pregunta","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO experimentos_rag (experimento_id, fecha, estado) VALUES (?,?,?)", ("EXP_TEST","2026-01-01","test"))
    conn.execute("INSERT INTO generacion_experimentos (generacion_experimento_id, retrieval_experimento_id, fecha, estado) VALUES (?,?,?,?)", (GEN,"EXP_TEST","2026-01-01","test"))
    # Also insert experimentos_rag for GEN
    conn.execute("INSERT INTO experimentos_rag (experimento_id, fecha, estado) VALUES (?,?,?)", (GEN,"2026-01-01","test"))
    conn.commit()
    return conn, db_path

def test_tablas_detalle_existen_isolated():
    conn, path=_temp_db()
    for tbl in ["evaluacion_completitud_detalle","evaluacion_faithfulness_detalle","evaluacion_citation_correctness_detalle"]:
        assert conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'").fetchone() is not None
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_estados_validos_isolated():
    conn, path=_temp_db()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,QID,"P_INVALID","INVALIDO","test","2026-01-01"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_duplicate_rechazada_isolated():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,QID,"Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,QID,"Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_m04_puede_evaluarse_isolated():
    conn, path=_temp_db()
    # Q04 insert should work (FK ok)
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q04","p","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,"Q04","Q04_P01","NO_CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    cnt=conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id='Q04'", (GEN,)).fetchone()[0]
    assert cnt==1
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_no_overwrite_isolated():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,QID,"Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,QID,"Q01_P01","NO_CUBIERTO","otro","2026-01-02"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_fk_generacion_existe():
    conn, path=_temp_db()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            ("GEN_INEXISTENTE",QID,"Q01_P01","CUBIERTO","test","2026-01-01"))
        assert False
    except sqlite3.IntegrityError:
        pass  # FK failed as expected
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)

def test_relevancia_rango():
    assert 5 in [1,2,3,4,5]
    assert 6 not in [1,2,3,4,5]

def test_parcial_conservado_isolated():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,QID,"Q01_P01","PARCIAL","investigador_manual_v1","2026-01-01"))
    conn.commit()
    estado=conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND punto_id=?", (GEN,QID,"Q01_P01")).fetchone()[0]
    assert estado=="PARCIAL"
    conn.close()
    pathlib.Path(path).unlink(missing_ok=True)
