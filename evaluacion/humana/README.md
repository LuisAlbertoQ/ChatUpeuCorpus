# Evaluación humana de generación (v3.1)

- `fichas_humanas_v31/`: 17 fichas oficiales (66 puntos, claims atómicos, citas por ocurrencia). **Ya evaluadas e importadas (FASE 4 cerrada).**
- `fichas_humanas/`: borradores pre-v3.1 (referencia, no oficiales).
- `importar_ficha_humana.py`: validador + importador idempotente (exige `groundtruth_version=v3.1_curado`).
- `calcular_metricas_humanas.py`: agregados macro/micro (completitud, faithfulness, citation, relevancia).
- `GUIA_EVALUACION_HUMANA_V3.md`: reglas del evaluador.
- `ficha_documental.md`: ficha del corpus (generada por `legacy/generar_ficha.py`).

Resultados FASE 4: completitud micro 0.106 · faithfulness micro 0.918 · citation micro 0.879 · relevancia 2.53.

> **2026-11-21/22:** estos resultados corresponden al corpus V2 con el prompt `v2-adaptativo` y el recorte de 700 caracteres. Los 66 juicios de completitud se usaron para validar la medida automática `../comparacion_v2_v3/completitud_auto.py` (89 % de acuerdo cubierto sí/no, kappa 0.53). Con el corpus V3 y las mejoras, la completitud automática subió a ~0.57 (banco v3.2). **Pendiente**: evaluar con personas la fidelidad de las respuestas del prompt `v3-completo` (~2× más largas), que la medida automática no mide.

## Revisión 3 — evaluación humana pendiente (2026-11-22)

El .docx (§8) pide una submuestra **ciega** de respuestas del sistema final (y de los generadores del Exp. B: Qwen2.5-7B vs `llama3.2:3b`, `qwen3:4b-instruct`, `gemma3:4b`),
con la rúbrica fijada antes de ver los resultados y acuerdo entre evaluadores. Las fichas de esta carpeta
(FASE 4) evaluaron el sistema V2 de septiembre, así que sirven como antecedente y para reutilizar la rúbrica
(`GUIA_EVALUACION_HUMANA_V3.md`), no como resultado del estudio. Se hace después del gold set y del Exp. B oficial; decide el generador final del chatbot (candidato `qwen3:4b-instruct`,
ver `../ESTADO_REVISION_3.md` §5). Qué reciben los evaluadores: `../ENTREGA_EVALUADORES.md` (ronda 2).

**Herramienta lista (2026-11-23):**
- `RUBRICA_FIDELIDAD_REV3.md`: rúbrica fijada antes de ver resultados (fidelidad 0–2, corrección 0–2, atribución
  exacta/parcial/incorrecta/ausente, relevancia 1–5) y cómo se resume.
- `fichas_fidelidad.py preparar`: fichas ciegas idénticas para dos evaluadores (`ficha_fidelidad_E1.xlsx` / `_E2.xlsx`):
  respuestas de los 4 generadores mezcladas con código R001…, hoja "Fuentes" con el texto de los artículos que recibió
  el modelo; la clave código → modelo queda en `clave_NO_ENTREGAR.json`.
- `fichas_fidelidad.py analizar`: κ por dimensión, desacuerdos, comparación contra Qwen2.5-7B (Wilcoxon + Holm,
  IC95) y `detalle_fidelidad.csv` para la Tabla 6.
- Prueba con el banco v3.2 (12 preguntas × 4 modelos = 48 respuestas): `fidelidad_rev3/prueba_banco_v32/` — **solo
  para revisar el formato, no se entrega**. Las fichas oficiales se generan con el gold set (50 preguntas × 4 = 200).
  Tests: `backend/tests/test_fichas_fidelidad.py`.
