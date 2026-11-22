# -*- coding: utf-8 -*-
"""Genera las fichas ciegas del gold set de 260 (Revisión 3, §3) para los dos anotadores.

    python evaluacion/banco/gold/preparar_fichas.py

Salida en evaluacion/banco/gold/:
    ficha_anotador_A.xlsx, ficha_anotador_B.xlsx   misma ficha; cada anotador trabaja la suya sin ver la otra
    plantilla_ood_nuevas.xlsx                      40 preguntas fuera de dominio NUEVAS (las del pool ya se
                                                   usaron en el desarrollo y no sirven para H5)

La ficha es ciega: solo trae el ID y el texto de cada pregunta (de pool_260_preliminar.csv). No muestra
bloque, documento candidato, artículo ni puntos. Las listas desplegables (tipo, documento, categoría,
confianza) salen del corpus V3 que usa el chatbot, para que los nombres de documento coincidan letra por
letra y el kappa no baje por errores de tipeo.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BANCO = AQUI.parent
sys.path.insert(0, str(AQUI))
import xlsx_simple  # noqa: E402

TIPOS = ["DIRECTA", "REQUISITOS", "PROCEDIMIENTO", "SIN_COBERTURA", "AMBIGUA"]
CATEGORIAS = ["A", "B", "C", "D", "E"]
CONFIANZA = ["alta", "media", "baja"]
NINGUNO = "(ninguno)"
COLUMNAS = ["pregunta_id", "pregunta", "tipo", "documento", "articulos", "documento_2", "articulos_2",
            "categoria", "respuesta_referencia", "puntos_clave", "confianza", "notas"]
EDITABLES = list(range(2, len(COLUMNAS)))
N_OOD_NUEVAS = 40


def _cargar_cb():
    spec = importlib.util.spec_from_file_location("cb", BANCO / "construir_banco_v32.py")
    cb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cb)
    return cb


def documentos_corpus() -> list[dict]:
    """[{documento, categoria, n_articulos}] del corpus V3 (vector_store/ del OE5), orden alfabético."""
    cb = _cargar_cb()
    coleccion, por_doc = cb.cargar_corpus()
    docs = []
    for metas in por_doc.values():
        nombre = (metas[0].get("documento") or "").removesuffix(".pdf")
        cat = Counter(m.get("categoria_tematica") for m in metas).most_common(1)[0][0]
        arts = {cb.num(m.get("articulo")) for m in metas if cb.num(m.get("articulo"))}
        docs.append({"documento": nombre, "categoria": cat or "", "n_articulos": len(arts), "coleccion": coleccion})
    return sorted(docs, key=lambda d: d["documento"].lower())


def preguntas_ciegas() -> list[tuple[str, str]]:
    with open(BANCO / "pool_260_preliminar.csv", encoding="utf-8-sig", newline="") as f:
        return [(r["pregunta_id"], r["texto"]) for r in csv.DictReader(f, delimiter=";")]


INSTRUCCIONES = [
    ["Gold set 260 — instrucciones para el anotador (resumen de evaluacion/banco/guia_anotacion.md)"],
    ["1. Trabaja SOLO, sin consultar al otro anotador ni usar el chatbot. Lee los PDF del corpus."],
    ["2. Completa las columnas amarillas de la hoja 'Anotacion'. No cambies pregunta_id ni el texto."],
    ["3. tipo: DIRECTA (un dato), REQUISITOS (lista de condiciones), PROCEDIMIENTO (pasos, plazos, oficinas), "
     "SIN_COBERTURA (el tema no está en los 48 documentos), AMBIGUA (dos intenciones o falta saber de qué trámite se habla)."],
    ["4. documento: elige de la lista (son los 48 del corpus). Si es SIN_COBERTURA o AMBIGUA deja '(ninguno)'."],
    ["5. articulos: los artículos que responden la pregunta, separados por ';' (ej.: Artículo 12°; Artículo 18°). "
     "Vacío si el documento no tiene artículos (TUPA, políticas, guías)."],
    ["6. documento_2 / articulos_2: solo si la respuesta completa necesita un segundo documento."],
    ["7. categoria: A Gobierno, B Académico, C Investigación, D Bienestar, E Laboral/docencia/políticas "
     "(la hoja 'Documentos' muestra la categoría de cada documento). Para SIN_COBERTURA/AMBIGUA deja vacío."],
    ["8. respuesta_referencia: la respuesta correcta en 1–3 oraciones, con tus palabras, según el documento."],
    ["9. puntos_clave: los datos que una respuesta completa DEBE incluir, separados por ';' "
     "(ej.: promedio mínimo 14; no tener deudas; presentar solicitud en marzo)."],
    ["10. confianza: alta / media / baja. Usa notas para explicar dudas o casos frontera."],
    ["Al terminar, guarda el archivo con tus iniciales: ficha_anotador_A_<INICIALES>.xlsx y entrégalo."],
]


def ficha(docs, preguntas) -> list[dict]:
    n = len(preguntas)
    filas = [COLUMNAS] + [[pid, texto] + [""] * (len(COLUMNAS) - 2) for pid, texto in preguntas]
    lista_docs = [[d["documento"], d["categoria"], d["n_articulos"]] for d in docs]
    fin_docs = len(lista_docs) + 2  # incluye la fila "(ninguno)"
    ref_docs = f"Documentos!$A$2:$A${fin_docs}"
    col = {c: i for i, c in enumerate(COLUMNAS)}
    return [
        {"nombre": "Instrucciones", "filas": INSTRUCCIONES, "anchos": [160]},
        {"nombre": "Anotacion", "filas": filas, "columnas_editables": EDITABLES,
         "anchos": [11, 48, 16, 40, 22, 30, 16, 10, 50, 50, 11, 30],
         "validaciones": [
             (col["tipo"], 2, n + 1, '"' + ",".join(TIPOS) + '"'),
             (col["documento"], 2, n + 1, ref_docs),
             (col["documento_2"], 2, n + 1, ref_docs),
             (col["categoria"], 2, n + 1, '"' + ",".join(CATEGORIAS) + '"'),
             (col["confianza"], 2, n + 1, '"' + ",".join(CONFIANZA) + '"'),
         ]},
        {"nombre": "Documentos", "filas": [["documento", "categoria", "n_articulos"], [NINGUNO, "", ""]] + lista_docs,
         "anchos": [70, 10, 12]},
    ]


def plantilla_ood() -> list[dict]:
    filas = [["id", "pregunta", "tipo_ood", "por_que_esta_fuera", "autor"]]
    filas += [[f"OODN_{i:02d}", "", "", "", ""] for i in range(1, N_OOD_NUEVAS + 1)]
    instr = [
        ["40 preguntas fuera de dominio NUEVAS para H5 (las 40 del pool ya se usaron al calibrar el umbral)"],
        ["Quién: alguien que no haya visto el sistema ni sus pruebas (idealmente no los anotadores A/B)."],
        ["Redáctalas como las escribiría un estudiante, sin probarlas en el chatbot."],
        ["tipo_ood 'lejana' (20): nada que ver con la universidad (clima, recetas, deportes, precios)."],
        ["tipo_ood 'cercana' (20): parece universitaria pero NO está en los 48 documentos "
         "(p. ej. normas de otra universidad, trámites de SUNEDU/MINEDU/SUNAT, datos personales de un alumno, "
         "horarios de un curso concreto). Son las que de verdad ponen a prueba la abstención."],
        ["Verifica en la hoja 'Documentos' de la ficha que el tema no esté en el corpus."],
    ]
    return [{"nombre": "Instrucciones", "filas": instr, "anchos": [150]},
            {"nombre": "OOD_nuevas", "filas": filas, "columnas_editables": [1, 2, 3, 4], "anchos": [11, 60, 12, 50, 14],
             "validaciones": [(2, 2, N_OOD_NUEVAS + 1, '"lejana,cercana"')]}]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    docs = documentos_corpus()
    preguntas = preguntas_ciegas()
    assert len(preguntas) == 260 and len({p for p, _ in preguntas}) == 260, "el pool debe tener 260 IDs únicos"
    for letra in ("A", "B"):
        xlsx_simple.escribir(AQUI / f"ficha_anotador_{letra}.xlsx", ficha(docs, preguntas))
    xlsx_simple.escribir(AQUI / "plantilla_ood_nuevas.xlsx", plantilla_ood())
    print(f"corpus {docs[0]['coleccion']}: {len(docs)} documentos · {len(preguntas)} preguntas")
    print("fichas: ficha_anotador_A.xlsx, ficha_anotador_B.xlsx, plantilla_ood_nuevas.xlsx")


if __name__ == "__main__":
    main()
