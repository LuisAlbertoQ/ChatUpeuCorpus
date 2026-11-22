#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_reranker.py — Mejora 2: ¿el cross-encoder ordena mejor que el boost por keyword?

Compara, sobre los MISMOS candidatos semánticos (Top-K de bge-m3, filtrados por el umbral
calibrado), dos formas de elegir los 4 chunks que van al LLM:
  boost   : distancia - 0.02 × keywords en el nombre del documento (producción actual)
  rerank  : puntaje de BAAI/bge-reranker-v2-m3 (pregunta, texto del chunk)
Bancos: 17 Q (v3_curado, documento + artículo) y 325 positivas de calibración (documento;
artículo solo en las del OE1 que lo traen). Mide también la latencia en CPU.

Uso:
  docker exec oe5-backend python /data/evaluacion/retrieval/evaluar_reranker.py
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, "/app")

import config  # noqa: E402
from calibrar_v3_bgem3 import OE1_BANCO, cargar, keywords, prefiltro  # noqa: E402
from evaluar_rag_v3 import clave_articulo, normalizar_documento  # noqa: E402

RERANKER = "BAAI/bge-reranker-v2-m3"
RERANKER_REV = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
KS = [15, 20, 30]
T = config.RAG_DISTANCE_THRESHOLD
B = config.RAG_KEYWORD_BOOST
MAX_CHARS = 2000  # igual que OE1 (09_evaluacion.py)


def encabezado(m: dict) -> str:
    doc = m.get("nombre_documento") or (m.get("documento") or "").removesuffix(".pdf")
    art = m.get("articulo") or ""
    return (f"{doc} | {art}" if art else doc) + "\n"


def main():
    import chromadb
    from sentence_transformers import CrossEncoder, SentenceTransformer

    col = chromadb.PersistentClient(path="/data/vector_store").get_collection(config.CORPUS_VERSION)
    docs_corpus = sorted({m["documento"] for m in col.get(include=["metadatas"])["metadatas"]})
    pos_cal, _, _ = cargar(OE1_BANCO, docs_corpus)
    conn = sqlite3.connect("/data/registro_interacciones.db")
    q17 = [{"id": i, "texto": p, "doc": d, "art": a or "", "fuente": "17Q"} for i, p, d, a in conn.execute(
        "SELECT id, pregunta, documento_esperado, articulo_esperado FROM banco_preguntas "
        "WHERE banco_version='v3_curado' AND activa=1 ORDER BY id")]

    # La calidad no depende del dispositivo; la GPU solo acelera la evaluación.
    # En CPU (backend) se midió ~16 s por pregunta con 30 candidatos.
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    kw = {"model_kwargs": {"torch_dtype": torch.float16}} if dev == "cuda" else {}
    print(f"dispositivo: {dev}", flush=True)
    emb = SentenceTransformer(config.EMBEDDING_MODEL, revision=config.EMBEDDING_REVISION, device=dev)
    ce = CrossEncoder(RERANKER, revision=RERANKER_REV, max_length=512, device=dev, **kw)

    todas = q17 + pos_cal
    vecs = emb.encode([q["texto"] for q in todas], batch_size=16).tolist()
    lat = {k: [] for k in KS}
    print(f"preguntas: 17Q={len(q17)} calibracion={len(pos_cal)}", flush=True)
    for n, (q, v) in enumerate(zip(todas, vecs), 1):
        if n % 25 == 0:
            print(f"  progreso {n}/{len(todas)}  latencia media K=30: {sum(lat[30]) / len(lat[30]):.2f}s", flush=True)
        q["pre"], q["kw"] = prefiltro(q["texto"])
        r = col.query(query_embeddings=[v], n_results=max(KS), include=["documents", "metadatas", "distances"])
        q["cands"] = list(zip(r["documents"][0], r["metadatas"][0], r["distances"][0]))
        # puntajes del cross-encoder para el pool más grande (los menores son prefijos)
        t0 = time.perf_counter()
        q["scores"] = ce.predict([(q["texto"], d[:MAX_CHARS]) for d, _, _ in q["cands"]], batch_size=16).tolist()
        dt = time.perf_counter() - t0
        lat[30].append(dt)
        # variante con encabezado: el chunk guardado no trae el nombre del documento
        # (el breadcrumb del OE1 solo se usó para el embedding)
        q["scores_ctx"] = ce.predict([(q["texto"], encabezado(m) + d[:MAX_CHARS]) for d, m, _ in q["cands"]],
                                     batch_size=16).tolist()
        if q["fuente"] == "17Q":  # latencia real para K=15/20 en una muestra
            for k in (15, 20):
                t0 = time.perf_counter()
                ce.predict([(q["texto"], d[:MAX_CHARS]) for d, _, _ in q["cands"][:k]], batch_size=16)
                lat[k].append(time.perf_counter() - t0)

    def top4(q, modo, k):
        """Mismo conjunto de candidatos en todos los modos: los que pasan el umbral con la
        distancia ajustada por boost (como en producción); solo cambia el orden."""
        cands = [(i, d, m, dist) for i, (d, m, dist) in enumerate(q["cands"][:k])]
        kws = keywords(q["texto"])
        aj = [(max(0.0, dist - B * sum(1 for w in kws if w in (m.get("documento") or "").lower())), i, m)
              for i, d, m, dist in cands]
        validos = [(a, i, m) for a, i, m in aj if a < T]
        if modo == "boost":
            orden = sorted(validos, key=lambda x: x[0])
        else:
            s = q["scores"] if modo == "rerank" else q["scores_ctx"]
            orden = sorted(validos, key=lambda x: -s[x[1]])
        return [m for _, _, m in orden[:4]]

    def metricas(banco, modo, k):
        hd = ha = na = 0
        rr = 0.0
        for q in banco:
            if q["pre"]:
                continue
            top = top4(q, modo, k)
            kd = normalizar_documento(q["doc"])
            hd += any(normalizar_documento(m["documento"]) == kd for m in top)
            if q["art"]:
                na += 1
                ka = clave_articulo(q["doc"], q["art"])
                pos = next((j + 1 for j, m in enumerate(top) if clave_articulo(m["documento"], m.get("articulo", "")) == ka), None)
                ha += bool(pos)
                rr += 1 / pos if pos else 0
        n = sum(1 for q in banco if not q["pre"])
        return {"hit_doc4": round(hd / n, 3), "hit_art4": round(ha / max(na, 1), 3), "mrr_art4": round(rr / max(na, 1), 3), "n": n, "n_art": na}

    res = {"reranker": RERANKER, "revision": RERANKER_REV, "umbral": T, "boost": B, "dispositivo": dev,
           "nota_latencia": "medida en el dispositivo indicado; CPU del backend ~16 s con K=30 (2026-11-21)",
           "resultados": [],
           "latencia_cpu_s": {k: {"media": round(sum(v) / len(v), 2), "max": round(max(v), 2)} for k, v in lat.items() if v}}
    for nombre, banco in (("17Q", q17), ("calibracion_325", pos_cal)):
        for k in KS:
            for modo in ("boost", "rerank", "rerank_ctx"):
                fila = {"banco": nombre, "k_candidatos": k, "modo": modo, **metricas(banco, modo, k)}
                res["resultados"].append(fila)
                print(f"{nombre:16} K={k:2} {modo:6} {fila}")
    print("latencia CPU (s):", res["latencia_cpu_s"])

    # detalle 17 Q (K=15): qué cambia por pregunta
    print("\nDetalle 17 Q, K=15 (artículo esperado en top-4: boost → rerank_ctx)")
    for q in q17:
        tb, tr = top4(q, "boost", 15), top4(q, "rerank_ctx", 15)
        ka = clave_articulo(q["doc"], q["art"]) if q["art"] else None
        kd = normalizar_documento(q["doc"])
        f = lambda top: ("A" if ka and any(clave_articulo(m["documento"], m.get("articulo", "")) == ka for m in top)  # noqa: E731
                         else "D" if any(normalizar_documento(m["documento"]) == kd for m in top) else "-")
        print(f"  {q['id']} {f(tb)} → {f(tr)}   rerank top1: {tr[0]['documento'][:40] if tr else '-'} {tr[0].get('articulo', '') if tr else ''}")
        res.setdefault("detalle_17q", []).append({"id": q["id"], "boost": f(tb), "rerank_ctx": f(tr)})

    out = EVAL_DIR / "reranker_v3_bgem3.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Salida:", out)


if __name__ == "__main__":
    main()
