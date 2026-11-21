# Hipótesis del estudio — Revisión 3 (RAG 100 % local UPeU)

Fuente: `docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx`, § “Hipótesis contrastables”.
RQ principal: sobre el corpus de 48 documentos institucionales en español, ¿cómo afectan
la estrategia de recuperación, el tamaño de fragmentación, el modelo de embeddings y el
modelo generativo local a la recuperación documental, la calidad de las respuestas,
la fidelidad y la atribución verificable?

Regla de reporte (del documento): cada hipótesis debe producir al menos un resultado
específico. No se incorporarán resultados que no estén vinculados con una pregunta
o hipótesis del estudio.

| ID | Hipótesis | Experimento | Resultado que la responde |
|---|---|---|---|
| H1 | Los métodos de recuperación semántica basados en embeddings superan a BM25 en Recall@5 sobre el corpus institucional. | A | Tabla 2: Recall@5 por recuperador |
| H2 | Existe un tamaño de fragmento intermedio entre las configuraciones evaluadas que maximiza el desempeño de recuperación documental. | A | Tabla 2 + Figura 1: Recall@5 vs chunk por recuperador |
| H3 | Los modelos generativos locales evaluados presentan diferencias significativas en calidad de respuesta, fidelidad, atribución y latencia bajo las mismas condiciones. | B | Tabla 3: Qwen2.5-7B vs Llama 3 8B |
| H4 | El desempeño de recuperación varía entre categorías documentales y tiende a disminuir en las categorías con menor representación en el corpus. | A | Tabla 4 + Figura 2: Recall@5 por categoría con IC |
| H5 | El sistema RAG puede abstenerse correctamente ante consultas fuera de dominio y ambiguas, alcanzando una tasa de abstención correcta previamente definida. | C | Tabla 5: abstención correcta, falsa abstención (criterio de éxito H5: abstention_accuracy ≥ 0.90 con IC95%) |

Estado: H1–H5 aprobadas (cronograma 04-09). Criterio H5 propuesto; pendiente de ratificación del equipo/asesor.
