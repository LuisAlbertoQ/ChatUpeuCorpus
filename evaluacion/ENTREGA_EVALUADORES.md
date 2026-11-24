# Qué entregar a los evaluadores — Revisión 3

Actualizado: **2026-11-23** (con generador de fichas de fidelidad). Este archivo dice exactamente qué archivos recibe cada persona, qué hace con ellos y
qué devuelve. Hay **dos rondas de trabajo humano** en el .docx; la segunda depende de la primera.

## Ronda 1 — Gold set de 260 preguntas (.docx §3) · ahora

Sin esta ronda no se pueden correr los experimentos A, B y C oficiales.

| Rol | Quién | Recibe (carpeta `evaluacion/banco/`) | Hace | Devuelve |
|---|---|---|---|---|
| **Anotador A** | Integrante del equipo que conozca los reglamentos | `gold/ficha_anotador_A.xlsx` + `guia_anotacion.md` | Para cada una de las 260 preguntas: tipo, documento y artículo(s) donde está la respuesta, categoría, respuesta de referencia, puntos clave (separados por `;`) y confianza | `ficha_anotador_A_<iniciales>.xlsx` |
| **Anotador B** | Otra persona, **sin ver** la ficha de A | `gold/ficha_anotador_B.xlsx` + `guia_anotacion.md` | Lo mismo que A, por su cuenta | `ficha_anotador_B_<iniciales>.xlsx` |
| **Redactor fuera de dominio** | Alguien que **no haya usado ni visto** el chatbot | `gold/plantilla_ood_nuevas.xlsx` + §2 de `guia_anotacion.md` | Escribe 40 preguntas que el chatbot NO debe responder: 20 lejanas (clima, fútbol…) y 20 cercanas al dominio pero sin respuesta en los reglamentos | `plantilla_ood_nuevas.xlsx` completa |
| **Juez (tercer evaluador)** | Docente o asesor | *Después*: `gold/conflictos_para_juez.xlsx` (lo genero yo cuando A y B entregan) | Decide solo las preguntas en que A y B no coinciden | `conflictos_para_juez.xlsx` completo |

**Antes de repartir:** abrir una ficha en Excel y comprobar que las listas desplegables (amarillas) funcionan, porque
se generaron sin Excel. Los anotadores necesitan acceso a los 48 PDF del corpus (carpeta del OE1) para buscar el
artículo.

**Qué hago yo cuando devuelven:**
1. `acuerdo_gold.py kappa` → revisa errores, calcula el acuerdo (κ; mínimo κ documento ≥ 0.80, κ tipo ≥ 0.75) y arma
   la ficha de conflictos para el juez.
2. `acuerdo_gold.py consolidar` → `banco/banco_gold_260.json`, verificado contra el corpus V3.
3. Corro los experimentos A, B y C oficiales con ese banco.

Detalle técnico: `banco/gold/README.md`. Reglas: `banco/guia_anotacion.md`.

## Ronda 2 — Evaluación humana de la fidelidad (.docx §8) · después de los experimentos oficiales

Mide lo que ninguna métrica automática mide: si lo que dice cada respuesta está realmente en los documentos citados.
Es la que decide el generador final (ver "Modelo del chatbot" en `ESTADO_REVISION_3.md`).

| Rol | Quién | Recibe | Hace | Devuelve |
|---|---|---|---|---|
| **Evaluadores 1 y 2** | Dos personas, por separado (pueden ser A y B) | `ficha_fidelidad_E1.xlsx` / `_E2.xlsx` (respuestas **ciegas**, sin decir qué modelo las escribió, con la hoja "Fuentes") + `humana/RUBRICA_FIDELIDAD_REV3.md` | Por cada respuesta: fidelidad 0–2 (¿está en las fuentes?), corrección 0–2, atribución (exacta/parcial/incorrecta/ausente) y relevancia 1–5 | Fichas completas con sus iniciales |

El generador ya está listo (`humana/fichas_fidelidad.py`) y la rúbrica fijada (`humana/RUBRICA_FIDELIDAD_REV3.md`).
Las fichas oficiales se generan cuando estén las corridas del Exp. B (Qwen2.5-7B, `llama3.2:3b`, `qwen3:4b-instruct`,
`gemma3:4b`) sobre el gold set: 50 preguntas × 4 modelos = 200 respuestas por evaluador. Para ver cómo se verán:
`humana/fidelidad_rev3/prueba_banco_v32/ficha_fidelidad_E1.xlsx` (prueba, no se entrega).

Entregables de la ronda 2: `ficha_fidelidad_E1.xlsx` al evaluador 1 y `ficha_fidelidad_E2.xlsx` al evaluador 2, más
la rúbrica. **Nunca** entregar `clave_NO_ENTREGAR.json`. Devuelven `ficha_fidelidad_E1_<INICIALES>.xlsx` y `_E2_…`.

## Resumen de lo que falta del .docx

| Falta | Depende de | Quién |
|---|---|---|
| Anotación del gold set + 40 fuera de dominio nuevas | — | **Equipo (ronda 1)** |
| κ, consolidación, experimentos A/B/C oficiales | Ronda 1 | Yo |
| Evaluación humana de fidelidad | Exp. B oficial | **Equipo (ronda 2)** |
| Decisión final del generador del chatbot | Ronda 2 | Equipo con el asesor |
| Tablas 1–6 y figuras | Todo lo anterior | Yo |
