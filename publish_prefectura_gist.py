import json
import os
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import requests

PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"
GITHUB_API_GIST = "https://api.github.com/gists/{gist_id}"


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    txt = str(value).strip().replace(",", ".")
    if txt in {"", "-", "--", "S/E", "S/E."}:
        return None

    try:
        return float(txt)
    except ValueError:
        return None


def get_prefectura_row():
    html = requests.get(
        PREFECTURA_URL,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        },
    ).text

    df = pd.read_html(StringIO(html))[0]
    df.columns = [" ".join(str(c).split()) for c in df.columns]

    fila = df[
        df["Puerto"].astype(str).str.upper().str.contains("BUENOS AIRES", na=False)
        & df["Río"].astype(str).str.upper().str.contains("PLATA", na=False)
    ]

    if fila.empty:
        raise RuntimeError("No encontré la fila BUENOS AIRES / DE LA PLATA en Prefectura.")

    row = fila.iloc[0]

    return {
        "source": "prefectura_buenos_aires",
        "station": "Buenos Aires / De la Plata",
        "puerto": str(row.get("Puerto")),
        "rio": str(row.get("Río")),
        "nivel_rio_m": to_float(row.get("Ult. registro")),
        "variacion_m": to_float(row.get("Variación")),
        "estado": str(row.get("Estado")).strip().upper() if "Estado" in fila.columns else None,
        "registro_anterior_m": to_float(row.get("Registro Anterior")),
        "fecha_hora": str(row.get("Fecha Hora")) if "Fecha Hora" in fila.columns else None,
        "fecha_anterior": str(row.get("Fecha Anterior")) if "Fecha Anterior" in fila.columns else None,
        "alerta_rio_m": to_float(row.get("Alerta")),
        "evacuacion_rio_m": to_float(row.get("Evacuación")),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def publish_to_gist(payload):
    github_token = os.getenv("GITHUB_TOKEN")
    gist_id = os.getenv("GIST_ID")

    if not github_token:
        raise RuntimeError("Falta variable de entorno GITHUB_TOKEN")
    if not gist_id:
        raise RuntimeError("Falta variable de entorno GIST_ID")

    url = GITHUB_API_GIST.format(gist_id=gist_id)

    body = {
        "files": {
            "prefectura_latest.json": {
                "content": json.dumps(payload, ensure_ascii=False, indent=2)
            }
        }
    }

    r = requests.patch(
        url,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        },
        json=body,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def main():
    payload = get_prefectura_row()
    publish_to_gist(payload)
    print("Publicado OK en Gist.")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()