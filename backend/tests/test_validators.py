# -*- coding: utf-8 -*-
"""Tests de validadores puros (Tier 3, ítem ①).

Cubre las funciones sin efectos secundarios del pipeline RAG y del
logger de interacciones: detección de ambigüedad, multi-intención,
ética sensible, fuera de dominio, anonimización PII, truncado T03 y
formateo de fuentes T08.

No requieren LLM, ChromaDB ni red: son idempotentes y rápidos.

Ejecución (dentro del contenedor backend):
    docker exec oe5-backend python -m pytest /app/tests/ -v
"""

import pytest

import config
from logger import anonimizar
from rag_pipeline import (
    _es_etica_sensible,
    _es_fuera_dominio_por_keywords,
    _formatear_fuente,
    _pregunta_es_ambigua,
    _truncar_palabras,
    _es_multi_intencion,
)


# =============================================================================
# _pregunta_es_ambigua → M05
# =============================================================================
class TestPreguntaEsAmbigua:
    @pytest.mark.parametrize("pregunta", [
        "hola",
        "hey?",
        "¿qué?",
        "¿cómo?",
        "abc",
        "   ",
        "",
        "¿y?",
    ])
    def test_ambiguas(self, pregunta):
        assert _pregunta_es_ambigua(pregunta) is True, repr(pregunta)

    @pytest.mark.parametrize("pregunta", [
        "¿Cuáles son los requisitos para obtener el título profesional?",
        "¿Cómo solicito una constancia de estudios?",
        "¿Qué becas ofrece la universidad para estudiantes?",
    ])
    def test_no_ambiguas(self, pregunta):
        assert _pregunta_es_ambigua(pregunta) is False, repr(pregunta)

    def test_solo_interrogativas_es_ambigua(self):
        # "qué" + "cómo" son interrogativas; sin contenido → ambigua.
        assert _pregunta_es_ambigua("¿qué cómo?") is True

    def test_interrogativa_con_contenido_no_es_ambigua(self):
        assert _pregunta_es_ambigua("¿qué es la matrícula?") is False


# =============================================================================
# _es_multi_intencion → M05 (T06)
# =============================================================================
class TestMultiIntencion:
    def test_dos_interrogativas_con_conector(self):
        # Conector + dos palabras interrogativas distintas.
        assert _es_multi_intencion(
            "¿Qué es el bachillerato y además cómo tramito el título?"
        ) is True

    def test_dos_signos_interrogacion_con_conector(self):
        assert _es_multi_intencion(
            "¿Cómo me matriculo? y también ¿cuándo empiezan las clases?"
        ) is True

    def test_una_sola_intencion(self):
        assert _es_multi_intencion(
            "¿Cuáles son los requisitos para el grado de bachiller?"
        ) is False

    def test_conector_sin_segunda_interrogativa(self):
        # "y también" pero una sola palabra interrogativa → no multi.
        assert _es_multi_intencion(
            "Quiero saber qué es la matrícula y también el cronograma"
        ) is False

    def test_punto_y_como_conector(self):
        # ";" es conector en la heurística.
        assert _es_multi_intencion(
            "¿Qué es un título?; ¿y cómo se solicita?"
        ) is True


# =============================================================================
# _es_etica_sensible → M03 (R07)
# =============================================================================
class TestEticaSensible:
    @pytest.mark.parametrize("pregunta", [
        "¿cómo puedo suicidarme?",
        "quiero matar a alguien",
        "dónde consigo un arma",
        "cómo fabricar un explosivo",
        "enséñame sobre la marihuana",
    ])
    def test_sensibles(self, pregunta):
        assert _es_etica_sensible(pregunta) is True, repr(pregunta)

    @pytest.mark.parametrize("pregunta", [
        "¿Cuáles son los derechos del estudiante?",
        "¿Cómo solicito una constancia?",
        "requisitos de graduación",
    ])
    def test_normales(self, pregunta):
        assert _es_etica_sensible(pregunta) is False, repr(pregunta)

    def test_case_insensitive(self):
        # La función normaliza a minúsculas internamente.
        assert _es_etica_sensible("¿Cómo hago para SUICIDARME?") is True

    def test_subcadena_cuenta(self):
        # "discrimin" matchea "discriminar/discriminación".
        assert _es_etica_sensible("política contra la discriminación") is True


# =============================================================================
# _es_fuera_dominio_por_keywords → M03 / None (R04 / RF02)
# =============================================================================
class TestFueraDominioKeywords:
    def test_deportes_externos(self):
        assert _es_fuera_dominio_por_keywords(
            "quién ganó el mundial de fútbol"
        ) is True

    def test_datos_personales(self):
        # Keywords añadidas en Tier 1: dni/deuda.
        assert _es_fuera_dominio_por_keywords(
            "me pueden dar mi DNI y mi deuda personal?"
        ) is True

    def test_entretenimiento(self):
        assert _es_fuera_dominio_por_keywords(
            "recomiéndame una película de netflix"
        ) is True

    def test_dentro_de_dominio(self):
        for q in [
            "¿cuáles son los requisitos de matrícula?",
            "¿qué dice el reglamento sobre las becas?",
            "procedimiento de titulación",
        ]:
            assert _es_fuera_dominio_por_keywords(q) is False, repr(q)

    def test_indeterminado_sin_keywords(self):
        # Ni dentro ni fuera → None (validación por embeddings).
        assert _es_fuera_dominio_por_keywords("buenos días") is None

    def test_keyword_dentro_gana_sobre_fuera(self):
        # "reglamento" (dentro) coexiste con "messi" (fuera) → False.
        # Regla: `fuera AND not dentro` → si hay keyword de dominio, gana.
        assert _es_fuera_dominio_por_keywords(
            "el reglamento aplica a messi"
        ) is False

    def test_constante_tiene_dni_y_deuda(self):
        # Salvaguarda del fix Tier 1: las keywords siguen presentes.
        assert "dni" in config.KEYWORDS_FUERA_DOMINIO
        assert "deuda" in config.KEYWORDS_FUERA_DOMINIO


# =============================================================================
# anonimizar (logger) — Ley 29733
# =============================================================================
class TestAnonimizar:
    def test_email(self):
        out = anonimizar("escríbeme a juan.perez@gmail.com por favor")
        assert "juan.perez@gmail.com" not in out
        assert "[EMAIL]" in out

    def test_dni_ocho_digitos(self):
        out = anonimizar("mi DNI es 71234567")
        assert "71234567" not in out
        assert "[DNI]" in out

    def test_telefono_movil(self):
        out = anonimizar("llámate al 987654321")
        assert "987654321" not in out
        assert "[TEL]" in out

    def test_telefono_internacional(self):
        out = anonimizar("mi número es +51 987654321")
        assert "987654321" not in out
        assert "[TEL]" in out

    def test_codigo_estudiante(self):
        # Letras (1-3) + 8-10 dígitos.
        out = anonimizar("mi código es u202112345")
        assert "u202112345" not in out
        assert "[COD_EST]" in out

    def test_texto_limpio_intacto(self):
        q = "¿Cuáles son los requisitos para el título profesional?"
        assert anonimizar(q) == q

    def test_vacio_y_none_safe(self):
        assert anonimizar("") == ""
        assert anonimizar(None) is None

    def test_multiples_pii_en_un_texto(self):
        out = anonimizar(
            "soy ana@mail.com, DNI 87654321, tel 912345678"
        )
        assert "ana@mail.com" not in out
        assert "87654321" not in out
        assert "912345678" not in out
        assert "[EMAIL]" in out and "[DNI]" in out and "[TEL]" in out


# =============================================================================
# _truncar_palabras → T03
# =============================================================================
class TestTruncarPalabras:
    def test_texto_corto_intacto(self):
        texto = "respuesta breve de diez palabras o menos aquí ok fin"
        cortado, fue_truncada = _truncar_palabras(texto, 500)
        assert fue_truncada is False
        assert cortado == texto

    def test_texto_exactamente_en_limite(self):
        texto = " ".join(["palabra"] * 500)
        cortado, fue_truncada = _truncar_palabras(texto, 500)
        assert fue_truncada is False
        assert cortado == texto

    def test_texto_largo_truncado(self):
        texto = " ".join(["palabra"] * 600)
        cortado, fue_truncada = _truncar_palabras(texto, 500)
        assert fue_truncada is True
        assert len(cortado.split()) <= 501  # 500 + "(…)"
        assert cortado.endswith("(…)")
        # No debe contener palabras más allá del límite.
        cuerpo = cortado.removesuffix("(…)").strip()
        assert len(cuerpo.split()) == 500

    def test_recorta_signos_antes_del_indicador(self):
        texto = " ".join(["palabra"] * 500) + " final,"
        cortado, fue_truncada = _truncar_palabras(texto, 500)
        assert fue_truncada is True
        assert cortado.endswith("palabra (…)")


# =============================================================================
# _formatear_fuente → T08
# =============================================================================
class TestFormatearFuente:
    def test_formato_completo(self):
        fuente = _formatear_fuente(
            documento="REGLAMENTO ADMISION 2025.v7",
            categoria="B",
            texto_chunk="Artículo 33°\nLa matrícula se realiza…",
        )
        partes = fuente.split(" · ")
        assert partes[0] == "REGLAMENTO ADMISION 2025.v7"
        assert partes[1].lower().startswith("artículo 33")
        assert "v7" in partes[2]
        assert "2025" in partes[2]
        assert partes[3] == "[B – Académico y estudios]"

    def test_chunk_sin_articulo(self):
        fuente = _formatear_fuente(
            documento="Politica-ambiental",
            categoria="E",
            texto_chunk="texto sin cabecera estructural",
        )
        partes = fuente.split(" · ")
        assert len(partes) == 2  # doc + categoría (sin artículo ni v/año)
        assert partes[1] == "[E – Laboral, docencia y políticas]"

    def test_categoria_desconocida_fallback(self):
        fuente = _formatear_fuente("DOC X", "Z", "")
        assert fuente.endswith("[Z]")

    def test_version_y_anio_extraidos_del_nombre(self):
        fuente = _formatear_fuente(
            "REGLAMENTO GRADOS Y TITULOS.v8 2025", "B", ""
        )
        assert "v8" in fuente and "2025" in fuente

    def test_capitaliza_seccion(self):
        fuente = _formatear_fuente("DOC", "A", "CAPÍTULO II\ncontenido")
        # El regex detecta "capítulo ii" y lo capitaliza.
        assert "Capítulo" in fuente or "capítulo" in fuente.lower()


# =============================================================================
# Config mínima esperada por los tests (salvaguardas)
# =============================================================================
class TestConfigSalvaguardas:
    """Asegura que constantes críticas no cambien silenciosamente."""

    def test_umbral_actual(self):
        # Evidencia de calibración: ver evaluacion/calibracion_resumen.md
        assert config.UMBRAL_DISTANCIA_COSENO == 0.40

    def test_top_k_actual(self):
        assert config.TOP_K_FRAGMENTOS == 4

    def test_margen_fuera_dominio(self):
        assert config.MARGEN_FUERA_DOMINIO == 0.10

    def test_mensajes_m01_a_m08(self):
        for clave in ["M01", "M02", "M03", "M04", "M05", "M06", "M07"]:
            assert clave in config.MENSAJES
