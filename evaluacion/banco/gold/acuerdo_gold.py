# -*- coding: utf-8 -*-
"""Acuerdo entre anotadores y consolidación del gold set de 260 (Revisión 3, §3).

Paso 1 — acuerdo (κ de Cohen) y lista de conflictos para el tercer evaluador:
    python acuerdo_gold.py kappa ficha_anotador_A_XX.xlsx ficha_anotador_B_YY.xlsx
        → acuerdo_anotadores.csv   una fila por pregunta: A, B y si coinciden
        → kappa_resumen.csv        κ de tipo, bloque y documento; acuerdo de artículos
        → conflictos_para_juez.xlsx  solo las preguntas en desacuerdo, con columnas para el juez

Paso 2 — consolidación (cuando el juez completó sus columnas):
    python acuerdo_gold.py consolidar ficha_A.xlsx ficha_B.xlsx --juez conflictos_para_juez.xlsx \
        [--ood-nuevas plantilla_ood_nuevas.xlsx]
        → ../banco_gold_260.json      mismo formato que banco_v32.json (lo leen exp_a, correr_17q_e2e, exp_c)
        → ../validacion_banco_gold_260.md  composición y verificación contra el corpus V3

Las fichas pueden ser .xlsx (de preparar_fichas.py) o .jsonl (formato de guia_anotacion.md).
Umbrales de calidad (guia_anotacion.md §6): κ documento ≥ 0.80 y κ tipo ≥ 0.75.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BANCO = AQUI.parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(BANCO.parent / "estadistica"))
import estadistica as est  # noqa: E402
import xlsx_simple  # noqa: E402
from preparar_fichas import CATEGORIAS, NINGUNO, TIPOS, _cargar_cb, documentos_corpus  # noqa: E402

RESPONDIBLES = {"DIRECTA", "REQUISITOS", "PROCEDIMIENTO"}
UMBRAL_KAPPA = {"documento": 0.80, "tipo": 0.75}
CAMPOS_JUEZ = ["juez_tipo", "juez_documento", "juez_articulos", "juez_documento_2", "juez_articulos_2",
               "juez_categoria", "juez_respuesta_referencia", "juez_puntos_clave", "juez_notas"]


# --------------------------------------------------------------------------- lectura
def bloque(tipo: str) -> str:
    return "dominio" if tipo in RESPONDIBLES else "ood" if tipo == "SIN_COBERTURA" else "ambigua"


def arts_set(texto: str) -> frozenset:
    """'Artículo 12°; Art. 18' → {'12', '18'} (solo números: el formato de escritura no cuenta)."""
    return frozenset(re.findall(r"\d+", texto or ""))


def _doc(v: str) -> str:
    v = (v or "").strip()
    return "" if v in ("", NINGUNO) else v.removesuffix(".pdf")


def leer_ficha(path: Path) -> dict:
    """{pregunta_id: {campo: valor}} desde .xlsx (hoja Anotacion) o .jsonl."""
    filas = {}
    if path.suffix.lower() == ".jsonl":
        for linea in path.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                r = json.loads(linea)
                filas[r["pregunta_id"]] = {
                    "pregunta": r.get("texto", ""), "tipo": r.get("tipo", ""),
                    "documento": r.get("documento_esperado", ""), "articulos": r.get("articulo_esperado", ""),
                    "documento_2": r.get("documento_2", ""), "articulos_2": r.get("articulos_2", ""),
                    "categoria": r.get("categoria", ""), "respuesta_referencia": r.get("respuesta_referencia", ""),
                    "puntos_clave": r.get("puntos_clave", ""), "confianza": r.get("confianza", ""),
                    "notas": r.get("notas", "")}
    else:
        tabla = xlsx_simple.leer(path, "Anotacion")
        enc = [c.strip() for c in tabla[0]]
        for fila in tabla[1:]:
            if not fila or not fila[0].strip():
                continue
            r = {enc[i]: (fila[i].strip() if i < len(fila) else "") for i in range(len(enc))}
            filas[r["pregunta_id"]] = r
    for r in filas.values():
        r["tipo"] = r.get("tipo", "").strip().upper()
        r["documento"] = _doc(r.get("documento"))
        r["documento_2"] = _doc(r.get("documento_2"))
        r["categoria"] = r.get("categoria", "").strip().upper()
    return filas


def validar_ficha(nombre: str, ficha: dict, docs_validos: set, ids_esperados: list) -> list[str]:
    err = []
    faltan = [i for i in ids_esperados if i not in ficha]
    if faltan:
        err.append(f"{nombre}: faltan {len(faltan)} preguntas (p. ej. {faltan[:3]})")
    for pid, r in ficha.items():
        if r["tipo"] not in TIPOS:
            err.append(f"{nombre} {pid}: tipo vacío o inválido ({r['tipo']!r})")
            continue
        for campo in ("documento", "documento_2"):
            if r[campo] and r[campo] not in docs_validos:
                err.append(f"{nombre} {pid}: {campo} no está en el corpus ({r[campo]!r})")
        if r["tipo"] in RESPONDIBLES:
            if not r["documento"]:
                err.append(f"{nombre} {pid}: {r['tipo']} sin documento")
            if r["categoria"] not in CATEGORIAS:
                err.append(f"{nombre} {pid}: categoría vacía o inválida ({r['categoria']!r})")
    return err


# --------------------------------------------------------------------------- acuerdo
def comparar(a: dict, b: dict, ids: list) -> list[dict]:
    filas = []
    for pid in ids:
        ra, rb = a[pid], b[pid]
        arts_a, arts_b = arts_set(ra["articulos"]), arts_set(rb["articulos"])
        union = arts_a | arts_b
        filas.append({
            "pregunta_id": pid, "pregunta": ra.get("pregunta", ""),
            "A_tipo": ra["tipo"], "B_tipo": rb["tipo"], "tipo_ok": int(ra["tipo"] == rb["tipo"]),
            "bloque_ok": int(bloque(ra["tipo"]) == bloque(rb["tipo"])),
            "A_documento": ra["documento"], "B_documento": rb["documento"],
            "documento_ok": int(ra["documento"] == rb["documento"]),
            "A_articulos": ra["articulos"], "B_articulos": rb["articulos"],
            "articulos_ok": int(arts_a == arts_b),
            "articulos_jaccard": round(len(arts_a & arts_b) / len(union), 3) if union else 1.0,
            "A_respuesta": ra.get("respuesta_referencia", ""), "B_respuesta": rb.get("respuesta_referencia", ""),
        })
    for f in filas:
        f["conflicto"] = int(not (f["tipo_ok"] and f["documento_ok"] and f["articulos_ok"]))
    return filas


def resumen_kappa(filas: list[dict]) -> list[dict]:
    salida = []
    for campo, col_a, col_b, f in (("tipo", "A_tipo", "B_tipo", None),
                                   ("bloque", "A_tipo", "B_tipo", bloque),
                                   ("documento", "A_documento", "B_documento", lambda d: d or NINGUNO)):
        va = [f(r[col_a]) if f else r[col_a] for r in filas]
        vb = [f(r[col_b]) if f else r[col_b] for r in filas]
        k = est.cohen_kappa(va, vb)
        umbral = UMBRAL_KAPPA.get(campo)
        salida.append({"medida": f"kappa_{campo}", "valor": round(k["kappa"], 4), "n": k["n"],
                       "acuerdo_observado": round(k["acuerdo_observado"], 4), "lectura": est.lectura_kappa(k["kappa"]),
                       "umbral": umbral or "", "cumple": ("sí" if k["kappa"] >= umbral else "no") if umbral else ""})
    mismos_doc = [r for r in filas if r["documento_ok"] and r["A_documento"]]
    if mismos_doc:
        salida.append({"medida": "articulos_iguales (mismo documento)", "n": len(mismos_doc),
                       "valor": round(sum(r["articulos_ok"] for r in mismos_doc) / len(mismos_doc), 4),
                       "acuerdo_observado": "", "lectura": "proporción", "umbral": "", "cumple": ""})
        salida.append({"medida": "articulos_jaccard_medio (mismo documento)", "n": len(mismos_doc),
                       "valor": round(sum(r["articulos_jaccard"] for r in mismos_doc) / len(mismos_doc), 4),
                       "acuerdo_observado": "", "lectura": "proporción", "umbral": "", "cumple": ""})
    salida.append({"medida": "preguntas_en_conflicto", "valor": sum(r["conflicto"] for r in filas), "n": len(filas),
                   "acuerdo_observado": "", "lectura": "van al tercer evaluador", "umbral": "", "cumple": ""})
    return salida


def _csv(path: Path, filas: list[dict]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def hoja_conflictos(filas: list[dict], a: dict, b: dict, docs: list[dict]) -> list[dict]:
    enc = ["pregunta_id", "pregunta", "A_tipo", "B_tipo", "A_documento", "B_documento", "A_articulos",
           "B_articulos", "A_documento_2", "B_documento_2", "A_respuesta", "B_respuesta"] + CAMPOS_JUEZ
    datos = [enc]
    for r in filas:
        if not r["conflicto"]:
            continue
        pid = r["pregunta_id"]
        datos.append([pid, r["pregunta"], r["A_tipo"], r["B_tipo"], r["A_documento"], r["B_documento"],
                      r["A_articulos"], r["B_articulos"], a[pid]["documento_2"], b[pid]["documento_2"],
                      r["A_respuesta"], r["B_respuesta"]] + [""] * len(CAMPOS_JUEZ))
    n = len(datos) - 1
    i0 = len(enc) - len(CAMPOS_JUEZ)
    ref_docs = f"Documentos!$A$2:$A${len(docs) + 2}"
    instr = [["Tercer evaluador: resuelve SOLO estas preguntas (los anotadores no coincidieron en tipo, documento o artículos)."],
             ["Completa las columnas amarillas juez_* con la decisión final (puedes copiar la de A o la de B, o una tercera)."],
             ["juez_respuesta_referencia y juez_puntos_clave: si los dejas vacíos se usa lo del anotador cuya decisión elegiste."],
             ["Para SIN_COBERTURA o AMBIGUA deja documento en '(ninguno)' y artículos vacío."]]
    return [{"nombre": "Instrucciones", "filas": instr, "anchos": [150]},
            {"nombre": "Conflictos", "filas": datos, "columnas_editables": list(range(i0, len(enc))),
             "anchos": [11, 40, 14, 14, 30, 30, 16, 16, 20, 20, 40, 40, 14, 30, 16, 24, 14, 10, 40, 40, 30],
             "validaciones": [(i0, 2, n + 1, '"' + ",".join(TIPOS) + '"'), (i0 + 1, 2, n + 1, ref_docs),
                              (i0 + 3, 2, n + 1, ref_docs), (i0 + 5, 2, n + 1, '"' + ",".join(CATEGORIAS) + '"')]},
            {"nombre": "Documentos", "filas": [["documento", "categoria", "n_articulos"], [NINGUNO, "", ""]]
             + [[d["documento"], d["categoria"], d["n_articulos"]] for d in docs], "anchos": [70, 10, 12]}]


def cmd_kappa(args):
    docs = documentos_corpus()
    validos = {d["documento"] for d in docs}
    a, b = leer_ficha(Path(args.ficha_a)), leer_ficha(Path(args.ficha_b))
    ids = sorted(set(a) & set(b))
    errores = validar_ficha("A", a, validos, sorted(set(a) | set(b))) + \
        validar_ficha("B", b, validos, sorted(set(a) | set(b)))
    if errores:
        print(f"{len(errores)} problemas en las fichas (corrígelos antes de calcular el acuerdo):")
        print("\n".join("  " + e for e in errores[:60]))
        if not args.forzar:
            raise SystemExit(1)
    filas = comparar(a, b, ids)
    resumen = resumen_kappa(filas)
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    _csv(salida / "acuerdo_anotadores.csv", filas)
    _csv(salida / "kappa_resumen.csv", resumen)
    xlsx_simple.escribir(salida / "conflictos_para_juez.xlsx", hoja_conflictos(filas, a, b, docs))
    for r in resumen:
        extra = f"  (umbral {r['umbral']}: {r['cumple']})" if r["umbral"] else ""
        print(f"  {r['medida']:<44} {r['valor']}  n={r['n']}  {r['lectura']}{extra}")
    print(f"\nacuerdo_anotadores.csv, kappa_resumen.csv y conflictos_para_juez.xlsx en {salida}")


# --------------------------------------------------------------------------- consolidación
def _puntos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;\n]", texto or "") if p.strip()]


def _union_puntos(pa: list[str], pb: list[str]) -> list[str]:
    vistos, salida = set(), []
    for p in pa + pb:
        k = re.sub(r"\W+", " ", p.lower()).strip()
        if k and k not in vistos:
            vistos.add(k)
            salida.append(p)
    return salida


def decision_final(pid: str, a: dict, b: dict, juez: dict) -> dict:
    ra, rb = a[pid], b[pid]
    acuerdo = (ra["tipo"] == rb["tipo"] and ra["documento"] == rb["documento"]
               and arts_set(ra["articulos"]) == arts_set(rb["articulos"]))
    if acuerdo:
        return {"tipo": ra["tipo"], "documento": ra["documento"], "articulos": ra["articulos"],
                "documento_2": ra["documento_2"] or rb["documento_2"],
                "articulos_2": ra["articulos_2"] or rb["articulos_2"],
                "categoria": ra["categoria"] or rb["categoria"],
                "respuesta_referencia": ra.get("respuesta_referencia") or rb.get("respuesta_referencia", ""),
                "puntos": _union_puntos(_puntos(ra.get("puntos_clave")), _puntos(rb.get("puntos_clave"))),
                "resuelto_por": "acuerdo"}
    j = juez.get(pid)
    if not j or not j.get("juez_tipo"):
        return None
    tipo = j["juez_tipo"].strip().upper()
    doc = _doc(j.get("juez_documento"))
    # respuesta/puntos por defecto: los del anotador cuya decisión coincide con la del juez
    base = ra if (ra["tipo"], ra["documento"]) == (tipo, doc) else rb if (rb["tipo"], rb["documento"]) == (tipo, doc) else ra
    return {"tipo": tipo, "documento": doc, "articulos": j.get("juez_articulos", ""),
            "documento_2": _doc(j.get("juez_documento_2")), "articulos_2": j.get("juez_articulos_2", ""),
            "categoria": (j.get("juez_categoria") or base["categoria"]).strip().upper(),
            "respuesta_referencia": j.get("juez_respuesta_referencia") or base.get("respuesta_referencia", ""),
            "puntos": _puntos(j.get("juez_puntos_clave")) or _puntos(base.get("puntos_clave")),
            "resuelto_por": "juez"}


def cmd_consolidar(args):
    cb = _cargar_cb()
    _, por_doc = cb.cargar_corpus()
    a, b = leer_ficha(Path(args.ficha_a)), leer_ficha(Path(args.ficha_b))
    juez = {}
    if args.juez:
        tabla = xlsx_simple.leer(Path(args.juez), "Conflictos")
        enc = tabla[0]
        for fila in tabla[1:]:
            if fila and fila[0]:
                juez[fila[0]] = {enc[i]: (fila[i].strip() if i < len(fila) else "") for i in range(len(enc))}
    pool = {x["pregunta_id"]: x for x in json.loads((BANCO / "pool_260_verificacion.json").read_text(encoding="utf-8"))}
    v32 = json.loads((BANCO / "banco_v32.json").read_text(encoding="utf-8"))
    textos_dev = {cb.norm(q["pregunta"]) for q in v32["preguntas"]} | {cb.norm(n["pregunta"]) for n in v32["negativas"]}

    preguntas, negativas, pendientes, errores = [], [], [], []
    for pid in sorted(set(a) & set(b)):
        d = decision_final(pid, a, b, juez)
        if d is None:
            pendientes.append(pid)
            continue
        texto = pool[pid]["texto"] if pid in pool else a[pid].get("pregunta", "")
        dev = pool.get(pid, {}).get("estado") == "SEMILLA_CURADA" or cb.norm(texto) in textos_dev
        if d["tipo"] in RESPONDIBLES:
            docs, arts = [], []
            for doc_k, arts_k in (("documento", "articulos"), ("documento_2", "articulos_2")):
                doc = d[doc_k]
                if not doc:
                    continue
                docs.append(doc)
                if not cb.chunks_de(por_doc, doc, ""):
                    errores.append(f"{pid}: el documento {doc!r} no existe en el corpus")
                for n in sorted(arts_set(d[arts_k]), key=int):
                    if not cb.chunks_de(por_doc, doc, n):
                        errores.append(f"{pid}: Artículo {n} no existe en {doc!r}")
                    arts.append({"documento": doc, "articulo": f"Artículo {n}°"})
            preguntas.append({
                "id": pid, "pregunta": texto, "categoria": d["categoria"], "tipo_pregunta": d["tipo"],
                "cobertura_esperada": "ANSWERABLE", "documentos_esperados": docs, "articulos_esperados": arts,
                "respuesta_referencia": d["respuesta_referencia"],
                "puntos": [{"punto_id": f"{pid}_P{i:02d}", "descripcion": p, "documento": docs[0] if docs else "",
                            "articulo": arts[0]["articulo"] if arts else ""} for i, p in enumerate(d["puntos"], 1)],
                "conjunto_desarrollo": dev, "resuelto_por": d["resuelto_por"],
                "bloque_pool": pool.get(pid, {}).get("bloque", ""),
            })
        else:
            negativas.append({"id": pid, "pregunta": texto, "bloque": bloque(d["tipo"]), "tipo": d["tipo"],
                              # las 40 OOD del pool se usaron al calibrar el umbral (34) o en ablaciones (6)
                              "vista_en_desarrollo": pool.get(pid, {}).get("bloque") == "ood" or dev,
                              "resuelto_por": d["resuelto_por"]})
    if args.ood_nuevas:
        for fila in xlsx_simple.leer(Path(args.ood_nuevas), "OOD_nuevas")[1:]:
            if len(fila) > 1 and fila[1].strip():
                negativas.append({"id": fila[0], "pregunta": fila[1].strip(), "bloque": "ood", "tipo": "SIN_COBERTURA",
                                  "tipo_ood": fila[2] if len(fila) > 2 else "", "vista_en_desarrollo": False,
                                  "resuelto_por": "plantilla_ood_nuevas"})
    if pendientes:
        print(f"{len(pendientes)} conflictos sin decisión del juez: {pendientes[:10]}…")
        if not args.forzar:
            raise SystemExit(1)
    comp = Counter(q["bloque"] for q in negativas)
    comp["dominio"] = len(preguntas)
    data = {"version": "gold_260_v1", "fecha": date.today().isoformat(), "corpus": "corpus_upeu_v3_bgem3",
            "descripcion": "Gold set de la Revisión 3: doble anotación ciega + tercer evaluador",
            "composicion": dict(comp), "preguntas": preguntas, "negativas": negativas}
    destino = Path(args.destino)
    destino.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = [f"# Validación {destino.name} ({date.today().isoformat()})", "",
              f"- Composición: {dict(comp)} (objetivo del .docx: 200 dominio / 40 fuera de dominio / 20 ambiguas)",
              f"- Fuera de dominio no vistas en desarrollo: "
              f"{sum(1 for n in negativas if n['bloque'] == 'ood' and not n['vista_en_desarrollo'])}",
              f"- Preguntas de dominio del conjunto de desarrollo (17Q / v3.2): "
              f"{sum(q['conjunto_desarrollo'] for q in preguntas)}",
              f"- Resueltas por acuerdo / juez: {Counter(x['resuelto_por'] for x in preguntas + negativas)}",
              f"- Categorías (dominio): {dict(Counter(q['categoria'] for q in preguntas))}",
              f"- Errores contra el corpus: {len(errores)}", ""] + [f"  - {e}" for e in errores]
    destino.with_name(f"validacion_{destino.stem}.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kappa")
    k.add_argument("ficha_a")
    k.add_argument("ficha_b")
    k.add_argument("--salida", default=str(AQUI))
    k.add_argument("--forzar", action="store_true", help="calcular aunque haya problemas de validación")
    k.set_defaults(fn=cmd_kappa)
    c = sub.add_parser("consolidar")
    c.add_argument("ficha_a")
    c.add_argument("ficha_b")
    c.add_argument("--juez")
    c.add_argument("--ood-nuevas")
    c.add_argument("--destino", default=str(BANCO / "banco_gold_260.json"))
    c.add_argument("--forzar", action="store_true", help="escribir aunque haya conflictos sin resolver")
    c.set_defaults(fn=cmd_consolidar)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
