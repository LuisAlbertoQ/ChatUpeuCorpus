# Auditoría del banco de 17 preguntas — 2026-11-21

Corpus: colección `corpus_upeu_v3_bgem3` (vector_store). Fuentes comparadas: `preguntas_comparacion.json` (JSON), `banco_preguntas` v3_curado (BP, **la que leen los scripts de evaluación**) y `groundtruth_v31_preguntas/_puntos` (v3.1, curado, 66 puntos). Generado por `auditar_banco_17q.py` (solo lectura).

## Resumen por pregunta

| Q | Pregunta | Tema | Cat. banco → real | Documento (v3.1) | Artículos v3.1 en V3 | Puntos BP/v3.1 |
|---|---|---|---|---|---|---|
| Q01 | ¿Qué dice el estatuto sobre las autoridades universitarias? | Gobierno | A | ESTATUTO 2024. 04-09-2024 | Artículo 19° (pág. 8); Artículo 32° (pág. 12); Artículo 34° (pág. 14) | 3/4 |
| Q02 | ¿Cómo se eligen el rector y vicerrectores? | Gobierno | A | ESTATUTO 2024. 04-09-2024 | Artículo 34° (pág. 14); Artículo 38° (pág. 15); Artículo 42° (pág. 16) | 3/4 |
| Q03 | ¿Cuáles son los requisitos para obtener el título profesional? | Académico | B | REGLAMENTO GRADOS Y TITULOS.v8 2025 | Artículo 41° (pág. 23); Artículo 42° (pág. 23) | 3/6 |
| Q04 | ¿Cómo me matriculo en la UPeU? | Académico | **A → B** | REGLAMENTO DE ESTUDIOS V5_2025 | Artículo 70° (pág. 21); Artículo 71° (pág. 21); Artículo 72° (pág. 21) | 3/3 |
| Q05 | ¿Qué requisitos hay para un proyecto de tesis? | Investigación | C | REGLAMENTO INVESTIGACION UPeU 2025 V8 | Artículo 15° (pág. 10); Artículo 16° (pág. 10) | 3/3 |
| Q06 | ¿Cuáles son los requisitos para publicar un artículo científico? | Investigación | C | REGLAMENTO INVESTIGACION UPeU 2025 V8 | Artículo 119° (pág. 28) | 3/3 |
| Q07 | ¿Qué becas ofrece la universidad? | Bienestar | **B → D** | REGLAMENTO BECAS 2021 ACTUALIZADO | Artículo 4° (pág. 6,7; 3 partes); Artículo 13° (pág. 9) | 3/5 |
| Q08 | ¿Qué sanciones existen para los estudiantes? | Bienestar | **B → D** | REGLAMENTO ESTUDIANTE UNIONISTA V3 | Artículo 45° (pág. 20); Artículo 50° (pág. 27); Artículo 55° (pág. 28; 2 partes) | 3/5 |
| Q09 | ¿Qué dice la política de trabajo digno? | Laboral | E | Politica Institucional de trabajo digno y protección de la persona v.1 | (sin artículo) | 3/3 |
| Q10 | ¿Quién supervisa la auditoría interna? | Laboral | E | reglamento_deauditoria_interna | Artículo 8° (pág. 2); Artículo 10° (pág. 2); Artículo 11° (pág. 2; 3 partes) | 3/3 |
| Q11 | ¿Cómo solicito una constancia de estudios? | Académico | **B → A** | TUPA V6 2023 UPeU | (sin artículo) | 2/2 |
| Q12 | ¿Cuál es el procedimiento para cambiar de carrera? | Académico | B | REGLAMENTO DE ESTUDIOS V5_2025 | Artículo 283º (pág. 84) | 3/3 |
| Q13 | ¿Qué incentivos hay para investigadores? | Investigación | C | REGLAMENTO INCENTIVOS INVESTIGACION E INNOVACIÓN 2025 | Artículo 22° (pág. 10) | 3/4 |
| Q14 | ¿Qué derechos tiene el estudiante universitario? | Bienestar | **B → D** | REGLAMENTO ESTUDIANTE UNIONISTA V3 | Artículo 32° (pág. 15,16; 3 partes) | 3/6 |
| Q15 | ¿Cómo solicito una beca en la UPeU? | Bienestar | **B → D** | REGLAMENTO BECAS 2021 ACTUALIZADO | Artículo 49° (pág. 18,19; 3 partes) | 4/6 |
| Q16 | ¿Cuál es el procedimiento para presentar una queja? | Gobierno | **A → E** | REGLAMENTO INTERNO DE TRABAJO Final 2020 | Artículo 140° (pág. 82) | 3/3 |
| Q17 | ¿Qué servicios ofrece la universidad a los egresados? | Bienestar | **A → E** | Reglamento de seguimiento de egresados | Artículo 12° (pág. 6); Artículo 18° (pág. 8; 2 partes) | 2/3 |

## Hallazgos

- **Q01**: Artículos: los scripts comparan solo contra 'Artículo 19°' · v3.1 acepta ['Artículo 19°', 'Artículo 32°', 'Artículo 34°'] · Columna plural articulos_esperados desactualizada en BP: ['Artículo 132°'] (singular: 'Artículo 19°') · Evidencia con baja coincidencia en el texto: Q01_P04 (42%)
- **Q02**: Artículos: los scripts comparan solo contra 'Artículo 42°' · v3.1 acepta ['Artículo 34°', 'Artículo 38°', 'Artículo 42°']
- **Q03**: Artículos: los scripts comparan solo contra 'Artículo 42°' · v3.1 acepta ['Artículo 41°', 'Artículo 42°']
- **Q04**: Artículos: los scripts comparan solo contra 'Artículo 70°' · v3.1 acepta ['Artículo 70°', 'Artículo 71°', 'Artículo 72°'] · Columna plural articulos_esperados desactualizada en BP: ['Artículo 319°'] (singular: 'Artículo 70°') · Categoría desactualizada: banco=A · documento V3=B (Académico y estudios)
- **Q05**: Artículos: los scripts comparan solo contra 'Artículo 15°' · v3.1 acepta ['Artículo 15°', 'Artículo 16°']
- **Q07**: Artículos: los scripts comparan solo contra 'Artículo 13°' · v3.1 acepta ['Artículo 4°', 'Artículo 13°'] · Columna plural articulos_esperados desactualizada en BP: ['Artículo 4°'] (singular: 'Artículo 13°') · Categoría desactualizada: banco=B · documento V3=D (Bienestar estudiantil)
- **Q08**: Artículos: los scripts comparan solo contra 'Artículo 55°' · v3.1 acepta ['Artículo 45°', 'Artículo 50°', 'Artículo 55°'] · Categoría desactualizada: banco=B · documento V3=D (Bienestar estudiantil) · Evidencia con baja coincidencia en el texto: Q08_P04 (69%), Q08_P05 (64%)
- **Q09**: Columna plural articulos_esperados desactualizada en BP: ['Artículo 1°'] (singular: '')
- **Q10**: Artículos: los scripts comparan solo contra 'Artículo 8°' · v3.1 acepta ['Artículo 8°', 'Artículo 10°', 'Artículo 11°']
- **Q11**: Categoría desactualizada: banco=B · documento V3=A (Gobierno y estatuto institucional) · Tema 'Académico' sugiere B pero el documento es A
- **Q14**: Categoría desactualizada: banco=B · documento V3=D (Bienestar estudiantil)
- **Q15**: Categoría desactualizada: banco=B · documento V3=D (Bienestar estudiantil)
- **Q16**: Categoría desactualizada: banco=A · documento V3=E (Laboral, docencia y políticas) · Tema 'Gobierno' sugiere A pero el documento es E
- **Q17**: Documento distinto: JSON/BP='REGLAMENTO GENERAL UPeU 2023' vs v3.1='Reglamento de seguimiento de egresados' · Artículos: los scripts comparan solo contra 'Artículo 421°' · v3.1 acepta ['Artículo 12°', 'Artículo 18°'] · Categoría desactualizada: banco=A · documento V3=E (Laboral, docencia y políticas) · Tema 'Bienestar' sugiere D pero el documento es E

Sin hallazgos: Q06, Q12, Q13.
