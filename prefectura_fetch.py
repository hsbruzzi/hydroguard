import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"
OUT = Path("cache/prefectura_latest.json")

def to_float(v):
    try:
        return float(str(v).replace(",", "."))
    except:
        return None

html = requests.get(URL, timeout=20, headers={"User-Agent":"Mozilla/5.0"}).text
df = pd.read_html(StringIO(html))[0]
df.columns = [" ".join(str(c).split()) for c in df.columns]

fila = df[
    df["Puerto"].str.upper().str.contains("BUENOS AIRES", na=False) &
    df["Río"].str.upper().str.contains("PLATA", na=False)
]

row = fila.iloc[0]

data = {
    "nivel_rio_m": to_float(row["Ult. registro"]),
    "alerta_rio_m": to_float(row["Alerta"]),
    "evacuacion_rio_m": to_float(row["Evacuación"]),
    "updated_at": datetime.now(timezone.utc).isoformat()
}

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(data, indent=2))
print("OK")