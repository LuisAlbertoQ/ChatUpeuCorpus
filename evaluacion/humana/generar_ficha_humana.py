#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_ficha_humana.py — Ficha vacía para evaluación manual V3 (sin puntuar).
Genera 1 JSON + 1 CSV por pregunta con 50 puntos checklist, claims y citas vacíos.
"""
import json, pathlib, sqlite3, sys
PROJECT_ROOT=pathlib.Path(__file__).parent.parent.parent.parent.parent.parent.parent
DB=PROJECT_ROOT/"registro_interacciones.db"
GEN="GEN_20260924_232127_8e01ef"
OUT_DIR=PROJECT_ROOT/"evaluacion"/"humana"/"fichas_humanas"
OUT_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(PROJECT_ROOT/"backend"))
import logger
logger.DB_PATH=str(DB)
logger.inicializar_bd()
conn=sqlite3.connect(str(DB))
# Datos
banco=list(conn.execute("SELECT id, pregunta FROM banco_preguntas WHERE banco_version='v3_curado' ORDER BY id").fetchall())
gen_rows=dict((r[0], r) for r in conn.execute("SELECT pregunta_id, respuesta_generada, puntos_esperados, evidencias_esperadas, fuentes_generadas, tipo_mensaje, source_validity, citation_match FROM evaluacion_generacion WHERE generacion_experimento_id=?", (GEN,)).fetchall())
# Para cada Q, generar ficha
for qid, pregunta in banco:
    row=gen_rows.get(qid)
    if not row:
        print(f"WARN {qid} sin generación")
        continue
    _, resp, pj, ej, fg, tm, sv, cm = row
    puntos=json.loads(pj) if pj else []
    evid=json.loads(ej) if ej else []
    # contexto real: Top4 chunks
    ctx_rows=list(conn.execute("SELECT chunk_id_recuperado, documento_recuperado, articulo_recuperado, distancia_ajustada FROM evaluacion_retrieval WHERE pregunta_id=? AND experimento_id='EXP_20260924_231553_2cd31b' AND entro_top4=1 ORDER BY rank_reranked", (qid,)).fetchall())
    # Citas detectadas
    import validators_evaluacion as vd
    citas=vd.parse_citas(resp or "")
    # Claims: extraer heurísticamente oraciones con verbo normativo (placeholder, humano debe refinar)
    # No puntuar, solo preparar estructura vacía: el humano extraerá claims reales
    ficha={
        "pregunta_id": qid,
        "pregunta": pregunta,
        "respuesta_congelada": resp,
        "contexto_real": [{"chunk_id":r[0],"documento":r[1],"articulo":r[2],"distancia":r[3]} for r in ctx_rows],
        "fuentes_finales": json.loads(fg) if fg else [],
        "tipo_mensaje": tm,
        "source_validity": sv,
        "citation_match": cm,
        "puntos_esperados": [],
        "claims": [],
        "citas": [],
        "relevancia": None,
        "notas": ""
    }
    for p in puntos:
        ev_next=[e for e in evid if e["punto_id"]==p["punto_id"]]
        ficha["puntos_esperados"].append({
            "punto_id": p["punto_id"],
            "descripcion": p["descripcion"],
            "evidencia": ev_next[0]["texto_evidencia"] if ev_next else "",
            "estado": None,  # CUBIERTO/PARCIAL/NO_CUBIERTO - vacio
            "justificacion": "",
            "fragmento_respuesta": ""
        })
    # Claims placeholder: humano debe extraer; dejamos 1 claim vacío por punto como guía, pero sin estado
    # No auto-generar claims con regex para no sesgar
    # Dejamos array vacío para que humano llene
    for c in citas:
        ficha["citas"].append({
            "cita_texto": c["raw"],
            "documento": c["documento"],
            "articulo": c["articulo"],
            "tipo": c.get("tipo",""),
            "claim_asociado": "",
            "estado": None,  # CORRECTA/PARCIAL/INCORRECTA/NO_ASOCIABLE
            "justificacion": ""
        })
    # Guardar JSON por pregunta
    out_path=OUT_DIR / f"ficha_{qid}_{GEN}.json"
    out_path.write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{qid}: {len(puntos)} puntos, {len(citas)} citas -> {out_path.name}")

# Índice agregado
idx={
    "generacion_experimento_id": GEN,
    "retrieval_experimento_id": "EXP_20260924_231553_2cd31b",
    "total_puntos": 50,
    "total_preguntas": 17,
    "fichas": [f"ficha_{qid}_{GEN}.json" for qid,_ in banco],
    "evaluador": "investigador_manual_v1",
    "estado": "vacía - pendiente evaluación humana"
}
(OUT_DIR / f"indice_{GEN}.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Índice: {OUT_DIR / f'indice_{GEN}.json'}")
# CSV resumen vacío
import csv
csv_path=OUT_DIR / f"resumen_fichas_{GEN}.csv"
with open(csv_path,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["pregunta_id","pregunta","respuesta_len","tipo_mensaje","num_puntos","num_citas","relevancia","completitud_estricta","faithfulness","citation_correctness"])
    for qid, pregunta in banco:
        row=gen_rows.get(qid)
        pj=json.loads(row[2]) if row and row[2] else []
        citas=len(__import__('validators_evaluacion').parse_citas(row[1] or "")) if row else 0
        w.writerow([qid, pregunta[:50], len(row[1]) if row else 0, row[5] if row else "", len(pj), citas, "", "", "", ""])
print(f"CSV: {csv_path}")
print("Fichas listas - NO puntuar automáticamente")
