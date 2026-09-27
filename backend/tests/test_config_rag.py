# -*- coding: utf-8 -*-
"""Tests para configurabilidad RAG (Fase 4, §8/10/11).

Verifica:
- defaults 0.40/15/4
- overrides válidos por env
- valores inválidos y fuera de rango usan default + warning
- threshold fuera de [0,1] y TOP_K <=0
- pipeline usa realmente los valores configurados
- TOP_K_FINAL limita ANTES de construir_contexto()
- construir_contexto() no implementa lógica propia de TOP_K

Ejecución:
    docker exec oe5-backend python -m pytest /app/tests/test_config_rag.py -v
"""

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def _aislar_db_productiva(tmp_path, monkeypatch):
    """Todo generar_respuesta() va a DB temporal (no contaminar producción)."""
    import logger as _logger
    tmp = str(tmp_path / "config_test.db")
    monkeypatch.setattr(_logger, "DB_PATH", tmp)
    _logger.inicializar_bd()


# ---------------------------------------------------------------------------
# Helpers para recargar config con env modificado
# ---------------------------------------------------------------------------
def reload_config(monkeypatch, env_vars: dict):
    """Aplica env_vars, recarga config y retorna el módulo."""
    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
    # Limpiar del cache y reimportar
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])
    else:
        import config
    import config as cfg
    return cfg


def reload_config_clean(monkeypatch):
    """Limpia env vars relevantes y recarga config a defaults."""
    for k in ["RAG_DISTANCE_THRESHOLD", "RAG_TOP_K_RAW", "RAG_TOP_K_FINAL"]:
        monkeypatch.delenv(k, raising=False)
    if "config" in sys.modules:
        importlib.reload(sys.modules["config"])
    import config as cfg
    return cfg


# ===========================================================================
# Defaults
# ===========================================================================
class TestDefaults:
    def test_defaults_sin_env(self, monkeypatch):
        cfg = reload_config_clean(monkeypatch)
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.40
        assert cfg.RAG_TOP_K_RAW == 15
        assert cfg.RAG_TOP_K_FINAL == 4
        # Alias por compatibilidad apuntan a mismo valor
        assert cfg.UMBRAL_DISTANCIA_COSENO == cfg.RAG_DISTANCE_THRESHOLD
        assert cfg.TOP_K_FRAGMENTOS == cfg.RAG_TOP_K_FINAL

    def test_alias_son_mismos_objetos_valor(self, monkeypatch):
        cfg = reload_config_clean(monkeypatch)
        assert cfg.UMBRAL_DISTANCIA_COSENO is cfg.RAG_DISTANCE_THRESHOLD or cfg.UMBRAL_DISTANCIA_COSENO == cfg.RAG_DISTANCE_THRESHOLD
        assert cfg.TOP_K_FRAGMENTOS == cfg.RAG_TOP_K_FINAL


# ===========================================================================
# Overrides válidos
# ===========================================================================
class TestOverridesValidos:
    def test_override_threshold_valido(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "0.35"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.35
        assert cfg.UMBRAL_DISTANCIA_COSENO == 0.35

    def test_override_top_k_raw_valido(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_RAW": "20"})
        assert cfg.RAG_TOP_K_RAW == 20

    def test_override_top_k_final_valido(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_FINAL": "6"})
        assert cfg.RAG_TOP_K_FINAL == 6
        assert cfg.TOP_K_FRAGMENTOS == 6

    def test_override_threshold_limites(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "0"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.0
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "1"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 1.0

    def test_override_top_k_minimo(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_RAW": "1"})
        assert cfg.RAG_TOP_K_RAW == 1
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_FINAL": "1"})
        assert cfg.RAG_TOP_K_FINAL == 1


# ===========================================================================
# Valores inválidos y fuera de rango → fallback a default + warning
# ===========================================================================
class TestInvalidos:
    def test_threshold_no_numerico(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "nope"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.40
        assert "inválido" in caplog.text or "invalid" in caplog.text.lower() or "RAG_DISTANCE_THRESHOLD" in caplog.text

    def test_threshold_fuera_de_rango_bajo(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "-0.1"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.40

    def test_threshold_fuera_de_rango_alto(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": "1.5"})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.40

    def test_top_k_raw_no_entero(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_RAW": "abc"})
        assert cfg.RAG_TOP_K_RAW == 15

    def test_top_k_raw_cero(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_RAW": "0"})
        assert cfg.RAG_TOP_K_RAW == 15

    def test_top_k_final_cero(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_FINAL": "0"})
        assert cfg.RAG_TOP_K_FINAL == 4

    def test_top_k_final_negativo(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_FINAL": "-5"})
        assert cfg.RAG_TOP_K_FINAL == 4

    def test_top_k_raw_negativo(self, monkeypatch, caplog):
        cfg = reload_config(monkeypatch, {"RAG_TOP_K_RAW": "-2"})
        assert cfg.RAG_TOP_K_RAW == 15

    def test_env_vacio_usa_default(self, monkeypatch):
        cfg = reload_config(monkeypatch, {"RAG_DISTANCE_THRESHOLD": ""})
        assert cfg.RAG_DISTANCE_THRESHOLD == 0.40


# ===========================================================================
# Pipeline usa valores configurados
# ===========================================================================
class TestPipelineUsaConfig:
    """Verifica que generar_respuesta respeta RAG_* y que el límite
    TOP_K_FINAL se aplica ANTES de construir_contexto."""

    def test_top_k_raw_usado_en_query(self, monkeypatch):
        import config

        # Fijar TOP_K_RAW a 7 y verificar que collection.query recibe n_results=7
        monkeypatch.setenv("RAG_TOP_K_RAW", "7")
        importlib.reload(config)
        # Recargar rag_pipeline para que lea el nuevo valor
        import rag_pipeline
        importlib.reload(rag_pipeline)

        from unittest.mock import MagicMock, patch

        # Mock model: encode([q])[0].tolist() -> [0.1]*768
        mock_model = MagicMock()
        mock_emb = MagicMock()
        mock_emb.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = [mock_emb]
        rag_pipeline.model = mock_model

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["doc"] * 7],
            "metadatas": [[{"documento": f"DOC {i}", "categoria": "B", "chunk_id": f"id_{i}"} for i in range(7)]],
            "distances": [[0.1] * 7],
        }
        rag_pipeline.collection = mock_collection
        # Evitar validaciones previas
        monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: None)
        # Mock LLM para no llamar Ollama
        monkeypatch.setattr(rag_pipeline, "_invocar_llm_con_timeout", lambda prompt: "Respuesta de prueba (DOC, Artículo 1°)")

        try:
            rag_pipeline.generar_respuesta("pregunta de prueba con categoria becas", sesion_id="test-topk-raw")
        except Exception:
            pass

        # Verificar que se llamó con n_results == 7
        assert mock_collection.query.called
        kwargs = mock_collection.query.call_args[1]
        assert kwargs["n_results"] == 7

        # Restaurar defaults
        monkeypatch.delenv("RAG_TOP_K_RAW", raising=False)
        importlib.reload(config)
        importlib.reload(rag_pipeline)

    def test_threshold_filtra_correctamente(self, monkeypatch):
        import config
        monkeypatch.setenv("RAG_DISTANCE_THRESHOLD", "0.30")
        importlib.reload(config)
        import rag_pipeline
        importlib.reload(rag_pipeline)

        from unittest.mock import MagicMock, patch

        mock_model = MagicMock()
        mock_emb = MagicMock()
        mock_emb.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = [mock_emb]
        rag_pipeline.model = mock_model

        # 3 docs: distancias 0.1, 0.5, 0.2 -> solo 2 pasan threshold 0.30
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["doc1", "doc2", "doc3"]],
            "metadatas": [[
                {"documento": "DOC A", "categoria": "B", "chunk_id": "a"},
                {"documento": "DOC B", "categoria": "B", "chunk_id": "b"},
                {"documento": "DOC C", "categoria": "B", "chunk_id": "c"},
            ]],
            "distances": [[0.10, 0.50, 0.20]],
        }
        rag_pipeline.collection = mock_collection
        monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: None)
        monkeypatch.setattr(rag_pipeline, "_invocar_llm_con_timeout", lambda prompt: "Respuesta (DOC A, Artículo 1°)")

        result = rag_pipeline.generar_respuesta("pregunta de prueba", sesion_id="test-threshold")
        # Debe haber filtrado a 2 fuentes (0.10 y 0.20), no 3
        assert len(result["fuentes"]) == 2

        monkeypatch.delenv("RAG_DISTANCE_THRESHOLD", raising=False)
        importlib.reload(config)
        importlib.reload(rag_pipeline)

    def test_top_k_final_limita_antes_de_construir_contexto(self, monkeypatch):
        """RAG_TOP_K_FINAL debe limitar la selección ANTES de llamar a
        construir_contexto, y construir_contexto no debe truncar por sí mismo."""
        import config
        monkeypatch.setenv("RAG_TOP_K_FINAL", "2")
        monkeypatch.setenv("RAG_TOP_K_RAW", "15")
        importlib.reload(config)
        import rag_pipeline
        importlib.reload(rag_pipeline)

        from unittest.mock import MagicMock

        mock_model = MagicMock()
        mock_emb = MagicMock()
        mock_emb.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = [mock_emb]
        rag_pipeline.model = mock_model

        # 5 docs todos con dist < threshold, pero TOP_K_FINAL=2 → solo 2
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["d1", "d2", "d3", "d4", "d5"]],
            "metadatas": [[
                {"documento": f"DOC {i}", "categoria": "B", "chunk_id": f"id_{i}"} for i in range(5)
            ]],
            "distances": [[0.10, 0.11, 0.12, 0.13, 0.14]],
        }
        rag_pipeline.collection = mock_collection
        monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: None)

        captured = {}
        original_construir = rag_pipeline.construir_contexto

        def spy_construir(frags):
            captured["len"] = len(frags)
            captured["frags"] = frags
            return original_construir(frags)

        monkeypatch.setattr(rag_pipeline, "construir_contexto", spy_construir)
        monkeypatch.setattr(rag_pipeline, "_invocar_llm_con_timeout", lambda prompt: "Respuesta (DOC 0, Artículo 1°)")

        result = rag_pipeline.generar_respuesta("pregunta", sesion_id="test-limit")
        # construir_contexto debe haber recibido exactamente 2 fragmentos (no 5)
        assert captured["len"] == 2
        assert len(result["fuentes"]) == 2

        monkeypatch.delenv("RAG_TOP_K_FINAL", raising=False)
        monkeypatch.delenv("RAG_TOP_K_RAW", raising=False)
        importlib.reload(config)
        importlib.reload(rag_pipeline)


# ===========================================================================
# construir_contexto no implementa TOP_K por sí mismo
# ===========================================================================
class TestConstruirContextoNoTrunca:
    def test_construir_contexto_no_trunca(self):
        from context_builder import construir_contexto
        # Pasar 10 fragmentos, debe retornar 10 bloques FUENTE
        frags = [
            {"documento": f"DOC {i}", "text": f"Texto {i}", "distance": 0.1}
            for i in range(10)
        ]
        ctx = construir_contexto(frags)
        assert ctx.count("FUENTE ") == 10
        # No debe limitar a 4 (valor por defecto de RAG_TOP_K_FINAL)
        assert "FUENTE 10" in ctx

    def test_construir_contexto_respeta_lo_que_recibe(self):
        from context_builder import construir_contexto
        frags = [
            {"documento": f"DOC {i}", "text": f"Texto {i}", "distance": 0.1}
            for i in range(3)
        ]
        ctx = construir_contexto(frags)
        assert ctx.count("FUENTE ") == 3
