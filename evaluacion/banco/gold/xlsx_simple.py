# -*- coding: utf-8 -*-
"""Lectura y escritura mínima de .xlsx con la librería estándar (sin openpyxl).

Escritura: varias hojas, encabezado en negrita con fondo, ancho de columnas, primera fila fija,
texto con ajuste de línea y listas desplegables (validación de datos) por columna.
Lectura: devuelve las filas de una hoja como listas de texto; entiende cadenas compartidas
(lo que escribe Excel al guardar) y cadenas en línea (lo que escribe este módulo).
"""
from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_INVALIDOS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def col_letra(i: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def col_indice(letras: str) -> int:
    n = 0
    for c in letras:
        n = n * 26 + ord(c) - 64
    return n - 1


def _celda(ref: str, valor, estilo: int) -> str:
    s = f' s="{estilo}"' if estilo else ""
    if valor is None or valor == "":
        return f'<c r="{ref}"{s}/>' if estilo else ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}"{s}><v>{valor}</v></c>'
    texto = escape(_INVALIDOS.sub("", str(valor)))
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'


def _hoja_xml(hoja: dict) -> str:
    filas = hoja["filas"]
    anchos = hoja.get("anchos", [])
    partes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              f'<worksheet xmlns="{NS}" xmlns:r="{NS_R}">',
              '<sheetViews><sheetView workbookViewId="0">'
              '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
              '</sheetView></sheetViews>']
    if anchos:
        partes.append("<cols>" + "".join(
            f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(anchos)) + "</cols>")
    partes.append("<sheetData>")
    editables = set(hoja.get("columnas_editables", []))
    for r, fila in enumerate(filas, start=1):
        celdas = []
        for c, v in enumerate(fila):
            estilo = 1 if r == 1 else (3 if c in editables else 2)
            celdas.append(_celda(f"{col_letra(c)}{r}", v, estilo))
        partes.append(f'<row r="{r}">' + "".join(celdas) + "</row>")
    partes.append("</sheetData>")
    val = hoja.get("validaciones", [])
    if val:
        partes.append(f'<dataValidations count="{len(val)}">')
        for v in val:
            # v = (columna, fila_ini, fila_fin, formula) ; formula: '"A,B,C"' o 'Hoja!$A$2:$A$50'
            col, ini, fin, formula = v
            ref = f"{col_letra(col)}{ini}:{col_letra(col)}{fin}"
            partes.append(f'<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
                          f'errorTitle="Valor no válido" error="Elige un valor de la lista" sqref="{ref}">'
                          f"<formula1>{escape(formula)}</formula1></dataValidation>")
        partes.append("</dataValidations>")
    partes.append("</worksheet>")
    return "".join(partes)


_ESTILOS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{NS}">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFD9E1F2"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/></patternFill></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
    '<cellXfs count="4"><xf/>'
    '<xf fontId="1" fillId="2" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>'
    '<xf applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>'
    '<xf fillId="3" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>'
    '</cellXfs></styleSheet>'
)


def escribir(path, hojas: list[dict]) -> None:
    """hojas: [{nombre, filas, anchos?, validaciones?, columnas_editables?}] (columnas editables = fondo amarillo)."""
    n = len(hojas)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(1, n + 1)) + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{NS_PKG}"><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f'<workbook xmlns="{NS}" xmlns:r="{NS_R}"><sheets>'
          + "".join(f'<sheet name="{escape(h["nombre"][:31])}" sheetId="{i}" r:id="rId{i}"/>'
                    for i, h in enumerate(hojas, start=1)) + "</sheets></workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               f'<Relationships xmlns="{NS_PKG}">'
               + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                         f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, n + 1))
               + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
               'relationships/styles" Target="styles.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _ESTILOS)
        for i, h in enumerate(hojas, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _hoja_xml(h))


def _texto(el) -> str:
    return "".join(t.text or "" for t in el.iter(f"{{{NS}}}t"))


def leer(path, hoja: str) -> list[list[str]]:
    """Filas de la hoja `hoja` como listas de texto (celdas vacías = "")."""
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        destino = {r.get("Id"): r.get("Target") for r in rels}
        rid = None
        for s in wb.iter(f"{{{NS}}}sheet"):
            if s.get("name") == hoja:
                rid = s.get(f"{{{NS_R}}}id")
        if rid is None:
            raise KeyError(f"{path}: no existe la hoja {hoja!r}")
        objetivo = destino[rid].lstrip("/")
        objetivo = objetivo if objetivo.startswith("xl/") else "xl/" + objetivo
        compartidas = []
        if "xl/sharedStrings.xml" in z.namelist():
            compartidas = [_texto(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{{{NS}}}si")]
        raiz = ET.fromstring(z.read(objetivo))
    filas = []
    for row in raiz.iter(f"{{{NS}}}row"):
        fila = {}
        for c in row.iter(f"{{{NS}}}c"):
            col = col_indice(re.match(r"[A-Z]+", c.get("r")).group())
            tipo = c.get("t")
            v = c.find(f"{{{NS}}}v")
            if tipo == "s" and v is not None:
                val = compartidas[int(v.text)]
            elif tipo == "inlineStr":
                val = _texto(c)
            else:
                val = v.text if v is not None and v.text is not None else ""
                if re.fullmatch(r"-?\d+\.0", val):
                    val = val[:-2]
            fila[col] = val
        idx = int(row.get("r")) - 1
        while len(filas) < idx:
            filas.append([])
        filas.append([fila.get(i, "") for i in range(max(fila) + 1)] if fila else [])
    return filas
