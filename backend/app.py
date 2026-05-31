from fastapi import FastAPI
from pydantic import BaseModel
from rag_pipeline import generar_respuesta, inicializar
from config import MENSAJES

app = FastAPI()

class Consulta(BaseModel):
    pregunta: str

@app.on_event("startup")
async def startup_event():
    inicializar()

@app.post("/consulta")
async def consultar(consulta: Consulta):
    resultado = generar_respuesta(consulta.pregunta)
    return resultado

@app.get("/bienvenida")
async def bienvenida():
    return {"mensaje": MENSAJES["M01"]}

@app.get("/documentos")
async def listar_documentos():
    from rag_pipeline import collection
    docs = collection.get()  # obtiene todos los chunks
    documentos = set(meta['documento'] for meta in docs['metadatas'])
    return {"documentos_en_corpus": sorted(list(documentos))}