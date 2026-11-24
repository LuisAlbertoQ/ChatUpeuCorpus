# Tablas y figuras del artículo (Revisión 3, .docx §11)

Creado el 2026-11-23. `generar_tablas.py` arma las tablas 1–6 y las figuras 1–3 leyendo los resultados ya
calculados (no vuelve a correr experimentos). Hoy usa los resultados **preliminares**; cuando estén los oficiales del
gold set se vuelve a correr con otras rutas y todo se regenera con la misma estructura.

```powershell
python evaluacion/tablas/generar_tablas.py            # preliminar → evaluacion/tablas/salida/
```

| Elemento del .docx | Fuente | Estado hoy |
|---|---|---|
| Tabla 1 — corpus y composición del banco | CSV de chunks del OE1 + banco | corpus real (48 docs, 5,117 chunks); banco v3.2 en lugar del gold set |
| Tabla 2 — recuperadores × chunk (R@k, MRR, nDCG) | `retrieval/exp_a/h2_<etiqueta>/tabla2.csv` | preliminar (154 preguntas del OE1) |
| Figura 1 — R@5 vs tamaño de chunk | `h2_<etiqueta>/figura1.csv` → `figura1_recall_chunk.svg` | preliminar |
| Tabla 3 — generadores (fidelidad, relevancia, corrección, atribución, latencia) | `generacion/exp_b_nuevos/` + `humana/fidelidad_rev3/resumen_fidelidad.csv` | automáticas listas; columnas humanas "pendiente" |
| Tabla 4 — por categoría del sistema final | `exp_a/<etiqueta>_chunk350/S4_bgem3.csv` | preliminar |
| Figura 2 — R@5 por categoría con IC | → `figura2_recall_categoria.svg` | preliminar |
| Tabla 5 — abstención | `exp_c/resumen_exp_c.csv` | preliminar (fuera de dominio ya vistas) |
| Tabla 6 — análisis de errores | corrida del sistema final + `humana/fidelidad_rev3/detalle_fidelidad.csv` | preliminar; "generación infiel" espera la evaluación humana |
| Figura 3 — ejemplos cualitativos | misma corrida → `figura3_ejemplos.md` | un candidato por tipo de error, para elegir y editar |

Tabla 6 clasifica cada respuesta del sistema final, en este orden: error técnico (M06) → recuperación fallida (el
documento correcto no está entre los 4 fragmentos) → falsa abstención → generación infiel (fidelidad 0 de algún
evaluador) → atribución (exacta = correcta y sustentada, parcial, incorrecta, ausente).

Con el gold set: `--banco ../banco/banco_gold_260.json --etiqueta-a GOLD --exp-b <carpeta> --exp-c <carpeta>
--corrida-final "<corrida del sistema final>"`. Tests: `backend/tests/test_generar_tablas.py`.
