#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera evaluacion/humana/fichas_humanas_v31/ (17 fichas, 66 puntos) desde v3.1_curado.
Solo lectura de DB + respuestas congeladas GEN_20260924_232127_8e01ef. Sin juicios."""
import json, pathlib, sqlite3, sys
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.parent.parent.parent
DB = PROJECT_ROOT / "registro_interacciones.db"
GEN = "GEN_20260924_232127_8e01ef"
RET = "EXP_20260924_231553_2cd31b"
GTV = "v3.1_curado"
OUT = PROJECT_ROOT / "evaluacion" / "humana" / "fichas_humanas_v31"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
import validators_evaluacion as vd
conn = sqlite3.connect(str(DB))
qs = conn.execute("SELECT pregunta_id, pregunta FROM groundtruth_v31_preguntas ORDER BY pregunta_id").fetchall()
assert len(qs) == 17, len(qs)
total = 0
for qid, pregunta in qs:
    grow = conn.execute("SELECT respuesta_generada, fuentes_generadas, tipo_mensaje, source_validity, citation_match, citation_presence, answerable_but_abstained FROM evaluacion_generacion WHERE generacion_experimento_id=? AND pregunta_id=?", (GEN, qid)).fetchone()
    assert grow, f"sin baseline {qid}"
    resp, fg, tm, sv, cm, cp, abst = grow
    ctx = conn.execute("SELECT chunk_id_recuperado, documento_recuperado, articulo_recuperado, distancia_ajustada FROM evaluacion_retrieval WHERE pregunta_id=? AND experimento_id=? AND entro_top4=1 ORDER BY rank_reranked", (qid, RET)).fetchall()
    pts = conn.execute("SELECT punto_id, descripcion, documento, articulo, evidencia FROM groundtruth_v31_puntos WHERE pregunta_id=? ORDER BY punto_id", (qid,)).fetchall()
    total += len(pts)
    ficha = {
        "pregunta_id": qid,
        "pregunta": conn.execute("SELECT pregunta FROM banco_preguntas WHERE id=?", (qid,)).fetchone()[0],
        "respuesta_congelada": resp,
        "contexto_real": [{"chunk_id": r[0], "documento": r[1], "articulo": r[2], "distancia": r[3]} for r in ctx],
        "fuentes_finales": json.loads(fg) if fg else [],
        "diagnosticos_automaticos": {"source_validity": sv, "citation_match": cm, "citation_presence": cp, "answerable_but_abstained": abst, "tipo_mensaje": tm,
            "nota": "Automático/determinístico del baseline; no es recomendación de score humano."},
        "groundtruth_version": GTV,
        "generation_experiment_id": GEN,
        "retrieval_experimento_id": RET,
        "borrador_pre_v31": f"../fichas_humanas/ficha_{qid}_{GEN}.json",
        "puntos_esperados": [{"punto_id": p[0], "descripcion": p[1], "documento": p[2], "articulo": p[3], "evidencia": p[4], "estado": None, "justificacion": "", "fragmento_respuesta": ""} for p in pts],
        "claims": [],
        "citas": [{"cita_texto": c["raw"], "documento": c["documento"], "articulo": c["articulo"], "tipo": c.get("tipo", ""), "claim_asociado": "", "estado": None, "justificacion": ""} for c in vd.parse_citas(resp or "")],
        "relevancia": None,
        "relevancia_justificacion": "",
        "notas": "",
        "evaluador": "",
    }
    (OUT / f"ficha_{qid}_{GEN}_v31.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{qid}: {len(pts)} puntos, {len(ficha['citas'])} citas")
print("TOTAL:", total)
assert total == 66, total
# índice + CSV consolidado
(OUT / f"indice_{GEN}_v31.json").write_text(json.dumps({"generacion_experimento_id": GEN, "groundtruth_version": GTV, "total_puntos": total, "fichas": [f"ficha_{qid}_{GEN}_v31.json" for qid, _ in qs]}, ensure_ascii=False, indent=2), encoding="utf-8")
import csv
with open(OUT / f"evaluacion_manual_v31.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tipo", "pregunta_id", "id", "descripcion", "estado_humano", "justificacion", "fragmento"])
    for qid, _ in qs:
        data = json.loads((OUT / f"ficha_{qid}_{GEN}_v31.json").read_text(encoding="utf-8"))
        for p in data["puntos_esperados"]:
            w.writerow(["PUNTO", qid, p["punto_id"], p["descripcion"], "", "", ""])
        for c in data["citas"]:
            w.writerow(["CITA", qid, c["cita_texto"], f"{c['documento']} {c['articulo']}".strip(), "", "", ""])
        w.writerow(["RELEVANCIA", qid, "", "", "", "", ""])
        w.writerow(["NOTAS", qid, "", "", "", "", ""])
print("OK fichas v3.1")
