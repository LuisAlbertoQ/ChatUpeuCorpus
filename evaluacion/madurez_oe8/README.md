# Madurez OE8 (FASE 5–6)

- `calcular_madurez.py`: métricas automáticas + 6 dimensiones (umbrales en `UMBRALES_OE8`). Uso FASE 5: `python madurez_oe8/calcular_madurez.py --auto-only` (snapshot `OE8_AUTO_PRE_PILOTO`, sin piloto/CAP final).
- `instrumento_piloto_oe8_v1.json`: 30 ítems Likert (6×5). `plantilla_piloto.csv`, `importar_piloto.py`, `PROCEDIMIENTO_PILOTO.md`.
- `reporte_madurez.md`, `resultados_madurez.csv`: deliverables (se regeneran).
- `INSTRUMENTOS.md`, `COMPARACION_LLMS.md`: documentos OE6/comparativa (Qwen2.5-7B adoptado).

Estado: FASE 5 cerrada (auto 2/3/2/5/5/2) · FASE 6 pendiente de datos (0 respuestas reales).

> **2026-11-22:** el snapshot de FASE 5 es del corpus V2. Con la configuración vigente (corpus V3, prompt `v3-completo`) el tiempo típico de respuesta pasó de ~11 s a ~23 s (p95 58 s), lo que baja la dimensión de usabilidad (≤ 20 s → 4, ≤ 30 s → 3). `COMPARACION_LLMS.md` es de junio (corpus v1) y sigue siendo la base de la elección de Qwen2.5-7B.
