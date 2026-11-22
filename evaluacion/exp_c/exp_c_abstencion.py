# -*- coding: utf-8 -*-
"""Experimento C de la Revisión 3 — abstención ante preguntas fuera de dominio (40) y ambiguas (20).

Dos pasos:

    # 1) construir el banco desde el pool de 260 (sin anotaciones de documento: no hacen falta)
    python exp_c_abstencion.py construir

    # 2) correrlo contra el backend (vía comparacion_v2_v3/correr_17q_e2e.py --negativas) y analizar
    python exp_c_abstencion.py analizar ../comparacion_v2_v3/E2E_C_s42_NEG_<fecha>.json [más corridas]

Criterio (evaluacion/retrieval/criterio_h5.md, ratificado 2026-09-27, opción A):
    fuera de dominio → correcta si el sistema NO da respuesta factual: M03 o M04 (M05 se cuenta como
                       correcta, porque tampoco responde, pero se informa aparte).
                       H5 confirmada si el límite inferior del IC95 % (Wilson) ≥ 0.90.
    ambiguas         → correcta si pide aclaración (M05) o se abstiene (M03/M04); se reportan aparte.
    M06 (error técnico) no cuenta como acierto ni como fallo: se excluye y se informa.

Advertencia de fuga: las 40 preguntas fuera de dominio del pool ya se vieron durante el desarrollo
(34 en la calibración del umbral y 6 = N01–N06 en las ablaciones). El análisis las marca
(`vista_en_desarrollo`) y reporta el resultado con y sin ellas; la decisión oficial de H5 exige
preguntas fuera de dominio nuevas en el gold set.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EVAL = AQUI.parent
sys.path.insert(0, str(EVAL / "estadistica"))
import estadistica as est  # noqa: E402

POOL = EVAL / "banco" / "pool_260_verificacion.json"
BANCO_SALIDA = EVAL / "banco" / "banco_exp_c_pool.json"
UMBRAL_H5 = 0.90
NO_RESPONDE = {"M03", "M04", "M05"}


def construir(_args):
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    negativas = []
    for x in pool:
        if x["bloque"] not in ("ood", "ambigua"):
            continue
        negativas.append({
            "id": x["pregunta_id"], "pregunta": x["texto"], "bloque": x["bloque"],
            "estado_pool": x["estado"],
            # 34 OOD en la calibración (calibrar_v3_bgem3.py: "pool 260 OOD sin semillas") + 6 semillas N01–N06
            "vista_en_desarrollo": x["bloque"] == "ood",
        })
    data = {"version": "exp_c_pool_v1", "fecha": date.today().isoformat(),
            "descripcion": "Experimento C (Revisión 3): 40 fuera de dominio + 20 ambiguas del pool de 260",
            "preguntas": [], "negativas": negativas}
    BANCO_SALIDA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{BANCO_SALIDA.name}: {Counter(n['bloque'] for n in negativas)}")


def _proporcion(nombre, ok, n):
    if n == 0:
        return {"grupo": nombre, "correctas": 0, "n": 0, "tasa": "", "ic95_lo": "", "ic95_hi": "", "decision_h5": ""}
    p, lo, hi = est.wilson_ic(ok, n)
    dec = "confirmada" if lo >= UMBRAL_H5 else "evidencia parcial" if p >= UMBRAL_H5 else "no confirmada"
    return {"grupo": nombre, "correctas": ok, "n": n, "tasa": round(p, 4), "ic95_lo": round(lo, 4),
            "ic95_hi": round(hi, 4), "decision_h5": dec}


def analizar(args):
    banco = {n["id"]: n for n in json.loads(Path(args.banco).read_text(encoding="utf-8"))["negativas"]}
    filas_det, resumen = [], []
    for ruta in args.corridas:
        corrida = json.loads(Path(ruta).read_text(encoding="utf-8"))
        etiqueta = Path(ruta).stem
        res = corrida["resultados"] if isinstance(corrida, dict) else corrida
        por = {"ood": [], "ambigua": []}
        errores = Counter()
        for r in res:
            meta = banco.get(r["id"])
            if not meta:
                continue
            tipo = r.get("tipo_mensaje") or "ERROR"
            if tipo not in NO_RESPONDE and tipo != "M02":
                errores[tipo] += 1
                correcta = ""
            else:
                correcta = int(tipo in NO_RESPONDE)
                por[meta["bloque"]].append((correcta, tipo, meta["vista_en_desarrollo"]))
            filas_det.append({"corrida": etiqueta, "id": r["id"], "bloque": meta["bloque"],
                              "vista_en_desarrollo": int(meta["vista_en_desarrollo"]), "tipo_mensaje": tipo,
                              "correcta": correcta, "pregunta": meta["pregunta"],
                              "respuesta": (r.get("respuesta") or "")[:300].replace("\n", " ")})
        ood, amb = por["ood"], por["ambigua"]
        for nombre, xs in [(f"fuera de dominio ({len(ood)})", ood),
                           ("fuera de dominio no vistas en desarrollo", [x for x in ood if not x[2]]),
                           (f"ambiguas ({len(amb)})", amb)]:
            fila = _proporcion(nombre, sum(x[0] for x in xs), len(xs))
            fila["corrida"] = etiqueta
            fila["por_tipo"] = dict(Counter(x[1] for x in xs))
            fila["excluidas_error"] = dict(errores) if nombre == f"fuera de dominio ({len(ood)})" else ""
            resumen.append(fila)
        amb_m05 = sum(1 for x in amb if x[1] == "M05")
        print(f"\n== {etiqueta}")
        for f in resumen[-3:]:
            print(f"  {f['grupo']:<42} {f['correctas']}/{f['n']} = {f['tasa']}  IC95 [{f['ic95_lo']}, {f['ic95_hi']}]"
                  f"  {f['por_tipo']}  {('H5: ' + f['decision_h5']) if 'fuera' in f['grupo'] else ''}")
        print(f"  ambiguas que piden aclaración (M05): {amb_m05}/{len(amb)}"
              + (f" · errores técnicos excluidos: {dict(errores)}" if errores else ""))
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, filas in (("resumen_exp_c.csv", resumen), ("detalle_exp_c.csv", filas_det)):
        with open(salida / nombre, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
    print(f"\nresultados en {salida}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("construir").set_defaults(fn=construir)
    p = sub.add_parser("analizar")
    p.add_argument("corridas", nargs="+")
    p.add_argument("--banco", default=str(BANCO_SALIDA),
                   help="banco con las negativas (por defecto el del pool; con el gold set: banco_gold_260.json)")
    p.add_argument("--salida", default=str(AQUI))
    p.set_defaults(fn=analizar)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
