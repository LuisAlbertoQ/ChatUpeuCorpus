# -*- coding: utf-8 -*-
"""Tablas 1–6 y figuras 1–3 del artículo (Revisión 3, .docx §11) a partir de los resultados ya calculados.

Hoy corre con los resultados PRELIMINARES (bancos de desarrollo); cuando existan los oficiales del gold set se
vuelve a correr cambiando las rutas y cada tabla se regenera igual. No recalcula experimentos: solo lee sus CSV/JSON.

    python generar_tablas.py                                   # preliminar (valores por defecto)
    python generar_tablas.py --banco ../banco/banco_gold_260.json --etiqueta-a GOLD \
        --exp-b ../generacion/exp_b_gold --exp-c ../exp_c/gold --corrida-final "../comparacion_v2_v3/E2E_GOLD_qwen_s42_*.json"

Salida (`salida/`): `TABLAS.md` (todo junto, para pegar en el artículo), `tablaN_*.csv`, `figura1_recall_chunk.svg`,
`figura2_recall_categoria.svg` y `figura3_ejemplos.md`.
"""
from __future__ import annotations

import argparse
import csv
import glob
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EVAL = AQUI.parent
sys.path.insert(0, str(EVAL / "estadistica"))
import estadistica as est  # noqa: E402

_spec = importlib.util.spec_from_file_location("exp_b", EVAL / "generacion" / "exp_b_generacion.py")
exp_b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp_b)

CHUNKS_CANDIDATOS = [
    EVAL.parent.parent / "oe1_arquitectura_corpus" / "corpus_upeu" / "metadatos" / "v3" / "chunks_v3_bgem3.csv",
    Path("/oe1/chunks_v3_bgem3.csv"),
]
CATEGORIAS = {"A": "Gobierno y estatuto", "B": "Académico", "C": "Investigación", "D": "Bienestar",
              "E": "Laboral, docencia y políticas"}
RECUPERADORES = {"bm25": "BM25 (S1)", "minilm": "MiniLM (S2)", "mpnet": "mpnet (S3)", "bgem3": "bge-m3 (S4)"}
COLORES = {"bm25": "#6b7280", "minilm": "#d97706", "mpnet": "#2563eb", "bgem3": "#059669"}
ABSTENCION = {"M03", "M04", "M05"}


# ---------------------------------------------------------------- utilidades
def leer_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv(path: Path, filas: list[dict]) -> None:
    if not filas:
        return
    campos = list(dict.fromkeys(k for r in filas for k in r))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def md_tabla(filas: list[dict], columnas: list[str] | None = None) -> str:
    if not filas:
        return "_(sin datos todavía)_"
    columnas = columnas or list(filas[0])
    lineas = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    for r in filas:
        lineas.append("| " + " | ".join(str(r.get(c, "")) for c in columnas) + " |")
    return "\n".join(lineas)


def f3(x) -> str:
    try:
        return f"{float(x):.3f}"
    except (TypeError, ValueError):
        return "—"


def ic(lo, hi) -> str:
    return f"[{f3(lo)}, {f3(hi)}]"


# ---------------------------------------------------------------- tablas
def tabla1(banco: dict, chunks: Path | None) -> list[dict]:
    """Corpus (documentos y chunks por categoría) y composición del banco de preguntas."""
    docs, n_chunks = defaultdict(set), Counter()
    if chunks and chunks.exists():
        csv.field_size_limit(10 ** 9)
        with open(chunks, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                c = r.get("categoria_tematica") or "-"
                docs[c].add(r["nombre_documento"])
                n_chunks[c] += 1
    preg = Counter(q.get("categoria") or "-" for q in banco.get("preguntas", []))
    filas = []
    for c in sorted(set(docs) | set(preg)):
        filas.append({"categoria": f"{c} {CATEGORIAS.get(c, '')}".strip(), "documentos": len(docs[c]) or "—",
                      "chunks": n_chunks[c] or "—", "preguntas_dominio": preg[c]})
    filas.append({"categoria": "**Total**", "documentos": sum(len(v) for v in docs.values()) or "—",
                  "chunks": sum(n_chunks.values()) or "—", "preguntas_dominio": sum(preg.values())})
    return filas


def composicion(banco: dict) -> list[dict]:
    neg = banco.get("negativas", [])
    bloques = Counter(n.get("bloque") or ("ood" if n.get("cobertura_esperada") == "NO_ANSWER" else "-") for n in neg)
    tipos = Counter(q.get("tipo_pregunta") or "-" for q in banco.get("preguntas", []))
    filas = [{"grupo": "Dominio (con respuesta)", "n": len(banco.get("preguntas", [])),
              "detalle": ", ".join(f"{k} {v}" for k, v in sorted(tipos.items()))}]
    filas += [{"grupo": {"ood": "Fuera de dominio", "ambigua": "Ambiguas"}.get(b, b), "n": n,
               "detalle": (f"no vistas en desarrollo: {sum(1 for x in neg if x.get('bloque') == b and not x.get('vista_en_desarrollo', True))}"
                           if b == "ood" else "")} for b, n in sorted(bloques.items())]
    return filas


def tabla2(exp_a: Path, etq: str) -> list[dict]:
    filas = []
    for r in leer_csv(exp_a / f"h2_{etq}" / "tabla2.csv"):
        filas.append({"recuperador": RECUPERADORES.get(r["recuperador"], r["recuperador"]), "chunk": r["chunk"],
                      "n": r["n"], **{m: f3(r[m]) for m in ("recall@1", "recall@3", "recall@5", "recall@10",
                                                            "mrr@10", "ndcg@5")}})
    return filas


def figura1(exp_a: Path, etq: str, destino: Path) -> None:
    datos = defaultdict(list)
    for r in leer_csv(exp_a / f"h2_{etq}" / "figura1.csv"):
        datos[r["recuperador"]].append((int(r["chunk"]), float(r["recall@5"]), float(r["ic95_lo"]), float(r["ic95_hi"])))
    if not datos:
        return
    W, H, L, R, T, B = 560, 360, 60, 150, 30, 50
    tam = sorted({c for pts in datos.values() for c, *_ in pts})
    x = {c: L + (W - L - R) * i / max(1, len(tam) - 1) for i, c in enumerate(tam)}
    y = lambda v: T + (1 - v) * (H - T - B)  # noqa: E731
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for v in (0, .25, .5, .75, 1):
        p.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v)}" y2="{y(v)}" stroke="#e5e7eb"/>'
                 f'<text x="{L - 8}" y="{y(v) + 4}" text-anchor="end" fill="#374151">{v:.2f}</text>')
    for c, xx in x.items():
        p.append(f'<text x="{xx}" y="{H - B + 18}" text-anchor="middle" fill="#374151">{c}</text>')
    p.append(f'<text x="{(L + W - R) / 2}" y="{H - 10}" text-anchor="middle" fill="#111">Tamaño de chunk (tokens)</text>'
             f'<text x="14" y="{(T + H - B) / 2}" transform="rotate(-90 14 {(T + H - B) / 2})" text-anchor="middle" fill="#111">Recall@5</text>')
    for i, (rec, pts) in enumerate(sorted(datos.items(), key=lambda kv: list(RECUPERADORES).index(kv[0])
                                          if kv[0] in RECUPERADORES else 9)):
        col = COLORES.get(rec, "#000")
        pts.sort()
        p.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="'
                 + " ".join(f"{x[c]},{y(v)}" for c, v, _, _ in pts) + '"/>')
        for c, v, lo, hi in pts:
            p.append(f'<line x1="{x[c]}" x2="{x[c]}" y1="{y(lo)}" y2="{y(hi)}" stroke="{col}" opacity=".5"/>'
                     f'<circle cx="{x[c]}" cy="{y(v)}" r="4" fill="{col}"/>')
        ly = T + 10 + i * 20
        p.append(f'<rect x="{W - R + 15}" y="{ly - 8}" width="12" height="3" fill="{col}"/>'
                 f'<text x="{W - R + 32}" y="{ly - 3}" fill="#111">{RECUPERADORES.get(rec, rec)}</text>')
    p.append("</svg>")
    destino.write_text("\n".join(p), encoding="utf-8")


def tabla4(exp_a: Path, etq: str, n_boot: int) -> list[dict]:
    """Desempeño por categoría del sistema final (bge-m3, chunks de producción)."""
    filas_q = leer_csv(exp_a / f"{etq}_chunk350" / "S4_bgem3.csv")
    por_cat = defaultdict(list)
    for r in filas_q:
        por_cat[r["categoria"]].append(r)
    filas = []
    for c in sorted(por_cat):
        rs = por_cat[c]
        r5, lo, hi = est.bootstrap_ic([float(r["recall@5"]) for r in rs], n_boot=n_boot)
        filas.append({"categoria": f"{c} {CATEGORIAS.get(c, '')}".strip(), "n": len(rs), "recall@5": f3(r5),
                      "ic95": ic(lo, hi), "mrr@10": f3(sum(float(r["mrr@10"]) for r in rs) / len(rs)),
                      "rdoc@5": f3(sum(float(r["rdoc@5"]) for r in rs) / len(rs)),
                      "_r5": r5, "_lo": lo, "_hi": hi})
    return filas


def figura2(filas: list[dict], destino: Path) -> None:
    if not filas:
        return
    W, H, L, T, B = 560, 340, 60, 30, 70
    ancho = (W - L - 20) / len(filas)
    y = lambda v: T + (1 - v) * (H - T - B)  # noqa: E731
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for v in (0, .25, .5, .75, 1):
        p.append(f'<line x1="{L}" x2="{W - 20}" y1="{y(v)}" y2="{y(v)}" stroke="#e5e7eb"/>'
                 f'<text x="{L - 8}" y="{y(v) + 4}" text-anchor="end" fill="#374151">{v:.2f}</text>')
    for i, r in enumerate(filas):
        cx = L + ancho * (i + .5)
        p.append(f'<rect x="{cx - ancho * .3}" y="{y(r["_r5"])}" width="{ancho * .6}" height="{y(0) - y(r["_r5"])}" fill="#059669"/>'
                 f'<line x1="{cx}" x2="{cx}" y1="{y(r["_lo"])}" y2="{y(r["_hi"])}" stroke="#111"/>'
                 f'<line x1="{cx - 6}" x2="{cx + 6}" y1="{y(r["_lo"])}" y2="{y(r["_lo"])}" stroke="#111"/>'
                 f'<line x1="{cx - 6}" x2="{cx + 6}" y1="{y(r["_hi"])}" y2="{y(r["_hi"])}" stroke="#111"/>'
                 f'<text x="{cx}" y="{H - B + 18}" text-anchor="middle" fill="#111">{r["categoria"][0]}</text>'
                 f'<text x="{cx}" y="{H - B + 34}" text-anchor="middle" fill="#6b7280">n={r["n"]}</text>')
    p.append(f'<text x="14" y="{(T + H - B) / 2}" transform="rotate(-90 14 {(T + H - B) / 2})" text-anchor="middle" '
             f'fill="#111">Recall@5 (IC95)</text><text x="{(L + W) / 2}" y="{H - 8}" text-anchor="middle" fill="#111">'
             f'Categoría documental</text></svg>')
    destino.write_text("\n".join(p), encoding="utf-8")


def tabla3(exp_b: Path, fidelidad: Path) -> tuple[list[dict], list[dict]]:
    fid = {r["sistema"]: r for r in leer_csv(fidelidad / "resumen_fidelidad.csv")}
    filas = []
    for r in leer_csv(exp_b / "resumen_exp_b.csv"):
        h = fid.get(r["sistema"], {})
        filas.append({"sistema": r["sistema"],
                      "fidelidad (humana)": f3(h["fidelidad"]) if h else "pendiente",
                      "corrección (humana)": f3(h["correccion"]) if h else "pendiente",
                      "relevancia 1–5 (humana)": f3(h["relevancia"]) if h else "pendiente",
                      "completitud (auto)": f3(r["completitud"]), "atrib. exacta": f3(r["atrib_exacta"]),
                      "atrib. parcial": f3(r["atrib_parcial"]), "sin cita": f3(r["atrib_ausente"]),
                      "latencia p50 / p95 (s)": f"{float(r['latencia_p50']):.1f} / {float(r['latencia_p95']):.1f}",
                      "timeouts": f3(r["error_m06"]), "negativas": r["negativas_abstenidas"]})
    comps = [{"métrica": c["metrica"], "comparación": c["comparacion"], "diferencia": f3(c["diferencia"]),
              "IC95": ic(c["ic95_lo"], c["ic95_hi"]), "p Holm": f3(c["p_holm"]), "r": f3(c["r_rango_biserial"]),
              "significativo": "sí" if c["significativo"] == "True" else "no"}
             for c in leer_csv(exp_b / "comparaciones_exp_b.csv") + leer_csv(fidelidad / "comparaciones_fidelidad.csv")]
    return filas, comps


def tabla5(exp_c: Path) -> list[dict]:
    vistos, filas = set(), []
    for r in leer_csv(exp_c / "resumen_exp_c.csv"):
        if r["grupo"] in vistos:  # una fila por grupo (semillas repetidas dan lo mismo)
            continue
        vistos.add(r["grupo"])
        filas.append({"grupo": r["grupo"], "correctas / n": f"{r['correctas']}/{r['n']}", "tasa": f3(r["tasa"]),
                      "IC95 Wilson": ic(r["ic95_lo"], r["ic95_hi"]) if r["ic95_lo"] else "—",
                      "H5 (≥ 0.90)": r["decision_h5"] or "—", "respuestas": r["por_tipo"]})
    return filas


def errores_corrida(patron: str, banco: dict, fidelidad: Path, sistema: str = "qwen") -> tuple[list[dict], list[dict]]:
    """Tabla 6: clasifica cada respuesta del sistema final en un tipo de error (o correcta)."""
    archivos = [f for f in sorted(glob.glob(patron)) if "_NEG_" not in f]
    if not archivos:
        return [], []
    data = json.loads(Path(archivos[0]).read_text(encoding="utf-8"))
    # generación infiel: fidelidad 0 de algún evaluador en la evaluación humana (si ya se hizo)
    det_fid = leer_csv(fidelidad / "detalle_fidelidad.csv")
    infieles = {r["pregunta_id"] for r in det_fid
                if r["sistema"] == sistema and "0" in (r["fidelidad_E1"], r["fidelidad_E2"])}
    preg = {q["id"]: q for q in banco.get("preguntas", [])}
    detalle = []
    for r in data["resultados"]:
        q = preg.get(r["id"])
        if not q:
            continue
        tipo, resp = r.get("tipo_mensaje"), r.get("respuesta") or ""
        if tipo == "M06" or r.get("error"):
            clase = "error técnico"
        elif str(r.get("hit_documento_top4")) not in ("True", "1"):
            clase = "recuperación fallida"
        elif tipo in ABSTENCION:
            clase = "falsa abstención"
        elif r["id"] in infieles:
            clase = "generación infiel"
        else:
            at = exp_b.atribucion(resp, q["documentos_esperados"], [a["articulo"] for a in q["articulos_esperados"]])
            clase = {"exacta": "correcta y sustentada", "parcial": "atribución parcial"}.get(at, f"atribución {at}")
        detalle.append({"id": r["id"], "clase": clase, "pregunta": q["pregunta"], "respuesta": resp})
    cuenta = Counter(d["clase"] for d in detalle)
    orden = ["recuperación fallida", "generación infiel", "atribución incorrecta", "atribución ausente",
             "atribución parcial", "falsa abstención", "error técnico", "correcta y sustentada"]
    n = len(detalle)
    filas = [{"tipo": c, "n": cuenta[c], "%": f"{100 * cuenta[c] / n:.0f} %" if n else "—"}
             for c in orden if c in cuenta or c == "generación infiel"]
    for f in filas:
        if f["tipo"] == "generación infiel" and not det_fid:
            f["n"], f["%"] = "pendiente", "requiere evaluación humana"
    return filas, detalle


def figura3(detalle: list[dict], destino: Path) -> None:
    lineas = ["# Figura 3 — ejemplos cualitativos (candidatos; elegir y editar para el artículo)", ""]
    vistos = set()
    for d in detalle:
        if d["clase"] in vistos:
            continue
        vistos.add(d["clase"])
        resp = d["respuesta"][:700] + ("…" if len(d["respuesta"]) > 700 else "")
        lineas += [f"## {d['clase']} ({d['id']})", "", f"**Pregunta:** {d['pregunta']}", "", "**Respuesta:**", "",
                   "> " + resp.replace("\n", "\n> "), ""]
    destino.write_text("\n".join(lineas), encoding="utf-8")


# ---------------------------------------------------------------- main
def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco", default=str(EVAL / "banco" / "banco_v32.json"))
    ap.add_argument("--exp-a", default=str(EVAL / "retrieval" / "exp_a"))
    ap.add_argument("--etiqueta-a", default="OE1_154", help="prefijo de las corridas del Exp. A (OE1_154, B32, GOLD…)")
    ap.add_argument("--exp-b", default=str(EVAL / "generacion" / "exp_b_nuevos"))
    ap.add_argument("--exp-c", default=str(EVAL / "exp_c"))
    ap.add_argument("--fidelidad", default=str(EVAL / "humana" / "fidelidad_rev3"))
    ap.add_argument("--corrida-final", default=str(EVAL / "comparacion_v2_v3" / "E2E_B_qwen_s42_*.json"))
    ap.add_argument("--sistema-final", default="qwen", help="nombre del sistema final en la evaluación de fidelidad")
    ap.add_argument("--chunks", default="")
    ap.add_argument("--salida", default=str(AQUI / "salida"))
    ap.add_argument("--n-boot", type=int, default=est.N_BOOT)
    a = ap.parse_args(argv)

    banco = json.loads(Path(a.banco).read_text(encoding="utf-8"))
    oficial = "gold" in str(banco.get("version", "")).lower()
    exp_a, exp_bp, exp_cp, fid = Path(a.exp_a), Path(a.exp_b), Path(a.exp_c), Path(a.fidelidad)
    chunks = Path(a.chunks) if a.chunks else next((p for p in CHUNKS_CANDIDATOS if p.exists()), None)
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    t1, comp = tabla1(banco, chunks), composicion(banco)
    t2 = tabla2(exp_a, a.etiqueta_a)
    figura1(exp_a, a.etiqueta_a, salida / "figura1_recall_chunk.svg")
    t3, t3c = tabla3(exp_bp, fid)
    t4 = tabla4(exp_a, a.etiqueta_a, a.n_boot)
    figura2(t4, salida / "figura2_recall_categoria.svg")
    t5 = tabla5(exp_cp)
    t6, detalle = errores_corrida(a.corrida_final, banco, fid, a.sistema_final)
    figura3(detalle, salida / "figura3_ejemplos.md")

    t4_pub = [{k: v for k, v in r.items() if not k.startswith("_")} for r in t4]
    for nombre, filas in (("tabla1_corpus.csv", t1), ("tabla1_composicion.csv", comp), ("tabla2_recuperacion.csv", t2),
                          ("tabla3_generadores.csv", t3), ("tabla3_comparaciones.csv", t3c),
                          ("tabla4_categorias.csv", t4_pub), ("tabla5_abstencion.csv", t5), ("tabla6_errores.csv", t6)):
        escribir_csv(salida / nombre, filas)

    estado = ("Resultados **oficiales** (gold set)." if oficial else
              "⚠️ **PRELIMINAR**: bancos de desarrollo, no el gold set. Las cifras cambiarán; la estructura no.")
    md = [f"# Tablas y figuras del artículo (Revisión 3, .docx §11)", "", estado, "",
          f"Fuentes: banco `{Path(a.banco).name}` · Exp. A `{a.etiqueta_a}` · Exp. B `{exp_bp.name}` · "
          f"Exp. C `{exp_cp.name}` · sistema final `{Path(a.corrida_final).name}`. Regenerar: `tablas/generar_tablas.py`.", "",
          "## Tabla 1. Corpus y composición del banco de preguntas", "", md_tabla(t1), "", md_tabla(comp), "",
          f"## Tabla 2. Recuperadores × tamaño de chunk (H1, H2; {t2[0]['n'] if t2 else '?'} preguntas)", "",
          md_tabla(t2), "", "## Figura 1. Recall@5 frente al tamaño de chunk", "",
          "![Figura 1](figura1_recall_chunk.svg)", "",
          "## Tabla 3. Generadores locales con la misma recuperación (H3)", "", md_tabla(t3), "",
          "Comparaciones contra Qwen2.5-7B (Wilcoxon + Holm, IC95 bootstrap):", "", md_tabla(t3c), "",
          "## Tabla 4. Desempeño por categoría documental del sistema final (H4)", "", md_tabla(t4_pub), "",
          "## Figura 2. Recall@5 por categoría con IC95", "", "![Figura 2](figura2_recall_categoria.svg)", "",
          "## Tabla 5. Abstención y control de dominio (H5)", "", md_tabla(t5), "",
          "## Tabla 6. Análisis de errores del sistema final", "", md_tabla(t6), "",
          "## Figura 3. Ejemplos cualitativos", "", "Candidatos por tipo de error en `figura3_ejemplos.md`.", ""]
    (salida / "TABLAS.md").write_text("\n".join(md), encoding="utf-8")
    print(estado)
    print(f"tablas y figuras en {salida}")


if __name__ == "__main__":
    main()
