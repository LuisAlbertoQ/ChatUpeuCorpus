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
| S0 | Sin recuperación | Qwen2.5-7B | Control: generación local sin contexto RAG | pendiente |
| S1 | BM25 (`retrieval/bm25_local.py`) | Qwen2.5-7B | Línea base léxica | pendiente (implementar) |
| S2 | MiniLM-L12-v2 | Qwen2.5-7B | Recuperación semántica local | comparativa previa hecha, falta réplica controlada |
| S3 | mpnet-base-v2 | Qwen2.5-7B | Configuración anterior / referencia | operativo hasta 2026-11-21 (V2); réplica de control `EXP_20261122_000124_31a0b8` idéntica al baseline de septiembre |
| S4 | bge-m3 | Qwen2.5-7B | **Configuración vigente** (corpus V3, umbral 0.41, boost 0.02) | operativo desde 2026-11-21; comparado con S3 en 17 Q y 30 Q (`comparacion_v2_v3/`); falta sobre el gold set |
| S5 | Mejor recuperador del Exp. A | Llama 3 8B | Comparación de generación local | pendiente (`ollama pull llama3:8b`) |
| S6 | Mejor recuperador del Exp. A | Qwen2.5-7B | Comparación de generación local | pendiente (réplica controlada) |

## Notas

- Si alguna herramienta local cambia durante el desarrollo, se documenta
  como cambio de implementación, no como comparación local-vs-nube.
- Exp. A usa S0–S4; Exp. B usa S5–S6 con el ganador de A.
