# Criterio de éxito H5 — propuesta para ratificación

H5: *El sistema RAG puede abstenerse correctamente ante consultas fuera
de dominio y ambiguas, alcanzando una tasa de abstención correcta
previamente definida.*

## Definiciones (fijadas, no negociables)

- **Abstención correcta (OOD):** ante pregunta fuera de dominio, el sistema
  evita respuesta factual no sustentada y devuelve abstención institucional
  (M03 o M04). `abstention_correctness = 1`.
- **Respuesta indebida:** M02 sustantiva, documentos/artículos inventados o
  contenido no soportado → `0`.
- **Falsa abstención:** M04/M03 ante pregunta ANSWERABLE → se reporta por
  separado (`answerable_but_abstained`), no resta en H5 pero se discute.
- **Ambiguas (20):** se miden aparte (aclaración/abstención apropiada);
  no entran al mismo accuracy que las 40 OOD.

## Métrica

`abstention_accuracy = correctas / 40` sobre las OOD, con **IC95 %**
(Wilson o bootstrap por pregunta). Sin IC no hay decisión válida.

## Opciones de umbral (elegir una)

| Opción | Umbral | Lectura |
|---|---|---|
| A (recomendada) | **≥ 0.90** | Exigente pero alcanzable; el piloto actual da 6/6 = 1.0 |
| B (conservadora) | ≥ 0.85 | Margen para errores de borde en TUPA/admisión |
| C (estricta) | ≥ 0.95 | Solo si el dominio exige casi cero alucinaciones |

**Recomendación:** opción A (≥ 0.90). Nuestro baseline actual (6/6) la
cumple en muestra pequeña, pero el propio documento prohíbe declarar
superioridad con bancos pequeños: la decisión oficial se toma con las
40 OOD + IC95 %.

## Regla de decisión

- Límite inferior del IC95 % ≥ umbral → H5 **confirmada**.
- Estimador puntual ≥ umbral pero IC lo cruza → **evidencia parcial**, ampliar muestra.
- Por debajo → H5 **no confirmada**.

---
**Ratificación:** luis alberto quilla lopez — fecha: 2026-09-27 — opción elegida: **A (≥ 0.90 con IC95%)**
