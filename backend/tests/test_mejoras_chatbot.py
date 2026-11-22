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


ON = {"RAG_CONTEXTO_ARTICULO": "1"}


class TestMejora3Articulo:
    def test_expande_partes_vecinas_contiguas(self, pipeline):
        textos, metas = _partes("g1", ["P1 " * 100, "P2 " * 100, "P3 " * 100, "P4 " * 100])
        _, cap = pipeline([textos[1]], [metas[1]], [0.10], grupos={"g1": (textos, metas)}, env=ON)
        f = cap["frags"][0]
        assert f["partes"] == [1, 2, 3, 4]
        assert all(f"P{i}" in f["text"] for i in range(1, 5)) and "[…]" not in f["text"]
        assert f["chunk_id"] == "g1_2"  # la fuente sigue siendo la parte recuperada

    def test_respeta_tope_por_articulo(self, pipeline):
        textos, metas = _partes("g1", ["A" * 900, "B" * 900, "C" * 900, "D" * 900, "E" * 900])
        _, cap = pipeline([textos[2]], [metas[2]], [0.10], grupos={"g1": (textos, metas)},
                          env={**ON, "RAG_ARTICULO_MAX_CHARS": 2000})
        f = cap["frags"][0]
        assert f["partes"] in ([2, 3], [3, 4])
        assert f["text"].startswith("[…]") and f["text"].endswith("[…]")
        assert len(f["text"].replace("[…]", "").strip()) <= 2000

    def test_respeta_presupuesto_total(self, pipeline):
        textos, metas = _partes("g1", ["A" * 900, "B" * 900, "C" * 900])
        _, cap = pipeline([textos[0]], [metas[0]], [0.10], grupos={"g1": (textos, metas)},
                          env={**ON, "RAG_CONTEXT_MAX_CHARS": 1900})
        assert cap["frags"][0]["partes"] == [1, 2]

    def test_partes_del_mismo_articulo_ocupan_un_solo_lugar(self, pipeline):
        textos, metas = _partes("g1", ["uno " * 50, "dos " * 50])
        docs = [textos[0], textos[1], "otro documento"]
        ms = [metas[0], metas[1], _meta("DOC B", cid="b1")]
        _, cap = pipeline(docs, ms, [0.10, 0.11, 0.12], grupos={"g1": (textos, metas)},
                          env={**ON, "RAG_TOP_K_FINAL": 2})
        assert [f["chunk_id"] for f in cap["frags"]] == ["g1_1", "b1"]
        assert cap["frags"][0]["partes"] == [1, 2]

    def test_sin_metadatos_de_grupo_no_expande(self, pipeline):
        _, cap = pipeline(["texto suelto"], [_meta("DOC A")], [0.10], env=ON)
        assert "partes" not in cap["frags"][0] and cap["frags"][0]["text"] == "texto suelto"

    def test_apagada_por_defecto(self, pipeline, monkeypatch):
        monkeypatch.delenv("RAG_CONTEXTO_ARTICULO", raising=False)  # independiente del entorno del contenedor
        textos, metas = _partes("g1", ["uno " * 50, "dos " * 50])
        _, cap = pipeline(textos, metas, [0.10, 0.11], grupos={"g1": (textos, metas)})
        assert [f["chunk_id"] for f in cap["frags"]] == ["g1_1", "g1_2"]

    def test_desactivable_por_entorno(self, pipeline):
        textos, metas = _partes("g1", ["uno " * 50, "dos " * 50])
        _, cap = pipeline(textos, metas, [0.10, 0.11], grupos={"g1": (textos, metas)},
                          env={"RAG_CONTEXTO_ARTICULO": "0"})
        assert [f["chunk_id"] for f in cap["frags"]] == ["g1_1", "g1_2"]
        assert all("partes" not in f for f in cap["frags"])

    def test_conserva_partes_recuperadas_no_contiguas(self, pipeline):
        """Caso Q15 (TUPA): dos partes recuperadas del mismo grupo, lejos entre sí;
        ninguna debe perderse aunque no quepan las vecinas."""
        textos, metas = _partes("g1", [f"FILA{i} " * 60 for i in range(1, 11)])  # 10 partes de ~420 chars
        _, cap = pipeline([textos[1], textos[7], "otro"], [metas[1], metas[7], _meta("DOC B", cid="b1")],
                          [0.10, 0.11, 0.12], grupos={"g1": (textos, metas)},
                          env={**ON, "RAG_ARTICULO_MAX_CHARS": 1000, "RAG_TOP_K_FINAL": 2})
        f = cap["frags"][0]
        assert "FILA2" in f["text"] and "FILA8" in f["text"]
        assert 2 in f["partes"] and 8 in f["partes"]
        assert "[…]" in f["text"]  # hueco entre tramos
        assert [x["chunk_id"] for x in cap["frags"]] == ["g1_2", "b1"]


# ---------------------------------------------------------------------------
# Mejora 4 — abstención disfrazada (oración meta con paréntesis)
# ---------------------------------------------------------------------------
Q17_REAL = ("El corpus no contiene información sobre servicios específicos que la Universidad "
            "Peruana Unión (UPeU) ofrece a los egresados.")


class TestMejora4AbstencionDisfrazada:
    def test_caso_real_q17_se_convierte_en_m04(self, pipeline):
        res, _ = pipeline(["texto"], [_meta("DOC A")], [0.10], llm=Q17_REAL)
        assert res["tipo_mensaje"] == "M04"

    @pytest.mark.parametrize("meta", [
        "(El corpus no contiene información sobre X.)",
        "No hay información específica sobre X en los fragmentos proporcionados.",
        "Los documentos no incluyen información sobre la UPeU (Lima) ni sus sedes",
    ])
    def test_variantes_solas_son_abstencion(self, pipeline, meta):
        res, _ = pipeline(["texto"], [_meta("DOC A")], [0.10], llm=meta)
        assert res["tipo_mensaje"] == "M04"

    def test_respuesta_real_con_nota_final_sigue_siendo_m02(self, pipeline):
        resp = ("- Requisito uno del trámite (DOC A, Artículo 1°)\n- Requisito dos (DOC A, Artículo 1°)\n"
                "El corpus no contiene información sobre los plazos (UPeU).")
        res, _ = pipeline(["texto"], [_meta("DOC A")], [0.10], llm=resp)
        assert res["tipo_mensaje"] == "M02"
        assert "Requisito dos" in res["respuesta"] and "no contiene" not in res["respuesta"]

    def test_no_borra_vinetas_si_la_meta_va_primero(self, pipeline):
        resp = ("No hay información sobre el costo\n- Paso uno (DOC A, Artículo 1°)\n"
                "- Paso dos con detalle suficiente (DOC A, Artículo 1°)")
        res, _ = pipeline(["texto"], [_meta("DOC A")], [0.10], llm=resp)
        assert res["tipo_mensaje"] == "M02" and "Paso dos" in res["respuesta"]
