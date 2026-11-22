# Experimento C — abstención (Revisión 3, H5)

`exp_c_abstencion.py construir` genera `../banco/banco_exp_c_pool.json` con las 40 preguntas fuera de
dominio y las 20 ambiguas del pool de 260. `exp_c_abstencion.py analizar <corridas NEG .json>` aplica el
criterio ratificado (`../retrieval/criterio_h5.md`, opción A: límite inferior del IC95 Wilson ≥ 0.90) y
escribe `resumen_exp_c.csv` y `detalle_exp_c.csv`.

```powershell
.\evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta C_s42 -Vars @{OLLAMA_SEED="42"} -BancoJson banco_exp_c_pool.json -Negativas
python evaluacion/exp_c/exp_c_abstencion.py analizar evaluacion/comparacion_v2_v3/E2E_C_s42_NEG_*.json
```

## Corrida preliminar 2026-11-22 (configuración congelada `c47d455a`, semillas 42 y 7, resultados idénticos)

| Grupo | Correctas | IC95 Wilson | Detalle |
|---|---|---|---|
| Fuera de dominio (40) | **40/40 = 1.00** | [0.912, 1.00] | M03 26, M04 14 · cumple el criterio (≥ 0.90) |
| Ambiguas (20) | **14/20 = 0.70** | [0.48, 0.85] | M05 (pide aclaración) 4, M04 7, M03 3, **M02 (responde) 6** |

**No es todavía el resultado oficial de H5**, por dos razones:

1. **Fuga:** las 40 preguntas fuera de dominio del pool ya se usaron en el desarrollo (34 en la
   calibración del umbral, que se eligió justamente para que se abstuvieran, y 6 = N01–N06 en las
   ablaciones). El 40/40 era esperable por construcción. Para la decisión oficial hacen falta 40
   preguntas fuera de dominio nuevas, redactadas por los anotadores sin ver el sistema.
2. Las 60 preguntas siguen como `CANDIDATO_NO_VALIDADO` en el pool: falta que los anotadores confirmen
   que de verdad son fuera de dominio / ambiguas.

**Hallazgo:** el sistema maneja mal la ambigüedad. Solo 4 de 20 reciben una pregunta de aclaración (M05);
6 reciben una respuesta inventando el contexto (p. ej. "¿Qué documentos necesito?" → requisitos de
admisión; "¿Qué sanciones hay?" → sanciones del reglamento de investigadores). El detector de ambigüedad
(`_pregunta_es_ambigua`) solo reconoce algunos patrones. Mejorarlo cambiaría la configuración congelada:
si se hace, debe registrarse en `../REPRODUCIBILIDAD.md` y repetirse este experimento.
