import requests
from lxml import html
from datetime import datetime

URL = "https://www.hidro.gov.ar/Oceanografia/AlturasHorarias.asp"

def fetch_hidro():
    try:
        r = requests.get(
            URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 HydroGuard"}
        )
        r.raise_for_status()

        tree = html.fromstring(r.content)

        rows = tree.xpath("//table//tr")

        for row in rows:
            cells = [c.text_content().strip() for c in row.xpath(".//td")]
            if not cells:
                continue

            station = cells[0].strip().lower()
            print(f"[DEBUG][Hidro] estación detectada: {station}")

            if "buenos aires" in station:
                values = cells[1:]
                valid_values = []

                for v in values:
                    vv = v.strip()
                    if not vv:
                        continue
                    if vv.upper() == "S/D":
                        continue
                    valid_values.append(vv)

                if not valid_values:
                    print("[Hidro] fila Buenos Aires encontrada pero sin valores válidos")
                    return None

                latest_value = valid_values[0]

                return {
                    "source": "hidro_html",
                    "station": "Buenos Aires",
                    "value_m": float(latest_value.replace(",", ".")),
                    "timestamp": datetime.utcnow().isoformat()
                }

        print("[Hidro] no se encontró la estación Buenos Aires")
        return None

    except Exception as e:
        print(f"[Hidro] error: {e}")
        return None