#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calcular_metricas_humanas.py — Calcula agregados a partir de evaluaciones humanas ya rellenadas.
No puntúa si ficha vacía.
Fórmulas §4,7,9: estricta y ponderada, NULL si no evaluable.
"""
import sqlite3, pathlib, json, statistics
PROJECT_ROOT=pathlib.Path(__file__).parent.parent.parent
DB=PROJECT_ROOT/"registro_interacciones.db"
GEN="GEN_20260924_232127_8e01ef"
GTV="v3.1_curado"
import sys
sys.path.insert(0, str(PROJECT_ROOT/"backend"))
import logger
logger.DB_PATH=str(DB)
logger.inicializar_bd()
conn=sqlite3.connect(str(DB))

def completitud_por_pregunta(qid):
    # Denominador: puntos v3.1 de la pregunta (66 distribuidos); evaluados filtrados por GTV
    rows=list(conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND groundtruth_version=?", (GEN, qid, GTV)).fetchall())
    if not rows: return None, None
    total=len(rows)
    covered=sum(1 for r in rows if r[0]=="CUBIERTO")
    partial=sum(1 for r in rows if r[0]=="PARCIAL")
    estricta=covered/total if total else None
    ponderada=(covered+0.5*partial)/total if total else None
    return estricta, ponderada

def faithfulness_por_pregunta(qid):
    rows=list(conn.execute("SELECT estado FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND groundtruth_version=?", (GEN, qid, GTV)).fetchall())
    if not rows: return None, None
    total=len(rows)
    sop=sum(1 for r in rows if r[0]=="SOPORTADO")
    parc=sum(1 for r in rows if r[0]=="PARCIALMENTE_SOPORTADO")
    est=sop/total if total else None
    pond=(sop+0.5*parc)/total if total else None
    return est, pond

def citation_correctness_por_pregunta(qid):
    rows=list(conn.execute("SELECT estado FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND groundtruth_version=? AND estado!='NO_ASOCIABLE'", (GEN, qid, GTV)).fetchall())
    if not rows: return None, None
    total=len(rows)
    corr=sum(1 for r in rows if r[0]=="CORRECTA")
    parc=sum(1 for r in rows if r[0]=="PARCIAL")
    est=corr/total if total else None
    pond=(corr+0.5*parc)/total if total else None
    return est, pond

# Verificar ficha vacía -> no calcular (filtrado v3.1)
has_any=conn.execute("SELECT count(*) FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchone()[0]
if has_any==0:
    print(f"Ficha vacía v3.1 (0 completitud {GTV}), no hay cálculos humanos todavía. Agregados NULL.")
    sys.exit(0)

QIDS=[f"Q{i:02d}" for i in range(1,18)]
for qid in QIDS:
    ce, cp = completitud_por_pregunta(qid)
    fe, fp = faithfulness_por_pregunta(qid)
    ce2, cp2 = citation_correctness_por_pregunta(qid)
    rel=conn.execute("SELECT relevancia FROM evaluacion_generacion WHERE generacion_experimento_id=? AND pregunta_id=? AND groundtruth_version=?", (GEN, qid, GTV)).fetchone()
    print(f"{qid} completitud {ce} / {cp} faith {fe}/{fp} cite {ce2}/{cp2} rel {rel[0] if rel else None}")
    # Persistir estrictos en evaluacion_generacion (solo v3.1, sin sobrescribir otra versión)
    conn.execute("UPDATE evaluacion_generacion SET completitud=?, faithfulness=?, citation_correctness=? WHERE generacion_experimento_id=? AND pregunta_id=? AND (groundtruth_version=? OR groundtruth_version IS NULL)", (ce, fe, ce2, GEN, qid, GTV))
conn.commit()

def _avg(xs):
    xs=[x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None
# Completitud: macro por pregunta (estricta sobre puntos de cada Q) y micro sobre 66
per_q_ce=[completitud_por_pregunta(q)[0] for q in QIDS]
per_q_cp=[completitud_por_pregunta(q)[1] for q in QIDS]
rows=conn.execute("SELECT estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchall()
micro_ce=sum(1 for r in rows if r[0]=="CUBIERTO")/len(rows) if rows else None
micro_cp=(sum(1 for r in rows if r[0]=="CUBIERTO")+0.5*sum(1 for r in rows if r[0]=="PARCIAL"))/len(rows) if rows else None
print(f"COMPLETENESS macro_estricta={_avg(per_q_ce)} macro_ponderada={_avg(per_q_cp)} micro_estricta={micro_ce} micro_ponderada={micro_cp} n={len(rows)}")
# Faithfulness: macro solo evaluables, micro por claims
per_q_fe=[faithfulness_por_pregunta(q)[0] for q in QIDS]
per_q_fp=[faithfulness_por_pregunta(q)[1] for q in QIDS]
frows=conn.execute("SELECT estado FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchall()
micro_fe=sum(1 for r in frows if r[0]=="SOPORTADO")/len(frows) if frows else None
micro_fp=(sum(1 for r in frows if r[0]=="SOPORTADO")+0.5*sum(1 for r in frows if r[0]=="PARCIALMENTE_SOPORTADO"))/len(frows) if frows else None
print(f"FAITHFULNESS macro_estricta={_avg(per_q_fe)} macro_ponderada={_avg(per_q_fp)} micro_estricta={micro_fe} micro_ponderada={micro_fp} n={len(frows)} evaluables={sum(1 for x in per_q_fe if x is not None)}/17")
# Citation correctness: NO_ASOCIABLE excluida del denominador (documentado)
per_q_cc=[citation_correctness_por_pregunta(q)[0] for q in QIDS]
per_q_ccp=[citation_correctness_por_pregunta(q)[1] for q in QIDS]
crows=conn.execute("SELECT estado FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND groundtruth_version=? AND estado!='NO_ASOCIABLE'", (GEN, GTV)).fetchall()
micro_cc=sum(1 for r in crows if r[0]=="CORRECTA")/len(crows) if crows else None
micro_ccp=(sum(1 for r in crows if r[0]=="CORRECTA")+0.5*sum(1 for r in crows if r[0]=="PARCIAL"))/len(crows) if crows else None
print(f"CITATION macro_estricta={_avg(per_q_cc)} macro_ponderada={_avg(per_q_ccp)} micro_estricta={micro_cc} micro_ponderada={micro_ccp} n={len(crows)} evaluables={sum(1 for x in per_q_cc if x is not None)}/17")
# Relevancia
rels=[r[0] for r in conn.execute("SELECT relevancia FROM evaluacion_generacion WHERE generacion_experimento_id=? AND groundtruth_version=?", (GEN, GTV)).fetchall()]
from collections import Counter
print(f"RELEVANCIA promedio={_avg(rels)} distribucion={dict(sorted(Counter(rels).items()))} n={len([r for r in rels if r is not None])}/17")
