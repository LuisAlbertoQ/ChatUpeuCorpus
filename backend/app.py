"""API HTTP del sistema conversacional UPeU (FastAPI).

Endpoints públicos:
  POST   /consulta                Pipeline RAG → respuesta + fuentes.
  GET    /bienvenida              Mensaje M01 (sección 4 OE4).
  GET    /historial               Exporta CSV (opcional ?sesion_id=).
  DELETE /historial/{sesion_id}   Borra interacciones de una sesión (sección 3.4).
  GET    /documentos              Lista los documentos indexados en el corpus.
  GET    /politica-privacidad     Texto de la política (sección 3.3, Ley 29733).
  GET    /salud                   Healthcheck para Docker / monitoreo.
  GET    /config-publica          Parámetros visibles para el frontend.
"""

import csv
import io
import logging
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from config import (
    ALLOWED_ORIGINS,
    DOMINIO_CATEGORIAS,
    LIMITE_PREGUNTAS_SESION,
    MAPEO_CATEGORIAS,
    MAX_PALABRAS_RESPUESTA,
    MENSAJES,
    MODO_PILOTO,
    TIMEOUT_RESPUESTA,
    TOP_K_FRAGMENTOS,
    UMBRAL_DISTANCIA_COSENO,
)
from logger import (
    DB_PATH,
    contar_preguntas_sesion,
    eliminar_por_sesion,
    inicializar_bd,
)
from rag_pipeline import generar_respuesta, inicializar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("api")


# -----------------------------------------------------------------------------
# Lifespan (FastAPI moderno reemplaza @app.on_event)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Inicializando recursos…")
    inicializar()
    inicializar_bd()
    log.info("Backend listo para recibir consultas.")
    yield
    log.info("Backend detenido.")


app = FastAPI(
    title="Chatbot UPeU – Sistema conversacional OE5",
    version="2.0.0",
    description=(
        "Sistema conversacional con IA generativa explicable y trazabilidad "
        "documental. Cumple con el documento OE4 v2.0."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Schemas (Pydantic) — validación estricta
# -----------------------------------------------------------------------------
class Consulta(BaseModel):
    pregunta: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pregunta del usuario en lenguaje natural.",
    )
    sesion_id: str = Field(
        default="",
        max_length=64,
        description="UUID generado por el cliente para agrupar la sesión (T07).",
    )


class RespuestaConsulta(BaseModel):
    respuesta: str
    fuentes: list[str]
    tipo_mensaje: str
    tiempo_respuesta: float
    preguntas_restantes: int | None = None
    debug_distancias: list[float] | None = None


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/salud", tags=["infra"])
async def salud():
    """Healthcheck simple para Docker / proxy inverso."""
    return {"status": "ok", "modo_piloto": MODO_PILOTO}


@app.get("/bienvenida", tags=["transparencia"])
async def bienvenida():
    """M01 — texto exacto del aviso inicial."""
    return {"mensaje": MENSAJES["M01"]}


@app.get("/config-publica", tags=["infra"])
async def config_publica():
    """Parámetros que el frontend necesita conocer (sin secretos)."""
    return {
        "modo_piloto": MODO_PILOTO,
        "limite_preguntas_sesion": LIMITE_PREGUNTAS_SESION,
        "umbral_distancia_coseno": UMBRAL_DISTANCIA_COSENO,
        "top_k_fragmentos": TOP_K_FRAGMENTOS,
        "max_palabras_respuesta": MAX_PALABRAS_RESPUESTA,
        "timeout_respuesta": TIMEOUT_RESPUESTA,
        "dominios": [
            {"codigo": c, **MAPEO_CATEGORIAS.get(c, {})}
            for c in DOMINIO_CATEGORIAS
        ],
        "mensajes": MENSAJES,
    }


@app.post("/consulta", tags=["chat"], response_model=RespuestaConsulta)
async def consultar(consulta: Consulta):
    """Endpoint principal: pipeline RAG + manejo de errores T04/M06.

    Si el cliente excede LIMITE_PREGUNTAS_SESION en modo piloto (T07), se
    rechaza con HTTP 429.
    """
    sesion_id = (consulta.sesion_id or "").strip()

    # T07 — límite de preguntas por sesión en modo piloto
    preguntas_previas = 0
    if MODO_PILOTO and sesion_id:
        preguntas_previas = contar_preguntas_sesion(sesion_id)
        if preguntas_previas >= LIMITE_PREGUNTAS_SESION:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "respuesta": MENSAJES["M08_LIMITE"],
                    "tipo_mensaje": "M08",
                    "preguntas_restantes": 0,
                },
            )

    # Pipeline (los errores internos ya se traducen a M06 dentro del pipeline)
    try:
        resultado = generar_respuesta(consulta.pregunta, sesion_id=sesion_id)
    except Exception as exc:  # red de seguridad — nunca debería ocurrir
        log.exception("Excepción no controlada en /consulta")
        return RespuestaConsulta(
            respuesta=MENSAJES["M06"],
            fuentes=[],
            tipo_mensaje="M06",
            tiempo_respuesta=0.0,
            preguntas_restantes=None,
        )

    # Anexar contador de sesión si aplica
    if MODO_PILOTO and sesion_id:
        usadas = preguntas_previas + 1
        resultado["preguntas_restantes"] = max(0, LIMITE_PREGUNTAS_SESION - usadas)

    return resultado


@app.get("/historial", tags=["evaluacion"])
async def obtener_historial(
    sesion_id: str | None = Query(default=None, max_length=64),
):
    """Exporta el historial en CSV (opcional filtrado por sesión).

    Útil para evaluación OE6/OE8.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if sesion_id:
            cursor.execute(
                "SELECT * FROM interacciones WHERE sesion_id = ? ORDER BY id",
                (sesion_id,),
            )
        else:
            cursor.execute("SELECT * FROM interacciones ORDER BY id")
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    writer.writerows(rows)
    return {"csv": output.getvalue(), "total": len(rows)}


@app.delete("/historial/{sesion_id}", tags=["privacidad"])
async def borrar_historial(sesion_id: str):
    """Sección 3.4 OE4 — derecho de eliminación.

    Borra todas las interacciones asociadas a la sesión indicada.
    """
    if not sesion_id or len(sesion_id) > 64:
        raise HTTPException(status_code=400, detail="sesion_id inválido")
    borradas = eliminar_por_sesion(sesion_id)
    return {"borradas": borradas, "sesion_id": sesion_id}


@app.get("/documentos", tags=["evaluacion"])
async def listar_documentos():
    """Lista todos los documentos indexados (introspección del corpus)."""
    from rag_pipeline import collection

    docs = collection.get()
    documentos = sorted({m["documento"] for m in docs["metadatas"]})
    categorias = sorted({m.get("categoria", "") for m in docs["metadatas"] if m.get("categoria")})
    return {
        "total": len(documentos),
        "categorias": categorias,
        "documentos_en_corpus": documentos,
    }


@app.get("/politica-privacidad", tags=["privacidad"], response_class=PlainTextResponse)
async def politica_privacidad():
    """Sección 3.3 OE4 — política de privacidad alineada con Ley 29733."""
    ruta = os.path.join(os.path.dirname(__file__), "POLITICA_PRIVACIDAD.md")
    if not os.path.isfile(ruta):
        return PlainTextResponse(
            "Política de privacidad no disponible en este despliegue.",
            status_code=404,
        )
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()
