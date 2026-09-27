# Ground Truth Múltiple — Decisión de Representación

**Fecha:** 2026-08-14 (Fase 1, Parte 3)
**Contexto:** Preguntas `MULTI_CHUNK` y `MULTI_DOCUMENTO` requieren múltiples elementos relevantes.

## Opciones evaluadas

| Opción | Pros | Contras |
|---|---|---|
| **A. JSON TEXT en columnas existentes** (`documento_esperado` como `'["DOC A","DOC B"]'`) | Sin JOIN, compatible con SQLite, preserva fila única por pregunta | Rompe tipo TEXT simple, requiere `json.loads` en lectura |
| **B. Tabla secundaria** `banco_preguntas_documentos (pregunta_id, documento)` | Normalizado, queries relacionales | JOIN adicional, 2 tablas, más complejo para 17 preguntas |

## Decisión

**Opción A con columnas nuevas JSON para múltiples:**

- Mantener columnas singulares (`documento_esperado`, `articulo_esperado`, etc.) para compatibilidad con código y reportes existentes que esperan string único.
- Añadir columnas nuevas `documentos_esperados`, `articulos_esperados`, `chunks_esperados`, `secciones_esperadas`, `paginas_esperadas` como **JSON TEXT** (`json.dumps([...], ensure_ascii=False)`).
- Para preguntas con un solo relevante, ambas representaciones coexisten: singular con string, plural con array de 1 elemento (ej. `documento_esperado="REGLAMENTO X"`, `documentos_esperados='["REGLAMENTO X"]'`).
- Para `MULTI_*`, la columna plural contiene array completo; la singular queda con el primero por compatibilidad o `NULL` con nota.

**Justificación:** 17 preguntas, máximo 2-3 relevantes por pregunta, sin necesidad de queries relacionales complejas. JSON mantiene una fila por pregunta, simple de sincronizar idempotentemente via `id`, y facilita `evaluacion_retrieval` al permitir múltiples filas por `pregunta_id`/`experimento_id` sin duplicar banco.

## Estado actual

- 17 preguntas migradas con `documento_esperado` singular y `documentos_esperados` como JSON array de 1 elemento.
- Campos no verificables (`tipo_pregunta`, `cobertura_esperada` para 17) quedan `NULL` hasta curación manual reportada en `preguntas_pendientes_curacion.md` (próximo).
- Segunda ejecución de `sincronizar_banco.py` → 0 insertadas, 17 actualizadas, total 25 (8 históricas P + 17 Q), idempotente.
