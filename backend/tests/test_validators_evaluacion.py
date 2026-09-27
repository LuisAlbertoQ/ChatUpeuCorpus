# -*- coding: utf-8 -*-
import validators_evaluacion as ve

def _fuentes_esperadas():
    return [
        {"chunk_id":"est_a_1", "documento":"ESTATUTO 2024. 04-09-2024", "articulo":"Artículo 19°"},
        {"chunk_id":"est_a_2", "documento":"REGLAMENTO DE ESTUDIOS V5_2025", "articulo":"Artículo 70°"},
        {"chunk_id":"pol_a_1", "documento":"Politica Institucional de trabajo digno y protección de la persona v.1", "articulo":""},
    ]

def test_source_validity_all_valid():
    esperadas=_fuentes_esperadas()
    mostradas=["ESTATUTO 2024. 04-09-2024 · Artículo 19° · v1", "REGLAMENTO DE ESTUDIOS V5_2025 · Artículo 70° · v5"]
    r=ve.source_validity_deterministico(mostradas, esperadas)
    assert r["validity"]=="valid" and r["valid_sources"]==2

def test_source_validity_invented_with_dot():
    esperadas=_fuentes_esperadas()
    mostradas=["DOCUMENTO INVENTADO · Artículo 99° · fake"]  # tiene · pero no existe
    r=ve.source_validity_deterministico(mostradas, esperadas)
    assert r["validity"]=="invalid" and r["valid_sources"]==0

def test_source_validity_doc_level_valid():
    esperadas=[{"documento":"Politica Institucional de trabajo digno y protección de la persona v.1", "articulo":""}]
    mostradas=["Politica Institucional de trabajo digno y protección de la persona v.1 ·  · v1"]
    r=ve.source_validity_deterministico(mostradas, esperadas)
    assert r["validity"]=="valid"

def test_citation_match_doc_art_correct():
    esperadas=[{"documento":"ESTATUTO 2024. 04-09-2024","articulo":"Artículo 19°"}]
    resp="Según el ESTATUTO 2024. 04-09-2024, Artículo 19° (ESTATUTO 2024. 04-09-2024, Artículo 19°) la autoridad..."
    assert ve.citation_match_deterministico(resp, esperadas)=="valid"

def test_citation_match_doc_correct_art_incorrect():
    esperadas=[{"documento":"ESTATUTO 2024. 04-09-2024","articulo":"Artículo 19°"}]
    resp="Según el ESTATUTO 2024. 04-09-2024, Artículo 99° (ESTATUTO 2024. 04-09-2024, Artículo 99°) ..."
    assert ve.citation_match_deterministico(resp, esperadas)=="invalid"

def test_citation_match_doc_inventado():
    esperadas=[{"documento":"ESTATUTO 2024. 04-09-2024","articulo":"Artículo 19°"}]
    resp="(DOCUMENTO INVENTADO, Artículo 1°) texto"
    assert ve.citation_match_deterministico(resp, esperadas)=="invalid"

def test_citation_match_doc_level_valid():
    esperadas=[{"documento":"Politica Institucional de trabajo digno y protección de la persona v.1","articulo":""}]
    resp="(Politica Institucional de trabajo digno y protección de la persona v.1) establece..."
    assert ve.citation_match_deterministico(resp, esperadas)=="valid"

def test_citation_match_fake_textual():
    esperadas=[{"documento":"ESTATUTO 2024. 04-09-2024","articulo":"Artículo 19°"}]
    resp="El estatuto dice que las autoridades son elegidas..."  # menciona estatuto sin cita formal
    # Nuestro parser exige paréntesis o Según, así que será not_applicable -> no valid
    assert ve.citation_match_deterministico(resp, esperadas) in ("invalid","not_applicable")
