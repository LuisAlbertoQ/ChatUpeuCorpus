# -*- coding: utf-8 -*-
"""
Constructor de contexto y fuentes para el pipeline RAG (Fase 2 — PARTE 2).

Implementa dos funciones puras exigidas por docs/PARTE_2_CHATBOT_RAG.md §12 y §15:

- construir_contexto(fragmentos) → str  : bloque estructurado FUENTE N para el LLM
- construir_fuentes(fragmentos)   → list[str] : lista determinística de fuentes desde metadatos

Cada fragmento es un dict con las claves que existan entre:
  documento / document_title / document_id  → nombre del documento
  categoria / category                     → código A-E
  articulo / article / chapter / section  → sección detectada (opcional)
  chunk_id                               → id del chunk
  text / texto                           → contenido ya recortado (700 chars)
  distance                               → distancia coseno (opcional, para trazabilidad)
  page                                   → página si existe

Nota: no todas las claves existen en el corpus actual (ej. page, status);
el constructor incluye solo lo que existe, manteniendo el orden de
relevancia y sin mezclar metadata con contenido de forma ambigua (§13).
Las fuentes NO dependen del LLM: se derivan exclusivamente de los
metadatos recuperados (§15).
"""

import re

# Regex auxiliares (copia intencionada de rag_pipeline para evitar import circular)
_RE_ARTICULO = re.compile(
    r"(art[íi]culo\s*\d+[ºo°]?|cap[íi]tulo\s+[ivxlcdm\d]+|secci[óo]n\s+\d+)",
    re.IGNORECASE,
)
_RE_VERSION = re.compile(r"v\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_RE_ANIO = re.compile(r"\b(20\d{2})\b")


def _norm_categoria(cat: str) -> str:
    """Normaliza código de categoría a A-E mayúscula, o '' si vacío."""
    if not cat:
        return ""
    c = str(cat).strip().upper()
    return c if c in ("A", "B", "C", "D", "E") else c


def _extraer_articulo(texto: str, meta_articulo: str = "") -> str:
    """Prioriza articulo de metadata; si falta, extrae del texto."""
    if meta_articulo and meta_articulo.strip():
        return meta_articulo.strip()
    if not texto:
        return ""
    m = _RE_ARTICULO.search(texto[:300])
    return m.group(1).strip().capitalize() if m else ""


def _extraer_version_y_anio(documento: str) -> list[str]:
    extras: list[str] = []
    if not documento:
        return extras
    m_ver = _RE_VERSION.search(documento)
    m_anio = _RE_ANIO.search(documento)
    if m_ver:
        extras.append(f"v{m_ver.group(1)}")
    if m_anio:
        extras.append(m_anio.group(1))
    return extras


def construir_contexto(fragmentos: list[dict]) -> str:
    """
    Construye el contexto estructurado para el LLM a partir de fragmentos válidos.

    Cada bloque sigue §12:

        FUENTE N
        Documento: <titulo>
        Categoría: <nombre> (X)
        Artículo: <artículo>
        Chunk ID: <id>
        Distancia: 0.1234

        CONTENIDO:
        <texto>

    Solo se incluyen líneas cuyo dato existe. El orden de entrada
    (relevancia) se preserva. No se incluyen chunks descartados.
    """
    if not fragmentos:
        return ""

    # Import tardío para evitar ciclo si rag_pipeline importa este módulo
    try:
        from config import MAPEO_CATEGORIAS
    except Exception:
        MAPEO_CATEGORIAS = {}

    bloques: list[str] = []
    for idx, frag in enumerate(fragmentos, 1):
        if not isinstance(frag, dict):
            continue

        doc = (
            frag.get("documento")
            or frag.get("document_title")
            or frag.get("document_id")
            or ""
        ).strip()
        cat_raw = (
            frag.get("categoria")
            or frag.get("categoria_tematica")
            or frag.get("category")
            or ""
        )
        cat = _norm_categoria(cat_raw)
        articulo = _extraer_articulo(
            frag.get("text") or frag.get("texto") or "",
            frag.get("articulo") or frag.get("article") or "",
        )
        chunk_id = (frag.get("chunk_id") or "").strip()
        distance = frag.get("distance")
        text = frag.get("text") if "text" in frag else frag.get("texto", "")

        # Campos opcionales del spec §12
        chapter = (frag.get("chapter") or "").strip()
        section = (frag.get("section") or "").strip()
        article_alt = (frag.get("article") or "").strip()
        # Si article_alt existe y no hay articulo, usarlo
        if not articulo and article_alt:
            articulo = article_alt
        page = frag.get("page")
        # Fallback si page no existe en metadatos (corpus actual no lo tiene)
        if page is None or not str(page).strip():
            page = frag.get("pagina", "")
        version_info = _extraer_version_y_anio(doc)

        lineas: list[str] = [f"FUENTE {idx}"]
        if doc:
            lineas.append(f"Documento: {doc}")
        if cat:
            nombre = MAPEO_CATEGORIAS.get(cat, {}).get("nombre", "")
            if nombre:
                lineas.append(f"Categoría: {nombre} ({cat})")
            else:
                lineas.append(f"Categoría: {cat}")
        if version_info:
            lineas.append(f"Versión: {' '.join(version_info)}")
        if chapter:
            lineas.append(f"Capítulo: {chapter}")
        if section:
            lineas.append(f"Sección: {section}")
        if articulo:
            lineas.append(f"Artículo: {articulo}")
        if page is not None and str(page).strip():
            lineas.append(f"Página: {page}")
        if chunk_id:
            lineas.append(f"Chunk ID: {chunk_id}")
        if isinstance(distance, (int, float)):
            lineas.append(f"Distancia: {distance:.4f}")

        lineas.append("")
        lineas.append("CONTENIDO:")
        lineas.append(text or "")

        bloques.append("\n".join(lineas))

    return "\n\n".join(bloques)


def construir_fuentes(fragmentos: list[dict]) -> list[str]:
    """
    Construye la lista determinística de fuentes desde metadatos (§15).

    Formato: "Documento · Artículo · vX Año · [C – Nombre]"
    Solo se añaden segmentos cuyo dato existe. No depende del LLM.
    """
    if not fragmentos:
        return []

    try:
        from config import MAPEO_CATEGORIAS
    except Exception:
        MAPEO_CATEGORIAS = {}

    fuentes: list[str] = []
    for frag in fragmentos:
        if not isinstance(frag, dict):
            continue

        doc = (
            frag.get("documento")
            or frag.get("document_title")
            or frag.get("document_id")
            or "Documento sin nombre"
        ).strip()
        articulo = _extraer_articulo(
            frag.get("text") or frag.get("texto") or "",
            frag.get("articulo") or frag.get("article") or "",
        )
        cat_raw = (
            frag.get("categoria")
            or frag.get("categoria_tematica")
            or frag.get("category")
            or ""
        )
        cat = _norm_categoria(cat_raw)

        partes: list[str] = [doc]
        if articulo:
            partes.append(articulo)

        extras = _extraer_version_y_anio(doc)
        if extras:
            partes.append(" ".join(extras))

        if cat:
            if cat in MAPEO_CATEGORIAS:
                partes.append(f"[{cat} – {MAPEO_CATEGORIAS[cat]['nombre']}]")
            else:
                partes.append(f"[{cat}]")

        fuentes.append(" · ".join(partes))

    return fuentes
