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

        # Buscar la fila que contiene el link con data-nombre="Buenos Aires"
        row = tree.xpath('//tr[.//a[@data-nombre="Buenos Aires"]]')
        if not row:
            print("[Hidro] no se encontró la fila de Buenos Aires")
            return None

        row = row[0]

        # Tomar todos los td de la fila
        tds = row.xpath('./td')
        if len(tds) < 3:
            print("[Hidro] fila Buenos Aires encontrada pero con estructura inesperada")
            return None

        # Los dos primeros td suelen ser:
        # 0 = icono
        # 1 = nombre de estación
        # desde 2 en adelante = valores horarios
        values = []
        for td in tds[2:]:
            text = td.text_content().strip()
            if not text:
                continue
            if text.upper() == "S/D":
                continue
            try:
                values.append(float(text.replace(",", ".")))
            except ValueError:
                continue

        if not values:
            print("[Hidro] Buenos Aires encontrada pero sin valores numéricos válidos")
            return None

        latest_value = values[0]

        data = {
            "source": "hidro_html",
            "station": "Buenos Aires",
            "value_m": latest_value,
            "timestamp": datetime.utcnow().isoformat()
        }

        print(f"OK Hidro: {data}")
        return data

    except Exception as e:
        print(f"[Hidro] error: {e}")
        return None