# Dominio permitido
DOMINIO_CATEGORIAS = ["D01", "D02", "D03", "D04", "D05", "D06"]  # etc.

# Umbrales técnicos
UMBRAL_SIMILITUD = 0.7  # coseno (en realidad distancia < 0.3)
TOP_K_FRAGMENTOS = 5
MAX_PALABRAS_RESPUESTA = 350
TIMEOUT_RESPUESTA = 15  # segundos
UMBRAL_DISTANCIA_COSENO = 0.32  # equivalente a similitud >= 0.7

# Mensajes
MENSAJES = {
    "M01": "Hola, soy un asistente basado en IA generativa. Mis respuestas se fundamentan en documentos institucionales oficiales de la Universidad Peruana Unión (reglamentos, instructivos, cronogramas y lineamientos vigentes). Recuerda que mi función es informativa y no reemplaza la validación administrativa oficial. Si necesitas resolver un trámite personal, contacta directamente con la oficina correspondiente.",
    "M02": "Fuente(s): [nombre del documento, versión y año] _ [enlace al documento si está disponible públicamente]",
    "M03": "Lo siento, solo puedo ayudarte con consultas sobre reglamentos académicos, procedimientos administrativos, cronogramas, bienestar estudiantil y normas de convivencia de la UPeU. Tu pregunta está fuera de mi alcance. Si necesitas información personalizada o confidencial, te recomiendo acudir a la oficina de [nombre de oficina según contexto].",
    "M04": "No encontré información suficiente en los documentos institucionales disponibles para responder tu pregunta con confianza. Te sugiero revisar directamente el documento [nombre del documento relacionado más cercano] o contactar con la [oficina correspondiente] para una respuesta precisa.",
    "M05": "No entendí claramente tu pregunta. ¿Podrías reformularla con más detalles? Por ejemplo, indica el tipo de trámite, el documento o el procedimiento específico que te interesa.",
    "M06": "Ocurrió un error al procesar tu consulta. Por favor, inténtalo de nuevo más tarde. Si el problema persiste, contacta con soporte técnico a [correo o formulario].",
    "M07": "Respuesta generada por inteligencia artificial. La UPeU no se hace responsable por el uso indebido de la información. Verifica con fuentes oficiales cuando sea necesario."
}