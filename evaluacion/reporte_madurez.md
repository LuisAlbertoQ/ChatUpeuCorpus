# Reporte de madurez del chatbot UPeU

## Resumen ejecutivo

- **Total de interacciones evaluadas:** 289
- **Total de evaluaciones de piloto:** 0
- **Puntaje global final:** **3.00** / 5.00
- **Nivel de madurez:** **Básico**
- **Dimensión crítica mínima:** 2.00

## Métricas crudas del chatbot (de registro_interacciones.db)

| Métrica | Valor |
|---|---:|
| % respuestas exitosas (M02) | 58.1% |
| % fuera de dominio (M03) | 5.2% |
| % sin cobertura (M04) | 22.1% |
| % preguntas ambiguas (M05) | 5.5% |
| % errores (M06) | 9.0% |
| % con fuentes documentales | 58.8% |
| Tiempo promedio (segundos) | 14.79 |

## Resultados por dimensión

| Dimensión | Auto | Piloto | Final | Nivel |
|---|---:|---:|---:|---|
| Funcional | 3.00 | — | 3.00 | Básico |
| Recuperación documental | 3.00 | — | 3.00 | Básico |
| Explicabilidad y trazabilidad | 2.00 | — | 2.00 | Inicial |
| Usabilidad | 4.00 | — | 4.00 | Gestionado |
| Gobernanza y uso responsable | 5.00 | — | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 3.00 | — | 3.00 | Básico |

## Cobertura por categoría del corpus (A–E)

Atribución por la categoría de la primera fuente citada.
M03/M05 no llevan fuentes y no aparecen. Un % M04 alto en una
categoría indica dónde falta (o es débil) el corpus (OE1).

| Categoría | Interacciones | M02 | M04 | M06 | % M04 |
|---|---:|---:|---:|---:|---:|
| A | 55 | 54 | 1 | 0 | 1.8% |
| B | 60 | 57 | 3 | 0 | 5.0% |
| C | 15 | 15 | 0 | 0 | 0.0% |
| D | 4 | 4 | 0 | 0 | 0.0% |
| E | 20 | 19 | 1 | 0 | 5.0% |

**Categoría con peor cobertura:** `B` con **5.0%** de M04 (3 de 60 interacciones con fuentes).

## Interpretación

El chatbot alcanza un nivel de madurez **Básico** según el modelo CMMI--TRL adaptado, con un puntaje global de **3.00** sobre 5.00. El cálculo combina métricas automáticas del registro de interacciones con puntajes Likert del piloto de usuarios (100% automático (sin datos de piloto)).

## Regla de consistencia aplicada

El nivel global (Básico) no supera en más de un nivel al valor mínimo de las dimensiones críticas (2.00).

## Fuente de datos

Las métricas se calcularon directamente desde la tabla `interacciones`
de `registro_interacciones.db`, sin puntajes manuales. El snapshot
histórico quedó guardado en la tabla `evaluacion_automatica`.