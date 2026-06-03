# Reporte de madurez del chatbot UPeU

## Resumen ejecutivo

- **Total de interacciones evaluadas:** 138
- **Total de evaluaciones de piloto:** 0
- **Puntaje global final:** **3.00** / 5.00
- **Nivel de madurez:** **Básico**
- **Dimensión crítica mínima:** 2.00

## Métricas crudas del chatbot (de registro_interacciones.db)

| Métrica | Valor |
|---|---:|
| % respuestas exitosas (M02) | 50.7% |
| % fuera de dominio (M03) | 2.9% |
| % sin cobertura (M04) | 27.5% |
| % preguntas ambiguas (M05) | 5.8% |
| % errores (M06) | 13.0% |
| % con fuentes documentales | 48.6% |
| Tiempo promedio (segundos) | 16.54 |

## Resultados por dimensión

| Dimensión | Auto | Piloto | Final | Nivel |
|---|---:|---:|---:|---|
| Funcional | 3.00 | — | 3.00 | Básico |
| Recuperación documental | 2.00 | — | 2.00 | Inicial |
| Explicabilidad y trazabilidad | 2.00 | — | 2.00 | Inicial |
| Usabilidad | 4.00 | — | 4.00 | Gestionado |
| Gobernanza y uso responsable | 5.00 | — | 5.00 | Optimizado |
| Preparación tecnológica y mejora | 2.00 | — | 2.00 | Inicial |

## Interpretación

El chatbot alcanza un nivel de madurez **Básico** según el modelo CMMI--TRL adaptado, con un puntaje global de **3.00** sobre 5.00. El cálculo combina métricas automáticas del registro de interacciones con puntajes Likert del piloto de usuarios (100% automático (sin datos de piloto)).

## Regla de consistencia aplicada

El nivel global (Básico) no supera en más de un nivel al valor mínimo de las dimensiones críticas (2.00).

## Fuente de datos

Las métricas se calcularon directamente desde la tabla `interacciones`
de `registro_interacciones.db`, sin puntajes manuales. El snapshot
histórico quedó guardado en la tabla `evaluacion_automatica`.