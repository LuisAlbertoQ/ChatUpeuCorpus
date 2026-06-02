#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calcular_madurez.py

Script de apoyo para el OE8 del PPI:
Aplicar pruebas funcionales y piloto con usuarios, analizar resultados
de desempeño, usabilidad y explicabilidad, y determinar el nivel de madurez
alcanzado según el modelo CMMI--TRL adaptado.

Entrada principal:
    evaluacion_respuestas.csv

Salidas generadas:
    reporte_madurez.md
    resultados_madurez.csv

Uso:
    python calcular_madurez.py
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List


ARCHIVO_EVALUACION = Path("evaluacion_respuestas.csv")
REPORTE_MD = Path("reporte_madurez.md")
RESULTADOS_CSV = Path("resultados_madurez.csv")


@dataclass
class ResultadoMadurez:
    dimensiones: Dict[str, float]
    puntaje_global_original: float
    puntaje_global_ajustado: float
    dimension_critica_minima: float
    nivel_original: str
    nivel_ajustado: str
    total_preguntas: int


def convertir_float(valor: str, campo: str) -> float:
    """Convierte un valor de CSV a float y valida que esté en escala 1-5."""
    try:
        numero = float(str(valor).replace(",", ".").strip())
    except ValueError as exc:
        raise ValueError(f"Valor inválido en el campo '{campo}': {valor}") from exc

    if not 1 <= numero <= 5:
        raise ValueError(
            f"El campo '{campo}' debe estar en escala 1 a 5. Valor recibido: {numero}"
        )
    return numero


def clasificar_nivel(puntaje: float) -> str:
    """Clasifica el nivel de madurez según los rangos definidos en el PPI."""
    if 1.00 <= puntaje <= 2.00:
        return "Inicial"
    if 2.01 <= puntaje <= 3.00:
        return "Básico"
    if 3.01 <= puntaje <= 4.00:
        return "Gestionado"
    if 4.01 <= puntaje <= 5.00:
        return "Optimizado"
    return "No determinado"


def nivel_a_numero(nivel: str) -> int:
    return {"Inicial": 1, "Básico": 2, "Gestionado": 3, "Optimizado": 4}.get(nivel, 0)


def numero_a_nivel(numero: int) -> str:
    return {1: "Inicial", 2: "Básico", 3: "Gestionado", 4: "Optimizado"}.get(
        numero, "No determinado"
    )


def puntaje_maximo_por_nivel(nivel: str) -> float:
    return {"Inicial": 2.00, "Básico": 3.00, "Gestionado": 4.00, "Optimizado": 5.00}.get(
        nivel, 0.00
    )


def puntaje_tiempo(tiempo_segundos: float) -> int:
    """
    Convierte el tiempo de respuesta a escala 1-5.
    Ajusta estos rangos según la capacidad real del servidor.
    """
    if tiempo_segundos <= 5:
        return 5
    if tiempo_segundos <= 10:
        return 4
    if tiempo_segundos <= 15:
        return 3
    if tiempo_segundos <= 25:
        return 2
    return 1


def cargar_evaluacion(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró {path}. Copia o crea el archivo evaluacion_respuestas.csv."
        )

    with path.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        filas = list(lector)

    if not filas:
        raise ValueError("El archivo evaluacion_respuestas.csv está vacío.")

    campos_requeridos = {
        "id",
        "pregunta",
        "fuente_correcta",
        "respuesta_pertinente",
        "trazabilidad",
        "usabilidad",
        "gobernanza",
        "tiempo_respuesta_seg",
    }

    faltantes = campos_requeridos - set(filas[0].keys())
    if faltantes:
        raise ValueError(
            "Faltan columnas requeridas en evaluacion_respuestas.csv: "
            + ", ".join(sorted(faltantes))
        )

    return filas


def calcular_madurez(filas: List[dict]) -> ResultadoMadurez:
    funcional = []
    recuperacion = []
    explicabilidad = []
    usabilidad = []
    gobernanza = []
    preparacion = []

    for fila in filas:
        funcional.append(convertir_float(fila["respuesta_pertinente"], "respuesta_pertinente"))
        recuperacion.append(convertir_float(fila["fuente_correcta"], "fuente_correcta"))
        explicabilidad.append(convertir_float(fila["trazabilidad"], "trazabilidad"))
        usabilidad.append(convertir_float(fila["usabilidad"], "usabilidad"))
        gobernanza.append(convertir_float(fila["gobernanza"], "gobernanza"))

        try:
            tiempo = float(str(fila["tiempo_respuesta_seg"]).replace(",", ".").strip())
        except ValueError as exc:
            raise ValueError(
                f"Tiempo inválido en la fila {fila.get('id', '')}: "
                f"{fila['tiempo_respuesta_seg']}"
            ) from exc

        preparacion.append(puntaje_tiempo(tiempo))

    dimensiones = {
        "Funcional": mean(funcional),
        "Recuperación documental": mean(recuperacion),
        "Explicabilidad y trazabilidad": mean(explicabilidad),
        "Usabilidad": mean(usabilidad),
        "Gobernanza y uso responsable": mean(gobernanza),
        "Preparación tecnológica y mejora": mean(preparacion),
    }

    puntaje_global_original = mean(dimensiones.values())
    nivel_original = clasificar_nivel(puntaje_global_original)

    # Regla de consistencia del PPI:
    # el nivel global no debe superar en más de un nivel al valor mínimo
    # de las dimensiones críticas.
    dimensiones_criticas = [
        dimensiones["Funcional"],
        dimensiones["Recuperación documental"],
        dimensiones["Explicabilidad y trazabilidad"],
        dimensiones["Gobernanza y uso responsable"],
        dimensiones["Preparación tecnológica y mejora"],
    ]
    dimension_critica_minima = min(dimensiones_criticas)
    nivel_minimo_critico = clasificar_nivel(dimension_critica_minima)

    nivel_original_num = nivel_a_numero(nivel_original)
    nivel_minimo_num = nivel_a_numero(nivel_minimo_critico)
    nivel_ajustado_num = min(nivel_original_num, nivel_minimo_num + 1)
    nivel_ajustado = numero_a_nivel(nivel_ajustado_num)

    max_ajustado = puntaje_maximo_por_nivel(nivel_ajustado)
    puntaje_global_ajustado = min(puntaje_global_original, max_ajustado)

    return ResultadoMadurez(
        dimensiones=dimensiones,
        puntaje_global_original=puntaje_global_original,
        puntaje_global_ajustado=puntaje_global_ajustado,
        dimension_critica_minima=dimension_critica_minima,
        nivel_original=nivel_original,
        nivel_ajustado=nivel_ajustado,
        total_preguntas=len(filas),
    )


def generar_reporte(resultado: ResultadoMadurez) -> None:
    lineas = [
        "# Reporte de madurez del chatbot UPeU",
        "",
        "## Resumen",
        "",
        f"- Total de preguntas evaluadas: **{resultado.total_preguntas}**",
        f"- Puntaje global original: **{resultado.puntaje_global_original:.2f}**",
        f"- Nivel original: **{resultado.nivel_original}**",
        f"- Dimensión crítica mínima: **{resultado.dimension_critica_minima:.2f}**",
        f"- Puntaje global ajustado por consistencia: **{resultado.puntaje_global_ajustado:.2f}**",
        f"- Nivel de madurez ajustado: **{resultado.nivel_ajustado}**",
        "",
        "## Resultados por dimensión",
        "",
        "| Dimensión | Puntaje | Nivel referencial |",
        "|---|---:|---|",
    ]

    for dimension, puntaje in resultado.dimensiones.items():
        lineas.append(f"| {dimension} | {puntaje:.2f} | {clasificar_nivel(puntaje)} |")

    lineas.extend(
        [
            "",
            "## Interpretación",
            "",
            (
                f"El chatbot alcanza un nivel de madurez **{resultado.nivel_ajustado}** "
                "según el modelo CMMI--TRL adaptado. Este resultado debe interpretarse "
                "junto con las observaciones del piloto, la revisión de fuentes documentales, "
                "la usabilidad percibida, las reglas de gobernanza y la evidencia de trazabilidad."
            ),
            "",
            "## Regla de consistencia aplicada",
            "",
            (
                "El nivel global no debe superar en más de un nivel al valor mínimo obtenido "
                "en las dimensiones críticas: Funcional, Recuperación documental, "
                "Explicabilidad y trazabilidad, Gobernanza y Preparación tecnológica."
            ),
        ]
    )

    REPORTE_MD.write_text("\n".join(lineas), encoding="utf-8")


def generar_csv_resultados(resultado: ResultadoMadurez) -> None:
    with RESULTADOS_CSV.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["dimension", "puntaje", "nivel_referencial"])
        for dimension, puntaje in resultado.dimensiones.items():
            escritor.writerow([dimension, f"{puntaje:.2f}", clasificar_nivel(puntaje)])
        escritor.writerow([])
        escritor.writerow(["puntaje_global_original", f"{resultado.puntaje_global_original:.2f}"])
        escritor.writerow(["nivel_original", resultado.nivel_original])
        escritor.writerow(["dimension_critica_minima", f"{resultado.dimension_critica_minima:.2f}"])
        escritor.writerow(["puntaje_global_ajustado", f"{resultado.puntaje_global_ajustado:.2f}"])
        escritor.writerow(["nivel_ajustado", resultado.nivel_ajustado])


def main() -> None:
    filas = cargar_evaluacion(ARCHIVO_EVALUACION)
    resultado = calcular_madurez(filas)
    generar_reporte(resultado)
    generar_csv_resultados(resultado)

    print("Evaluación de madurez completada.")
    print(f"Preguntas evaluadas: {resultado.total_preguntas}")
    print(f"Puntaje global original: {resultado.puntaje_global_original:.2f}")
    print(f"Nivel original: {resultado.nivel_original}")
    print(f"Puntaje global ajustado: {resultado.puntaje_global_ajustado:.2f}")
    print(f"Nivel ajustado: {resultado.nivel_ajustado}")
    print(f"Reporte generado: {REPORTE_MD}")
    print(f"CSV generado: {RESULTADOS_CSV}")


if __name__ == "__main__":
    main()
