# -*- coding: utf-8 -*-
"""
Harness de calibración de umbrales RAG (Tier 3, ítem ②).

Grid search reproducible: UMBRAL_DISTANCIA_COSENO × TOP_K_FRAGMENTOS
sobre el banco `preguntas_comparacion.json` (17 preguntas con documento
y artículo esperados).

Métricas por combinación:
  - cobertura_m02: % preguntas cuyo top-1 (tras filtro) pasa el umbral
  - acierto_doc:   % preguntas cuyo top-1 es del documento esperado
  - acierto_cat:   % preguntas cuyo top-1 es de la categoría objetivo
  - chunks_validos_prom: nº medio de chunks bajo el umbral
  - latencia_ms: tiempo medio embedding+query

Uso (dentro del contenedor backend):
    docker compose run --rm backend python /data/evaluacion/calibrar_umbral.py

Salidas:
    evaluacion/resultados_calibracion.csv
    evaluacion/calibracion_resumen.md
"""

import json
import re
import time
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# --- Configuración del grid ---------------------------------------------------
UMBRALES = [0.35, 0.36, 0.37, 0.38, 0.39, 0.40, 0.41, 0.42, 0.43, 0.44, 0.45]
TOPKS = [3, 4, 5]

# --- Rutas (dentro del contenedor) ---------------------------------------------
VECTOR_STORE = "/data/vector_store"
COLECCION = "corpus_upeu"
BANCO = Path("/data/evaluacion/preguntas_comparacion.json")
OUT_CSV = Path("/data/evaluacion/resultados_calibracion.csv")
OUT_MD = Path("/data/evaluacion/calibracion_resumen.md")

MODELO = "paraphrase-multilingual-mpnet-base-v2"
BOOST_KEYWORD = 0.07
TOP_K_RAW = max(max(TOPKS) * 3, 15)

# Stopwords idénticas a rag_pipeline._STOPWORDS_ES
_STOPWORDS_ES = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "u", "e", "que", "qué", "cual", "cuál", "como", "cómo", "donde",
    "dónde", "cuando", "cuándo", "quien", "quién", "por", "para", "con", "sin",
    "a", "en", "es", "son", "se", "su", "sus", "le", "les", "lo", "me", "te",
    "nos", "os", "mi", "ti", "si", "no", "ya", "ha", "han", "he", "hay",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel",
    "del", "más", "mas", "menos", "sobre", "entre", "hasta", "desde", "ante",
})

_RE_PALABRA = re.compile(r"\b[a-záéíóúñü]{4,}\b", re.IGNORECASE)


def keywords_query(pregunta):
    """Keywords no-stopword de la pregunta (igual que rag_pipeline)."""
    return [
        w.lower()
        for w in _RE_PALABRA.findall(pregunta.lower())
        if w.lower() not in _STOPWORDS_ES
    ]


def main():
    print("=" * 70)
    print("HARNESS DE CALIBRACIÓN RAG - oe5_chatbot_upeu")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Recursos
    # ------------------------------------------------------------------
    print(f"[1/5] Cargando modelo {MODELO}...")
    model = SentenceTransformer(MODELO)

    print(f"[2/5] Conectando a ChromaDB ({VECTOR_STORE})...")
    client = chromadb.PersistentClient(path=VECTOR_STORE)
    collection = client.get_collection(COLECCION)
    n_chunks = collection.count()
    print(f"      Colección '{COLECCION}': {n_chunks} chunks")

    # ------------------------------------------------------------------
    # 2. Banco
    # ------------------------------------------------------------------
    print(f"[3/5] Cargando banco {BANCO.name}...")
    banco = json.loads(BANCO.read_text(encoding="utf-8"))
    print(f"      {len(banco)} preguntas")

    # ------------------------------------------------------------------
    # 3. Retrieval base por pregunta (UNA vez; reutilizable en todo el grid)
    # ------------------------------------------------------------------
    print("[4/5] Retrieval base por pregunta...")
    base = []
    t0 = time.time()

    for item in banco:
        pregunta = item["pregunta"]
        inicio = time.time()

        emb = model.encode([pregunta], normalize_embeddings=True)[0].tolist()
        res = collection.query(query_embeddings=[emb], n_results=TOP_K_RAW)
        lat_ms = (time.time() - inicio) * 1000

        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = list(res["distances"][0])

        # Re-ranking con boost por keyword (igual que producción)
        kws = keywords_query(pregunta)
        if kws:
            boosted = []
            for d, m in zip(dists, metas):
                doc_norm = (m.get("documento", "") or "").lower()
                matches = sum(1 for kw in kws if kw in doc_norm)
                boosted.append(max(0.0, d - matches * BOOST_KEYWORD))
            orden = sorted(range(len(dists)), key=lambda i: boosted[i])
        else:
            orden = sorted(range(len(dists)), key=lambda i: dists[i])

        base.append({
            "item": item,
            "metas": [metas[i] for i in orden],
            "dists": [dists[i] for i in orden],
            "lat_ms": lat_ms,
        })

    print(f"      Completado en {time.time()-t0:.1f}s "
          f"(latencia media {sum(b['lat_ms'] for b in base)/len(base):.0f} ms)")

    # ------------------------------------------------------------------
    # 4. Grid search (sin LLM: solo recuperación)
    # ------------------------------------------------------------------
    print(f"[5/5] Grid: {len(UMBRALES)} umbrales x {len(TOPKS)} top_k = "
          f"{len(UMBRALES)*len(TOPKS)} combinaciones")

    filas = []
    for umbral in UMBRALES:
        for topk in TOPKS:
            m02 = doc_ok = cat_ok = 0
            chunks_val_total = 0

            for r in base:
                dists = r["dists"]
                validos = [i for i, d in enumerate(dists) if d < umbral]
                chunks_val_total += len(validos)

                if not validos:
                    continue

                top1_meta = r["metas"][validos[0]]
                m02 += 1

                doc_esp = r["item"].get("documento_esperado", "")
                if doc_esp and doc_esp.lower() in (
                    top1_meta.get("documento") or ""
                ).lower():
                    doc_ok += 1

                if top1_meta.get("categoria") == r["item"]["categoria_objetivo"]:
                    cat_ok += 1

            filas.append({
                "umbral": f"{umbral:.2f}",
                "top_k": topk,
                "cobertura_pct": round(100 * m02 / len(banco), 1),
                "acierto_doc_pct": round(100 * doc_ok / len(banco), 1),
                "acierto_cat_pct": round(100 * cat_ok / len(banco), 1),
                "chunks_validos_prom": round(chunks_val_total / len(banco), 2),
                "latencia_ms": round(sum(r["lat_ms"] for r in base) / len(base), 0),
            })

    # ------------------------------------------------------------------
    # 5. Salidas CSV + Markdown
    # ------------------------------------------------------------------
    def fila_csv(f):
        return ",".join(str(f[k]) for k in
                        ["umbral", "top_k", "cobertura_pct", "acierto_doc_pct",
                         "acierto_cat_pct", "chunks_validos_prom", "latencia_ms"])

    cabecera = ("umbral,top_k,cobertura_pct,acierto_doc_pct,"
                "acierto_cat_pct,chunks_validos_prom,latencia_ms")
    OUT_CSV.write_text(
        cabecera + "\n" + "\n".join(fila_csv(f) for f in filas) + "\n",
        encoding="utf-8",
    )
    print(f"\nCSV guardado: {OUT_CSV.name}")

    mejor = max(filas, key=lambda f: (f["acierto_doc_pct"], -f["top_k"]))
    actual = next(f for f in filas
                  if float(f["umbral"]) == 0.40 and f["top_k"] == 4)

    lineas_md = [
        "# Calibración RAG — Resultados",
        "",
        f"- Banco: **{len(banco)} preguntas** (`preguntas_comparacion.json` v2)",
        f"- Corpus: **{n_chunks} chunks** | Modelo: `{MODELO}`",
        f"- Grid: umbral ∈ [{UMBRALES[0]}–{UMBRALES[-1]}] × top_k ∈ {TOPKS}",
        f"- Boost por keyword: {BOOST_KEYWORD} | Re-ranking idéntico a producción",
        f"- Fecha: {time.strftime('%Y-%m-%d')}",
        "",
        "## Tabla completa (33 combinaciones)",
        "",
        "| Umbral | Top-K | Cobertura % | Acierto doc % | Acierto cat % | "
        "Chunks válidos prom | Latencia ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in filas:
        marca = " ← actual" if f is actual else (
            " ★" if f is mejor else "")
        lineas_md.append(
            f"| {f['umbral']} | {f['top_k']} | {f['cobertura_pct']} | "
            f"{f['acierto_doc_pct']} | {f['acierto_cat_pct']} | "
            f"{f['chunks_validos_prom']} | {int(f['latencia_ms'])} |{marca}"
        )
    lineas_md += [
        "",
        "## Recomendación",
        "",
        f"- **Mejor combinación:** umbral=**{mejor['umbral']}**, "
        f"top_k=**{mejor['top_k']}** → acierto doc **{mejor['acierto_doc_pct']}%**, "
        f"categoría **{mejor['acierto_cat_pct']}%**, "
        f"cobertura **{mejor['cobertura_pct']}%**.",
        f"- **Configuración actual:** umbral=0.40, top_k=4 → "
        f"doc **{actual['acierto_doc_pct']}%**, categoría "
        f"**{actual['acierto_cat_pct']}%**, cobertura "
        f"**{actual['cobertura_pct']}%**.",
        "",
        "> La calibración simula SOLO la recuperación (embedding+query+re-ranking),",
        "> sin LLM. La calidad final de respuesta depende también del LLM.",
    ]
    OUT_MD.write_text("\n".join(lineas_md), encoding="utf-8")
    print(f"Markdown guardado: {OUT_MD.name}")

    # ------------------------------------------------------------------
    # Resumen consola: top 5 por acierto_doc
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("TOP-5 COMBINACIONES POR ACIERTO DE DOCUMENTO")
    print("=" * 70)
    top5 = sorted(filas, key=lambda f: (-f["acierto_doc_pct"], f["top_k"]))[:5]
    print(f"{'umbral':>7} {'topk':>4} {'cobertura':>10} {'doc%':>6} "
          f"{'cat%':>6} {'chunks':>7}")
    for f in top5:
        print(f"{f['umbral']:>7} {f['top_k']:>4} {f['cobertura_pct']:>9}% "
              f"{f['acierto_doc_pct']:>5}% {f['acierto_cat_pct']:>5}% "
              f"{f['chunks_validos_prom']:>7}")


if __name__ == "__main__":
    main()
