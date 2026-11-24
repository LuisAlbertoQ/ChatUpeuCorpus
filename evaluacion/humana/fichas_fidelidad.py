# -*- coding: utf-8 -*-
"""Evaluación humana ciega de la fidelidad (Revisión 3, .docx §8) — ronda 2 de evaluadores.

Dos pasos:

  preparar  arma dos fichas Excel idénticas (evaluador 1 y 2) con una submuestra de respuestas de varios
            generadores. Las respuestas van mezcladas y con un código (R001…): el evaluador NO sabe qué modelo
            escribió cada una. La relación código → sistema se guarda en `clave_NO_ENTREGAR.json`.

      python fichas_fidelidad.py preparar --banco ../banco/banco_gold_260.json --n-preguntas 50 \
          qwen=../comparacion_v2_v3/E2E_B_qwen_s42_*.json qwen3=... llama32=... gemma3=...

  analizar  lee las dos fichas completas, mide el acuerdo entre evaluadores (κ) y compara los sistemas contra la
            referencia (Wilcoxon + Holm, IC95 bootstrap): insumo de la Tabla 3.

      python fichas_fidelidad.py analizar --clave fidelidad_rev3/clave_NO_ENTREGAR.json \
          ficha_fidelidad_E1_XX.xlsx ficha_fidelidad_E2_YY.xlsx

Rúbrica (fijada antes de ver resultados): RUBRICA_FIDELIDAD_REV3.md.
"""
from __future__ import annotations

import argparse
import ast
import csv
import glob
import json
import random
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EVAL = AQUI.parent
sys.path.insert(0, str(EVAL / "estadistica"))
sys.path.insert(0, str(EVAL / "banco" / "gold"))
import estadistica as est  # noqa: E402
import xlsx_simple  # noqa: E402

CHUNKS_CANDIDATOS = [
    EVAL.parent.parent / "oe1_arquitectura_corpus" / "corpus_upeu" / "metadatos" / "v3" / "chunks_v3_bgem3.csv",
    Path("/oe1/chunks_v3_bgem3.csv"),
]
MAX_CELDA = 32000  # límite de Excel: 32 767 caracteres por celda

CORRECCION = ["0", "1", "2"]
FIDELIDAD = ["0", "1", "2"]
ATRIBUCION = ["exacta", "parcial", "incorrecta", "ausente"]
RELEVANCIA = ["1", "2", "3", "4", "5"]
COLUMNAS = ["item", "pregunta_cod", "pregunta", "respuesta_referencia", "puntos_clave", "respuesta_a_evaluar",
            "correccion", "fidelidad", "atribucion", "relevancia", "notas"]
EDITABLES = [6, 7, 8, 9, 10]
DIMENSIONES = ["correccion", "fidelidad", "atribucion", "relevancia"]

INSTRUCCIONES = [
    ["Evaluación humana ciega de respuestas del chatbot — Revisión 3 (rúbrica completa: RUBRICA_FIDELIDAD_REV3.md)"],
    ["1. Trabaja SOLO. No sabes qué modelo escribió cada respuesta y no intentes adivinarlo."],
    ["2. Cada fila es una respuesta. La misma pregunta aparece varias veces (una por modelo), en distinto orden."],
    ["3. Abre la hoja 'Fuentes' y busca el pregunta_cod: son los fragmentos de reglamento que recibió el modelo."],
    ["4. Evalúa en este orden: fidelidad → corrección → atribución → relevancia (la impresión general al final)."],
    ["fidelidad: 2 = todo lo que afirma está en las fuentes; 1 = alguna afirmación menor no está en las fuentes; "
     "0 = afirma algo importante que no está en las fuentes o las contradice."],
    ["correccion: comparando con respuesta_referencia y puntos_clave: 2 = correcta y completa en lo esencial; "
     "1 = correcta pero incompleta, o con un error menor; 0 = incorrecta o no responde."],
    ["atribucion: exacta = cita el documento y artículo correctos; parcial = documento correcto, artículo no; "
     "incorrecta = cita otra fuente; ausente = no cita."],
    ["relevancia: 1 (no responde lo preguntado) a 5 (responde directo y suficiente, sin relleno)."],
    ["Si la respuesta es una abstención ('No encontré información…'): fidelidad 2, correccion 0, atribucion ausente, "
     "y anota 'abstención' en notas."],
    ["Al terminar guarda el archivo con tus iniciales: ficha_fidelidad_E1_<INICIALES>.xlsx y entrégalo."],
]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]|_", " ", t)).strip()


def num_art(a: str) -> str:
    m = re.search(r"\d+", a or "")
    return m.group() if m else ""


def _lista(v) -> list:
    if isinstance(v, list):
        return v
    if not v:
        return []
    try:
        x = ast.literal_eval(v)
        return x if isinstance(x, list) else [x]
    except (ValueError, SyntaxError):
        return [v]


def cargar_textos(path: Path | None) -> dict:
    """{(documento normalizado, número de artículo): texto completo del artículo} desde el CSV de chunks."""
    if not path or not path.exists():
        return {}
    csv.field_size_limit(10 ** 9)
    partes = defaultdict(list)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            n = num_art(r.get("articulo"))
            if n:
                partes[(norm(r["nombre_documento"]), n)].append((int(r.get("parte_num") or 1), r["texto"]))
    return {k: "\n".join(t for _, t in sorted(v)) for k, v in partes.items()}


def fuentes_de(resultado: dict, textos: dict) -> list[str]:
    """Fragmentos que recibió el LLM (documento + artículo), con su texto cuando se puede ubicar."""
    docs = _lista(resultado.get("documentos_llm"))
    arts = _lista(resultado.get("articulos_llm"))
    salida, vistos = [], set()
    for d, a in zip(docs, arts + [""] * (len(docs) - len(arts))):
        nombre = re.sub(r"\.pdf$", "", d or "", flags=re.I)
        clave = (norm(nombre), num_art(a))
        if clave in vistos:
            continue
        vistos.add(clave)
        texto = textos.get(clave) if clave[1] else None
        cab = f"[{nombre} · {a or 'sin artículo'}]"
        salida.append(f"{cab}\n{texto}" if texto else f"{cab}\n(texto no ubicado automáticamente: revisar en el PDF)")
    return salida


def cargar_corrida(patron: str) -> dict:
    archivos = [f for f in sorted(glob.glob(patron)) if "_NEG_" not in f]
    if len(archivos) != 1:
        raise SystemExit(f"{patron}: se esperaba 1 corrida (sin _NEG_), hay {len(archivos)}: {archivos}")
    data = json.loads(Path(archivos[0]).read_text(encoding="utf-8"))
    return {"archivo": Path(archivos[0]).name, "llm": data.get("meta", {}).get("llm_model"),
            "por_id": {r["id"]: r for r in data["resultados"]}}


def muestrear(ids: list[str], banco: dict, n: int, semilla: int) -> list[str]:
    """Muestra estratificada por categoría (proporcional, al menos 1 por categoría presente)."""
    if n >= len(ids):
        return sorted(ids)
    rng = random.Random(semilla)
    por_cat = defaultdict(list)
    for q in sorted(ids):
        por_cat[banco[q].get("categoria") or "-"].append(q)
    cuota = {c: max(1, round(n * len(v) / len(ids))) for c, v in por_cat.items()}
    while sum(cuota.values()) > n:
        c = max(cuota, key=lambda k: (cuota[k], k))
        cuota[c] -= 1
    while sum(cuota.values()) < n:
        c = max(por_cat, key=lambda k: (len(por_cat[k]) - cuota[k], k))
        cuota[c] += 1
    return sorted(q for c, v in por_cat.items() for q in rng.sample(v, min(cuota[c], len(v))))


def preparar(a) -> None:
    banco_data = json.loads(Path(a.banco).read_text(encoding="utf-8"))
    banco = {q["id"]: q for q in banco_data["preguntas"]}
    corridas = {}
    for s in a.sistemas:
        nombre, _, patron = s.partition("=")
        corridas[nombre] = cargar_corrida(patron)
    ids = [q for q in banco if all(q in c["por_id"] for c in corridas.values())]
    if not ids:
        raise SystemExit("ninguna pregunta del banco aparece en todas las corridas")
    elegidas = muestrear(ids, banco, a.n_preguntas, a.semilla)
    textos = cargar_textos(Path(a.chunks) if a.chunks else next((p for p in CHUNKS_CANDIDATOS if p.exists()), None))

    rng = random.Random(a.semilla + 1)
    cod_preg = {q: f"P{i:03d}" for i, q in enumerate(rng.sample(elegidas, len(elegidas)), start=1)}
    items = [(q, s) for q in elegidas for s in corridas]
    rng.shuffle(items)

    filas = [COLUMNAS]
    clave = {"banco": banco_data.get("version"), "semilla": a.semilla, "sistemas": {}, "items": {}}
    for s, c in corridas.items():
        clave["sistemas"][s] = {"archivo": c["archivo"], "llm": c["llm"]}
    for i, (q, s) in enumerate(items, start=1):
        item = f"R{i:03d}"
        p = banco[q]
        ref = p.get("respuesta_referencia") or ""
        puntos = "; ".join(x.get("descripcion", "") for x in (p.get("puntos") or []))
        resp = (corridas[s]["por_id"][q].get("respuesta") or "")[:MAX_CELDA]
        filas.append([item, cod_preg[q], p["pregunta"], ref, puntos, resp, "", "", "", "", ""])
        clave["items"][item] = {"sistema": s, "pregunta_id": q, "pregunta_cod": cod_preg[q],
                                "tipo_mensaje": corridas[s]["por_id"][q].get("tipo_mensaje")}

    ref_sis = next(iter(corridas))
    filas_fuentes = [["pregunta_cod", "pregunta", "fragmentos que recibió el modelo"]]
    sin_texto = 0
    for q in sorted(elegidas, key=lambda x: cod_preg[x]):
        frs = fuentes_de(corridas[ref_sis]["por_id"][q], textos)
        sin_texto += sum("no ubicado" in f for f in frs)
        filas_fuentes.append([cod_preg[q], banco[q]["pregunta"], "\n\n".join(frs)[:MAX_CELDA]])

    n = len(filas) - 1
    hojas = [
        {"nombre": "Instrucciones", "filas": INSTRUCCIONES, "anchos": [150]},
        {"nombre": "Evaluacion", "filas": filas, "columnas_editables": EDITABLES,
         "anchos": [7, 9, 40, 40, 40, 70, 11, 10, 12, 10, 30],
         "validaciones": [(6, 2, n + 1, '"' + ",".join(CORRECCION) + '"'),
                          (7, 2, n + 1, '"' + ",".join(FIDELIDAD) + '"'),
                          (8, 2, n + 1, '"' + ",".join(ATRIBUCION) + '"'),
                          (9, 2, n + 1, '"' + ",".join(RELEVANCIA) + '"')]},
        {"nombre": "Fuentes", "filas": filas_fuentes, "anchos": [12, 40, 120]},
    ]
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for e in ("E1", "E2"):
        xlsx_simple.escribir(salida / f"ficha_fidelidad_{e}.xlsx", hojas)
    (salida / "clave_NO_ENTREGAR.json").write_text(json.dumps(clave, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(elegidas)} preguntas × {len(corridas)} sistemas = {n} respuestas por evaluador")
    print(f"fragmentos sin texto ubicado: {sin_texto} (el evaluador los revisa en el PDF)")
    print(f"fichas y clave en {salida}  — la clave NO se entrega a los evaluadores")


def leer_ficha(path: str) -> dict:
    filas = xlsx_simple.leer(path, "Evaluacion")
    cab = filas[0]
    idx = {c: cab.index(c) for c in COLUMNAS if c in cab}
    out, errores = {}, []
    for f in filas[1:]:
        f = f + [""] * (len(cab) - len(f))
        item = f[idx["item"]].strip()
        if not item:
            continue
        v = {d: f[idx[d]].strip().lower() for d in DIMENSIONES}
        for d, permitidos in (("correccion", CORRECCION), ("fidelidad", FIDELIDAD), ("atribucion", ATRIBUCION),
                              ("relevancia", RELEVANCIA)):
            if v[d] not in permitidos:
                errores.append(f"{item}: {d} = {v[d]!r} (permitidos: {', '.join(permitidos)})")
        out[item] = v
    if errores:
        raise SystemExit(f"{path}: {len(errores)} errores\n  " + "\n  ".join(errores[:30]))
    return out


def puntaje(v: dict) -> dict:
    return {"fidelidad": int(v["fidelidad"]) / 2, "correccion": int(v["correccion"]) / 2,
            "atrib_exacta": float(v["atribucion"] == "exacta"), "relevancia": float(v["relevancia"])}


def analizar(a) -> None:
    clave = json.loads(Path(a.clave).read_text(encoding="utf-8"))
    e1, e2 = leer_ficha(a.ficha1), leer_ficha(a.ficha2)
    items = sorted(clave["items"])
    faltan = [i for i in items if i not in e1 or i not in e2]
    if faltan:
        raise SystemExit(f"faltan {len(faltan)} ítems en alguna ficha: {faltan[:10]}")

    acuerdo, desacuerdos = [], []
    for d in DIMENSIONES:
        k = est.cohen_kappa([e1[i][d] for i in items], [e2[i][d] for i in items])
        acuerdo.append({"dimension": d, "n": k["n"], "kappa": k["kappa"], "acuerdo_observado": k["acuerdo_observado"],
                        "lectura": est.lectura_kappa(k["kappa"])})
    for i in items:
        dif = [d for d in DIMENSIONES if e1[i][d] != e2[i][d]]
        if dif:
            desacuerdos.append({"item": i, **{f"{d}_E1": e1[i][d] for d in dif}, **{f"{d}_E2": e2[i][d] for d in dif},
                                "dimensiones": ",".join(dif)})

    # puntaje por (sistema, pregunta) = promedio de los dos evaluadores
    por_sis = defaultdict(lambda: defaultdict(dict))
    for i in items:
        c = clave["items"][i]
        p1, p2 = puntaje(e1[i]), puntaje(e2[i])
        for m in p1:
            por_sis[m][c["sistema"]][c["pregunta_id"]] = (p1[m] + p2[m]) / 2

    detalle = [{"item": i, "sistema": clave["items"][i]["sistema"], "pregunta_id": clave["items"][i]["pregunta_id"],
                **{f"{d}_E{k}": e[i][d] for d in DIMENSIONES for k, e in ((1, e1), (2, e2))}} for i in items]

    metricas = list(por_sis)
    sistemas = list(clave["sistemas"])
    resumen = []
    for s in sistemas:
        fila = {"sistema": s, "llm": clave["sistemas"][s].get("llm"), "n_preguntas": len(por_sis["fidelidad"][s])}
        for m in metricas:
            media, lo, hi = est.bootstrap_ic(list(por_sis[m][s].values()), n_boot=a.n_boot)
            fila[m], fila[f"{m}_ic95"] = media, f"[{lo:.3f}, {hi:.3f}]"
        resumen.append(fila)
    referencia = a.referencia if a.referencia in sistemas else sistemas[0]
    comps = []
    for m in metricas:
        for f in est.comparar_sistemas({s: por_sis[m][s] for s in sistemas}, base=referencia, n_boot=a.n_boot):
            comps.append({"metrica": m, **f})

    salida = Path(a.salida or Path(a.clave).parent)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, filas in (("acuerdo_fidelidad.csv", acuerdo), ("resumen_fidelidad.csv", resumen),
                          ("comparaciones_fidelidad.csv", comps), ("desacuerdos_fidelidad.csv", desacuerdos),
                          ("detalle_fidelidad.csv", detalle)):
        if not filas:
            continue
        campos = list(dict.fromkeys(k for r in filas for k in r))
        with open(salida / nombre, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for r in filas:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

    for r in acuerdo:
        print(f"  κ {r['dimension']:<11} {r['kappa']:.2f} ({r['lectura']}), acuerdo {r['acuerdo_observado']:.0%}")
    print(f"\n{'sistema':<10} " + " ".join(f"{m:>12}" for m in metricas))
    for r in resumen:
        print(f"{r['sistema']:<10} " + " ".join(f"{r[m]:>12.3f}" for m in metricas))
    print()
    for c in comps:
        print(f"  {c['metrica']:<12} {c['comparacion']:<16} dif {c['diferencia']:+.3f} "
              f"[{c['ic95_lo']:+.3f}, {c['ic95_hi']:+.3f}]  p Holm {c['p_holm']:.4f}{'  *' if c['significativo'] else ''}")
    print(f"\n{len(desacuerdos)} ítems con desacuerdo → desacuerdos_fidelidad.csv; resultados en {salida}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--banco", required=True)
    p.add_argument("--n-preguntas", type=int, default=50)
    p.add_argument("--semilla", type=int, default=2026)
    p.add_argument("--chunks", default="", help="CSV de chunks del OE1 (por defecto chunks_v3_bgem3.csv)")
    p.add_argument("--salida", default=str(AQUI / "fidelidad_rev3"))
    p.add_argument("sistemas", nargs="+", help="NOMBRE=glob de UNA corrida (la primera es la que da las fuentes)")
    q = sub.add_parser("analizar")
    q.add_argument("--clave", required=True)
    q.add_argument("--referencia", default="qwen")
    q.add_argument("--salida", default="")
    q.add_argument("--n-boot", type=int, default=est.N_BOOT)
    q.add_argument("ficha1")
    q.add_argument("ficha2")
    a = ap.parse_args(argv)
    preparar(a) if a.cmd == "preparar" else analizar(a)


if __name__ == "__main__":
    main()
