# Banco de preguntas y ground truth

- `preguntas_comparacion.json`: banco canónico 17 Q (documento/artículo esperado).
- `sincronizar_banco.py`: upsert idempotente JSON → `banco_preguntas` (uso: `python banco/sincronizar_banco.py`).
- `migrar_banco.py`: [YA EJECUTADO] one-shot CSV → DB.
- `GROUND_TRUTH_DECISION.md`: decisiones de curación v2.
- `CHANGELOG_GROUNDTRUTH_V31.md`: trazabilidad v3 (50 pts) → v3.1 (66 pts, tablas `groundtruth_v31_*`) + banco negativo N01-N06 (`banco_no_answer`).

Ground truth oficial vigente: **v3.1_curado** (congelado, no modificar).
