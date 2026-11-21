# Guía de Anotación — Gold Set 260 (v3.1)

**Versión:** 1.0 | **Fecha:** 2026-09-27 | **Proyecto:** RAG 100 % Local UPeU (OE8)

---

## 1. Propósito

Construir **Gold Set 260** (v3.1) para evaluación experimental RAG 100 % local UPeU.
Este documento define los criterios de anotación para que **dos anotadores independientes**
clasifiquen 260 preguntas (200 dominio + 40 fuera de dominio + 20 ambiguas).

**Objetivo:** `banco_gold_260.json` + tabla `banco_gold` (66 actuales + 237 nuevos = 260).

---

## 1. Alcance y organización

| Subconjunto | Nº | Fuente sugerida |
|---|---|---|
| **Dentro de dominio** (ANSWERABLE) | 200 | Banco v3.1 (17) + nuevos de reglamentos, estatutos, TUPA, becas, investigación, admisión, posgrado, bienestar, gobierno |
| **Fuera de dominio** (NO_ANSWER) | 40 | Consultas externas a UPeU (precios, clima, recetas, licencias, deportes, trámites ajenos) |
| **Ambiguas / Multi-intención** | 20 | Preguntas con ≥2 intenciones, sin entidad clara, o que requieren desambiguación |

**Total: 260** = 200 + 40 + 20.

---

## 2. Tipos de pregunta (mutuamente excluyentes)

| Código | Etiqueta | Definición operativa | Ejemplo |
|---|---|---|---|
| **DIRECTA** | Respuesta factual única, basada en un artículo/sección específico | "¿Cuál es el artículo 42 del Reglamento de Becas?" |
| **REQUISITOS** | Lista de condiciones/requisitos para un trámite/beneficio | "¿Qué requisitos necesito para la beca de excelencia?" |
| **PROCEDIMIENTO** | Pasos, oficinas, plazos, documentos para un trámite | "¿Cómo solicito una constancia de estudios?" |
| **SIN_COBERTURA** | Pregunta sobre tema que **no existe** en el corpus (fuera de dominio) | "¿Cuál es el precio de una laptop en Lima?" |
| **AMBIGUA** | Pregunta con ≥2 intenciones plausibles, entidad ausente, o necesita desambiguación | "¿Qué dice el estatuto sobre el rector y la matrícula?" (dos temas) |

> **Regla de oro:** una pregunta = **un solo código**. Si duda, consultar al tercer evaluador.

---

## 3. Formato de salida obligatorio

Cada anotador entrega **un JSON Lines** (`.jsonl`) con 260 líneas, una por pregunta.
Nombre de archivo: `anotador_{iniciales}_{YYYYMMDD}.jsonl`

```json
{
  "pregunta_id": "GOLD_001",
  "texto": "¿Cómo solicito una constancia de estudios?",
  "tipo": "PROCEDIMIENTO",
  "documento_esperado": "TUPA V6 2023 UPeU",
  "articulo_esperado": "Artículo 114°",
  "categoria": "B",
  "anotador": "LAL",
  "fecha": "2026-09-28",
  "notas": "Opcional: ambigüedad detectada, decisión tomada"
}
```

**Campos obligatorios:**
| Campo | Tipo | Requerido |
|---|---|---|
| `pregunta_id` | string (GOLD_NNN) | Sí |
| `texto` | string | Sí |
| `tipo` | enum[DIRECTA, REQUISITOS, PROCEDIMIENTO, SIN_COBERTURA, AMBIGUA] | Sí |
| `documento_esperado` | string (vacío si SIN_COBERTURA) | Sí |
| `articulo_esperado` | string (vacío si no aplica / SIN_COBERTURA) | Sí |
| `categoria` | A–E | Sí |
| `anotador` | string (iniciales) | Sí |
| `fecha` | YYYY-MM-DD | Sí |
| `notas` | string (opcional) | No |

---

## 3. Flujo de trabajo

1. **Recibir** el pool de 260 preguntas en bruto (`pool_260_preliminar.jsonl` — se entrega aparte).
   El archivo trae **solo** `pregunta_id` y `texto`, en orden mezclado: no incluye
   bloque, tema, tipo, documento, artículo ni puntos candidatos. Cada anotador debe
   asignar por su cuenta `tipo`, `documento_esperado`, `articulo_esperado` y
   `categoria`, consultando los PDF del corpus.
2. **Anotar independientemente** (sin consultar al otro anotador).
3. Entregar archivo `anotador_{INICIALES}_{YYYYMMDD}.jsonl`.
4. **Reunión de consenso** (tercer evaluador resuelve conflictos → `banco_gold_260.json`).
5. **Acuerdo interanotador**: calcular κ de Cohen por documento y por tipo.

---

## 5. Criterios de decisión (casos frontera)

| Situación | Decisión |
|---|---|
| Pregunta menciona dos trámites distintos | **AMBIGUA** (dos intenciones) |
| Pregunta cita artículo pero pide procedimiento | **PROCEDIMIENTO** (la intención es "cómo") |
| Pregunta cita artículo y pide requisitos | **REQUISITOS** (la intención es "qué necesito") |
| Pregunta sobre tema no regulado en UPeU | **SIN_COBERTURA** |
| Pregunta con pronombres ambiguos ("¿qué dice el artículo 10 sobre eso?") | **AMBIGUA** (entidad no resuelta) |
| Pregunta sobre norma que sí existe pero en otro documento | **SIN_COBERTURA** si el doc no está en corpus |

---

## 5. Entregables

| Archivo | Formato | Quién |
|---|---|---|
| `anotador_{INICIALES}_{YYYYMMDD}.jsonl` | JSONL (260 líneas) | Cada anotador |
| `acuerdo_anotadores.csv` | CSV (pregunta_id, anotador1, anotador2, juez, decisión_final) | Tercer evaluador |
| `banco_gold_260.json` | JSON (260 objetos consolidados) | Resultado final |
| `acuerdo_anotadores.csv` | κ documento, κ tipo | Auditoría |

---

## 6. Control de calidad

- **κ documento ≥ 0.80** y **κ tipo ≥ 0.75** → aceptable.
- Si κ < umbral → tercera ronda de discusión + re-entrenamiento con ejemplos de conflicto.
- **No se imputan** valores faltantes; se discuten en consenso.

---

## 7. Checklist final (antes de entregar)

- [ ] 260 líneas exactas en JSONL
- [ ] Todos los `pregunta_id` únicos (GOLD_001 a GOLD_260)
- [ ] Todos los `tipo` válidos (5 categorías)
- [ ] `documento_esperado` coherente con corpus v3.1
- [ ] `articulo_esperado` vacío solo si `tipo == "SIN_COBERTURA"`
- [ ] `categoria` en A–E
- [ ] `anotador` = iniciales del evaluador
- [ ] `fecha` = YYYY-MM-DD
- [ ] Sin duplicados de `pregunta_id`

---

**Fin de guía.** Cualquier duda → tercer evaluador (E. Tocto).
---
*Generado: 2026-09-27 | v1.0 | OE8 FASE 6 — Gold Set 260*