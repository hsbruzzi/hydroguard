"""Consultas del panel y navegadores activos; sin guardar direcciones IP."""

import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


ACTIVE_WINDOW_SECONDS = 120
DEFAULT_DB = "/tmp/hydroguard/visitas.sqlite3"


@contextmanager
def conexion():
    ruta = Path(os.environ.get("HYDROGUARD_VISITS_DB") or DEFAULT_DB)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(ruta), timeout=5)) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS visitas_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total INTEGER NOT NULL DEFAULT 0,
                inicio TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS visitas (
                visita_id TEXT PRIMARY KEY,
                navegador_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS navegadores (
                navegador_id TEXT PRIMARY KEY,
                ultimo_contacto REAL NOT NULL
            );
        """)
        with db:
            db.execute(
                "INSERT OR IGNORE INTO visitas_meta (id, total, inicio) VALUES (1, 0, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
        yield db


def _resumen(db, ahora):
    meta = db.execute("SELECT total, inicio FROM visitas_meta WHERE id=1").fetchone()
    activos = db.execute(
        "SELECT COUNT(*) FROM navegadores WHERE ultimo_contacto >= ? AND ultimo_contacto <= ?",
        (ahora.timestamp() - ACTIVE_WINDOW_SECONDS, ahora.timestamp()),
    ).fetchone()[0]
    return {
        "consultas_total": meta["total"],
        "navegadores_activos": activos,
        "ventana_activos_segundos": ACTIVE_WINDOW_SECONDS,
        "desde": meta["inicio"],
        "actualizado_at": ahora.isoformat(),
    }


def consultar_visitas():
    with conexion() as db:
        with db:
            return _resumen(db, datetime.now(timezone.utc))


def registrar_visita(visita_id, navegador_id):
    # BEGIN IMMEDIATE serializa el alta y el resumen entre procesos.
    with conexion() as db:
        with db:
            db.execute("BEGIN IMMEDIATE")
            ahora = datetime.now(timezone.utc)
            existente = db.execute(
                "SELECT navegador_id FROM visitas WHERE visita_id = ?", (visita_id,)
            ).fetchone()
            if existente and existente["navegador_id"] != navegador_id:
                raise ValueError("La consulta pertenece a otro navegador")
            if not existente:
                db.execute(
                    "INSERT INTO visitas (visita_id, navegador_id) VALUES (?, ?)",
                    (visita_id, navegador_id),
                )
                db.execute("UPDATE visitas_meta SET total=total+1 WHERE id=1")
            db.execute(
                "INSERT INTO navegadores (navegador_id, ultimo_contacto) VALUES (?, ?) "
                "ON CONFLICT(navegador_id) DO UPDATE SET ultimo_contacto=excluded.ultimo_contacto",
                (navegador_id, ahora.timestamp()),
            )
            db.execute(
                "DELETE FROM navegadores WHERE ultimo_contacto < ?",
                (ahora.timestamp() - 86400,),
            )
            return _resumen(db, ahora)
