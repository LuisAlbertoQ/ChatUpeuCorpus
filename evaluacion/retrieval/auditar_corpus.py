#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoría del corpus indexado (Revisión 3, §2).

Reporta, solo lectura sobre `corpus_upeu_v2`:
- documentos procesados con OCR (ruta_extraccion con OCR/ESCANEADO/MIXTO);
- % de fragmentos con alineación artículo/capítulo, global y por documento.

Uso: docker compose exec backend python /data/evaluacion/retrieval/auditar_corpus.py [--guardar]
  Sin flags: solo imprime. Con --guardar: además persiste reporte .md + detalle .csv
  versionados por fecha en el mismo directorio (trazabilidad para el paper).
"""
import csv
import datetime
import sys
from collections import Counter
from pathlib import Path

import chromadb

COLECCION = "corpus_upeu_v2"
OUT_DIR = Path(__file__).parent

RUTAS_CON_OCR = ("OCR", "ESCANEADO", "MIXTO")


def main() -> int:
    guardar = "--guardar" in sys.argv
    client = chromadb.PersistentClient(path="/data/vector_store")
    col = client.get_collection(COLECCION)
    total = col.count()
    res = col.get(include=["metadatas"], limit=max(total, 1))
    metas = res["metadatas"]

    rutas = Counter(m.get("ruta_extraccion", "?") for m in metas)
    bloques = Counter(m.get("tipo_bloque", "?") for m in metas)
    docs = {}
    for m in metas:
        d = docs.setdefault(m.get("documento", "?"), {"rutas": set(), "alineados": 0, "total": 0})
        d["rutas"].add(m.get("ruta_extraccion", "?"))
        d["total"] += 1
        if m.get("articulo") or m.get("capitulo"):
            d["alineados"] += 1

    con_ocr = sorted(d for d, v in docs.items() if v["rutas"] & set(RUTAS_CON_OCR))
    alineados = sum(v["alineados"] for v in docs.values())
    fecha = datetime.date.today().isoformat()

    lineas = [
        f"# Auditoría del corpus — {fecha}",
        "",
        f"- colección: `{COLECCION}`",
        f"- documentos: **{len(docs)}**",
        f"- fragmentos: **{total}**",
        f"- rutas de extracción: {dict(sorted(rutas.items()))}",
        f"- tipos de bloque: {dict(sorted(bloques.items()))}",
        f"- docs con OCR {RUTAS_CON_OCR}: **{len(con_ocr)}**",
        "",
        "## Documentos con OCR",
        "",
    ]
    for d in con_ocr:
        lineas.append(f"- {d} `{sorted(docs[d]['rutas'])}`")
    lineas += [
        "",
        f"## Alineación artículo/capítulo: {alineados}/{total} = {alineados / total * 100:.1f}%",
        "",
        "| documento | alineados | total | rutas |",
        "|---|---|---|---|",
    ]
    for d in sorted(docs):
        v = docs[d]
        lineas.append(f"| {d} | {v['alineados']} | {v['total']} | {', '.join(sorted(v['rutas']))} |")

    for ln in lineas:
        print(ln)

    if guardar:
        md = OUT_DIR / f"auditoria_corpus_{fecha}.md"
        md.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        csv_path = OUT_DIR / f"auditoria_corpus_{fecha}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["documento", "fragmentos", "alineados", "pct_alineacion", "rutas"])
            for d in sorted(docs):
                v = docs[d]
                w.writerow([d, v["total"], v["alineados"],
                            round(v["alineados"] / v["total"] * 100, 1),
                            ";".join(sorted(v["rutas"]))])
        print(f"\nGuardado: {md.name} + {csv_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
