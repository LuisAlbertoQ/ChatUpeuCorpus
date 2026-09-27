#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_rag.py — Evaluación técnica OFFLINE de retrieval (Parte 3, Fase 3).

Proceso offline y reproducible por experimento:
1. crear experimento_id y registrar snapshot de configuración
2. cargar banco técnico (banco_version='v2_tecnico' AND activa=1) — 17 preguntas
3. para cada pregunta: embedding → retrieval Top15 raw → reranking keyword boost → threshold+Top4 final
4. persistir candidatos en evaluacion_retrieval con flags es_relevante_* y posiciones
5. calcular métricas agregadas (Hit/Recall/MRR/NDCG @5/@10/@15 + final Top4) y persistir en metricas_retrieval_experimento
6. exportar CSV/JSON

Uso:
  docker compose run --rm backend python /data/evaluacion/retrieval/evaluar_rag.py
  python evaluacion/retrieval/evaluar_rag.py  # host, si tiene chromadb
"""

import datetime
import hashlib
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

import chromadb
from chromadb.config import Settings

# ---------------------------------------------------------------------------
# Configuración de fuentes canónicas (reutiliza Parte 2 sin modificarla)
# ---------------------------------------------------------------------------
EVAL_DIR = Path(__file__).parent
PROJECT_ROOT = EVAL_DIR.parent.parent.parent
DB_CANDIDATES = [PROJECT_ROOT / "registro_interacciones.db", Path("/data/registro_interacciones.db")]
VECTOR_CANDIDATES = [PROJECT_ROOT / "vector_store", Path("/data/vector_store")]

# Importar configuración real de Parte 2 (no duplicar valores)
for p in [PROJECT_ROOT / "backend", Path("/app")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import config  # noqa: E402

# ---------------------------------------------------------------------------
# Normalización determinística (sin fuzzy, sin embeddings)
# ---------------------------------------------------------------------------
def normalizar_documento(texto: str) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    # quitar extensión .pdf
    if t.endswith(".pdf"):
        t = t[:-4]
    # puntuación irrelevante → espacio, colapsar
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

_RE_ART_NUM = re.compile(r"(\d+(?:[.-]\d+)?(?:[a-zA-Z])?)")

def normalizar_articulo(texto: str) -> str:
    if not texto:
        return ""
    # Eliminar ordinales antes de NFKD para que no se descompongan a 'o'/'a'
    t0 = texto.replace("º", "").replace("°", "").replace("ª", "")
    t = unicodedata.normalize("NFKD", t0).lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    # extraer núcleo "articulo 42" / "42" / "42.1" / "42-a"
    m = re.search(r"(?:art[íi]culo|cap[íi]tulo|secci[óo]n|t[íi]tulo)?\s*(\d+(?:[.-][\w]+)?)", t)
    if m:
        num = m.group(1).strip().lower()
        return num
    # fallback: solo número
    m2 = _RE_ART_NUM.search(t)
    return m2.group(1).lower() if m2 else re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()

def clave_documento(doc: str) -> str:
    return normalizar_documento(doc)

def clave_articulo(doc: str, art: str) -> str:
    # NEGRO: documento + artículo, no solo número
    return f"{normalizar_documento(doc)}|{normalizar_articulo(art)}" if art else normalizar_documento(doc)

# ---------------------------------------------------------------------------
# Deduplicación
# ---------------------------------------------------------------------------
def deduplicar_por_documento(ranking):
    """ranking: lista de dicts con 'documento'; preserva primera aparición."""
    vistos = set()
    out = []
    for item in ranking:
        k = clave_documento(item.get("documento", ""))
        if k not in vistos:
            vistos.add(k)
            out.append(item)
    return out

def deduplicar_por_articulo(ranking):
    """Preserva primera aparición de cada par documento+artículo."""
    vistos = set()
    out = []
    for item in ranking:
        k = clave_articulo(item.get("documento", ""), item.get("articulo", ""))
        if k not in vistos:
            vistos.add(k)
            out.append(item)
    return out

# ---------------------------------------------------------------------------
# Métricas estándar
# ---------------------------------------------------------------------------
def hit_at_k(retrieved, relevant, k):
    # retrieved: lista deduplicada ordenada; relevant: set de claves
    topk = set(retrieved[:k])
    return 1 if any(r in topk for r in relevant) else 0

def recall_at_k(retrieved, relevant, k):
    if not relevant:
        return None  # excluir del denominador
    topk = set(retrieved[:k])
    return len(topk & relevant) / len(relevant)

def mrr_at_k(retrieved, relevant, k):
    if not relevant:
        return None
    for i, r in enumerate(retrieved[:k], 1):
        if r in relevant:
            return 1.0 / i
    return 0.0

def dcg_at_k(retrieved, relevant, k):
    dcg = 0.0
    for i, r in enumerate(retrieved[:k], 1):
        if r in relevant:
            dcg += 1.0 / math.log2(i + 1)
    return dcg

def ndcg_at_k(retrieved, relevant, k):
    if not relevant:
        return None
    dcg = dcg_at_k(retrieved, relevant, k)
    # IDCG: relevantes al inicio
    ideal = [1] * min(len(relevant), k) + [0] * max(0, k - len(relevant))
    idcg = sum(rel / math.log2(i + 1) for i, rel in enumerate(ideal[:k], 1))
    return dcg / idcg if idcg > 0 else 0.0

# ---------------------------------------------------------------------------
# Ranking Parte 2 (reutilizado sin modificar comportamiento)
# ---------------------------------------------------------------------------
_STOPWORDS_ES = __import__("rag_pipeline", fromlist=["_STOPWORDS_ES"])._STOPWORDS_ES if False else frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "u", "e", "que", "qué", "cual", "cuál", "como", "cómo", "donde",
    "dónde", "cuando", "cuándo", "quien", "quién", "por", "para", "con", "sin",
    "a", "en", "es", "son", "se", "su", "sus", "le", "les", "lo", "me", "te",
    "nos", "os", "mi", "ti", "si", "no", "ya", "ha", "han", "he", "hay",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel",
    "del", "más", "mas", "menos", "sobre", "entre", "hasta", "desde", "ante",
})
_BOOST = 0.07
_RE_PALABRA = re.compile(r"\b[a-záéíóúñü]{4,}\b", re.IGNORECASE)

def keywords_query(pregunta: str):
    return [w.lower() for w in _RE_PALABRA.findall(pregunta.lower()) if w.lower() not in _STOPWORDS_ES]

def rerank(distancias, metadatas, pregunta):
    kws = keywords_query(pregunta)
    if not kws:
        orden = sorted(range(len(distancias)), key=lambda i: distancias[i])
        return orden, distancias, distancias
    boosted = []
    for d, m in zip(distancias, metadatas):
        dn = (m.get("documento") or "").lower()
        matches = sum(1 for kw in kws if kw in dn)
        boosted.append(max(0.0, d - matches * _BOOST))
    orden = sorted(range(len(distancias)), key=lambda i: boosted[i])
    dist_ajustada = [boosted[i] for i in orden]
    # distancias ya reordenadas para retorno
    return orden, distancias, dist_ajustada

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def find_db():
    for p in DB_CANDIDATES:
        if p.exists():
            return p
    return DB_CANDIDATES[0]

def find_vector():
    for p in VECTOR_CANDIDATES:
        if p.exists():
            return p
    return VECTOR_CANDIDATES[0]

def main():
    t_start = time.time()
    db_path = find_db()
    vector_path = find_vector()
    print(f"DB: {db_path}")
    print(f"Vector: {vector_path}")
    print(f"Config: threshold={config.RAG_DISTANCE_THRESHOLD} top_raw={config.RAG_TOP_K_RAW} top_final={config.RAG_TOP_K_FINAL} corpus={config.CORPUS_VERSION} emb={config.EMBEDDING_MODEL}")

    # 1. Crear experimento_id
    ts = datetime.datetime.now().isoformat()
    exp_id = f"EXP_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(ts.encode()).hexdigest()[:6]}"
    print(f"Experimento: {exp_id}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    # Registrar snapshot de configuración
    conn.execute(
        "INSERT INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version, descripcion, estado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (exp_id, ts, config.CORPUS_VERSION, config.EMBEDDING_MODEL, config.OLLAMA_MODEL, config.RAG_TOP_K_RAW, config.RAG_TOP_K_FINAL, config.RAG_DISTANCE_THRESHOLD, config.RANKING_METHOD, config.RANKING_VERSION, config.PROMPT_VERSION, "Evaluación retrieval offline banco v2_tecnico", "completado"),
    )
    conn.commit()

    # 2. Cargar banco técnico explícito (no LIKE)
    banco = list(conn.execute("SELECT id, pregunta, documento_esperado, articulo_esperado FROM banco_preguntas WHERE banco_version='v2_tecnico' AND activa=1 ORDER BY id").fetchall())
    if len(banco) != 17:
        print(f"WARN: banco técnico tiene {len(banco)} filas, esperado 17", file=sys.stderr)
    print(f"Banco técnico: {len(banco)} preguntas")

    # Conexión Chroma + modelo
    from sentence_transformers import SentenceTransformer
    import chromadb
    from chromadb.config import Settings
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(vector_path), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection("corpus_upeu_v2")

    # Para métricas agregadas
    all_metrics = []

    t_exp_start = time.time()
    total_retrieval_rows = 0

    for qid, pregunta, doc_esp, art_esp in banco:
        # Ground truth relevante (singular actual, pero preparado para múltiples)
        rel_docs = {clave_documento(doc_esp)} if doc_esp else set()
        # Artículo relevante solo si existe y cobertura no es NO_ANSWER (todas ANSWERABLE)
        rel_arts = {clave_articulo(doc_esp, art_esp)} if doc_esp and art_esp else set()
        # Q11 tiene art_esp vacío → excluir de métricas artículo
        evaluar_articulo = bool(art_esp and art_esp.strip())

        # Embedding + retrieval Top15 raw
        emb = model.encode([pregunta], normalize_embeddings=True)[0].tolist()
        res = collection.query(query_embeddings=[emb], n_results=config.RAG_TOP_K_RAW)
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists_raw = list(res["distances"][0])

        # Capturar RAW ranking (sin boost)
        raw_rank = list(range(len(dists_raw)))  # ya ordenado por Chroma

        # Reranking
        orden, dists_orig_reordered, dists_adj = rerank(dists_raw, metas, pregunta)
        # Reordenar docs/metas según rerank
        docs_r = [docs[i] for i in orden]
        metas_r = [metas[i] for i in orden]
        # dists_raw reordenado y ajustada
        # Para persistencia: distancia_original = dists_raw reordenado, distancia_ajustada = dists_adj
        # rank_raw = posición original (1-indexed) del chunk en orden raw
        # rank_reranked = posición en orden rerankeado (1..15)

        # Mapear rank_raw: necesitamos posición original de cada chunk
        # Como orden es permutación, rank_raw de chunk en posición rerankeada j es orden[j]+1? No, orden[j] es índice original.
        # Para cada chunk en orden rerankeado, su rank_raw = posición original +1
        # Invertir: pos_original = orden.index? Mejor calcular
        pos_raw_map = {orig_idx: rank+1 for rank, orig_idx in enumerate(sorted(range(len(dists_raw)), key=lambda i: dists_raw[i]))}  # pero dists_raw ya estaba ordenado, así que rank_raw = orig_idx+1
        # Simplificación: como Chroma ya devuelve ordenado, rank_raw = orig_idx+1
        # Tras rerank, cada elemento en posición j tiene rank_raw = orden[j]+1 y rank_reranked = j+1
        # Guardaremos ambos

        # Determinar sobrevivió threshold y entró Top4
        # Final selection: primeros RAG_TOP_K_FINAL del rerankeado que pasan threshold
        valid_idx = [j for j, d in enumerate(dists_adj) if d < config.RAG_DISTANCE_THRESHOLD]
        top4_final_set = set(valid_idx[:config.RAG_TOP_K_FINAL])

        # Persistir 15 candidatos por pregunta
        for j in range(len(docs_r)):
            meta = metas_r[j]
            chunk_id = meta.get("chunk_id", "")
            doc_rec = meta.get("documento", "")
            art_rec = meta.get("articulo", "")
            d_orig = dists_raw[orden[j]] if j < len(orden) else dists_raw[j]
            # Nota: d_orig reordenado
            d_orig_val = dists_raw[orden[j]]
            d_adj_val = dists_adj[j]
            rank_raw_val = orden[j] + 1
            rank_rer_val = j + 1
            sobrevivio = 1 if d_adj_val < config.RAG_DISTANCE_THRESHOLD else 0
            entro = 1 if j in top4_final_set else 0
            es_doc = 1 if clave_documento(doc_rec) in rel_docs else 0
            es_art = 1 if evaluar_articulo and clave_articulo(doc_rec, art_rec) in rel_arts else (0 if evaluar_articulo else None)

            conn.execute(
                "INSERT INTO evaluacion_retrieval (pregunta_id, experimento_id, top_k, chunk_id_recuperado, documento_recuperado, articulo_recuperado, distancia_original, distancia_ajustada, rank_raw, rank_reranked, sobrevivio_threshold, entro_top4, es_relevante_documento, es_relevante_articulo, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (qid, exp_id, config.RAG_TOP_K_RAW, chunk_id, doc_rec, art_rec, d_orig_val, d_adj_val, rank_raw_val, rank_rer_val, sobrevivio, entro, es_doc, es_art, datetime.datetime.now().isoformat()),
            )
            total_retrieval_rows += 1

    conn.commit()

    # Calcular métricas agregadas por unidad y K
    # Documento: 17 preguntas; Artículo: 16 (excluye Q11)
    for unidad in ["documento", "articulo"]:
        n_preg = 17 if unidad == "documento" else 16
        # Para cada K
        for k in [5,10,15]:
            hits = []
            recalls = []
            rrs = []
            ndcgs = []
            for qid, pregunta, doc_esp, art_esp in banco:
                if unidad == "articulo" and not art_esp:
                    continue
                rel = {clave_documento(doc_esp)} if unidad=="documento" else {clave_articulo(doc_esp, art_esp)}
                # Recuperar ranking deduplicado para esta pregunta y unidad
                rows = list(conn.execute("SELECT documento_recuperado, articulo_recuperado, es_relevante_documento, es_relevante_articulo, rank_reranked FROM evaluacion_retrieval WHERE pregunta_id=? AND experimento_id=? ORDER BY rank_reranked", (qid, exp_id)).fetchall())
                # Construir ranking deduplicado
                seen = set()
                ranking = []
                for doc_rec, art_rec, es_doc, es_art, rank in rows:
                    key = clave_documento(doc_rec) if unidad=="documento" else clave_articulo(doc_rec, art_rec)
                    if key not in seen:
                        seen.add(key)
                        ranking.append(key)
                # Hit/Recall
                # Para Recall con 1 relevante, es igual a Hit
                relevant = rel
                hit = hit_at_k(ranking, relevant, k)
                rec = recall_at_k(ranking, relevant, k)
                rr = mrr_at_k(ranking, relevant, k)
                ndcg = ndcg_at_k(ranking, relevant, k)
                hits.append(hit)
                recalls.append(rec if rec is not None else 0)
                rrs.append(rr if rr is not None else 0)
                ndcgs.append(ndcg if ndcg is not None else 0)
            # Promedios
            for metrica, vals in [("hit_rate", hits), ("recall", recalls), ("mrr", rrs), ("ndcg", ndcgs)]:
                valor = sum(vals)/len(vals) if vals else 0
                conn.execute(
                    "INSERT INTO metricas_retrieval_experimento (experimento_id, unidad, metrica, k, valor, n_preguntas, timestamp) VALUES (?,?,?,?,?,?,?)",
                    (exp_id, unidad, metrica, k, valor, n_preg, datetime.datetime.now().isoformat()),
                )
    # Final Top4 métricas separadas (una sola vez, fuera del bucle unidad)
    final_hits_doc = []
    final_hits_art = []
    final_nums = []
    abstentions = 0
    for qid, pregunta, doc_esp, art_esp in banco:
        rows = list(conn.execute("SELECT es_relevante_documento, es_relevante_articulo, entro_top4 FROM evaluacion_retrieval WHERE pregunta_id=? AND experimento_id=?", (qid, exp_id)).fetchall())
        hit_doc = any(r[0]==1 and r[2]==1 for r in rows)
        final_hits_doc.append(1 if hit_doc else 0)
        if art_esp:
            hit_art = any(r[1]==1 and r[2]==1 for r in rows)
            final_hits_art.append(1 if hit_art else 0)
        final_nums.append(sum(1 for r in rows if r[2]==1))
        if sum(1 for r in rows if r[2]==1) == 0:
            abstentions += 1
    for unidad, vals in [("documento", final_hits_doc), ("articulo", final_hits_art)]:
        if not vals:
            continue
        hit_rate = sum(vals)/len(vals)
        n = len(vals)
        conn.execute("INSERT INTO metricas_retrieval_experimento (experimento_id, unidad, metrica, k, valor, n_preguntas, timestamp) VALUES (?,?,?,?,?,?,?)", (exp_id, unidad, "final_hit_rate", 4, hit_rate, n, datetime.datetime.now().isoformat()))
    conn.execute("INSERT INTO metricas_retrieval_experimento (experimento_id, unidad, metrica, k, valor, n_preguntas, timestamp) VALUES (?,?,?,?,?,?,?)", (exp_id, "final", "final_num_chunks_avg", 4, sum(final_nums)/len(final_nums) if final_nums else 0, len(banco), datetime.datetime.now().isoformat()))
    conn.execute("INSERT INTO metricas_retrieval_experimento (experimento_id, unidad, metrica, k, valor, n_preguntas, timestamp) VALUES (?,?,?,?,?,?,?)", (exp_id, "final", "abstention_due_threshold_rate", 4, abstentions/len(banco), len(banco), datetime.datetime.now().isoformat()))

    conn.commit()
    elapsed = time.time() - t_start
    # Exportar CSV
    import csv as csvm
    csv_path = EVAL_DIR / f"metricas_{exp_id}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csvm.writer(f)
        w.writerow(["experimento_id","unidad","metrica","k","valor","n_preguntas"])
        for row in conn.execute("SELECT experimento_id, unidad, metrica, k, valor, n_preguntas FROM metricas_retrieval_experimento WHERE experimento_id=? ORDER BY unidad, metrica, k", (exp_id,)):
            w.writerow(row)
    print(f"Experimento {exp_id} completado en {elapsed:.1f}s")
    print(f"Filas retrieval: {total_retrieval_rows} (17*15)")
    print(f"CSV: {csv_path}")
    # Resumen
    for row in conn.execute("SELECT unidad, metrica, k, valor FROM metricas_retrieval_experimento WHERE experimento_id=? ORDER BY unidad, metrica, k", (exp_id,)):
        print(f"{row[0]:10} {row[1]:15} @{row[2] if row[2] else '-':>2} = {row[3]:.3f}")

if __name__ == "__main__":
    import time as _t
    t_exp_start = _t.time()
    main()
