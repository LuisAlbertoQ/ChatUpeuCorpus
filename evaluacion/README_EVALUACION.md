# Evaluación de madurez del chatbot UPeU

Esta carpeta implementa la **evaluación automática de madurez** del
chatbot (OE8) según el modelo **CMMI--TRL adaptado** descrito en el
PPI. A partir de esta versión, el sistema **se conecta directamente
a `registro_interacciones.db`**; no utiliza puntajes manuales en CSV.

## Modelo de madurez

Seis dimensiones evaluadas en escala Likert 1--5:

1. **Funcional** — capacidad de responder consultas frecuentes.
2. **Recuperación documental** — uso del corpus institucional.
3. **Explicabilidad y trazabilidad** — presencia y claridad de fuentes.
4. **Usabilidad** — tiempo de respuesta, fluidez.
5. **Gobernanza y uso responsable** — delimitación de dominio, datos.
6. **Preparación tecnológica y mejora** — estabilidad, métricas, mejora.

Cuatro niveles posibles: **Inicial**, **Básico**, **Gestionado**,
**Optimizado**.

## Fuentes de datos

Toda la información proviene de `registro_interacciones.db` (SQLite):

| Tabla | Origen | Uso |
|---|---|---|
| `interacciones` | Log automático del chatbot (cada consulta) | Métricas base: % M02, % M06, tiempo, fuentes |
| `banco_preguntas` | Banco canónico de preguntas de prueba | Validar cobertura del banco |
| `evaluacion_piloto` | Puntajes Likert 1--5 de usuarios reales | Combinar con métricas automáticas |
| `evaluacion_automatica` | Snapshots históricos de madurez | Tendencia en el tiempo |

## Cálculo del puntaje final

Cada dimensión combina dos fuentes con pesos fijos:

```
P_final = 0.6 × P_automático + 0.4 × P_piloto
```

Si no hay datos de piloto, se usa solo el automático
(`P_final = P_automático`).

### Mapeo de métricas a puntajes automáticos

| Dimensión | Métrica base | Regla de mapeo a 1--5 |
|---|---|---|
| Funcional | % M02 | ≥90→5, ≥75→4, ≥50→3, ≥25→2, <25→1 |
| Recuperación documental | % con fuentes | ≥90→5, ≥75→4, ≥50→3, ≥25→2 |
| Explicabilidad | % con fuentes | ≥95→5, ≥80→4, ≥60→3, ≥40→2 |
| Usabilidad | Tiempo promedio (s) | ≤10→5, ≤20→4, ≤30→3, ≤40→2 |
| Gobernanza | % M03 + M05 | 5--30%→5 (detecta bien), <5%→3, >30%→2 |
| Preparación | 1 -- % M06 | ≥98%→5, ≥95%→4, ≥90%→3, ≥80%→2 |

## Regla de consistencia

El nivel global **no puede superar en más de un nivel** al valor
mínimo de las cinco dimensiones críticas: Funcional, Recuperación
documental, Explicabilidad y trazabilidad, Gobernanza, Preparación
tecnológica.

## Archivos

| Archivo | Descripción | Origen |
|---|---|---|
| `INSTRUMENTOS.md` | 5 instrumentos del OE6 (ficha, cotejo, gobernanza, rúbrica, SUS) | Manual |
| `calcular_madurez.py` | Lee DB, calcula puntajes, genera reportes. | Script |
| `generar_ficha.py` | Genera `ficha_documental.md` desde DB + ChromaDB. | Script |
| `migrar_banco.py` | [YA EJECUTADO] One-shot: importa `banco_preguntas.csv` a la DB. | Script (idempotente) |
| `migrar_esquema_vector_store.py` | [YA EJECUTADO] One-shot: añade columnas `topic` si el vector store fue migrado a chromadb 1.x. | Script (idempotente) |
| `ficha_documental.md` | Deliverable (corpus indexado). Se regenera con `generar_ficha.py`. | Auto-generado |
| `reporte_madurez.md` | Deliverable. Se regenera con `calcular_madurez.py`. | Auto-generado |
| `resultados_madurez.csv` | Deliverable. Se regenera con `calcular_madurez.py`. | Auto-generado |

## Flujo de trabajo

> **Importante:** este proyecto es **100% Docker**. Los scripts de
> evaluación que necesitan `chromadb` (`generar_ficha.py`) deben
> ejecutarse **dentro del contenedor backend**, no en el host.
> Los que solo usan `sqlite3` (`migrar_banco.py`,
> `calcular_madurez.py`) pueden correr en el host.

### 1. Inicialización (una sola vez)

Asegurarse de que las tablas existen en la DB. El backend las crea
automáticamente al arrancar, pero también pueden crearse manualmente:

```bash
docker compose restart backend
```

### 2. Migrar el banco de preguntas (ya ejecutado)

**Nota: este paso ya se ejecutó en junio 2026.** Si reinstalas el sistema
desde cero y tienes el CSV original, puedes migrarlo así:

```bash
cd evaluacion
python migrar_banco.py
```

Esto inserta las preguntas en la tabla `banco_preguntas` de la DB.
Tras verificar la migración, `banco_preguntas.csv` puede eliminarse.

### 3. Cargar puntajes del piloto (cuando aplique)

Los puntajes Likert 1-5 de usuarios reales se insertan directamente
en `evaluacion_piloto`. Puede hacerse desde un formulario web, una
encuesta exportada a CSV, o directamente con SQL:

```sql
INSERT INTO evaluacion_piloto
(sesion_id, pregunta_id, timestamp_inicio, funcional, recuperacion,
 explicabilidad, usabilidad, gobernanza, preparacion, observacion)
VALUES
('anonimizado', 'P01', '2026-06-02T10:00:00', 5, 5, 4, 4, 5, 4,
 'Respuesta clara y con fuente');
```

### 4. Generar la ficha documental (dentro del contenedor)

```bash
docker compose run --rm backend python /data/evaluacion/generar_ficha.py
```

El script escribe `evaluacion/ficha_documental.md` en el host
(el volumen `./evaluacion:/data/evaluacion` propaga los cambios).

### 5. Calcular la madurez (host o contenedor)

En el host:

```bash
cd evaluacion
python calcular_madurez.py
```

O dentro del contenedor:

```bash
docker compose run --rm backend python /data/evaluacion/calcular_madurez.py
```

El script:

1. Lee `interacciones` y calcula métricas crudas.
2. Convierte métricas a puntajes 1--5 por dimensión.
3. Si hay datos de `evaluacion_piloto`, los promedia y combina
   (60% auto + 40% piloto).
4. Aplica la regla de consistencia (cap por dimensión crítica).
5. Guarda snapshot en `evaluacion_automatica`.
6. Genera `reporte_madurez.md` y `resultados_madurez.csv`.

## Salidas

### `reporte_madurez.md`

Reporte ejecutivo con:
- Resumen (interacciones, piloto, puntaje global, nivel)
- Métricas crudas (% M02, % M06, tiempo, fuentes)
- Tabla de puntajes por dimensión (auto, piloto, final, nivel)
- Interpretación automática
- Regla de consistencia aplicada

### `resultados_madurez.csv`

Tabla plana con puntajes por dimensión y resumen global.
Apto para importar a Excel o alimentar análisis estadístico.

### Tabla `evaluacion_automatica`

Un INSERT por ejecución con `periodo = 'YYYY-MM'`. Permite ver
tendencia histórica:

```sql
SELECT periodo, total_interacciones, puntaje_global_calculado
FROM evaluacion_automatica
ORDER BY periodo;
```

## Escala usada

Cada criterio se evalúa de 1 a 5:

- 1 = Muy deficiente
- 2 = Deficiente
- 3 = Regular
- 4 = Bueno
- 5 = Muy bueno

## Niveles de madurez (rangos)

| Rango | Nivel | Interpretación |
|---|---|---|
| 1.00--2.00 | Inicial | Desarrollo incipiente, funcionamiento parcial. |
| 2.01--3.00 | Básico | Avances funcionales, limitaciones en cobertura. |
| 3.01--4.00 | Gestionado | Respuestas sustentadas, mecanismos de control. |
| 4.01--5.00 | Optimizado | Explicabilidad verificable, monitoreo, mejora continua. |

## Nota metodológica

El script no reemplaza el juicio metodológico ni el piloto. Solo
sistematiza los resultados de los instrumentos y ayuda a calcular
el nivel de madurez de manera reproducible, basándose en datos
reales de uso del chatbot.
