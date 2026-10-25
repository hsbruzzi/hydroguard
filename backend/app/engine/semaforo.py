from datetime import datetime, timedelta, timezone

from app.services.providers import fetch_weather, fetch_river


ARGENTINA = timezone(timedelta(hours=-3))


def fecha_argentina(value):
    if not isinstance(value, str) or not value.strip():
        return "sin dato"

    try:
        fecha = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
        if fecha.tzinfo is None or fecha.utcoffset() is None:
            return "sin zona horaria verificable"

        return fecha.astimezone(ARGENTINA).strftime(
            "%d/%m/%Y %H:%M:%S (Argentina)"
        )
    except ValueError:
        return "fecha no válida"


def antiguedad_minutos(value):
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        fecha = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
        if fecha.tzinfo is None or fecha.utcoffset() is None:
            return None

        minutos = (
            datetime.now(timezone.utc) - fecha
        ).total_seconds() / 60

        return round(minutos, 1) if minutos >= 0 else None
    except ValueError:
        return None


def texto_antiguedad(minutos):
    if minutos is None:
        return "desconocida"

    if minutos < 60:
        return f"{minutos:.0f} minutos"

    horas, resto = divmod(int(minutos), 60)
    return f"{horas} h {resto:02d} min"


def calcular_semaforo(data):
    alerta_meteo = (data.get("alerta_smn") or "").lower()

    nivel_rio = data.get("nivel_rio_m")
    alerta_rio = data.get("alerta_rio_m")
    evacuacion_rio = data.get("evacuacion_rio_m")
    direccion_viento = (data.get("direccion_viento") or "").upper()

    if alerta_meteo in ["naranja", "rojo"]:
        return "ROJO"

    if (
        nivel_rio is not None
        and evacuacion_rio is not None
        and nivel_rio >= evacuacion_rio
    ):
        return "ROJO"

    if (
        nivel_rio is not None
        and alerta_rio is not None
        and nivel_rio >= alerta_rio
    ):
        return "AMARILLO"

    if (
        data.get("lluvia_24h_mm", 0) > 80
        or data.get("intensidad_mm_h", 0) > 40
    ):
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

    try:
        river = fetch_river()
        if river.get("river_source") and river["river_source"] != "none":
            fuentes.append(river["river_source"])

        if river.get("thresholds_source"):
            fuentes.append(river["thresholds_source"])

        if river.get("river_errors"):
            errors.extend(river["river_errors"])

    except Exception as e:
        errors.append("river: " + str(e))
        river = {
            "nivel_rio_m": None,
            "river_previous_value_m": None,
            "river_variacion_m": None,
            "river_tendencia": None,
            "river_source": "none",
            "river_site_name": None,
            "thresholds_source": "thresholds_default_buenos_aires",
            "alerta_rio_m": 3.30,
            "evacuacion_rio_m": 3.90,
        }

    data = {
        "lluvia_actual_mm": weather.get("lluvia_actual_mm", 0),
        "lluvia_24h_mm": weather.get("lluvia_24h_mm", 0),
        "intensidad_mm_h": weather.get("intensidad_mm_h", 0),
        "lluvia_3dias_mm": weather.get("lluvia_3dias_mm", 0),

        "nivel_rio_m": river.get("nivel_rio_m"),
        "river_previous_value_m": river.get("river_previous_value_m"),
        "river_variacion_m": river.get("river_variacion_m"),
        "river_tendencia": river.get("river_tendencia"),
        "river_site_name": river.get("river_site_name"),

        "river_observed_at": river.get("river_observed_at"),
        "river_previous_observed_at": river.get(
            "river_previous_observed_at"
        ),
        "river_fetched_at": river.get("river_fetched_at"),
        "river_interval_hours": river.get("river_interval_hours"),
        "river_source": river.get("river_source"),
        "river_source_name": river.get("river_source_name"),
        "river_source_url": river.get("river_source_url"),
        "river_reference": river.get("river_reference"),
        "river_unit": river.get("river_unit") or "m",

        "alerta_rio_m": river.get("alerta_rio_m", 3.30),
        "evacuacion_rio_m": river.get("evacuacion_rio_m", 3.90),
        "viento_kmh": weather.get("viento_kmh", 0),
        "direccion_viento": weather.get("direccion_viento", "--"),

        "alerta_smn": "no verificada",
        "pronostico_5dias": weather.get("pronostico_5dias", []),
    }

    # La antigüedad se calcula desde la medición, no desde la consulta.
    edad = antiguedad_minutos(data["river_observed_at"])
    data["river_age_minutes"] = edad

    if data["nivel_rio_m"] is None:
        calidad = "sin dato"
    elif edad is None:
        calidad = "antigüedad no verificable"
    elif edad > 180:
        calidad = "dato atrasado"
    else:
        calidad = "dentro del margen operativo de 3 horas"

    data["river_data_status"] = calidad

    semaforo = calcular_semaforo(data)

    if semaforo == "ROJO":
        interpretacion = (
            "Alta probabilidad de anegamiento. El sistema puede entrar en "
            "sobrecarga por lluvia intensa, nivel del río elevado o superación "
            "de umbrales oficiales."
        )
        conclusion = (
            "ROJO: evitar desplazamientos innecesarios y proteger accesos bajos."
        )
    elif semaforo == "AMARILLO":
        interpretacion = (
            "El sistema está bajo estrés moderado. Puede haber anegamientos "
            "puntuales si se intensifica la lluvia o si el río se acerca "
            "a umbrales críticos."
        )
        conclusion = "AMARILLO: reforzar monitoreo y revisar desagües cercanos."
    else:
        interpretacion = (
            "Las condiciones son estables. No hay señales de sobrecarga "
            "relevante del sistema de drenaje en este momento."
        )
        conclusion = (
            "VERDE: monitoreo normal, sin acción preventiva especial por ahora."
        )

    tendencia = data["river_tendencia"]
    variacion = data["river_variacion_m"]
    intervalo = data["river_interval_hours"]

    if tendencia:
        tendencia_txt = "Tendencia del río: " + str(tendencia).upper()
        if variacion is not None:
            tendencia_txt += f" ({variacion:+.2f} m)"
        if intervalo is not None:
            tendencia_txt += f" en {intervalo:g} horas"
        else:
            tendencia_txt += "; intervalo no verificado"
    else:
        tendencia_txt = "Tendencia del río: sin dato"

    checklist = [
        "Alerta SMN: NO VERIFICADA. Consultar https://www.smn.gob.ar/alertas",
        "Lluvia actual: " + str(data["lluvia_actual_mm"]) + " mm",
        "Lluvia últimas 24 h: " + str(data["lluvia_24h_mm"]) + " mm",
        "Intensidad estimada: " + str(data["intensidad_mm_h"]) + " mm/h",
        "Lluvia acumulada 3 días: " + str(data["lluvia_3dias_mm"]) + " mm",
        (
            "Nivel del río: " + str(data["nivel_rio_m"]) + " m"
            if data["nivel_rio_m"] is not None
            else "Nivel del río: sin dato"
        ),
        "Estación del río: " + str(data["river_site_name"] or "sin dato"),
        "Fuente del río: " + str(
            data["river_source_name"]
            or data["river_source"]
            or "sin dato"
        ),
        "Enlace de la fuente: " + str(
            data["river_source_url"] or "sin dato"
        ),
        "Referencia del nivel: " + str(
            data["river_reference"] or "no informada"
        ),
        "Medición del río: " + fecha_argentina(data["river_observed_at"]),
        "Antigüedad de la medición: " + texto_antiguedad(edad),
        "Estado del dato del río: " + calidad,
        (
            "Margen de antigüedad: 3 horas, criterio operativo propio "
            "de HydroGuard; no es un umbral oficial de emergencia"
        ),
        "Consulta de la fuente: " + fecha_argentina(
            data["river_fetched_at"]
        ),
        "Medición anterior: " + fecha_argentina(
            data["river_previous_observed_at"]
        ),
        tendencia_txt,
        "Nivel de alerta configurado: " + str(data["alerta_rio_m"]) + " m",
        "Nivel de evacuación configurado: "
        + str(data["evacuacion_rio_m"]) + " m",
        (
            "Viento: "
            + str(data["direccion_viento"])
            + " "
            + str(data["viento_kmh"])
            + " km/h"
        ),
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