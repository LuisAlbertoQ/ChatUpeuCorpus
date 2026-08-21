#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calcular_madurez.py

Calcula el nivel de madurez del chatbot UPeU combinando métricas
automáticas del registro de interacciones con puntajes Likert del
piloto de usuarios, según el modelo CMMI--TRL adaptado (OE8).

Fuentes de datos (registro_interacciones.db):
  - interacciones:        log automático del chatbot
  - evaluacion_piloto:    puntajes Likert 1-5 del piloto
  - banco_preguntas:      banco canónico de preguntas

Salidas:
  - reporte_madurez.md          (deliverable para el PPI)
  - resultados_madurez.csv      (deliverable para el PPI)
  - INSERT en evaluacion_automatica (snapshot histórico con tendencia)

Uso:
    python calcular_madurez.py
"""

from __future__ import annotations

import csv
import datetime
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Dict, Optional


# -----------------------------------------------------------------------------
# Paths y constantes
# -----------------------------------------------------------------------------
EVAL_DIR = Path(__file__).parent
DB_PATH = EVAL_DIR.parent / "registro_interacciones.db"
REPORTE_MD = EVAL_DIR / "reporte_madurez.md"
RESULTADOS_CSV = EVAL_DIR / "resultados_madurez.csv"

# Pesos para combinar métricas automáticas + piloto (60% datos reales / 40% subjetivo)
PESOS = {"auto": 0.6, "piloto": 0.4}

DIMENSIONES = [
    "Funcional",
    "Recuperación documental",
    "Explicabilidad y trazabilidad",
    "Usabilidad",
    "Gobernanza y uso responsable",
    "Preparación tecnológica y mejora",
]

DIMENSIONES_CRITICAS = [
    "Funcional",
    "Recuperación documental",
    "Explicabilidad y trazabilidad",
    "Gobernanza y uso responsable",
    "Preparación tecnológica y mejora",
]

CAPS_NIVEL = {"Inicial": 2.00, "Básico": 3.00, "Gestionado": 4.00, "Optimizado": 5.00}
NIVELES_NUM = {"Inicial": 1, "Básico": 2, "Gestionado": 3, "Optimizado": 4}

# Categorías del corpus (A-E) y regex para extraerlas de las fuentes
# guardadas en `interacciones` (formato: "... · [B – Académico y estudios]").
CATEGORIAS_CORPUS = ["A", "B", "C", "D", "E"]
_RE_CATEGORIA_FUENTE = re.compile(r"\[([A-E])\s*[–-]")


# -----------------------------------------------------------------------------
# Desglose por categoría (dónde falta corpus)
# -----------------------------------------------------------------------------
def calcular_desglose_categorias(conn) -> Dict[str, Dict[str, float]]:
    """Contador de interacciones por categoría del corpus (ítem 4 Tier 3).

    Atribuye cada interacción CON fuentes a la categoría de su primera
    fuente (categoría primaria). Permite detectar qué categorías
    concentran más M04 ("el corpus tenía candidatos pero el sistema no
    respondió") = dónde falta o sobra corpus.

    Nota: M03/M05 no llevan fuentes, por lo que no aparecen aquí.
    """
    filas = conn.execute(
        """
        SELECT tipo_mensaje, fuentes FROM interacciones
        WHERE fuentes IS NOT NULL AND fuentes != ''
        """
    ).fetchall()

    desglose = {
        cat: {"total": 0, "M02": 0, "M03": 0, "M04": 0, "M05": 0, "M06": 0}
        for cat in CATEGORIAS_CORPUS
    }

    for tipo_mensaje, fuentes_raw in filas:
        m = _RE_CATEGORIA_FUENTE.search(fuentes_raw or "")
        if not m:
            continue
        cat = m.group(1)
        if cat not in desglose:
            continue
        desglose[cat]["total"] += 1
        if tipo_mensaje in desglose[cat]:
            desglose[cat][tipo_mensaje] += 1

    return desglose


def categoria_peor_cobertura(desglose: Dict) -> Optional[Dict]:
    """Categoría con mayor % M04 entre las que tienen interacciones."""
    candidatas = []
    for cat, d in desglose.items():
        if d["total"] > 0:
            pct_m04 = d["M04"] / d["total"] * 100
            candidatas.append((pct_m04, cat, d))
    if not candidatas:
        return None
    pct_m04, cat, d = max(candidatas, key=lambda x: x[0])
    if pct_m04 <= 0:
        return None
    return {"categoria": cat, "pct_m04": pct_m04, **{
        k: v for k, v in d.items() if k != "total"}}


# -----------------------------------------------------------------------------
# Dataclass
# -----------------------------------------------------------------------------
@dataclass
class ResultadoMadurez:
    dimensiones_auto: Dict[str, float]
    dimensiones_piloto: Optional[Dict[str, float]]
    dimensiones_final: Dict[str, float]
    puntaje_global: float
    nivel: str
    dimension_critica_minima: float
    total_interacciones: int
    total_piloto: int
    metricas_raw: Dict
    desglose_categorias: Dict = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def clasificar_nivel(puntaje: float) -> str:
    if 1.00 <= puntaje <= 2.00:
        return "Inicial"
    if 2.01 <= puntaje <= 3.00:
        return "Básico"
    if 3.01 <= puntaje <= 4.00:
        return "Gestionado"
    if 4.01 <= puntaje <= 5.00:
        return "Optimizado"
    return "No determinado"


def numero_a_nivel(numero: int) -> str:
    return {v: k for k, v in NIVELES_NUM.items()}.get(numero, "No determinado")


# -----------------------------------------------------------------------------
# Métricas automáticas desde `interacciones`
# -----------------------------------------------------------------------------
def calcular_metricas_automaticas(conn) -> Dict:
    totales = conn.execute(
        """
        SELECT
            COUNT(*),
            AVG(tiempo_respuesta),
            SUM(CASE WHEN tipo_mensaje='M02' THEN 1 ELSE 0 END),
            SUM(CASE WHEN tipo_mensaje='M03' THEN 1 ELSE 0 END),
            SUM(CASE WHEN tipo_mensaje='M04' THEN 1 ELSE 0 END),
            SUM(CASE WHEN tipo_mensaje='M05' THEN 1 ELSE 0 END),
            SUM(CASE WHEN tipo_mensaje='M06' THEN 1 ELSE 0 END),
            SUM(CASE WHEN fuentes IS NOT NULL AND fuentes != '' THEN 1 ELSE 0 END)
        FROM interacciones
        """
    ).fetchone()

    total = totales[0] or 1
    return {
        "total_interacciones": totales[0] or 0,
        "tiempo_promedio": float(totales[1] or 0.0),
        "pct_m02": (totales[2] or 0) / total * 100,
        "pct_m03": (totales[3] or 0) / total * 100,
        "pct_m04": (totales[4] or 0) / total * 100,
        "pct_m05": (totales[5] or 0) / total * 100,
        "pct_m06": (totales[6] or 0) / total * 100,
        "pct_con_fuentes": (totales[7] or 0) / total * 100,
    }


def _puntaje_por_porcentaje(pct: float, escala: list) -> float:
    """Convierte un porcentaje en puntaje 1-5 según umbrales."""
    for umbral, valor in escala:
        if pct >= umbral:
            return float(valor)
    return 1.0


def _puntaje_por_tiempo(segundos: float, escala: list) -> float:
    """Convierte un tiempo en puntaje 1-5 según umbrales."""
    for umbral, valor in escala:
        if segundos <= umbral:
            return float(valor)
    return 1.0


def calcular_dimensiones_auto(m: Dict) -> Dict[str, float]:
    """Convierte métricas crudas en puntajes 1-5 por dimensión."""

    # Funcional: % de respuestas exitosas (M02)
    funcional = _puntaje_por_porcentaje(
        m["pct_m02"],
        [(90, 5), (75, 4), (50, 3), (25, 2)],
    )

    # Recuperación documental: % con fuentes
    recuperacion = _puntaje_por_porcentaje(
        m["pct_con_fuentes"],
        [(90, 5), (75, 4), (50, 3), (25, 2)],
    )

    # Explicabilidad: % con fuentes (proxy de trazabilidad)
    explicabilidad = _puntaje_por_porcentaje(
        m["pct_con_fuentes"],
        [(95, 5), (80, 4), (60, 3), (40, 2)],
    )

    # Usabilidad: tiempo promedio de respuesta (escala ajustada a hardware)
    usabilidad = _puntaje_por_tiempo(
        m["tiempo_promedio"],
        [(10, 5), (20, 4), (30, 3), (40, 2)],
    )

    # Gobernanza: % de rechazos correctos (M03 + M05 = fuera de dominio detectado)
    pct_rechazo = m["pct_m03"] + m["pct_m05"]
    if 5 <= pct_rechazo <= 30:
        gobernanza = 5.0
    elif pct_rechazo < 5:
        gobernanza = 3.0
    else:
        gobernanza = 2.0

    # Preparación: inversa de % M06 (errores)
    preparacion = _puntaje_por_porcentaje(
        100 - m["pct_m06"],
        [(98, 5), (95, 4), (90, 3), (80, 2)],
    )

    return {
        "Funcional": funcional,
        "Recuperación documental": recuperacion,
        "Explicabilidad y trazabilidad": explicabilidad,
        "Usabilidad": usabilidad,
        "Gobernanza y uso responsable": gobernanza,
        "Preparación tecnológica y mejora": preparacion,
    }


# -----------------------------------------------------------------------------
# Métricas desde `evaluacion_piloto`
# -----------------------------------------------------------------------------
def calcular_dimensiones_piloto(conn) -> tuple:
    """Retorna (dict_promedios, total_evaluaciones) o (None, 0) si vacío."""
    fila = conn.execute(
        """
        SELECT
            AVG(funcional), AVG(recuperacion), AVG(explicabilidad),
            AVG(usabilidad), AVG(gobernanza), AVG(preparacion),
            COUNT(*)
        FROM evaluacion_piloto
        """
    ).fetchone()

    if not fila or not fila[6]:
        return None, 0

    promedios = {
        "Funcional": float(fila[0] or 0),
        "Recuperación documental": float(fila[1] or 0),
        "Explicabilidad y trazabilidad": float(fila[2] or 0),
        "Usabilidad": float(fila[3] or 0),
        "Gobernanza y uso responsable": float(fila[4] or 0),
        "Preparación tecnológica y mejora": float(fila[5] or 0),
    }
    return promedios, int(fila[6])


# -----------------------------------------------------------------------------
# Combinación + regla de consistencia
# -----------------------------------------------------------------------------
def combinar_dimensiones(
    auto: Dict[str, float], piloto: Optional[Dict[str, float]]
) -> Dict[str, float]:
    final = {}
    for dim in DIMENSIONES:
        if piloto and piloto.get(dim, 0) > 0:
            final[dim] = PESOS["auto"] * auto[dim] + PESOS["piloto"] * piloto[dim]
        else:
            final[dim] = auto[dim]
    return final


def aplicar_regla_consistencia(dimensiones: Dict[str, float]) -> tuple:
    """El nivel global no debe superar en más de 1 al mínimo crítico."""
    puntaje_global = mean(dimensiones.values())
    nivel_global = clasificar_nivel(puntaje_global)

    criticas = {k: dimensiones[k] for k in DIMENSIONES_CRITICAS}
    dim_min = min(criticas.values())
    nivel_min = clasificar_nivel(dim_min)

    nivel_global_num = NIVELES_NUM[nivel_global]
    nivel_min_num = NIVELES_NUM[nivel_min]
    nivel_ajustado_num = min(nivel_global_num, nivel_min_num + 1)
    nivel_ajustado = numero_a_nivel(nivel_ajustado_num)

    puntaje_ajustado = min(puntaje_global, CAPS_NIVEL[nivel_ajustado])
    return puntaje_ajustado, nivel_ajustado, dim_min


# -----------------------------------------------------------------------------
# Persistencia del snapshot
# -----------------------------------------------------------------------------
def guardar_snapshot(
    conn, m: Dict, dim: Dict[str, float], nivel: str,
    puntaje_global: float, dim_min: float,
) -> None:
    periodo = datetime.date.today().strftime("%Y-%m")
    conn.execute(
        """
        INSERT INTO evaluacion_automatica
        (periodo, fecha_calculo, total_interacciones,
         pct_m02, pct_m03, pct_m04, pct_m05, pct_m06, pct_con_fuentes,
         tiempo_promedio, tiempo_p95,
         funcional_auto, recuperacion_auto, explicabilidad_auto,
         usabilidad_auto, gobernanza_auto, preparacion_auto,
         puntaje_global, nivel, dimension_critica_minima)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?)
        """,
        (
            periodo,
            datetime.datetime.now().isoformat(),
            m["total_interacciones"],
            m["pct_m02"], m["pct_m03"], m["pct_m04"],
            m["pct_m05"], m["pct_m06"], m["pct_con_fuentes"],
            m["tiempo_promedio"], m.get("tiempo_p95", 0.0),
            dim["Funcional"],
            dim["Recuperación documental"],
            dim["Explicabilidad y trazabilidad"],
            dim["Usabilidad"],
            dim["Gobernanza y uso responsable"],
            dim["Preparación tecnológica y mejora"],
            puntaje_global, nivel, dim_min,
        ),
    )


# -----------------------------------------------------------------------------
# Reportes
# -----------------------------------------------------------------------------
def generar_reporte(r: ResultadoMadurez) -> None:
    lineas = [
        "# Reporte de madurez del chatbot UPeU",
        "",
        "## Resumen ejecutivo",
        "",
        f"- **Total de interacciones evaluadas:** {r.total_interacciones}",
        f"- **Total de evaluaciones de piloto:** {r.total_piloto}",
        f"- **Puntaje global final:** **{r.puntaje_global:.2f}** / 5.00",
        f"- **Nivel de madurez:** **{r.nivel}**",
        f"- **Dimensión crítica mínima:** {r.dimension_critica_minima:.2f}",
        "",
        "## Métricas crudas del chatbot (de registro_interacciones.db)",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| % respuestas exitosas (M02) | {r.metricas_raw['pct_m02']:.1f}% |",
        f"| % fuera de dominio (M03) | {r.metricas_raw['pct_m03']:.1f}% |",
        f"| % sin cobertura (M04) | {r.metricas_raw['pct_m04']:.1f}% |",
        f"| % preguntas ambiguas (M05) | {r.metricas_raw['pct_m05']:.1f}% |",
        f"| % errores (M06) | {r.metricas_raw['pct_m06']:.1f}% |",
        f"| % con fuentes documentales | {r.metricas_raw['pct_con_fuentes']:.1f}% |",
        f"| Tiempo promedio (segundos) | {r.metricas_raw['tiempo_promedio']:.2f} |",
        "",
        "## Resultados por dimensión",
        "",
        "| Dimensión | Auto | Piloto | Final | Nivel |",
        "|---|---:|---:|---:|---|",
    ]

    for dim in DIMENSIONES:
        auto = r.dimensiones_auto.get(dim, 0)
        piloto = "—"
        if r.dimensiones_piloto and dim in r.dimensiones_piloto:
            piloto = f"{r.dimensiones_piloto[dim]:.2f}"
        final = r.dimensiones_final.get(dim, 0)
        nivel = clasificar_nivel(final)
        lineas.append(f"| {dim} | {auto:.2f} | {piloto} | {final:.2f} | {nivel} |")

    # Desglose por categoría (dónde falta corpus)
    if r.desglose_categorias:
        lineas.extend([
            "",
            "## Cobertura por categoría del corpus (A–E)",
            "",
            "Atribución por la categoría de la primera fuente citada.",
            "M03/M05 no llevan fuentes y no aparecen. Un % M04 alto en una",
            "categoría indica dónde falta (o es débil) el corpus (OE1).",
            "",
            "| Categoría | Interacciones | M02 | M04 | M06 | % M04 |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for cat in CATEGORIAS_CORPUS:
            d = r.desglose_categorias[cat]
            if d["total"] == 0:
                continue
            pct_m04 = d["M04"] / d["total"] * 100
            lineas.append(
                f"| {cat} | {d['total']} | {d['M02']} | {d['M04']} "
                f"| {d['M06']} | {pct_m04:.1f}% |"
            )
        peor = categoria_peor_cobertura(r.desglose_categorias)
        if peor:
            lineas.extend([
                "",
                (
                    f"**Categoría con peor cobertura:** `{peor['categoria']}` "
                    f"con **{peor['pct_m04']:.1f}%** de M04 "
                    f"({peor['M04']} de {r.desglose_categorias[peor['categoria']]['total']} "
                    f"interacciones con fuentes)."
                ),
            ])

    pesos_txt = (
        f"60% automático / 40% piloto"
        if r.dimensiones_piloto
        else "100% automático (sin datos de piloto)"
    )
    lineas.extend([
        "",
        "## Interpretación",
        "",
        (
            f"El chatbot alcanza un nivel de madurez **{r.nivel}** según el "
            f"modelo CMMI--TRL adaptado, con un puntaje global de "
            f"**{r.puntaje_global:.2f}** sobre 5.00. El cálculo combina "
            f"métricas automáticas del registro de interacciones con "
            f"puntajes Likert del piloto de usuarios ({pesos_txt})."
        ),
        "",
        "## Regla de consistencia aplicada",
        "",
        (
            f"El nivel global ({r.nivel}) no supera en más de un nivel al "
            f"valor mínimo de las dimensiones críticas "
            f"({r.dimension_critica_minima:.2f})."
        ),
        "",
        "## Fuente de datos",
        "",
        "Las métricas se calcularon directamente desde la tabla `interacciones`",
        "de `registro_interacciones.db`, sin puntajes manuales. El snapshot",
        "histórico quedó guardado en la tabla `evaluacion_automatica`.",
    ])

    REPORTE_MD.write_text("\n".join(lineas), encoding="utf-8")


def generar_csv_resultados(r: ResultadoMadurez) -> None:
    with RESULTADOS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "dimension", "puntaje_auto", "puntaje_piloto",
            "puntaje_final", "nivel",
        ])
        for dim in DIMENSIONES:
            piloto = ""
            if r.dimensiones_piloto and dim in r.dimensiones_piloto:
                piloto = f"{r.dimensiones_piloto[dim]:.2f}"
            w.writerow([
                dim,
                f"{r.dimensiones_auto.get(dim, 0):.2f}",
                piloto,
                f"{r.dimensiones_final.get(dim, 0):.2f}",
                clasificar_nivel(r.dimensiones_final.get(dim, 0)),
            ])
        w.writerow([])
        w.writerow(["total_interacciones", r.total_interacciones])
        w.writerow(["total_evaluaciones_piloto", r.total_piloto])
        w.writerow(["puntaje_global", f"{r.puntaje_global:.2f}"])
        w.writerow(["nivel_madurez", r.nivel])
        w.writerow(["dimension_critica_minima", f"{r.dimension_critica_minima:.2f}"])


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: no se encontró la base de datos en {DB_PATH}.")
        print("Inicia el backend al menos una vez para que se cree el esquema.")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # 1. Métricas automáticas desde el log
    metricas = calcular_metricas_automaticas(conn)
    if metricas["total_interacciones"] == 0:
        print("ERROR: la tabla 'interacciones' está vacía.")
        print("Realiza algunas consultas al chatbot antes de calcular madurez.")
        conn.close()
        return 1

    dim_auto = calcular_dimensiones_auto(metricas)

    # 2. Métricas del piloto (pueden no existir aún)
    dim_piloto, total_piloto = calcular_dimensiones_piloto(conn)

    # 3. Combinación ponderada + regla de consistencia
    dim_final = combinar_dimensiones(dim_auto, dim_piloto)
    puntaje, nivel, dim_min = aplicar_regla_consistencia(dim_final)

    # 3b. Desglose por categoría (dónde falta corpus)
    desglose = calcular_desglose_categorias(conn)

    # 4. Snapshot histórico en evaluacion_automatica
    guardar_snapshot(conn, metricas, dim_auto, nivel, puntaje, dim_min)
    conn.commit()
    conn.close()

    # 5. Deliverables para el PPI
    resultado = ResultadoMadurez(
        dimensiones_auto=dim_auto,
        dimensiones_piloto=dim_piloto,
        dimensiones_final=dim_final,
        puntaje_global=puntaje,
        nivel=nivel,
        dimension_critica_minima=dim_min,
        total_interacciones=metricas["total_interacciones"],
        total_piloto=total_piloto,
        metricas_raw=metricas,
        desglose_categorias=desglose,
    )
    generar_reporte(resultado)
    generar_csv_resultados(resultado)

    print("=" * 60)
    print("Evaluación de madurez completada")
    print("=" * 60)
    print(f"Interacciones evaluadas:    {metricas['total_interacciones']}")
    print(f"Evaluaciones de piloto:     {total_piloto}")
    print(f"Puntaje global final:       {puntaje:.2f}")
    print(f"Nivel de madurez:           {nivel}")
    print(f"Dimensión crítica mínima:   {dim_min:.2f}")
    print("=" * 60)
    print(f"Reporte:   {REPORTE_MD}")
    print(f"CSV:       {RESULTADOS_CSV}")
    print(f"Snapshot:  tabla 'evaluacion_automatica'")

    peor = categoria_peor_cobertura(desglose)
    if peor:
        total_cat = desglose[peor["categoria"]]["total"]
        print("-" * 60)
        print(
            f"Cobertura por categoría: peor = {peor['categoria']} "
            f"({peor['pct_m04']:.1f}% M04 de {total_cat} interacciones)"
        )
    return 0


if __name__ == "__main__":
    exit(main())
