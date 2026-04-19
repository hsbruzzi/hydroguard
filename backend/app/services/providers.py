from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

LAT = -34.684
LON = -58.342

# Umbrales oficiales observados para BUENOS AIRES / DE LA PLATA
DEFAULT_ALERTA_M = 3.30
DEFAULT_EVACUACION_M = 3.90


def _to_float(value: Any) -> float | None:
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


def grados_a_cardinal(deg: float) -> str:
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


# -------------------------
# WEATHER
# -------------------------
def fetch_weather() -> dict[str, Any]:
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


# -------------------------
# PREFECTURA
# -------------------------
def fetch_river_prefectura_buenos_aires() -> dict[str, Any] | None:
    """
    Busca específicamente la fila:
    PUERTO = BUENOS AIRES
    RIO = DE LA PLATA

    Devuelve:
    - nivel_rio_m
    - river_variacion_m
    - river_estado
    - alerta_rio_m
    - evacuacion_rio_m
    """
    r = requests.get(
        PREFECTURA_URL,
        timeout=8,
        headers={
            "User-Agent": "Mozilla/5.0 HydroGuard/1.0",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        },
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.find_all("tr")

    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 11:
            continue

        puerto = cells[0].strip().upper()
        rio = cells[1].strip().upper()

        if "BUENOS AIRES" in puerto and "PLATA" in rio:
            nivel = _to_float(cells[2])
            variacion = _to_float(cells[3])
            estado = cells[6].strip().upper() if len(cells) > 6 else None
            alerta = _to_float(cells[9]) if len(cells) > 9 else None
            evacuacion = _to_float(cells[10]) if len(cells) > 10 else None

            return {
                "nivel_rio_m": nivel,
                "river_variacion_m": variacion,
                "river_estado": estado,
                "alerta_rio_m": alerta if alerta is not None else DEFAULT_ALERTA_M,
                "evacuacion_rio_m": evacuacion if evacuacion is not None else DEFAULT_EVACUACION_M,
                "river_source": "prefectura_buenos_aires",
                "thresholds_source": "prefectura_buenos_aires",
            }

    # Si la tabla cambia o viene rara, devolvemos None
    return None


# -------------------------
# RIVER MAIN
# -------------------------
def fetch_river() -> dict[str, Any]:
    """
    Estrategia final:
    1. Intentar Prefectura Buenos Aires / De la Plata
    2. Si falla, no inventar nivel
    3. Mantener umbrales oficiales por defecto para la interfaz y la lógica
    """
    errors: list[str] = []

    try:
        pref = fetch_river_prefectura_buenos_aires()
        if pref is not None:
            pref["river_errors"] = errors
            return pref
        errors.append("Prefectura sin datos")
    except Exception as e:
        errors.append(f"Prefectura: {e}")

    return {
        "nivel_rio_m": None,
        "river_variacion_m": None,
        "river_estado": None,
        "alerta_rio_m": DEFAULT_ALERTA_M,
        "evacuacion_rio_m": DEFAULT_EVACUACION_M,
        "river_source": "none",
        "thresholds_source": "thresholds_default_buenos_aires",
        "river_errors": errors,
    }