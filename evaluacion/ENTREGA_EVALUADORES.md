# Qué entregar a los evaluadores — Revisión 3

Actualizado: **2026-11-23**. Este archivo dice exactamente qué archivos recibe cada persona, qué hace con ellos y
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
| **Evaluadores 1 y 2** | Dos personas, por separado (pueden ser A y B) | Fichas **ciegas** con una submuestra de respuestas (no dicen qué modelo las escribió) + los fragmentos citados + `humana/GUIA_EVALUACION_HUMANA_V3.md` | Por cada afirmación: ¿está en la fuente? ¿la cita es correcta? ¿cubre los puntos clave? | Fichas completas |

Estas fichas **todavía no existen**: se generan cuando estén las corridas oficiales del Exp. B (Qwen2.5-7B,
`llama3.2:3b`, `qwen3:4b-instruct`, `gemma3:4b`) sobre el gold set. La rúbrica se fija antes de ver los resultados.

## Resumen de lo que falta del .docx

| Falta | Depende de | Quién |
|---|---|---|
| Anotación del gold set + 40 fuera de dominio nuevas | — | **Equipo (ronda 1)** |
| κ, consolidación, experimentos A/B/C oficiales | Ronda 1 | Yo |
| Evaluación humana de fidelidad | Exp. B oficial | **Equipo (ronda 2)** |
| Decisión final del generador del chatbot | Ronda 2 | Equipo con el asesor |
| Tablas 1–6 y figuras | Todo lo anterior | Yo |
