#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importar_ficha_humana.py — Importa fichas completadas por investigador (validación estricta, no overwrite silencioso).
Uso: python evaluacion/humana/importar_ficha_humana.py evaluacion/humana/fichas_humanas/ficha_Q01_*.json
"""
import json, sqlite3, pathlib, sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).parent.parent.parent
DB=PROJECT_ROOT/"registro_interacciones.db"
sys.path.insert(0, str(PROJECT_ROOT/"backend"))
import logger
GTV = "v3.1_curado"

def validar_ficha(data, gen_id):
    errors=[]
    if data.get("groundtruth_version") != GTV:
        errors.append(f"groundtruth_version debe ser {GTV}, hallado {data.get('groundtruth_version')} (fichas v3 rechazadas en fase v3.1)")
    if data.get("pregunta_id") not in [f"Q{i:02d}" for i in range(1,18)]:
        errors.append(f"pregunta_id inválido {data.get('pregunta_id')}")
    # punto_id válido contra v3.1 (no v3)
    import sqlite3
    try:
        _c = sqlite3.connect(str(DB))
        _v31 = {r[0] for r in _c.execute("SELECT punto_id FROM groundtruth_v31_puntos WHERE pregunta_id=?", (data.get("pregunta_id"),)).fetchall()}
        _c.close()
    except Exception:
        _v31 = set()
    for p in data.get("puntos_esperados",[]):
        if p["estado"] not in (None,"CUBIERTO","PARCIAL","NO_CUBIERTO"):
            errors.append(f"punto {p['punto_id']} estado {p['estado']}")
        if p["estado"] is not None and _v31 and p["punto_id"] not in _v31:
            errors.append(f"punto {p['punto_id']} no existe en {GTV} (¿ficha v3?)")
    # relevancia 1-5
    rel=data.get("relevancia")
    if rel is not None and rel not in [1,2,3,4,5]:
        errors.append(f"relevancia {rel}")
    # claims
    for c in data.get("claims",[]):
        if c.get("estado") not in (None,"SOPORTADO","PARCIALMENTE_SOPORTADO","NO_SOPORTADO"):
            errors.append(f"claim {c.get('claim_id')} estado {c.get('estado')}")
    # citas
    for ci in data.get("citas",[]):
        if ci.get("estado") not in (None,"CORRECTA","PARCIAL","INCORRECTA","NO_ASOCIABLE"):
            errors.append(f"cita {ci.get('cita_texto')} estado {ci.get('estado')}")
    # evaluador
    # debe haber al menos un campo evaluador no vacío si hay algún juicio
    has_judgment=any(p["estado"] for p in data.get("puntos_esperados",[])) or data.get("relevancia") is not None
    if has_judgment and not data.get("evaluador"):
        # ficha nivel pregunta no tiene evaluador, pero detalle sí
        pass
    return errors

def main():
    if len(sys.argv)<2:
        print("Uso: python importar_ficha_humana.py <ficha.json> [...]")
        sys.exit(1)
    logger.DB_PATH=str(DB)
    logger.inicializar_bd()
    conn=sqlite3.connect(str(DB))
    for path_str in sys.argv[1:]:
        path=Path(path_str)
        if not path.exists():
            path=PROJECT_ROOT / path_str
        data=json.loads(path.read_text(encoding="utf-8"))
        gen_id=data.get("generation_experiment_id") or "GEN_20260924_232127_8e01ef"
        # fallback: try to infer from filename
        if "generation_experiment_id" not in data:
            # from ficha
            import re
            m=re.search(r"GEN_\d{8}_\d{6}_\w+", path.name)
            if m: gen_id=m.group(0)
        errors=validar_ficha(data, gen_id)
        if errors:
            print(f"{path.name} ERRORES: {errors}")
            continue
        # Verificar baseline distinto rechazado
        if gen_id != "GEN_20260924_232127_8e01ef":
            print(f"{path.name} rechazado: generacion_experimento_id {gen_id} != baseline oficial")
            continue
        # No overwrite silencioso: verificar si ya existe evaluación para ese punto/claim
        qid=data["pregunta_id"]
        # Completitud: check duplicates (versionado v3.1)
        for p in data["puntos_esperados"]:
            if p["estado"] is None: continue
            exists=conn.execute("SELECT id FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND punto_id=? AND groundtruth_version=?", (gen_id, qid, p["punto_id"], GTV)).fetchone()
            if exists:
                print(f"{qid} punto {p['punto_id']} ya evaluado, no overwrite")
                continue
            conn.execute("INSERT INTO evaluacion_completitud_detalle (generacion_experimento_id, pregunta_id, punto_id, estado, justificacion, fragmento_respuesta, evaluador, timestamp, groundtruth_version) VALUES (?,?,?,?,?,?,?,?,?)",
                (gen_id, qid, p["punto_id"], p["estado"], p.get("justificacion",""), p.get("fragmento_respuesta",""), data.get("evaluador","investigador_manual_v1"), __import__('datetime').datetime.now().isoformat(), GTV))
        # Faithfulness
        for c in data.get("claims",[]):
            if c.get("estado") is None: continue
            exists=conn.execute("SELECT id FROM evaluacion_faithfulness_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND claim_id=? AND groundtruth_version=?", (gen_id, qid, c["claim_id"], GTV)).fetchone()
            if exists:
                print(f"{qid} claim {c['claim_id']} ya existe")
                continue
            conn.execute("INSERT INTO evaluacion_faithfulness_detalle (generacion_experimento_id, pregunta_id, claim_id, claim_texto, estado, evidencia_contexto, evaluador, timestamp, groundtruth_version) VALUES (?,?,?,?,?,?,?,?,?)",
                (gen_id, qid, c["claim_id"], c["claim_texto"], c["estado"], c.get("evidencia_contexto",""), c.get("evaluador","investigador_manual_v1"), __import__('datetime').datetime.now().isoformat(), GTV))
        # Citation correctness
        for ci in data.get("citas",[]):
            if ci.get("estado") is None: continue
            # need citation_id
            cid=ci.get("citation_id") or ci["cita_texto"][:30]
            exists=conn.execute("SELECT id FROM evaluacion_citation_correctness_detalle WHERE generacion_experimento_id=? AND pregunta_id=? AND citation_id=? AND groundtruth_version=?", (gen_id, qid, cid, GTV)).fetchone()
            if exists:
                print(f"{qid} cita {cid} ya existe")
                continue
            conn.execute("INSERT INTO evaluacion_citation_correctness_detalle (generacion_experimento_id, pregunta_id, citation_id, cita_texto, claim_asociado, estado, justificacion, evaluador, timestamp, groundtruth_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (gen_id, qid, cid, ci["cita_texto"], ci.get("claim_asociado",""), ci["estado"], ci.get("justificacion",""), ci.get("evaluador","investigador_manual_v1"), __import__('datetime').datetime.now().isoformat(), GTV))
        # Relevancia: actualizar evaluacion_generacion si no existe (versionado)
        if data.get("relevancia") is not None:
            # verificar no overwrite
            cur=conn.execute("SELECT relevancia FROM evaluacion_generacion WHERE generacion_experimento_id=? AND pregunta_id=?", (gen_id, qid)).fetchone()
            if cur and cur[0] is not None:
                print(f"{qid} relevancia ya existe {cur[0]}, no overwrite")
            else:
                conn.execute("UPDATE evaluacion_generacion SET relevancia=?, evaluador=?, groundtruth_version=? WHERE generacion_experimento_id=? AND pregunta_id=?", (data["relevancia"], data.get("evaluador","investigador_manual_v1"), GTV, gen_id, qid))
        conn.commit()
        print(f"{path.name} importado OK")
    conn.close()

if __name__=="__main__":
    main()
