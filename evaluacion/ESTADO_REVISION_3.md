# Estado de la Revisión 3 — dónde está el proyecto

Actualizado: **2026-11-22**. Documento guía: `docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx` (03-09-2026).
Este archivo resume en qué fase está el estudio, qué se hizo, qué salió y qué falta. El detalle de cada
pieza está en los archivos enlazados.

## 1. Fases del proyecto

| Fase | Fechas | Qué se hizo | Estado |
|---|---|---|---|
| Chatbot RAG (OE4/OE5) | jun–sep 2026 | Sistema completo: FastAPI + ChromaDB + Ollama + React, reglas M01–M08, registro | ✅ |
| Evaluación PARTE 3 y madurez OE8 (FASE 1–5) | sep 2026 | Ground truth v3.1 (17 Q), métricas de retrieval/generación, evaluación humana FASE 4, madurez automática | ✅ (corpus V2, histórico) |
| Corpus V3 del OE1 | 20–21 nov 2026 | Nuevo chunking (100 % del texto embebido) y cambio a bge-m3 | ✅ |
| Migración del chatbot y mejoras | 21–22 nov 2026 | V3 + bge-m3, calibración (umbral 0.41), contexto completo, prompt `v3-completo`, banco v3.2 | ✅ (`comparacion_v2_v3/COMPARACION_V2_V3.md`) |
| **Revisión 3: experimentos del .docx** | desde 22 nov 2026 | Configuración congelada, estadística, sistemas S0–S6, experimentos A/B/C preliminares, herramientas del gold set | 🟡 **fase actual** |

## 2. Fase actual: qué está hecho y qué falta

La configuración del chatbot está **congelada** en el commit `c47d455a` (`REPRODUCIBILIDAD.md`): todos los
experimentos se corren con ella y cualquier cambio posterior se registra allí.

| § del .docx | Estado | Archivo |
|---|---|---|
| 0 Hipótesis H1–H5 | ✅ aprobadas; criterio H5 ratificado (≥ 0.90 con IC95) | `banco/hipotesis.md`, `retrieval/criterio_h5.md` |
| 2 Corpus | ✅ V3 (48 docs, 5,117 chunks) + variantes de 150/300/600 tokens del OE1 | `REPRODUCIBILIDAD.md` |
| 3 Gold set 260 | 🟡 pool + fichas ciegas + κ + consolidación listos; **falta la anotación del equipo** y 40 preguntas fuera de dominio nuevas | `banco/gold/README.md` |
| 4 Sistemas | ✅ S0–S4 listos; S5 (Llama 3 8B) **descartado**; generadores nuevos S5b `llama3.2:3b`, S7 `qwen3:4b-instruct`, S8 `gemma3:4b` descargados el 2026-11-22 (§4) | `retrieval/matriz_sistemas.md` |
| 5A Recuperación | 🟡 preliminar: 4 recuperadores × 4 tamaños de chunk | `retrieval/README.md`, `retrieval/exp_a/` |
| 5B Generación | 🟡 preliminar: Qwen vs Llama 3 8B y S0; siguiente: modelos de 3–4B | `generacion/README.md`, `generacion/exp_b/` |
| 5C Abstención | 🟡 preliminar: 40/40 fuera de dominio (preguntas ya vistas), 14/20 ambiguas | `exp_c/README.md` |
| 7 Métricas | ✅ R@k, MRR, nDCG@5, atribución, completitud, abstención, latencia; ❌ fidelidad | — |
| 8 Evaluación humana | ❌ por hacer sobre el sistema final | `humana/README.md` |
| 9 Estadística | ✅ bootstrap IC95, Wilson, Wilcoxon, Holm, efecto, κ | `estadistica/README.md` |
| 10 Reproducibilidad | ✅ | `REPRODUCIBILIDAD.md` |
| 11 Tablas y figuras | ❌ (hay datos preliminares para Tabla 2 y Figura 1) | `retrieval/exp_a/h2_*` |

## 3. Resultados preliminares

Todos con bancos de desarrollo (154 preguntas del OE1 sin revisión humana y banco v3.2 de 30). **No son los
resultados oficiales**: el .docx exige el gold set de 260, porque con bancos chicos las diferencias pueden no
sostenerse (ya pasó: con 30 preguntas la ventaja de bge-m3 sobre BM25 no sobrevive a Holm).

**H1 — recuperadores (R@5, artículo correcto entre los 5 primeros; 154 Q, chunks de producción):**

| BM25 | MiniLM | mpnet | bge-m3 |
|---|---|---|---|
| 0.675 | 0.526 | 0.617 | **0.916** |

Solo bge-m3 supera a BM25 (+0.24 [0.16, 0.32], p Holm < 0.001). mpnet empata y MiniLM es peor: ambos leen solo
128 tokens y dejan sin leer el 44 % del texto.

**H2 — tamaño de chunk (R@5, 154 Q):** bge-m3 0.903 / 0.929 / 0.909 con 150 / 300 / 600 tokens; mpnet también
máximo en 300. Ninguna diferencia es significativa. BM25 mejora con chunks grandes (600 vs 150: +0.078, p 0.02).

**H3 — generadores (banco v3.2, misma recuperación y prompt):**

| Sistema | Completitud | Atribución exacta | Latencia p50 / p95 | Timeouts | Negativas |
|---|---|---|---|---|---|
| Qwen2.5-7B (vigente) | **0.53** | 0.42 | 20 s / 58 s | 0 % | 12/12 |
| Llama 3 8B | 0.39 | 0.40 | 39 s / 121 s | 17 % | 6/6 |
| S0 sin recuperación | 0.03 | 0.02 | 8 s / 23 s | 0 % | 11/12 |

**H4 — por categoría:** sin datos suficientes (requiere el gold set).

**H5 — abstención:** fuera de dominio 40/40 (IC95 Wilson [0.91, 1.00]) pero con preguntas usadas en la
calibración, así que no vale para la decisión; ambiguas 14/20, solo 4 piden aclaración.

## 4. Decisión del 2026-11-22: se descarta Llama 3 8B

**Qué:** el sistema S5 del .docx (Llama 3 8B) sale de la comparación de generadores. Se reemplaza por tres
modelos que caben en la GPU: `llama3.2:3b` (S5b, mantiene la familia Llama que pide el .docx), `qwen3:4b-instruct`
(S7, misma familia que el vigente pero más chico) y `gemma3:4b` (S8, otra familia, buena en español).
Qwen2.5-7B sigue como referencia (S6).

**Por qué (evidencia del Exp. B preliminar, `generacion/exp_b/`):**
1. **No cabe en el hardware del estudio.** Con la misma configuración que Qwen (`num_ctx` 8192) ocupa 7.3 GB; la
   RTX 4050 tiene 6 GB, de los que Ollama dispone de ~5 GB. Quedan 10 de sus 33 capas en CPU.
2. **Pierde respuestas por tiempo.** 17 % de timeouts (> 120 s) con la semilla 42; latencia p50 39 s vs 20 s.
3. **Se degrada con el uso.** La parte en CPU depende de la RAM de Docker (7.7 GB), que se agota con la caché de
   Ollama: la corrida con semilla 7 dio 27/30 timeouts y no se pudo usar.
4. **No compensa en calidad.** Completitud 0.39 vs 0.53 de Qwen (p Holm 0.03); en las preguntas que sí respondió,
   calidad parecida (0.47 vs 0.51), sin ventaja en atribución.
5. Bajar su contexto para que quepa cambiaría las condiciones de la comparación, que el .docx exige iguales.

**Cómo se reporta:** como "evaluado y descartado por inviabilidad en el hardware", con estos datos, no como
omitido. El .docx pide comparar "al menos" Qwen2.5-7B y Llama 3 8B, así que el cambio debe registrarlo el equipo
con el asesor. Las corridas de Llama 3 se conservan en `comparacion_v2_v3/E2E_B_llama_*`.

**Qué cambia en el estudio:** H3 pasa a comparar Qwen2.5-7B con tres modelos de 3–4B; la pregunta práctica es si un
modelo más chico que cabe entero en la GPU da una calidad parecida con menos latencia. Son 3 comparaciones contra
Qwen con Holm.

## 5. Próximos pasos

1. Instalar `llama3.2:3b`, `qwen3:4b-instruct` y `gemma3:4b` (≈ 2.0 / 2.5 / 3.3 GB) y adaptar lo necesario (ver
   `generacion/README.md`, "Modelos nuevos").
2. Exp. B preliminar con los cuatro generadores (banco v3.2, 2 semillas).
3. El equipo anota el gold set y redacta 40 preguntas fuera de dominio nuevas (`banco/gold/`).
4. Con el gold set: experimentos A, B y C oficiales.
5. Evaluación humana ciega de la fidelidad (sistema final y generadores del Exp. B).
6. Tablas 1–6 y figuras del artículo.
