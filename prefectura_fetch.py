import re
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"


def build_session():
    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": "Mozilla/5.0 HydroGuard/1.0",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    })

    return session


def parse_prefectura_html(html):
    """
    Parser simple para buscar la fila de Buenos Aires en el HTML de Prefectura.

    Si la estructura cambia o no se puede detectar un valor confiable,
    devuelve None para que main.py use el fallback SHN.
    """

    text = re.sub(r"\s+", " ", html)

    # Buscamos una zona cercana a "Buenos Aires"
    match = re.search(r"Buenos Aires.{0,500}", text, flags=re.IGNORECASE)
    if not match:
        print("[Prefectura] no se encontró Buenos Aires en el HTML")
        return None

    fragment = match.group(0)

    # Buscar números con formato 1.23 o 1,23 dentro del fragmento
    numbers = re.findall(r"\b\d+[,.]\d+\b", fragment)

    if not numbers:
        print("[Prefectura] Buenos Aires encontrado, pero sin valores numéricos cercanos")
        return None

    value = float(numbers[0].replace(",", "."))

    return {
        "source": "prefectura",
        "station": "Buenos Aires",
        "value_m": value,
        "timestamp": datetime.utcnow().isoformat()
    }


def fetch_prefectura():
    session = build_session()

    for attempt in range(1, 4):
        try:
            r = session.get(URL, timeout=(10, 30))
            r.raise_for_status()

            html = r.text

            if not html.strip():
                print("[Prefectura] respuesta vacía")
                return None

            data = parse_prefectura_html(html)

            if data:
                print(f"OK Prefectura: {data}")
                return data

            print("[Prefectura] HTML recibido, pero no se pudo parsear dato confiable")
            return None

        except requests.exceptions.ConnectTimeout as e:
            print(f"[Prefectura] intento {attempt}/3 timeout de conexión: {e}")

        except requests.exceptions.ReadTimeout as e:
            print(f"[Prefectura] intento {attempt}/3 timeout de lectura: {e}")

        except requests.exceptions.RequestException as e:
            print(f"[Prefectura] intento {attempt}/3 error HTTP/red: {e}")

        except Exception as e:
            print(f"[Prefectura] intento {attempt}/3 error inesperado: {e}")

        if attempt < 3:
            time.sleep(5 * attempt)

    return None
