# -*- coding: utf-8 -*-
"""Tests de las mejoras del chatbot sobre corpus V3 + bge-m3 (2026-11-21).

Mejora 1: contexto con fragmentos completos (sin recorte 700 chars) + num_ctx/num_predict/semilla.
Mejora 3: contexto por artículo (partes vecinas + una fuente por artículo).
"""
import importlib
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _restaurar_modulos():
    yield
    importlib.reload(sys.modules["config"])
    if "rag_pipeline" in sys.modules:
        importlib.reload(sys.modules["rag_pipeline"])


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """Devuelve run(docs, metas, dists, llm=..., env=...) → (resultado, capturado)."""
    import logger

    monkeypatch.setattr(logger, "DB_PATH", str(tmp_path / "t.db"))
    logger.inicializar_bd()

    def run(docs, metas, dists, llm="Respuesta (DOC A, Artículo 1°)", env=None, pregunta="pregunta de prueba",
            grupos=None):
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, str(v))
        import config
        importlib.reload(config)
        import rag_pipeline as rp
        importlib.reload(rp)

        emb = MagicMock()
        emb.tolist.return_value = [0.1] * 8
        rp.model = MagicMock()
        rp.model.encode.return_value = [emb]
        rp.collection = MagicMock()
        rp.collection.query.return_value = {"documents": [docs], "metadatas": [metas], "distances": [dists]}
        if grupos:  # partes de cada artículo para la expansión (mejora 3)
            rp.collection.get.side_effect = lambda where=None, include=None, **kw: {
                "documents": grupos[where["grupo_articulo_id"]][0],
                "metadatas": grupos[where["grupo_articulo_id"]][1]}
        for f in ("_pregunta_es_ambigua", "_es_etica_sensible", "_es_multi_intencion"):
            monkeypatch.setattr(rp, f, lambda x: False)
        monkeypatch.setattr(rp, "_es_fuera_dominio_por_keywords", lambda x: None)

        cap = {"prompts": []}
        orig = rp.construir_contexto

        def spy(frags):
            cap["frags"] = frags
            return orig(frags)

        monkeypatch.setattr(rp, "construir_contexto", spy)
        respuestas = llm if isinstance(llm, list) else [llm]

        def fake_llm(prompt):
            cap["prompts"].append(prompt)
            return respuestas[min(len(cap["prompts"]) - 1, len(respuestas) - 1)]

        monkeypatch.setattr(rp, "_invocar_llm_con_timeout", fake_llm)
        return rp.generar_respuesta(pregunta, sesion_id="t-mejoras"), cap

    return run


def _meta(doc, art="Artículo 1°", cid=None, **kw):
    return {"documento": doc, "articulo": art, "categoria_tematica": "B", "chunk_id": cid or f"{doc}_{art}", **kw}


# ---------------------------------------------------------------------------
# Mejora 1 — contexto completo
# ---------------------------------------------------------------------------
class TestMejora1ContextoCompleto:
    def test_fragmento_largo_llega_completo_sin_marcador(self, pipeline):
        largo = "Inicio del artículo. " + ("Texto del medio que antes se perdía. " * 60) + "Final."
        assert len(largo) > 700
        res, cap = pipeline([largo], [_meta("DOC A")], [0.10])
        assert res["tipo_mensaje"] == "M02"
        assert cap["frags"][0]["text"] == largo
        assert "[…]" not in cap["prompts"][0]
        assert "Texto del medio que antes se perdía" in cap["prompts"][0]

    def test_presupuesto_total_salta_chunk_que_no_cabe(self, pipeline):
        docs = ["a" * 600, "b" * 600, "c" * 200]
        metas = [_meta("DOC A", cid="a"), _meta("DOC B", cid="b"), _meta("DOC C", cid="c")]
        _, cap = pipeline(docs, metas, [0.10, 0.11, 0.12], env={"RAG_CONTEXT_MAX_CHARS": 900})
        assert [f["chunk_id"] for f in cap["frags"]] == ["a", "c"]

    def test_primer_fragmento_mayor_que_presupuesto_se_recorta_en_oracion(self, pipeline):
        texto = "Primera oración completa. " * 40  # ~1040 chars
        _, cap = pipeline([texto], [_meta("DOC A")], [0.10], env={"RAG_CONTEXT_MAX_CHARS": 500})
        t = cap["frags"][0]["text"]
        assert len(t) <= 500 and t.endswith(".")

    def test_opciones_ollama_desde_config(self, monkeypatch):
        import json
        import config
        importlib.reload(config)
        import rag_pipeline as rp
        importlib.reload(rp)
        enviado = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"response": "ok"}).encode()

        def fake_urlopen(req, timeout=None):
            enviado.update(json.loads(req.data.decode()))
            return Resp()

        monkeypatch.setattr(rp._urlreq, "urlopen", fake_urlopen)
        assert rp._invocar_llm_con_timeout("hola") == "ok"
        assert enviado["options"]["num_ctx"] == config.OLLAMA_NUM_CTX == 8192
        assert enviado["options"]["num_predict"] == config.OLLAMA_NUM_PREDICT == 1024
        assert enviado["options"]["seed"] == config.OLLAMA_SEED == 42

    def test_recorte_legacy_solo_para_ablacion_y_sin_expansion(self, pipeline):
        largo = "y" * 1500
        _, cap = pipeline([largo], [_meta("DOC A", grupo_articulo_id="g", parte_num=1, total_partes=3)],
                          [0.10], env={"RAG_RECORTE_LEGACY_700": "1"})
        assert "partes" not in cap["frags"][0]

    def test_recorte_legacy_solo_para_ablacion(self, pipeline):
        largo = "x" * 1500
        _, cap = pipeline([largo], [_meta("DOC A")], [0.10], env={"RAG_RECORTE_LEGACY_700": "1"})
        assert "[…]" in cap["frags"][0]["text"] and len(cap["frags"][0]["text"]) < 720


# ---------------------------------------------------------------------------
# Mejora 3 — contexto por artículo (expansión + una fuente por artículo)
# ---------------------------------------------------------------------------
def _partes(grupo, textos, doc="DOC A", art="Artículo 5°"):
    metas = [_meta(doc, art, cid=f"{grupo}_{i}", grupo_articulo_id=grupo, parte_num=i, total_partes=len(textos))
             for i in range(1, len(textos) + 1)]
    return textos, metas


class TestMejora3Articulo:
    def test_expande_partes_vecinas_contiguas(self, pipeline):
        textos, metas = _partes("g1", ["P1 " * 100, "P2 " * 100, "P3 " * 100, "P4 " * 100])
        _, cap = pipeline([textos[1]], [metas[1]], [0.10], grupos={"g1": (textos, metas)})
        f = cap["frags"][0]
        assert f["partes"] == [1, 2, 3, 4]
        assert all(f"P{i}" in f["text"] for i in range(1, 5)) and "[…]" not in f["text"]
        assert f["chunk_id"] == "g1_2"  # la fuente sigue siendo la parte recuperada

    def test_respeta_tope_por_articulo(self, pipeline):
        textos, metas = _partes("g1", ["A" * 900, "B" * 900, "C" * 900, "D" * 900, "E" * 900])
        _, cap = pipeline([textos[2]], [metas[2]], [0.10], grupos={"g1": (textos, metas)},
                          env={"RAG_ARTICULO_MAX_CHARS": 2000})
        f = cap["frags"][0]
        assert f["partes"] in ([2, 3], [3, 4])
        assert f["text"].startswith("[…]") and f["text"].endswith("[…]")
        assert len(f["text"].replace("[…]", "").strip()) <= 2000

    def test_respeta_presupuesto_total(self, pipeline):
        textos, metas = _partes("g1", ["A" * 900, "B" * 900, "C" * 900])
        _, cap = pipeline([textos[0]], [metas[0]], [0.10], grupos={"g1": (textos, metas)},
                          env={"RAG_CONTEXT_MAX_CHARS": 1900})
        assert cap["frags"][0]["partes"] == [1, 2]

    def test_partes_del_mismo_articulo_ocupan_un_solo_lugar(self, pipeline):
        textos, metas = _partes("g1", ["uno " * 50, "dos " * 50])
        docs = [textos[0], textos[1], "otro documento"]
        ms = [metas[0], metas[1], _meta("DOC B", cid="b1")]
        _, cap = pipeline(docs, ms, [0.10, 0.11, 0.12], grupos={"g1": (textos, metas)},
                          env={"RAG_TOP_K_FINAL": 2})
        assert [f["chunk_id"] for f in cap["frags"]] == ["g1_1", "b1"]
        assert cap["frags"][0]["partes"] == [1, 2]

    def test_sin_metadatos_de_grupo_no_expande(self, pipeline):
        _, cap = pipeline(["texto suelto"], [_meta("DOC A")], [0.10])
        assert "partes" not in cap["frags"][0] and cap["frags"][0]["text"] == "texto suelto"

    def test_desactivable_por_entorno(self, pipeline):
        textos, metas = _partes("g1", ["uno " * 50, "dos " * 50])
        _, cap = pipeline(textos, metas, [0.10, 0.11], grupos={"g1": (textos, metas)},
                          env={"RAG_CONTEXTO_ARTICULO": "0"})
        assert [f["chunk_id"] for f in cap["frags"]] == ["g1_1", "g1_2"]
        assert all("partes" not in f for f in cap["frags"])
