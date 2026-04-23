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

        # Buscar todas las filas de tabla
        rows = tree.xpath("//table//tr")

        for row in rows:
            cells = [c.text_content().strip() for c in row.xpath(".//td")]
            if not cells:
                continue

            # Esperamos algo tipo:
            # [Buenos Aires, 1.34, 1.34, 1.23, ...]
            station = cells[0]

            if station.lower() == "buenos aires":
                values = cells[1:]
                valid_values = [v for v in values if v and v.upper() != "S/D"]

                if not valid_values:
                    print("[Hidro] fila encontrada pero sin valores válidos")
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