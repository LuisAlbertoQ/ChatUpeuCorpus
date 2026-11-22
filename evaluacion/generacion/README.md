# Evaluación de generación

- `baseline_generacion_v3_oficial.py`: genera las 17 respuestas oficiales con el Top4 persistido del retrieval v3 (Qwen 2.5:7b, prompt v2-adaptativo). **No re-ejecutar**: el baseline `GEN_20260924_232127_8e01ef` está congelado.
- `evaluar_generacion.py`, `evaluar_generacion_file.py`, `insertar_generacion.py`: harnesses históricos (corrida preliminar + inserción con backend detenido).
- `generacion_GEN_*.json/.csv`, `ficha_evaluacion_GEN_*.json/.csv`: artefactos de corridas.

> Desde 2026-11-21 la generación se evalúa end-to-end con `../comparacion_v2_v3/correr_17q_e2e.py` (corpus V3, semilla fija, banco v3.2) en lugar de este baseline sobre el Top-4 persistido de septiembre. El prompt vigente es `v3-completo` (antes `v2-adaptativo`); ver `../comparacion_v2_v3/COMPARACION_V2_V3.md` §7 y §10.

## Revisión 3 — Experimento B (Qwen vs Llama 3), 2026-11-22

Listo para correr, **no corrido**: se hace con el mejor recuperador del Exp. A (bge-m3) y el gold set.
- Llama 3 8B ya está en Ollama (`llama3:latest`, ID `365c0bd3c000`); se elige con la variable `OLLAMA_MODEL`:
  `evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta B_llama_s42 -Vars @{OLLAMA_MODEL="llama3:latest"; OLLAMA_SEED="42"} -BancoJson banco_gold_260.json`
- Control S0 (sin recuperación): `-Vars @{RAG_SIN_RECUPERACION="1"}`.
- Mismo prompt (`v3-completo`), contexto, top-k y reglas en ambos modelos. Métricas: atribución
  (OK_ARTICULO / OK_DOCUMENTO), completitud automática, latencia p50/p95; la fidelidad requiere evaluación
  humana o un juez validado contra personas (.docx §7).
