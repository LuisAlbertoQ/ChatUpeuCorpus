# PARTE 2 — IMPLEMENTACIÓN Y MEJORA DEL CHATBOT RAG UPeU

## 0. Propósito del documento

Este documento es la especificación técnica para implementar y mejorar la **Parte 2: Chatbot RAG de la UPeU**.

El proyecto ya cuenta con una **Parte 1 — construcción del corpus y base vectorial**, la cual se considera implementada y funcional.

El objetivo de esta etapa NO es reconstruir el corpus.

El objetivo es mejorar el flujo de consulta para que:

1. El usuario realice una pregunta.
2. El sistema valide la pregunta.
3. Se genere el embedding.
4. ChromaDB recupere los fragmentos relevantes.
5. Los resultados sean ordenados/rankeados.
6. Se aplique un umbral configurable.
7. Se construya explícitamente el contexto.
8. El LLM genere una respuesta únicamente utilizando el contexto recuperado.
9. Las fuentes sean construidas de manera determinística desde los metadatos recuperados.
10. Se apliquen guardrails.
11. Se registre toda la información necesaria para evaluación posterior.
12. El frontend muestre respuesta, fuentes y métricas de forma clara.

---

# 1. RESTRICCIONES IMPORTANTES

## 1.1 No modificar la Parte 1

La Parte 1 ya está implementada.

NO modificar salvo que exista una dependencia estrictamente necesaria:

* extracción de documentos;
* OCR;
* limpieza;
* normalización;
* detección de estructura;
* chunking;
* generación de embeddings;
* modelo MPNet;
* colección ChromaDB existente;
* documentos ya procesados;
* metadata ya almacenada.

NO reconstruir el corpus.

NO volver a generar embeddings en cada consulta.

NO reemplazar ChromaDB.

NO reemplazar MPNet.

NO cambiar el modelo LLM salvo indicación explícita.

---

# 2. ESTADO ACTUAL CONOCIDO

La implementación actual utiliza aproximadamente:

* Frontend: React + nginx.
* Backend: FastAPI.
* Vector DB: ChromaDB.
* Embeddings: MPNet, 768 dimensiones.
* Colección: `corpus_upeu_mpnet`.
* LLM: Qwen 2.5 7B mediante Ollama.
* Comunicación con Ollama: HTTP `/api/generate`.
* `TOP_K_RAW = 15`.
* `TOP_K_FRAGMENTOS = 4`.
* Threshold inicial: `distance < 0.40`.
* Keyword boost aproximado: `+0.07` por coincidencia.
* Temperatura LLM: `0.2`.
* `num_predict`: `1024`.
* Timeout aproximado: `50s`.
* Reintentos: HTTP 5xx, máximo 3 con backoff.
* Persistencia de interacciones: SQLite.

Estos valores son configuraciones iniciales y deben permanecer configurables.

NO tratarlos como valores universalmente óptimos.

---

# 3. FLUJO OBJETIVO

El flujo de consulta debe quedar conceptualmente así:

```text
USUARIO
   |
   v
PREGUNTA
   |
   v
PREPROCESAMIENTO
   |
   v
VALIDACIONES
   |
   +---- M03 / M05 si corresponde
   |
   v
EMBEDDING MPNet
   |
   v
CHROMADB
   |
   | TOP 15 RAW
   v
RANKING / SCORING
   |
   | keyword boost / reranking
   v
TOP 4
   |
   v
FILTRO POR THRESHOLD
   |
   +---- 0 resultados -> M04
   |
   v
CONSTRUCTOR DE CONTEXTO
   |
   v
PROMPT RAG
   |
   v
QWEN 2.5 7B
   |
   v
POSTPROCESAMIENTO
   |
   v
GUARDRAILS
   |
   +--------------------+
   |                    |
   v                    v
RESPUESTA            FUENTES
   |                    |
   +----------+---------+
              |
              v
         RESPUESTA JSON
              |
              v
           FRONTEND
```

---

# 4. MENSAJES DEL SISTEMA

Mantener los tipos existentes:

```text
M01 = Bienvenida / inicial
M02 = Respuesta válida con fuentes
M03 = Fuera de alcance / rechazo
M04 = Sin cobertura
M05 = Pregunta ambigua / inválida / multi-intención
M06 = Error técnico
M07 = Disclaimer IA
M08 = Límite de sesión
```

No es necesario crear nuevos mensajes públicos.

Sin embargo, internamente se deben registrar subtipos.

## 4.1 M03

Agregar:

```text
failure_reason:
- out_of_domain
- sensitive_request
```

## 4.2 M04

Agregar:

```text
failure_reason:
- retrieval_no_coverage
- generation_empty
```

## 4.3 M05

Agregar:

```text
validation_reason:
- too_short
- ambiguous
- multi_intent
```

## 4.4 M06

Agregar:

```text
error_type:
- timeout
- http_5xx
- exception
```

Esto permite analizar posteriormente las causas de fallo.

---

# 5. PREPROCESAMIENTO

Mantener:

```text
pregunta_original
        |
        v
strip()
        |
        v
normalización
        |
        v
pregunta_normalizada
```

Registrar ambas:

```text
pregunta
pregunta_normalizada
```

No modificar semánticamente la pregunta de forma agresiva.

---

# 6. VALIDACIÓN

Las validaciones actuales deben mantenerse:

```text
_pregunta_es_ambigua()
_es_multi_intencion()
_es_etica_sensible()
_es_fuera_dominio_por_keywords()
```

Estas validaciones actualmente funcionan sin LLM.

No sustituirlas automáticamente por un LLM.

Registrar:

```text
validation_reason
```

cuando una validación bloquee la consulta.

---

# 7. RETRIEVAL

## 7.1 Embedding

Utilizar el modelo MPNet ya existente.

Registrar:

```text
embedding_model
embedding_dimension
embedding_latency_ms
```

No generar embeddings para documentos nuevamente durante la consulta.

---

# 8. CHROMADB

Realizar:

```text
Pregunta
   |
   v
Embedding
   |
   v
ChromaDB
   |
   v
TOP_K_RAW = 15
```

Mantener inicialmente:

```text
TOP_K_RAW = 15
```

pero convertirlo en configuración:

```text
RAG_TOP_K_RAW
```

---

# 9. RANKING

La implementación actual posee un boost por keywords:

```text
+0.07 por coincidencia
```

Mantenerlo inicialmente si ya funciona.

Sin embargo, documentarlo como:

```text
heuristic keyword scoring / keyword boost
```

NO llamarlo automáticamente "reranker" si no existe un modelo específico de reranking.

El ranking debe ser reproducible.

Registrar:

```text
ranking_method
ranking_version
```

---

# 10. TOP-K FINAL

Mantener inicialmente:

```text
TOP_K_FRAGMENTOS = 4
```

pero hacerlo configurable:

```text
RAG_TOP_K_FINAL
```

Flujo:

```text
Chroma TOP 15
      |
      v
Ranking
      |
      v
TOP 4
```

---

# 11. THRESHOLD

Mantener inicialmente:

```text
distance < 0.40
```

pero hacerlo configurable:

```text
RAG_DISTANCE_THRESHOLD
```

El valor 0.40 NO debe considerarse óptimo por definición.

Debe poder probarse posteriormente:

```text
0.30
0.35
0.40
0.45
0.50
```

La evaluación de estas configuraciones corresponde a la Parte 3.

Registrar siempre:

```text
threshold_used
```

---

# 12. CONSTRUCTOR DE CONTEXTO

Esta es una de las principales mejoras requeridas.

Crear una función conceptual:

```text
construir_contexto(resultados)
```

El constructor debe transformar los fragmentos recuperados en un contexto estructurado para el LLM.

Cada fragmento debe contener, cuando exista:

```text
chunk_id
document_id
document_title
document_type
category
version
status
chapter
section
article
page
text
distance
```

Ejemplo conceptual:

```text
FUENTE 1
Documento: REGLAMENTO BECAS 2021 ACTUALIZADO.pdf
Categoría: Becas
Artículo: 49°
Página: 18
Chunk ID: becas_2021_art49_01

CONTENIDO:
[texto del fragmento]
```

Después:

```text
FUENTE 2
Documento: REGLAMENTO BECAS 2021 ACTUALIZADO.pdf
Categoría: Becas
Artículo: 61°
Página: 21
Chunk ID: becas_2021_art61_01

CONTENIDO:
[texto del fragmento]
```

---

# 13. REGLAS DEL CONTEXTO

El contexto debe:

1. Mantener el texto original recuperado.
2. Mantener metadata.
3. Identificar claramente cada fuente.
4. Evitar mezclar metadata con contenido de forma ambigua.
5. Mantener el orden de relevancia.
6. No incluir chunks descartados por threshold.
7. No incluir información externa al corpus.
8. Permitir identificar posteriormente qué chunk originó una afirmación.

---

# 14. PROMPT RAG

El prompt debe indicar explícitamente:

```text
- Responde únicamente con información contenida en el contexto.
- No inventes información.
- Si el contexto no contiene la respuesta, indícalo.
- No utilices conocimiento externo.
- Prioriza la información directamente relacionada con la pregunta.
- No agregues información secundaria innecesaria.
- No inventes documentos, artículos, páginas ni fuentes.
```

El prompt debe recibir:

```text
PREGUNTA
+
CONTEXTO
```

Registrar:

```text
prompt_version
```

No guardar necesariamente el prompt completo si contiene información innecesaria para auditoría.

---

# 15. REGLA FUNDAMENTAL DE FUENTES

Las fuentes NO deben depender de lo que escriba el LLM.

La arquitectura debe ser:

```text
                    ┌──> CONTEXTO ──> QWEN ──> RESPUESTA
                    |
Pregunta -> Retrieval
                    |
                    └──> METADATA ──> FUENTES
```

Por lo tanto:

```text
fuentes = construir_fuentes(resultados_validos)
```

Las fuentes deben obtenerse de los metadatos de los fragmentos recuperados.

El LLM puede mencionar:

```text
Artículo 49°
```

pero el sistema debe validar que ese artículo realmente está presente en los resultados recuperados.

---

# 16. GUARDRAILS

Mantener los guardrails existentes.

## 16.1 `_validar_encuadre()`

Puede permanecer.

Su función es detectar referencias a documentos que no están presentes en las fuentes.

## 16.2 `_reparar_citas()`

Puede permanecer como mecanismo de corrección.

Pero NO debe ser el mecanismo principal para construir las fuentes.

Prioridad:

```text
1. Metadata retrieval
2. Validación
3. Corrección determinística
4. LLM únicamente para contenido
```

---

# 17. RESPUESTA SIN COBERTURA

Si:

```text
num_valid_chunks == 0
```

devolver:

```text
M04
failure_reason = retrieval_no_coverage
```

Si el retrieval sí encontró información pero el LLM devuelve vacío:

```text
M04
failure_reason = generation_empty
```

No mezclar ambas causas internamente.

---

# 18. SCORE MOSTRADO EN FRONTEND

Actualmente existe una visualización del tipo:

```text
84% afinidad
```

basada en:

```text
(1 - distance) * 100
```

No presentar este valor como una probabilidad de corrección.

Preferir:

```text
Relevancia: ...
```

o:

```text
Similitud: ...
```

según la métrica utilizada.

Si se muestra un porcentaje, documentar exactamente cómo se calcula y verificar que el rango sea interpretable.

NO presentar "84% de certeza".

---

# 19. REGISTRO DE INTERACCIONES

La tabla `interacciones` debe permitir reconstruir qué ocurrió en una consulta.

Agregar o mantener los siguientes campos cuando sea compatible con la implementación:

```text
id
timestamp
sesion_id

pregunta
pregunta_normalizada
respuesta

tipo_mensaje
failure_reason
validation_reason
error_type

top_k_raw
top_k_final
threshold_used
num_valid_chunks

retrieved_chunk_ids
retrieved_document_ids
retrieved_articles
retrieved_distances

fuentes
citation_validation

embedding_model
llm_model
prompt_version
corpus_version
ranking_version

embedding_latency_ms
retrieval_latency_ms
llm_latency_ms
total_latency_ms

http_status
```

No almacenar información personal innecesaria.

---

# 20. VERSIONADO

El sistema debe poder registrar:

```text
corpus_version
embedding_model
llm_model
prompt_version
ranking_version
```

Esto es importante para reproducibilidad.

Una evaluación realizada con:

```text
corpus_v1
MPNet
Qwen2.5:7b
prompt_v1
threshold=0.40
```

debe poder distinguirse de otra evaluación posterior.

---

# 21. API

Mantener:

```text
POST /consulta
```

La respuesta debe conservar compatibilidad con el frontend actual.

Estructura conceptual:

```json
{
  "respuesta": "...",
  "fuentes": [],
  "tipo_mensaje": "M02",
  "tiempo": 24.06,
  "debug_distancias": [],
  "preguntas_restantes": 9,
  "sesion_id": "..."
}
```

Se pueden agregar campos nuevos si no rompen el frontend:

```json
{
  "retrieval": {
    "top_k_raw": 15,
    "top_k_final": 4,
    "num_valid_chunks": 4
  }
}
```

Los campos de debug no deben exponerse innecesariamente al usuario final.

---

# 22. FRONTEND

Mantener:

* React.
* ReactMarkdown.
* remark-gfm.
* SourceBadge.

El frontend debe mostrar:

```text
Respuesta
   |
   +-- Fuentes
       |
       +-- Documento
       +-- Artículo
       +-- Página si existe
       +-- Score/relevancia
```

No mostrar información técnica excesiva al usuario normal.

---

# 23. EJEMPLO ESPERADO

Pregunta:

```text
¿Cómo solicito una beca en la UPeU?
```

Retrieval:

```text
TOP 15
   |
   v
ranking
   |
   v
TOP 4

1. Artículo 49°
2. Artículo 61°
3. Artículo 45°
4. Artículo 11°
```

Después:

```text
threshold
   |
   v
4 chunks válidos
```

Constructor:

```text
Contexto
 ├── Fuente 1: Art.49
 ├── Fuente 2: Art.61
 ├── Fuente 3: Art.45
 └── Fuente 4: Art.11
```

Qwen:

```text
genera respuesta
```

Fuentes:

```text
se construyen directamente
desde los 4 resultados recuperados
```

---

# 24. CRITERIOS DE ACEPTACIÓN

La Parte 2 se considera implementada cuando:

### Retrieval

* [ ] Se mantiene ChromaDB existente.
* [ ] Se genera embedding con MPNet.
* [ ] Se recuperan inicialmente 15 candidatos.
* [ ] Existe ranking configurable.
* [ ] Se seleccionan inicialmente 4 fragmentos.
* [ ] El threshold es configurable.
* [ ] Se registra el threshold usado.

### Contexto

* [ ] Existe `construir_contexto()`.
* [ ] El contexto contiene texto + metadata.
* [ ] Cada fuente tiene identificador.
* [ ] Los chunks descartados no llegan al LLM.

### Generación

* [ ] Qwen recibe pregunta + contexto.
* [ ] El prompt prohíbe inventar información.
* [ ] Existe versión del prompt.
* [ ] La respuesta puede abstenerse si no hay cobertura.

### Fuentes

* [ ] Las fuentes se generan desde metadata.
* [ ] El LLM no controla las fuentes.
* [ ] Las citas pueden validarse.
* [ ] Los guardrails permanecen.

### Registro

* [ ] Se registra retrieval.
* [ ] Se registran chunks recuperados.
* [ ] Se registran distancias.
* [ ] Se registra latencia.
* [ ] Se registra configuración.
* [ ] Se registra versión.

### Frontend

* [ ] Respuesta Markdown funciona.
* [ ] Tablas funcionan.
* [ ] Fuentes funcionan.
* [ ] El score se muestra de forma no engañosa.

---

# 25. NO HACER TODAVÍA

No implementar en esta etapa:

* GraphRAG.
* Cambio de vector DB.
* Cambio de embedding.
* Reprocesamiento masivo del corpus.
* Agentes autónomos.
* Búsqueda web.
* Fine-tuning del LLM.
* Reranker complejo si no es necesario.
* Cambios en chunking de la Parte 1.

Primero hacer funcionar y medir correctamente el RAG existente.

---

# 26. ORDEN DE IMPLEMENTACIÓN

Implementar en este orden:

```text
FASE 1
Analizar código existente
        ↓
Identificar archivos y funciones
        ↓
No modificar todavía
```

```text
FASE 2
Crear/implementar construir_contexto()
        ↓
Probar contexto
```

```text
FASE 3
Separar construcción de fuentes del LLM
        ↓
Probar trazabilidad
```

```text
FASE 4
Convertir TOP_K y threshold en configuración
        ↓
Probar diferentes valores
```

```text
FASE 5
Mejorar logging
        ↓
Probar SQLite
```

```text
FASE 6
Ajustar frontend
        ↓
Probar respuesta + fuentes
```

```text
FASE 7
Pruebas funcionales
        ↓
Entregar Parte 2
```

---

# 27. INSTRUCCIÓN PARA EL AGENTE DE PROGRAMACIÓN

Antes de modificar código:

1. Leer este documento completo.
2. Inspeccionar el repositorio.
3. Identificar:

   * archivo principal del RAG;
   * endpoint `/consulta`;
   * funciones de retrieval;
   * funciones de ranking;
   * funciones de guardrails;
   * modelo de datos SQLite;
   * frontend relacionado con fuentes;
   * configuración actual.
4. Presentar un plan de cambios.
5. NO modificar la Parte 1.
6. NO ejecutar cambios masivos sin validar primero.
7. Implementar por fases.
8. Ejecutar pruebas después de cada fase.
9. Mantener compatibilidad con la API existente.
10. Documentar los archivos modificados.

El agente NO debe asumir que las funciones o nombres descritos en este documento existen exactamente.

Debe localizar primero la implementación real del proyecto.

---

# 28. RESULTADO FINAL ESPERADO

El resultado debe ser un chatbot RAG UPeU con:

```text
Pregunta
   ↓
Validación
   ↓
MPNet
   ↓
ChromaDB
   ↓
Top 15
   ↓
Ranking
   ↓
Top 4
   ↓
Threshold
   ↓
Context Builder
   ↓
Qwen
   ↓
Guardrails
   ↓
Respuesta
   +
Fuentes determinísticas
   ↓
Registro completo
```

La Parte 2 debe quedar preparada para ser evaluada posteriormente por la Parte 3.
