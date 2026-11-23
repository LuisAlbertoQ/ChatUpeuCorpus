# Matriz de sistemas comparados — Revisión 3 (RAG 100 % local)

Fuente: `docs/Revisión_3_Actualizada_RAG_Local_UpeU.docx`, §4 y Tabla 2.
Todos los sistemas son locales. No existe comparador cloud/no-code
(n8n, Qdrant, OpenAI/GPT quedan excluidos por decisión metodológica).

## Variables de control (constantes en toda comparación)

- corpus: `corpus_upeu_v2` (48 docs, 5126 chunks; ver `auditoria_corpus_*.md`) — **actualización 2026-11-21:** el chatbot usa ahora
  `corpus_upeu_v3_bgem3` (48 docs, 5117 chunks, OE1 V3). Para el experimento A todos los sistemas deben
  compararse sobre el **mismo** corpus; la V2 queda en `vector_store_backup_v2_20261121/` para S3 si se requiere.
- gold set: `banco_gold_260.json` (pendiente; semilla actual: **banco v3.2 = 30 + 6**, `banco/banco_v32.json`)
- prompt: v2-adaptativo hasta 2026-11-21; **v3-completo vigente desde 2026-11-22** (mismas reglas M01–M08). Fijar uno para todo el experimento
- al comparar UN componente, los demás permanecen fijos

## Sistemas

| ID | Recuperador | Generador | Rol | Estado |
|---|---|---|---|---|
| S0 | Sin recuperación | Qwen2.5-7B | Control: generación local sin contexto RAG | **implementado y corrido 2026-11-22** (banco v3.2): completitud 0.03 vs 0.53 con RAG |
| S1 | BM25 (`retrieval/exp_a_recuperacion.py`, k1 1.5, b 0.75) | Qwen2.5-7B | Línea base léxica | **recuperación implementada 2026-11-22**; preliminar R@5 0.675 (154 Q OE1) |
| S2 | MiniLM-L12-v2 | Qwen2.5-7B | Recuperación semántica local | **recuperación evaluada 2026-11-22** (revisión `e8f8c211…`); preliminar R@5 0.526 (154 Q OE1), peor que BM25; lee el 56 % del texto (128 tokens) |
| S3 | mpnet-base-v2 | Qwen2.5-7B | Configuración anterior / referencia | operativo hasta 2026-11-21 (V2); réplica de control `EXP_20261122_000124_31a0b8` idéntica al baseline de septiembre; sobre los chunks V3: R@5 0.617 (154 Q), lee el 56 % del texto (128 tokens) |
| S4 | bge-m3 | Qwen2.5-7B | **Configuración vigente** (corpus V3, umbral 0.41, boost 0.02) | operativo desde 2026-11-21; comparado con S3 en 17 Q y 30 Q (`comparacion_v2_v3/`); falta sobre el gold set |
| ~~S5~~ | Mejor recuperador del Exp. A | Llama 3 8B | Comparación de generación local | **descartado 2026-11-22** por inviabilidad en el hardware: no cabe en la GPU de 6 GB (10/33 capas en CPU), 17 % de timeouts, se degrada con el uso; completitud 0.39 vs 0.53 de Qwen. Aprobado por el asesor el 2026-11-23. Ver `../ESTADO_REVISION_3.md` §4 |
| S5b | Mejor recuperador del Exp. A (bge-m3) | Llama 3.2 3B (`llama3.2:3b`) | Familia Llama que cabe en la GPU | descargado 2026-11-22 (ID `a80c4f17acd5`); 100 % en GPU. Exp. B preliminar: completitud 0.51, p50 7 s |
| S7 | Mejor recuperador del Exp. A (bge-m3) | Qwen3 4B Instruct (`qwen3:4b-instruct`) | Misma familia que S6, más chico | descargado 2026-11-22 (ID `0edcdef34593`); 90 % en GPU. (`qwen3:4b` se descartó: es la variante de razonamiento). Exp. B preliminar: completitud 0.63, p50 22 s / p95 26 s |
| S8 | Mejor recuperador del Exp. A (bge-m3) | Gemma 3 4B (`gemma3:4b`) | Otra familia, multilingüe | descargado 2026-11-22 (ID `68ceab7e468a`); 79 % en GPU. Exp. B preliminar: completitud 0.58, p50 17 s |
| S6 | Mejor recuperador del Exp. A | Qwen2.5-7B | Comparación de generación local | referencia del Exp. B preliminar (completitud 0.53, p50 20 s); falta sobre el gold set |

## Notas

- Si alguna herramienta local cambia durante el desarrollo, se documenta
  como cambio de implementación, no como comparación local-vs-nube.
- Exp. A usa S0–S4; Exp. B usa S6 (Qwen2.5-7B, referencia) contra S5b, S7 y S8 con el ganador de A (bge-m3), más S0 como control. S5 (Llama 3 8B) se reporta como descartado.

- 2026-11-22: configuración congelada en `../REPRODUCIBILIDAD.md` (commit `c47d455a`). Resultados preliminares del Exp. A en `exp_a/` (ver README de esta carpeta).
- 2026-11-22: Exp. A preliminar con chunks de 150/300/350/600 tokens (OE1): sin tamaño óptimo significativo para los modelos semánticos (`analisis_h2.py`).
