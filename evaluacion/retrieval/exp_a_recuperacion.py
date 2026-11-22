# -*- coding: utf-8 -*-
"""Experimento A de la Revisión 3 — recuperación pura (sin LLM): BM25, MiniLM, mpnet y bge-m3.

Todos los recuperadores buscan sobre los MISMOS chunks (por defecto los del corpus V3 que usa el
chatbot, `chunks_v3_bgem3.csv` del OE1) y con el mismo texto de entrada (`texto_embedding` =
breadcrumb + texto). La búsqueda es exacta (producto punto sobre vectores normalizados), así se
mide el recuperador y no el índice HNSW.

Métricas por pregunta (al nivel más específico anotado: artículo si existe; si no, documento):
    R@1, R@3, R@5, R@10, MRR@10, nDCG@5 (relevancia binaria, cada artículo cuenta una vez)
    y Rdoc@1/5/10 (documento correcto) para todas.

Salida en evaluacion/retrieval/exp_a/<etiqueta>/:
    <recuperador>.csv   una fila por pregunta (entrada para estadistica/estadistica.py)
    resumen.csv         media e IC95 bootstrap por recuperador y métrica
    h1_vs_bm25.csv      Wilcoxon + Holm de cada recuperador semántico contra BM25 (H1)
    meta.json           versiones, revisiones, hash de los chunks, banco y fecha

Uso (dentro de la imagen del backend; ver README de retrieval/ para el `docker run`):
    python exp_a_recuperacion.py --banco /data/evaluacion/banco/banco_v32.json \
        --chunks /oe1/chunks_v3_bgem3.csv --emb-bgem3 /oe1/embeddings_v3_bgem3.npy \
        --recuperadores bm25,mpnet,bgem3 --etiqueta B32_chunk350
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "estadistica"))
import estadistica as est  # noqa: E402

KS = (1, 3, 5, 10)
PROFUNDIDAD = 50  # posiciones guardadas por pregunta

MODELOS = {
    "minilm": dict(nombre="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", revision=None,
                   max_seq=128, prefijo=""),
    "mpnet": dict(nombre="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
                  revision="4328cf26390c98c5e3c738b4460a05b95f4911f5", max_seq=128, prefijo=""),
    "bgem3": dict(nombre="BAAI/bge-m3", revision="5617a9f61b028005a4858fdac845db406aefb181",
                  max_seq=384, prefijo=""),
}
SISTEMA = {"bm25": "S1", "minilm": "S2", "mpnet": "S3", "bgem3": "S4"}

_STOP = set("""a al algo algun alguna algunas alguno algunos ante antes como con contra cual cuales cuando
de del desde donde dos el ella ellas ellos en entre era es esa esas ese eso esos esta estas este esto estos
fue ha han hasta hay la las le les lo los mas me mi mis mucho muy ni no nos o os otra otras otro otros para
pero por porque puede pueden que quien se sea segun ser si sin sobre son su sus tambien te tiene tienen
todo todos tu tus un una unas uno unos y ya cual cuanto cuanta cuantos cuantas debo puedo hacer""".split())


# --------------------------------------------------------------------------- utilidades
def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t[:-4] if t.endswith(".pdf") else t
    # "_" cuenta como espacio: el CSV trae "V5_2025.pdf" en `documento` y "V5 2025" en `nombre_documento`
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]|_", " ", t)).strip()


def num_art(a) -> str:
    m = re.search(r"\d+", str(a or ""))
    return m.group(0) if m else ""


def tokenizar(t: str) -> list[str]:
    return [w for w in norm(t).split() if len(w) > 1 and w not in _STOP]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- datos
def cargar_chunks(path: Path) -> list[dict]:
    csv.field_size_limit(10 ** 9)
    with open(path, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        r["_doc"] = norm(r.get("nombre_documento") or r.get("documento"))
        r["_art"] = num_art(r.get("articulo"))
        r["_texto"] = r.get("texto_embedding") or r.get("texto") or ""
    return filas


def cargar_banco(path: Path) -> list[dict]:
    """Normaliza el banco a [{id, pregunta, categoria, docs:set, arts:set[(doc,num)], dev:bool}].

    Acepta el formato JSON del banco v3.2 / gold set (`preguntas` con documentos_esperados y
    articulos_esperados) y el CSV del OE1 (documento_esperado como subcadena + articulo_esperado).
    """
    salida = []
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        for q in data["preguntas"]:
            if q.get("cobertura_esperada", "ANSWERABLE") != "ANSWERABLE":
                continue
            docs = {norm(d) for d in q.get("documentos_esperados", [])}
            arts = {(norm(a["documento"]), num_art(a["articulo"])) for a in q.get("articulos_esperados", [])
                    if num_art(a.get("articulo"))}
            salida.append(dict(id=q["id"], pregunta=q["pregunta"], categoria=q.get("categoria", ""),
                               docs=docs, arts=arts, dev=bool(q.get("conjunto_desarrollo", True)),
                               subcadena=False))
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("tipo", "positiva") != "positiva":
                    continue
                d = norm(r["documento_esperado"])
                a = num_art(r.get("articulo_esperado"))
                salida.append(dict(id=r["id"], pregunta=r["pregunta"], categoria=r.get("categoria_esperada", ""),
                                   docs={d}, arts={(d, a)} if a else set(), dev=False, subcadena=True))
    return salida


def es_doc_relevante(doc_chunk: str, q: dict) -> bool:
    if q["subcadena"]:
        return any(d and d in doc_chunk for d in q["docs"])
    return doc_chunk in q["docs"]


def clave_art_relevante(ch: dict, q: dict):
    """Devuelve la clave del artículo relevante que contiene el chunk, o None."""
    if not ch["_art"]:
        return None
    for d, a in q["arts"]:
        if a == ch["_art"] and ((d in ch["_doc"]) if q["subcadena"] else d == ch["_doc"]):
            return (d, a)
    return None


# --------------------------------------------------------------------------- recuperadores
class BM25:
    def __init__(self, textos: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenizar(t)) for t in textos]
        self.largos = np.array([sum(c.values()) for c in self.docs], dtype=float)
        self.media = float(self.largos.mean())
        df = Counter(w for c in self.docs for w in c)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.post = defaultdict(list)
        for i, c in enumerate(self.docs):
            for w, tf in c.items():
                self.post[w].append((i, tf))

    def puntajes(self, consulta: str) -> np.ndarray:
        s = np.zeros(len(self.docs))
        for w in set(tokenizar(consulta)):
            idf = self.idf.get(w)
            if idf is None:
                continue
            for i, tf in self.post[w]:
                s[i] += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.largos[i] / self.media))
        return s


def embeddings_modelo(clave: str, textos: list[str], cache: Path, emb_bgem3: Path | None, ids: list[str],
                      dispositivo: str) -> tuple[np.ndarray, object, dict]:
    """Embeddings normalizados de los chunks (con caché en disco) y el modelo para codificar preguntas."""
    from sentence_transformers import SentenceTransformer
    cfg = MODELOS[clave]
    modelo = SentenceTransformer(cfg["nombre"], revision=cfg["revision"], device=dispositivo)
    modelo.max_seq_length = cfg["max_seq"]
    info = {"modelo": cfg["nombre"], "revision": cfg["revision"] or "última disponible (registrar)",
            "max_seq": cfg["max_seq"]}
    # tokens que se pierden por truncamiento (relevante para H2 con chunks grandes)
    n_tok = [len(modelo.tokenizer(t, add_special_tokens=True)["input_ids"]) for t in textos]
    info["pct_chunks_truncados"] = round(100 * sum(n > cfg["max_seq"] for n in n_tok) / len(n_tok), 2)
    info["pct_tokens_embebidos"] = round(100 * sum(min(n, cfg["max_seq"]) for n in n_tok) / sum(n_tok), 2)

    if clave == "bgem3" and emb_bgem3 and emb_bgem3.exists():
        ids_npy = emb_bgem3.with_name(emb_bgem3.name.replace("embeddings_", "chunk_ids_"))
        if ids_npy.exists() and list(np.load(ids_npy, allow_pickle=True)) == ids:
            e = np.load(emb_bgem3).astype(np.float32)
            info["origen_embeddings"] = f"{emb_bgem3.name} (índice de producción, sha256 {sha256(emb_bgem3)[:12]})"
            return e / np.linalg.norm(e, axis=1, keepdims=True), modelo, info
        print("  aviso: los chunk_ids del .npy no coinciden con el CSV; se recalcula bge-m3", flush=True)
    archivo = cache / f"{clave}_{hashlib.sha1(''.join(ids).encode()).hexdigest()[:10]}.npy"
    if archivo.exists():
        e = np.load(archivo)
        info["origen_embeddings"] = f"caché {archivo.name}"
    else:
        t0 = time.time()
        e = modelo.encode([cfg["prefijo"] + t for t in textos], batch_size=32, show_progress_bar=False,
                          normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
        cache.mkdir(parents=True, exist_ok=True)
        np.save(archivo, e)
        info["origen_embeddings"] = f"calculado en {time.time() - t0:.0f} s ({dispositivo}) → {archivo.name}"
    return e, modelo, info


# --------------------------------------------------------------------------- métricas
def metricas_pregunta(orden: np.ndarray, chunks: list[dict], q: dict) -> dict:
    nivel = "articulo" if q["arts"] else "documento"
    rank_doc = rank_obj = None
    vistos, ganancias = set(), []
    for pos, i in enumerate(orden[:PROFUNDIDAD], start=1):
        ch = chunks[i]
        doc_ok = es_doc_relevante(ch["_doc"], q)
        if doc_ok and rank_doc is None:
            rank_doc = pos
        if nivel == "articulo":
            clave = clave_art_relevante(ch, q)
        else:
            clave = ch["_doc"] if doc_ok else None
        nueva = clave is not None and clave not in vistos
        if nueva:
            vistos.add(clave)
            if rank_obj is None:
                rank_obj = pos
        if pos <= 5:
            ganancias.append(1.0 if nueva else 0.0)
    n_rel = len(q["arts"]) if nivel == "articulo" else len(q["docs"])
    dcg = sum(g / math.log2(p + 1) for p, g in enumerate(ganancias, start=1))
    idcg = sum(1 / math.log2(p + 1) for p in range(1, min(n_rel, 5) + 1))
    fila = {"pregunta_id": q["id"], "categoria": q["categoria"], "nivel": nivel, "desarrollo": int(q["dev"]),
            "rank": rank_obj or "", "rank_documento": rank_doc or ""}
    for k in KS:
        fila[f"recall@{k}"] = int(bool(rank_obj and rank_obj <= k))
    fila["mrr@10"] = (1 / rank_obj) if rank_obj and rank_obj <= 10 else 0.0
    fila["ndcg@5"] = dcg / idcg if idcg else 0.0
    for k in (1, 5, 10):
        fila[f"rdoc@{k}"] = int(bool(rank_doc and rank_doc <= k))
    top = chunks[orden[0]]
    fila["top1_documento"] = top.get("nombre_documento") or top.get("documento")
    fila["top1_articulo"] = top.get("articulo", "")
    return fila


METRICAS = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr@10", "ndcg@5", "rdoc@1", "rdoc@5", "rdoc@10"]


def escribir_csv(path: Path, filas: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        for r in filas:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


# --------------------------------------------------------------------------- main
def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco", type=Path, required=True)
    ap.add_argument("--chunks", type=Path, required=True)
    ap.add_argument("--emb-bgem3", type=Path, help="embeddings del índice de producción (se reutilizan)")
    ap.add_argument("--recuperadores", default="bm25,minilm,mpnet,bgem3")
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--salida", type=Path, default=AQUI / "exp_a")
    ap.add_argument("--cache", type=Path, default=AQUI / "exp_a" / "_cache_embeddings")
    ap.add_argument("--dispositivo", default=None, help="cuda | cpu (por defecto: cuda si hay)")
    ap.add_argument("--n-boot", type=int, default=est.N_BOOT)
    a = ap.parse_args(argv)

    recs = [r.strip() for r in a.recuperadores.split(",") if r.strip()]
    for r in recs:
        if r != "bm25" and r not in MODELOS:
            raise SystemExit(f"recuperador desconocido: {r}")
    dispositivo = a.dispositivo
    if dispositivo is None:
        try:
            import torch
            dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            dispositivo = "cpu"

    chunks = cargar_chunks(a.chunks)
    banco = cargar_banco(a.banco)
    ids = [c["chunk_id"] for c in chunks]
    textos = [c["_texto"] for c in chunks]
    # preguntas cuyo documento esperado no existe en estos chunks: error del banco, no del recuperador
    docs_corpus = {c["_doc"] for c in chunks}
    sin_doc = [q["id"] for q in banco if not any(es_doc_relevante(d, q) for d in docs_corpus)]
    if sin_doc:
        print(f"aviso: {len(sin_doc)} preguntas con documento inexistente se excluyen: {sin_doc}")
        banco = [q for q in banco if q["id"] not in sin_doc]
    print(f"chunks: {len(chunks)} · preguntas: {len(banco)} · recuperadores: {recs} · dispositivo: {dispositivo}")

    out = a.salida / a.etiqueta
    out.mkdir(parents=True, exist_ok=True)
    meta = {"etiqueta": a.etiqueta, "fecha": datetime.now().isoformat(timespec="seconds"),
            "banco": str(a.banco), "n_preguntas": len(banco), "excluidas_sin_documento": sin_doc,
            "chunks": str(a.chunks), "n_chunks": len(chunks), "sha256_chunks": sha256(a.chunks),
            "tokens_chunk": {"max": max(int(c.get("num_tokens") or 0) for c in chunks),
                             "mediana": float(np.median([int(c.get("num_tokens") or 0) for c in chunks]))},
            "busqueda": "exacta (producto punto, vectores normalizados)", "dispositivo": dispositivo,
            "recuperadores": {}}

    por_rec = {}
    for r in recs:
        t0 = time.time()
        print(f"\n== {SISTEMA[r]} {r}", flush=True)
        if r == "bm25":
            bm = BM25(textos)
            puntajes = [bm.puntajes(q["pregunta"]) for q in banco]
            meta["recuperadores"][r] = {"k1": bm.k1, "b": bm.b, "tokenizador": "minúsculas, sin tildes, sin stopwords"}
        else:
            emb, modelo, info = embeddings_modelo(r, textos, a.cache, a.emb_bgem3, ids, dispositivo)
            qv = modelo.encode([MODELOS[r]["prefijo"] + q["pregunta"] for q in banco], normalize_embeddings=True,
                               convert_to_numpy=True, show_progress_bar=False)
            puntajes = list(qv @ emb.T)
            meta["recuperadores"][r] = info
            del modelo
        filas = []
        for q, s in zip(banco, puntajes):
            orden = np.argsort(-np.asarray(s), kind="stable")
            filas.append(metricas_pregunta(orden, chunks, q))
        escribir_csv(out / f"{SISTEMA[r]}_{r}.csv", filas)
        por_rec[r] = filas
        meta["recuperadores"][r]["segundos"] = round(time.time() - t0, 1)
        print("   " + "  ".join(f"{m}={np.mean([f[m] for f in filas]):.3f}" for m in METRICAS), flush=True)

    # resumen con IC95
    resumen = []
    for r, filas in por_rec.items():
        for m in METRICAS:
            media, lo, hi = est.bootstrap_ic([f[m] for f in filas], n_boot=a.n_boot)
            resumen.append({"sistema": SISTEMA[r], "recuperador": r, "metrica": m, "n": len(filas),
                            "media": media, "ic95_lo": lo, "ic95_hi": hi})
    escribir_csv(out / "resumen.csv", resumen)

    # H1: cada recuperador semántico contra BM25 (Holm sobre las comparaciones de cada métrica)
    if "bm25" in por_rec and len(por_rec) > 1:
        comp = []
        for m in ("recall@5", "mrr@10", "ndcg@5"):
            datos = {r: {f["pregunta_id"]: f[m] for f in filas} for r, filas in por_rec.items()}
            for fila in est.comparar_sistemas(datos, base="bm25", n_boot=a.n_boot):
                comp.append({"metrica": m, **fila})
        escribir_csv(out / "h1_vs_bm25.csv", comp)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultados en {out}")


if __name__ == "__main__":
    main()
