# PARTE 3 — EVALUACIÓN TÉCNICA Y MADUREZ DEL CHATBOT RAG UPeU

# 0. PROPÓSITO

Este documento define la implementación de la **Parte 3: Evaluación del chatbot RAG y evaluación de madurez OE8**.

La evaluación debe dividirse en dos niveles:

```text
NIVEL 1
Evaluación técnica del RAG
        ↓
¿Recupera correctamente?
¿Responde correctamente?
¿Las fuentes son correctas?
        ↓
NIVEL 2
Evaluación de madurez OE8
        ↓
¿Qué nivel de madurez presenta el sistema?
```

NO mezclar ambas evaluaciones.

La evaluación técnica mide desempeño del RAG.

La evaluación OE8 mide madurez operacional/propuesta del sistema.

---

# 1. RESTRICCIÓN PRINCIPAL

La Parte 1 ya está implementada.

La Parte 3 NO debe reconstruir:

* corpus;
* OCR;
* chunks;
* embeddings;
* ChromaDB.

La Parte 3 utiliza el sistema existente como objeto de evaluación.

---

# 2. FUENTES DE DATOS

La evaluación debe utilizar:

```text
registro_interacciones.db
│
├── interacciones
├── banco_preguntas
├── evaluacion_retrieval
├── evaluacion_generacion
├── evaluacion_piloto
├── evaluacion_automatica
└── experimentos_rag
```

Si algunas tablas ya existen, reutilizarlas y adaptarlas en lugar de duplicarlas.

---

# 3. ARQUITECTURA DE EVALUACIÓN

```text
                    SISTEMA RAG
                        |
             +----------+----------+
             |                     |
             v                     v
       BANCO DE PRUEBAS       USUARIOS REALES
             |                     |
             v                     v
     EVALUACIÓN TÉCNICA       INTERACCIONES
             |                     |
             |                     v
             |               MÉTRICAS OE8
             |                     |
             v                     v
      RETRIEVAL + GENERACIÓN   PILOTO LIKERT
             |                     |
             +----------+----------+
                        |
                        v
                 EVALUACIÓN OE8
                        |
                        v
                NIVEL DE MADUREZ
```

---

# 4. BANCO DE PREGUNTAS

Actualmente existe un banco aproximado de 17 preguntas.

Debe convertirse en un dataset de evaluación con ground truth.

Tabla:

```text
banco_preguntas
```

Campos recomendados:

```text
pregunta_id
pregunta
categoria
tipo_pregunta

documento_esperado
articulo_esperado
seccion_esperada
pagina_esperada

chunk_esperado
respuesta_esperada

cobertura_esperada
```

---

# 5. TIPOS DE PREGUNTAS

El banco debe contener diferentes tipos.

Categorías sugeridas:

```text
DIRECTA
ARTICULO
REQUISITOS
PROCEDIMIENTO
MULTI_CHUNK
MULTI_DOCUMENTO
SIN_COBERTURA
```

Ejemplo:

```text
P001
Pregunta:
¿Cómo solicito una beca?

Tipo:
REQUISITOS

Documento esperado:
Reglamento Becas 2021

Artículo esperado:
49°

Cobertura:
ANSWERABLE
```

---

# 6. GROUND TRUTH

Para cada pregunta se debe establecer la referencia correcta.

Ejemplo:

```text
Pregunta:
¿Cómo solicito una beca?

Ground truth:

Documento:
REGLAMENTO BECAS 2021 ACTUALIZADO.pdf

Artículo:
49°

Página:
XX

Chunk:
becas_2021_art49_01
```

Cuando sea posible guardar `chunk_esperado`, hacerlo.

Sin embargo, el ground truth principal debe poder funcionar aunque cambie el `chunk_id` después de una reconstrucción.

Por ello, priorizar:

```text
documento
artículo
sección
página
```

y utilizar `chunk_id` como referencia versionada.

---

# 7. PREGUNTAS SIN COBERTURA

El banco debe contener preguntas que NO tengan respuesta en el corpus.

Ejemplo conceptual:

```text
Pregunta:
¿Cuál es el precio de una laptop en Lima?

cobertura_esperada:
NO_ANSWER
```

El sistema debe responder con una abstención apropiada.

Esto permite evaluar:

```text
¿El sistema sabe decir "no tengo información"?
```

y detectar alucinaciones.

---

# 8. EVALUACIÓN DE RETRIEVAL

Crear o adaptar:

```text
evaluacion_retrieval
```

Campos:

```text
evaluacion_id
pregunta_id
experimento_id

top_k
chunk_esperado
posicion_chunk_esperado

recuperado

distancia

documento_recuperado
articulo_recuperado
seccion_recuperada
pagina_recuperada

timestamp
```

Para preguntas con múltiples fuentes, permitir múltiples registros.

---

# 9. FLUJO DE EVALUACIÓN RETRIEVAL

```text
Pregunta del banco
       |
       v
Embedding
       |
       v
ChromaDB
       |
       v
TOP 15
       |
       v
Comparar contra Ground Truth
       |
       +---- ¿Está el documento?
       |
       +---- ¿Está el artículo?
       |
       +---- ¿Está el chunk?
       |
       +---- ¿En qué posición?
       |
       v
Guardar resultado
```

---

# 10. MÉTRICAS DE RETRIEVAL

Calcular:

```text
Recall@5
Recall@10
Recall@15

Hit Rate@5
Hit Rate@10
Hit Rate@15

MRR
NDCG
```

No utilizar únicamente una métrica.

---

# 11. DEFINICIONES

## Recall@K

Determina si el conjunto de información relevante esperado fue recuperado dentro de los primeros K resultados.

## Hit Rate@K

Determina si al menos un resultado relevante apareció dentro de K.

## MRR

Mide la posición del primer resultado relevante.

Cuanto más arriba aparece el resultado correcto, mayor es el MRR.

## NDCG

Permite considerar diferentes grados de relevancia y posición.

---

# 12. EVALUACIÓN DE GENERACIÓN

Crear o adaptar:

```text
evaluacion_generacion
```

Campos:

```text
evaluacion_id
pregunta_id
experimento_id

respuesta_generada
respuesta_esperada

relevancia
faithfulness
completitud

citation_precision
citation_correctness

respuesta_valida

evaluador
timestamp
```

---

# 13. CRITERIOS DE GENERACIÓN

Evaluar:

### Relevancia

¿La respuesta responde realmente la pregunta?

### Faithfulness

¿Las afirmaciones de la respuesta están sustentadas por el contexto recuperado?

### Completitud

¿Incluye los elementos importantes que aparecen en la respuesta esperada?

### Citation correctness

¿Las citas/documentos/artículos corresponden realmente al contenido utilizado?

### Abstención

Cuando la pregunta no tiene cobertura:

```text
¿El sistema evita inventar una respuesta?
```

---

# 14. EVALUACIÓN DE CITAS

Las fuentes deben verificarse contra los resultados de retrieval.

Ejemplo:

```text
Respuesta:

Según el Artículo 49°...

Fuentes:

Artículo 49°
Artículo 61°
Artículo 45°
Artículo 11°
```

Verificar:

```text
¿Artículo 49 existe en retrieval?
¿Documento coincide?
¿Artículo coincide?
```

No considerar correcta una fuente únicamente porque el LLM la escribió.

---

# 15. EXPERIMENTOS

Crear:

```text
experimentos_rag
```

Campos:

```text
experimento_id
fecha

corpus_version
embedding_model
llm_model

top_k_raw
top_k_final
threshold

ranking_method
ranking_version

prompt_version
```

Esto permite comparar configuraciones.

---

# 16. EXPERIMENTOS INICIALES

Probar como mínimo:

```text
EXP01
Top15 → Top4 → threshold 0.40

EXP02
Top15 → Top4 → threshold 0.35

EXP03
Top15 → Top4 → threshold 0.45
```

Posteriormente:

```text
EXP04
Top20 → Top5 → threshold 0.40
```

y, si se incorpora un reranker real:

```text
EXP05
Top15 → reranker → Top4
```

No cambiar múltiples variables sin registrar claramente qué se modificó.

---

# 17. INTERACCIONES REALES

La tabla:

```text
interacciones
```

representa uso real del chatbot.

Debe utilizarse para la evaluación operacional.

No mezclar directamente todas las interacciones con el banco de pruebas.

---

# 18. EXCLUSIONES PARA MÉTRICAS

Al calcular métricas de desempeño RAG, no contar indiscriminadamente:

```text
M01 = bienvenida
M07 = disclaimer
M08 = límite de sesión
```

como consultas RAG normales.

M06 tampoco debe interpretarse como fallo de retrieval.

Separar:

```text
consultas RAG válidas
errores técnicos
validaciones
bienvenida
disclaimer
límite de sesión
```

---

# 19. MÉTRICAS AUTOMÁTICAS OE8

Mantener las seis dimensiones:

```text
1. Funcional
2. Recuperación documental
3. Explicabilidad
4. Usabilidad
5. Gobernanza
6. Preparación tecnológica
```

---

# 20. MÉTRICAS AUTOMÁTICAS ACTUALES

Utilizar:

```text
total
pct_M02
pct_M03
pct_M04
pct_M05
pct_M06
pct_fuentes
tiempo_prom
tiempo_p95
```

Estas métricas deben describirse como:

> métricas operacionales definidas para el modelo de madurez OE8

No presentarlas como métricas estándar oficiales de CMMI o TRL.

---

# 21. DIMENSIÓN FUNCIONAL

Mapeo actual:

```text
% M02

>= 90% → 5
>= 75% → 4
>= 50% → 3
>= 25% → 2
< 25%  → 1
```

Implementar como configuración, no como números codificados en múltiples lugares.

---

# 22. RECUPERACIÓN DOCUMENTAL

Usar:

```text
% de interacciones con fuentes
```

Mapeo:

```text
>= 90% → 5
>= 75% → 4
>= 50% → 3
>= 25% → 2
< 25%  → 1
```

Sin embargo, la evaluación técnica de retrieval debe mantenerse separada.

---

# 23. EXPLICABILIDAD

Usar inicialmente:

```text
% de interacciones con fuentes
```

Mapeo:

```text
>= 95% → 5
>= 80% → 4
>= 60% → 3
>= 40% → 2
< 40%  → 1
```

Revisar posteriormente el riesgo de doble contabilización con Recuperación Documental.

---

# 24. USABILIDAD

Usar tiempo promedio:

```text
<= 10 s → 5
<= 20 s → 4
<= 30 s → 3
<= 40 s → 2
> 40 s  → 1
```

Además registrar:

```text
P95
```

El promedio y P95 deben aparecer en el reporte.

---

# 25. GOBERNANZA

Regla actual:

```text
% (M03 + M05)

5–30% → 5
< 5%  → 3
> 30% → 2
```

Esta regla debe implementarse tal como está definida actualmente, pero debe quedar documentada como una regla propia del modelo OE8.

No asumir que corresponde a una escala oficial CMMI.

Posteriormente debe revisarse si los intervalos tienen justificación suficiente.

---

# 26. PREPARACIÓN TECNOLÓGICA

Calcular:

```text
100 - %M06
```

Mapeo:

```text
>= 98% → 5
>= 95% → 4
>= 90% → 3
>= 80% → 2
< 80%  → 1
```

---

# 27. EVALUACIÓN PILOTO

La evaluación piloto contiene:

```text
6 dimensiones
×
5 ítems
=
30 ítems
```

Escala:

```text
1 = muy bajo / totalmente en desacuerdo
2
3
4
5 = muy alto / totalmente de acuerdo
```

Los ítems deben estar claramente asociados a una dimensión.

Tabla:

```text
evaluacion_piloto
```

Campos mínimos:

```text
evaluacion_id
participante_id_anonimo
fecha

dimension
item
respuesta_likert
```

No guardar información personal innecesaria.

---

# 28. PROMEDIO DEL PILOTO

Calcular:

```text
promedio_funcional
promedio_recuperacion
promedio_explicabilidad
promedio_usabilidad
promedio_gobernanza
promedio_preparacion
```

Después:

```text
P_piloto
```

---

# 29. COMBINACIÓN

Mantener:

```text
P_final = 0.6 × P_auto + 0.4 × P_piloto
```

si existe evaluación piloto.

Si no existe:

```text
P_final = P_auto
```

El peso 60/40 es una regla del modelo propuesto y debe documentarse como tal.

---

# 30. CONSISTENCY CAP

Mantener:

```text
dimensiones críticas:

Funcional
Recuperación documental
Explicabilidad
Gobernanza
Preparación tecnológica
```

No incluir Usabilidad en el conjunto crítico.

Calcular:

```text
dim_min = mínimo de las dimensiones críticas
```

Calcular nivel global por promedio.

Calcular nivel mínimo.

Aplicar:

```text
nivel_ajustado = min(
    nivel_global,
    nivel_min + 1
)
```

Después:

```text
puntaje_ajustado =
min(
    puntaje_global,
    CAP_NIVEL[nivel_ajustado]
)
```

---

# 31. CAP

Valores:

```text
Inicial      = 2.00
Básico       = 3.00
Gestionado   = 4.00
Optimizado   = 5.00
```

---

# 32. NIVELES

Utilizar:

```text
1.00 – 2.00  Inicial
2.01 – 3.00  Básico
3.01 – 4.00  Gestionado
4.01 – 5.00  Optimizado
```

No utilizar etiquetas adicionales.

---

# 33. TABLA DE RESULTADOS OE8

Crear o adaptar:

```text
evaluacion_automatica
```

Campos:

```text
evaluacion_id
fecha

total_interacciones

pct_M02
pct_M03
pct_M04
pct_M05
pct_M06
pct_fuentes

tiempo_promedio
tiempo_p95

score_funcional
score_recuperacion
score_explicabilidad
score_usabilidad
score_gobernanza
score_preparacion

score_piloto

p_final

puntaje_global
puntaje_ajustado

nivel_global
nivel_minimo
nivel_ajustado
```

Guardar snapshots históricos.

Idealmente:

```text
1 snapshot / mes
```

o por cada evaluación oficial.

---

# 34. REPORTE

Generar:

```text
reporte_madurez.md
```

El reporte debe contener:

```text
1. Fecha de evaluación
2. Versión del corpus
3. Modelo de embedding
4. Modelo LLM
5. Configuración RAG
6. Número de interacciones
7. Métricas automáticas
8. Resultados piloto
9. Seis dimensiones
10. Puntaje global
11. Consistency CAP
12. Nivel final
13. Resultados técnicos del RAG
14. Limitaciones
15. Recomendaciones de mejora
```

---

# 35. RESULTADOS TÉCNICOS Y MADUREZ NO DEBEN MEZCLARSE

El reporte debe separar:

```text
A. DESEMPEÑO TÉCNICO RAG

Recall@K
Hit Rate@K
MRR
NDCG
Faithfulness
Citation correctness
etc.
```

de:

```text
B. MADUREZ OE8

Funcional
Recuperación
Explicabilidad
Usabilidad
Gobernanza
Preparación tecnológica
P_final
Nivel
```

---

# 36. VALIDACIÓN DEL MODELO DE MADUREZ

El sistema debe permitir revisar posteriormente:

### Doble contabilización

Por ejemplo:

```text
Recuperación documental
+
Explicabilidad
```

actualmente pueden utilizar `% fuentes`.

Esto puede hacer que una misma característica tenga demasiado peso.

No cambiar automáticamente la fórmula.

Registrar esta observación como una posible mejora metodológica.

---

# 37. VALIDACIÓN DE UMBRALES

Los siguientes valores son reglas propuestas:

```text
M02 >= 90 → 5
Fuentes >= 90 → 5
Tiempo <= 10 → 5
etc.
```

Deben poder modificarse mediante configuración.

No codificarlos de forma irreversible.

---

# 38. REPRODUCIBILIDAD

Cada ejecución de evaluación debe registrar:

```text
experimento_id
corpus_version
embedding_model
llm_model
top_k_raw
top_k_final
threshold
ranking_version
prompt_version
fecha
```

Una evaluación debe poder reproducirse con la misma configuración.

---

# 39. SCRIPT PRINCIPAL

Crear/adaptar:

```text
calcular_madurez.py
```

Debe ejecutar conceptualmente:

```text
1. Cargar interacciones
2. Filtrar interacciones válidas
3. Calcular métricas automáticas
4. Convertir métricas a escala 1–5
5. Cargar piloto
6. Calcular dimensiones piloto
7. Combinar 60/40
8. Calcular promedio global
9. Aplicar consistency CAP
10. Determinar nivel
11. Guardar snapshot
12. Generar reporte
```

---

# 40. SCRIPT DE EVALUACIÓN TÉCNICA

Crear un ejecutable separado conceptualmente:

```text
evaluar_rag.py
```

Responsabilidad:

```text
1. Cargar banco de preguntas
2. Ejecutar retrieval
3. Registrar resultados
4. Calcular Recall@K
5. Calcular Hit Rate@K
6. Calcular MRR
7. Calcular NDCG
8. Ejecutar generación cuando corresponda
9. Evaluar respuestas
10. Evaluar citas
11. Guardar resultados
```

NO ejecutar esta evaluación completa en cada consulta del usuario.

Debe ser un proceso offline.

---

# 41. FLUJO DE EVALUACIÓN TÉCNICA

```text
banco_preguntas
      |
      v
evaluar_rag.py
      |
      v
Sistema RAG
      |
      +---------> Retrieval
      |               |
      |               v
      |       evaluacion_retrieval
      |
      +---------> Generation
                      |
                      v
              evaluacion_generacion
                      |
                      v
                  métricas
```

---

# 42. FLUJO DE MADUREZ

```text
interacciones
      |
      v
métricas automáticas
      |
      v
6 dimensiones
      |
      +------+
             |
evaluacion_piloto
             |
             v
        P_piloto
             |
             v
       combinación 60/40
             |
             v
      consistency CAP
             |
             v
      nivel de madurez
```

---

# 43. CRITERIOS DE ACEPTACIÓN

La Parte 3 se considera implementada cuando:

### Dataset

* [ ] Existe banco de preguntas estructurado.
* [ ] Existe ground truth.
* [ ] Existen preguntas answerable.
* [ ] Existen preguntas no-answer.
* [ ] Existen preguntas de diferentes tipos.

### Retrieval

* [ ] Existe evaluación offline.
* [ ] Se calcula Recall@K.
* [ ] Se calcula Hit Rate@K.
* [ ] Se calcula MRR.
* [ ] Se calcula NDCG.
* [ ] Se registra posición de resultados.

### Generation

* [ ] Se evalúa relevancia.
* [ ] Se evalúa faithfulness.
* [ ] Se evalúa completitud.
* [ ] Se evalúan citas.
* [ ] Se evalúa abstención.

### OE8

* [ ] Se calculan seis dimensiones.
* [ ] Se utiliza escala 1–5.
* [ ] Se procesa evaluación piloto.
* [ ] Se aplica 60/40.
* [ ] Se aplica consistency CAP.
* [ ] Se obtiene nivel.
* [ ] Se guarda snapshot.

### Reproducibilidad

* [ ] Cada evaluación tiene experiment_id.
* [ ] Se registra versión del corpus.
* [ ] Se registra modelo embedding.
* [ ] Se registra modelo LLM.
* [ ] Se registra threshold.
* [ ] Se registra Top-K.
* [ ] Se registra versión del prompt.

### Reporte

* [ ] Se genera `reporte_madurez.md`.
* [ ] Se genera `resultados_madurez.csv`.
* [ ] Se pueden comparar evaluaciones históricas.

---

# 44. NO HACER TODAVÍA

No implementar:

* nuevos modelos de embedding;
* GraphRAG;
* agentes;
* búsqueda web;
* fine-tuning;
* cambios grandes al corpus;
* nuevos niveles de madurez;
* nuevos pesos sin justificación;
* modificaciones arbitrarias a las reglas OE8.

Primero implementar, medir y documentar.

---

# 45. INSTRUCCIÓN PARA EL AGENTE DE PROGRAMACIÓN

Antes de modificar código:

1. Leer este documento completo.
2. Inspeccionar el repositorio.
3. Identificar:

   * estructura SQLite;
   * `calcular_madurez.py`;
   * banco de preguntas existente;
   * sistema de logging;
   * scripts de evaluación existentes;
   * configuración RAG;
   * archivos de reportes.
4. Presentar un plan de implementación.
5. No modificar Parte 1.
6. No modificar la fórmula OE8 sin autorización.
7. Reutilizar tablas existentes cuando sea posible.
8. Implementar evaluación técnica de forma independiente.
9. Ejecutar pruebas.
10. Documentar archivos modificados.

---

# 46. ORDEN DE IMPLEMENTACIÓN

## FASE 1

```text
Inspeccionar base de datos
        ↓
Inspeccionar banco de preguntas
        ↓
Inspeccionar calcular_madurez.py
        ↓
Inspeccionar scripts existentes
```

No modificar.

## FASE 2

```text
Completar banco de preguntas
        ↓
Agregar ground truth
```

## FASE 3

```text
Crear evaluacion_retrieval
        ↓
Implementar métricas
```

## FASE 4

```text
Crear evaluacion_generacion
        ↓
Evaluar respuestas y citas
```

## FASE 5

```text
Validar métricas automáticas OE8
```

## FASE 6

```text
Procesar evaluación piloto
        ↓
Aplicar 60/40
        ↓
Aplicar CAP
```

## FASE 7

```text
Generar reportes
        ↓
Guardar snapshot
        ↓
Comparar resultados
```

---

# 47. RESULTADO FINAL ESPERADO

La Parte 3 debe producir:

```text
                 SISTEMA RAG
                      |
             +--------+--------+
             |                 |
             v                 v
       EVALUACIÓN RAG      USO REAL
             |                 |
             v                 v
      Métricas técnicas   Métricas OE8
             |                 |
             v                 v
      Retrieval + Gen.    6 dimensiones
             |                 |
             +--------+--------+
                      |
                      v
               PILOTO 1–5
                      |
                      v
                  60 / 40
                      |
                      v
             CONSISTENCY CAP
                      |
                      v
             NIVEL DE MADUREZ
```

El resultado debe ser reproducible, auditable y separable de la Parte 1.
