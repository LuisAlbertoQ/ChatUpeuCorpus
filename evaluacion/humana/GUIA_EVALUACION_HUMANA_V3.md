# Guía de Evaluación Humana — Baseline Generación V3

**Baseline oficial:** `GEN_20260924_232127_8e01ef` ligado a `EXP_20260924_231553_2cd31b` (corpus `corpus_upeu_v2`, `mpnet`, `top 15→4`, `thr 0.40`, `prompt v2-adaptativo`, `temp 0.2`, `qwen2.5:7b`). 17 respuestas congeladas. **No regenerar. No LLM-as-judge.**

**Evaluador:** `investigador_manual_v1` (solo al completar/importar, no en fichas vacías).

---

## Orden obligatorio (¿por qué no empezar por relevancia?)

1. **Completitud** (checklist 50 puntos)
2. **Claims** (extraer atómicos)
3. **Faithfulness** (claim vs contexto real)
4. **Citation correctness** (cita vs fuente)
5. **Relevancia global 1-5**
6. **Notas / causa fallo**

Empezar por relevancia sesga: el evaluador tiende a justificar completitud/faithfulness para coincidir con su impresión global. Evaluar contenido y evidencia primero reduce sesgo de confirmación.

---

## Completitud

Para cada `punto_esperado`:

- **CUBIERTO**: respuesta expresa el punto de forma suficiente (sin exigir cita).
- **PARCIAL**: menciona el concepto pero omite parte necesaria o incompleto.
- **NO_CUBIERTO**: no aparece o dice algo diferente.

> No decidir por cita. Primero contenido.

*Ejemplo genérico (no Q01-Q17):* Punto “Entregar solicitud y DNI”. Respuesta “Entregar solicitud.” → **PARCIAL** (falta DNI). “Entregar solicitud y DNI (TUPA, Art 5)” → **CUBIERTO**.

Guardar: `estado`, `justificacion`, `fragmento_respuesta`.

---

## Claims

Afirmación factual/normativa atómica.

*Ejemplo:* “Para X se necesita A y B.” → claim1: necesita A, claim2: necesita B.

No considerar: saludos, conectores, sugerencias genéricas, disclaimers sin factual.

Guardar `claim_id, claim_texto`. Para M04 sin factual: dejar `claims=[]` → `faithfulness NULL/N/A` (no 1.0).

---

## Faithfulness

Cada claim **solo vs `contexto_real`** (chunks Top4 enviados a Qwen), **no** vs reglamento completo.

- **SOPORTADO**
- **PARCIALMENTE_SOPORTADO**
- **NO_SOPORTADO**

> Verdadero en el reglamento pero no en contexto → **NO_SOPORTADO** (distinción fundamental). Guardar `evidencia_contexto`.

---

## Citation correctness

Para cada cita inline (`(DOC, Art)` o `Artículo 69°`):

- **CORRECTA**: fuente respalda claramente el claim asociado.
- **PARCIAL**: respalda solo parte.
- **INCORRECTA**: no respalda.
- **NO_ASOCIABLE**: no se puede asociar a claim razonable.

> `citation_match=valid` (sintaxis) ≠ `CORRECTA` (semántica). Diagnósticos automáticos son auxiliares, no recomendación.

---

## Relevancia (al final)

- **5**: responde directa y suficientemente, sin irrelevante.
- **4**: responde directa con omisión/desviación menor.
- **3**: parcial, útil pero insuficiente.
- **2**: tangencial/mayormente insuficiente.
- **1**: no responde.

M04 en ANSWERABLE: evaluar literalmente, no auto 1.

---

## M04 `answerable_but_abstained=1`

Q04, Q09, Q11, Q17. Ficha muestra diagnóstico, **no preselecciona** `NO_CUBIERTO` ni relevancia. Decisión humana.

---

## Estructura ficha

- **Información del caso**: pregunta, `respuesta_congelada`, `contexto_real`, ground truth.
- **Diagnósticos automáticos**: `source_validity`, `citation_match`, `citation_presence`, `answerable_but_abstained` (etiquetados *automático*).
- **Evaluación humana** (vacío): puntos, claims, citas, relevancia, notas.

---

## Checklist previo a guardar

- [ ] todos los puntos con estado
- [ ] claims identificados o justificación 0 claims
- [ ] todos los claims con faithfulness
- [ ] todas las citas con citation correctness
- [ ] relevancia 1-5
- [ ] evaluador no vacío
- [ ] notas si dudoso

---

## Flujo importación

1. Completar JSON ficha (no CSV manual).
2. `python evaluacion/humana/importar_ficha_humana.py evaluacion/humana/fichas_humanas/ficha_QXX_*.json`
3. Validador revisa: `pregunta_id` Q01-17, `punto_id` existe en v3, estados permitidos, `relevancia 1-5`, `evaluador` no vacío, no duplicados, `generation_experimento_id` == oficial (rechaza distinto), parcial requiere marca explícita, `null` inicial permitido.
4. Si error → NO importar.
5. No overwrite silencioso (`UNIQUE`).
6. Calcular métricas solo tras importación válida: `python evaluacion/humana/calcular_metricas_humanas.py` (estricta `covered/total`, ponderada `(covered+0.5*partial)/total`; faithfulness/citation igual; `NULL` si no evaluable).

Mientras fichas vacías: agregados `NULL`.

---

## Evaluador y no automatizar

No decidir con regex si punto cubierto/claim soportado/cita correcta/relevancia. Juicio humano con justificación auditable.

---

## Archivos

- Fichas vacías: `evaluacion/fichas_humanas/ficha_Q*_GEN_20260924_232127_8e01ef.json` (50 puntos, 32 citas, claims [], relevancia null)
- Consolidado: `evaluacion/fichas_humanas/evaluacion_manual_v3.csv` (vista editable, no reemplaza JSON)
- Importador/calculador: ver arriba
