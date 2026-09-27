# Evaluación de generación

- `baseline_generacion_v3_oficial.py`: genera las 17 respuestas oficiales con el Top4 persistido del retrieval v3 (Qwen 2.5:7b, prompt v2-adaptativo). **No re-ejecutar**: el baseline `GEN_20260924_232127_8e01ef` está congelado.
- `evaluar_generacion.py`, `evaluar_generacion_file.py`, `insertar_generacion.py`: harnesses históricos (corrida preliminar + inserción con backend detenido).
- `generacion_GEN_*.json/.csv`, `ficha_evaluacion_GEN_*.json/.csv`: artefactos de corridas.
