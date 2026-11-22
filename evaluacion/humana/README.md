# Evaluación humana de generación (v3.1)

- `fichas_humanas_v31/`: 17 fichas oficiales (66 puntos, claims atómicos, citas por ocurrencia). **Ya evaluadas e importadas (FASE 4 cerrada).**
- `fichas_humanas/`: borradores pre-v3.1 (referencia, no oficiales).
- `importar_ficha_humana.py`: validador + importador idempotente (exige `groundtruth_version=v3.1_curado`).
- `calcular_metricas_humanas.py`: agregados macro/micro (completitud, faithfulness, citation, relevancia).
- `GUIA_EVALUACION_HUMANA_V3.md`: reglas del evaluador.
- `ficha_documental.md`: ficha del corpus (generada por `legacy/generar_ficha.py`).

Resultados FASE 4: completitud micro 0.106 · faithfulness micro 0.918 · citation micro 0.879 · relevancia 2.53.

> **2026-11-21/22:** estos resultados corresponden al corpus V2 con el prompt `v2-adaptativo` y el recorte de 700 caracteres. Los 66 juicios de completitud se usaron para validar la medida automática `../comparacion_v2_v3/completitud_auto.py` (89 % de acuerdo cubierto sí/no, kappa 0.53). Con el corpus V3 y las mejoras, la completitud automática subió a ~0.57 (banco v3.2). **Pendiente**: evaluar con personas la fidelidad de las respuestas del prompt `v3-completo` (~2× más largas), que la medida automática no mide.
