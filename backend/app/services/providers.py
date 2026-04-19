import pandas as pd
import requests
from io import StringIO

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

LAT = -34.684
LON = -58.342

DEFAULT_ALERTA_M = 3.30
DEFAULT_EVACUACION_M = 3.90


def _to_float(value):
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


def grados_a_cardinal(deg):
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


def fetch_weather():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "precipitation,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation",
        "past_hours": 72,
        "timezone": "America/Argentina/Buenos_Aires",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    r = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {}).get("precipitation", []) or []

    lluvia_actual = _to_float(current.get("precipitation")) or 0.0
    viento = _to_float(current.get("wind_speed_10m")) or 0.0
    direccion = _to_float(current.get("wind_direction_10m")) or 0.0

    ult24 = hourly[-24:] if len(hourly) >= 24 else hourly
    ult72 = hourly[-72:] if len(hourly) >= 72 else hourly

    ult24_clean = [(_to_float(x) or 0.0) for x in ult24]
    ult72_clean = [(_to_float(x) or 0.0) for x in ult72]

    return {
        "lluvia_actual_mm": round(lluvia_actual, 1),
        "lluvia_24h_mm": round(sum(ult24_clean), 1),
        "intensidad_mm_h": round(max(ult24_clean, default=0.0), 1),
        "lluvia_3dias_mm": round(sum(ult72_clean), 1),
        "viento_kmh": round(viento, 1),
        "direccion_viento": grados_a_cardinal(direccion),
        "weather_source": "open-meteo",
    }


def fetch_river_prefectura():
    try:
        html = requests.get(
            PREFECTURA_URL,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            },
        ).text

        tablas = pd.read_html(StringIO(html))
        if not tablas:
            return {
                "nivel_rio_m": None,
                "river_source": "none",
                "river_site_name": None,
                "alerta_rio_m": DEFAULT_ALERTA_M,
                "evacuacion_rio_m": DEFAULT_EVACUACION_M,
                "thresholds_source": "thresholds_default_buenos_aires",
                "river_errors": ["Prefectura sin tablas"],
            }

        df = tablas[0]
        df.columns = [" ".join(str(c).split()) for c in df.columns]

        fila = df[
            df["Puerto"].astype(str).str.upper().str.contains("BUENOS AIRES", na=False)
            & df["Río"].astype(str).str.upper().str.contains("PLATA", na=False)
        ]

        if fila.empty:
            return {
                "nivel_rio_m": None,
                "river_source": "none",
                "river_site_name": None,
                "alerta_rio_m": DEFAULT_ALERTA_M,
                "evacuacion_rio_m": DEFAULT_EVACUACION_M,
                "thresholds_source": "thresholds_default_buenos_aires",
                "river_errors": ["Prefectura sin fila BUENOS AIRES / DE LA PLATA"],
            }

        row = fila.iloc[0]

        nivel = _to_float(row.get("Ult. registro"))
        variacion = _to_float(row.get("Variación"))
        alerta = _to_float(row.get("Alerta")) or DEFAULT_ALERTA_M
        evacuacion = _to_float(row.get("Evacuación")) or DEFAULT_EVACUACION_M
        estado = str(row.get("Estado")).strip().upper() if "Estado" in fila.columns else None

        return {
            "nivel_rio_m": nivel,
            "river_variacion_m": variacion,
            "river_estado": estado,
            "river_source": "prefectura_buenos_aires",
            "river_site_name": "Buenos Aires / De la Plata",
            "alerta_rio_m": alerta,
            "evacuacion_rio_m": evacuacion,
            "thresholds_source": "prefectura_buenos_aires",
            "river_errors": [],
        }

    except Exception as e:
        return {
            "nivel_rio_m": None,
            "river_source": "none",
            "river_site_name": None,
            "alerta_rio_m": DEFAULT_ALERTA_M,
            "evacuacion_rio_m": DEFAULT_EVACUACION_M,
            "thresholds_source": "thresholds_default_buenos_aires",
            "river_errors": ["Prefectura error: " + str(e)],
        }


def fetch_river():
    return fetch_river_prefectura()