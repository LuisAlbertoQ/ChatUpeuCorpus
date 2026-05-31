from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
import chromadb
from sentence_transformers import SentenceTransformer
from config import *

# Variables globales que se inicializarán en startup
client = None
collection = None
model = None
PROMPT = PromptTemplate(
    template=(
        "Eres un asistente universitario que responde preguntas sobre reglamentos, trámites y procedimientos para ESTUDIANTES de la Universidad Peruana Unión.\n"
        "Utiliza EXCLUSIVAMENTE los fragmentos de documentos institucionales que se te proporcionan a continuación.\n"
        "Responde ÚNICAMENTE si los fragmentos contienen información específica y suficiente para responder EXACTAMENTE lo que el usuario pregunta.\n"
        "Si la información no es suficiente o no corresponde a lo preguntado, responde EXACTAMENTE con este texto: 'No encontré información suficiente en los documentos disponibles para responder tu pregunta con confianza.'\n"
        "No agregues ninguna otra frase, ni sugerencias, ni detalles adicionales en ese caso.\n"
        "Si decides responder, sé conciso y menciona las fuentes.\n\n"
        "Fragmentos:\n{context}\n\n"
        "Pregunta: {question}\n\n"
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
    # 1. Embedding
    embedding = model.encode([pregunta])[0].tolist()
    # 2. Búsqueda
    resultados = collection.query(
        query_embeddings=[embedding],
        n_results=TOP_K_FRAGMENTOS
    )
    docs = resultados['documents'][0]
    metas = resultados['metadatas'][0]
    distancias = resultados['distances'][0]
    
    # 3. Filtrar por umbral
    fragmentos_validos = []
    fuentes = []
    distancias_debug = []
    for doc, meta, dist in zip(docs, metas, distancias):
        distancias_debug.append(round(dist, 4))
        if dist < UMBRAL_DISTANCIA_COSENO:
            fragmentos_validos.append(doc)
            fuentes.append(f"{meta['documento']}, {meta.get('categoria', '')}")
    
    if not fragmentos_validos:
        return {
            "respuesta": MENSAJES["M04"], 
            "fuentes": [],
            "debug_distancias": distancias_debug}
    
    # 4. Prompt y LLM
    contexto = "\n\n".join(fragmentos_validos)
    prompt = PROMPT.format(context=contexto, question=pregunta)
    llm = Ollama(model="llama3", base_url="http://llm:11434")
    respuesta_generada = llm.invoke(prompt)
    
    # 5. Formatear salida
    respuesta_final = respuesta_generada + "\n\n" + MENSAJES["M02"] + "\n" + "\n".join(fuentes)
    return {
        "respuesta": respuesta_final, 
        "fuentes": fuentes,
        "debug_distancias": distancias_debug}