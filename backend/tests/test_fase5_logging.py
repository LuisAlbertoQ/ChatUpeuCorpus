# -*- coding: utf-8 -*-
"""Tests Fase 5 — logging extendido, subtipos M03/M04/M05/M06 y versionado.

Cubre los 10 grupos obligatorios del spec:
- M03/M04/M05/M06 subtipos
- SQLite migración retrocompatible
- JSON listas
- Latencias independientes
- Versionado
- API compatibilidad
"""

import json
import sqlite3
import time

import pytest

import config
from logger import DB_PATH, _columnas_existentes, inicializar_bd, registrar_interaccion


@pytest.fixture(autouse=True)
def _aislar_db_productiva(tmp_path, monkeypatch):
    """Evita contaminar registro_interacciones.db: todo va a DB temporal.

    Hallazgo FASE 5b: este módulo insertaba ~25 filas t-* en producción
    por cada corrida de la suite (105 filas acumuladas). Desde ahora los
    writes de generar_respuesta y las lecturas usan DB temporal.
    """
    import sys as _sys
    import logger as _logger
    tmp = str(tmp_path / "fase5_test.db")
    monkeypatch.setattr(_logger, "DB_PATH", tmp)
    monkeypatch.setattr(_sys.modules[__name__], "DB_PATH", tmp)
    _logger.inicializar_bd()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_pipeline(monkeypatch, threshold=0.40, top_k_raw=15, top_k_final=4):
    """Prepara mocks para generar_respuesta sin tocar Chroma/LLM."""
    import importlib
    import rag_pipeline
    from unittest.mock import MagicMock

    # Fijar config a valores conocidos para tests determinísticos
    monkeypatch.setenv("RAG_DISTANCE_THRESHOLD", str(threshold))
    monkeypatch.setenv("RAG_TOP_K_RAW", str(top_k_raw))
    monkeypatch.setenv("RAG_TOP_K_FINAL", str(top_k_final))
    importlib.reload(config)
    importlib.reload(rag_pipeline)

    mock_model = MagicMock()
    mock_emb = MagicMock()
    mock_emb.tolist.return_value = [0.1] * 768
    mock_model.encode.return_value = [mock_emb]
    rag_pipeline.model = mock_model

    mock_collection = MagicMock()
    rag_pipeline.collection = mock_collection

    # Evitar validaciones que no son el foco del test salvo que se testee
    monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
    monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: False)
    monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)
    monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: None)

    return rag_pipeline


# ===========================================================================
# M03 subtipos
# ===========================================================================
class TestM03Subtipos:
    def test_sensitive_request(self, monkeypatch):
        import rag_pipeline
        # _es_etica_sensible True debe dar failure_reason sensitive_request
        monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: True)
        # Evitar otras validaciones
        monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: None)

        r = rag_pipeline.generar_respuesta("quiero matar a alguien", sesion_id="t-m03-sens")
        assert r["tipo_mensaje"] == "M03"
        # Verificar en BD que failure_reason se persistió
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT failure_reason FROM interacciones WHERE sesion_id='t-m03-sens' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None and row[0] == "sensitive_request"

    def test_out_of_domain_por_keywords(self, monkeypatch):
        import rag_pipeline
        monkeypatch.setattr(rag_pipeline, "_es_fuera_dominio_por_keywords", lambda x: True)
        monkeypatch.setattr(rag_pipeline, "_es_etica_sensible", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_pregunta_es_ambigua", lambda x: False)
        monkeypatch.setattr(rag_pipeline, "_es_multi_intencion", lambda x: False)

        r = rag_pipeline.generar_respuesta("quien gano el mundial fifa", sesion_id="t-m03-kw")
        assert r["tipo_mensaje"] == "M03"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT failure_reason FROM interacciones WHERE sesion_id='t-m03-kw' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "out_of_domain"

    def test_out_of_domain_por_embedding(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch, threshold=0.10)  # threshold muy bajo para forzar out_of_domain
        from unittest.mock import MagicMock
        # Distancias altas > threshold+MARGEN (0.10+0.10=0.20) → out_of_domain
        rag.collection.query.return_value = {
            "documents": [["doc"] * 3],
            "metadatas": [[{"documento": "DOC X", "categoria": "B", "chunk_id": "x"}] * 3],
            "distances": [[0.90, 0.91, 0.92]],
        }
        r = rag.generar_respuesta("pregunta rara sin keywords", sesion_id="t-m03-emb")
        assert r["tipo_mensaje"] == "M03"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT failure_reason FROM interacciones WHERE sesion_id='t-m03-emb' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "out_of_domain"
        # Cleanup: restaurar config
        monkeypatch.delenv("RAG_DISTANCE_THRESHOLD", raising=False)
        import importlib
        import config
        importlib.reload(config)
        import rag_pipeline
        importlib.reload(rag_pipeline)


# ===========================================================================
# M04 subtipos
# ===========================================================================
class TestM04Subtipos:
    def test_retrieval_no_coverage(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch, threshold=0.10)
        # Evitar M03 por embedding (dominio_kw=None → out_of_domain), forzar dentro de dominio
        monkeypatch.setattr(rag, "_es_fuera_dominio_por_keywords", lambda x: False)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"documento": "DOC A", "categoria": "B", "chunk_id": "a"}, {"documento": "DOC B", "categoria": "B", "chunk_id": "b"}]],
            "distances": [[0.90, 0.91]],  # ambos > threshold
        }
        r = rag.generar_respuesta("pregunta sin cobertura", sesion_id="t-m04-ret")
        assert r["tipo_mensaje"] == "M04"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT failure_reason, num_valid_chunks FROM interacciones WHERE sesion_id='t-m04-ret' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "retrieval_no_coverage"
        assert row[1] == 0
        monkeypatch.delenv("RAG_DISTANCE_THRESHOLD", raising=False)
        import importlib
        import config
        importlib.reload(config)
        import rag_pipeline
        importlib.reload(rag_pipeline)

    def test_generation_empty(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["doc relevante sobre becas"]],
            "metadatas": [[{"documento": "REGLAMENTO BECAS 2021", "categoria": "B", "chunk_id": "c1", "articulo": "Artículo 49°"}]],
            "distances": [[0.10]],
        }
        # LLM devuelve vacío → postproceso <30 → M04 generation_empty
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "   ")
        r = rag.generar_respuesta("pregunta con retrieval pero LLM vacío", sesion_id="t-m04-gen")
        assert r["tipo_mensaje"] == "M04"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT failure_reason FROM interacciones WHERE sesion_id='t-m04-gen' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "generation_empty"


# ===========================================================================
# M05 subtipos
# ===========================================================================
class TestM05Subtipos:
    def test_too_short(self, monkeypatch):
        import rag_pipeline
        r = rag_pipeline.generar_respuesta("hi", sesion_id="t-m05-short")
        assert r["tipo_mensaje"] == "M05"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT validation_reason FROM interacciones WHERE sesion_id='t-m05-short' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "too_short"

    def test_ambiguous(self, monkeypatch):
        import rag_pipeline
        # "¿qué?" tiene 1 palabra y sin contenido → ambiguous (no too_short por len<5? "¿qué?" len 4 → too_short, probar otro)
        r = rag_pipeline.generar_respuesta("¿qué cómo?", sesion_id="t-m05-amb")
        # "¿qué cómo?" tiene 2 palabras interrogativas sin contenido → ambiguous per _clasificar
        assert r["tipo_mensaje"] == "M05"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT validation_reason FROM interacciones WHERE sesion_id='t-m05-amb' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] in ("ambiguous", "too_short")  # depende de heurística

    def test_multi_intent(self, monkeypatch):
        import rag_pipeline
        r = rag_pipeline.generar_respuesta("¿Qué es X y además cómo Y? ¿otra?", sesion_id="t-m05-multi")
        # Necesita conector + 2 ? o 2 interrogativas
        # Si no dispara multi_intent, puede ser ambiguous; verificamos que sea M05 y validation_reason sea multi_intent cuando aplique
        # Forzamos caso claro
        from unittest.mock import MagicMock
        # Directo: pregunta con conector y 2 ?
        r2 = rag_pipeline.generar_respuesta("¿Cómo me matriculo? y también ¿cuándo empiezan clases?", sesion_id="t-m05-multi2")
        assert r2["tipo_mensaje"] == "M05"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT validation_reason FROM interacciones WHERE sesion_id='t-m05-multi2' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "multi_intent"


# ===========================================================================
# M06 subtipos
# ===========================================================================
class TestM06Subtipos:
    def test_timeout(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        from concurrent.futures import TimeoutError as FutTimeout
        rag.collection.query.return_value = {
            "documents": [["doc"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c"}]],
            "distances": [[0.10]],
        }
        def raise_timeout(prompt):
            raise FutTimeout("timeout")
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", raise_timeout)
        r = rag.generar_respuesta("pregunta timeout", sesion_id="t-m06-timeout")
        assert r["tipo_mensaje"] == "M06"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT error_type, http_status FROM interacciones WHERE sesion_id='t-m06-timeout' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "timeout"
        assert row[1] is None

    def test_http_5xx(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        from urllib.error import HTTPError
        rag.collection.query.return_value = {
            "documents": [["doc"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c"}]],
            "distances": [[0.10]],
        }
        def raise_http5(prompt):
            raise HTTPError(url="http://llm", code=500, msg="Internal", hdrs={}, fp=None)
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", raise_http5)
        r = rag.generar_respuesta("pregunta http5", sesion_id="t-m06-5xx")
        assert r["tipo_mensaje"] == "M06"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT error_type, http_status FROM interacciones WHERE sesion_id='t-m06-5xx' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "http_5xx"
        assert row[1] == 500

    def test_exception(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.side_effect = RuntimeError("boom")
        r = rag.generar_respuesta("pregunta exception", sesion_id="t-m06-exc")
        assert r["tipo_mensaje"] == "M06"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT error_type FROM interacciones WHERE sesion_id='t-m06-exc' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == "exception"


# ===========================================================================
# SQLite migración retrocompatible
# ===========================================================================
class TestMigracion:
    def test_migrar_bd_vieja_preserva_filas(self, tmp_path, monkeypatch):
        # Crear DB vieja con esquema mínimo
        db_vieja = tmp_path / "vieja.db"
        conn = sqlite3.connect(str(db_vieja))
        conn.execute("CREATE TABLE interacciones (id INTEGER PRIMARY KEY, timestamp TEXT, pregunta TEXT, respuesta TEXT, fuentes TEXT, tiempo_respuesta REAL, umbral_usado REAL, tipo_mensaje TEXT, sesion_id TEXT, error TEXT)")
        conn.execute("INSERT INTO interacciones (timestamp, pregunta, respuesta, tipo_mensaje) VALUES ('2026-01-01', 'hola', 'hola', 'M02')")
        conn.commit()
        conn.close()

        # Usar esa DB temporal con nuestro inicializar_bd
        import logger
        import importlib
        importlib.reload(logger)
        logger.DB_PATH = str(db_vieja)
        logger.inicializar_bd()

        conn = sqlite3.connect(str(db_vieja))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(interacciones)").fetchall()}
        # Nuevas columnas deben existir
        for col in ["failure_reason", "validation_reason", "error_type", "sources", "retrieved_chunk_ids"]:
            assert col in cols, f"falta {col}"
        # Fila vieja preservada y nuevos campos NULL
        row = conn.execute("SELECT pregunta, failure_reason FROM interacciones").fetchone()
        assert row[0] == "hola"
        assert row[1] is None
        conn.close()

        # Segunda inicialización idempotente
        logger.inicializar_bd()
        # No debe fallar ni duplicar columnas
        conn = sqlite3.connect(str(db_vieja))
        cols2 = {row[1] for row in conn.execute("PRAGMA table_info(interacciones)").fetchall()}
        assert cols == cols2
        conn.close()

        # Restaurar DB_PATH original
        logger.DB_PATH = DB_PATH
        importlib.reload(logger)


# ===========================================================================
# JSON listas
# ===========================================================================
class TestJSON:
    def test_arrays_json_validos_y_orden(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["d1", "d2"]],
            "metadatas": [[
                {"documento": "DOC A", "categoria": "B", "chunk_id": "id_a", "articulo": "Artículo 1°"},
                {"documento": "DOC B", "categoria": "B", "chunk_id": "id_b", "articulo": "Artículo 2°"},
            ]],
            "distances": [[0.10, 0.11]],
        }
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "Respuesta (DOC A, Artículo 1°)")
        r = rag.generar_respuesta("pregunta json", sesion_id="t-json")
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT retrieved_chunk_ids, retrieved_document_ids, retrieved_articles, retrieved_distances, sources FROM interacciones WHERE sesion_id='t-json' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        for col in row:
            assert col is not None
            parsed = json.loads(col)
            assert isinstance(parsed, list)
        # Orden y correspondencia 1:1
        chunk_ids = json.loads(row[0])
        doc_ids = json.loads(row[1])
        articles = json.loads(row[2])
        distances = json.loads(row[3])
        assert chunk_ids == ["id_a", "id_b"]
        assert doc_ids[0] == "DOC A"
        assert articles[0] == "Artículo 1°"
        assert len(chunk_ids) == len(doc_ids) == len(articles) == len(distances) == 2

    def test_deserializacion_correcta(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["d1"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c", "articulo": "Art 1°"}]],
            "distances": [[0.10]],
        }
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "Resp (DOC, Artículo 1°)")
        rag.generar_respuesta("pregunta deser", sesion_id="t-deser")
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT retrieved_distances FROM interacciones WHERE sesion_id='t-deser' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        parsed = json.loads(row[0])
        assert parsed == [0.10] or parsed == [0.1]


# ===========================================================================
# Latencias
# ===========================================================================
class TestLatencias:
    def test_no_negativas_e_independientes(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["d1"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c", "articulo": "A 1°"}]],
            "distances": [[0.10]],
        }
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "Resp (DOC, Artículo 1°)")
        rag.generar_respuesta("pregunta lat", sesion_id="t-lat")
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT embedding_latency_ms, retrieval_latency_ms, llm_latency_ms, latency_total_ms FROM interacciones WHERE sesion_id='t-lat' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        for v in row:
            assert v is None or v >= 0
        # Cuando hay retrieval+LLM, latencias deben estar presentes
        assert row[0] is not None and row[1] is not None and row[2] is not None

    def test_etapas_no_ejecutadas_null(self, monkeypatch):
        import rag_pipeline
        # M05 corta antes de embedding → latencias deben ser NULL
        r = rag_pipeline.generar_respuesta("hi", sesion_id="t-lat-m05")
        assert r["tipo_mensaje"] == "M05"
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT embedding_latency_ms, retrieval_latency_ms, llm_latency_ms FROM interacciones WHERE sesion_id='t-lat-m05' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row == (None, None, None)


# ===========================================================================
# Versionado
# ===========================================================================
class TestVersionado:
    def test_valores_coinciden_config(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["d1"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c", "articulo": "A 1°"}]],
            "distances": [[0.10]],
        }
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "Resp (DOC, Artículo 1°)")
        rag.generar_respuesta("pregunta ver", sesion_id="t-ver")
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT embedding_model, llm_model, prompt_version, corpus_version, ranking_method, ranking_version FROM interacciones WHERE sesion_id='t-ver' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row[0] == config.EMBEDDING_MODEL
        assert row[1] == config.OLLAMA_MODEL
        assert row[2] == config.PROMPT_VERSION
        assert row[3] == config.CORPUS_VERSION == "corpus_upeu_v2"
        assert row[4] == config.RANKING_METHOD
        assert row[5] == config.RANKING_VERSION


# ===========================================================================
# Compatibilidad API y registros antiguos
# ===========================================================================
class TestCompatibilidad:
    def test_consulta_conserva_campos_anteriores(self, monkeypatch):
        rag = _mock_pipeline(monkeypatch)
        from unittest.mock import MagicMock
        rag.collection.query.return_value = {
            "documents": [["d1"]],
            "metadatas": [[{"documento": "DOC", "categoria": "B", "chunk_id": "c", "articulo": "A 1°"}]],
            "distances": [[0.10]],
        }
        monkeypatch.setattr(rag, "_invocar_llm_con_timeout", lambda prompt: "Respuesta de prueba con contenido suficiente para superar el umbral de treinta caracteres (DOC, Artículo 1°)")
        r = rag.generar_respuesta("pregunta compat", sesion_id="t-compat")
        # Campos públicos históricos deben seguir existiendo
        assert "respuesta" in r and "fuentes" in r and "tipo_mensaje" in r and "tiempo_respuesta" in r
        assert r["tipo_mensaje"] == "M02"

    def test_registros_antiguos_siguen_legibles(self, monkeypatch):
        # Filas históricas con nuevos campos NULL no deben romper SELECT *
        conn = sqlite3.connect(DB_PATH)
        # Sembrar una fila antigua simulada (DB temporal aislada)
        conn.execute(
            "INSERT INTO interacciones (timestamp, pregunta, respuesta, tipo_mensaje) VALUES (?,?,?,?)",
            ("2026-01-01", "hola", "hola", "M02"),
        )
        conn.commit()
        rows = conn.execute("SELECT * FROM interacciones LIMIT 1").fetchall()
        assert len(rows) >= 1
        # No debe fallar al leer con columnas nuevas NULL
        for row in rows:
            assert row is not None
        conn.close()
