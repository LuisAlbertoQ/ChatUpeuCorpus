#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_ficha.py

Genera la ficha documental del corpus institucional a partir de los
metadatos almacenados en la tabla `interacciones` y los datos
persistidos en `vector_store/`.

Salida:
    evaluacion/ficha_documental.md
"""

from __future__ import annotations

import datetime
import sqlite3
from collections import defaultdict
from pathlib import Path


EVAL_DIR = Path(__file__).parent
DB_PATH = EVAL_DIR.parent / "registro_interacciones.db"
FICHA_MD = EVAL_DIR / "ficha_documental.md"

MAPEO_CATEGORIAS = {
    "A": "Gobierno y estatuto institucional",
    "B": "Académico y estudios",
    "C": "Investigación",
    "D": "Bienestar estudiantil",
    "E": "Laboral, docencia y políticas",
}


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: no se encontró la base de datos en {DB_PATH}.")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tablas = {r[0] for r in cur.fetchall()}

    if "banco_preguntas" not in tablas:
        print("ERROR: tabla 'banco_preguntas' no existe. Ejecuta migrar_banco.py primero.")
        conn.close()
        return 1

    # Contar preguntas del banco
    total_banco = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
    activos = conn.execute(
        "SELECT COUNT(*) FROM banco_preguntas WHERE activa = 1"
    ).fetchone()[0]

    # Contar evaluaciones piloto
    total_piloto = 0
    if "evaluacion_piloto" in tablas:
        total_piloto = conn.execute(
            "SELECT COUNT(*) FROM evaluacion_piloto"
        ).fetchone()[0]

    # Contar interacciones
    total_inter = 0
    if "interacciones" in tablas:
        total_inter = conn.execute(
            "SELECT COUNT(*) FROM interacciones"
        ).fetchone()[0]

    conn.close()

    # Intentar leer metadatos del vector store para enumerar documentos
    docs_por_categoria = defaultdict(list)
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(EVAL_DIR.parent / "vector_store"))
        collection = client.get_collection("corpus_upeu")
        total_chunks = collection.count()

        resultados = collection.get(include=["metadatas"], limit=collection.count())
        for meta in resultados["metadatas"]:
            doc = meta.get("documento", "Desconocido")
            cat = meta.get("categoria", "?")
            docs_por_categoria[cat].append(doc)

        docs_unicos_por_cat = {
            cat: sorted(set(docs)) for cat, docs in docs_por_categoria.items()
        }
        total_docs = sum(len(v) for v in docs_unicos_por_cat.values())
    except Exception as exc:
        total_chunks = 0
        total_docs = 0
        docs_unicos_por_cat = {}
        print(f"AVISO: no se pudo leer el vector store: {exc}")

    # Generar Markdown
    hoy = datetime.date.today().isoformat()
    lineas = [
        "# Ficha documental del corpus UPeU",
        "",
        f"**Fecha de generación:** {hoy}",
        "",
        "## 1. Datos generales",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Versión del corpus | v1.0 |",
        f"| Total de documentos indexados | {total_docs} |",
        f"| Total de fragmentos (chunks) | {total_chunks} |",
        f"| Total de preguntas en banco | {total_banco} ({activos} activas) |",
        f"| Total de evaluaciones piloto registradas | {total_piloto} |",
        f"| Total de interacciones del chatbot | {total_inter} |",
        f"| Modelo de embeddings | paraphrase-multilingual-mpnet-base-v2 (768 dim) |",
        f"| Espacio vectorial | cosine |",
        f"| Última actualización | {hoy} |",
        "",
        "## 2. Distribución por categoría",
        "",
        "| Categoría | Nombre | # Documentos | # Fragmentos | % del corpus |",
        "|---|---|---:|---:|---:|",
    ]

    total_chunks_cat = sum(len(docs) for docs in docs_por_categoria.values()) or 1
    for cat in ["A", "B", "C", "D", "E"]:
        n_docs = len(docs_unicos_por_cat.get(cat, []))
        n_chunks = len(docs_por_categoria.get(cat, []))
        pct = n_chunks / total_chunks_cat * 100 if total_chunks_cat else 0
        lineas.append(
            f"| {cat} | {MAPEO_CATEGORIAS[cat]} | {n_docs} | {n_chunks} | {pct:.1f}% |"
        )

    lineas.extend([
        "",
        "## 3. Listado de documentos por categoría",
        "",
    ])

    for cat in ["A", "B", "C", "D", "E"]:
        docs = docs_unicos_por_cat.get(cat, [])
        if not docs:
            continue
        lineas.append(f"### Categoría {cat} — {MAPEO_CATEGORIAS[cat]}")
        lineas.append("")
        for i, doc in enumerate(docs, 1):
            lineas.append(f"{i}. {doc}")
        lineas.append("")

    lineas.extend([
        "## 4. Banco de preguntas activo",
        "",
        "| ID | Pregunta | Tipo | Documento esperado |",
        "|---|---|---|---|",
    ])

    if "banco_preguntas" in tablas:
        conn2 = sqlite3.connect(DB_PATH)
        for fila in conn2.execute(
            "SELECT id, pregunta, tipo_consulta, documento_esperado "
            "FROM banco_preguntas WHERE activa = 1 ORDER BY id"
        ):
            lineas.append(
                f"| {fila[0]} | {fila[1]} | {fila[2]} | {fila[3] or 'N/A'} |"
            )
        conn2.close()

    lineas.extend([
        "",
        "## 5. Criterios de inclusión / exclusión",
        "",
        "| Criterio | Tipo |",
        "|---|---|",
        "| Reglamentos oficiales de la UPeU vigentes | Incluido |",
        "| Lineamientos institucionales aprobados | Incluido |",
        "| Procedimientos administrativos publicados | Incluido |",
        "| Documentos con datos personales de terceros | Excluido |",
        "| Actas de sesiones internas no publicadas | Excluido |",
        "| Documentos en construcción / borrador | Excluido |",
        "| Documentos fuera del alcance temático | Excluido |",
        "",
        "---",
        "",
        f"_Ficha generada automáticamente el {hoy} por `generar_ficha.py`._",
    ])

    FICHA_MD.write_text("\n".join(lineas), encoding="utf-8")

    print("=" * 60)
    print("Ficha documental generada")
    print("=" * 60)
    print(f"Documentos indexados:    {total_docs}")
    print(f"Fragmentos totales:      {total_chunks}")
    print(f"Preguntas en banco:      {total_banco}")
    print(f"Interacciones del chat:  {total_inter}")
    print(f"Evaluaciones piloto:     {total_piloto}")
    print("=" * 60)
    print(f"Archivo: {FICHA_MD}")
    return 0


if __name__ == "__main__":
    exit(main())
