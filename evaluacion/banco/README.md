# Banco de preguntas y ground truth

- `preguntas_comparacion.json`: banco canónico 17 Q (documento/artículo esperado). ⚠️ Desactualizado
  respecto de la v3.1 en Q17 y en 8 categorías (ver auditoría abajo); se conserva por trazabilidad.
- `sincronizar_banco.py`: upsert idempotente JSON → `banco_preguntas` (uso: `python banco/sincronizar_banco.py`).
- `migrar_banco.py`: [YA EJECUTADO] one-shot CSV → DB.
- `GROUND_TRUTH_DECISION.md`: decisiones de curación v2.
- `CHANGELOG_GROUNDTRUTH_V31.md`: trazabilidad v3 (50 pts) → v3.1 (66 pts, tablas `groundtruth_v31_*`) + banco negativo N01-N06 (`banco_no_answer`).

Ground truth v3.1_curado: **congelado en la base de datos, no modificar**.

## Banco técnico v3.2 (2026-11-21) — vigente para evaluar el chatbot

| Archivo | Contenido |
|---|---|
| `banco_v32.json` | 30 preguntas + 6 negativas, con documentos y **todos** los artículos aceptados (página, chunk_ids, partes), categoría/tema desde los metadatos del corpus V3, 114 puntos con evidencia, origen y estado de cada pregunta |
| `banco_v32.csv` | Resumen tabular |
| `validacion_banco_v32.md` | Resultado de la validación automática |
| `construir_banco_v32.py` | Genera y valida el banco contra el corpus (solo escribe si no hay errores) |
| `auditar_banco_17q.py` / `auditoria_banco_17q_2026-11-21.md` | Auditoría que motivó la v3.2 |
| `banco_oe1_162.csv` | Banco del OE1 (162 Q, sin revisión humana), usado para calibrar el umbral |

**Qué cambia respecto de la v3.1** (la v3.1 de la base no se tocó; la v3.2 es un archivo nuevo):

1. **Q17**: se propaga la corrección que la v3.1 ya tenía (Reglamento de seguimiento de egresados,
   Art. 12° y 18°) y que nunca había llegado a `banco_preguntas` ni a `preguntas_comparacion.json`.
2. **Categorías y temas** recalculados desde los metadatos del corpus V3 (8 de 17 venían de la
   taxonomía previa a la V2: Q04, Q07, Q08, Q11, Q14, Q15, Q16, Q17).
3. **Artículos múltiples**: se aceptan todos los artículos de la v3.1 (antes los scripts comparaban
   contra uno solo). En `banco_preguntas`, la columna plural `articulos_esperados` contradice a la
   singular en Q01, Q04, Q07 y Q09: no usarla.
4. **Q05** ("requisitos para un proyecto de tesis"): Art. 15–16 → **Art. 17–18** del Reglamento de
   Investigación (perfil de proyecto para la tesis y su estructura).
5. **Q16** ("procedimiento para presentar una queja"): Reglamento Interno de Trabajo Art. 140° →
   **Defensoría Universitaria Art. 15, 17 y 22** (vías, contenido y plazos). El contenido anterior
   pasa a **Q28**, con la pregunta bien formulada (reclamo laboral de un trabajador).
6. **13 preguntas nuevas (Q18–Q30)** en documentos que no tenían ninguna: Admisión, Idiomas, Movilidad,
   Pago de servicios, Código de Ética, Excelencia académica, PRODAC, Comité Electoral, Duplicado de
   diplomas, Acoso y hostigamiento sexual, Reglamento Interno de Trabajo, TUPA (carné) y Jefes de prácticas.

**Validación** (`construir_banco_v32.py`): cada documento existe en `corpus_upeu_v3_bgem3`, cada artículo
existe en su documento, la categoría coincide con los metadatos, el tema con la categoría, no hay
preguntas duplicadas, y la evidencia de cada punto aparece en el texto del artículo. Las 49 evidencias
de preguntas nuevas o corregidas son **literales**; 21 heredadas de la v3.1 son paráfrasis encontradas
con 69–100 % de coincidencia (avisos, no errores).

**Estado**: 15 preguntas `CURADO_V31` y 15 `PROPUESTA_V32_PENDIENTE_REVISION_HUMANA` (Q05, Q16, Q18–Q30).
Antes de usarlas como ground truth definitivo deben pasar por un segundo anotador (Revisión 3 §3; fichas en `gold/`,
reparto en `../ENTREGA_EVALUADORES.md`).

⚠️ **Sesgo de facilidad**: las preguntas nuevas se redactaron leyendo el artículo y comparten su
vocabulario, por eso se recuperan mejor (documento 13/13 vs 13/17). Reportar los dos subconjuntos por
separado. En el gold set de 260, las preguntas deben redactarlas anotadores en lenguaje de estudiante,
sin mirar el documento.

**Uso**:

```bash
python evaluacion/banco/construir_banco_v32.py            # regenerar y validar
docker exec oe5-backend python /data/evaluacion/comparacion_v2_v3/correr_17q_e2e.py --etiqueta X \
    --banco-json /data/evaluacion/banco/banco_v32.json [--negativas]
python evaluacion/comparacion_v2_v3/completitud_auto.py --banco-json evaluacion/banco/banco_v32.json E2E_X_*.json
```

O con el script de ablación: `.\evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta X -BancoJson banco_v32.json -Negativas`.
Línea base de la configuración vigente: `evaluacion/comparacion_v2_v3/COMPARACION_V2_V3.md` §9.

## Gold set 260 (2026-11-22)

Fichas de anotación ciegas, plantilla de 40 preguntas fuera de dominio nuevas, κ de Cohen y consolidación en
`gold/` (ver `gold/README.md`). El resultado será `banco_gold_260.json`, con el mismo formato que `banco_v32.json`.
