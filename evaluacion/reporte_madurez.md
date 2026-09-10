# Reporte de madurez del chatbot UPeU

## Resumen ejecutivo

- **Total de interacciones evaluadas:** 300
- **Total de evaluaciones de piloto:** 0
- **Puntaje global final:** **3.50** / 5.00
- **Nivel de madurez:** **Gestionado**
- **Dimensión crítica mínima:** 3.00

## Métricas crudas del chatbot (de registro_interacciones.db)

| Métrica | Valor |
|---|---:|
| % respuestas exitosas (M02) | 59.0% |
| % fuera de dominio (M03) | 5.0% |
| % sin cobertura (M04) | 22.0% |
| % preguntas ambiguas (M05) | 5.3% |
| % errores (M06) | 8.7% |
| % con fuentes documentales | 60.3% |
| Tiempo promedio (segundos) | 14.91 |

## Resultados por dimensión

| Dimensión | Auto | Piloto | Final | Nivel |
|---|---:|---:|---:|---|
| Funcional | 3.00 | — | 3.00 | Básico |
| Recuperación documental | 3.00 | — | 3.00 | Básico |
| Explicabilidad y trazabilidad | 3.00 | — | 3.00 | Básico |
| Usabilidad | 4.00 | — | 4.00 | Gestionado |
| Gobernanza y uso responsable | 5.00 | — | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 3.00 | — | 3.00 | Básico |

## Cobertura por categoría del corpus (A–E)

Atribución por la categoría de la primera fuente citada.
M03/M05 no llevan fuentes y no aparecen. Un % M04 alto en una
categoría indica dónde falta (o es débil) el corpus (OE1).

| Categoría | Interacciones | M02 | M04 | M06 | % M04 |
|---|---:|---:|---:|---:|---:|
| A | 56 | 55 | 1 | 0 | 1.8% |
| B | 69 | 65 | 4 | 0 | 5.8% |
| C | 15 | 15 | 0 | 0 | 0.0% |
| D | 4 | 4 | 0 | 0 | 0.0% |
| E | 21 | 19 | 2 | 0 | 9.5% |

**Categoría con peor cobertura:** `E` con **9.5%** de M04 (2 de 21 interacciones con fuentes).

## Interpretación

El chatbot alcanza un nivel de madurez **Gestionado** según el modelo CMMI--TRL adaptado, con un puntaje global de **3.50** sobre 5.00. El cálculo combina métricas automáticas del registro de interacciones con puntajes Likert del piloto de usuarios (100% automático (sin datos de piloto)).

## Regla de consistencia aplicada

El nivel global (Gestionado) no supera en más de un nivel al valor mínimo de las dimensiones críticas (3.00).

## Fuente de datos

Las métricas se calcularon directamente desde la tabla `interacciones`
de `registro_interacciones.db`, sin puntajes manuales. El snapshot
histórico quedó guardado en la tabla `evaluacion_automatica`.