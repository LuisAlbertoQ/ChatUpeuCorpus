# Comparación de Modelos LLM: Llama 3 8B vs Qwen2.5-7B

**Fecha:** Junio 2026
**Propósito:** Evaluar ambos modelos como generadores de respuesta en el pipeline
RAG del chatbot UPeU (corpus de 48 PDFs, 3886 chunks, modelo de embeddings
`paraphrase-multilingual-mpnet-base-v2`).

---

## Metodología

- **10 preguntas** de prueba que cubren las 5 categorías del corpus (A–E, 2 cada una).
- **Misma sesión de recuperación** para ambos modelos (ChromaDB query con
  `top_k_raw=15`, re-ranking por keywords, `TOP_K_FRAGMENTOS=5`).
- Evaluación cuantitativa: cobertura M02/M04, tiempo de respuesta, distancias.
- Evaluación cualitativa: revisión manual de la calidad de las respuestas,
  seguimiento del PROMPT v2 (8 reglas), precisión de citas.
- Llama 3 8B (`llama3:latest`, 4.7 GB) y Qwen2.5-7B (`qwen2.5:7b`, 4.7 GB),
  ambos servidos por Ollama con CUDA v13 en RTX 4050 (6 GB VRAM).

---

## Resultados cuantitativos

| Métrica | Llama 3 8B | Qwen2.5-7B | Diferencia |
|---|---|---|---|
| **Cobertura M02** | 10/10 (100%) | 9/10 (90%) | Llama 3 +1 |
| **M04 (sin cobertura)** | 0/10 | 1/10 | Llama 3 mejor |
| **Tiempo promedio** | **24.04 s** | **8.94 s** | **Qwen 2.7× más rápido** |
| Tiempo mínimo | 15.33 s | 2.73 s | Qwen más rápido |
| Tiempo máximo | 35.94 s | 17.35 s | Qwen más rápido |
| Distancia promedio | 0.2532 | 0.2532 | Idéntico (mismo retrieval) |
| Fuentes totales | 50 | 50 | Idéntico |

### Distribución de tiempos por pregunta

| Pregunta | Llama 3 | Qwen2.5 | Ganador |
|---|---|---|---|
| Q01: Autoridades universitarias | 22.34s | **11.39s** | Qwen |
| Q02: Elección rector/vicerrectores | 15.33s | **10.29s** | Qwen |
| Q03: Título profesional | 26.88s | **8.37s** | Qwen |
| Q04: Matrícula | 35.94s | **2.73s** (M04) | Qwen (rápido, pero sin respuesta) |
| Q05: Proyecto de tesis | 24.18s | **17.35s** | Qwen |
| Q06: Publicación científica | 25.12s | **10.72s** | Qwen |
| Q07: Becas | 31.35s | **3.71s** | Qwen |
| Q08: Sanciones estudiantes | 20.80s | **12.51s** | Qwen |
| Q09: Política trabajo digno | 18.33s | **7.70s** | Qwen |
| Q10: Auditoría interna | 20.17s | **4.61s** | Qwen |

---

## Análisis cualitativo

### Estructura de respuestas

Ambos modelos siguen el PROMPT v2 (lista vertical con guiones, citas por viñeta,
sin bloque "Fuentes:" final). Sin embargo:

| Criterio | Llama 3 8B | Qwen2.5-7B |
|---|---|---|
| Citas con artículo | ✅ Generalmente presente | ✅ Siempre presente |
| Precisión de artículo citado | ⚠️ A veces usa artículo incorrecto | ✅ Más preciso |
| Formato de viñetas | ✅ Markdown correcto | ✅ Markdown correcto |
| Meta-frases técnicas | ✅ Post-procesado las elimina | ✅ Post-procesado las elimina |
| Concisión | ⚠️ Tiende a ser verboso | ✅ Más conciso |

### Ejemplos de respuestas comparadas

#### Q02: "¿Cómo se eligen el rector y vicerrectores?"

**Llama 3** (M02, 15.33s):
> - La elección para Rector y Vicerrector Académico se realiza por voto directo, personal y a mano a...

**Qwen2.5** (M02, 10.29s):
> - La elección para Rector, Vicerrector Académico, Decanos y Director de la Escuela de Posgrado se realiza por voto...

**Veredicto:** Qwen es más detallado (incluye Decanos y Director de Posgrado), con mejor cita al artículo.

#### Q03: "¿Cuáles son los requisitos para obtener el título profesional?"

**Llama 3** (M02, 26.88s):
> - Requisito específico de ingreso: ejercicio y experiencia laboral, mínimo de tres (03) años como...

**Qwen2.5** (M02, 8.37s):
> - Haber abonado el grado de estudios respectivo. (Artículo 42°, 42.2.)
> - Evidenciar, antes de sus...

**Veredicto:** La respuesta de Qwen corresponde al Reglamento de Grados y Títulos
(categoría E), mientras que Llama 3 parece haber confundido el documento
(habla de "experiencia laboral" que corresponde a requisitos docentes, no a
titulación). **Qwen gana claramente en precisión.**

#### Q04: "¿Cómo me matriculo en la UPeU?" (caso límite)

**Llama 3** (M02, 35.94s):
> - Para matricularse en la Universidad Peruana Unión (UPeU), es necesario ser registrado como estudi...

**Qwen2.5** (M04, 2.73s):
> No encontré información suficiente...

**Análisis:** Ambos recuperaron los mismos 5 chunks con d=0.27, pero Qwen
determinó que la información era insuficiente para responder y su respuesta
fue reemplazada por M04 (post-procesado). Llama 3 fue más "confiado" y dio una
respuesta genérica. Dependiendo del estándar de calidad, la honestidad de Qwen
puede ser preferible.

#### Q07: "¿Qué becas ofrece la universidad?"

**Llama 3** (M02, 31.35s):
> - La Universidad Peruana Unión (UPeU) otorga las siguientes becas:
>    + Beca parcial que financia el...

**Qwen2.5** (M02, 3.71s):
> - Beca parcial (ESTATUTO 2024, Artículo 43°1.)
> - Beca total (ESTATUTO 2024, Artículo 43°2.)

**Veredicto:** Qwen es más estructurado y cita artículos específicos. Llama 3
es más descriptivo pero no cita números de artículo. **Qwen gana en trazabilidad.**

---

## Tabla resumen de calidad

| Pregunta | Llama 3 | Qwen2.5 | Ganador |
|---|---|---|---|
| Q01: Autoridades | Regular | ✅ Bueno | Qwen |
| Q02: Elección autoridades | ✅ Bueno | ✅ Excelente (más detallado) | Qwen |
| Q03: Título profesional | ⚠️ Incorrecto (habla de docentes) | ✅ Correcto | **Qwen** |
| Q04: Matrícula | ✅ Respondió (genérico) | ⚠️ M04 (honesto) | Llama 3 |
| Q05: Proyecto tesis | ✅ Bueno | ✅ Bueno | Empate |
| Q06: Publicación científica | ⚠️ Impreciso | ✅ Bueno | Qwen |
| Q07: Becas | ✅ Bueno | ✅ Excelente (con artículos) | **Qwen** |
| Q08: Sanciones | ✅ Bueno | ✅ Bueno | Empate |
| Q09: Trabajo digno | ✅ Bueno | ✅ Bueno (con cita) | Empate |
| Q10: Auditoría interna | ✅ Bueno | ✅ Bueno | Empate |

---

## Consumo de recursos

| Recurso | Llama 3 8B | Qwen2.5-7B |
|---|---|---|
| Tamaño en disco (Q4) | 4.7 GB | 4.7 GB |
| VRAM estimada (RTX 4050) | ~4.5 GB | ~4.5 GB |
| Velocidad de generación | ~15 tok/s | ~25 tok/s |
| Licencia | Comunitaria Meta | **Apache 2.0** |

---

## Veredicto final

| Dimensión | Ganador |
|---|---|
| **Velocidad** | **Qwen2.5-7B** (2.7× más rápido) |
| **Precisión de respuestas** | **Qwen2.5-7B** (menos errores de documento) |
| **Cobertura (M02)** | Llama 3 8B (10/10 vs 9/10) |
| **Formato y citas** | **Qwen2.5-7B** (citas más precisas) |
| **Licencia** | **Qwen2.5-7B** (Apache 2.0 vs Comunitaria) |
| **Conservadurismo** | Qwen2.5-7B (más honesto, M04 cuando no sabe) |
| **Contexto máximo** | **Qwen2.5-7B** (128K vs 8K tokens) |

### Recomendación: Qwen2.5-7B

Aunque Llama 3 empató en cobertura (10/10 vs 9/10), Qwen2.5 es **superior en
los aspectos que más importan** para un chatbot RAG en producción:

1. **Velocidad**: 8.94s promedio vs 24.04s de Llama 3. En modo piloto (OE8),
   la diferencia es notable para la experiencia de usuario.

2. **Precisión**: En Q03 (título profesional), Llama 3 confundió el documento
   y respondió con requisitos de docentes. Qwen no cometió ese error.

3. **Citas**: Qwen cita consistentemente números de artículo específicos,
   mientras que Llama 3 es más vago.

4. **Licencia**: Apache 2.0 (Qwen) vs licencia comunitaria (Llama 3) — sin
   restricciones de uso comercial o distribución.

5. **Contexto**: 128K tokens de Qwen permite en el futuro aumentar el número
   de chunks en el prompt sin preocuparse por el límite de `n_ctx=4096`.

El único punto débil es Q04 (matrícula), donde Qwen fue honesto (M04) mientras
Llama 3 respondió. Esto se debe a que el corpus no tiene un documento
específico de "Reglamento de Matrícula" — la mejora está en el corpus, no en
el modelo.

---

## Decisión

**Se adopta Qwen2.5-7B** como modelo LLM por defecto del chatbot UPeU.

---

*Generado automáticamente a partir de `evaluacion/resultados_llama3.json`
y `evaluacion/resultados_qwen.json`.*
