from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.engine.semaforo import build_estado

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="HydroGuard Avellaneda", version="0.1.0")

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

print(f"Nivel río actualizado: {data['value_m']} m")

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/estado")
def estado():
    return build_estado()


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")
