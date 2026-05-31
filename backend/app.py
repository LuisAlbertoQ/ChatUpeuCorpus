import sqlite3
import csv
import io
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from rag_pipeline import generar_respuesta, inicializar
from config import MENSAJES
from logger import inicializar_bd, DB_PATH

app = FastAPI()

# Permitir peticiones desde el frontend (React en desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # o ["*"] para permitir todo en dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Consulta(BaseModel):
    pregunta: str

@app.on_event("startup")
async def startup_event():
    inicializar()
    inicializar_bd()
    print("Backend listo para recibir consultas.")

@app.post("/consulta")
async def consultar(consulta: Consulta):
    resultado = generar_respuesta(consulta.pregunta)
    return resultado

@app.get("/bienvenida")
async def bienvenida():
    return {"mensaje": MENSAJES["M01"]}

@app.get("/historial")
async def obtener_historial():
    """
    Devuelve el historial de interacciones en formato CSV.
    Útil para la evaluación de madurez (OE8).
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM interacciones")
        rows = cursor.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "pregunta", "respuesta", "fuentes", "tiempo_respuesta", "umbral_usado", "tipo_mensaje"])
    writer.writerows(rows)
    return {"csv": output.getvalue()}

@app.get("/documentos")
async def listar_documentos():
    from rag_pipeline import collection
    docs = collection.get()  # obtiene todos los chunks
    documentos = set(meta['documento'] for meta in docs['metadatas'])
    return {"documentos_en_corpus": sorted(list(documentos))}