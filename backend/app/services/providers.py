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

# Umbrales observados para Buenos Aires en la tabla de Prefectura
# Los dejamos como respaldo para no perder esa referencia oficial
DEFAULT_ALERTA_M = 3.30
DEFAULT_EVACUACION_M = 3.90


def grados_a_cardinal(deg: float) -> str:
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
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
# PREFECTURA (preferida)
# -------------------------
def fetch_river_prefectura_buenos_aires() -> dict[str, Any] | None:
    """
    Intenta leer la fila:
    BUENOS AIRES | DE LA PLATA | Ult.registro | ... | Alerta | Evacuación
    """
    r = requests.get(PREFECTURA_URL, timeout=8)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Primero intentamos parseo estructurado por filas de tabla
    rows = soup.find_all("tr")
    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 10:
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

    # Si falla el parseo estructurado, hacemos un fallback por texto
    text = soup.get_text(" ", strip=True).upper()
    if "BUENOS AIRES" in text and "PLATA" in text:
        nums = re.findall(r"-?\d+\.\d+", text)
        values = []
        for n in nums:
            val = _to_float(n)
            if val is not None and -5 < val < 20:
                values.append(val)

        if len(values) >= 4:
            # Intento razonable:
            # nivel, variacion, ..., alerta, evacuacion
            return {
                "nivel_rio_m": round(values[0], 2),
                "river_variacion_m": round(values[1], 2),
                "river_estado": None,
                "alerta_rio_m": round(values[-2], 2),
                "evacuacion_rio_m": round(values[-1], 2),
                "river_source": "prefectura_fallback_text",
                "thresholds_source": "prefectura_fallback_text",
            }

    return None


# -------------------------
# INA (alternativa)
# -------------------------
def fetch_river_ina() -> dict[str, Any] | None:
    """
    Intento alternativo con una estación fija del INA.
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
                        "thresholds_source": "thresholds_default_buenos_aires",
                        "alerta_rio_m": DEFAULT_ALERTA_M,
                        "evacuacion_rio_m": DEFAULT_EVACUACION_M,
                    }
        except Exception:
            continue

    return None


# -------------------------
# MAIN RIVER PROVIDER
# -------------------------
def fetch_river() -> dict[str, Any]:
    """
    Estrategia:
    1. Prefectura Buenos Aires (nivel + umbrales)
    2. INA (nivel) + umbrales por defecto
    3. Sin dato de nivel, pero conservando umbrales por defecto
    """
    errors: list[str] = []

    # 1. Prefectura
    try:
        pref = fetch_river_prefectura_buenos_aires()
        if pref is not None:
            pref["river_errors"] = errors
            return pref
        errors.append("Prefectura sin datos")
    except Exception as e:
        errors.append(f"Prefectura: {e}")

    # 2. INA
    try:
        ina = fetch_river_ina()
        if ina is not None:
            ina["river_errors"] = errors
            return ina
        errors.append("INA sin datos")
    except Exception as e:
        errors.append(f"INA: {e}")

    # 3. Sin nivel real, pero con umbrales por defecto
    return {
        "nivel_rio_m": None,
        "river_source": "none",
        "thresholds_source": "thresholds_default_buenos_aires",
        "alerta_rio_m": DEFAULT_ALERTA_M,
        "evacuacion_rio_m": DEFAULT_EVACUACION_M,
        "river_errors": errors,
    }