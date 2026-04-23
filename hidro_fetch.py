import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://www.hidro.gov.ar/oceanografia/alturashorarias.xml"

def fetch_hidro():
    try:
        r = requests.get(RSS_URL, timeout=30)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        # 👉 esto depende del formato real del XML
        # ejemplo simple:
        for item in root.findall(".//item"):
            title = item.find("title").text

            if "Buenos Aires" in title:
                return {
                    "source": "hidro_rss",
                    "station": "Buenos Aires",
                    "value_m": 1.68,  # ← ajustar parsing real
                    "timestamp": "now"
                }

    except Exception as e:
        print(f"[Hidro] error: {e}")

    return None