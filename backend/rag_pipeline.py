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
    template="""Eres un asistente universitario. Responde la pregunta basándote ÚNICAMENTE en los siguientes fragmentos de documentos institucionales.
Si la información no está en los fragmentos, di que no puedes responder.

Fragmentos:
{context}

Pregunta: {question}

Respuesta (incluye al final las fuentes en formato: Documento: nombre, Sección: artículo, Año: año):
""",
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
    for doc, meta, dist in zip(docs, metas, distancias):
        if dist < UMBRAL_DISTANCIA_COSENO:
            fragmentos_validos.append(doc)
            fuentes.append(f"{meta['documento']}, {meta.get('categoria', '')}")
    
    if not fragmentos_validos:
        return {"respuesta": MENSAJES["M04"], "fuentes": []}
    
    # 4. Prompt y LLM
    contexto = "\n\n".join(fragmentos_validos)
    prompt = PROMPT.format(context=contexto, question=pregunta)
    llm = Ollama(model="llama3", base_url="http://llm:11434")
    respuesta_generada = llm.invoke(prompt)
    
    # 5. Formatear salida
    respuesta_final = f"{respuesta_generada}\n\nFuentes:\n" + "\n".join(fuentes)
    return {"respuesta": respuesta_final, "fuentes": fuentes}