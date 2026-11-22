# -*- coding: utf-8 -*-
"""Análisis estadístico de la Revisión 3 (§9): IC95 bootstrap, Wilcoxon pareado, Holm y tamaño de efecto.

Uso como librería (lo importan los scripts de los experimentos) o desde la línea de comandos:

    # Compara una métrica por pregunta entre sistemas (un CSV por sistema, columnas pregunta_id + métrica)
    python estadistica.py comparar --metrica recall@5 --base S1=exp_a/S1.csv \
        S2=exp_a/S2.csv S3=exp_a/S3.csv S4=exp_a/S4.csv --salida tabla.csv

    # Proporción con IC de Wilson (H5): 38 correctas de 40
    python estadistica.py proporcion 38 40 --umbral 0.90

Reglas del .docx: IC95 % por bootstrap sobre las preguntas; Wilcoxon para comparaciones pareadas;
Holm dentro de cada experimento; tamaño de efecto además del p; no declarar superioridad solo con
diferencias descriptivas. Solo usa la librería estándar (scipy es opcional: si está, se usa para
contrastar el p de Wilcoxon).
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from itertools import product
from pathlib import Path
from statistics import NormalDist, mean

SEMILLA = 20261122
N_BOOT = 10_000


# --------------------------------------------------------------------------- IC
def bootstrap_ic(valores, n_boot: int = N_BOOT, alfa: float = 0.05, semilla: int = SEMILLA,
                 estadistico=mean) -> tuple[float, float, float]:
    """Estimador puntual e IC percentil (1-alfa) remuestreando preguntas con reemplazo."""
    v = [float(x) for x in valores]
    if not v:
        raise ValueError("bootstrap_ic: lista vacía")
    rng = random.Random(semilla)
    n = len(v)
    reps = sorted(estadistico([v[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    lo = reps[int(math.floor(alfa / 2 * n_boot))]
    hi = reps[min(n_boot - 1, int(math.ceil((1 - alfa / 2) * n_boot)) - 1)]
    return estadistico(v), lo, hi


def bootstrap_diferencia(a, b, **kw) -> tuple[float, float, float]:
    """IC bootstrap de la diferencia media pareada (b - a): remuestrea pares, no valores sueltos."""
    if len(a) != len(b):
        raise ValueError("bootstrap_diferencia: las listas deben estar pareadas")
    return bootstrap_ic([float(y) - float(x) for x, y in zip(a, b)], **kw)


def wilson_ic(exitos: int, n: int, alfa: float = 0.05) -> tuple[float, float, float]:
    """Proporción con IC de Wilson (recomendado para H5: n pequeño y p cerca de 1)."""
    if n <= 0:
        raise ValueError("wilson_ic: n debe ser > 0")
    z = NormalDist().inv_cdf(1 - alfa / 2)
    p = exitos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centro - medio), min(1.0, centro + medio)


# --------------------------------------------------------------------------- Wilcoxon
def _rangos(valores):
    """Rangos promedio (empates comparten el rango medio)."""
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    r = [0.0] * len(valores)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and valores[orden[j + 1]] == valores[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            r[orden[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def wilcoxon_pareado(a, b) -> dict:
    """Wilcoxon de rangos con signo (dos colas) para b - a, descartando diferencias cero (Wilcoxon/Pratt "wilcox").

    p exacto por enumeración si n <= 20 sin empates; si no, aproximación normal con corrección de
    empates (sin corrección de continuidad, igual que scipy por defecto). Devuelve también el tamaño de efecto r de rango biserial
    (r = (W+ - W-) / (W+ + W-), entre -1 y 1; positivo = b mayor que a).
    """
    if len(a) != len(b):
        raise ValueError("wilcoxon_pareado: las listas deben estar pareadas")
    # redondeo: 0.6-0.3 y 0.5-0.2 deben contar como empate aunque difieran en el último bit
    d = [round(float(y) - float(x), 10) for x, y in zip(a, b)]
    d = [x for x in d if x != 0]
    n = len(d)
    res = {"n_pares": len(a), "n_no_cero": n, "w_mas": 0.0, "w_menos": 0.0,
           "p": 1.0, "metodo": "sin diferencias", "r_rango_biserial": 0.0}
    if n == 0:
        return res
    r = _rangos([abs(x) for x in d])
    w_mas = sum(ri for ri, x in zip(r, d) if x > 0)
    w_menos = sum(ri for ri, x in zip(r, d) if x < 0)
    total = w_mas + w_menos
    res.update(w_mas=w_mas, w_menos=w_menos, r_rango_biserial=(w_mas - w_menos) / total)
    hay_empates = len(set(r)) < n
    w = min(w_mas, w_menos)
    if n <= 20 and not hay_empates:
        # distribución exacta de W+ bajo H0: cada rango entra con signo + o - con prob. 1/2
        cuenta = {0: 1}
        for k in range(1, n + 1):
            nueva = dict(cuenta)
            for s, c in cuenta.items():
                nueva[s + k] = nueva.get(s + k, 0) + c
            cuenta = nueva
        cola = sum(c for s, c in cuenta.items() if s <= w) / 2 ** n
        res.update(p=min(1.0, 2 * cola), metodo="exacto")
    else:
        media = n * (n + 1) / 4
        var = n * (n + 1) * (2 * n + 1) / 24
        # corrección por empates
        from collections import Counter
        var -= sum(t ** 3 - t for t in Counter(r).values()) / 48
        if var <= 0:
            return res
        z = abs(w - media) / math.sqrt(var)
        res.update(p=min(1.0, 2 * (1 - NormalDist().cdf(max(z, 0.0)))), metodo="normal", z=z)
    try:  # contraste opcional con scipy
        from scipy.stats import wilcoxon as _w
        res["p_scipy"] = float(_w([round(float(y) - float(x), 10) for x, y in zip(a, b)],
                                   zero_method="wilcox", alternative="two-sided").pvalue)
    except Exception:
        pass
    return res


# --------------------------------------------------------------------------- Holm y efecto
def holm(pvalores: dict) -> dict:
    """Ajuste de Holm-Bonferroni. Recibe {nombre: p} y devuelve {nombre: p_ajustado} (monótono, tope 1)."""
    orden = sorted(pvalores, key=lambda k: pvalores[k])
    m = len(orden)
    ajust, previo = {}, 0.0
    for i, k in enumerate(orden):
        previo = max(previo, min(1.0, (m - i) * pvalores[k]))
        ajust[k] = previo
    return ajust


def cohen_dz(a, b) -> float:
    """d de Cohen para muestras pareadas (media de diferencias / DE de diferencias)."""
    d = [float(y) - float(x) for x, y in zip(a, b)]
    if len(d) < 2:
        return 0.0
    m = mean(d)
    de = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
    return 0.0 if de == 0 else m / de


def magnitud_r(r: float) -> str:
    """Lectura convencional del r de rango biserial."""
    r = abs(r)
    return "despreciable" if r < 0.1 else "pequeño" if r < 0.3 else "mediano" if r < 0.5 else "grande"


def comparar_sistemas(por_sistema: dict, base: str | None = None, alfa: float = 0.05, **kw_boot) -> list[dict]:
    """Compara una métrica por pregunta entre sistemas ya pareados ({sistema: {pregunta_id: valor}}).

    Si `base` se indica, compara cada sistema contra la base; si no, todos contra todos.
    Holm se aplica sobre el conjunto de comparaciones de esta llamada (= un experimento).
    """
    ids = sorted(set.intersection(*(set(v) for v in por_sistema.values())))
    if not ids:
        raise ValueError("comparar_sistemas: no hay preguntas en común")
    nombres = list(por_sistema)
    pares = ([(base, s) for s in nombres if s != base] if base
             else [(x, y) for i, x in enumerate(nombres) for y in nombres[i + 1:]])
    filas = []
    for x, y in pares:
        a = [por_sistema[x][q] for q in ids]
        b = [por_sistema[y][q] for q in ids]
        w = wilcoxon_pareado(a, b)
        dif, lo, hi = bootstrap_diferencia(a, b, **kw_boot)
        filas.append({"comparacion": f"{y} vs {x}", "n": len(ids), "media_a": mean(a), "media_b": mean(b),
                      "diferencia": dif, "ic95_lo": lo, "ic95_hi": hi, "p": w["p"], "metodo": w["metodo"],
                      "r_rango_biserial": w["r_rango_biserial"], "magnitud": magnitud_r(w["r_rango_biserial"]),
                      "d_z": cohen_dz(a, b)})
    ajustados = holm({f["comparacion"]: f["p"] for f in filas})
    for f in filas:
        f["p_holm"] = ajustados[f["comparacion"]]
        # significativo solo si Holm lo confirma Y el IC de la diferencia no incluye 0
        f["significativo"] = f["p_holm"] < alfa and not (f["ic95_lo"] <= 0 <= f["ic95_hi"])
    return filas


def resumen_sistemas(por_sistema: dict, **kw_boot) -> list[dict]:
    """Media e IC95 bootstrap por sistema."""
    filas = []
    for s, vals in por_sistema.items():
        m, lo, hi = bootstrap_ic(list(vals.values()), **kw_boot)
        filas.append({"sistema": s, "n": len(vals), "media": m, "ic95_lo": lo, "ic95_hi": hi})
    return filas


# --------------------------------------------------------------------------- CLI
def _leer(path: Path, metrica: str) -> dict:
    with open(path, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    if not filas or metrica not in filas[0]:
        raise SystemExit(f"{path}: no tiene la columna {metrica!r}")
    clave = "pregunta_id" if "pregunta_id" in filas[0] else "id"
    return {r[clave]: float(r[metrica]) for r in filas if r.get(metrica) not in ("", None)}


def _escribir(filas, salida):
    if not filas:
        return
    out = open(salida, "w", encoding="utf-8", newline="") if salida else sys.stdout
    w = csv.DictWriter(out, fieldnames=list(filas[0]))
    w.writeheader()
    for f in filas:
        w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in f.items()})
    if salida:
        out.close()


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("comparar", help="métrica por pregunta entre sistemas")
    c.add_argument("--metrica", required=True)
    c.add_argument("--base", help="sistema de referencia (si no, todos contra todos)")
    c.add_argument("--salida")
    c.add_argument("sistemas", nargs="+", help="NOMBRE=archivo.csv")
    p = sub.add_parser("proporcion", help="proporción con IC de Wilson (H5)")
    p.add_argument("exitos", type=int)
    p.add_argument("n", type=int)
    p.add_argument("--umbral", type=float, default=0.90)
    a = ap.parse_args(argv)

    if a.cmd == "proporcion":
        prop, lo, hi = wilson_ic(a.exitos, a.n)
        decision = ("confirmada" if lo >= a.umbral else "evidencia parcial" if prop >= a.umbral else "no confirmada")
        print(f"{a.exitos}/{a.n} = {prop:.3f}  IC95 Wilson [{lo:.3f}, {hi:.3f}]  umbral {a.umbral:.2f} -> {decision}")
        return
    datos = {}
    for s in a.sistemas:
        nombre, _, ruta = s.partition("=")
        datos[nombre] = _leer(Path(ruta), a.metrica)
    print("# Resumen por sistema")
    _escribir(resumen_sistemas(datos), None)
    print("\n# Comparaciones pareadas (Wilcoxon + Holm, IC95 bootstrap de la diferencia)")
    _escribir(comparar_sistemas(datos, base=a.base), a.salida)


if __name__ == "__main__":
    main()
