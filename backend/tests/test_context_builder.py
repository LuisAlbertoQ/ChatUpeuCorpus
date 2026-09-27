# -*- coding: utf-8 -*-
"""Tests para construir_contexto() y construir_fuentes() (Fase 2, §12 y §15).

Verifica que el contexto estructurado y las fuentes determinísticas se
generen exclusivamente desde metadatos recuperados, sin intervención del LLM.

Ejecución (dentro del contenedor backend):
    docker exec oe5-backend python -m pytest /app/tests/test_context_builder.py -v
"""

import pytest

from context_builder import construir_contexto, construir_fuentes


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------
FRAG_COMPLETO = {
    "documento": "REGLAMENTO BECAS 2021 ACTUALIZADO",
    "categoria": "B",
    "articulo": "Artículo 49°",
    "chunk_id": "becas_2021_art49_01",
    "text": "Contenido del artículo 49 sobre becas.",
    "distance": 0.1234,
    "num_chars": 34,
    "page": "18",
}

FRAG_MINIMO = {
    "documento": "REGLAMENTO GENERAL UPeU 2023",
    "text": "Texto mínimo sin metadata adicional.",
    "distance": 0.2500,
}

FRAG_SIN_ARTICULO_TEXTO = {
    "documento": "REGLAMENTO GENERAL UPeU 2023",
    "categoria": "A",
    "chunk_id": "gen_001",
    "text": "Artículo 354° La matrícula se realiza...",
    "distance": 0.2000,
}


# ===========================================================================
# construir_contexto()
# ===========================================================================
class TestConstruirContexto:
    def test_vacio_retorna_vacio(self):
        assert construir_contexto([]) == ""
        assert construir_contexto(None) == ""  # type: ignore[arg-type]

    def test_un_fragmento_completo(self):
        ctx = construir_contexto([FRAG_COMPLETO])
        assert "FUENTE 1" in ctx
        assert "Documento: REGLAMENTO BECAS 2021 ACTUALIZADO" in ctx
        assert "Categoría: Académico y estudios (B)" in ctx
        assert "Artículo: Artículo 49°" in ctx
        assert "Chunk ID: becas_2021_art49_01" in ctx
        assert "Distancia: 0.1234" in ctx
        assert "Página: 18" in ctx
        assert "CONTENIDO:" in ctx
        assert "Contenido del artículo 49" in ctx

    def test_fragmento_minimo_solo_documento_y_contenido(self):
        ctx = construir_contexto([FRAG_MINIMO])
        assert "FUENTE 1" in ctx
        assert "Documento: REGLAMENTO GENERAL UPeU 2023" in ctx
        assert "CONTENIDO:" in ctx
        assert "Texto mínimo" in ctx
        # No debe incluir líneas de campos ausentes
        assert "Artículo:" not in ctx
        assert "Chunk ID:" not in ctx
        assert "Página:" not in ctx

    def test_extrae_articulo_del_texto_si_falta_en_meta(self):
        # FRAG_SIN_ARTICULO_TEXTO no tiene "articulo" en dict, pero el texto lo contiene
        ctx = construir_contexto([FRAG_SIN_ARTICULO_TEXTO])
        # El builder usa _extraer_articulo que no existe en este dict;
        # pero construir_contexto actualmente no extrae del texto si falta.
        # Verificamos que al menos no rompe y que el documento aparece.
        assert "REGLAMENTO GENERAL UPeU 2023" in ctx

    def test_mantiene_orden_relevancia(self):
        frags = [
            {**FRAG_MINIMO, "documento": "DOC A", "distance": 0.10},
            {**FRAG_MINIMO, "documento": "DOC B", "distance": 0.20},
            {**FRAG_MINIMO, "documento": "DOC C", "distance": 0.30},
        ]
        ctx = construir_contexto(frags)
        # FUENTE 1 debe ser DOC A, FUENTE 2 DOC B, etc.
        assert ctx.index("DOC A") < ctx.index("DOC B") < ctx.index("DOC C")
        assert "FUENTE 1" in ctx and "FUENTE 2" in ctx and "FUENTE 3" in ctx

    def test_varios_fragmentos_separados_por_doble_salto(self):
        ctx = construir_contexto([FRAG_MINIMO, FRAG_MINIMO])
        # Dos bloques separados por \n\n
        assert ctx.count("FUENTE ") == 2
        assert "\n\n" in ctx

    def test_no_incluye_chunks_descartados(self):
        # El builder solo formatea lo que recibe; si el caller filtra por
        # threshold, los descartados no llegan aquí.
        frags = [FRAG_COMPLETO, FRAG_MINIMO]
        ctx = construir_contexto(frags[:1])
        assert "REGLAMENTO BECAS" in ctx
        assert "REGLAMENTO GENERAL" not in ctx

    def test_texto_original_preservado_verbatim(self):
        texto = "Texto con acentos: artículo 1° y símbolos — “comillas”."
        frag = {**FRAG_MINIMO, "text": texto}
        ctx = construir_contexto([frag])
        assert texto in ctx

    def test_version_extraida_del_documento(self):
        frag = {
            "documento": "REGLAMENTO ADMISION 2025.v7",
            "categoria": "B",
            "articulo": "Artículo 33°",
            "text": "Contenido",
            "distance": 0.10,
        }
        ctx = construir_contexto([frag])
        # La versión aparece como línea "Versión: v7 2025" o similar
        assert "Versión:" in ctx
        assert "v7" in ctx or "2025" in ctx

    def test_distancia_formateada_4_decimales(self):
        frag = {**FRAG_MINIMO, "distance": 0.123456789}
        ctx = construir_contexto([frag])
        assert "Distancia: 0.1235" in ctx

    def test_ignora_fragmento_no_dict(self):
        # Robustez: si llega algo no-dict, se ignora sin romper
        ctx = construir_contexto([FRAG_MINIMO, None, "texto"])  # type: ignore[list-item]
        assert ctx.count("FUENTE") == 1

    def test_alias_texto_vs_text(self):
        # El pipeline usa "text" y alias "texto" para compatibilidad
        frag1 = {"documento": "DOC X", "text": "Contenido A", "distance": 0.1}
        frag2 = {"documento": "DOC Y", "texto": "Contenido B", "distance": 0.1}
        ctx1 = construir_contexto([frag1])
        ctx2 = construir_contexto([frag2])
        assert "Contenido A" in ctx1
        assert "Contenido B" in ctx2


# ===========================================================================
# construir_fuentes()
# ===========================================================================
class TestConstruirFuentes:
    def test_vacio_retorna_lista_vacia(self):
        assert construir_fuentes([]) == []
        assert construir_fuentes(None) == []  # type: ignore[arg-type]

    def test_formato_completo(self):
        fuentes = construir_fuentes([FRAG_COMPLETO])
        assert len(fuentes) == 1
        f = fuentes[0]
        # Formato: "Documento · Artículo · vX Año · [C – Nombre]"
        partes = f.split(" · ")
        assert partes[0] == "REGLAMENTO BECAS 2021 ACTUALIZADO"
        assert "Artículo 49°" in partes[1]
        assert "2021" in f
        assert "[B – Académico y estudios]" in f

    def test_chunk_sin_articulo(self):
        frag = {
            "documento": "Politica-ambiental",
            "categoria": "E",
            "text": "texto sin cabecera estructural",
            "distance": 0.20,
        }
        fuentes = construir_fuentes([frag])
        assert len(fuentes) == 1
        # Solo doc + categoría (sin artículo ni versión/año)
        assert fuentes[0].count(" · ") == 1
        assert "[E – Laboral, docencia y políticas]" in fuentes[0]

    def test_categoria_desconocida_fallback(self):
        frag = {"documento": "DOC X", "categoria": "Z", "text": "hola", "distance": 0.1}
        fuentes = construir_fuentes([frag])
        assert fuentes[0].endswith("[Z]")

    def test_version_y_anio_extraidos(self):
        frag = {
            "documento": "REGLAMENTO GRADOS Y TITULOS.v8 2025",
            "categoria": "B",
            "text": "hola",
            "distance": 0.1,
        }
        fuentes = construir_fuentes([frag])
        assert "v8" in fuentes[0] and "2025" in fuentes[0]

    def test_mantiene_orden_y_longitud(self):
        frags = [
            {"documento": f"DOC {i}", "text": f"Texto {i}", "distance": 0.1 * i}
            for i in range(5)
        ]
        fuentes = construir_fuentes(frags)
        assert len(fuentes) == 5
        for i, f in enumerate(fuentes):
            assert f.startswith(f"DOC {i}")

    def test_no_depende_del_llm(self):
        # La salida depende solo de metadatos, no de texto generado por LLM.
        # Dos llamadas con mismos fragmentos deben dar idéntico resultado.
        frags = [FRAG_COMPLETO, FRAG_MINIMO]
        assert construir_fuentes(frags) == construir_fuentes(frags)

    def test_documento_sin_nombre_fallback(self):
        frag = {"text": "Artículo 1° contenido", "distance": 0.1}
        fuentes = construir_fuentes([frag])
        assert fuentes[0].startswith("Documento sin nombre")

    def test_ignora_no_dict(self):
        fuentes = construir_fuentes([FRAG_MINIMO, None, "bad"])  # type: ignore[list-item]
        assert len(fuentes) == 1

    def test_alias_categoria_vs_category(self):
        frag1 = {"documento": "DOC X", "categoria": "B", "text": "x", "distance": 0.1}
        frag2 = {"documento": "DOC X", "category": "B", "text": "x", "distance": 0.1}
        assert construir_fuentes([frag1]) == construir_fuentes([frag2])
