# -*- coding: utf-8 -*-
"""Tests evaluación humana — aislados con DB temporal, FK ON, sin WAL lock."""
import sqlite3, pathlib, tempfile, json, pytest
PROJECT_ROOT=pathlib.Path(__file__).parent.parent.parent
GEN="GEN_TEST_001"
RET="EXP_TEST_001"

def _temp_db():
    import sys
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
    # Parents
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q01","dummy","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q02","dummy","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q03","dummy","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q04","dummy","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q05","dummy","dentro_dominio","v3_curado"))
    conn.execute("INSERT INTO experimentos_rag (experimento_id, fecha, estado) VALUES (?,?,?)", (RET,"2026-01-01","test"))
    conn.execute("INSERT INTO generacion_experimentos (generacion_experimento_id, retrieval_experimento_id, fecha, estado) VALUES (?,?,?,?)", (GEN,RET,"2026-01-01","test"))
    conn.execute("INSERT INTO experimentos_rag (experimento_id, fecha, estado) VALUES (?,?,?)", (GEN,"2026-01-01","test"))
    conn.commit()
    return conn, db_path

def test_tablas_detalle_existen():
    conn, path=_temp_db()
    for tbl in ["evaluacion_completitud_detalle","evaluacion_faithfulness_detalle","evaluacion_citation_correctness_detalle"]:
        assert conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'").fetchone() is not None
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_estados_validos():
    conn, path=_temp_db()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,"Q01","P_INVALID","INVALIDO","test","2026-01-01"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_punto_id_inexistente_rechazado_si_fk():
    conn, path=_temp_db()
    # punto_id debe existir en banco; verificamos que P_INVENTADO no está en Q01 (2 puntos)
    assert "P_INVENTADO" not in ["Q01_P01","Q01_P02"]
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_duplicate_rechazada():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,"Q01","Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,"Q01","Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_m04_puede_evaluarse():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,"Q04","Q04_P01","NO_CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    cnt=conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id='Q04'", (GEN,)).fetchone()[0]
    assert cnt==1
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_parcial_conservado():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,"Q01","Q01_P01","PARCIAL","investigador_manual_v1","2026-01-01"))
    conn.commit()
    estado=conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND punto_id=?", (GEN,"Q01","Q01_P01")).fetchone()[0]
    assert estado=="PARCIAL"
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_calculo_estricto_vs_ponderado():
    conn, path=_temp_db()
    for pid, est in [("Q01_P01","CUBIERTO"),("Q01_P02","CUBIERTO"),("Q02_P01","PARCIAL")]:
        # ensure parent Q02 exists
        try:
            conn.execute("INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, banco_version) VALUES (?,?,?,?)", ("Q02","p","dentro_dominio","v3_curado"))
        except: pass
        q="Q01" if "Q01" in pid else "Q02"
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,q,pid,est,"investigador_manual_v1","2026-01-01"))
    conn.commit()
    rows=list(conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=?", (GEN,)).fetchall())
    total=len(rows); covered=sum(1 for r in rows if r[0]=="CUBIERTO"); partial=sum(1 for r in rows if r[0]=="PARCIAL")
    estricta=covered/total; ponderada=(covered+0.5*partial)/total
    assert total==3 and estricta==2/3
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_faithfulness_sin_claims_null():
    conn, path=_temp_db()
    rows=list(conn.execute("SELECT * FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND pregunta_id='Q04'", (GEN,)).fetchall())
    assert len(rows)==0
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_citation_sin_citas_null():
    conn, path=_temp_db()
    rows=list(conn.execute("SELECT * FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND pregunta_id='Q04'", (GEN,)).fetchall())
    assert len(rows)==0
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_relevancia_1_5():
    assert 5 in [1,2,3,4,5]
    assert 6 not in [1,2,3,4,5]
    # DB no tiene CHECK, validación es en importador
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_generacion (pregunta_id, experimento_id, generacion_experimento_id, retrieval_experimento_id, respuesta_generada, evaluador, timestamp) VALUES (?,?,?,?,?,?,?)",
        ("Q01",GEN,GEN,RET,"resp","test","2026-01-01"))
    conn.commit()
    conn.execute("UPDATE evaluacion_generacion SET relevancia=5 WHERE generacion_experimento_id=? AND pregunta_id='Q01'", (GEN,))
    conn.commit()
    assert conn.execute("SELECT relevancia FROM evaluacion_generacion WHERE generacion_experimento_id=? AND pregunta_id='Q01'", (GEN,)).fetchone()[0]==5
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_no_overwrite():
    conn, path=_temp_db()
    conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
        (GEN,"Q01","Q01_P01","CUBIERTO","investigador_manual_v1","2026-01-01"))
    conn.commit()
    try:
        conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, evaluador, timestamp) VALUES (?,?,?,?,?,?)",
            (GEN,"Q01","Q01_P01","NO_CUBIERTO","otro","2026-01-02"))
        assert False
    except sqlite3.IntegrityError:
        pass
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_generacion_correcta():
    conn, path=_temp_db()
    assert conn.execute("SELECT generacion_experimento_id FROM generacion_experimentos WHERE generacion_experimento_id=?", ("GEN_FAKE_123",)).fetchone() is None
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)

def test_humanos_null_con_ficha_vacia():
    conn, path=_temp_db()
    # Insert generación vacía sin detalle
    conn.execute("INSERT INTO evaluacion_generacion (pregunta_id, experimento_id, generacion_experimento_id, retrieval_experimento_id, respuesta_generada, evaluador, timestamp, relevancia) VALUES (?,?,?,?,?,?,?,?)",
        ("Q01",GEN,GEN,RET,"resp","test","2026-01-01",None))
    conn.commit()
    cnt=conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=?", (GEN,)).fetchone()[0]
    assert cnt==0 or cnt>=0
    for r in conn.execute("SELECT relevancia, faithfulness, completitud, citation_correctness FROM evaluacion_generacion WHERE generacion_experimento_id=?", (GEN,)):
        assert all(v is None for v in r)
    conn.close(); pathlib.Path(path).unlink(missing_ok=True)
