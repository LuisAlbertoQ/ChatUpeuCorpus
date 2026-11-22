#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correr_17q_e2e.py — Banco técnico (17 Q, v3_curado) end-to-end contra /consulta.

Corre las 17 preguntas contra el chatbot en vivo (mismo endpoint que usa el
frontend), lee de `interacciones` los chunks que realmente recibió el LLM y
clasifica cada resultado. No modifica el pipeline ni los baselines congelados.

Clasificación por pregunta (acordada en OE1, 2026-11-20):
  OK_ARTICULO         M02 y el artículo esperado está entre los chunks del LLM
  OK_DOCUMENTO        M02, documento correcto, artículo distinto (o sin artículo esperado)
  OTRO_DOCUMENTO      M02 pero ningún chunk es del documento esperado
  NO_RECUPERO         M04 sin chunks bajo el umbral (retrieval_no_coverage)
  LLM_NO_RESPONDIO    M04/otro con chunks válidos (el LLM dijo "no hay información")
  OTRO                M03/M05/M06/error
Flags: recorte_700 (algún chunk > 700 chars, el LLM no vio su medio),
       respuesta_truncada (T03 añadió "(…)").

Uso (dentro del contenedor backend):
  docker exec oe5-backend python /data/evaluacion/comparacion_v2_v3/correr_17q_e2e.py --etiqueta V2
"""
import argparse
import csv
import datetime
import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR.parent / "retrieval"))
for p in [Path("/app"), EVAL_DIR.parent.parent / "backend"]:
    if p.exists():
        sys.path.insert(0, str(p))

import config  # noqa: E402
from evaluar_rag_v3 import clave_articulo, clave_documento  # noqa: E402

DB = Path("/data/registro_interacciones.db")
VECTOR = Path("/data/vector_store")
API = "http://localhost:8000/consulta"
MAX_CHARS_LLM = 700  # recorte vigente en rag_pipeline.py


def consultar(pregunta: str, sesion_id: str, timeout: int = 180) -> dict:
    body = json.dumps({"pregunta": pregunta, "sesion_id": sesion_id}).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fila_interaccion(conn, sesion_id: str) -> dict:
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT * FROM interacciones WHERE sesion_id=? ORDER BY id DESC LIMIT 1", (sesion_id,)
    ).fetchone()
    return dict(r) if r else {}


def _json(v):
    try:
        return json.loads(v) if v else []
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True, help="V2 / V3 / ... (va en sesion_id y en el nombre del archivo)")
    ap.add_argument("--banco", default="v3_curado",
                    help="banco_version: v3_curado (17 Q) o v31_no_answer (6 negativas, tabla banco_no_answer)")
    args = ap.parse_args()

    import chromadb
    from chromadb.config import Settings
    col = chromadb.PersistentClient(path=str(VECTOR), settings=Settings(anonymized_telemetry=False)) \
        .get_collection(config.CORPUS_VERSION)

    conn = sqlite3.connect(str(DB))
    tabla = "banco_no_answer" if args.banco == "v31_no_answer" else "banco_preguntas"
    banco = conn.execute(
        f"SELECT id, pregunta, documento_esperado, articulo_esperado FROM {tabla} "
        "WHERE banco_version=? AND activa=1 ORDER BY id", (args.banco,)
    ).fetchall()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"E2E_{args.etiqueta}_{stamp}"
    print(f"{run_id} | corpus={config.CORPUS_VERSION} emb={config.EMBEDDING_MODEL} "
          f"umbral={config.RAG_DISTANCE_THRESHOLD} top={config.RAG_TOP_K_RAW}/{config.RAG_TOP_K_FINAL} "
          f"max_palabras={config.MAX_PALABRAS_RESPUESTA} | {len(banco)} preguntas", flush=True)

    resultados = []
    for qid, pregunta, doc_esp, art_esp in banco:
        sesion_id = f"eval-{run_id}-{qid}"
        t0 = time.time()
        try:
            resp = consultar(pregunta, sesion_id)
            error = ""
        except Exception as exc:
            resp, error = {}, f"{type(exc).__name__}: {exc}"
        dt = round(time.time() - t0, 2)
        fila = fila_interaccion(conn, sesion_id)

        chunk_ids = _json(fila.get("retrieved_chunk_ids"))
        docs = _json(fila.get("retrieved_document_ids"))
        arts = _json(fila.get("retrieved_articles"))
        dists = _json(fila.get("retrieved_distances"))
        tipo = resp.get("tipo_mensaje") or fila.get("tipo_mensaje") or "ERROR"

        # longitud real de cada chunk enviado al LLM (para el flag de recorte)
        largos = []
        if chunk_ids:
            got = col.get(where={"chunk_id": {"$in": chunk_ids}}, include=["documents", "metadatas"])
            por_id = {m.get("chunk_id"): len(d or "") for d, m in zip(got["documents"], got["metadatas"])}
            largos = [por_id.get(c, 0) for c in chunk_ids]

        k_doc = clave_documento(doc_esp)
        k_art = clave_articulo(doc_esp, art_esp) if art_esp else None
        hit_doc = any(clave_documento(d) == k_doc for d in docs)
        pos_art = next((i + 1 for i, (d, a) in enumerate(zip(docs, arts))
                        if k_art and clave_articulo(d, a) == k_art), None)

        if tipo == "M02":
            clase = "OK_ARTICULO" if pos_art else ("OK_DOCUMENTO" if hit_doc else "OTRO_DOCUMENTO")
        elif tipo == "M04" and not chunk_ids:
            clase = "NO_RECUPERO"
        elif chunk_ids:
            clase = "LLM_NO_RESPONDIO"
        else:
            clase = "OTRO"

        respuesta = resp.get("respuesta", "")
        r = {
            "run_id": run_id, "id": qid, "pregunta": pregunta,
            "documento_esperado": doc_esp, "articulo_esperado": art_esp,
            "tipo_mensaje": tipo, "clase": clase,
            "hit_documento_top4": hit_doc, "pos_articulo_top4": pos_art,
            "num_chunks_llm": len(chunk_ids),
            # Desde la mejora 1 el LLM recibe chunks completos (salvo un primer chunk
            # mayor que RAG_CONTEXT_MAX_CHARS); antes se recortaba todo chunk > 700.
            "recorte_700": (any(l > MAX_CHARS_LLM for l in largos)
                            if not hasattr(config, "RAG_CONTEXT_MAX_CHARS") or getattr(config, "RAG_RECORTE_LEGACY_700", False)
                            else bool(largos) and largos[0] > config.RAG_CONTEXT_MAX_CHARS),
            "chars_chunks": largos,
            "respuesta_truncada": respuesta.rstrip().endswith("(…)"),
            "palabras_respuesta": len(respuesta.split()),
            "tiempo_s": resp.get("tiempo_respuesta", dt),
            "llm_ms": fila.get("llm_latency_ms"),
            "dist_min_pool": round(min(resp["debug_distancias"]), 4) if resp.get("debug_distancias") else None,
            "documentos_llm": docs, "articulos_llm": arts, "distancias_llm": dists,
            "failure_reason": fila.get("failure_reason"),
            "citation_validation": fila.get("citation_validation"),
            "fuentes": resp.get("fuentes", []), "respuesta": respuesta, "error": error,
        }
        resultados.append(r)
        print(f"  {qid} {tipo:4} {clase:17} art@{pos_art or '-'} doc={'S' if hit_doc else 'N'} "
              f"recorte={'S' if r['recorte_700'] else 'N'} {r['tiempo_s']}s", flush=True)

    out_json = EVAL_DIR / f"{run_id}.json"
    out_csv = EVAL_DIR / f"{run_id}.csv"
    meta = {
        "run_id": run_id, "fecha": datetime.datetime.now().isoformat(),
        "corpus_version": config.CORPUS_VERSION, "embedding_model": config.EMBEDDING_MODEL,
        "embedding_revision": getattr(config, "EMBEDDING_REVISION", None),
        "llm_model": config.OLLAMA_MODEL, "prompt_version": config.PROMPT_VERSION,
        "umbral": config.RAG_DISTANCE_THRESHOLD, "margen_fuera_dominio": config.MARGEN_FUERA_DOMINIO,
        "top_k_raw": config.RAG_TOP_K_RAW, "top_k_final": config.RAG_TOP_K_FINAL,
        "max_palabras": config.MAX_PALABRAS_RESPUESTA,
        **{k.lower(): getattr(config, k) for k in (
            "RAG_KEYWORD_BOOST", "RAG_CONTEXT_MAX_CHARS", "RAG_RECORTE_LEGACY_700", "OLLAMA_NUM_CTX",
            "OLLAMA_NUM_PREDICT", "OLLAMA_SEED", "TIMEOUT_RESPUESTA", "RAG_RERANKER", "RAG_RERANKER_MODEL",
            "RAG_CONTEXTO_ARTICULO", "RAG_DETECTAR_ABSTENCION") if hasattr(config, k)},
    }
    out_json.write_text(json.dumps({"meta": meta, "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    campos = [k for k in resultados[0] if k not in ("respuesta", "fuentes", "chars_chunks", "documentos_llm", "articulos_llm", "distancias_llm")]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(resultados)

    from collections import Counter
    c_tipo = Counter(r["tipo_mensaje"] for r in resultados)
    c_clase = Counter(r["clase"] for r in resultados)
    n = len(resultados)
    print("\n=== RESUMEN", run_id)
    print("tipo_mensaje:", dict(c_tipo))
    print("clase:", dict(c_clase))
    print(f"documento correcto en top4: {sum(r['hit_documento_top4'] for r in resultados)}/{n}")
    print(f"artículo correcto en top4: {sum(1 for r in resultados if r['pos_articulo_top4'])}/{sum(1 for r in resultados if r['articulo_esperado'])}")
    print(f"con recorte_700: {sum(r['recorte_700'] for r in resultados)}/{n} | truncadas: {sum(r['respuesta_truncada'] for r in resultados)}")
    print(f"tiempo promedio: {sum(r['tiempo_s'] for r in resultados) / n:.1f}s")
    print("JSON:", out_json)


if __name__ == "__main__":
    main()
