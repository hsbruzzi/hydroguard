import os
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from io import StringIO

import pandas as pd
import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"
CACHE_URL_DEFAULT = (
    "https://raw.githubusercontent.com/hsbruzzi/hydroguard/"
    "main/cache/prefectura_latest.json"
)

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
    if txt in {"", "-", "--", "S/E", "S/E.", "S/D"}:
        return None

    try:
        return float(txt)
    except ValueError:
        return None


def _norm_text(s):
    s = unicodedata.normalize("NFKD", str(s).strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace(".", " ").replace("/", " ").replace("_", " ")
    return " ".join(s.split())


def _find_col(df, candidates):
    norm_map = {_norm_text(c): c for c in df.columns}
    for cand in candidates:
        for norm_name, real_name in norm_map.items():
            if _norm_text(cand) in norm_name:
                return real_name
    return None


def _fecha_con_zona(value):
    """Acepta fechas ISO únicamente si incluyen zona horaria."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        fecha = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
        if fecha.tzinfo is None or fecha.utcoffset() is None:
            return None
        return fecha
    except ValueError:
        return None


def _metadatos_rio(payload):
    medicion = _fecha_con_zona(payload.get("observed_at"))
    anterior = _fecha_con_zona(payload.get("previous_observed_at"))
    consulta = _fecha_con_zona(payload.get("fetched_at"))

    # Un timestamp antiguo es hora de consulta, nunca de medición.
    if consulta is None:
        consulta = _fecha_con_zona(payload.get("timestamp"))

    ahora = datetime.now(timezone.utc)
    antiguedad = None

    if medicion is not None:
        minutos = (ahora - medicion).total_seconds() / 60
        if minutos >= 0:
            antiguedad = round(minutos, 1)

    intervalo = None
    if medicion is not None and anterior is not None:
        horas = (medicion - anterior).total_seconds() / 3600
        if horas > 0:
            intervalo = round(horas, 2)

    return {
        "river_observed_at": (
            medicion.isoformat() if medicion is not None else None
        ),
        "river_previous_observed_at": (
            anterior.isoformat() if anterior is not None else None
        ),
        "river_fetched_at": (
            consulta.isoformat() if consulta is not None else None
        ),
        "river_age_minutes": antiguedad,
        "river_interval_hours": intervalo,
        "river_source_name": payload.get("source_name"),
        "river_source_url": payload.get("source_url"),
        "river_reference": payload.get("reference"),
        "river_unit": payload.get("unit") or "m",
    }


def grados_a_cardinal(deg):
    dirs = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSO", "SO", "OSO",
        "O", "ONO", "NO", "NNO",
    ]
    return dirs[int((deg + 11.25) / 22.5) % 16]


def weather_code_text(code):
    mapping = {
        0: "Despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Niebla",
        48: "Niebla con escarcha",
        51: "Llovizna débil",
        53: "Llovizna moderada",
        55: "Llovizna intensa",
        61: "Lluvia débil",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        71: "Nieve débil",
        73: "Nieve moderada",
        75: "Nieve intensa",
        80: "Chaparrones débiles",
        81: "Chaparrones moderados",
        82: "Chaparrones intensos",
        95: "Tormenta",
        96: "Tormenta con granizo débil",
        99: "Tormenta con granizo intenso",
    }
    return mapping.get(code, "Condición no especificada")


def _sum_precipitation_last_hours(
    hourly_times, hourly_precip, current_time, hours
):
    """Suma valores del proveedor correspondientes a horas pasadas."""
    start_time = current_time - timedelta(hours=hours)
    total = 0.0
    max_hour = 0.0

    for t, p in zip(hourly_times, hourly_precip):
        try:
            ts = datetime.fromisoformat(t)
        except Exception:
            continue

        if start_time <= ts <= current_time:
            value = _to_float(p) or 0.0
            total += value
            max_hour = max(max_hour, value)

    return round(total, 1), round(max_hour, 1)


def fetch_weather():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "precipitation,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation",
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max"
        ),
        "forecast_days": 5,
        "past_hours": 72,
        "timezone": "America/Argentina/Buenos_Aires",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    r = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    lluvia_actual = _to_float(current.get("precipitation")) or 0.0
    viento = _to_float(current.get("wind_speed_10m")) or 0.0
    direccion = _to_float(current.get("wind_direction_10m")) or 0.0

    current_time_raw = current.get("time")
    current_time = (
        datetime.fromisoformat(current_time_raw)
        if current_time_raw
        else datetime.now()
    )

    hourly_times = hourly.get("time", []) or []
    hourly_precip = hourly.get("precipitation", []) or []

    lluvia_24h, intensidad_24h = _sum_precipitation_last_hours(
        hourly_times, hourly_precip, current_time, 24
    )
    lluvia_72h, _ = _sum_precipitation_last_hours(
        hourly_times, hourly_precip, current_time, 72
    )

    times = daily.get("time", []) or []
    codes = daily.get("weather_code", []) or []
    tmax = daily.get("temperature_2m_max", []) or []
    tmin = daily.get("temperature_2m_min", []) or []
    psum = daily.get("precipitation_sum", []) or []
    pprob = daily.get("precipitation_probability_max", []) or []

    pronostico_5dias = []
    for i in range(min(len(times), 5)):
        code = codes[i] if i < len(codes) else None
        pronostico_5dias.append({
            "fecha": times[i],
            "weather_code": code,
            "condicion": weather_code_text(code),
            "temp_max_c": tmax[i] if i < len(tmax) else None,
            "temp_min_c": tmin[i] if i < len(tmin) else None,
            "lluvia_mm": psum[i] if i < len(psum) else None,
            "prob_lluvia_pct": pprob[i] if i < len(pprob) else None,
        })

    return {
        "lluvia_actual_mm": round(lluvia_actual, 1),
        "lluvia_24h_mm": lluvia_24h,
        "intensidad_mm_h": intensidad_24h,
        "lluvia_3dias_mm": lluvia_72h,
        "viento_kmh": round(viento, 1),
        "direccion_viento": grados_a_cardinal(direccion),
        "weather_source": "open-meteo",
        "pronostico_5dias": pronostico_5dias,
    }


def fetch_river_from_cache():
    url = os.getenv("PREFECTURA_CACHE_URL", CACHE_URL_DEFAULT)
    sep = "&" if "?" in url else "?"
    url += sep + "t=" + str(int(time.time()))

    r = requests.get(
        url,
        timeout=8,
        headers={"User-Agent": "Mozilla/5.0 HydroGuard"},
    )
    r.raise_for_status()
    payload = r.json()

    nivel = _to_float(payload.get("nivel_rio_m"))
    if nivel is None:
        nivel = _to_float(payload.get("value_m"))

    resultado = {
        "nivel_rio_m": nivel,
        "river_previous_value_m": _to_float(
            payload.get("previous_value_m")
        ),
        "river_variacion_m": _to_float(payload.get("variacion_m")),
        "river_tendencia": payload.get("tendencia"),
        "river_estado": payload.get("estado"),
        "river_source": payload.get("source") or "github_cache_json",
        "river_site_name": payload.get("station") or "Buenos Aires",
        "alerta_rio_m": (
            _to_float(payload.get("alerta_rio_m")) or DEFAULT_ALERTA_M
        ),
        "evacuacion_rio_m": (
            _to_float(payload.get("evacuacion_rio_m"))
            or DEFAULT_EVACUACION_M
        ),
        "thresholds_source": "cache_json_default_thresholds",
        "river_errors": [],
    }
    resultado.update(_metadatos_rio(payload))
    return resultado


def fetch_river_prefectura_direct():
    try:
        resp = requests.get(
            PREFECTURA_URL,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            },
        )
        resp.raise_for_status()
        tablas = pd.read_html(StringIO(resp.text))

        selected_df = None
        selected_cols = None

        for tabla in tablas:
            df = tabla.copy()
            df.columns = [" ".join(str(c).split()) for c in df.columns]

            cols = {
                "puerto": _find_col(df, ["Puerto"]),
                "rio": _find_col(df, ["Rio", "Río"]),
                "ult": _find_col(
                    df, ["Ult registro", "Ult. registro", "Ultimo registro"]
                ),
                "alerta": _find_col(df, ["Alerta"]),
                "evac": _find_col(df, ["Evacuacion", "Evacuación"]),
                "estado": _find_col(df, ["Estado"]),
                "variacion": _find_col(df, ["Variacion", "Variación"]),
            }

            if all(cols[k] is not None for k in ["puerto", "rio", "ult"]):
                selected_df = df
                selected_cols = cols
                break

        if selected_df is None:
            raise RuntimeError("No encontré tabla válida")

        df = selected_df
        fila = df[
            df[selected_cols["puerto"]].astype(str).str.upper()
            .str.contains("BUENOS AIRES", na=False)
            & df[selected_cols["rio"]].astype(str).str.upper()
            .str.contains("PLATA", na=False)
        ]

        if fila.empty:
            raise RuntimeError(
                "No encontré fila BUENOS AIRES / DE LA PLATA"
            )

        row = fila.iloc[0]

        def valor(clave):
            columna = selected_cols[clave]
            return row.get(columna) if columna is not None else None

        alerta = _to_float(valor("alerta"))
        evacuacion = _to_float(valor("evac"))
        estado = valor("estado")

        resultado = {
            "nivel_rio_m": _to_float(valor("ult")),
            "river_variacion_m": _to_float(valor("variacion")),
            "river_tendencia": None,
            "river_estado": (
                str(estado).strip().upper() if estado is not None else None
            ),
            "river_source": "prefectura_direct",
            "river_site_name": "Buenos Aires / De la Plata",
            "alerta_rio_m": (
                alerta if alerta is not None else DEFAULT_ALERTA_M
            ),
            "evacuacion_rio_m": (
                evacuacion
                if evacuacion is not None
                else DEFAULT_EVACUACION_M
            ),
            "thresholds_source": "prefectura_direct",
            "river_errors": [],
        }
        resultado.update(_metadatos_rio({
            "source_name": "Prefectura Naval Argentina",
            "source_url": PREFECTURA_URL,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "unit": "m",
        }))
        return resultado

    except Exception as e:
        return {
            "nivel_rio_m": None,
            "river_source": "none",
            "river_site_name": None,
            "alerta_rio_m": DEFAULT_ALERTA_M,
            "evacuacion_rio_m": DEFAULT_EVACUACION_M,
            "thresholds_source": "thresholds_default_buenos_aires",
            "river_errors": ["Prefectura directa: " + str(e)],
            **_metadatos_rio({}),
        }


def fetch_river():
    try:
        cached = fetch_river_from_cache()
        if cached is not None:
            return cached
    except Exception as e:
        return {
            "nivel_rio_m": None,
            "river_source": "none",
            "river_site_name": None,
            "alerta_rio_m": DEFAULT_ALERTA_M,
            "evacuacion_rio_m": DEFAULT_EVACUACION_M,
            "thresholds_source": "thresholds_default_buenos_aires",
            "river_errors": ["Cache JSON: " + str(e)],
            **_metadatos_rio({}),
        }

    return fetch_river_prefectura_direct()