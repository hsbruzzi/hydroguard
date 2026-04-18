import requests
from bs4 import BeautifulSoup

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
INA_URL = "https://alerta.ina.gob.ar/pub/datos/datos"
PREFECTURA_URL = "https://contenidosweb.prefecturanaval.gob.ar/alturas/"

LAT = -34.684
LON = -58.342


# -------------------------
# WEATHER
# -------------------------
def fetch_weather():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "precipitation,wind_speed_10m,wind_direction_10m",
        "hourly": "precipitation",
        "past_hours": 72,
        "timezone": "America/Argentina/Buenos_Aires"
    }

    r = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    data = r.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {}).get("precipitation", [])

    lluvia_actual = current.get("precipitation", 0) or 0
    viento = current.get("wind_speed_10m", 0) or 0
    direccion = current.get("wind_direction_10m", 0) or 0

    ult24 = hourly[-24:] if len(hourly) >= 24 else hourly
    ult72 = hourly[-72:] if len(hourly) >= 72 else hourly

    return {
        "lluvia_actual_mm": round(lluvia_actual, 1),
        "lluvia_24h_mm": round(sum(ult24), 1),
        "intensidad_mm_h": round(max(ult24) if ult24 else 0, 1),
        "lluvia_3dias_mm": round(sum(ult72), 1),
        "viento_kmh": round(viento, 1),
        "direccion_viento": grados_a_cardinal(direccion),
        "weather_source": "open-meteo"
    }


def grados_a_cardinal(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


# -------------------------
# INA (FUENTE PRINCIPAL)
# -------------------------
def fetch_river_ina():
    SITE_CODE = "BAPLA"

    for var_id in [2, 1, 3]:
        try:
            params = {
                "siteCode": SITE_CODE,
                "varId": var_id
            }

            r = requests.get(INA_URL, params=params, timeout=10)
            data = r.json()

            if isinstance(data, list) and len(data) > 0:
                valor = data[-1].get("valor")

                if valor is not None:
                    return {
                        "nivel_rio_m": round(float(valor), 2),
                        "river_source": "ina"
                    }

        except Exception:
            continue

    return None


# -------------------------
# PREFECTURA (FALLBACK)
# -------------------------
def fetch_river_prefectura():
    try:
        r = requests.get(PREFECTURA_URL, timeout=6)
        soup = BeautifulSoup(r.text, "html.parser")

        texto = soup.get_text(" ", strip=True)

        import re
        nums = re.findall(r"\d+\.\d+", texto)

        if nums:
            return {
                "nivel_rio_m": float(nums[0]),
                "river_source": "prefectura"
            }

    except Exception:
        return None

    return None


# -------------------------
# RIVER MAIN
# -------------------------
def fetch_river():
    errores = []

    # 1. INA
    try:
        ina = fetch_river_ina()
        if ina:
            return ina
        else:
            errores.append("INA sin datos")
    except Exception as e:
        errores.append(f"INA error: {e}")

    # 2. Prefectura
    try:
        pref = fetch_river_prefectura()
        if pref:
            pref["river_errors"] = errores
            return pref
        else:
            errores.append("Prefectura sin datos")
    except Exception as e:
        errores.append(f"Prefectura error: {e}")

    # 3. fallback final
    return {
        "nivel_rio_m": None,
        "river_source": "none",
        "river_errors": errores
    }