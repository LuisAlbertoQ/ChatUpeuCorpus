# Análisis estadístico (Revisión 3, §9)

`estadistica.py` (solo librería estándar; scipy opcional para contrastar):

- `bootstrap_ic` / `bootstrap_diferencia`: IC95 % percentil remuestreando preguntas (10,000 réplicas, semilla fija).
- `wilson_ic`: proporción con IC de Wilson, para H5 (abstención) y tasas con n pequeño.
- `wilcoxon_pareado`: rangos con signo, dos colas; exacto si n ≤ 20 sin empates, si no normal con
  corrección de empates (coincide con scipy). Devuelve el tamaño de efecto r de rango biserial.
- `holm`: ajuste de Holm-Bonferroni dentro de un experimento.
- `cohen_dz`, `magnitud_r`, `comparar_sistemas`, `resumen_sistemas`.

Regla aplicada: una diferencia es "significativa" solo si el p de Holm < 0.05 **y** el IC95 de la
diferencia no incluye 0.

```powershell
python evaluacion/estadistica/estadistica.py comparar --metrica recall@5 --base bm25 bm25=S1.csv bgem3=S4.csv
python evaluacion/estadistica/estadistica.py proporcion 38 40 --umbral 0.90
```

Tests: `backend/tests/test_estadistica.py` (valores de referencia de Wilson, Wilcoxon exacto y Holm).
