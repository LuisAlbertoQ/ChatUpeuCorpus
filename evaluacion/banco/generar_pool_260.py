#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el pool de 260 preguntas del gold set (Revisión 3, §3).

Entradas:
  - cuotas_pool_260.json           reparto por documento (Opción 1: espejo del corpus)
  - draft/*.json                   preguntas borrador (una por objeto)
  - registro_interacciones.db      semillas curadas: 17 dominio (v3.1) + 6 fuera de dominio
  - ChromaDB corpus_upeu_v2        texto real para extraer evidencia y puntos candidatos

Salidas:
  - pool_260_verificacion.json     Capa 0: borrador completo (doc/art/puntos) para revisión del investigador
  - pool_260_preliminar.jsonl      Capa 1: pool ciego para anotadores (solo id, texto, bloque, tema)
  - pool_260_preliminar.csv        misma Capa 1 en CSV (Excel)
  - pool_260_resumen.md            distribución, cobertura por documento y advertencias

Nada de lo generado es ground truth: todo borrador sale marcado CANDIDATO_NO_VALIDADO.

Uso:
  docker compose exec backend python /data/evaluacion/banco/generar_pool_260.py --check
  docker compose exec backend python /data/evaluacion/banco/generar_pool_260.py --guardar
"""
import csv
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DRAFT_DIR = BASE / "draft"
DB = "/data/registro_interacciones.db"
VECTOR_STORE = "/data/vector_store"
COLECCION = "corpus_upeu_v2"

BLOQUE_DOMINIO = "dominio"
BLOQUE_OOD = "ood"
BLOQUE_AMBIGUA = "ambigua"

TIPOS_VALIDOS = {"DIRECTA", "REQUISITOS", "PROCEDIMIENTO", "SIN_COBERTURA", "AMBIGUA"}
MAX_PUNTOS = 5
SEMILLA_MEZCLA = 20260927


# --------------------------------------------------------------------------- utilidades
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def clave_articulo(etiqueta: str):
    """Normaliza 'Artículo 42°', 'ARTICULO  42', 'Capítulo X' -> ('art', '42') / ('cap', 'X')."""
    t = norm(etiqueta).lower()
    t = t.replace("í", "i").replace("ó", "o").replace("º", "").replace("°", "")
    if t.startswith("cap"):
        m = re.search(r"([ivxlcdm]+|\d+)", t)
        return ("cap", m.group(1)) if m else None
    m = re.search(r"(\d+)", t)
    return ("art", m.group(1)) if m else None


def limpiar_texto(t: str) -> str:
    t = re.sub(r"-{2,}\s*Pág\s*\d+[^-]*?-{2,}", " ", t)      # marcadores de página OCR
    t = re.sub(r"\[TABLA[^\]]*\]", " ", t)
    t = re.sub(r"\.{3,}", ". ", t)                            # índices con puntos suspensivos
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def recortar(t: str, n: int) -> str:
    if len(t) <= n:
        return t
    corte = t[:n]
    if " " in corte:
        corte = corte[: corte.rfind(" ")]
    return corte.rstrip(" ,;:.") + "…"


def descripcion_desde(seg: str) -> str:
    seg = norm(seg)
    seg = re.sub(r"^\d{1,3}\.\d{1,2}(\.\d{1,2})?\.?\s*", "", seg)
    m = re.split(r"(?<=[.;:])\s+", seg, maxsplit=1)
    d = m[0] if m else seg
    d = recortar(d, 150)
    return d[:1].upper() + d[1:] if d else d


def extraer_puntos(texto: str, pregunta: str = ""):
    """Devuelve [(descripcion, evidencia)] a partir del texto real del artículo.

    En documentos con articulado se respeta el orden del artículo. En documentos
    sin articulado (`pregunta` no vacía) se eligen las oraciones con mayor
    solapamiento léxico con la pregunta, para no quedarse con la portada.
    """
    t = limpiar_texto(texto)
    if len(t) < 40:
        return []
    if pregunta:
        return extraer_puntos_documento(t, pregunta)
    t = re.sub(r"^art[ií]culo\s*\d+[°º]?\s*[.:]?\s*", "", t, flags=re.I)
    partes = re.split(r"(?=\b\d{1,3}\.\d{1,2}(?:\.\d{1,2})?\s*[.)]?\s+[A-ZÁÉÍÓÚÑ¿])", t)
    segs = [p for p in partes if len(norm(p)) >= 40]
    if len(segs) < 2:
        segs = [s for s in re.split(r"(?<=[.;])\s+", t) if len(norm(s)) >= 40]
    puntos = []
    for s in segs:
        s = norm(s)
        if not s:
            continue
        puntos.append((descripcion_desde(s), recortar(s, 320)))
        if len(puntos) >= MAX_PUNTOS:
            break
    return puntos


STOPWORDS = {
    "para", "como", "cuando", "donde", "quien", "quienes", "cual", "cuales",
    "cuanto", "cuanta", "cuantos", "cuantas", "sobre", "entre", "desde", "hasta",
    "debe", "deben", "puede", "pueden", "tiene", "tienen", "hace", "hacen",
    "este", "esta", "estos", "estas", "aquel", "según", "segun", "mediante",
    "upeu", "universidad", "peruana", "union", "unión", "reglamento", "dice",
    "establece", "señala", "senala", "cuál", "qué", "que", "los", "las", "del",
    "por", "con", "sin", "una", "uno", "sus", "mas", "más", "muy", "hay",
}


def _claves(texto: str):
    t = norm(texto).lower()
    t = re.sub(r"[^a-záéíóúñü0-9 ]+", " ", t)
    return {w for w in t.split() if len(w) > 3 and w not in STOPWORDS}


def extraer_puntos_documento(texto: str, pregunta: str):
    """Candidatos por solapamiento léxico para documentos sin articulado."""
    from collections import Counter

    t = limpiar_texto(texto)
    crudo = [u.strip() for u in re.split(r"(?<=[.;:])\s+|\n+", t) if len(norm(u)) >= 90]
    # descartar encabezados repetidos, líneas de índice y títulos en mayúsculas
    freq = Counter(norm(u)[:90] for u in crudo)
    unidades = []
    for u in crudo:
        if freq[norm(u)[:90]] > 2:
            continue
        if re.search(r"\.{4,}", u):
            continue
        letras = [c for c in u if c.isalpha()]
        if letras and sum(c.isupper() for c in letras) / len(letras) > 0.6:
            continue
        unidades.append(u)
    if not unidades:
        unidades = crudo
    if not unidades:
        return []

    clave_preg = _claves(pregunta)
    puntuadas = []
    for i, u in enumerate(unidades):
        cl = _claves(u)
        sol = len(clave_preg & cl)
        if sol:
            puntuadas.append((sol, sol / (len(cl) ** 0.5), i, u))
    # exigir al menos 2 términos en común; si no alcanza, bajar a 1; si no, primeras unidades
    for minimo in (2, 1):
        elegibles = [x for x in puntuadas if x[0] >= minimo]
        if len(elegibles) >= 2:
            puntuadas = elegibles
            break
    if not puntuadas:
        puntuadas = [(0, 0.0, i, u) for i, u in enumerate(unidades[:MAX_PUNTOS])]
    elegidas = sorted(sorted(puntuadas, key=lambda x: -x[1])[:MAX_PUNTOS], key=lambda x: x[2])
    salida, huellas = [], set()
    for _, _, _, u in elegidas:
        h = norm(u)[:140].lower()
        if h in huellas:
            continue
        huellas.add(h)
        salida.append((descripcion_desde(u), recortar(u, 320)))
    return salida


# --------------------------------------------------------------------------- fuentes
def cargar_cuotas():
    data = json.loads((BASE / "cuotas_pool_260.json").read_text(encoding="utf-8"))
    docs = data["docs"]
    total = sum(d["objetivo"] for d in docs.values())
    if total != data["_total_dominio"]:
        raise SystemExit(f"ERROR cuotas: suma {total} != {data['_total_dominio']}")
    return docs


def cargar_semillas_dominio():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    preguntas = [dict(r) for r in con.execute(
        "SELECT * FROM groundtruth_v31_preguntas ORDER BY pregunta_id")]
    puntos = [dict(r) for r in con.execute(
        "SELECT * FROM groundtruth_v31_puntos ORDER BY punto_id")]
    con.close()
    por_pregunta = {}
    for p in puntos:
        por_pregunta.setdefault(p["pregunta_id"], []).append(p)
    return preguntas, por_pregunta


def cargar_semillas_ood():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    filas = [dict(r) for r in con.execute("SELECT * FROM banco_no_answer ORDER BY id")]
    con.close()
    return filas


def cargar_temas_semilla():
    f = BASE / "preguntas_comparacion.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {d["id"]: d.get("tema", "") for d in data}


def nfc(s: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFC", s or "")


def resolver_doc(nombre: str, exactos: dict):
    """Devuelve el nombre exacto tal como está en ChromaDB (NFD/NFC, con o sin .pdf)."""
    if not nombre:
        return None
    for cand in (nombre, nombre + ".pdf", nombre[:-4] if nombre.lower().endswith(".pdf") else nombre):
        if cand in exactos:
            return exactos[cand]
    n = nfc(nombre)
    if n in exactos:
        return exactos[n]
    if n + ".pdf" in exactos:
        return exactos[n + ".pdf"]
    if n.lower().endswith(".pdf") and n[:-4] in exactos:
        return exactos[n[:-4]]
    return None


def indice_corpus():
    """documento -> {'categoria':..., 'articulos': {clave: texto}}"""
    import chromadb

    client = chromadb.PersistentClient(path=VECTOR_STORE)
    col = client.get_collection(COLECCION)
    total = col.count()
    res = col.get(include=["metadatas", "documents"], limit=max(total, 1))
    idx = {}
    buffers = {}
    completos = {}
    for meta, doc in zip(res["metadatas"], res["documents"]):
        nombre = meta.get("documento")
        entrada = idx.setdefault(nombre, {"categoria": meta.get("categoria_tematica"),
                                          "articulos": {}})
        completos.setdefault(nombre, []).append(norm(doc))
        etiqueta = meta.get("articulo") or meta.get("capitulo")
        if not etiqueta:
            continue
        k = clave_articulo(etiqueta)
        if not k:
            continue
        buffers.setdefault((nombre, k), []).append(norm(doc))
    for (nombre, k), trozos in buffers.items():
        idx[nombre]["articulos"][k] = " ".join(trozos)
    for nombre, trozos in completos.items():
        idx[nombre]["texto"] = " ".join(trozos)
    # mapa NFC -> nombre exacto de ChromaDB
    idx["__nfc__"] = {nfc(n): n for n in completos}
    return idx


def cargar_drafts():
    if not DRAFT_DIR.exists():
        return []
    items = []
    for f in sorted(DRAFT_DIR.glob("draft_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for it in data:
            it["_archivo"] = f.name
            items.append(it)
    return items


# --------------------------------------------------------------------------- construcción
def construir():
    cuotas = cargar_cuotas()
    sem_dom, puntos_dom = cargar_semillas_dominio()
    sem_ood = cargar_semillas_ood()
    temas = cargar_temas_semilla()
    drafts = cargar_drafts()
    idx = indice_corpus()

    doc_por_clave = {}
    clave_por_doc = {}
    exactos = idx["__nfc__"]
    for k, v in cuotas.items():
        exacto = resolver_doc(v["documento"], exactos)
        if not exacto:
            raise SystemExit(f"ERROR cuota {k}: documento no existe en corpus -> {v['documento']}")
        doc_por_clave[k] = exacto
        clave_por_doc[nfc(exacto)] = k
        clave_por_doc[exacto] = k

    # --- semillas de dominio -> clave de cuota
    semillas_por_clave = {}
    clave_de_semilla = {}
    for p in sem_dom:
        doc = resolver_doc(p["documento_esperado"], exactos)
        clave = clave_por_doc.get(doc) if doc else None
        if not clave:
            raise SystemExit(f"ERROR semilla {p['pregunta_id']}: documento sin cuota -> {p['documento_esperado']}")
        semillas_por_clave.setdefault(clave, []).append(p)
        clave_de_semilla[p["pregunta_id"]] = clave

    # --- validar reparto
    problemas = []
    borradores_por_clave = {}
    for it in drafts:
        if it.get("bloque") in (BLOQUE_OOD, BLOQUE_AMBIGUA):
            continue
        c = it.get("clave")
        if c not in cuotas:
            problemas.append(f"clave inexistente en cuotas: {c}")
            continue
        if it.get("tipo") not in TIPOS_VALIDOS:
            problemas.append(f"{c}: tipo invalido {it.get('tipo')}")
        borradores_por_clave.setdefault(c, []).append(it)

    for clave, cfg in cuotas.items():
        n_sem = len(semillas_por_clave.get(clave, []))
        n_bor = len(borradores_por_clave.get(clave, []))
        if n_sem + n_bor != cfg["objetivo"]:
            problemas.append(f"{clave}: objetivo {cfg['objetivo']} != semillas {n_sem} + borradores {n_bor}")

    # --- artículos existen y extracción de puntos
    faltantes = []
    for it in drafts:
        if it.get("bloque") in (BLOQUE_OOD, BLOQUE_AMBIGUA):
            continue
        clave = it["clave"]
        doc = doc_por_clave[clave]
        k = clave_articulo(it.get("art", ""))
        arts = idx.get(doc, {}).get("articulos", {})
        if it.get("art") and k not in arts:
            faltantes.append(f"{clave} {doc} -> {it.get('art')}")
        it["_texto"] = arts.get(k, "") if it.get("art") else idx.get(doc, {}).get("texto", "")
        pregunta = "" if it.get("art") else it["texto"]
        it["_puntos"] = extraer_puntos(it["_texto"], pregunta) if it["_texto"] else []

    for f in faltantes:
        problemas.append(f"articulo no encontrado en corpus: {f}")

    sin_puntos = [f"{it['clave']} {it.get('art')} ({len(it['_texto'])} chars)"
                  for it in drafts
                  if it.get("bloque") not in (BLOQUE_OOD, BLOQUE_AMBIGUA) and not it["_puntos"]]
    for s in sin_puntos:
        problemas.append(f"sin puntos candidatos: {s}")

    if problemas:
        print("VALIDACION FALLIDA:")
        for p in problemas:
            print("  -", p)
        return None

    # --- ensamblado del bloque de dominio (orden categoria + documento)
    def orden(it):
        clave = it["clave"]
        doc = doc_por_clave[clave]
        k = clave_articulo(it.get("art", "") or "")
        num = int(k[1]) if k and k[0] == "art" else 0
        return (cuotas[clave]["categoria"], doc, num)

    dominio = []
    for p in sem_dom:
        clave = clave_de_semilla[p["pregunta_id"]]
        doc = doc_por_clave[clave]
        puntos = []
        for i, pt in enumerate(puntos_dom.get(p["pregunta_id"], []), start=1):
            puntos.append({
                "punto_id": f"{p['pregunta_id']}_P{i:02d}",
                "descripcion": pt["descripcion"],
                "documento": pt["documento"],
                "articulo": pt["articulo"],
                "evidencia": pt["evidencia"],
                "obligatorio": pt["obligatorio"],
            })
        dominio.append({
            "clave": clave,
            "texto": p["pregunta"],
            "tipo": "DIRECTA",
            "tema": temas.get(p["pregunta_id"], cuotas[clave]["tema"]),
            "documento_esperado": doc,
            "articulo_esperado": p["articulo_esperado"] or "",
            "puntos": puntos,
            "origen": f"SEMILLA_CURADA:{p['pregunta_id']}",
            "estado": "SEMILLA_CURADA",
        })

    for it in sorted([d for d in drafts if d.get("clave") in cuotas], key=orden):
        clave = it["clave"]
        doc = doc_por_clave[clave]
        puntos = [{
            "punto_id": None,
            "descripcion": d,
            "documento": doc,
            "articulo": it["art"],
            "evidencia": e,
            "obligatorio": 1,
        } for d, e in it["_puntos"]]
        dominio.append({
            "clave": clave,
            "texto": norm(it["texto"]),
            "tipo": it["tipo"],
            "tema": it.get("tema") or cuotas[clave]["tema"],
            "documento_esperado": doc,
            "articulo_esperado": it["art"],
            "puntos": puntos,
            "origen": f"BORRADOR_CORPUS:{it['_archivo']}",
            "estado": "CANDIDATO_NO_VALIDADO",
        })

    # --- fuera de dominio
    ood = []
    for f in sem_ood:
        ood.append({
            "texto": f["pregunta"],
            "tipo": "SIN_COBERTURA",
            "tema": "Fuera de dominio",
            "documento_esperado": "",
            "articulo_esperado": "",
            "motivo_no_cobertura": f["motivo_no_cobertura"],
            "puntos": [],
            "origen": f"SEMILLA_CURADA:{f['id']}",
            "estado": "SEMILLA_CURADA",
        })
    draft_ood = [d for d in drafts if d.get("bloque") == BLOQUE_OOD]
    for d in draft_ood:
        ood.append({
            "texto": norm(d["texto"]),
            "tipo": "SIN_COBERTURA",
            "tema": d.get("tema") or "Fuera de dominio",
            "documento_esperado": "",
            "articulo_esperado": "",
            "motivo_no_cobertura": d["motivo"],
            "puntos": [],
            "origen": f"BORRADOR:{d['_archivo']}",
            "estado": "CANDIDATO_NO_VALIDADO",
        })

    # --- ambiguas
    ambiguas = []
    for d in [x for x in drafts if x.get("bloque") == BLOQUE_AMBIGUA]:
        ambiguas.append({
            "texto": norm(d["texto"]),
            "tipo": "AMBIGUA",
            "tema": d.get("tema") or "Ambigua",
            "documento_esperado": "",
            "articulo_esperado": "",
            "motivo_no_cobertura": d["motivo"],
            "puntos": [],
            "origen": f"BORRADOR:{d['_archivo']}",
            "estado": "CANDIDATO_NO_VALIDADO",
        })

    examenes = [("dominio", dominio), (BLOQUE_OOD, ood), (BLOQUE_AMBIGUA, ambiguas)]
    if len(dominio) != 200 or len(ood) != 40 or len(ambiguas) != 20:
        print(f"VALIDACION FALLIDA: dominio {len(dominio)}/200, ood {len(ood)}/40, ambiguas {len(ambiguas)}/20")
        return None

    # --- duplicados exactos en todo el pool
    vistos = {}
    for bloque, lista in examenes:
        for it in lista:
            t = re.sub(r"[¿?¡!.,;:]+", "", norm(it["texto"]).lower()).strip()
            if t in vistos:
                print(f"VALIDACION FALLIDA: pregunta duplicada -> {it['texto']!r} "
                      f"({vistos[t]} y {bloque})")
                return None
            vistos[t] = bloque

    # --- asignación de IDs: primero se mezcla (semilla fija) para que el orden
    #     del pool ciego no revele a qué bloque pertenece cada pregunta.
    for bloque, lista in examenes:
        for it in lista:
            it["bloque"] = bloque
    plano = [it for _, lista in examenes for it in lista]
    random.Random(SEMILLA_MEZCLA).shuffle(plano)

    salida = []
    for n, item in enumerate(plano, start=1):
        pid = f"GOLD_{n:03d}"
        bloque = item["bloque"]
        for i, pt in enumerate(item["puntos"], start=1):
            pt["punto_id"] = f"{pid}_P{i:02d}"
        item["pregunta_id"] = pid
        item["categoria"] = cuotas[item["clave"]]["categoria"] if bloque == BLOQUE_DOMINIO else ""
        item["cobertura"] = ("ANSWERABLE" if bloque == BLOQUE_DOMINIO
                             else "NO_ANSWER" if bloque == BLOQUE_OOD else "AMBIGUA")
        item.pop("clave", None)
        salida.append(item)
    return salida, cuotas, idx


# --------------------------------------------------------------------------- salidas
def escribir(pool, cuotas, idx):
    verif = BASE / "pool_260_verificacion.json"
    verif.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")

    blind = [{"pregunta_id": it["pregunta_id"], "texto": it["texto"]} for it in pool]
    with open(BASE / "pool_260_preliminar.jsonl", "w", encoding="utf-8") as f:
        for it in blind:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    with open(BASE / "pool_260_preliminar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pregunta_id", "texto"])
        for it in blind:
            w.writerow([it["pregunta_id"], it["texto"]])

    # resumen
    from collections import Counter
    cat = Counter(it["categoria"] for it in pool if it["bloque"] == BLOQUE_DOMINIO)
    tipo = Counter(it["tipo"] for it in pool if it["bloque"] == BLOQUE_DOMINIO)
    estado = Counter(it["estado"] for it in pool)
    puntos = sum(len(it["puntos"]) for it in pool)
    lineas = [
        "# Pool 260 — reporte de generación",
        "",
        f"- preguntas: **{len(pool)}** (200 dominio + 40 fuera de dominio + 20 ambiguas)",
        f"- puntos candidatos: **{puntos}**",
        f"- estados: {dict(estado)}",
        "",
        "## Dominio por categoría documental",
        "",
        "| cat | preguntas | documentos |",
        "|---|---|---|",
    ]
    for c in sorted(cat):
        ndocs = sum(1 for v in cuotas.values() if v["categoria"] == c)
        lineas.append(f"| {c} | {cat[c]} | {ndocs} |")
    lineas += ["", "## Dominio por tipo", "", "| tipo | preguntas |", "|---|---|"]
    for t, v in tipo.most_common():
        lineas.append(f"| {t} | {v} |")
    lineas += ["", "## Cobertura por documento", "",
               "| clave | documento | cat | objetivo | real |", "|---|---|---|---|---|"]
    for clave in sorted(cuotas):
        cfg = cuotas[clave]
        n_real = sum(1 for it in pool if it["bloque"] == BLOQUE_DOMINIO
                     and nfc(it.get("documento_esperado", "")) == nfc(cfg["documento"]))
        flag = "" if n_real == cfg["objetivo"] else " **REVISAR**"
        lineas.append(f"| {clave} | {cfg['documento']} | {cfg['categoria']} | {cfg['objetivo']} | {n_real}{flag} |")
    lineas += [
        "",
        "## Ceguera del pool",
        "",
        f"- Los IDs `GOLD_NNN` se asignaron tras mezclar los 260 ítems con semilla fija "
        f"`{SEMILLA_MEZCLA}`; el orden **no** agrupa dominio, fuera de dominio ni ambiguas.",
        "- `pool_260_preliminar.jsonl/.csv` contiene solo `pregunta_id` y `texto`:",
        "  el anotador no ve bloque, tema, documento, artículo, tipo ni puntos candidatos.",
        "- `pool_260_verificacion.json` (este equipo, no se entrega a los anotadores) conserva",
        "  bloque, documento candidato, artículo y puntos candidatos para la revisión del investigador.",
        "",
        "## Advertencias metodológicas",
        "",
        "1. Los puntos de las preguntas `CANDIDATO_NO_VALIDADO` se extraen automáticamente del texto del",
        "   artículo (incisos numerados o primeras oraciones). **No son ground truth**: son hipótesis a",
        "   verificar por los anotadores leyendo el documento.",
        "2. La pregunta se redactó a partir del corpus, por lo que el documento candidato puede coincidir",
        "   con el esperado. Es un sesgo conocido de la generación; se declara en el informe y se mitiga",
        "   con doble anotación ciega (el anotador no ve el candidato).",
        "3. Las 17 preguntas `SEMILLA_CURADA` y las 6 fuera de dominio ya están curadas y no requieren",
        "   re-anotación; cuentan dentro de las 260.",
        "4. Documentos sin articulado (políticas, resoluciones, TUPA, guías) tienen cuota reducida porque",
        "   su contenido no soporta 4 preguntas independientes sin forzar preguntas artificiales. En esos",
        "   casos los puntos candidatos se eligen por solapamiento léxico con la pregunta, no por orden de",
        "   lectura: son más débiles y requieren revisión manual obligatoria.",
        "5. Las 20 preguntas ambiguas se redactaron deliberadamente sin entidad resoluble; su valor está en",
        "   evaluar si el sistema pide aclaración o alucina una respuesta.",
        "6. El `tipo` del borrador (DIRECTA/REQUISITOS/PROCEDIMIENTO) es solo una hipótesis de redacción:",
        "   el tipo definitivo lo asignan los anotadores y es el que se usa para el κ de tipo. La distribución",
        "   final puede diferir de la mostrada arriba.",
        "",
    ]
    (BASE / "pool_260_resumen.md").write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas[:12]))
    print(f"\nGuardado: {verif.name}, pool_260_preliminar.jsonl/.csv, pool_260_resumen.md")


def main():
    r = construir()
    if not r:
        return 1
    pool, cuotas, idx = r
    if "--guardar" in sys.argv:
        escribir(pool, cuotas, idx)
    else:
        from collections import Counter
        print("OK validación:", len(pool), "preguntas")
        print("  dominio:", sum(1 for x in pool if x["bloque"] == BLOQUE_DOMINIO))
        print("  ood:", sum(1 for x in pool if x["bloque"] == BLOQUE_OOD))
        print("  ambiguas:", sum(1 for x in pool if x["bloque"] == BLOQUE_AMBIGUA))
        print("  puntos:", sum(len(x["puntos"]) for x in pool))
        print("  categorias:", dict(Counter(x["categoria"] for x in pool if x["categoria"])))
        print("  usa --guardar para escribir los archivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
