# -*- coding: utf-8 -*-
"""Experimento B de la Revisión 3 (H3): Qwen2.5-7B vs Llama 3 8B con la misma recuperación, y control S0.

Lee corridas end-to-end de comparacion_v2_v3/correr_17q_e2e.py (una o más semillas por sistema) y compara,
por pregunta (promediando las semillas):

    completitud      proporción de puntos del banco CUBIERTOS (proxy automático, kappa 0.53 vs humano)
    atrib_exacta     la respuesta cita un artículo esperado (.docx §7: atribución exacta)
    atrib_parcial    cita el documento esperado pero no el artículo (parcial)
    atrib_ausente    no cita ningún artículo ni documento
    falsa_abstencion responde M03/M04/M05 a una pregunta con respuesta en el corpus
    palabras, latencia (s) y errores técnicos (M06)

Comparaciones pareadas contra la referencia (por defecto qwen): Wilcoxon + Holm e IC95 bootstrap.
La fidelidad (si lo dicho está en las fuentes) NO se mide aquí: requiere evaluación humana (.docx §8).

    python exp_b_generacion.py --banco ../banco/banco_v32.json \
        qwen=E2E_B_qwen_s42_*.json,E2E_B_qwen_s7_*.json llama=E2E_B_llama_s42_*.json,... s0=...
"""
from __future__ import annotations

import argparse
import csv
import glob
import importlib.util
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EVAL = AQUI.parent
sys.path.insert(0, str(EVAL / "estadistica"))
import estadistica as est  # noqa: E402

_spec = importlib.util.spec_from_file_location("completitud_auto", EVAL / "comparacion_v2_v3" / "completitud_auto.py")
comp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(comp)

ABSTENCION = {"M03", "M04", "M05"}
METRICAS = ["completitud", "atrib_exacta", "atrib_parcial", "atrib_ausente", "falsa_abstencion", "palabras",
            "latencia_s", "error_m06"]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]|_", " ", t)).strip()


def atribucion(respuesta: str, docs: list[str], arts: list[str]) -> str:
    nums = {re.sub(r"\D", "", a) for a in arts} - {""}
    if any(re.search(r"(?i)art[íi]culo\s*" + n + r"\b", respuesta) for n in nums):
        return "exacta"
    # documento mencionado: ≥ 75 % de las palabras significativas de su nombre aparecen en la respuesta
    # ("Reglamento de Becas 2021 actualizado" cuenta para "REGLAMENTO BECAS 2021 ACTUALIZADO")
    palabras_resp = set(norm(respuesta).split())
    for d in docs:
        sig = [w for w in norm(d).split() if len(w) >= 4 or w.isdigit()]
        if sig and sum(w in palabras_resp for w in sig) / len(sig) >= 0.75:
            return "parcial"
    if re.search(r"(?i)art[íi]culo\s*\d+", respuesta) or re.search(r"\((?:[^()]*?(?:reglamento|estatuto|tupa|"
                                                                     r"directiva|pol[íi]tica)[^()]*)\)", respuesta, re.I):
        return "incorrecta"
    return "ausente"


def metricas_corrida(path: Path, banco: dict) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    salida = {}
    for r in data["resultados"]:
        q = banco.get(r["id"])
        if not q:
            continue
        resp = r.get("respuesta") or ""
        tipo = r.get("tipo_mensaje") or "ERROR"
        pts = q["puntos"]
        cub = sum(comp.juzgar(p["descripcion"], resp)[0] == "CUBIERTO" for p in pts) / len(pts) if pts else 0.0
        at = atribucion(resp, q["documentos_esperados"], [a["articulo"] for a in q["articulos_esperados"]]) \
            if tipo == "M02" else "ausente"
        salida[r["id"]] = {
            "completitud": cub, "atrib_exacta": float(at == "exacta"), "atrib_parcial": float(at == "parcial"),
            "atrib_ausente": float(at == "ausente"), "falsa_abstencion": float(tipo in ABSTENCION),
            "palabras": float(len(resp.split())) if tipo == "M02" else 0.0,
            "latencia_s": float(r.get("tiempo_s") or 0), "error_m06": float(tipo == "M06"),
        }
    return {"meta": data.get("meta", {}), "por_pregunta": salida}


def abstencion_negativas(patron: str) -> tuple[int, int]:
    ok = n = 0
    for f in glob.glob(patron):
        for r in json.loads(Path(f).read_text(encoding="utf-8"))["resultados"]:
            n += 1
            ok += (r.get("tipo_mensaje") in ABSTENCION)
    return ok, n


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco", required=True)
    ap.add_argument("--referencia", default="qwen")
    ap.add_argument("--salida", default=str(AQUI / "exp_b"))
    ap.add_argument("--n-boot", type=int, default=est.N_BOOT)
    ap.add_argument("sistemas", nargs="+", help="NOMBRE=patron1,patron2 (globs de los JSON de cada semilla)")
    a = ap.parse_args(argv)

    banco = {q["id"]: q for q in json.loads(Path(a.banco).read_text(encoding="utf-8"))["preguntas"]}
    sistemas, metas, negs = {}, {}, {}
    for s in a.sistemas:
        nombre, _, patrones = s.partition("=")
        archivos = sorted({f for p in patrones.split(",") for f in glob.glob(p)})
        archivos = [f for f in archivos if "_NEG_" not in f]
        if not archivos:
            raise SystemExit(f"{nombre}: ningún archivo coincide con {patrones}")
        corridas = [metricas_corrida(Path(f), banco) for f in archivos]
        metas[nombre] = [{"archivo": Path(f).name, "llm": c["meta"].get("llm_model"),
                          "semilla": c["meta"].get("ollama_seed"), "s0": c["meta"].get("rag_sin_recuperacion"),
                          "prompt": c["meta"].get("prompt_version")} for f, c in zip(archivos, corridas)]
        ids = set.intersection(*(set(c["por_pregunta"]) for c in corridas))
        sistemas[nombre] = {q: {m: statistics.mean(c["por_pregunta"][q][m] for c in corridas) for m in METRICAS}
                            for q in ids}
        sistemas[nombre]["_lat_todas"] = [c["por_pregunta"][q]["latencia_s"] for c in corridas for q in ids]
        # negativas de cada semilla: E2E_B_qwen_s42_*.json → E2E_B_qwen_s42_NEG_*.json
        negs[nombre] = [abstencion_negativas(p.replace("_*.json", "_NEG_*.json")) for p in patrones.split(",")]

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    resumen = []
    for nombre, d in sistemas.items():
        lat = d.pop("_lat_todas")
        ok = sum(x[0] for x in negs[nombre])
        n = sum(x[1] for x in negs[nombre])
        fila = {"sistema": nombre, "n_preguntas": len(d), "semillas": len(metas[nombre])}
        for m in METRICAS:
            media, lo, hi = est.bootstrap_ic([v[m] for v in d.values()], n_boot=a.n_boot)
            fila[m] = media
            fila[f"{m}_ic95"] = f"[{lo:.3f}, {hi:.3f}]"
        fila["latencia_p50"] = statistics.median(lat)
        fila["latencia_p95"] = sorted(lat)[max(0, int(round(0.95 * len(lat))) - 1)]
        fila["negativas_abstenidas"] = f"{ok}/{n}"
        resumen.append(fila)
    comps = []
    for m in ("completitud", "atrib_exacta", "falsa_abstencion", "latencia_s"):
        datos = {s: {q: v[m] for q, v in d.items()} for s, d in sistemas.items()}
        for f in est.comparar_sistemas(datos, base=a.referencia, n_boot=a.n_boot):
            comps.append({"metrica": m, **f})

    for nombre, filas in (("resumen_exp_b.csv", resumen), ("comparaciones_exp_b.csv", comps)):
        with open(salida / nombre, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            for r in filas:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
    (salida / "corridas_exp_b.json").write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'sistema':<8} {'complet.':>9} {'atr.exac':>9} {'atr.parc':>9} {'atr.aus':>8} {'falsa_abs':>9} "
          f"{'palabras':>9} {'p50 s':>7} {'p95 s':>7} {'M06':>5} {'negativas':>10}")
    for r in resumen:
        print(f"{r['sistema']:<8} {r['completitud']:>9.3f} {r['atrib_exacta']:>9.3f} {r['atrib_parcial']:>9.3f} "
              f"{r['atrib_ausente']:>8.3f} {r['falsa_abstencion']:>9.3f} {r['palabras']:>9.0f} "
              f"{r['latencia_p50']:>7.1f} {r['latencia_p95']:>7.1f} {r['error_m06']:>5.2f} {r['negativas_abstenidas']:>10}")
    print()
    for c in comps:
        print(f"  {c['metrica']:<16} {c['comparacion']:<14} dif {c['diferencia']:+.3f} "
              f"[{c['ic95_lo']:+.3f}, {c['ic95_hi']:+.3f}]  p Holm {c['p_holm']:.4f}"
              f"  r {c['r_rango_biserial']:+.2f}{'  *' if c['significativo'] else ''}")
    print(f"\nresultados en {salida}")


if __name__ == "__main__":
    main()
