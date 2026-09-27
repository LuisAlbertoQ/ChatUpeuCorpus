# Procedimiento de campo — Piloto OE8 (instrumento v1)

1. Asignar a cada participante un ID anónimo (p. ej. `P-001`). No registrar nombre, DNI, correo ni teléfono.
2. Permitir el uso real del chatbot (consultas institucionales típicas).
3. Presentar los 30 ítems de `instrumento_piloto_oe8_v1.json` (escala 1–5).
4. Registrar cada respuesta en `plantilla_piloto.csv` (una fila por ítem).
5. Verificar 30/30 respuestas por participante antes de cerrar su ficha.
6. Exportar el CSV y validar: `python evaluacion/madurez_oe8/importar_piloto.py evaluacion/madurez_oe8/respuestas_piloto.csv`.
7. Si hay errores, corregir el archivo (no la BD) y reintentar.

Reglas:
- Válido para promedio oficial: participante con 30/30. Incompletos se conservan marcados, sin imputación.
- No indicar respuestas “correctas” ni sesgar.
- TAMAÑO MUESTRAL DEL PILOTO: PENDIENTE DE DEFINICIÓN.
