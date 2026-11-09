from pathlib import Path
import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.engine.semaforo import build_estado
from app.services.visitas import consultar_visitas, registrar_visita

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="HydroGuard Avellaneda", version="0.1.0")

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

logger = logging.getLogger(__name__)


class ContactoPanel(BaseModel):
    visita_id: UUID
    navegador_id: UUID


@app.get("/visitas")
def visitas(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return consultar_visitas()
    except Exception:
        logger.exception("No se pudo leer el contador")
        raise HTTPException(status_code=503, detail="Contador temporalmente no disponible")


@app.post("/visitas")
def contacto_panel(contacto: ContactoPanel, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return registrar_visita(str(contacto.visita_id), str(contacto.navegador_id))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except Exception:
        logger.exception("No se pudo registrar la consulta del panel")
        raise HTTPException(status_code=503, detail="Contador temporalmente no disponible")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/estado")
def estado():
    return build_estado()


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")
