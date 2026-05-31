import time
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
import chromadb
from sentence_transformers import SentenceTransformer
from config import *
from logger import registrar_interaccion

# Variables globales que se inicializarán en startup
client = None
collection = None
model = None

PROMPT = PromptTemplate(
    template=(
        "Eres un asistente universitario que responde preguntas sobre reglamentos, trámites y procedimientos para estudiantes de la Universidad Peruana Unión.\n\n"

        "Utiliza EXCLUSIVAMENTE los fragmentos proporcionados.\n"

        "Responde únicamente si los fragmentos contienen información específica y suficiente para responder exactamente la pregunta.\n"

        "Si la información no es suficiente o no corresponde a la pregunta, responde EXACTAMENTE:\n"
        "'No encontré información suficiente en los documentos disponibles para responder tu pregunta con confianza.'\n\n"

        "Reglas de formato:\n"
        "- Mantén la estructura original de la información cuando sea posible.\n"
        "- Si el contenido contiene listas, derechos, requisitos, pasos, categorías o elementos enumerados, preséntalos como lista con viñetas."
        "- No juntes todos los elementos en un solo párrafo.\n"
        "- Usa saltos de línea entre elementos.\n"
        "- Si hay artículos o numerales, indícalos junto a cada elemento.\n"
        "- No inventes información que no aparezca en los fragmentos.\n"
        "- Resume únicamente cuando no se pierda información relevante.\n\n"

        "No incluyas un apartado de 'Fuentes' o 'Referencias' al final de tu respuesta. "
        "El sistema agregará las fuentes automáticamente.\n\n"

        "Fragmentos:\n{context}\n\n"
        "Pregunta:\n{question}\n\n"
        "Respuesta:"
    ),
    input_variables=["context", "question"]
)

def inicializar():
    global client, collection, model
    client = chromadb.PersistentClient(path="./vector_store")
    collection = client.get_collection("corpus_upeu")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    print("Recursos RAG inicializados correctamente.")

def generar_respuesta(pregunta: str):
    inicio = time.time()
    
    # 1. Embedding
    embedding = model.encode([pregunta])[0].tolist()
    
    # 2. Búsqueda en ChromaDB
    resultados = collection.query(
        query_embeddings=[embedding],
        n_results=TOP_K_FRAGMENTOS
    )
    docs = resultados['documents'][0]
    metas = resultados['metadatas'][0]
    distancias = resultados['distances'][0]
    
    # 3. Filtrar por umbral de distancia coseno
    fragmentos_validos = []
    fuentes = []
    distancias_debug = [round(d, 4) for d in distancias]
    
    for doc, meta, dist in zip(docs, metas, distancias):
        if dist < UMBRAL_DISTANCIA_COSENO:
            fragmentos_validos.append(doc)
            fuentes.append(f"{meta['documento']}, {meta.get('categoria', '')}")
    
    # 4. Determinar tipo de mensaje y respuesta
    if not fragmentos_validos:
        tipo_mensaje = "M04"
        # Obtener el nombre del documento con la distancia más baja (aunque no pase el umbral)
        doc_sugerido = metas[0]['documento'] if metas else "generales de la UPeU"
        respuesta_final = MENSAJES["M04"].replace(
            "[nombre del documento relacionado más cercano]", doc_sugerido
        )
    else:
        tipo_mensaje = "M02"
        contexto = "\n\n".join(fragmentos_validos)
        prompt = PROMPT.format(context=contexto, question=pregunta)
        llm = Ollama(model="llama3", base_url="http://llm:11434")
        respuesta_generada = llm.invoke(prompt)
        respuesta_final = respuesta_generada + "\n\n" + MENSAJES["M02"] + "\n" + "\n".join(fuentes)
    
    tiempo_total = time.time() - inicio
    
    # 5. Registrar interacción
    registrar_interaccion(
        pregunta=pregunta,
        respuesta=respuesta_final,
        fuentes=fuentes,
        tiempo_respuesta=tiempo_total,
        umbral=UMBRAL_DISTANCIA_COSENO,
        tipo_mensaje=tipo_mensaje
    )
    
    # 6. Retornar resultado (incluye debug_distancias para validación)
    return {
        "respuesta": respuesta_final,
        "fuentes": fuentes,
        "tipo_mensaje": tipo_mensaje,
        "debug_distancias": distancias_debug
    }