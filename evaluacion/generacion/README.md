# Evaluación de generación

- `baseline_generacion_v3_oficial.py`: genera las 17 respuestas oficiales con el Top4 persistido del retrieval v3 (Qwen 2.5:7b, prompt v2-adaptativo). **No re-ejecutar**: el baseline `GEN_20260924_232127_8e01ef` está congelado.
- `evaluar_generacion.py`, `evaluar_generacion_file.py`, `insertar_generacion.py`: harnesses históricos (corrida preliminar + inserción con backend detenido).
- `generacion_GEN_*.json/.csv`, `ficha_evaluacion_GEN_*.json/.csv`: artefactos de corridas.

> Desde 2026-11-21 la generación se evalúa end-to-end con `../comparacion_v2_v3/correr_17q_e2e.py` (corpus V3, semilla fija, banco v3.2) en lugar de este baseline sobre el Top-4 persistido de septiembre. El prompt vigente es `v3-completo` (antes `v2-adaptativo`); ver `../comparacion_v2_v3/COMPARACION_V2_V3.md` §7 y §10.

## Revisión 3 — Experimento B (generadores locales), 2026-11-22

Listo para correr, **no corrido**: se hace con el mejor recuperador del Exp. A (bge-m3) y el gold set.
- El generador se elige con la variable `OLLAMA_MODEL` (ejemplo con el modelo ya descartado; los nuevos se corren igual):
  `evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta B_llama_s42 -Vars @{OLLAMA_MODEL="llama3:latest"; OLLAMA_SEED="42"} -BancoJson banco_gold_260.json`
- Control S0 (sin recuperación): `-Vars @{RAG_SIN_RECUPERACION="1"}`.
- Mismo prompt (`v3-completo`), contexto, top-k y reglas en ambos modelos. Métricas: atribución
  (OK_ARTICULO / OK_DOCUMENTO), completitud automática, latencia p50/p95; la fidelidad requiere evaluación
  humana o un juez validado contra personas (.docx §7).

### Corrida preliminar (2026-11-22, banco v3.2, configuración congelada `c47d455a`)

Análisis: `exp_b_generacion.py` → `exp_b/` (`resumen_exp_b.csv`, `comparaciones_exp_b.csv`, `corridas_exp_b.json`).
Completitud = proporción de puntos cubiertos por pregunta (proxy automático); atribución sobre el texto de la respuesta.

| Sistema | Completitud | Atribución exacta | Sin cita | Latencia p50 / p95 | Timeouts (M06) | Negativas |
|---|---|---|---|---|---|---|
| Qwen2.5-7B (2 semillas) | **0.533** | 0.417 | 0.133 | 20 s / 58 s | 0 % | 12/12 |
| Llama 3 8B (semilla 42) | 0.391 | 0.400 | 0.300 | 39 s / 121 s | **17 %** | 6/6 |
| S0 sin recuperación (Qwen, 2 semillas) | 0.029 | 0.017 | 0.517 | 8 s / 23 s | 0 % | 11/12* |

- **Llama 3 vs Qwen:** completitud −0.14 [−0.27, −0.03], p Holm 0.03; atribución exacta sin diferencia (p 0.74);
  latencia +28 s, p < 0.001. En las 25 preguntas que Llama 3 alcanzó a responder, la completitud es parecida
  (0.47 vs 0.51): la diferencia viene sobre todo de los timeouts.
- **Llama 3 no es viable en este hardware:** con `num_ctx` 8192 ocupa 7.3 GB y la GPU tiene 6 GB (5 GB libres;
  Windows usa ~1 GB). Ollama deja 10 de sus 33 capas en CPU, y esa parte depende de la RAM de Docker (7.7 GB),
  que se agota con la caché de prompts de Ollama: el modelo se vuelve más lento con el uso.
- **La corrida de Llama 3 con semilla 7 no es válida** (`E2E_B_llama_s7_*`, 27/30 timeouts): mide la degradación
  por memoria, no al modelo; se conserva solo como evidencia. Una corrida anterior de la semilla 42 se descartó
  porque se cruzó con otra corrida (desde entonces `ablacion.ps1` no arranca si ya hay una activa).
- **S0 confirma el valor de la recuperación:** sin documentos Qwen da respuestas genéricas (completitud 0.03, casi
  sin citas correctas). *La negativa "respondida" de S0 es en realidad una abstención redactada de otra forma
  ("No hay información sobre el tipo de cambio…") que el post-proceso no reconoce.
- **Decisión (2026-11-22): Llama 3 8B queda descartado** por inviabilidad en el hardware (motivo completo en
  `../ESTADO_REVISION_3.md` §4). Se reporta como evaluado y descartado, con estos datos.

### Modelos nuevos: `llama3.2:3b` (S5b), `qwen3:4b` (S7), `gemma3:4b` (S8) — por instalar

| | `llama3.2:3b` | `qwen3:4b` | `gemma3:4b` |
|---|---|---|---|
| Tamaño (Q4) | ~2.0 GB | ~2.5 GB | ~3.3 GB |
| ¿Cabe en ~5 GB de GPU con `num_ctx` 8192? | sí, holgado | sí | justo (verificar capas en GPU) |
| Por qué | Familia Llama (la que pide el .docx) | Misma familia que Qwen2.5, más chico | Otra familia, buena en español |
| Cuidado | Español y formato de citas más débiles | Modo "pensar": hay que apagarlo | A veces menos estricto con el formato |

Qué hay que tocar para correrlos:
1. **Descargarlos** en el volumen de Ollama (`ollama pull`, ~7.8 GB en total) y registrar su ID en `../REPRODUCIBILIDAD.md`.
2. **Qwen3 "pensar":** `qwen3:4b` razona en un bloque `<think>` antes de responder; con él la respuesta se ensucia y
   tarda mucho más. Agregar una variable (p. ej. `OLLAMA_THINK=false`) que mande `"think": false` a Ollama, con un
   test, y limpiar cualquier `<think>` que quede.
3. **Post-proceso:** revisar las primeras respuestas de cada modelo. La reparación de citas y la detección de "no hay
   información" (`_quitar_meta_no_info`) están afinadas con las frases de Qwen2.5; otra redacción de la abstención
   puede pasar como respuesta normal (ya pasó con S0).
4. **Mismas condiciones para todos:** prompt `v3-completo`, `num_ctx` 8192, temperatura 0.2, semillas 42 y 7, timeout
   120 s, mismo banco. Antes de cada corrida, reiniciar `oe5-llm` para vaciar la caché de Ollama.
5. **Análisis:** `exp_b_generacion.py` ya acepta cualquier modelo (`qwen=… llama32=… qwen3=… gemma3=… s0=…`);
   3 comparaciones contra Qwen2.5-7B con Holm.

No cambia: el chatbot (sigue con Qwen2.5-7B), la recuperación, `docker-compose.yml` (ya acepta `OLLAMA_MODEL`),
`ablacion.ps1` ni los demás experimentos.
