import time
import requests

URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

def fetch_prefectura():
    for attempt in range(3):
        try:
            r = requests.get(
                URL,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 HydroGuard"}
            )
            r.raise_for_status()

            html = r.text

            # 👉 acá va tu parser actual (NO lo cambio)
            # ejemplo placeholder:
            if "Buenos Aires" in html:
                return {
                    "source": "prefectura",
                    "station": "Buenos Aires",
                    "value_m": 1.70,  # ← reemplazar por parsing real
                    "timestamp": "now"
                }

        except Exception as e:
            print(f"[Prefectura] intento {attempt+1} falló: {e}")
            time.sleep(5 * (attempt + 1))

    return None