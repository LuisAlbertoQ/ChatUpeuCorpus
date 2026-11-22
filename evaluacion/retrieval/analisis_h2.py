# -*- coding: utf-8 -*-
"""H2 de la Revisión 3: ¿hay un tamaño de chunk intermedio que maximiza la recuperación?

Lee las corridas de exp_a_recuperacion.py de un banco en los cuatro tamaños
(<banco>_c150o50, <banco>_c300o50, <banco>_chunk350, <banco>_c600o50) y escribe en exp_a/h2_<banco>/:

    tabla2.csv          media e IC95 bootstrap por recuperador × tamaño (R@1/3/5/10, MRR@10, nDCG@5, Rdoc@5)
    figura1.csv         Recall@5 por recuperador y tamaño, con IC95 (datos de la Figura 1 del .docx)
    comparaciones.csv   dentro de cada recuperador, cada tamaño contra los demás de la serie 150/300/600
                        (Wilcoxon pareado por pregunta + Holm por recuperador e IC95 de la diferencia)

La serie limpia es 150/300/600 con solape 50; la producción (350, solape 40) se reporta aparte
(no es un punto más de la serie: cambia también el solape).

    python analisis_h2.py --banco OE1_154
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "estadistica"))
import estadistica as est  # noqa: E402

TAMANOS = [("c150o50", 150), ("c300o50", 300), ("chunk350", 350), ("c600o50", 600)]
SERIE = ("c150o50", "c300o50", "c600o50")
RECS = [("S1", "bm25"), ("S2", "minilm"), ("S3", "mpnet"), ("S4", "bgem3")]
METRICAS = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr@10", "ndcg@5", "rdoc@5"]


def leer(path: Path) -> dict:
    with open(path, encoding="utf-8", newline="") as f:
        return {r["pregunta_id"]: r for r in csv.DictReader(f)}


def escribir(path: Path, filas: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        for r in filas:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco", required=True, help="prefijo de las etiquetas, p. ej. OE1_154 o B32")
    ap.add_argument("--exp-a", type=Path, default=AQUI / "exp_a")
    ap.add_argument("--metrica", default="recall@5", help="métrica de las comparaciones")
    ap.add_argument("--n-boot", type=int, default=est.N_BOOT)
    a = ap.parse_args(argv)

    datos = {}  # (rec, tamaño) -> {pid: fila}
    for etiqueta, _ in TAMANOS:
        carpeta = a.exp_a / f"{a.banco}_{etiqueta}"
        for sis, rec in RECS:
            p = carpeta / f"{sis}_{rec}.csv"
            if p.exists():
                datos[(rec, etiqueta)] = leer(p)
    if not datos:
        raise SystemExit(f"no hay corridas {a.banco}_* en {a.exp_a}")
    ids = sorted(set.intersection(*(set(d) for d in datos.values())))
    out = a.exp_a / f"h2_{a.banco}"
    out.mkdir(parents=True, exist_ok=True)

    tabla, figura = [], []
    for sis, rec in RECS:
        for etiqueta, tam in TAMANOS:
            d = datos.get((rec, etiqueta))
            if not d:
                continue
            fila = {"sistema": sis, "recuperador": rec, "chunk": tam, "version": etiqueta,
                    "serie_150_300_600": int(etiqueta in SERIE), "n": len(ids)}
            for m in METRICAS:
                media, lo, hi = est.bootstrap_ic([float(d[q][m]) for q in ids], n_boot=a.n_boot)
                fila[m] = media
                if m == a.metrica:
                    figura.append({"recuperador": rec, "chunk": tam, "version": etiqueta, m: media,
                                   "ic95_lo": lo, "ic95_hi": hi})
            tabla.append(fila)
    escribir(out / "tabla2.csv", tabla)
    escribir(out / "figura1.csv", figura)

    comps = []
    for sis, rec in RECS:
        serie = {e: {q: float(datos[(rec, e)][q][a.metrica]) for q in ids} for e in SERIE if (rec, e) in datos}
        if len(serie) < 2:
            continue
        for f in est.comparar_sistemas(serie, n_boot=a.n_boot):
            comps.append({"recuperador": rec, "metrica": a.metrica, **f})
    if comps:
        escribir(out / "comparaciones.csv", comps)

    print(f"H2 · banco {a.banco} · {len(ids)} preguntas · {a.metrica}\n")
    print(f"{'recuperador':<10}" + "".join(f"{t:>10}" for _, t in TAMANOS))
    for sis, rec in RECS:
        celdas = [next((f[a.metrica] for f in tabla if f["recuperador"] == rec and f["version"] == e), None)
                  for e, _ in TAMANOS]
        print(f"{rec:<10}" + "".join(f"{c:>10.3f}" if c is not None else f"{'—':>10}" for c in celdas))
    print("\n(350 = producción, solape 40; el resto solape 50)\n")
    for c in comps:
        marca = "  *" if c["significativo"] else ""
        print(f"  {c['recuperador']:<7} {c['comparacion']:<22} dif {c['diferencia']:+.3f} "
              f"[{c['ic95_lo']:+.3f}, {c['ic95_hi']:+.3f}]  p Holm {c['p_holm']:.4f}{marca}")
    print(f"\nresultados en {out}")


if __name__ == "__main__":
    main()
