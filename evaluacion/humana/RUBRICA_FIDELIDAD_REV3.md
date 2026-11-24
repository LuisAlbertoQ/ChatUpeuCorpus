# Rúbrica de evaluación humana — Revisión 3 (.docx §8)

Fijada el **2026-11-23**, antes de evaluar las respuestas del Exp. B oficial. No se cambia después de ver
resultados; cualquier ajuste se registra aquí con fecha y motivo.

## Qué se evalúa

Una submuestra **ciega** de respuestas: las mismas preguntas respondidas por cada generador del Exp. B
(Qwen2.5-7B, `llama3.2:3b`, `qwen3:4b-instruct`, `gemma3:4b`) con la misma recuperación y el mismo prompt. El
evaluador no sabe qué modelo escribió cada respuesta. Dos evaluadores trabajan por separado sobre la misma ficha.

## Orden y escalas

Se evalúa en este orden (lo general al final, para no sesgar lo específico):

| Dimensión | Escala | Criterio |
|---|---|---|
| **Fidelidad** | 0 / 1 / 2 | 2 = todo lo que afirma está en los fragmentos de la hoja "Fuentes"; 1 = alguna afirmación menor sin respaldo; 0 = afirma algo importante sin respaldo o contradice las fuentes |
| **Corrección factual** | 0 / 1 / 2 | Frente a la respuesta de referencia y los puntos clave del gold set: 2 = correcta y completa en lo esencial; 1 = correcta pero incompleta o con un error menor; 0 = incorrecta o no responde |
| **Atribución** | exacta / parcial / incorrecta / ausente | Categorías del .docx §7: exacta = documento y artículo correctos; parcial = documento correcto, artículo no; incorrecta = otra fuente; ausente = no cita |
| **Relevancia** | 1 a 5 | 1 = no responde lo preguntado; 5 = responde directo y suficiente, sin relleno |

**Abstenciones** ("No encontré información…") en preguntas con respuesta: fidelidad 2 (no inventa), corrección 0,
atribución ausente, y se anota "abstención". El análisis reporta aparte cuántas hubo por sistema.

**Fuentes:** la hoja "Fuentes" muestra el texto completo de cada artículo que se le pasó al modelo. El modelo pudo
recibir solo una parte del artículo (fragmentos de hasta 350 tokens); si una afirmación está en el artículo pero
claramente no en la parte relevante, anótalo. Los fragmentos sin artículo (TUPA, políticas) se revisan en el PDF.

## Cómo se resume

- Puntaje por respuesta = promedio de los dos evaluadores; fidelidad y corrección se llevan a 0–1 (÷ 2).
- Acuerdo entre evaluadores: κ de Cohen por dimensión (lectura de Landis y Koch). Los desacuerdos quedan listados
  en `desacuerdos_fidelidad.csv`; si κ < 0.60 en fidelidad, se discuten los casos y se reporta el κ inicial.
- Comparación contra Qwen2.5-7B: Wilcoxon pareado por pregunta + Holm (3 comparaciones), IC95 bootstrap y tamaño
  de efecto (.docx §9). Es la columna de fidelidad, corrección y relevancia de la **Tabla 3**.
- **Decisión del generador del chatbot** (`../ESTADO_REVISION_3.md` §5): se adopta `qwen3:4b-instruct` si su fidelidad
  no es significativamente menor que la de Qwen2.5-7B y su corrección es igual o mejor.

## Herramienta

`fichas_fidelidad.py preparar` arma las fichas (`fidelidad_rev3/ficha_fidelidad_E1.xlsx` y `_E2.xlsx`) y la clave
(`clave_NO_ENTREGAR.json`, que no se da a los evaluadores). `fichas_fidelidad.py analizar` calcula κ y la comparación.
Tamaño propuesto: 50 preguntas del gold set (estratificadas por categoría) × 4 sistemas = 200 respuestas por evaluador.
