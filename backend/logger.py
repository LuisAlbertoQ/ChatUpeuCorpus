import json
import sqlite3
import datetime
from contextlib import contextmanager
from config import PII_PATTERNS

DB_PATH = "/data/registro_interacciones.db"


# -----------------------------------------------------------------------------
# Anonimización (sección 3.2 OE4 + Ley 29733)
# -----------------------------------------------------------------------------
def anonimizar(texto: str) -> str:
    """Aplica los patrones PII configurados sobre el texto.

    Reemplaza DNI, emails, teléfonos y códigos de estudiante por etiquetas
    no reversibles antes de persistir cualquier dato.
    """
    if not texto:
        return texto
    resultado = texto
    for patron, reemplazo in PII_PATTERNS:
        resultado = patron.sub(reemplazo, resultado)
    return resultado


# -----------------------------------------------------------------------------
# Conexión y esquema
# -----------------------------------------------------------------------------
@contextmanager
def _conn():
    """Context manager con foreign keys habilitadas."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columnas_existentes(conn, tabla: str) -> set:
    cur = conn.execute(f"PRAGMA table_info({tabla})")
    return {row[1] for row in cur.fetchall()}


def inicializar_bd():
    """Crea la tabla y aplica migraciones no destructivas si faltan columnas."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pregunta TEXT NOT NULL,
                respuesta TEXT NOT NULL,
                fuentes TEXT,
                tiempo_respuesta REAL,
                umbral_usado REAL,
                tipo_mensaje TEXT,
                sesion_id TEXT,
                error TEXT,
                pregunta_normalizada TEXT,
                latency_total_ms REAL,
                embedding_latency_ms REAL,
                retrieval_latency_ms REAL,
                llm_latency_ms REAL,
                top_k_raw INTEGER,
                top_k_final INTEGER,
                threshold_used REAL,
                num_valid_chunks INTEGER,
                retrieved_chunk_ids TEXT,
                retrieved_document_ids TEXT,
                retrieved_articles TEXT,
                retrieved_distances TEXT,
                sources TEXT,
                citation_validation TEXT,
                citation_repairs INTEGER,
                embedding_model TEXT,
                llm_model TEXT,
                prompt_version TEXT,
                corpus_version TEXT,
                ranking_method TEXT,
                ranking_version TEXT,
                http_status INTEGER,
                failure_reason TEXT,
                validation_reason TEXT,
                error_type TEXT
            )
            """
        )
        # Migración para BDs antiguas que ya tengan datos — idempotente
        existentes = _columnas_existentes(conn, "interacciones")
        # Columnas añadidas en Fase 5 (§19) — solo si faltan
        nuevas_columnas = {
            "pregunta_normalizada": "TEXT",
            "latency_total_ms": "REAL",
            "embedding_latency_ms": "REAL",
            "retrieval_latency_ms": "REAL",
            "llm_latency_ms": "REAL",
            "top_k_raw": "INTEGER",
            "top_k_final": "INTEGER",
            "threshold_used": "REAL",
            "num_valid_chunks": "INTEGER",
            "retrieved_chunk_ids": "TEXT",
            "retrieved_document_ids": "TEXT",
            "retrieved_articles": "TEXT",
            "retrieved_distances": "TEXT",
            "sources": "TEXT",
            "citation_validation": "TEXT",
            "citation_repairs": "INTEGER",
            "embedding_model": "TEXT",
            "llm_model": "TEXT",
            "prompt_version": "TEXT",
            "corpus_version": "TEXT",
            "ranking_method": "TEXT",
            "ranking_version": "TEXT",
            "http_status": "INTEGER",
            "failure_reason": "TEXT",
            "validation_reason": "TEXT",
            "error_type": "TEXT",
            "sesion_id": "TEXT",
            "error": "TEXT",
            "anonimizado_en": "TEXT",
        }
        for col, tipo in nuevas_columnas.items():
            if col not in existentes:
                conn.execute(f"ALTER TABLE interacciones ADD COLUMN {col} {tipo}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_interacciones_sesion ON interacciones(sesion_id)"
        )

        # ---------------------------------------------------------------------
        # Tablas para evaluación de madurez (OE8, modelo CMMI--TRL)
        # ---------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS banco_preguntas (
                id TEXT PRIMARY KEY,
                pregunta TEXT NOT NULL,
                tipo_consulta TEXT NOT NULL,
                documento_esperado TEXT,
                categoria_esperada TEXT,
                activa INTEGER DEFAULT 1
            )
            """
        )
        # Fase 3 Parte 3: ampliar banco_preguntas para ground truth estructurado (§4-7)
        # No borrar columnas antiguas; añadir nuevas de forma no destructiva.
        _banco_existentes = _columnas_existentes(conn, "banco_preguntas")
        _banco_nuevas = {
            "categoria": "TEXT",  # alias normalizado de categoria_esperada
            "tipo_pregunta": "TEXT",  # DIRECTA/ARTICULO/REQUISITOS/PROCEDIMIENTO/MULTI_CHUNK/MULTI_DOCUMENTO/SIN_COBERTURA
            "documentos_esperados": "TEXT",  # JSON array para múltiples documentos
            "articulos_esperados": "TEXT",  # JSON array
            "seccion_esperada": "TEXT",
            "pagina_esperada": "TEXT",
            "chunks_esperados": "TEXT",  # JSON array
            "respuesta_esperada": "TEXT",
            "cobertura_esperada": "TEXT",  # ANSWERABLE / NO_ANSWER
            "articulo_esperado": "TEXT",  # compatibilidad con JSON que usa articulo_esperado
            "secciones_esperadas": "TEXT",
            "paginas_esperadas": "TEXT",
            "banco_version": "TEXT",  # v2_tecnico para Q01-Q17, NULL/histórico para P01-P08
            "puntos_esperados": "TEXT",  # JSON array de {punto_id, descripcion, obligatorio}
            "evidencias_esperadas": "TEXT",  # JSON array de {punto_id, documento, articulo, texto_evidencia}
        }
        for col, tipo in _banco_nuevas.items():
            if col not in _banco_existentes:
                try:
                    conn.execute(f"ALTER TABLE banco_preguntas ADD COLUMN {col} {tipo}")
                except Exception:
                    pass  # idempotente, ignora si ya existe por carrera
        # Crear tablas de evaluación técnica (vacías, sin métricas aún) §8, §12, §15
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experimentos_rag (
                experimento_id TEXT PRIMARY KEY,
                fecha TEXT NOT NULL,
                corpus_version TEXT,
                embedding_model TEXT,
                llm_model TEXT,
                top_k_raw INTEGER,
                top_k_final INTEGER,
                threshold REAL,
                ranking_method TEXT,
                ranking_version TEXT,
                prompt_version TEXT,
                descripcion TEXT,
                estado TEXT,
                notas TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_retrieval (
                evaluacion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pregunta_id TEXT NOT NULL,
                experimento_id TEXT NOT NULL,
                top_k INTEGER,
                chunk_esperado TEXT,
                posicion_chunk_esperado INTEGER,
                recuperado INTEGER,
                distancia REAL,
                documento_recuperado TEXT,
                articulo_recuperado TEXT,
                seccion_recuperada TEXT,
                pagina_recuperada TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id),
                FOREIGN KEY (experimento_id) REFERENCES experimentos_rag(experimento_id)
            )
            """
        )
        # Fase 3 Parte 3: ampliar evaluacion_retrieval para métricas @K y estados
        _eval_ret_exist = _columnas_existentes(conn, "evaluacion_retrieval")
        _eval_ret_nuevas = {
            "chunk_id_recuperado": "TEXT",
            "distancia_original": "REAL",
            "distancia_ajustada": "REAL",
            "rank_raw": "INTEGER",
            "rank_reranked": "INTEGER",
            "sobrevivio_threshold": "INTEGER",
            "entro_top4": "INTEGER",
            "es_relevante_documento": "INTEGER",
            "es_relevante_articulo": "INTEGER",
        }
        for col, tipo in _eval_ret_nuevas.items():
            if col not in _eval_ret_exist:
                try:
                    conn.execute(f"ALTER TABLE evaluacion_retrieval ADD COLUMN {col} {tipo}")
                except Exception:
                    pass
        # Tabla agregada para métricas por experimento (preferencia SQLite + CSV)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metricas_retrieval_experimento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experimento_id TEXT NOT NULL,
                unidad TEXT NOT NULL,
                metrica TEXT NOT NULL,
                k INTEGER,
                valor REAL NOT NULL,
                n_preguntas INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (experimento_id) REFERENCES experimentos_rag(experimento_id),
                UNIQUE(experimento_id, unidad, metrica, k)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_generacion (
                evaluacion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pregunta_id TEXT NOT NULL,
                experimento_id TEXT NOT NULL,
                respuesta_generada TEXT,
                respuesta_esperada TEXT,
                relevancia INTEGER,
                faithfulness INTEGER,
                completitud INTEGER,
                citation_precision REAL,
                citation_correctness REAL,
                respuesta_valida INTEGER,
                evaluador TEXT,
                timestamp TEXT NOT NULL,
                abstention_correctness INTEGER,
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id),
                FOREIGN KEY (experimento_id) REFERENCES experimentos_rag(experimento_id)
            )
            """
        )
        # Fase 3 generación: añadir columnas para puntos y fuentes generadas y métricas separadas
        _eval_gen_exist = _columnas_existentes(conn, "evaluacion_generacion")
        _eval_gen_nuevas = {
            "puntos_esperados": "TEXT",  # JSON snapshot de puntos para completitud
            "evidencias_esperadas": "TEXT",  # JSON snapshot
            "fuentes_generadas": "TEXT",  # JSON array de fuentes mostradas
            "source_validity": "TEXT",  # valid / invalid
            "citation_match": "TEXT",  # valid / invalid / not_applicable
            "citation_correctness_humana": "TEXT",  # pendiente humana
        }
        for col, tipo in _eval_gen_nuevas.items():
            if col not in _eval_gen_exist:
                try:
                    conn.execute(f"ALTER TABLE evaluacion_generacion ADD COLUMN {col} {tipo}")
                except Exception:
                    pass
        # Ampliación no destructiva para baseline generación oficial V3 (§2-3, §7-12)
        # Nuevas columnas determinísticas sin romper FK existentes
        _eval_gen_v3_nuevas = {
            "generacion_experimento_id": "TEXT",
            "retrieval_experimento_id": "TEXT",
            "tipo_mensaje": "TEXT",
            "failure_reason": "TEXT",
            "citation_validation": "TEXT",
            "citation_repairs": "INTEGER",
            "answerable_but_abstained": "INTEGER",
            "citation_presence": "INTEGER",
            "citas_detectadas": "TEXT",
            "citas_validas": "TEXT",
            "citation_match_ratio": "REAL",
        }
        _eval_gen_exist2 = _columnas_existentes(conn, "evaluacion_generacion")
        for col, tipo in _eval_gen_v3_nuevas.items():
            if col not in _eval_gen_exist2:
                try:
                    conn.execute(f"ALTER TABLE evaluacion_generacion ADD COLUMN {col} {tipo}")
                except Exception:
                    pass
        # Tabla snapshot de generación oficial (no rompe FK de experimentos_rag)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generacion_experimentos (
                generacion_experimento_id TEXT PRIMARY KEY,
                retrieval_experimento_id TEXT NOT NULL,
                corpus_version TEXT,
                llm_model TEXT,
                prompt_version TEXT,
                temperature REAL,
                seed TEXT,
                fecha TEXT NOT NULL,
                estado TEXT,
                descripcion TEXT,
                FOREIGN KEY (retrieval_experimento_id) REFERENCES experimentos_rag(experimento_id)
            )
            """
        )
        # Tablas detalle para evaluación humana no automatizada (Parte 3 §14)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_completitud_detalle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generacion_experimento_id TEXT NOT NULL,
                pregunta_id TEXT NOT NULL,
                punto_id TEXT NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN ('CUBIERTO','PARCIAL','NO_CUBIERTO')),
                justificacion TEXT,
                fragmento_respuesta TEXT,
                evaluador TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(generacion_experimento_id, pregunta_id, punto_id),
                FOREIGN KEY (generacion_experimento_id) REFERENCES generacion_experimentos(generacion_experimento_id),
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_faithfulness_detalle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generacion_experimento_id TEXT NOT NULL,
                pregunta_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                claim_texto TEXT NOT NULL,
                estado TEXT NOT NULL CHECK (estado IN ('SOPORTADO','PARCIALMENTE_SOPORTADO','NO_SOPORTADO')),
                evidencia_contexto TEXT,
                evaluador TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(generacion_experimento_id, pregunta_id, claim_id),
                FOREIGN KEY (generacion_experimento_id) REFERENCES generacion_experimentos(generacion_experimento_id),
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_citation_correctness_detalle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generacion_experimento_id TEXT NOT NULL,
                pregunta_id TEXT NOT NULL,
                citation_id TEXT NOT NULL,
                cita_texto TEXT NOT NULL,
                claim_asociado TEXT,
                estado TEXT NOT NULL CHECK (estado IN ('CORRECTA','PARCIAL','INCORRECTA','NO_ASOCIABLE')),
                justificacion TEXT,
                evaluador TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(generacion_experimento_id, pregunta_id, citation_id),
                FOREIGN KEY (generacion_experimento_id) REFERENCES generacion_experimentos(generacion_experimento_id),
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id)
            )
            """
        )
        # Versionado humano v3.1 (Parte 3): groundtruth_version en detalle y generación
        for _tbl in ("evaluacion_completitud_detalle", "evaluacion_faithfulness_detalle", "evaluacion_citation_correctness_detalle", "evaluacion_generacion"):
            try:
                _cols = _columnas_existentes(conn, _tbl)
                if "groundtruth_version" not in _cols:
                    conn.execute(f"ALTER TABLE {_tbl} ADD COLUMN groundtruth_version TEXT")
            except Exception:
                pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_piloto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_id TEXT,
                pregunta_id TEXT,
                timestamp TEXT NOT NULL,
                funcional INTEGER,
                recuperacion INTEGER,
                explicabilidad INTEGER,
                usabilidad INTEGER,
                gobernanza INTEGER,
                preparacion INTEGER,
                observacion TEXT,
                FOREIGN KEY (pregunta_id) REFERENCES banco_preguntas(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluacion_automatica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo TEXT NOT NULL,
                fecha_calculo TEXT NOT NULL,
                total_interacciones INTEGER,
                pct_m02 REAL,
                pct_m03 REAL,
                pct_m04 REAL,
                pct_m05 REAL,
                pct_m06 REAL,
                pct_con_fuentes REAL,
                tiempo_promedio REAL,
                tiempo_p95 REAL,
                funcional_auto REAL,
                recuperacion_auto REAL,
                explicabilidad_auto REAL,
                usabilidad_auto REAL,
                gobernanza_auto REAL,
                preparacion_auto REAL
            )
            """
        )
        # Migración no destructiva: añadir resumen si falta
        cols_auto = _columnas_existentes(conn, "evaluacion_automatica")
        if "puntaje_global" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN puntaje_global REAL")
        if "nivel" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN nivel TEXT")
        if "dimension_critica_minima" not in cols_auto:
            conn.execute("ALTER TABLE evaluacion_automatica ADD COLUMN dimension_critica_minima REAL")
    print("Base de datos de registro inicializada.")


# -----------------------------------------------------------------------------
# Operaciones
# -----------------------------------------------------------------------------
def registrar_interaccion(
    pregunta: str,
    respuesta: str,
    fuentes,
    tiempo_respuesta: float,
    umbral: float,
    tipo_mensaje: str,
    sesion_id: str = "",
    error: str = "",
    # Fase 5 — campos técnicos opcionales (retrocompatibles, default NULL)
    pregunta_normalizada: str | None = None,
    latency_total_ms: float | None = None,
    embedding_latency_ms: float | None = None,
    retrieval_latency_ms: float | None = None,
    llm_latency_ms: float | None = None,
    top_k_raw: int | None = None,
    top_k_final: int | None = None,
    threshold_used: float | None = None,
    num_valid_chunks: int | None = None,
    retrieved_chunk_ids=None,
    retrieved_document_ids=None,
    retrieved_articles=None,
    retrieved_distances=None,
    sources=None,
    citation_validation: str | None = None,
    citation_repairs: int | None = None,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
    corpus_version: str | None = None,
    ranking_method: str | None = None,
    ranking_version: str | None = None,
    http_status: int | None = None,
    failure_reason: str | None = None,
    validation_reason: str | None = None,
    error_type: str | None = None,
):
    """Inserta un registro de interacción ya anonimizado (sección 3.2, Fase 5).

    Mantiene compatibilidad con llamadas antiguas (solo 8 args posicionales).
    Los campos nuevos quedan NULL para filas históricas.
    """
    pregunta_anon = anonimizar(pregunta)
    respuesta_anon = anonimizar(respuesta)
    fuentes_txt = ", ".join(fuentes) if fuentes else ""

    # Normalización y latencia total por compatibilidad
    if pregunta_normalizada is None:
        pregunta_normalizada = pregunta_anon
    else:
        pregunta_normalizada = anonimizar(pregunta_normalizada)
    if latency_total_ms is None and tiempo_respuesta is not None:
        try:
            latency_total_ms = float(tiempo_respuesta) * 1000.0
        except Exception:
            latency_total_ms = None
    if threshold_used is None:
        threshold_used = umbral

    def _to_json(val):
        if val is None:
            return None
        try:
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return None

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO interacciones
                (timestamp, pregunta, respuesta, fuentes,
                 tiempo_respuesta, umbral_usado, tipo_mensaje,
                 sesion_id, error,
                 pregunta_normalizada, latency_total_ms,
                 embedding_latency_ms, retrieval_latency_ms, llm_latency_ms,
                 top_k_raw, top_k_final, threshold_used, num_valid_chunks,
                 retrieved_chunk_ids, retrieved_document_ids,
                 retrieved_articles, retrieved_distances, sources,
                 citation_validation, citation_repairs,
                 embedding_model, llm_model, prompt_version, corpus_version,
                 ranking_method, ranking_version, http_status,
                 failure_reason, validation_reason, error_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(),
                pregunta_anon,
                respuesta_anon,
                fuentes_txt,
                tiempo_respuesta,
                umbral,
                tipo_mensaje,
                sesion_id or "",
                error or "",
                pregunta_normalizada,
                latency_total_ms,
                embedding_latency_ms,
                retrieval_latency_ms,
                llm_latency_ms,
                top_k_raw,
                top_k_final,
                threshold_used,
                num_valid_chunks,
                _to_json(retrieved_chunk_ids),
                _to_json(retrieved_document_ids),
                _to_json(retrieved_articles),
                _to_json(retrieved_distances),
                _to_json(sources),
                citation_validation,
                citation_repairs,
                embedding_model,
                llm_model,
                prompt_version,
                corpus_version,
                ranking_method,
                ranking_version,
                http_status,
                failure_reason,
                validation_reason,
                error_type,
            ),
        )


def contar_preguntas_sesion(sesion_id: str) -> int:
    """Cuenta interacciones registradas para una sesión (T07 modo piloto)."""
    if not sesion_id:
        return 0
    with _conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM interacciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return cur.fetchone()[0]


def eliminar_por_sesion(sesion_id: str) -> int:
    """Borra físicamente las filas de una sesión (uso administrativo).

    El endpoint público usa `anonimizar_por_sesion` para preservar
    la data agregada (tipo_mensaje, tiempo, error) útil para
    evaluación (OE6) sin retener contenido personal.
    """
    if not sesion_id:
        return 0
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM interacciones WHERE sesion_id = ?",
            (sesion_id,),
        )
        return cur.rowcount


def anonimizar_por_sesion(sesion_id: str) -> int:
    """Sección 3.4 OE4 — derecho al olvido vía seudonimización.

    Cumple el derecho de supresión de la Ley 29733 eliminando el
    único nexo entre la fila y el usuario (`sesion_id`); preserva
    el contenido (pregunta, respuesta, fuentes) para evaluación y
    entrenamiento de madurez, ya que esos campos YA pasan por
    `anonimizar()` al insertarse (DNI/email/tel/cod_est →
    `[DNI]`/`[EMAIL]`/`[TEL]`/`[COD_EST]`).

    - `sesion_id`        → 'anonimizado'   (corte del nexo personal)
    - `error`            → ''              (limpia stack traces)
    - `anonimizado_en`   → timestamp       (auditoría)
    - `pregunta`, `respuesta`, `fuentes` → SE PRESERVAN
    - `tipo_mensaje`, `tiempo_respuesta`, `umbral_usado`, `timestamp` → SE PRESERVAN

    Retorna el número de filas seudonimizadas. Es idempotente.
    """
    if not sesion_id:
        return 0
    placeholder_sesion = "anonimizado"
    with _conn() as conn:
        cur = conn.execute(
            """
            UPDATE interacciones
               SET sesion_id      = ?,
                   error          = '',
                   anonimizado_en = ?
             WHERE sesion_id = ?
               AND anonimizado_en IS NULL
            """,
            (
                placeholder_sesion,
                datetime.datetime.now().isoformat(),
                sesion_id,
            ),
        )
        return cur.rowcount
