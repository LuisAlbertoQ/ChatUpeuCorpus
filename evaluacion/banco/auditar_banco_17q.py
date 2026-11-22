#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auditar_banco_17q.py — Auditoría (solo lectura) del banco técnico de 17 preguntas.

Compara campo por campo las tres fuentes del banco:
  JSON   evaluacion/banco/preguntas_comparacion.json
  BP     registro_interacciones.db · banco_preguntas (banco_version='v3_curado')  ← lo que leen los scripts
  V31    registro_interacciones.db · groundtruth_v31_preguntas / _puntos       ← ground truth curado (66 puntos)
contra el corpus vigente (vector_store, colección V3: documento, categoria_tematica,
articulo, pagina, chunk_id, total_partes) y escribe un informe Markdown.

No modifica ninguna base ni archivo del banco.

Uso (host):  python evaluacion/banco/auditar_banco_17q.py
"""
import collections
import datetime
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CATS = {"A": "Gobierno y estatuto institucional", "B": "Académico y estudios", "C": "Investigación",
        "D": "Bienestar estudiantil", "E": "Laboral, docencia y políticas"}
# Temas libres del banco → categoría que implican (para detectar tema/categoría incoherentes)
TEMA_CAT = {"Gobierno": "A", "Académico": "B", "Investigación": "C", "Bienestar": "D", "Laboral": "E"}


def norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t[:-4] if t.endswith(".pdf") else t
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def num(a):
    m = re.search(r"\d+", a or "")
    return m.group() if m else ""


def toks(t):
    return {w for w in norm(t).split() if len(w) > 3}


def cargar_corpus():
    v = sqlite3.connect(f"file:{RAIZ / 'vector_store' / 'chroma.sqlite3'}?mode=ro", uri=True)
    coleccion = v.execute("SELECT name FROM collections").fetchone()[0]
    por_doc = collections.defaultdict(list)
    for (eid,) in v.execute("SELECT id FROM embeddings"):
        m = {k: (s if s is not None else i) for k, s, i in
             v.execute("SELECT key, string_value, int_value FROM embedding_metadata WHERE id=?", (eid,))}
        por_doc[norm(m.get("documento"))].append(m)
    return coleccion, por_doc


def buscar_doc(por_doc, nombre):
    k = norm(nombre)
    if k in por_doc:
        return k
    cands = [d for d in por_doc if d.startswith(k)]
    return cands[0] if len(cands) == 1 else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    coleccion, por_doc = cargar_corpus()
    js = {q["id"]: q for q in json.loads((RAIZ / "evaluacion/banco/preguntas_comparacion.json").read_text(encoding="utf-8"))}
    c = sqlite3.connect(f"file:{RAIZ / 'registro_interacciones.db'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    bp = {r["id"]: dict(r) for r in c.execute("SELECT * FROM banco_preguntas WHERE banco_version='v3_curado' AND activa=1")}
    v31 = {r["pregunta_id"]: dict(r) for r in c.execute("SELECT * FROM groundtruth_v31_preguntas")}
    pts = collections.defaultdict(list)
    for r in c.execute("SELECT * FROM groundtruth_v31_puntos ORDER BY punto_id"):
        pts[r["pregunta_id"]].append(dict(r))

    filas, hallazgos = [], collections.defaultdict(list)
    for qid in sorted(v31):
        j, b, g = js.get(qid, {}), bp.get(qid, {}), v31[qid]
        h = hallazgos[qid]
        # 1. pregunta
        if not (j.get("pregunta") == b.get("pregunta") == g["pregunta"]):
            h.append("El texto de la pregunta difiere entre fuentes")
        # 2. documento: JSON / BP / V31 y existencia en el corpus
        docs = {"JSON": j.get("documento_esperado"), "BP": b.get("documento_esperado"), "V31": g["documento_esperado"]}
        if len({norm(d) for d in docs.values()}) > 1:
            h.append(f"Documento distinto: JSON/BP='{docs['BP']}' vs v3.1='{docs['V31']}'")
        kdoc = buscar_doc(por_doc, g["documento_esperado"])
        chunks_doc = por_doc.get(kdoc, []) if kdoc else []
        if not kdoc:
            h.append(f"El documento v3.1 '{g['documento_esperado']}' NO existe en {coleccion}")
        cat_real = collections.Counter(m.get("categoria_tematica") for m in chunks_doc).most_common(1)
        cat_real = cat_real[0][0] if cat_real else None
        tipo_doc = chunks_doc[0].get("tipo_documental") if chunks_doc else None
        # 3. artículos: singular BP vs conjunto V31; existencia, página y partes en el corpus
        arts_v31 = [a["articulo"] for a in json.loads(g["articulos_esperados"] or "[]") if a.get("articulo")]
        art_bp = b.get("articulo_esperado") or ""            # singular: la que leen los scripts
        arts_bp_plural = json.loads(b.get("articulos_esperados") or "[]")
        if {num(art_bp)} - {""} != {num(a) for a in arts_v31}:
            h.append(f"Artículos: los scripts comparan solo contra '{art_bp or '(ninguno)'}' · "
                     f"v3.1 acepta {arts_v31 or ['(sin artículo)']}")
        if arts_bp_plural and {num(a) for a in arts_bp_plural} != ({num(art_bp)} - {""}):
            h.append(f"Columna plural articulos_esperados desactualizada en BP: {arts_bp_plural} (singular: '{art_bp}')")
        info_arts = []
        for a in arts_v31:
            ch = [m for m in chunks_doc if num(m.get("articulo")) == num(a)]
            if not ch:
                h.append(f"{a} no existe en el documento dentro de {coleccion}")
            pags = sorted({str(m.get("pagina")) for m in ch if m.get("pagina")})
            partes = max((m.get("total_partes") or 1) for m in ch) if ch else 0
            info_arts.append(f"{a} (pág. {','.join(pags) or '?'}{'; ' + str(partes) + ' partes' if partes > 1 else ''})")
        # 4. categoría y tema
        cat_bp, cat_js = b.get("categoria"), j.get("categoria_objetivo")
        if cat_real and (cat_bp != cat_real or cat_js != cat_real):
            h.append(f"Categoría desactualizada: banco={cat_bp} · documento V3={cat_real} ({CATS.get(cat_real)})")
        tema = j.get("tema")
        if tema in TEMA_CAT and cat_real and TEMA_CAT[tema] != cat_real:
            h.append(f"Tema '{tema}' sugiere {TEMA_CAT[tema]} pero el documento es {cat_real}")
        # 5. evidencias de los puntos v3.1 en el texto real
        ev_bajas = []
        for p in pts[qid]:
            kd = buscar_doc(por_doc, p["documento"])
            cand = [m for m in por_doc.get(kd, []) if not p["articulo"] or num(m.get("articulo")) == num(p["articulo"])]
            txt = set().union(*[toks(m.get("chroma:document", "")) for m in cand]) if cand else set()
            e = toks(p["evidencia"])
            r = len(e & txt) / len(e) if e else 0
            if r < 0.7:
                ev_bajas.append(f"{p['punto_id']} ({r:.0%})")
        if ev_bajas:
            h.append("Evidencia con baja coincidencia en el texto: " + ", ".join(ev_bajas))
        # 6. puntos: BP (v3, se usaba antes) vs v3.1
        n_bp = len(json.loads(b.get("puntos_esperados") or "[]"))
        filas.append({
            "id": qid, "pregunta": g["pregunta"], "tema": tema, "tipo": b.get("tipo_pregunta"),
            "cat_banco": cat_bp, "cat_real": cat_real, "doc_v31": g["documento_esperado"], "doc_bp": b.get("documento_esperado"),
            "tipo_documental": tipo_doc, "arts_v31": "; ".join(info_arts) or "(sin artículo)",
            "puntos_bp": n_bp, "puntos_v31": len(pts[qid]), "nota_v31": g.get("nota") or "",
        })

    fecha = datetime.date.today().isoformat()
    lin = [f"# Auditoría del banco de 17 preguntas — {fecha}", "",
           f"Corpus: colección `{coleccion}` (vector_store). Fuentes comparadas: `preguntas_comparacion.json` (JSON), "
           "`banco_preguntas` v3_curado (BP, **la que leen los scripts de evaluación**) y "
           "`groundtruth_v31_preguntas/_puntos` (v3.1, curado, 66 puntos). Generado por `auditar_banco_17q.py` (solo lectura).", "",
           "## Resumen por pregunta", "",
           "| Q | Pregunta | Tema | Cat. banco → real | Documento (v3.1) | Artículos v3.1 en V3 | Puntos BP/v3.1 |",
           "|---|---|---|---|---|---|---|"]
    for f in filas:
        cat = f["cat_banco"] if f["cat_banco"] == f["cat_real"] else f"**{f['cat_banco']} → {f['cat_real']}**"
        lin.append(f"| {f['id']} | {f['pregunta']} | {f['tema']} | {cat} | {f['doc_v31']} | {f['arts_v31']} | {f['puntos_bp']}/{f['puntos_v31']} |")
    lin += ["", "## Hallazgos", ""]
    for qid in sorted(hallazgos):
        if hallazgos[qid]:
            lin.append(f"- **{qid}**: " + " · ".join(hallazgos[qid]))
    sin = [q for q in sorted(hallazgos) if not hallazgos[q]]
    lin += ["", f"Sin hallazgos: {', '.join(sin) or 'ninguna'}."]
    out = RAIZ / "evaluacion/banco" / f"auditoria_banco_17q_{fecha}.md"
    out.write_text("\n".join(lin) + "\n", encoding="utf-8")
    print("\n".join(lin))
    print("\nInforme:", out)


if __name__ == "__main__":
    main()
