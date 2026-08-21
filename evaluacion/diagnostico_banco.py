# -*- coding: utf-8 -*-
"""Diagnóstico: resultado por pregunta en la config actual (0.40 / top_k 4)."""

import json
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_STORE = "/data/vector_store"
COLECCION = "corpus_upeu"
BANCO = Path("/data/evaluacion/preguntas_comparacion.json")
UMBRAL = 0.40
BOOST = 0.07

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

model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
client = chromadb.PersistentClient(path=VECTOR_STORE)
collection = client.get_collection(COLECCION)
banco = json.loads(BANCO.read_text(encoding="utf-8"))

print(f"{'ID':>4} {'cat':>3} {'top1_dist':>9} {'doc_ok':>6} {'cat_ok':>6}  pregunta")
print("-" * 95)

for item in banco:
    q = item["pregunta"]
    emb = model.encode([q], normalize_embeddings=True)[0].tolist()
    res = collection.query(query_embeddings=[emb], n_results=15)
    metas = res["metadatas"][0]
    dists = list(res["distances"][0])

    kws = [w.lower() for w in _RE_PALABRA.findall(q.lower())
           if w.lower() not in _STOPWORDS_ES]
    boosted = []
    for d, m in zip(dists, metas):
        dn = (m.get("documento") or "").lower()
        boosted.append(max(0.0, d - sum(1 for k in kws if k in dn) * BOOST))
    orden = sorted(range(len(dists)), key=lambda i: boosted[i])

    validos = [i for i in orden if dists[i] < UMBRAL]
    if not validos:
        print(f"{item['id']:>4} {item['categoria_objetivo']:>3} "
              f"{'SIN VALIDOS':>9} {'NO':>6} {'NO':>6}  {q[:55]}")
        continue

    i1 = validos[0]
    m1 = metas[i1]
    d1 = dists[i1]
    doc_ok = item.get("documento_esperado", "").lower() in (
        m1.get("documento") or "").lower()
    cat_ok = m1.get("categoria") == item["categoria_objetivo"]

    # ¿En qué posición quedó el documento esperado?
    pos_esp = "-"
    doc_esp_l = item.get("documento_esperado", "").lower()
    for rank, i in enumerate(orden, start=1):
        if doc_esp_l in (metas[i].get("documento") or "").lower():
            pos_esp = f"#{rank}" if dists[i] < UMBRAL else f"#{rank} (>umbral)"
            break

    print(f"{item['id']:>4} {item['categoria_objetivo']:>3} {d1:>9.3f} "
          f"{'SI' if doc_ok else 'no':>6} {'SI' if cat_ok else 'no':>6}  "
          f"{q[:48]:<48} esperado:{pos_esp}")
