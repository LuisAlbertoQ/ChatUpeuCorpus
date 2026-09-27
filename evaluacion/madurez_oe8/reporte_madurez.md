# Reporte de madurez del chatbot UPeU

## Resumen ejecutivo

- **Total de interacciones evaluadas:** 1066
- **Total de evaluaciones de piloto:** 0
- **Puntaje global final:** **3.00** / 5.00
- **Nivel de madurez:** **Básico**
- **Dimensión crítica mínima:** 2.00

## Métricas crudas del chatbot (de registro_interacciones.db)

| Métrica | Valor |
|---|---:|
| % respuestas exitosas (M02) | 42.7% |
| % fuera de dominio (M03) | 9.6% |
| % sin cobertura (M04) | 22.5% |
| % preguntas ambiguas (M05) | 14.7% |
| % errores (M06) | 10.5% |
| % con fuentes documentales | 56.3% |
| Tiempo promedio (segundos) | 5.95 |

## Resultados por dimensión

| Dimensión | Auto | Piloto | Final | Nivel |
|---|---:|---:|---:|---|
| Funcional | 2.00 | — | 2.00 | Inicial |
| Recuperación documental | 3.00 | — | 3.00 | Básico |
| Explicabilidad y trazabilidad | 2.00 | — | 2.00 | Inicial |
| Usabilidad | 5.00 | — | 5.00 | Optimizado |
| Gobernanza y uso responsable | 5.00 | — | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 2.00 | — | 2.00 | Inicial |

## Cobertura por categoría del corpus (A–E)

Atribución por la categoría de la primera fuente citada.
M03/M05 no llevan fuentes y no aparecen. Un % M04 alto en una
categoría indica dónde falta (o es débil) el corpus (OE1).

| Categoría | Interacciones | M02 | M04 | M06 | % M04 |
|---|---:|---:|---:|---:|---:|
| A | 94 | 83 | 11 | 0 | 11.7% |
| B | 384 | 256 | 128 | 0 | 33.3% |
| C | 39 | 39 | 0 | 0 | 0.0% |
| D | 22 | 21 | 1 | 0 | 4.5% |
| E | 40 | 33 | 7 | 0 | 17.5% |

**Categoría con peor cobertura:** `B` con **33.3%** de M04 (128 de 384 interacciones con fuentes).

## Interpretación

El chatbot alcanza un nivel de madurez **Básico** según el modelo CMMI--TRL adaptado, con un puntaje global de **3.00** sobre 5.00. El cálculo combina métricas automáticas del registro de interacciones con puntajes Likert del piloto de usuarios (100% automático (sin datos de piloto)).

## Regla de consistencia aplicada

El nivel global (Básico) no supera en más de un nivel al valor mínimo de las dimensiones críticas (2.00).

## Fuente de datos

Las métricas se calcularon directamente desde la tabla `interacciones`
de `registro_interacciones.db`, sin puntajes manuales. El snapshot
histórico quedó guardado en la tabla `evaluacion_automatica`.