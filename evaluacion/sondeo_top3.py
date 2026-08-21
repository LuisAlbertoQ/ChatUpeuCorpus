# -*- coding: utf-8 -*-
"""Sondeo puntual: top-3 para Q04 y Q06."""
import json, re
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
client = chromadb.PersistentClient(path="/data/vector_store")
collection = client.get_collection("corpus_upeu")

for q in ["¿Cómo me matriculo en la UPeU?",
          "¿Cuáles son los requisitos para publicar un artículo científico?",
          "¿Cuál es el procedimiento para cambiar de carrera?"]:
    emb = model.encode([q], normalize_embeddings=True)[0].tolist()
    res = collection.query(query_embeddings=[emb], n_results=3)
    print(f"\n{q}")
    for i in range(3):
        m = res["metadatas"][0][i]
        print(f"  #{i+1} d={res['distances'][0][i]:.3f} "
              f"[{m.get('categoria')}] {m.get('documento')} · {m.get('articulo','')}")
