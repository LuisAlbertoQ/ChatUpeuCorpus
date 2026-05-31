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