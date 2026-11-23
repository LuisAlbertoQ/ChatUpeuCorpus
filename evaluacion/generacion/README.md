# Evaluación de generación

- `baseline_generacion_v3_oficial.py`: genera las 17 respuestas oficiales con el Top4 persistido del retrieval v3 (Qwen 2.5:7b, prompt v2-adaptativo). **No re-ejecutar**: el baseline `GEN_20260924_232127_8e01ef` está congelado.
- `evaluar_generacion.py`, `evaluar_generacion_file.py`, `insertar_generacion.py`: harnesses históricos (corrida preliminar + inserción con backend detenido).
- `generacion_GEN_*.json/.csv`, `ficha_evaluacion_GEN_*.json/.csv`: artefactos de corridas.

> Desde 2026-11-21 la generación se evalúa end-to-end con `../comparacion_v2_v3/correr_17q_e2e.py` (corpus V3, semilla fija, banco v3.2) en lugar de este baseline sobre el Top-4 persistido de septiembre. El prompt vigente es `v3-completo` (antes `v2-adaptativo`); ver `../comparacion_v2_v3/COMPARACION_V2_V3.md` §7 y §10.

## Revisión 3 — Experimento B (generadores locales), 2026-11-22

Preliminar corrido con el banco v3.2 (abajo); el oficial se hace con el mejor recuperador del Exp. A (bge-m3) y el gold set.
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
  `../ESTADO_REVISION_3.md` §4). Se reporta como evaluado y descartado, con estos datos. Aprobado por el asesor el 2026-11-23.

### Modelos nuevos: `llama3.2:3b` (S5b), `qwen3:4b-instruct` (S7), `gemma3:4b` (S8) — descargados 2026-11-22

Prueba de carga con `num_ctx` 8192 (una consulta corta, sin el chatbot):

| Modelo | ID | Memoria con contexto 8192 | GPU / CPU | Observación |
|---|---|---|---|---|
| `llama3.2:3b` | `a80c4f17acd5` | 3.5 GB | 100 % GPU | Responde normal |
| `qwen3:4b` | `359d7dd4bcda` | 4.7 GB | 90 / 10 | Es la variante **de razonamiento**: sin `think` deja la respuesta vacía (todo va a "thinking"); con `think: false` igual escribe el razonamiento en la respuesta. Reemplazado por `qwen3:4b-instruct` |
| **`qwen3:4b-instruct`** (S7) | `0edcdef34593` | 4.7 GB | 90 / 10 | Responde directo, sin razonamiento: **es el que se usa** |
| `gemma3:4b` | `68ceab7e468a` | 3.9 GB | 79 / 21 | Incluye un módulo de visión que ocupa memoria; queda parte en CPU |

### Corrida preliminar con los modelos nuevos (2026-11-23, banco v3.2, 2 semillas, `c47d455a`)

Corridas `../comparacion_v2_v3/E2E_B_{llama32,qwen3,gemma3}_s{42,7}_*` (reiniciando `oe5-llm` antes de cada una);
la referencia es la misma corrida de Qwen2.5-7B del 2026-11-22. Análisis → `exp_b_nuevos/`. Las primeras respuestas de
cada modelo se revisaron a mano: ninguna abstención disfrazada, ningún texto de razonamiento.

| Sistema | Completitud | Atribución exacta | Sin cita | Palabras | Latencia p50 / p95 | Timeouts | Negativas |
|---|---|---|---|---|---|---|---|
| S6 Qwen2.5-7B (referencia) | 0.533 | 0.417 | 0.133 | 204 | 20.0 s / 58.3 s | 0 % | 12/12 |
| S5b `llama3.2:3b` | 0.507 | 0.350 | 0.217 | 256 | **7.4 s / 18.4 s** | 0 % | 12/12 |
| S7 `qwen3:4b-instruct` | **0.631** | **0.517** | 0.033 | 383 | 22.1 s / 25.7 s | 0 % | 12/12 |
| S8 `gemma3:4b` | 0.584 | 0.467 | 0.000 | 363 | 17.0 s / 34.3 s | 0 % | 12/12 |

Diferencias contra Qwen2.5-7B (IC95 bootstrap, Wilcoxon + Holm sobre 3 comparaciones; 30 preguntas):

| Métrica | `llama3.2:3b` | `qwen3:4b-instruct` | `gemma3:4b` |
|---|---|---|---|
| Completitud | −0.03 [−0.10, +0.05], p 0.44 | +0.10 [+0.02, +0.18], p 0.11 | +0.05 [−0.03, +0.13], p 0.25 |
| Atribución exacta | −0.07 [−0.20, +0.07], p 0.71 | +0.10 [+0.02, +0.20], p 0.19 | +0.05 [−0.07, +0.17], p 0.71 |
| Latencia | **−15.8 s**, p < 0.001 * | **−5.4 s**, p 0.04 * | **−5.6 s**, p 0.04 * |

Lectura:
- **Los tres caben y son estables:** 0 timeouts, 12/12 negativas abstenidas, sin falsas abstenciones (Qwen tuvo 1).
  Ninguno se degradó con el uso, a diferencia de Llama 3 8B.
- **Calidad:** ningún modelo nuevo es significativamente distinto de Qwen2.5-7B tras Holm. `qwen3:4b-instruct` es el
  mejor en completitud y atribución (su IC95 excluye 0 pero no sobrevive a Holm con 30 preguntas); `llama3.2:3b` queda
  algo por debajo pero sin diferencia significativa.
- **Latencia:** los tres son más rápidos que Qwen2.5-7B (significativo). `llama3.2:3b` es ~3 veces más rápido; Qwen3 y
  Gemma bajan sobre todo el p95 (26 / 34 s vs 58 s), porque caben casi enteros en la GPU.
- **Cuidado al interpretar la completitud:** Qwen3 y Gemma escriben respuestas ~1.8 veces más largas; el proxy automático
  premia cubrir más puntos y no castiga lo que sobra ni lo que esté mal. La fidelidad (si lo dicho está en las fuentes)
  se decide con la evaluación humana del gold set.
- Pendiente: repetir con el gold set de 260 (Exp. B oficial) y evaluar fidelidad a ciegas.

Plan original (antes de descargar, histórico):

| | `llama3.2:3b` | `qwen3:4b-instruct` | `gemma3:4b` |
|---|---|---|---|
| Tamaño (Q4) | ~2.0 GB | ~2.5 GB | ~3.3 GB |
| ¿Cabe en ~5 GB de GPU con `num_ctx` 8192? | sí, holgado | sí | justo (verificar capas en GPU) |
| Por qué | Familia Llama (la que pide el .docx) | Misma familia que Qwen2.5, más chico | Otra familia, buena en español |
| Cuidado | Español y formato de citas más débiles | Modo "pensar": hay que apagarlo | A veces menos estricto con el formato |

Qué había que tocar para correrlos (hecho 2026-11-22/23):
1. **Descargarlos** en el volumen de Ollama (`ollama pull`, ~7.8 GB en total) y registrar su ID en `../REPRODUCIBILIDAD.md`.
2. ~~**Qwen3 "pensar":** apagar el razonamiento con una variable~~ — no hizo falta: se usa `qwen3:4b-instruct`, que no razona.
3. **Post-proceso:** revisar las primeras respuestas de cada modelo. La reparación de citas y la detección de "no hay
   información" (`_quitar_meta_no_info`) están afinadas con las frases de Qwen2.5; otra redacción de la abstención
   puede pasar como respuesta normal (ya pasó con S0).
4. **Mismas condiciones para todos:** prompt `v3-completo`, `num_ctx` 8192, temperatura 0.2, semillas 42 y 7, timeout
   120 s, mismo banco. Antes de cada corrida, reiniciar `oe5-llm` para vaciar la caché de Ollama.
5. **Análisis:** `exp_b_generacion.py` ya acepta cualquier modelo (`qwen=… llama32=… qwen3=… gemma3=… s0=…`);
   3 comparaciones contra Qwen2.5-7B con Holm.

No cambia: el chatbot (sigue con Qwen2.5-7B), la recuperación, `docker-compose.yml` (ya acepta `OLLAMA_MODEL`),
`ablacion.ps1` ni los demás experimentos.
