#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insertar_generacion.py — Inserta JSON de generación en DB con backend detenido (evita lock).
Uso: python evaluacion/generacion/insertar_generacion.py evaluacion/generacion/generacion_GEN_*.json
"""
import json, sqlite3, sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Uso: python insertar_generacion.py <json>")
    sys.exit(1)

json_path = Path(sys.argv[1])
if not json_path.exists():
    # probar en EVAL_DIR
    json_path = Path(__file__).parent / Path(sys.argv[1]).name
data = json.loads(json_path.read_text(encoding="utf-8"))
exp_id = data["experimento_id"]
fecha = data["fecha"]
cfg = data["config"]
resultados = data["resultados"]

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_CANDIDATES = [PROJECT_ROOT / "registro_interacciones.db", Path("/data/registro_interacciones.db")]
db_path = next((p for p in DB_CANDIDATES if p.exists()), DB_CANDIDATES[0])
print(f"DB: {db_path} exp {exp_id}")

# asegurar esquema
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
import logger
orig = logger.DB_PATH
logger.DB_PATH = str(db_path)
logger.inicializar_bd()
logger.DB_PATH = orig

conn = sqlite3.connect(str(db_path))
conn.execute("PRAGMA foreign_keys = ON")
# Insert experimento
from pathlib import Path as P
import config as cfg_mod
# Reconstruir config desde JSON
conn.execute("INSERT INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version, descripcion, estado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (exp_id, fecha, cfg["corpus"], cfg["emb"], "qwen2.5:7b", cfg["top_raw"], cfg["top_final"], cfg["threshold"], "heuristic_keyword_boost", "1.0", cfg["prompt"], "Evaluación generación v3_curado 17Q", "completado"))
for r in resultados:
    conn.execute("INSERT INTO evaluacion_generacion (pregunta_id, experimento_id, respuesta_generada, respuesta_esperada, relevancia, faithfulness, completitud, citation_precision, citation_correctness, respuesta_valida, evaluador, timestamp, abstention_correctness, puntos_esperados, evidencias_esperadas, fuentes_generadas, source_validity, citation_match, citation_correctness_humana) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r["pregunta_id"], exp_id, r["respuesta_generada"], "", None, None, None, None, None, None, "auto", r["timestamp"], None, json.dumps(r["puntos_esperados"], ensure_ascii=False), json.dumps(r["evidencias_esperadas"], ensure_ascii=False), json.dumps(r["fuentes_generadas"], ensure_ascii=False), r["source_validity"], r["citation_match"], None))
conn.commit()
print(f"Insertadas {len(resultados)} filas")
for row in conn.execute("SELECT pregunta_id, source_validity, citation_match, length(respuesta_generada) FROM evaluacion_generacion WHERE experimento_id=?", (exp_id,)):
    print(row)
conn.close()
print("OK")
