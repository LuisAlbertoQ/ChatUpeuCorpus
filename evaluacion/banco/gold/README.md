# Gold set 260 — fichas de anotación, acuerdo y consolidación (Revisión 3, §3)

Preparado el 2026-11-22. Las reglas de anotación están en `../guia_anotacion.md`.

## Archivos para el equipo

| Archivo | Para quién | Qué hace |
|---|---|---|
| `ficha_anotador_A.xlsx` | Anotador A | 260 preguntas ciegas (solo ID y texto); columnas amarillas con listas desplegables (tipo, los 48 documentos del corpus V3, categoría, confianza) |
| `ficha_anotador_B.xlsx` | Anotador B | La misma ficha; se trabaja sin ver la de A |
| `plantilla_ood_nuevas.xlsx` | Una persona que no haya visto el sistema | 40 preguntas fuera de dominio **nuevas** (20 lejanas, 20 cercanas al dominio). Hacen falta porque las 40 del pool ya se usaron al calibrar el umbral |

Cada anotador guarda su ficha con sus iniciales (`ficha_anotador_A_XX.xlsx`) y la entrega.
Las fichas se generaron solo con la librería estándar de Python (sin Excel), así que conviene
abrir una antes de repartirlas para confirmar que las listas desplegables funcionan.

## Pasos

```powershell
# 0) (ya hecho) generar las fichas desde el pool y el corpus V3
python evaluacion/banco/gold/preparar_fichas.py

# 1) cuando A y B entregan: acuerdo (κ) y conflictos para el tercer evaluador
python evaluacion/banco/gold/acuerdo_gold.py kappa ficha_anotador_A_XX.xlsx ficha_anotador_B_YY.xlsx
#    → acuerdo_anotadores.csv, kappa_resumen.csv, conflictos_para_juez.xlsx

# 2) cuando el juez completa conflictos_para_juez.xlsx: consolidar
python evaluacion/banco/gold/acuerdo_gold.py consolidar ficha_anotador_A_XX.xlsx ficha_anotador_B_YY.xlsx `
    --juez conflictos_para_juez.xlsx --ood-nuevas plantilla_ood_nuevas.xlsx
#    → ../banco_gold_260.json y ../validacion_banco_gold_260.md
```

- `kappa` revisa primero las fichas (preguntas faltantes, tipos inválidos, documentos fuera del corpus,
  preguntas respondibles sin documento o sin categoría) y no calcula nada si hay errores (`--forzar` lo omite).
- κ de Cohen para **tipo**, **bloque** (dominio / fuera de dominio / ambigua) y **documento**; para los
  artículos, proporción de coincidencia exacta y Jaccard medio entre las preguntas con el mismo documento.
  Umbrales de la guía: κ documento ≥ 0.80, κ tipo ≥ 0.75.
- Va al juez toda pregunta en la que A y B difieren en tipo, documento o artículos (los artículos se comparan
  por número: "Artículo 12°" = "Art. 12").
- `consolidar` no escribe nada mientras quede un conflicto sin decisión del juez. Con acuerdo, la respuesta de
  referencia es la de A y los puntos clave son la unión de A y B sin duplicados. Verifica cada documento y
  artículo contra el corpus V3.
- El resultado tiene el mismo formato que `banco_v32.json`, así que lo leen directamente
  `retrieval/exp_a_recuperacion.py`, `comparacion_v2_v3/correr_17q_e2e.py` y `exp_c/exp_c_abstencion.py --banco`.
- Marcas para el análisis: `conjunto_desarrollo` (las preguntas de los bancos 17Q y v3.2, que se usaron para
  ajustar el sistema) y `vista_en_desarrollo` (las 40 fuera de dominio del pool). Los resultados oficiales se
  reportan también sin ellas.

Probado de punta a punta con dos anotadores simulados (A = candidatos del pool, B = A con un 15 % de cambios):
κ tipo 0.87, κ documento 1.0, 29 conflictos, consolidación con 0 errores contra el corpus.
Tests: `backend/tests/test_gold_acuerdo.py`.
