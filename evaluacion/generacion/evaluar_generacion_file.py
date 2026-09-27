#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_generacion_file.py — Generación sin tocar DB (evita corrupción por WAL concurrente).
Escribe JSON/CSV en /data/evaluacion, luego insertar con backend detenido.

Uso:
  docker compose exec backend python /data/evaluacion/generacion/evaluar_generacion_file.py
  # luego: docker compose stop backend && python evaluacion/generacion/insertar_generacion.py
"""
import json, sqlite3, datetime, hashlib, re, sys, time
from pathlib import Path
import urllib.request, urllib.error

EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent.parent.parent
DB_CANDIDATES = [PROJECT_ROOT / "registro_interacciones.db", Path("/data/registro_interacciones.db")]
API_CANDIDATES = ["http://localhost:8000/consulta", "http://backend:8000/consulta"]

for p in [PROJECT_ROOT / "backend", Path("/app")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import config

def find_db():
    for p in DB_CANDIDATES:
        if p.exists():
            return p
    return DB_CANDIDATES[0]

def find_api():
    for url in API_CANDIDATES:
        try:
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
        with urllib.request.urlopen(req, timeout=80) as resp:
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
    if not fuentes: return "invalid"
    for f in fuentes:
        if "·" not in f or not f.strip(): return "invalid"
        if len(f.split("·")) < 2: return "invalid"
    return "valid"

def citation_match(respuesta, fuentes):
    if not respuesta: return "invalid"
    has_encuadre = "Según el" in respuesta or "Según la" in respuesta
    if not fuentes:
        return "not_applicable" if not has_encuadre else "invalid"
    citas = re.findall(r"\[([^\]]+)\]", respuesta)
    if not citas:
        return "invalid" if has_encuadre else "not_applicable"
    src_docs = {f.split("·")[0].strip().lower() for f in fuentes}
    citas_norm = {c.strip().lower() for c in citas}
    if citas_norm & src_docs or any(any(doc in c or c in doc for doc in src_docs) for c in citas_norm):
        return "valid"
    return "invalid"

def main():
    db_path = find_db()
    api_url = find_api()
    print(f"DB (solo lectura): {db_path}")
    print(f"API: {api_url}")
    print(f"Config: {config.CORPUS_VERSION} {config.EMBEDDING_MODEL} {config.PROMPT_VERSION}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    banco = list(conn.execute("SELECT id, pregunta, puntos_esperados, evidencias_esperadas FROM banco_preguntas WHERE banco_version='v3_curado' AND activa=1 ORDER BY id").fetchall())
    conn.close()
    print(f"Banco v3_curado: {len(banco)} preguntas")

    ts = datetime.datetime.now().isoformat()
    exp_id = f"GEN_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(ts.encode()).hexdigest()[:6]}"
    print(f"Experimento generación: {exp_id}")

    resultados = []
    for qid, pregunta, puntos_j, ev_j in banco:
        print(f"\n[{qid}] {pregunta[:60]}...")
        resp, status = call_consulta(api_url, pregunta, sesion_id=f"eval_gen_{qid}")
        respuesta = resp.get("respuesta","") or ""
        fuentes = resp.get("fuentes", []) or []
        sv = source_validity(fuentes)
        cm = citation_match(respuesta, fuentes)
        resultados.append({
            "pregunta_id": qid,
            "pregunta": pregunta,
            "respuesta_generada": respuesta,
            "fuentes_generadas": fuentes,
            "puntos_esperados": json.loads(puntos_j) if puntos_j else [],
            "evidencias_esperadas": json.loads(ev_j) if ev_j else [],
            "source_validity": sv,
            "citation_match": cm,
            "status": status,
            "timestamp": datetime.datetime.now().isoformat()
        })
        print(f"  -> {len(respuesta)} chars, {len(fuentes)} fuentes, sv={sv}, cm={cm}, status={status}")
        time.sleep(0.6)

    # Guardar JSON y CSV sin tocar DB
    out_json = EVAL_DIR / f"generacion_{exp_id}.json"
    out_json.write_text(json.dumps({"experimento_id": exp_id, "fecha": ts, "config": {"corpus": config.CORPUS_VERSION, "emb": config.EMBEDDING_MODEL, "prompt": config.PROMPT_VERSION, "threshold": config.RAG_DISTANCE_THRESHOLD, "top_raw": config.RAG_TOP_K_RAW, "top_final": config.RAG_TOP_K_FINAL}, "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {out_json}")

    import csv
    out_csv = EVAL_DIR / f"generacion_{exp_id}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pregunta_id","source_validity","citation_match","len_respuesta","fuentes"])
        for r in resultados:
            w.writerow([r["pregunta_id"], r["source_validity"], r["citation_match"], len(r["respuesta_generada"]), json.dumps(r["fuentes_generadas"], ensure_ascii=False)])
    print(f"CSV: {out_csv}")
    print(f"Ahora ejecutar con backend detenido: python evaluacion/generacion/insertar_generacion.py {out_json.name}")

if __name__ == "__main__":
    main()
