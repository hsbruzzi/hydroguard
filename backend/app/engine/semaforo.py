from datetime import datetime, timezone

from app.services.providers import fetch_weather, fetch_river


def calcular_semaforo(data):
    alerta_meteo = (data.get("alerta_smn") or "").lower()

    nivel_rio = data.get("nivel_rio_m")
    alerta_rio = data.get("alerta_rio_m")
    evacuacion_rio = data.get("evacuacion_rio_m")
    direccion_viento = (data.get("direccion_viento") or "").upper()

    if alerta_meteo in ["naranja", "rojo"]:
        return "ROJO"

    if nivel_rio is not None and evacuacion_rio is not None and nivel_rio >= evacuacion_rio:
        return "ROJO"

    if nivel_rio is not None and alerta_rio is not None and nivel_rio >= alerta_rio:
        return "AMARILLO"

    if data.get("lluvia_24h_mm", 0) > 80 or data.get("intensidad_mm_h", 0) > 40:
        return "ROJO"

    if (
        data.get("lluvia_24h_mm", 0) > 40
        or data.get("intensidad_mm_h", 0) > 20
        or data.get("lluvia_3dias_mm", 0) > 50
        or (
            nivel_rio is not None
            and nivel_rio > 2.5
            and direccion_viento in ["SE", "ESE", "SSE"]
        )
        or (
            nivel_rio is not None
            and nivel_rio > 2.0
        )
    ):
        return "AMARILLO"

    return "VERDE"


def build_estado():
    errors = []
    fuentes = []

    weather = {}
    try:
        weather = fetch_weather()
        if weather.get("weather_source"):
            fuentes.append(weather["weather_source"])
    except Exception as e:
        errors.append("weather: " + str(e))
        weather = {
            "lluvia_actual_mm": 0,
            "lluvia_24h_mm": 0,
            "intensidad_mm_h": 0,
            "lluvia_3dias_mm": 0,
            "viento_kmh": 0,
            "direccion_viento": "--",
            "weather_source": "none",
            "pronostico_5dias": [],
        }

    river = {}
    try:
        river = fetch_river()
        if river.get("river_source") and river.get("river_source") != "none":
            fuentes.append(river["river_source"])
        if river.get("thresholds_source"):
            fuentes.append(river["thresholds_source"])
        if river.get("river_errors"):
            errors.extend(river["river_errors"])
    except Exception as e:
        errors.append("river: " + str(e))
        river = {
            "nivel_rio_m": None,
            "river_source": "none",
            "river_site_name": None,
            "thresholds_source": "thresholds_default_buenos_aires",
            "alerta_rio_m": 3.30,
            "evacuacion_rio_m": 3.90,
            "river_errors": [str(e)],
        }

    data = {
        "lluvia_actual_mm": weather.get("lluvia_actual_mm", 0),
        "lluvia_24h_mm": weather.get("lluvia_24h_mm", 0),
        "intensidad_mm_h": weather.get("intensidad_mm_h", 0),
        "lluvia_3dias_mm": weather.get("lluvia_3dias_mm", 0),
        "nivel_rio_m": river.get("nivel_rio_m", None),
        "alerta_rio_m": river.get("alerta_rio_m", 3.30),
        "evacuacion_rio_m": river.get("evacuacion_rio_m", 3.90),
        "river_site_name": river.get("river_site_name", None),
        "viento_kmh": weather.get("viento_kmh", 0),
        "direccion_viento": weather.get("direccion_viento", "--"),
        "alerta_smn": "verde",
        "pronostico_5dias": weather.get("pronostico_5dias", []),
    }

    semaforo = calcular_semaforo(data)

    if semaforo == "ROJO":
        interpretacion = (
            "Alta probabilidad de anegamiento. El sistema puede entrar en "
            "sobrecarga por lluvia intensa, nivel del río elevado o superación "
            "de umbrales oficiales."
        )
        conclusion = "ROJO: evitar desplazamientos innecesarios y proteger accesos bajos."
    elif semaforo == "AMARILLO":
        interpretacion = (
            "El sistema está bajo estrés moderado. Puede haber anegamientos "
            "puntuales si se intensifica la lluvia o si el río se acerca a umbrales críticos."
        )
        conclusion = "AMARILLO: reforzar monitoreo y revisar desagües cercanos."
    else:
        interpretacion = (
            "Las condiciones son estables. No hay señales de sobrecarga "
            "relevante del sistema de drenaje en este momento."
        )
        conclusion = "VERDE: monitoreo normal, sin acción preventiva especial por ahora."

    checklist = [
        "Alerta oficial: " + data["alerta_smn"].upper(),
        "Lluvia actual: " + str(data["lluvia_actual_mm"]) + " mm",
        "Lluvia últimas 24 h: " + str(data["lluvia_24h_mm"]) + " mm",
        "Intensidad estimada: " + str(data["intensidad_mm_h"]) + " mm/h",
        "Lluvia acumulada 3 días: " + str(data["lluvia_3dias_mm"]) + " mm",
        (
            "Nivel del río: " + str(data["nivel_rio_m"]) + " m"
            if data["nivel_rio_m"] is not None
            else "Nivel del río: sin dato"
        ),
        (
            "Estación usada: " + str(data["river_site_name"])
            if data["river_site_name"]
            else "Estación usada: sin dato"
        ),
        "Nivel de alerta: " + str(data["alerta_rio_m"]) + " m",
        "Nivel de evacuación: " + str(data["evacuacion_rio_m"]) + " m",
        "Viento: " + str(data["direccion_viento"]) + " " + str(data["viento_kmh"]) + " km/h",
    ]

    return {
        "semaforo": semaforo,
        "interpretacion": interpretacion,
        "checklist": checklist,
        "conclusion": conclusion,
        "datos": data,
        "meta": {
            "fuentes": list(dict.fromkeys(fuentes)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "zona": "Sarandí / Avellaneda",
            "errores_fuentes": errors,
        },
    }