#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
completitud_auto.py — Proxy automático de completitud contra el ground truth v3.1 (66 puntos).

Un punto se considera:
  CUBIERTO  si el recall de términos de su descripción en la respuesta >= UMBRAL_CUBIERTO
  PARCIAL   si >= UMBRAL_PARCIAL
  NO_CUBIERTO en otro caso.
Términos: palabras de >= 4 letras sin tildes ni stopwords, truncadas a 6 caracteres (raíz).
Umbrales fijados ANTES de validar (0.60 / 0.35). Completitud micro = cubiertos / 66
(misma fórmula que la evaluación humana de FASE 4).

Validación: compara el proxy con los 66 juicios humanos de GEN_20260924_232127_8e01ef
(evaluacion_completitud_detalle) y reporta acuerdo y kappa de Cohen.
No reemplaza a la evaluación humana: sirve para comparar corridas entre sí.

Uso (host, solo sqlite3):
  python evaluacion/comparacion_v2_v3/completitud_auto.py --validar
  python evaluacion/comparacion_v2_v3/completitud_auto.py E2E_V3cal_....json E2E_M1_....json
"""
import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DB = AQUI.parent.parent / "registro_interacciones.db"
GEN_HUMANO = "GEN_20260924_232127_8e01ef"
UMBRAL_CUBIERTO, UMBRAL_PARCIAL = 0.60, 0.35
STOP = {
    "para", "como", "cual", "cuales", "sobre", "entre", "desde", "hasta", "este", "esta", "estos", "estas",
    "debe", "deben", "puede", "pueden", "tiene", "tienen", "segun", "cada", "otro", "otra", "otros", "otras",
    "todo", "toda", "todos", "todas", "solo", "tambien", "donde", "cuando", "quien", "mismo", "misma", "upeu",
    "universidad", "articulo", "incluye", "incluyen", "parte", "sera", "seran", "siendo", "dicho", "dicha",
}


def terminos(texto: str) -> set[str]:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {w[:6] for w in re.findall(r"[a-zñ]{4,}", t) if w not in STOP}


def juzgar(descripcion: str, respuesta: str) -> tuple[str, float]:
    p = terminos(descripcion)
    if not p:
        return "NO_CUBIERTO", 0.0
    rec = len(p & terminos(respuesta)) / len(p)
    if rec >= UMBRAL_CUBIERTO:
        return "CUBIERTO", rec
    if rec >= UMBRAL_PARCIAL:
        return "PARCIAL", rec
    return "NO_CUBIERTO", rec


def puntos(conn):
    return conn.execute(
        "SELECT pregunta_id, punto_id, descripcion FROM groundtruth_v31_puntos ORDER BY pregunta_id, punto_id"
    ).fetchall()


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def validar(conn):
    resp = dict(conn.execute(
        "SELECT pregunta_id, respuesta_generada FROM evaluacion_generacion WHERE generacion_experimento_id=?",
        (GEN_HUMANO,)).fetchall())
    hum = dict(conn.execute(
        "SELECT punto_id, estado FROM evaluacion_completitud_detalle WHERE generacion_experimento_id=?",
        (GEN_HUMANO,)).fetchall())
    a, b = [], []
    for qid, pid, desc in puntos(conn):
        a.append(hum[pid])
        b.append(juzgar(desc, resp.get(qid, ""))[0])
    bin_a = ["S" if x == "CUBIERTO" else "N" for x in a]
    bin_b = ["S" if x == "CUBIERTO" else "N" for x in b]
    print(f"Validación contra humano ({GEN_HUMANO}, 66 puntos)")
    print(f"  humano: {dict(Counter(a))}")
    print(f"  proxy : {dict(Counter(b))}")
    print(f"  acuerdo 3 clases: {sum(x == y for x, y in zip(a, b)) / 66:.3f}  kappa={kappa(a, b):.3f}")
    print(f"  acuerdo CUBIERTO sí/no: {sum(x == y for x, y in zip(bin_a, bin_b)) / 66:.3f}  kappa={kappa(bin_a, bin_b):.3f}")
    print(f"  completitud micro: humano={a.count('CUBIERTO') / 66:.3f} proxy={b.count('CUBIERTO') / 66:.3f}")


def evaluar(conn, archivos):
    pts = puntos(conn)
    print(f"{'corrida':42} cubiertos parciales  micro  (micro con parcial=0.5)")
    for f in archivos:
        path = Path(f) if Path(f).exists() else AQUI / f
        res = {r["id"]: r["respuesta"] for r in json.loads(path.read_text(encoding="utf-8"))["resultados"]}
        est = [juzgar(desc, res.get(qid, ""))[0] for qid, _, desc in pts]
        c, p = est.count("CUBIERTO"), est.count("PARCIAL")
        print(f"{path.stem:42} {c:9} {p:9}  {c / 66:.3f}  ({(c + 0.5 * p) / 66:.3f})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("archivos", nargs="*")
    args = ap.parse_args()
    conn = sqlite3.connect(str(DB))
    if args.validar:
        validar(conn)
    if args.archivos:
        evaluar(conn, args.archivos)
