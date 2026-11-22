#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibrar_v3_bgem3.py — Calibración de variables RAG para corpus V3 + bge-m3.

Calibra con preguntas DISTINTAS al banco técnico de 17 Q (que queda para validar):
  positivas: banco OE1 (154, doc por prefijo) + pool 260 dominio sin semillas (183)
  negativas: banco OE1 negativas (8, cercanas al dominio) + pool 260 OOD sin semillas (34)

Replica la lógica de decisión de rag_pipeline.generar_respuesta (sin LLM):
  1. validadores previos (ambigua → M05, ética → M03, multi-intención → M05, keywords OOD → M03)
  2. query Top-K_raw → boost b por keyword en nombre de documento → orden por distancia ajustada
  3. M03 si dominio_kw es None y min(dist ajustada) > corte_ood (= umbral + margen)
  4. hasta 4 chunks con dist ajustada < umbral; si ninguno → M04; si no → M02

Variables: boost b, K_raw, umbral T, corte_ood C. Regla de selección (fijada antes de mirar):
  a) b y K_raw: máximo acierto de documento en el Top-4 de las positivas (T sin efecto, T=1).
  b) T: máxima abstención en negativas (prioridad H5: responder una pregunta fuera de dominio
     es peor que una falsa abstención); a igualdad, la menor falsa M04 en positivas.
  c) C no cambia SI se abstiene, solo el mensaje (M03 "fuera de alcance" vs M04 "no encontré"):
     el primer corte por encima de la distancia Top-1 máxima de las positivas (margen de
     seguridad: una pregunta del dominio sin keywords nunca debe recibir "fuera de alcance").
     Para H5, M03 y M04 cuentan igual como abstención correcta.

Uso:
  docker exec oe5-backend python /data/evaluacion/retrieval/calibrar_v3_bgem3.py
"""
import csv
import datetime
import json
import re
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, "/app")

import config  # noqa: E402
import rag_pipeline as rp  # noqa: E402  (solo validadores y stopwords; no se inicializa)
from evaluar_rag_v3 import clave_articulo, normalizar_documento  # noqa: E402

# Copia de oe1_arquitectura_corpus/corpus_upeu/config/banco_preguntas.csv (2026-11-21, sin revisión humana)
OE1_BANCO = Path("/data/evaluacion/banco/banco_oe1_162.csv")
POOL = Path("/data/evaluacion/banco/pool_260_verificacion.json")
K_FINAL = config.RAG_TOP_K_FINAL
BOOSTS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.07]
KRAWS = [15, 30, 50]
UMBRALES = [round(0.25 + 0.01 * i, 2) for i in range(31)]   # 0.25 … 0.55
CORTES = [round(0.30 + 0.01 * i, 2) for i in range(36)]     # 0.30 … 0.65
STOP = rp._STOPWORDS_ES


def cargar(oe1_path: Path, docs_corpus: list[str]):
    nd = {normalizar_documento(d): d for d in docs_corpus}
    pos, neg, sin_mapa = [], [], []
    with open(oe1_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["tipo"] == "negativa":
                neg.append({"id": f"OE1_{r['id']}", "texto": r["pregunta"], "fuente": "OE1"})
                continue
            e = normalizar_documento(r["documento_esperado"])
            cands = [d for k, d in nd.items() if k == e] or [d for k, d in nd.items() if k.startswith(e)]
            if len(cands) != 1:
                sin_mapa.append((r["id"], r["documento_esperado"], len(cands)))
                continue
            pos.append({"id": f"OE1_{r['id']}", "texto": r["pregunta"], "doc": cands[0],
                        "art": r["articulo_esperado"], "fuente": "OE1"})
    for i in json.loads(POOL.read_text(encoding="utf-8")):
        if i["estado"] == "SEMILLA_CURADA":
            continue  # semillas = banco de validación (17 Q + N01-N06)
        if i["bloque"] == "dominio":
            pos.append({"id": i["pregunta_id"], "texto": i["texto"], "doc": i["documento_esperado"],
                        "art": "", "fuente": "POOL"})
        elif i["bloque"] == "ood":
            neg.append({"id": i["pregunta_id"], "texto": i["texto"], "fuente": "POOL"})
    return pos, neg, sin_mapa


def prefiltro(texto: str):
    if rp._pregunta_es_ambigua(texto):
        return "M05", None
    if rp._es_etica_sensible(texto):
        return "M03", None
    if rp._es_multi_intencion(texto):
        return "M05", None
    kw = rp._es_fuera_dominio_por_keywords(texto)
    if kw is True:
        return "M03", kw
    return None, kw


def keywords(texto: str):
    return [w.lower() for w in re.findall(r"\b[a-záéíóúñü]{4,}\b", texto.lower()) if w.lower() not in STOP]


def ranking(q, b, kraw):
    """Pool Top-kraw ordenado por distancia ajustada → lista de (dist_aj, meta)."""
    kws = q["kws"]
    items = []
    for d, m in zip(q["dists"][:kraw], q["metas"][:kraw]):
        dn = (m.get("documento") or "").lower()
        matches = sum(1 for k in kws if k in dn) if kws else 0
        items.append((max(0.0, d - matches * b), m))
    items.sort(key=lambda x: x[0])
    return items


def decidir(q, b, kraw, T, C):
    if q["pre"]:
        return q["pre"], []
    rk = ranking(q, b, kraw)
    if q["kw"] is None and rk and rk[0][0] > C:
        return "M03", []
    top = [m for d, m in rk if d < T][:K_FINAL]
    return ("M02", top) if top else ("M04", [])


def main():
    import chromadb
    from sentence_transformers import SentenceTransformer

    col = chromadb.PersistentClient(path="/data/vector_store").get_collection(config.CORPUS_VERSION)
    metas_all = col.get(include=["metadatas"])["metadatas"]
    docs_corpus = sorted({m["documento"] for m in metas_all})
    pos, neg, sin_mapa = cargar(OE1_BANCO, docs_corpus)
    print(f"{config.CORPUS_VERSION} | {config.EMBEDDING_MODEL} | positivas={len(pos)} negativas={len(neg)} "
          f"| OE1 sin mapear={len(sin_mapa)} {sin_mapa}", flush=True)

    model = SentenceTransformer(config.EMBEDDING_MODEL, revision=config.EMBEDDING_REVISION)
    todas = pos + neg
    embs = model.encode([q["texto"] for q in todas], batch_size=16).tolist()
    for q, e in zip(todas, embs):
        q["pre"], q["kw"] = prefiltro(q["texto"])
        q["kws"] = keywords(q["texto"])
        r = col.query(query_embeddings=[e], n_results=max(KRAWS))
        q["dists"], q["metas"] = r["distances"][0], r["metadatas"][0]

    def m_pos(b, kraw, T, C):
        hit_doc = hit_art = n_art = m04 = m03 = 0
        for q in pos:
            tipo, top = decidir(q, b, kraw, T, C)
            m04 += tipo == "M04"
            m03 += tipo in ("M03", "M05")
            k = normalizar_documento(q["doc"])
            hit_doc += any(normalizar_documento(m["documento"]) == k for m in top)
            if q["art"]:
                n_art += 1
                ka = clave_articulo(q["doc"], q["art"])
                hit_art += any(clave_articulo(m["documento"], m.get("articulo", "")) == ka for m in top)
        n = len(pos)
        return {"hit_doc4": hit_doc / n, "hit_art4": hit_art / max(n_art, 1),
                "falsa_m04": m04 / n, "falsa_m03": m03 / n, "falsa_total": (m04 + m03) / n}

    def m_neg(b, kraw, T, C):
        tipos = [decidir(q, b, kraw, T, C)[0] for q in neg]
        return {"abst_neg": sum(t != "M02" for t in tipos) / len(neg),
                "neg_m03": sum(t == "M03" for t in tipos) / len(neg)}

    def pos_m03_emb(b, kraw, T, C):
        """Positivas enviadas a M03 por el corte de embeddings (no por validadores previos)."""
        return sum(1 for q in pos if not q["pre"] and decidir(q, b, kraw, T, C)[0] == "M03")

    filas = []
    # a) boost y K_raw (sin filtros: T=1, C=1)
    print("\n[a] boost × K_raw (T=1, C=1)")
    mejor_a = None
    for b in BOOSTS:
        for kraw in KRAWS:
            mp = m_pos(b, kraw, 1.0, 1.0)
            filas.append({"etapa": "a", "boost": b, "k_raw": kraw, "umbral": 1.0, "corte_ood": 1.0, **mp, **m_neg(b, kraw, 1.0, 1.0)})
            print(f"  b={b:.2f} K={kraw:2} hit_doc4={mp['hit_doc4']:.3f} hit_art4={mp['hit_art4']:.3f}")
            key = (round(mp["hit_doc4"], 4), round(mp["hit_art4"], 4), -b, -kraw)
            if mejor_a is None or key > mejor_a[0]:
                mejor_a = (key, b, kraw)
    _, B, K = mejor_a
    print(f"  → boost={B} K_raw={K}")

    # distribución de distancias Top-1 (ajustadas) para el informe
    def top1(q):
        rk = ranking(q, B, K)
        return rk[0][0] if rk else None
    d_pos = sorted(top1(q) for q in pos if not q["pre"])
    d_neg = sorted(top1(q) for q in neg if not q["pre"] and q["kw"] is None)
    pct = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
    dist = {"pos_p50": pct(d_pos, .5), "pos_p90": pct(d_pos, .9), "pos_p95": pct(d_pos, .95), "pos_max": d_pos[-1],
            "neg_min": d_neg[0] if d_neg else None, "neg_p10": pct(d_neg, .1) if d_neg else None,
            "neg_p50": pct(d_neg, .5) if d_neg else None, "n_neg_embeddings": len(d_neg),
            "n_neg_prefiltro": sum(1 for q in neg if q["pre"])}
    print("  distancias Top-1:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in dist.items()})

    # b) umbral T (C=1)
    print("\n[b] umbral (C=1)")
    cand_b = []
    for T in UMBRALES:
        mp, mn = m_pos(B, K, T, 1.0), m_neg(B, K, T, 1.0)
        filas.append({"etapa": "b", "boost": B, "k_raw": K, "umbral": T, "corte_ood": 1.0, **mp, **mn})
        print(f"  T={T:.2f} hit_doc4={mp['hit_doc4']:.3f} falsa_m04={mp['falsa_m04']:.3f} abst_neg={mn['abst_neg']:.3f}")
        cand_b.append((mn["abst_neg"], -mp["falsa_m04"], -T, T))
    T_sel = max(cand_b)[3]
    print(f"  → umbral={T_sel}")

    # c) corte fuera de dominio C (con T elegido)
    print("\n[c] corte_ood (T elegido)")
    cand_c = []
    for C in CORTES:
        if C < T_sel:
            continue
        mp, mn = m_pos(B, K, T_sel, C), m_neg(B, K, T_sel, C)
        pm = pos_m03_emb(B, K, T_sel, C)
        filas.append({"etapa": "c", "boost": B, "k_raw": K, "umbral": T_sel, "corte_ood": C, **mp, **mn})
        print(f"  C={C:.2f} neg_M03={mn['neg_m03']:.3f} abst_neg={mn['abst_neg']:.3f} pos_M03_emb={pm} hit_doc4={mp['hit_doc4']:.3f}")
        if pm == 0 and C > dist["pos_max"]:
            cand_c.append(C)
    C_sel = min(cand_c) if cand_c else T_sel + 0.10
    margen = round(C_sel - T_sel, 2)

    base = (m_pos(0.07, 15, 0.40, 0.50), m_neg(0.07, 15, 0.40, 0.50))
    sel = (m_pos(B, K, T_sel, C_sel), m_neg(B, K, T_sel, C_sel))
    resumen = {
        "fecha": datetime.datetime.now().isoformat(), "corpus": config.CORPUS_VERSION,
        "modelo": config.EMBEDDING_MODEL, "n_pos": len(pos), "n_neg": len(neg), "oe1_sin_mapear": sin_mapa,
        "seleccion": {"boost": B, "k_raw": K, "umbral": T_sel, "corte_ood": C_sel, "margen": margen},
        "distancias_top1": dist,
        "actual_0.40_0.10_b0.07_k15": {**base[0], **base[1]},
        "calibrado": {**sel[0], **sel[1]},
    }
    print("\n=== SELECCIÓN", json.dumps(resumen["seleccion"]))
    print("actual   :", {k: round(v, 3) for k, v in resumen["actual_0.40_0.10_b0.07_k15"].items()})
    print("calibrado:", {k: round(v, 3) for k, v in resumen["calibrado"].items()})

    out = EVAL_DIR / "calibracion_v3_bgem3"
    out.mkdir(exist_ok=True)
    (out / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "grid.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print("Salidas:", out)


if __name__ == "__main__":
    main()
