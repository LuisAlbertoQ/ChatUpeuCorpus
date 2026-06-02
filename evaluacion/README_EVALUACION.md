# Evaluación de madurez del chatbot UPeU

Esta carpeta complementa el **OE8** del PPI: aplicar pruebas funcionales y piloto con usuarios, analizar resultados de desempeño, usabilidad y explicabilidad, y determinar el nivel de madurez del sistema según el modelo CMMI--TRL adaptado.

## Archivos

- `banco_preguntas.csv`: preguntas representativas para probar el chatbot.
- `evaluacion_respuestas.csv`: plantilla con puntajes del piloto o evaluación funcional.
- `calcular_madurez.py`: script que calcula puntajes por dimensión, puntaje global y nivel de madurez.
- `reporte_madurez.md`: se genera al ejecutar el script.
- `resultados_madurez.csv`: se genera al ejecutar el script.

## Dónde colocar esta carpeta

En el repositorio `ChatUpeuCorpus`, debe quedar así:

```text
ChatUpeuCorpus/
├── backend/
├── frontend/
├── llm/
├── vector_store/
├── docker-compose.yml
└── evaluacion/
    ├── banco_preguntas.csv
    ├── evaluacion_respuestas.csv
    ├── calcular_madurez.py
    └── README_EVALUACION.md
```

## Cómo ejecutar

Desde la carpeta `evaluacion/`:

```bash
python calcular_madurez.py
```

El script generará:

```text
reporte_madurez.md
resultados_madurez.csv
```

## Escala usada

Cada criterio se evalúa de 1 a 5:

- 1 = Muy deficiente
- 2 = Deficiente
- 3 = Regular
- 4 = Bueno
- 5 = Muy bueno

## Dimensiones calculadas

- Funcional
- Recuperación documental
- Explicabilidad y trazabilidad
- Usabilidad
- Gobernanza y uso responsable
- Preparación tecnológica y mejora

## Niveles de madurez

- 1.00–2.00 = Inicial
- 2.01–3.00 = Básico
- 3.01–4.00 = Gestionado
- 4.01–5.00 = Optimizado

## Nota importante

El script no reemplaza el juicio metodológico ni el piloto. Solo sistematiza los resultados de los instrumentos y ayuda a calcular el nivel de madurez de manera reproducible.
