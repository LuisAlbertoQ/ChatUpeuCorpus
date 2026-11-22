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

> **Actualización 2026-11-21/22 (corpus V3 + bge-m3, umbral 0.41):** las 6 negativas N01–N06 se abstienen
> con todas las configuraciones probadas (2 semillas cada una); en la calibración, 42 negativas simuladas
> (8 del OE1 cercanas al dominio + 34 OOD del pool) dan 100 % de abstención. Sigue siendo una muestra
> pequeña: la decisión oficial requiere las 40 OOD + 20 ambiguas del gold set con IC95 %.

> **Experimento C preliminar (2026-11-22, `../exp_c/`):** 40/40 fuera de dominio (IC95 Wilson [0.912, 1.00]) y
> 14/20 ambiguas (solo 4 piden aclaración, 6 reciben respuesta). Las 40 del pool ya se vieron en el desarrollo
> (calibración + N01–N06), así que no sirven para la decisión oficial: el gold set necesita 40 nuevas.

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
