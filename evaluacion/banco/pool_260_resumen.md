# Pool 260 — reporte de generación

- preguntas: **260** (200 dominio + 40 fuera de dominio + 20 ambiguas)
- puntos candidatos: **903**
- estados: {'CANDIDATO_NO_VALIDADO': 237, 'SEMILLA_CURADA': 23}

## Dominio por categoría documental

| cat | preguntas | documentos |
|---|---|---|
| A | 25 | 5 |
| B | 61 | 14 |
| C | 27 | 7 |
| D | 35 | 7 |
| E | 52 | 15 |

## Dominio por tipo

| tipo | preguntas |
|---|---|
| DIRECTA | 138 |
| REQUISITOS | 35 |
| PROCEDIMIENTO | 27 |

## Cobertura por documento

| clave | documento | cat | objetivo | real |
|---|---|---|---|---|
| A01 | ESTATUTO 2024. 04-09-2024.pdf | A | 6 | 6 |
| A02 | REGLAMENTO GENERAL UPeU 2023.pdf | A | 7 | 7 |
| A03 | REGLAMENTO DEFENSORIA UNIVERSITARIA 2025 v4.pdf | A | 4 | 4 |
| A04 | Reglamento Comite Electoral Universitario 2016 OK.pdf | A | 4 | 4 |
| A05 | TUPA V6 2023 UPeU.pdf | A | 4 | 4 |
| B01 | Guía para la organización y orientación del legajo para la docencia ordinaria.pdf | B | 4 | 4 |
| B02 | Modelo de índice del contenido - Legajo.pdf | B | 1 | 1 |
| B03 | MODIFICACIÓN DIRECTIVA IMPLEMENTACION BACHILLER AUTOMATICO 2020 - 2021.pdf | B | 4 | 4 |
| B04 | REGLAMENTO ADMISION 2025.v7.pdf | B | 7 | 7 |
| B05 | REGLAMENTO DE ESTUDIOS POSGRADO 2025.pdf | B | 6 | 6 |
| B06 | REGLAMENTO DE ESTUDIOS V5_2025.pdf | B | 6 | 6 |
| B07 | REGLAMENTO GRADOS Y TITULOS.v8 2025.pdf | B | 7 | 7 |
| B08 | REGLAMENTO IDIOMAS INGLES O NATIVO 2023v.3.pdf | B | 4 | 4 |
| B09 | REGLAMENTO MOVILIDAD ACADEMICA ESTUDIANTIL Y DOCENTEv1.pdf | B | 4 | 4 |
| B10 | REGLAMENTO SERVICIO APRENDIZAJE IDIOMAS.pdf | B | 4 | 4 |
| B11 | REQUISITOS PARA TRASLADO EXTERNO UNIVERSIDADES NO LICENCIADAS.pdf | B | 2 | 2 |
| B12 | Reglamento Idiomas Ingles o Nativo.pdf | B | 4 | 4 |
| B13 | Reglamento Pago Servicios Educativos o Académicos.pdf | B | 4 | 4 |
| B14 | Reglamento de Publicaciones y Fondo Editorial.pdf | B | 4 | 4 |
| C01 | REGLAMENTO CODIGO ETICA INVESTIGACION 2021.pdf | C | 4 | 4 |
| C02 | REGLAMENTO INCENTIVOS INVESTIGACION E INNOVACIÓN 2025.pdf | C | 4 | 4 |
| C03 | REGLAMENTO INVESTIGACION UPeU 2025 V8.pdf | C | 6 | 6 |
| C04 | REGLAMENTO INVESTIGADORES UPeU V1 2025.pdf | C | 4 | 4 |
| C05 | REGLAMENTO PARA INVESTIGADORES UPeU V2 2025.pdf | C | 4 | 4 |
| C06 | REGLAMENTO PROPIEDAD INTELECTUALv3.pdf | C | 4 | 4 |
| C07 | TABLAS INCENTIVOS INVESTIGACION E INNOVACION 2023_para web upeu.pdf | C | 1 | 1 |
| D01 | REGLAMENTO BECAS 2021 ACTUALIZADO.pdf | D | 7 | 7 |
| D02 | REGLAMENTO ESTUDIANTE UNIONISTA V3.pdf | D | 6 | 6 |
| D03 | REGLAMENTO PRODAC 2022(R_SG).pdf | D | 5 | 5 |
| D04 | REGLAMENTO RECONOCIMIENTO EXCELENCIA ACADEMICA 2020.pdf | D | 4 | 4 |
| D05 | REGLAMENTO RESIDENCIAS UNIVERSITARIAS.pdf | D | 5 | 5 |
| D06 | Reglamento de promocion de recreación y del deporte.pdf | D | 4 | 4 |
| D07 | Reglamento del Laboratorio Multimedia del CI.pdf | D | 4 | 4 |
| E01 | DIRECTIVA SOBRE PUBLICACIONES CIENTÍFICAS 2025.pdf | E | 4 | 4 |
| E02 | Politica Institucional de Inclusión y diversidad cultural v1.pdf | E | 2 | 2 |
| E03 | Politica Institucional de trabajo digno y protección de la persona v.1.pdf | E | 2 | 2 |
| E04 | Politica-ambiental.pdf | E | 1 | 1 |
| E05 | REGLAMENTO DOCENCIA ORDINARIA v3.5.pdf | E | 5 | 5 |
| E06 | REGLAMENTO IDENTIDAD VISUAL Y REDES SOCIALES.pdf | E | 4 | 4 |
| E07 | REGLAMENTO INTERNO DE TRABAJO Final 2020.pdf | E | 5 | 5 |
| E08 | Reglamento Prevención Acoso y Hostigamiento Sexual 2025.pdf | E | 4 | 4 |
| E09 | Reglamento de Jefes de prácticas apoyo y profesional.pdf | E | 4 | 4 |
| E10 | Reglamento de duplicado de diplomas.pdf | E | 4 | 4 |
| E11 | Reglamento de seguimiento de egresados.pdf | E | 4 | 4 |
| E12 | Reglamento-capacitacion-docente.pdf | E | 4 | 4 |
| E13 | Reglamento-de-docentes-unionista_mod art.23 y24 final.pdf | E | 4 | 4 |
| E14 | reglamento_deauditoria_interna.pdf | E | 4 | 4 |
| E15 | Resolucion-TRANSCRIPCIÓN.pdf | E | 1 | 1 |

## Ceguera del pool

- Los IDs `GOLD_NNN` se asignaron tras mezclar los 260 ítems con semilla fija `20260927`; el orden **no** agrupa dominio, fuera de dominio ni ambiguas.
- `pool_260_preliminar.jsonl/.csv` contiene solo `pregunta_id` y `texto`:
  el anotador no ve bloque, tema, documento, artículo, tipo ni puntos candidatos.
- `pool_260_verificacion.json` (este equipo, no se entrega a los anotadores) conserva
  bloque, documento candidato, artículo y puntos candidatos para la revisión del investigador.

## Advertencias metodológicas

1. Los puntos de las preguntas `CANDIDATO_NO_VALIDADO` se extraen automáticamente del texto del
   artículo (incisos numerados o primeras oraciones). **No son ground truth**: son hipótesis a
   verificar por los anotadores leyendo el documento.
2. La pregunta se redactó a partir del corpus, por lo que el documento candidato puede coincidir
   con el esperado. Es un sesgo conocido de la generación; se declara en el informe y se mitiga
   con doble anotación ciega (el anotador no ve el candidato).
3. Las 17 preguntas `SEMILLA_CURADA` y las 6 fuera de dominio ya están curadas y no requieren
   re-anotación; cuentan dentro de las 260.
4. Documentos sin articulado (políticas, resoluciones, TUPA, guías) tienen cuota reducida porque
   su contenido no soporta 4 preguntas independientes sin forzar preguntas artificiales. En esos
   casos los puntos candidatos se eligen por solapamiento léxico con la pregunta, no por orden de
   lectura: son más débiles y requieren revisión manual obligatoria.
5. Las 20 preguntas ambiguas se redactaron deliberadamente sin entidad resoluble; su valor está en
   evaluar si el sistema pide aclaración o alucina una respuesta.
6. El `tipo` del borrador (DIRECTA/REQUISITOS/PROCEDIMIENTO) es solo una hipótesis de redacción:
   el tipo definitivo lo asignan los anotadores y es el que se usa para el κ de tipo. La distribución
   final puede diferir de la mostrada arriba.
