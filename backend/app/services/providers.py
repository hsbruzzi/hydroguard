from __future__ import annotations

from typing import Any

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
INA_URL = "https://alerta.ina.gob.ar/pub/datos/datos"

LAT = -34.684
LON = -58.342

# Umbrales oficiales de referencia para Buenos Aires / Río de la Plata
DEFAULT_ALERTA_M = 3.30
DEFAULT_EVACUACION_M = 3.90

# Estaciones INA elegidas
SITE_PALERMO = 52
SITE_MARTIN_GARCIA = 47


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
# INA
# -------------------------
def fetch_river_ina_site(site_code: int) -> dict[str, Any] | None:
    """
    Intenta leer el último valor de altura para una estación INA.
    Probamos varios varId porque la API no siempre es consistente.
    """
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
                        "river_source": f"ina_site_{site_code}",
                        "river_var_id": var_id,
                    }
        except Exception:
            continue

    return None


def fetch_river() -> dict[str, Any]:
    """
    Estrategia:
    1. INA Palermo (más cercano al Puerto de Buenos Aires)
    2. INA Martín García (fallback regional)
    3. Sin dato de nivel, pero manteniendo umbrales oficiales
    """
    errors: list[str] = []

    # 1. Palermo
    try:
        palermo = fetch_river_ina_site(SITE_PALERMO)
        if palermo is not None:
            palermo["river_site_name"] = "Palermo"
            palermo["alerta_rio_m"] = DEFAULT_ALERTA_M
            palermo["evacuacion_rio_m"] = DEFAULT_EVACUACION_M
            palermo["thresholds_source"] = "thresholds_default_buenos_aires"
            palermo["river_errors"] = errors
            return palermo
        errors.append("INA Palermo sin datos")
    except Exception as e:
        errors.append(f"INA Palermo: {e}")

    # 2. Martín García
    try:
        mg = fetch_river_ina_site(SITE_MARTIN_GARCIA)
        if mg is not None:
            mg["river_site_name"] = "Martín García"
            mg["alerta_rio_m"] = DEFAULT_ALERTA_M
            mg["evacuacion_rio_m"] = DEFAULT_EVACUACION_M
            mg["thresholds_source"] = "thresholds_default_buenos_aires"
            mg["river_errors"] = errors
            return mg
        errors.append("INA Martín García sin datos")
    except Exception as e:
        errors.append(f"INA Martín García: {e}")

    # 3. Sin dato real
    return {
        "nivel_rio_m": None,
        "river_source": "none",
        "river_site_name": None,
        "alerta_rio_m": DEFAULT_ALERTA_M,
        "evacuacion_rio_m": DEFAULT_EVACUACION_M,
        "thresholds_source": "thresholds_default_buenos_aires",
        "river_errors": errors,
    }