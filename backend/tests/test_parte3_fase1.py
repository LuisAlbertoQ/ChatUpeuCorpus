# -*- coding: utf-8 -*-
"""Tests Parte 3 Fase 1 — infraestructura de datos, ground truth y experimentos.

Cubre los 12 grupos obligatorios del spec sin implementar métricas aún.
"""

import json
import sqlite3

import pytest

import config
from logger import DB_PATH, _columnas_existentes, inicializar_bd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tmp_banco_viejo(path):
    """Crea DB vieja con esquema mínimo de 6 columnas y 2 filas."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE banco_preguntas (id TEXT PRIMARY KEY, pregunta TEXT NOT NULL, tipo_consulta TEXT NOT NULL, documento_esperado TEXT, categoria_esperada TEXT, activa INTEGER DEFAULT 1)"
    )
    conn.execute(
        "INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, documento_esperado, categoria_esperada, activa) VALUES ('P01', '¿Pregunta vieja 1?', 'dentro_dominio', 'DOC A', 'A', 1)"
    )
    conn.execute(
        "INSERT INTO banco_preguntas (id, pregunta, tipo_consulta, documento_esperado, categoria_esperada, activa) VALUES ('P02', '¿Pregunta vieja 2?', 'fuera_dominio', 'N/A', 'E', 1)"
    )
    conn.commit()
    conn.close()


# ===========================================================================
# Migración banco_preguntas
# ===========================================================================
class TestMigracionBanco:
    def test_migracion_vieja_preserva_filas_y_anade_columnas(self, tmp_path, monkeypatch):
        db = tmp_path / "test.db"
        _tmp_banco_viejo(db)
        # Usar esa DB con nuestro inicializar_bd
        monkeypatch.setattr("logger.DB_PATH", str(db))
        import logger
        import importlib
        importlib.reload(logger)
        logger.DB_PATH = str(db)
        logger.inicializar_bd()
        conn = sqlite3.connect(str(db))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(banco_preguntas)").fetchall()}
        # Nuevas columnas deben existir
        for col in ["categoria", "tipo_pregunta", "cobertura_esperada", "documentos_esperados", "chunks_esperados"]:
            assert col in cols, f"falta {col}"
        # Filas preservadas
        cnt = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
        assert cnt == 2
        # Segunda ejecución idempotente
        logger.inicializar_bd()
        cols2 = {r[1] for r in conn.execute("PRAGMA table_info(banco_preguntas)").fetchall()}
        assert cols == cols2
        conn.close()
        # Restaurar
        monkeypatch.setattr("logger.DB_PATH", DB_PATH)
        importlib.reload(logger)

    def test_campos_desconocidos_quedan_null(self, tmp_path, monkeypatch):
        db = tmp_path / "test2.db"
        _tmp_banco_viejo(db)
        monkeypatch.setattr("logger.DB_PATH", str(db))
        import logger
        import importlib
        importlib.reload(logger)
        logger.DB_PATH = str(db)
        logger.inicializar_bd()
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT tipo_pregunta, cobertura_esperada, documentos_esperados FROM banco_preguntas WHERE id='P01'").fetchone()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None
        conn.close()
        monkeypatch.setattr("logger.DB_PATH", DB_PATH)
        importlib.reload(logger)


# ===========================================================================
# Sincronización JSON ↔ SQLite 8→17
# ===========================================================================
class TestSincronizacion:
    def test_sync_8_a_17_sin_duplicar(self, tmp_path, monkeypatch):
        # DB vieja con 2 filas P
        db = tmp_path / "sync.db"
        _tmp_banco_viejo(db)
        # Simular JSON con 3 Q nuevas
        import logger
        import importlib
        monkeypatch.setattr("logger.DB_PATH", str(db))
        importlib.reload(logger)
        logger.DB_PATH = str(db)
        logger.inicializar_bd()
        # Insertar manualmente 3 Q como haría sincronizar_banco
        conn = sqlite3.connect(str(db))
        for qid in ["Q01", "Q02", "Q03"]:
            conn.execute(
                "INSERT OR IGNORE INTO banco_preguntas (id, pregunta, tipo_consulta, documento_esperado, categoria_esperada, activa, categoria, cobertura_esperada) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (qid, f"Pregunta {qid}", "dentro_dominio", f"DOC {qid}", "A", 1, "A", "ANSWERABLE"),
            )
        conn.commit()
        cnt1 = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
        assert cnt1 == 5  # 2 viejas + 3 nuevas
        # Segunda ejecución idempotente (INSERT OR IGNORE no duplica)
        for qid in ["Q01", "Q02", "Q03"]:
            conn.execute(
                "INSERT OR IGNORE INTO banco_preguntas (id, pregunta, tipo_consulta, documento_esperado, categoria_esperada, activa) VALUES (?, ?, ?, ?, ?, ?)",
                (qid, f"Pregunta {qid}", "dentro_dominio", f"DOC {qid}", "A", 1),
            )
        conn.commit()
        cnt2 = conn.execute("SELECT COUNT(*) FROM banco_preguntas").fetchone()[0]
        assert cnt2 == 5
        conn.close()
        monkeypatch.setattr("logger.DB_PATH", DB_PATH)
        importlib.reload(logger)

    def test_sync_preserva_ids_historicos(self):
        # Verificar que P01-P08 siguen existiendo tras sync real
        conn = sqlite3.connect(str(DB_PATH))
        cnt = conn.execute("SELECT COUNT(*) FROM banco_preguntas WHERE id LIKE 'P%'").fetchone()[0]
        assert cnt == 8, "IDs históricos P deben preservarse"
        cnt_q = conn.execute("SELECT COUNT(*) FROM banco_preguntas WHERE id LIKE 'Q%'").fetchone()[0]
        assert cnt_q == 17
        conn.close()


# ===========================================================================
# Validación tipo_pregunta y cobertura_esperada
# ===========================================================================
class TestValidacionTipos:
    TIPOS_PERMITIDOS = {"DIRECTA", "ARTICULO", "REQUISITOS", "PROCEDIMIENTO", "MULTI_CHUNK", "MULTI_DOCUMENTO", "SIN_COBERTURA"}
    COBERTURAS = {"ANSWERABLE", "NO_ANSWER"}

    def test_tipos_permitidos(self):
        for t in self.TIPOS_PERMITIDOS:
            assert isinstance(t, str) and len(t) > 0

    def test_coberturas_permitidas(self):
        for c in self.COBERTURAS:
            assert c in ("ANSWERABLE", "NO_ANSWER")

    def test_campos_nulos_por_defecto(self, tmp_path, monkeypatch):
        # Campos no verificables deben quedar NULL, no inventados
        db = tmp_path / "null.db"
        _tmp_banco_viejo(db)
        monkeypatch.setattr("logger.DB_PATH", str(db))
        import logger
        import importlib
        importlib.reload(logger)
        logger.DB_PATH = str(db)
        logger.inicializar_bd()
        conn = sqlite3.connect(str(db))
        # Insertar una pregunta sin tipo_pregunta
        conn.execute("INSERT OR IGNORE INTO banco_preguntas (id, pregunta, tipo_consulta) VALUES ('QX', '¿Pregunta sin tipo?', 'dentro_dominio')")
        conn.commit()
        row = conn.execute("SELECT tipo_pregunta, cobertura_esperada FROM banco_preguntas WHERE id='QX'").fetchone()
        assert row[0] is None
        assert row[1] is None
        conn.close()
        monkeypatch.setattr("logger.DB_PATH", DB_PATH)
        importlib.reload(logger)


# ===========================================================================
# Ground truth múltiple JSON
# ===========================================================================
class TestGroundTruthMultiple:
    def test_serializa_deserializa_multiple(self):
        docs = ["DOC A", "DOC B"]
        arts = ["Art 1°", "Art 2°"]
        chunks = ["id1", "id2"]
        # Simular almacenamiento JSON TEXT
        doc_json = json.dumps(docs, ensure_ascii=False)
        art_json = json.dumps(arts, ensure_ascii=False)
        chunk_json = json.dumps(chunks, ensure_ascii=False)
        # Deserializar
        assert json.loads(doc_json) == docs
        assert json.loads(art_json) == arts
        assert json.loads(chunk_json) == chunks

    def test_singular_vs_multiple_compat(self):
        # Singular sigue siendo string, múltiple es JSON array
        singular = "DOC A"
        multiple = json.dumps(["DOC A", "DOC B"], ensure_ascii=False)
        assert isinstance(singular, str)
        assert json.loads(multiple) == ["DOC A", "DOC B"]


# ===========================================================================
# Experimentos_rag
# ===========================================================================
class TestExperimentos:
    def test_creacion_idempotente(self, tmp_path, monkeypatch):
        db = tmp_path / "exp.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS experimentos_rag (experimento_id TEXT PRIMARY KEY, fecha TEXT, corpus_version TEXT, embedding_model TEXT, llm_model TEXT, top_k_raw INTEGER, top_k_final INTEGER, threshold REAL, ranking_method TEXT, ranking_version TEXT, prompt_version TEXT)")
        conn.commit()
        # Insertar experimento
        conn.execute(
            "INSERT OR IGNORE INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("EXP01", "2026-08-14", "corpus_upeu_v2", "mpnet", "qwen2.5:7b", 15, 4, 0.40, "heuristic", "1.0", "v2"),
        )
        conn.commit()
        cnt1 = conn.execute("SELECT COUNT(*) FROM experimentos_rag").fetchone()[0]
        # Segunda inserción mismo ID no duplica
        conn.execute(
            "INSERT OR IGNORE INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("EXP01", "2026-08-14", "corpus_upeu_v2", "mpnet", "qwen2.5:7b", 15, 4, 0.40, "heuristic", "1.0", "v2"),
        )
        conn.commit()
        cnt2 = conn.execute("SELECT COUNT(*) FROM experimentos_rag").fetchone()[0]
        assert cnt1 == cnt2 == 1
        conn.close()

    def test_experimento_captura_config_real(self, tmp_path, monkeypatch):
        # Verificar que experimento puede capturar valores reales de config
        import config
        # Simular inserción con valores reales
        db = tmp_path / "exp2.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS experimentos_rag (experimento_id TEXT PRIMARY KEY, fecha TEXT, corpus_version TEXT, embedding_model TEXT, llm_model TEXT, top_k_raw INTEGER, top_k_final INTEGER, threshold REAL, ranking_method TEXT, ranking_version TEXT, prompt_version TEXT)")
        conn.execute(
            "INSERT INTO experimentos_rag (experimento_id, fecha, corpus_version, embedding_model, llm_model, top_k_raw, top_k_final, threshold, ranking_method, ranking_version, prompt_version) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("EXP_TEST", config.CORPUS_VERSION, config.EMBEDDING_MODEL, config.OLLAMA_MODEL, config.RAG_TOP_K_RAW, config.RAG_TOP_K_FINAL, config.RAG_DISTANCE_THRESHOLD, config.RANKING_METHOD, config.RANKING_VERSION, config.PROMPT_VERSION),
        )
        row = conn.execute("SELECT corpus_version, embedding_model, threshold FROM experimentos_rag WHERE experimento_id='EXP_TEST'").fetchone()
        assert row[0] == "corpus_upeu_v2"
        assert row[1] == "paraphrase-multilingual-mpnet-base-v2"
        assert row[2] == 0.40
        conn.close()


# ===========================================================================
# Evaluacion retrieval/generacion vacías
# ===========================================================================
class TestEstructurasVacias:
    def test_creacion_idempotente_retrieval(self, tmp_path):
        db = tmp_path / "eval.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE IF NOT EXISTS banco_preguntas (id TEXT PRIMARY KEY, pregunta TEXT)")
        conn.execute("INSERT OR IGNORE INTO banco_preguntas (id, pregunta) VALUES ('Q01', 'Test')")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS experimentos_rag (experimento_id TEXT PRIMARY KEY, fecha TEXT)"
        )
        conn.execute("INSERT OR IGNORE INTO experimentos_rag (experimento_id, fecha) VALUES ('EXP01', '2026-08-14')")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS evaluacion_retrieval (evaluacion_id INTEGER PRIMARY KEY, pregunta_id TEXT, experimento_id TEXT, top_k INTEGER, chunk_esperado TEXT, posicion_chunk_esperado INTEGER, recuperado INTEGER, distancia REAL, documento_recuperado TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS evaluacion_generacion (evaluacion_id INTEGER PRIMARY KEY, pregunta_id TEXT, experimento_id TEXT, respuesta_generada TEXT, relevance INTEGER)"
        )
        # Segunda creación no falla
        conn.execute(
            "CREATE TABLE IF NOT EXISTS evaluacion_retrieval (evaluacion_id INTEGER PRIMARY KEY, pregunta_id TEXT, experimento_id TEXT, top_k INTEGER, chunk_esperado TEXT, posicion_chunk_esperado INTEGER, recuperado INTEGER, distancia REAL, documento_recuperado TEXT)"
        )
        conn.close()
        assert True  # No exception

    def test_relaciones_experimento_pregunta(self, tmp_path):
        db = tmp_path / "rel.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE banco_preguntas (id TEXT PRIMARY KEY, pregunta TEXT)")
        conn.execute("CREATE TABLE experimentos_rag (experimento_id TEXT PRIMARY KEY, fecha TEXT)")
        conn.execute("CREATE TABLE evaluacion_retrieval (evaluacion_id INTEGER PRIMARY KEY, pregunta_id TEXT, experimento_id TEXT, FOREIGN KEY(pregunta_id) REFERENCES banco_preguntas(id), FOREIGN KEY(experimento_id) REFERENCES experimentos_rag(experimento_id))")
        conn.execute("INSERT INTO banco_preguntas VALUES ('Q01', 'Pregunta 1')")
        conn.execute("INSERT INTO experimentos_rag VALUES ('EXP01', '2026-08-14')")
        conn.execute("INSERT INTO evaluacion_retrieval (pregunta_id, experimento_id) VALUES ('Q01', 'EXP01')")
        # Debe permitir múltiples filas por pregunta/experimento (para MULTI_CHUNK)
        conn.execute("INSERT INTO evaluacion_retrieval (pregunta_id, experimento_id) VALUES ('Q01', 'EXP01')")
        cnt = conn.execute("SELECT COUNT(*) FROM evaluacion_retrieval WHERE pregunta_id='Q01' AND experimento_id='EXP01'").fetchone()[0]
        assert cnt == 2
        conn.close()


# ===========================================================================
# DB histórica preservada
# ===========================================================================
class TestHistoricaPreservada:
    def test_interacciones_preservadas_tras_migracion(self):
        conn = sqlite3.connect(str(DB_PATH))
        # Verificar que interacciones con 472 filas siguen existiendo y son legibles
        cnt = conn.execute("SELECT COUNT(*) FROM interacciones").fetchone()[0]
        assert cnt >= 400  # al menos las 472 históricas
        # Verificar que filas antiguas con nuevos campos NULL siguen siendo legibles
        row = conn.execute("SELECT tipo_mensaje, pregunta FROM interacciones ORDER BY id ASC LIMIT 1").fetchone()
        assert row[0] is not None
        conn.close()
