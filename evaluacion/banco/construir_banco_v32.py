#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
construir_banco_v32.py — Banco técnico v3.2 (30 preguntas + 6 negativas) sobre el corpus V3.

Por qué existe (ver auditoria_banco_17q_2026-11-21.md):
  * Q17: la v3.1 ya había corregido el documento (Reglamento de seguimiento de egresados) pero la
    corrección nunca llegó a banco_preguntas ni al JSON que leen los scripts.
  * 8 de 17 categorías venían de la taxonomía previa a la V2.
  * La v3.1 acepta varios artículos por pregunta; los scripts solo comparaban contra uno.
  * Q05 y Q16 tenían una respuesta esperada que no responde la pregunta.
La v3.1 sigue congelada en la base de datos: este script NO la modifica. Escribe un archivo nuevo.

Fuentes:
  * Q01–Q04, Q06–Q15, Q17: documento, artículos y puntos de groundtruth_v31_* (curado, sin cambios
    de contenido); categoría y tema recalculados desde los metadatos del corpus.
  * Q05, Q16: respuesta esperada corregida contra el texto real del corpus (pendiente de revisión humana).
  * Q18–Q30: preguntas nuevas redactadas a partir del texto literal del artículo (pendiente de revisión
    humana). Q28 reutiliza los 3 puntos curados del antiguo Q16, con la pregunta bien formulada.
  * Negativas N01–N06: banco_no_answer (v31_no_answer).

Página, chunk_ids y número de partes se completan desde el corpus. Al final se valida todo
(documento, artículo, categoría, tema y evidencia literal) y solo se escribe si no hay errores.

Uso (host):  python evaluacion/banco/construir_banco_v32.py
Salidas:     evaluacion/banco/banco_v32.json · banco_v32.csv · validacion_banco_v32.md
"""
import collections
import csv
import datetime
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "evaluacion" / "banco"
CATS = {"A": "Gobierno y estatuto institucional", "B": "Académico y estudios", "C": "Investigación",
        "D": "Bienestar estudiantil", "E": "Laboral, docencia y políticas"}
TIPOS = {"DIRECTA", "REQUISITOS", "PROCEDIMIENTO"}
PENDIENTE = "PROPUESTA_V32_PENDIENTE_REVISION_HUMANA"

# -----------------------------------------------------------------------------
# Correcciones y preguntas nuevas. Cada punto: (descripción, documento, artículo, evidencia literal)
# -----------------------------------------------------------------------------
INV = "REGLAMENTO INVESTIGACION UPeU 2025 V8"
DEF = "REGLAMENTO DEFENSORIA UNIVERSITARIA 2025 v4"
CORREGIDAS = {
    "Q05": {
        "tipo": "REQUISITOS",
        "motivo": "v3.1 esperaba Art. 15–16 (coordinación del CIIEP en la investigación formativa), que no "
                  "trata requisitos de un proyecto de tesis. Art. 17–18 definen el perfil de proyecto para la "
                  "tesis y su estructura obligatoria.",
        "puntos": [
            ("El perfil de proyecto de investigación se escribe entre el III y VI semestre, con apoyo de un "
             "docente, en equipos de máximo tres estudiantes", INV, "Artículo 17°",
             "Entre el III y VI semestre, con el apoyo de un docente, cada equipo de investigación de "
             "estudiantes, máximo de tres (3), escribe un perfil de proyecto de investigación"),
            ("El perfil se ejecuta para la tesis en formato artículo que conduce al título profesional",
             INV, "Artículo 17°", "deberá ser ejecutado para la tesis en formato artículo que conduce a la "
             "obtención del título profesional"),
            ("Su estructura incluye título, planteamiento del problema y metodología", INV, "Artículo 18°",
             "18.1. Título 18.2. Planteamiento del problema 18.3. Metodología, según unidad académica y tema "
             "de investigación"),
            ("También incluye administración del proyecto, referencias bibliográficas y anexos", INV,
             "Artículo 18°", "18.4. Administración del proyecto 18.5. Referencias bibliográficas 18.6. Anexos"),
        ],
    },
    "Q16": {
        "tipo": "PROCEDIMIENTO",
        "motivo": "v3.1 esperaba el Art. 140° del Reglamento Interno de Trabajo (reclamo laboral de "
                  "trabajadores). Para un estudiante, la vía es la Defensoría Universitaria: Art. 15 (vías), "
                  "17 (contenido) y 22 (plazos). El contenido antiguo pasa a Q28 con la pregunta bien formulada.",
        "puntos": [
            ("La queja puede presentarse de forma presencial, por escrito en la oficina del campus o verbalmente",
             DEF, "Artículo 15°", "15.1. Presencial: 15.1.1. Escrita, en formato físico presentada en la "
             "oficina dispuesta en el campus 15.1.2. Verbal, sin formato o presentación de escrito alguno."),
            ("También de forma no presencial, por teléfono o por el correo electrónico de la Defensoría",
             DEF, "Artículo 15°", "15.2. No presencial: 15.2.1. Verbalmente a través de línea telefónica"),
            ("Debe contener los hechos que vulneran el derecho, la petición concreta y, si los hay, los medios "
             "probatorios", DEF, "Artículo 17°", "17.1. Los actos, hechos, situaciones, actuaciones o conductas "
             "materializadas que considere que violan su derecho fundamental individual. 17.2. La petición "
             "concreta, individualizada o específica."),
            ("La admisión toma hasta un día hábil y la resolución diez días hábiles, ampliables hasta treinta",
             DEF, "Artículo 22°", "Serán resueltas en un plazo de diez (10) días hábiles"),
        ],
    },
}
ADM, IDI, MOV, PAG = ("REGLAMENTO ADMISION 2025.v7", "REGLAMENTO IDIOMAS INGLES O NATIVO 2023v.3",
                      "REGLAMENTO MOVILIDAD ACADEMICA ESTUDIANTIL Y DOCENTEv1",
                      "Reglamento Pago Servicios Educativos o Académicos")
ETI, EXC, PRO, CEU = ("REGLAMENTO CODIGO ETICA INVESTIGACION 2021", "REGLAMENTO RECONOCIMIENTO EXCELENCIA ACADEMICA 2020",
                      "REGLAMENTO PRODAC 2022(R_SG)", "Reglamento Comite Electoral Universitario 2016 OK")
DUP, ACO, RIT = ("Reglamento de duplicado de diplomas", "Reglamento Prevención Acoso y Hostigamiento Sexual 2025",
                 "REGLAMENTO INTERNO DE TRABAJO Final 2020")
TUPA, JEF = "TUPA V6 2023 UPeU", "Reglamento de Jefes de prácticas apoyo y profesional"
NUEVAS = [
    ("Q18", "¿Qué modalidades de admisión ofrece la UPeU?", "DIRECTA", [
        ("En el concurso ordinario el postulante rinde la evaluación de aptitudes y actitudes (entrevista) y el "
         "examen de conocimiento", ADM, "Artículo 28°", "están obligados a pasar por el proceso de evaluación de "
         "aptitudes y actitudes (entrevista) y el examen de conocimiento"),
        ("Modalidades ordinarias: examen general, examen preferencial (preingreso), centro preuniversitario, "
         "personas con discapacidad y deportista calificado", ADM, "Artículo 28°",
         "28.1.1. Examen General"),
        ("En el concurso extraordinario el postulante está exonerado del examen de conocimiento y solo pasa la "
         "evaluación de aptitudes y actitudes", ADM, "Artículo 28°", "Son aquellos postulantes que están "
         "exonerado del examen de conocimiento y deben pasar por una evaluación de aptitudes y actitudes"),
        ("Modalidades extraordinarias: primeros puestos, internacionales, convenios, tercio superior, traslado "
         "externo, grado y título, titulado de instituto, traslado interno y egresados de colegios de la UPeU",
         ADM, "Artículo 28°", "28.2.1. Primeros Puestos"),
    ]),
    ("Q19", "¿A quiénes se aplica el requisito de idioma inglés o lengua nativa en pregrado?", "DIRECTA", [
        ("Se aplica a todas las carreras profesionales, en modalidad presencial, semipresencial y a distancia",
         IDI, "Artículo 8°", "se aplica a todas las carreras profesionales, modalidad presencial, "
         "semipresencial y a distancia"),
        ("Alcanza a postulantes e ingresantes", IDI, "Artículo 8°", "8.1. Postulantes: En el proceso de admisión "
         "a los postulantes a una carrera profesional en cualquiera de las modalidades. 8.2. Ingresantes"),
        ("Alcanza a todo estudiante antes de su matrícula, según el nivel exigido al momento de su ingreso",
         IDI, "Artículo 8°", "a todo estudiante antes de su matrícula para iniciar o seguir estudios en una "
         "carrera profesional, según el nivel exigido al momento de su ingreso"),
        ("A los egresados solo por excepción, cuando a la fecha de egreso es requisito para el bachiller",
         IDI, "Artículo 8°", "Egresados: En excepción, al culminar los estudios, solo cuando a la fecha de "
         "egreso es un requisito de obtención de grado académico de bachiller"),
    ]),
    ("Q20", "¿Qué requisitos debo cumplir para participar en la movilidad académica estudiantil?", "REQUISITOS", [
        ("Estar en el tercio superior, con matrícula regular y al menos 50 créditos aprobados", MOV, "Artículo 31°",
         "Estar ubicado en el tercio superior de evaluación. 31.1.2. Ser estudiante con matrícula regular en la "
         "UPeU, y haber aprobado como mínimo 50 créditos"),
        ("Acreditar el dominio del idioma que exija la institución receptora", MOV, "Artículo 31°",
         "Acreditar el dominio del idioma que corresponda, según el nivel requerido por la institución receptora"),
        ("No adeudar a la UPeU, no tener sanciones disciplinarias y participar por primera vez", MOV, "Artículo 31°",
         "No adeudar a la UPeU, por ningún concepto. 31.1.5. Participar por primera vez de un programa de "
         "movilidad estudiantil en la UPeU. 31.1.6. No tener o haber tenido sanciones disciplinarias."),
        ("Gozar de buena salud, contar con apoyo financiero acreditado y aprobar el curso de Identidad Educativa",
         MOV, "Artículo 31°", "Gozar de buena salud. 31.1.8. Contar con el apoyo financiero acreditado de sus "
         "progenitores o apoderado."),
    ]),
    ("Q21", "¿Qué pasa si no pago una cuota de la pensión en la fecha de vencimiento?", "DIRECTA", [
        ("La falta de pago total o parcial en la fecha de vencimiento genera mora automática", PAG, "Artículo 50",
         "La falta de pago total o parcial de la fracción o cuota en la fecha de su vencimiento determinada en el "
         "contrato de servicio educativo universitario de pregrado / posgrado genera la mora automática"),
        ("La UPeU puede no entregar ni certificar documentos académicos por ese incumplimiento", PAG, "Artículo 50",
         "La UPeU puede no entregar, certificar, acreditar, evidenciar los documentos académicos"),
    ]),
    ("Q22", "¿Qué principios éticos rigen la investigación en la UPeU?", "DIRECTA", [
        ("Autonomía: protege la dignidad, libertad y derechos de la persona", ETI, "Artículo 4°",
         "protege la dignidad, libertad y derechos de la persona"),
        ("Beneficencia y no maleficencia: prevenir el daño y minimizar riesgos", ETI, "Artículo 4°",
         "Beneficencia/ No maleficencia"),
        ("Justicia: los resultados benefician a la persona y la comunidad sin discriminación", ETI, "Artículo 4°",
         "sirve a la persona y a la comunidad sin discriminación alguna"),
    ]),
    ("Q23", "¿Qué requisitos generales hay para el reconocimiento a la excelencia académica?", "REQUISITOS", [
        ("Tener la calidad de estudiante sin limitación ni restricción vigente", EXC, "Artículo 15°",
         "Tener la calidad de estudiante sin limitación o restricción vigente alguna"),
        ("Representar la identidad de la formación integral de la educación cristiana adventista", EXC,
         "Artículo 15°", "Representar la identidad de la formación integral de la educación cristiana adventista"),
        ("No tener sanción disciplinaria vigente", EXC, "Artículo 15°", "No tener vigente sanción disciplinaria"),
    ]),
    ("Q24", "¿Qué requisitos debo cumplir para postular a la beca deportiva PRODAC?", "REQUISITOS", [
        ("Inscribirse en el sitio web de la UPeU y adjuntar todos los documentos solicitados", PRO, "Artículo 22°",
         "Inscribirse en el sitio web de la UPeU"),
        ("Haber concluido el ciclo anterior con carga regular y aprobado todo con promedio mínimo de 14", PRO,
         "Artículo 22°", "Haber aprobado todas las asignaturas matriculadas, alcanzando o superando el promedio "
         "ponderado mínimo de 14"),
        ("No tener sanciones ni deudas con la UPeU", PRO, "Artículo 22°", "No contar con ninguna sanción. 22.3.4 "
         "No tener deuda alguna con la UPeU"),
        ("Tener como máximo 25 años y participar en todas las etapas del proceso de selección", PRO, "Artículo 22°",
         "El postulante debe tener, como máximo, una edad igual o menor a 25 años"),
    ]),
    ("Q25", "¿Qué requisitos debe cumplir un estudiante para ser candidato a representante estudiantil?",
     "REQUISITOS", [
        ("Estar en los tres primeros puestos del tercio superior sin haber desaprobado asignaturas", CEU,
         "Artículo 23°", "Estar comprendido en los tres primeros puestos del tercio superior de notas"),
        ("Estar matriculado y cursando al menos el V semestre", CEU, "Artículo 23°",
         "Estar matriculado y estudiando como mínimo el V semestre académico de su carrera profesional"),
        ("No tener sanciones disciplinarias ni procesos por indisciplina", CEU, "Artículo 23°",
         "No haber sido sancionado, o tener vigente sanción disciplinaria"),
        ("No adeudar a la UPeU ni ser miembro del Comité Electoral Universitario", CEU, "Artículo 23°",
         "No adeudar a la UPeU por ningún concepto"),
    ]),
    ("Q26", "¿Qué documentos necesito para pedir el duplicado de mi diploma si lo perdí?", "REQUISITOS", [
        ("Solicitud dirigida al rector, cuatro fotografías tamaño pasaporte y copia simple del DNI", DUP,
         "Artículo 5°", "Solicitud dirigida al rector de la Universidad"),
        ("Recibo de pago de los derechos de duplicado y constancia de la denuncia policial", DUP, "Artículo 5°",
         "Constancia de la Denuncia Policial"),
        ("Constancia del Registro Nacional de Grados y Títulos y copia certificada de la resolución que otorga "
         "el grado o título", DUP, "Artículo 5°", "Constancia expedida por el Registro Nacional de Grados y "
         "Títulos"),
        ("Publicación del aviso de pérdida en un diario de mayor circulación", DUP, "Artículo 5°",
         "Publicación por única vez, en un diario de mayor circulación del lugar"),
    ]),
    ("Q27", "¿Cómo presento una denuncia por hostigamiento sexual en la UPeU?", "PROCEDIMIENTO", [
        ("La denuncia la puede presentar la persona hostigada, un tercero o iniciarse de oficio", ACO,
         "Artículo 22°", "La denuncia puede ser presentada por la persona hostigada, un tercero o interpuesta "
         "de oficio"),
        ("Puede ser verbal o escrita, presencial o electrónica, ante la Secretaría de Instrucción (SeIn)", ACO,
         "Artículo 22°", "de forma verbal o escrita, presencial o electrónica a la SeIn"),
        ("Debe narrar los hechos y adjuntar las pruebas disponibles e identificar al presunto hostigador", ACO,
         "Artículo 22°", "La denuncia contendrá una breve narración y listado de los hechos a investigar"),
        ("En un día hábil la SeIn pone a disposición de la víctima atención médica o psicológica", ACO,
         "Artículo 22°", "La SeIn, en un plazo no mayor a un (1) día hábil luego de recibida la denuncia, pone a "
         "disposición de la persona hostigada los canales de atención médica"),
    ]),
    ("Q28", "¿Cuál es el procedimiento para que un trabajador de la UPeU presente un reclamo laboral?",
     "PROCEDIMIENTO", "DESDE_V31:Q16"),
    ("Q29", "¿Qué requisitos y costo tiene el carné universitario al matricularse?", "REQUISITOS", [
        ("Estar matriculado en el semestre académico", TUPA, "", "CARNÉ UNIVERSITARIO | 1. Estar matriculado en "
         "el semestre académico"),
        ("Tomarse la foto digital de frente, con fondo blanco, ropa formal oscura y sin lentes ni alhajas", TUPA, "",
         "Tomarse la foto digital en el período determinado y según especificaciones y normativa vigente"),
        ("El derecho de trámite es S/. 20.00", TUPA, "", "Sin lentes, ni alhajas | S/. 20.00"),
    ]),
    ("Q30", "¿Qué requisitos se necesitan para ser jefe de prácticas en la UPeU?", "REQUISITOS", [
        ("Título profesional universitario de la especialidad o afín", JEF, "Artículo 10°",
         "Título profesional universitario de la formación profesional o especialidad"),
        ("Experiencia profesional no menor de un año y conocimientos básicos de TI", JEF, "Artículo 10°",
         "Experiencia profesional no menor de un (1) año"),
        ("Habilitación profesional o colegiatura cuando se requiera", JEF, "Artículo 10°",
         "Tener la habilitación profesional o colegiatura"),
        ("No tener antecedentes judiciales o penales ni sentencia por delito doloso", JEF, "Artículo 10°",
         "No tener antecedentes judiciales o penales"),
    ]),
]


# -----------------------------------------------------------------------------
def norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t[:-4] if t.endswith(".pdf") else t
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def num(a):
    m = re.search(r"\d+", a or "")
    return m.group() if m else ""


def cargar_corpus():
    v = sqlite3.connect(f"file:{RAIZ / 'vector_store' / 'chroma.sqlite3'}?mode=ro", uri=True)
    coleccion = v.execute("SELECT name FROM collections").fetchone()[0]
    por_doc = collections.defaultdict(list)
    for (eid,) in v.execute("SELECT id FROM embeddings"):
        m = {k: (s if s is not None else i) for k, s, i in
             v.execute("SELECT key, string_value, int_value FROM embedding_metadata WHERE id=?", (eid,))}
        por_doc[norm(m.get("documento"))].append(m)
    return coleccion, por_doc


def chunks_de(por_doc, documento, articulo):
    ch = por_doc.get(norm(documento), [])
    return [m for m in ch if not articulo or num(m.get("articulo")) == num(articulo)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    coleccion, por_doc = cargar_corpus()
    c = sqlite3.connect(f"file:{RAIZ / 'registro_interacciones.db'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    v31 = {r["pregunta_id"]: dict(r) for r in c.execute("SELECT * FROM groundtruth_v31_preguntas")}
    pts31 = collections.defaultdict(list)
    for r in c.execute("SELECT * FROM groundtruth_v31_puntos ORDER BY punto_id"):
        pts31[r["pregunta_id"]].append((r["descripcion"], r["documento"], r["articulo"] or "", r["evidencia"]))
    tipos_v31 = {r["id"]: r["tipo_pregunta"] for r in
                 c.execute("SELECT id, tipo_pregunta FROM banco_preguntas WHERE banco_version='v3_curado'")}
    negs = [dict(r) for r in c.execute("SELECT id, pregunta, motivo_no_cobertura FROM banco_no_answer "
                                       "WHERE banco_version='v31_no_answer' AND activa=1 ORDER BY id")]

    def armar(qid, pregunta, tipo, puntos, origen, estado, cambios):
        docs = list(dict.fromkeys(p[1] for p in puntos))
        arts = list(dict.fromkeys((p[1], p[2]) for p in puntos if p[2]))
        cat = collections.Counter(m.get("categoria_tematica") for d in docs for m in por_doc.get(norm(d), []))
        cat = cat.most_common(1)[0][0] if cat else None
        arts_info = []
        for d, a in arts:
            ch = chunks_de(por_doc, d, a)
            arts_info.append({"documento": d, "articulo": a,
                              "paginas": sorted({str(m.get("pagina")) for m in ch if m.get("pagina")}, key=lambda x: int(x) if x.isdigit() else 0),
                              "chunk_ids": sorted(m.get("chunk_id") for m in ch),
                              "total_partes": max((m.get("total_partes") or 1) for m in ch) if ch else 0})
        return {
            "id": qid, "pregunta": pregunta, "categoria": cat, "tema": CATS.get(cat), "tipo_pregunta": tipo,
            "cobertura_esperada": "ANSWERABLE", "documentos_esperados": docs, "articulos_esperados": arts_info,
            "puntos": [{"punto_id": f"{qid}_P{i:02d}", "descripcion": d, "documento": doc, "articulo": art,
                        "evidencia": ev} for i, (d, doc, art, ev) in enumerate(puntos, 1)],
            "origen": origen, "estado": estado, "cambios": cambios,
        }

    preguntas = []
    for qid in sorted(v31):
        g = v31[qid]
        if qid in CORREGIDAS:
            cfix = CORREGIDAS[qid]
            preguntas.append(armar(qid, g["pregunta"], cfix["tipo"], cfix["puntos"], "v3.1_corregida", PENDIENTE,
                                   cfix["motivo"]))
        else:
            cambios = "Categoría y tema recalculados desde los metadatos del corpus V3."
            if qid == "Q17":
                cambios = ("Se propaga la corrección de la v3.1 (Reglamento de seguimiento de egresados, Art. 12° y "
                           "18°) que no había llegado a banco_preguntas. " + cambios)
            preguntas.append(armar(qid, g["pregunta"], tipos_v31.get(qid) or "DIRECTA", pts31[qid], "v3.1",
                                   "CURADO_V31", cambios))
    for qid, pregunta, tipo, puntos in NUEVAS:
        if puntos == "DESDE_V31:Q16":
            preguntas.append(armar(qid, pregunta, tipo, pts31["Q16"], "nueva_v3.2 (puntos curados del Q16 v3.1)",
                                   PENDIENTE, "Reformulación del antiguo Q16: la respuesta esperada (reclamo laboral, "
                                   "Art. 140°) es correcta para un trabajador, no para un estudiante."))
        else:
            preguntas.append(armar(qid, pregunta, tipo, puntos, "nueva_v3.2", PENDIENTE,
                                   "Pregunta nueva redactada desde el texto literal del artículo."))

    # ------------------------------------------------------------------ validación
    errores, avisos, ev_estado = [], [], {}
    vistos = collections.Counter(norm(q["pregunta"]) for q in preguntas)
    for q in preguntas:
        qid = q["id"]
        if vistos[norm(q["pregunta"])] > 1:
            errores.append(f"{qid}: pregunta duplicada")
        if q["tipo_pregunta"] not in TIPOS:
            errores.append(f"{qid}: tipo_pregunta inválido {q['tipo_pregunta']}")
        for d in q["documentos_esperados"]:
            if norm(d) not in por_doc:
                errores.append(f"{qid}: documento '{d}' no existe en {coleccion}")
        for a in q["articulos_esperados"]:
            if not a["chunk_ids"]:
                errores.append(f"{qid}: {a['articulo']} no existe en '{a['documento']}'")
        cats_docs = {collections.Counter(m.get('categoria_tematica') for m in por_doc.get(norm(d), [])).most_common(1)[0][0]
                     for d in q["documentos_esperados"] if por_doc.get(norm(d))}
        if len(cats_docs) > 1:
            avisos.append(f"{qid}: documentos de categorías distintas {cats_docs}")
        if q["tema"] != CATS.get(q["categoria"]):
            errores.append(f"{qid}: tema no coincide con la categoría")
        if len(q["puntos"]) < 2:
            avisos.append(f"{qid}: solo {len(q['puntos'])} punto(s)")
        for p in q["puntos"]:
            # La evidencia puede citar otros artículos del mismo documento ("(Art38, …)"): se incluyen.
            citados = {p["articulo"]} | {f"Artículo {n}" for n in re.findall(r"(?i)art(?:[íi]culo)?\.?\s*(\d+)", p["evidencia"])}
            texto = norm(" ".join(m.get("chroma:document", "") for a in citados
                                  for m in chunks_de(por_doc, p["documento"], a)))
            ev = norm(p["evidencia"])
            if ev and ev in texto:
                ev_estado[p["punto_id"]] = "literal"
            else:
                e = {w for w in ev.split() if len(w) > 3}
                r = len(e & set(texto.split())) / len(e) if e else 0
                ev_estado[p["punto_id"]] = f"aproximada ({r:.0%})"
                if q["origen"].startswith("nueva") and not q["origen"].endswith("Q16 v3.1)"):
                    errores.append(f"{p['punto_id']}: evidencia de pregunta nueva no es literal ({r:.0%})")
                elif r < 0.6:
                    errores.append(f"{p['punto_id']}: evidencia no encontrada en el texto ({r:.0%})")
                else:
                    avisos.append(f"{p['punto_id']}: evidencia aproximada ({r:.0%}) — heredada de la v3.1")

    fecha = datetime.date.today().isoformat()
    por_cat = collections.Counter(q["categoria"] for q in preguntas)
    resumen = [f"# Validación del banco v3.2 — {fecha}", "",
               f"Corpus: `{coleccion}` · {len(preguntas)} preguntas + {len(negs)} negativas · "
               f"{sum(len(q['puntos']) for q in preguntas)} puntos · "
               f"{sum(1 for v in ev_estado.values() if v == 'literal')} evidencias literales.", "",
               "Por categoría: " + ", ".join(f"{k} {CATS[k]} = {por_cat[k]}" for k in sorted(por_cat)), "",
               f"Estados: {dict(collections.Counter(q['estado'] for q in preguntas))}", "",
               "## Errores", ""] + ([f"- {e}" for e in errores] or ["Ninguno."]) + \
              ["", "## Avisos", ""] + ([f"- {a}" for a in avisos] or ["Ninguno."]) + \
              ["", "## Preguntas", "", "| Q | Cat. | Tipo | Pregunta | Documento(s) | Artículos (pág.) | Puntos | Origen |",
               "|---|---|---|---|---|---|---|---|"]
    for q in preguntas:
        arts = "; ".join(f"{a['articulo']} (p. {','.join(a['paginas'])})" for a in q["articulos_esperados"]) or "(fila/sin artículo)"
        resumen.append(f"| {q['id']} | {q['categoria']} | {q['tipo_pregunta']} | {q['pregunta']} | "
                       f"{'; '.join(q['documentos_esperados'])} | {arts} | {len(q['puntos'])} | {q['origen']} |")
    print("\n".join(resumen[:14 + len(errores) + len(avisos) + 4]))
    if errores:
        print(f"\n{len(errores)} ERRORES: no se escribe el banco.")
        sys.exit(1)

    banco = {
        "version": "v3.2", "fecha": fecha, "corpus": coleccion,
        "descripcion": "Banco técnico: 17 preguntas de la v3.1 (Q05 y Q16 corregidas, Q17 propagada, categorías "
                       "recalculadas) + 13 nuevas (Q18–Q30) + 6 negativas. La v3.1 de la base de datos no se modificó.",
        "nota_revision": "Las preguntas con estado PROPUESTA_V32_PENDIENTE_REVISION_HUMANA requieren validación "
                         "por un segundo anotador antes de usarse como ground truth definitivo (Revisión 3 §3).",
        "categorias": CATS, "preguntas": preguntas,
        "negativas": [{"id": n["id"], "pregunta": n["pregunta"], "cobertura_esperada": "NO_ANSWER",
                       "motivo": n["motivo_no_cobertura"]} for n in negs],
    }
    (SALIDA / "banco_v32.json").write_text(json.dumps(banco, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(SALIDA / "banco_v32.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "pregunta", "categoria", "tema", "tipo_pregunta", "documentos_esperados",
                    "articulos_esperados", "n_puntos", "origen", "estado"])
        for q in preguntas:
            w.writerow([q["id"], q["pregunta"], q["categoria"], q["tema"], q["tipo_pregunta"],
                        " | ".join(q["documentos_esperados"]),
                        " | ".join(f"{a['documento']}: {a['articulo']}" for a in q["articulos_esperados"]),
                        len(q["puntos"]), q["origen"], q["estado"]])
    (SALIDA / "validacion_banco_v32.md").write_text("\n".join(resumen) + "\n", encoding="utf-8")
    print(f"\nEscrito: banco_v32.json, banco_v32.csv, validacion_banco_v32.md en {SALIDA}")


if __name__ == "__main__":
    main()
