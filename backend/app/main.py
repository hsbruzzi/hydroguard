from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.engine.semaforo import build_estado

app = FastAPI(title="HydroGuard Avellaneda")

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/estado")
def estado():
    return build_estado()

@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")
