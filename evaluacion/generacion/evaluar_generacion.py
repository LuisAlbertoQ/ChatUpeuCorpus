#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_generacion.py — Evaluación OFFLINE de generación (Parte 3, Fase 3).

Para cada Q en banco v3_curado:
  - llama POST /consulta (Qwen v2-adaptativo)
  - captura respuesta, fuentes, debug_distancias, contexto
  - calcula source_validity y citation_match determinísticos (sin LLM)
  - persiste en evaluacion_generacion + experimentos_rag

Uso:
  python evaluacion/generacion/evaluar_generacion.py
  docker compose run --rm backend python /data/evaluacion/generacion/evaluar_generacion.py
"""
import json, sqlite3, datetime, hashlib, re, sys, time
from pathlib import Path
import urllib.request, urllib.error

EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent.parent.parent
DB_CANDIDATES = [PROJECT_ROOT / "registro_interacciones.db", Path("/data/registro_interacciones.db")]
API_CANDIDATES = ["http://localhost:8000/consulta", "http://backend:8000/consulta", "http://127.0.0.1:8000/consulta"]

for p in [PROJECT_ROOT / "backend", Path("/app")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import config  # noqa: E402

def find_db():
    for p in DB_CANDIDATES:
        if p.exists():
            return p
    return DB_CANDIDATES[0]

def find_api():
    # probe quickly
    import socket
    for url in API_CANDIDATES:
        try:
            # quick HEAD via GET /salud
            base = url.replace("/consulta","/salud")
            with urllib.request.urlopen(base, timeout=2) as r:
                if r.status == 200:
                    return url
        except Exception:
            continue
    return API_CANDIDATES[0]

def call_consulta(api_url, pregunta, sesion_id="eval_gen"):
    payload = json.dumps({"pregunta": pregunta, "sesion_id": sesion_id}).encode("utf-8")
    req = urllib.request.Request(api_url, data=payload, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        try:
            return json.loads(body), e.code
        except:
            return {"respuesta": "", "fuentes": [], "error": body}, e.code
    except Exception as e:
        return {"respuesta": "", "fuentes": [], "error": str(e)}, 0

def source_validity(fuentes):
    if not fuentes:
        return "invalid"
    for f in fuentes:
        if "·" not in f or not f.strip():
            return "invalid"
        # debe tener al menos doc y artículo/categoría
        if len(f.split("·")) < 2:
            return "invalid"
    return "valid"

def citation_match(respuesta, fuentes):
    if not respuesta:
        return "invalid"
    has_encuadre = "Según el" in respuesta or "Según la" in respuesta
    if not fuentes:
        return "not_applicable" if not has_encuadre else "invalid"
    # extraer citas [Documento]
    citas = re.findall(r"\[([^\]]+)\]", respuesta)
    if not citas:
        return "invalid" if has_encuadre else "not_applicable"
    # normalizar fuentes esperadas vs citas
    src_docs = set()
    for f in fuentes:
        # fuente formato "Documento · Artículo · ..."
        doc = f.split("·")[0].strip().lower()
        src_docs.add(doc)
    citas_norm = {c.strip().lower() for c in citas}
    # si al menos una cita coincide con un doc de fuente → valid
    if citas_norm & src_docs or any(any(doc in c or c in doc for doc in src_docs) for c in citas_norm):
        return "valid"
    return "invalid"

def main():
    db_path = find_db()
    api_url = find_api()
    print(f"DB: {db_path} (existe={db_path.exists()})")
    print(f"API: {api_url}")
    print(f"Config: {config.CORPUS_VERSION} {config.EMBEDDING_MODEL} {config.PROMPT_VERSION}")

    # asegurar esquema
    import logger
    orig = logger.DB_PATH
    logger.DB_PATH = str(db_path)
    logger.inicializar_bd()
    logger.DB_PATH = orig

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")

    # crear experimento generación (con reintento por lock)
    ts = datetime.datetime.now().isoformat()
    exp_id = f"GEN_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(ts.encode()).hexdigest()[:6]}"
    print(f"Experimento generación: {exp_id}")
    for attempt in range(5):
        try:
            conn.execute(
                "INSERT INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version, descripcion, estado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (exp_id, ts, config.CORPUS_VERSION, config.EMBEDDING_MODEL, config.OLLAMA_MODEL, config.RAG_TOP_K_RAW, config.RAG_TOP_K_FINAL, config.RAG_DISTANCE_THRESHOLD, config.RANKING_METHOD, config.RANKING_VERSION, config.PROMPT_VERSION, "Evaluación generación v3_curado 17Q", "completado"),
            )
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(1.5 * (attempt+1))
                continue
            raise

    banco = list(conn.execute("SELECT id, pregunta, puntos_esperados, evidencias_esperadas FROM banco_preguntas WHERE banco_version='v3_curado' AND activa=1 ORDER BY id").fetchall())
    print(f"Banco v3_curado: {len(banco)} preguntas")
    if len(banco) != 17:
        print(f"WARN: esperado 17, hallado {len(banco)}", file=sys.stderr)

    inserted = 0
    for qid, pregunta, puntos_j, ev_j in banco:
        print(f"\n[{qid}] {pregunta[:60]}...")
        resp, status = call_consulta(api_url, pregunta, sesion_id=f"eval_gen_{qid}")
        respuesta = resp.get("respuesta","") or resp.get("reply","") or ""
        fuentes = resp.get("fuentes", []) or []
        # snapshot ground truth
        puntos_snapshot = puntos_j
        evidencias_snapshot = ev_j
        sv = source_validity(fuentes)
        cm = citation_match(respuesta, fuentes)
        # abstention: si respuesta es de abstención (M03/M05) → relevancia 0? Dejar NULL y evaluar manual
        now = datetime.datetime.now().isoformat()
        # reintento por busy
        for attempt in range(5):
            try:
                conn.execute(
                    "INSERT INTO evaluacion_generacion (pregunta_id, experimento_id, respuesta_generada, respuesta_esperada, relevancia, faithfulness, completitud, citation_precision, citation_correctness, respuesta_valida, evaluador, timestamp, abstention_correctness, puntos_esperados, evidencias_esperadas, fuentes_generadas, source_validity, citation_match, citation_correctness_humana) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (qid, exp_id, respuesta, "", None, None, None, None, None, None, "auto", now, None, puntos_snapshot, evidencias_snapshot, json.dumps(fuentes, ensure_ascii=False), sv, cm, None),
                )
                conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < 4:
                    time.sleep(1.5 * (attempt+1))
                    continue
                raise
        inserted += 1
        print(f"  -> {len(respuesta)} chars, {len(fuentes)} fuentes, sv={sv}, cm={cm}, status={status}")
        # rate limit to avoid Ollama overload
        time.sleep(0.8)
    print(f"\nInsertadas {inserted} filas en evaluacion_generacion exp {exp_id}")
    # resumen
    for row in conn.execute("SELECT pregunta_id, source_validity, citation_match, length(respuesta_generada) FROM evaluacion_generacion WHERE experimento_id=?", (exp_id,)):
        print(row)
    # export CSV
    import csv
    csv_path = EVAL_DIR / f"generacion_{exp_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pregunta_id","source_validity","citation_match","len_respuesta","fuentes"])
        for row in conn.execute("SELECT pregunta_id, source_validity, citation_match, length(respuesta_generada), fuentes_generadas FROM evaluacion_generacion WHERE experimento_id=?", (exp_id,)):
            w.writerow(row)
    print(f"CSV: {csv_path}")
    conn.close()

if __name__ == "__main__":
    main()
