from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import re

import requests
from bs4 import BeautifulSoup

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
INA_BASE_URL = "https://alerta.ina.gob.ar/pub/datos"
PREFECTURA_ALTURAS_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

# Sarandí / Avellaneda aprox.
DEFAULT_LAT = -34.684
DEFAULT_LON = -58.342

# Palabras clave para buscar estaciones relevantes del Río de la Plata
INA_SITE_KEYWORDS = [
    "BUENOS AIRES",
    "LA PLATA",
    "ATALAYA",
    "BRAGA",
]

# Como no siempre está claro el varId del nivel en todas las implementaciones,
# probamos varios candidatos razonables.
INA_VARID_CANDIDATES = [2, 1, 3]


def _safe_get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 12,
) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            "User-Agent": "HydroGuard/1.0 (+Render)",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        },
    )
    response.raise_for_status()
    return response


def _safe_get_json(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 12,
) -> Any:
    return _safe_get(url, params=params, timeout=timeout).json()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().upper())


def _to_float(text: str | float | int | None) -> float | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    txt = str(text).strip().replace(",", ".")
    if txt in {"", "-", "--", "S/E", "S/E."}:
        return None

    try:
        return float(txt)
    except ValueError:
        return None


def degrees_to_compass(deg: float) -> str:
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


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

    data = _safe_get_json(OPEN_METEO_URL, params=params, timeout=12)

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


def extract_latest_numeric_value(payload: Any) -> float | None:
    """
    Busca el último valor numérico razonable dentro de un JSON arbitrario.
    """
    candidates: list[float] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in ["valor", "value", "nivel", "altura", "medicion", "dato"]:
                if key in obj:
                    value = _to_float(obj[key])
                    if value is not None:
                        candidates.append(value)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return candidates[-1] if candidates else None


def _extract_station_records(payload: Any) -> list[dict[str, Any]]:
    """
    Recorre un JSON arbitrario y junta diccionarios que parezcan estaciones
    (siteCode/código/nombre).
    """
    records: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            keys = {k.lower() for k in obj.keys()}
            looks_like_station = (
                "sitecode" in keys
                or "codigo" in keys
                or ("nombre" in keys and ("sitecode" in keys or "id" in keys))
            )
            if looks_like_station:
                records.append(obj)

            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return records


def _station_name(record: dict[str, Any]) -> str:
    for key in ["nombre", "name", "descripcion", "siteName", "stationName"]:
        if key in record and record[key]:
            return str(record[key])
    return ""


def _station_code(record: dict[str, Any]) -> str | None:
    for key in ["siteCode", "codigo", "code", "id"]:
        if key in record and record[key] is not None:
            return str(record[key])
    return None


def find_ina_station_candidates() -> list[dict[str, str]]:
    """
    Intenta descubrir estaciones relevantes desde /estaciones.
    """
    url = f"{INA_BASE_URL}/estaciones"

    try:
        payload = _safe_get_json(url, timeout=12)
    except Exception:
        return []

    stations = _extract_station_records(payload)
    results: list[dict[str, str]] = []

    for st in stations:
        name = _station_name(st)
        code = _station_code(st)

        if not code or not name:
            continue

        upper_name = _normalize(name)
        if any(keyword in upper_name for keyword in INA_SITE_KEYWORDS):
            results.append({
                "siteCode": code,
                "name": name,
            })

    # sacar duplicados por siteCode
    dedup: dict[str, dict[str, str]] = {}
    for item in results:
        dedup[item["siteCode"]] = item

    return list(dedup.values())


def fetch_river_level_ina(site_code: str, var_id: int) -> dict[str, Any]:
    """
    Consulta el endpoint /datos del INA para una estación + variable.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).replace(microsecond=0).isoformat()
    end = now.replace(microsecond=0).isoformat()

    url = f"{INA_BASE_URL}/datos"
    params = {
        "siteCode": site_code,
        "varId": var_id,
        "timeStart": start,
        "timeEnd": end,
    }

    payload = _safe_get_json(url, params=params, timeout=12)
    level = extract_latest_numeric_value(payload)

    if level is None:
        raise ValueError(f"INA sin dato numérico para siteCode={site_code}, varId={var_id}")

    return {
        "nivel_rio_m": round(level, 2),
        "river_source": f"ina_site_{site_code}_var_{var_id}",
        "river_site": site_code,
        "river_var_id": var_id,
    }


def fetch_river_level_prefectura() -> dict[str, Any]:
    """
    Fallback: scraping de Prefectura.
    No dependemos de un nombre exacto de estación; usamos el primer valor
    decimal razonable encontrado en la página.
    """
    response = _safe_get(PREFECTURA_ALTURAS_URL, timeout=8)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    nums = re.findall(r"-?\d+\.\d+", text)
    values: list[float] = []

    for n in nums:
        val = _to_float(n)
        if val is not None and -5 < val < 10:
            values.append(val)

    if len(values) >= 2:
        return {
            "nivel_rio_m": round(values[0], 2),
            "river_variacion_m": round(values[1], 2),
            "river_source": "prefectura_fallback",
            "river_site": "auto_detectado",
        }

    if len(values) == 1:
        return {
            "nivel_rio_m": round(values[0], 2),
            "river_variacion_m": None,
            "river_source": "prefectura_fallback",
            "river_site": "auto_detectado",
        }

    return {
        "nivel_rio_m": None,
        "river_source": "prefectura_fail",
        "river_errors": ["No se pudieron extraer datos numéricos desde Prefectura"],
    }


def fetch_river_level_ina_auto() -> dict[str, Any]:
    """
    Estrategia:
    1. Intentar INA descubriendo estaciones candidatas
    2. Probar varios varId razonables
    3. Si todo falla, usar Prefectura como fallback
    """
    errors: list[str] = []

    candidates = find_ina_station_candidates()

    for st in candidates:
        site_code = st["siteCode"]
        site_name = st["name"]

        for var_id in INA_VARID_CANDIDATES:
            try:
                result = fetch_river_level_ina(site_code, var_id)
                result["river_site_name"] = site_name
                result["river_candidates_tested"] = [c["siteCode"] for c in candidates]
                result["river_errors"] = errors
                return result
            except Exception as e:
                errors.append(f"INA {site_code}/{var_id}: {e}")

    # fallback Prefectura
    try:
        result = fetch_river_level_prefectura()
        result["river_candidates_tested"] = [c["siteCode"] for c in candidates]
        if "river_errors" in result:
            result["river_errors"] = errors + result["river_errors"]
        else:
            result["river_errors"] = errors
        return result
    except Exception as e:
        errors.append(f"Prefectura: {e}")

    return {
        "nivel_rio_m": None,
        "river_source": "river_unavailable",
        "river_candidates_tested": [c["siteCode"] for c in candidates],
        "river_errors": errors if errors else ["No hubo respuesta válida de INA ni Prefectura"],
    }