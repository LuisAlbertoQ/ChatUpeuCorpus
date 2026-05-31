# Dominio permitido
DOMINIO_CATEGORIAS = ["D01", "D02", "D03", "D04", "D05", "D06"]

# Umbrales técnicos
UMBRAL_DISTANCIA_COSENO = 0.32   # Ajustado para equilibrar cobertura y precisión
TOP_K_FRAGMENTOS = 5
MAX_PALABRAS_RESPUESTA = 350
TIMEOUT_RESPUESTA = 15  # segundos (a implementar manejo de timeout)

# Mensajes de transparencia
MENSAJES = {
    "M01": "Hola, soy un asistente basado en IA generativa. Mis respuestas se fundamentan en documentos institucionales oficiales de la Universidad Peruana Unión (reglamentos, instructivos, cronogramas y lineamientos vigentes). Recuerda que mi función es informativa y no reemplaza la validación administrativa oficial. Si necesitas resolver un trámite personal, contacta directamente con la oficina correspondiente.",
    "M02": "Fuentes consultadas:",
    "M03": "Lo siento, solo puedo responder consultas sobre reglamentos académicos, procedimientos administrativos, cronogramas, bienestar estudiantil y normas de convivencia de la UPeU. Si tu consulta no pertenece a estos temas, te sugiero contactar con la oficina administrativa correspondiente.",
    "M04": "No encontré información suficiente en los documentos institucionales disponibles para responder tu pregunta con confianza. Te sugiero revisar directamente el documento [nombre del documento relacionado más cercano] o contactar con la oficina correspondiente.",
    "M05": "No entendí claramente tu pregunta. ¿Podrías reformularla con más detalles? Por ejemplo, indica el tipo de trámite, el documento o el procedimiento específico que te interesa.",
    "M06": "Ocurrió un error al procesar tu consulta. Por favor, inténtalo de nuevo más tarde. Si el problema persiste, contacta con soporte técnico a [correo o formulario].",
    "M07": "Respuesta generada por inteligencia artificial. La UPeU no se hace responsable por el uso indebido de la información. Verifica con fuentes oficiales cuando sea necesario."
}