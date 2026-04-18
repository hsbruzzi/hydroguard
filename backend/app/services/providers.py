from __future__ import annotations

from typing import Any
import re
import requests
from bs4 import BeautifulSoup

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PREFECTURA_ALTURAS_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

# Sarandí / Avellaneda aprox.
DEFAULT_LAT = -34.684
DEFAULT_LON = -58.342

# Usamos el nombre exacto que hoy aparece en la tabla de Prefectura
DEFAULT_PREFECTURA_SITE = "BUENOS AIRES DE LA PLATA"


def _safe_get(url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> requests.Response:
    r = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 HydroGuard/1.0",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        },
    )
    r.raise_for_status()
    return r


def degrees_to_compass(deg: float) -> str:
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


def _to_float(text: str) -> float | None:
    if text is None:
        return None
    txt = text.strip().replace(",", ".")
    if txt in {"", "-", "S/E", "S/E.", "--"}:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def fetch_weather_open_meteo(
    latitude: float = DEFAULT_LAT,
    longitude: float = DEFAULT_LON,
) -> dict[str, Any]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "precipitation,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation",
        "timezone": "America/Argentina/Buenos_Aires",
        "past_hours": 72,
        "forecast_hours": 0,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    response = _safe_get(OPEN_METEO_URL, params=params)
    data = response.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    precip = hourly.get("precipitation", []) or []

    lluvia_actual = float(current.get("precipitation", 0) or 0)
    viento_kmh = float(current.get("wind_speed_10m", 0) or 0)
    direccion_grados = float(current.get("wind_direction_10m", 0) or 0)

    ult24 = precip[-24:] if len(precip) >= 24 else precip
    ult72 = precip[-72:] if len(precip) >= 72 else precip

    return {
        "lluvia_actual_mm": round(lluvia_actual, 1),
        "lluvia_24h_mm": round(sum(float(x or 0) for x in ult24), 1),
        "intensidad_mm_h": round(max((float(x or 0) for x in ult24), default=0), 1),
        "lluvia_3dias_mm": round(sum(float(x or 0) for x in ult72), 1),
        "viento_kmh": round(viento_kmh, 1),
        "direccion_viento": degrees_to_compass(direccion_grados),
        "weather_raw_updated_at": current.get("time"),
        "weather_source": "open-meteo",
    }


def _extract_prefectura_lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines


def fetch_river_level_prefectura(site_name: str = "BUENOS AIRES") -> dict[str, Any]:
    response = _safe_get(PREFECTURA_ALTURAS_URL, timeout=20)
    html = response.text

    soup = BeautifulSoup(html, "html.parser")

    # 🔥 clave: buscar TODA la tabla sin depender del nombre
    text = soup.get_text(" ", strip=True)

    import re

    # Busca números tipo 0.79 o -0.02
    nums = re.findall(r"-?\d+\.\d+", text)

    valores = []
    for n in nums:
        try:
            v = float(n)
            # filtramos valores razonables de nivel de río
            if -5 < v < 10:
                valores.append(v)
        except:
            pass

    if len(valores) >= 2:
        return {
            "nivel_rio_m": round(valores[0], 2),
            "river_variacion_m": round(valores[1], 2),
            "river_source": "prefectura_fallback",
            "river_site": "auto_detectado",
        }

    return {
        "nivel_rio_m": None,
        "river_source": "prefectura_fail_total",
        "river_errors": ["No se pudieron extraer datos numéricos"],
    }
    # Extrae todos los números decimales de la línea; los dos primeros son altura y variación.
    nums = re.findall(r"-?\d+(?:\.\d+)?", matched_line)
    valores = [_to_float(n) for n in nums]
    valores = [v for v in valores if v is not None]

    estado = None
    upper_line = matched_line.upper()
    for token in ["CRECE", "BAJA", "ESTAC."]:
        if token in upper_line:
            estado = token
            break

    if not valores:
        return {
            "nivel_rio_m": None,
            "river_variacion_m": None,
            "river_estado": estado,
            "river_source": "prefectura_fail",
            "river_site": site_name,
            "river_errors": [f"No se pudieron extraer números de la línea: {matched_line}"],
        }

    return {
        "nivel_rio_m": round(valores[0], 2),
        "river_variacion_m": round(valores[1], 2) if len(valores) > 1 else None,
        "river_estado": estado,
        "river_source": "prefectura_buenos_aires_de_la_plata",
        "river_site": site_name,
        "river_debug_line": matched_line,
    }


def fetch_river_level_ina_auto() -> dict[str, Any]:
    """
    Dejamos este nombre para no tocar semaforo.py.
    Por ahora usa Prefectura como fuente operativa real del nivel del estuario.
    """
    return fetch_river_level_prefectura(DEFAULT_PREFECTURA_SITE)