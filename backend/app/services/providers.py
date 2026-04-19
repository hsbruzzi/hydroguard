from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
INA_URL = "https://alerta.ina.gob.ar/pub/datos/datos"
PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

LAT = -34.684
LON = -58.342


def grados_a_cardinal(deg: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


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
# INA (FUENTE PRINCIPAL)
# -------------------------
def fetch_river_ina() -> dict[str, Any] | None:
    """
    Intenta usar una estación fija del INA.
    Si no responde o no devuelve datos útiles, retorna None.
    """
    site_code = "BAPLA"

    for var_id in [2, 1, 3]:
        try:
            params = {
                "siteCode": site_code,
                "varId": var_id,
            }

            r = requests.get(INA_URL, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            if isinstance(data, list) and len(data) > 0:
                ultimo = data[-1]
                valor = _to_float(ultimo.get("valor"))

                if valor is not None:
                    return {
                        "nivel_rio_m": round(valor, 2),
                        "river_source": "ina",
                    }

        except Exception:
            continue

    return None


# -------------------------
# PREFECTURA (FALLBACK)
# -------------------------
def fetch_river_prefectura() -> dict[str, Any] | None:
    """
    Scraping de Prefectura. Si no responde desde cloud, retorna None.
    """
    try:
        r = requests.get(PREFECTURA_URL, timeout=6)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        texto = soup.get_text(" ", strip=True)

        nums = re.findall(r"-?\d+\.\d+", texto)

        values = []
        for n in nums:
            val = _to_float(n)
            if val is not None and -5 < val < 10:
                values.append(val)

        if values:
            return {
                "nivel_rio_m": round(values[0], 2),
                "river_source": "prefectura",
            }

    except Exception:
        return None

    return None


# -------------------------
# RIVER MAIN
# -------------------------
def fetch_river() -> dict[str, Any]:
    errors: list[str] = []

    # 1. INA
    try:
        ina = fetch_river_ina()
        if ina is not None:
            ina["river_errors"] = errors
            return ina
        errors.append("INA sin datos")
    except Exception as e:
        errors.append(f"INA error: {e}")

    # 2. Prefectura
    try:
        pref = fetch_river_prefectura()
        if pref is not None:
            pref["river_errors"] = errors
            return pref
        errors.append("Prefectura sin datos")
    except Exception as e:
        errors.append(f"Prefectura error: {e}")

    # 3. Fallback final para que la app nunca quede rota
    return {
        "nivel_rio_m": 1.8,
        "river_source": "fallback_estimated",
        "river_errors": errors,
    }