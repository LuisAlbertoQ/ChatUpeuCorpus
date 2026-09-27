# -*- coding: utf-8 -*-
"""
validators_evaluacion.py — Definiciones correctas para métricas determinísticas Parte 3.

source_validity: cada fuente mostrada debe pertenecer al conjunto determinístico de fuentes
  construidas desde los chunks finales (entro_top4=1) del experimento. Comparación por chunk_id
  o por (documento, articulo) normalizados. Retorna (valid_sources, shown_sources, validity).

citation_match: verifica citas inline parseadas [(DOC, Art)] contra fuentes finales.
  - documento normalizado (NFKD, lower, strip .pdf)
  - artículo normalizado cuando la cita lo incluye
  - Q09/Q11 permiten nivel documental si no existe artículo ground truth
  Retorna valid/invalid/not_applicable.
"""
import re
import unicodedata

def _norm_doc(doc: str) -> str:
    if not doc: return ""
    t = unicodedata.normalize("NFKD", doc).lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    if t.endswith(".pdf"): t = t[:-4]
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _norm_art(art: str) -> str:
    if not art: return ""
    t0 = art.replace("º","").replace("°","").replace("ª","")
    t = unicodedata.normalize("NFKD", t0).lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    m = re.search(r"(?:art[íi]culo|cap[íi]tulo|secci[óo]n|t[íi]tulo)?\s*(\d+(?:[.-][\w]+)?)", t)
    if m: return m.group(1).lower()
    m2 = re.search(r"(\d+(?:[.-]\d+)?)", t)
    return m2.group(1).lower() if m2 else re.sub(r"\s+", " ", re.sub(r"[^\w\s]"," ", t)).strip()

def source_validity_deterministico(fuentes_mostradas: list[str], fuentes_esperadas: list[dict]) -> dict:
    """
    fuentes_esperadas: lista de dicts con keys chunk_id/documento/articulo (construido desde chunks finales)
    fuentes_mostradas: lista de strings "Documento · Artículo · ..." (como sale en API)
    Retorna dict con valid_sources, shown_sources, validity.
    Una fuente inventada aunque tenga "·" será detectada como invalid.
    """
    shown = len(fuentes_mostradas)
    if shown == 0:
        return {"valid_sources": 0, "shown_sources": 0, "validity": "invalid"}
    # Construir set esperado por doc|art y por chunk_id
    esperado_doc_art = {f"{_norm_doc(f.get('documento',''))}|{_norm_art(f.get('articulo',''))}" for f in fuentes_esperadas}
    esperado_doc = {_norm_doc(f.get('documento','')) for f in fuentes_esperadas}
    esperado_chunk = {f.get('chunk_id') for f in fuentes_esperadas if f.get('chunk_id')}
    valid = 0
    for fm in fuentes_mostradas:
        # Parsear fuente mostrada: "Documento · Articulo · ..."
        partes = [p.strip() for p in fm.split("·")]
        doc_m = partes[0] if len(partes)>0 else ""
        art_m = partes[1] if len(partes)>1 else ""
        # Si fuente contiene chunk_id explícito, verificar; si no, verificar doc|art
        key = f"{_norm_doc(doc_m)}|{_norm_art(art_m)}"
        key_doc = _norm_doc(doc_m)
        # Considerar válido si doc|art exacto está en esperado, o al menos doc está
        # Para doc-level (Q09/Q11), art vacío es válido si doc coincide
        if key in esperado_doc_art or key_doc in esperado_doc:
            # Si art vacío y doc coincide, es válido doc-level
            if not _norm_art(art_m) and key_doc in esperado_doc:
                valid += 1
            elif key in esperado_doc_art:
                valid += 1
            elif key_doc in esperado_doc and not any(_norm_art(f.get('articulo','')) for f in fuentes_esperadas if _norm_doc(f.get('documento',''))==key_doc):
                # esperado es doc-level (sin artículo), entonces doc solo es suficiente
                valid += 1
    validity = "valid" if valid == shown else "invalid"
    return {"valid_sources": valid, "shown_sources": shown, "validity": validity}

def source_provenance_validity(fuentes_mostradas: list[str], fuentes_esperadas: list[dict]) -> dict:
    """
    Compara chunk_id si está disponible en la fuente mostrada; si no, no penaliza.
    Solo si la fuente mostrada expone chunk_id (no es el caso UI actual doc·art), verifica chunk_id ∈ Top4.
    """
    shown=len(fuentes_mostradas)
    if shown==0:
        return {"valid_sources":0,"shown_sources":0,"validity":"invalid"}
    esperado_chunk={f.get("chunk_id") for f in fuentes_esperadas if f.get("chunk_id")}
    # Si ninguna fuente mostrada contiene chunk_id, provenance no aplica → valid
    has_chunk_in_shown=any("chunk" in fm.lower() or "_" in fm for fm in fuentes_mostradas)  # heurística
    if not has_chunk_in_shown or not esperado_chunk:
        # No expone chunk_id → provenance N/A, considerar valid
        return {"valid_sources":shown,"shown_sources":shown,"validity":"valid","note":"chunk_id no visible, provenance N/A"}
    valid=0
    for fm in fuentes_mostradas:
        # intentar extraer chunk_id de la fuente mostrada (si lo tuviera)
        for cid in esperado_chunk:
            if cid in fm:
                valid+=1
                break
    validity="valid" if valid==shown else "invalid"
    return {"valid_sources":valid,"shown_sources":shown,"validity":validity}

# Citation parsing
_RE_CITA = re.compile(r"[\(\[]\s*([^\)\]]+?)\s*[\)\]]")  # captura dentro de () o []
_RE_DOC_ART = re.compile(r"([A-Za-zÁÉÍÓÚÑáéíóúñ\s\.\-]+?)\s*,?\s*(?:Art[íi]culo\s*([\dº°\-\.\w]+))?", re.IGNORECASE)

def parse_citas(texto: str) -> list[dict]:
    """Extrae 3 tipos: A doc+art, B doc-only, C art-only (Artículo 69°)."""
    citas=[]
    for m in _RE_CITA.finditer(texto):
        inner=m.group(1).strip()
        # Tipo A: Doc, Artículo
        m2 = re.search(r"(.+?)\s*,\s*Art[íi]culo\s*([\dº°\-\.\w]+)", inner, re.IGNORECASE)
        if m2:
            citas.append({"documento": m2.group(1).strip(), "articulo": m2.group(2).strip(), "raw": inner, "tipo": "A"})
            continue
        # Tipo C: solo Artículo (sin doc)
        m3 = re.search(r"^\s*Art[íi]culo\s*([\dº°\-\.\w]+)\s*$", inner, re.IGNORECASE)
        if m3:
            citas.append({"documento": "", "articulo": m3.group(1).strip(), "raw": inner, "tipo": "C"})
            continue
        # Tipo B: solo documento
        if any(k in inner.lower() for k in ["estatuto","reglamento","tupa","politica"]):
            # Evitar que "Artículo 69°" ya capturado como C se duplique
            citas.append({"documento": inner.strip(), "articulo": "", "raw": inner, "tipo": "B"})
    # También buscar "Según el/la [Documento]" sin paréntesis
    for m in re.finditer(r"Según el(?:la)?\s+([A-ZÁÉÍÓÚ][^,\n\(\)\[\]]+?)(?:,|\s+Art|$)", texto):
        doc=m.group(1).strip()
        if not any(c["documento"].lower()==doc.lower() for c in citas):
            citas.append({"documento": doc, "articulo": "", "raw": m.group(0), "tipo": "B"})
    # Buscar art-only fuera de paréntesis: "Artículo 69°" suelto
    for m in re.finditer(r"(?<!\w)Art[íi]culo\s+([\dº°\-\.\w]+)", texto):
        # Si ya existe cita C con mismo artículo, no duplicar
        art=m.group(1)
        if not any(c.get("tipo")=="C" and _norm_art(c["articulo"])==_norm_art(art) for c in citas):
            # Verificar que no es parte de una cita A ya capturada
            if not any(art in c["raw"] for c in citas):
                citas.append({"documento": "", "articulo": art.strip(), "raw": m.group(0), "tipo": "C"})
    return citas

def citation_match_deterministico(respuesta: str, fuentes_esperadas: list[dict]) -> str:
    """
    Tipos:
      A doc+art -> valid si doc|art en fuentes
      B doc-only -> valid si doc en fuentes
      C art-only -> valid si art aparece en exactamente 1 fuente, ambiguous si >1, invalid si 0
    No usa ground truth. Retorna valid/invalid/ambiguous/not_applicable.
    """
    if not respuesta:
        return "invalid"
    citas=parse_citas(respuesta)
    if not citas:
        has_encuadre="Según el" in respuesta or "Según la" in respuesta
        return "invalid" if has_encuadre else "not_applicable"
    esperado_doc_art = {f"{_norm_doc(f.get('documento',''))}|{_norm_art(f.get('articulo',''))}" for f in fuentes_esperadas}
    esperado_doc = {_norm_doc(f.get('documento','')) for f in fuentes_esperadas}
    # Para art-only: construir mapa articulo -> count de fuentes con ese art
    art_counts={}
    for f in fuentes_esperadas:
        a=_norm_art(f.get('articulo',''))
        if a:
            art_counts[a]=art_counts.get(a,0)+1
    has_ambiguous=False
    for c in citas:
        doc_n=_norm_doc(c["documento"])
        art_n=_norm_art(c["articulo"])
        tipo=c.get("tipo","")
        if tipo=="A":
            key=f"{doc_n}|{art_n}"
            if key in esperado_doc_art:
                return "valid"
            if doc_n in esperado_doc and not any(_norm_art(f.get('articulo','')) for f in fuentes_esperadas if _norm_doc(f.get('documento',''))==doc_n):
                return "valid"
        elif tipo=="B":
            if doc_n and doc_n in esperado_doc:
                return "valid"
        elif tipo=="C":
            if not art_n:
                continue
            cnt=art_counts.get(art_n,0)
            if cnt==1:
                return "valid"
            elif cnt>1:
                has_ambiguous=True
            # cnt==0 -> invalid, seguir
        else:
            # fallback
            if doc_n and not art_n and doc_n in esperado_doc:
                return "valid"
            if doc_n and art_n and f"{doc_n}|{art_n}" in esperado_doc_art:
                return "valid"
    if has_ambiguous:
        return "ambiguous"
    return "invalid"

def citation_match_detallado(respuesta: str, fuentes_esperadas: list[dict]) -> dict:
    citas=parse_citas(respuesta)
    if not citas:
        has_encuadre="Según el" in respuesta or "Según la" in respuesta
        estado="invalid" if has_encuadre else "not_applicable"
        return {"citas_detectadas":0,"citas_validas":0,"citas_invalidas":0,"citas_ambiguous":0,"ratio":None,"estado":estado,"citas":citas}
    esperado_doc_art = {f"{_norm_doc(f.get('documento',''))}|{_norm_art(f.get('articulo',''))}" for f in fuentes_esperadas}
    esperado_doc = {_norm_doc(f.get('documento','')) for f in fuentes_esperadas}
    art_counts={}
    for f in fuentes_esperadas:
        a=_norm_art(f.get('articulo',''))
        if a:
            art_counts[a]=art_counts.get(a,0)+1
    valid=invalid=ambiguous=0
    for c in citas:
        doc_n=_norm_doc(c["documento"]); art_n=_norm_art(c["articulo"]); tipo=c.get("tipo","")
        estado_cita="invalid"
        if tipo=="A":
            if f"{doc_n}|{art_n}" in esperado_doc_art: estado_cita="valid"
            elif doc_n in esperado_doc and not any(_norm_art(f.get('articulo','')) for f in fuentes_esperadas if _norm_doc(f.get('documento',''))==doc_n): estado_cita="valid"
        elif tipo=="B":
            if doc_n in esperado_doc: estado_cita="valid"
        elif tipo=="C":
            cnt=art_counts.get(art_n,0)
            if cnt==1: estado_cita="valid"
            elif cnt>1: estado_cita="ambiguous"
            else: estado_cita="invalid"
        if estado_cita=="valid": valid+=1
        elif estado_cita=="ambiguous": ambiguous+=1
        else: invalid+=1
    total=len(citas)
    ratio=valid/total if total else None
    if valid>0: estado="valid"
    elif ambiguous>0: estado="ambiguous"
    elif total>0: estado="invalid"
    else: estado="not_applicable"
    return {"citas_detectadas":total,"citas_validas":valid,"citas_invalidas":invalid,"citas_ambiguous":ambiguous,"ratio":ratio,"estado":estado,"citas":citas}
