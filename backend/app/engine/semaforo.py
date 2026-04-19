from __future__ import annotations

from datetime import datetime, timezone

from app.services.providers import fetch_weather, fetch_river


def calcular_semaforo(data: dict) -> str:
    alerta = (data.get("alerta_smn") or "").lower()
    nivel_rio = data.get("nivel_rio_m")
    direccion_viento = (data.get("direccion_viento") or "").upper()

    if alerta in ["naranja", "rojo"]:
        return "ROJO"

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


def build_estado() -> dict:
    errors = []
    fuentes = []

    # WEATHER
    weather = {}
    try:
        weather = fetch_weather()
        if weather.get("weather_source"):
            fuentes.append(weather["weather_source"])
    except Exception as e:
        errors.append(f"weather: {e}")
        weather = {
            "lluvia_actual_mm": 0,
            "lluvia_24h_mm": 0,
            "intensidad_mm_h": 0,
            "lluvia_3dias_mm": 0,
            "viento_kmh": 0,
            "direccion_viento": "--",
            "weather_source": "none",
        }

    # RIVER
    river = {}
    try:
        river = fetch_river()
        if river.get("river_source"):
            fuentes.append(river["river_source"])
        if river.get("river_errors"):
            errors.extend(river["river_errors"])
    except Exception as e:
        errors.append(f"river: {e}")
        river = {
            "nivel_rio_m": None,
            "river_source": "none",
            "river_errors": [str(e)],
        }

    data = {
        "lluvia_actual_mm": weather.get("lluvia_actual_mm", 0),
        "lluvia_24h_mm": weather.get("lluvia_24h_mm", 0),
        "intensidad_mm_h": weather.get("intensidad_mm_h", 0),
        "lluvia_3dias_mm": weather.get("lluvia_3dias_mm", 0),
        "nivel_rio_m": river.get("nivel_rio_m", None),
        "viento_kmh": weather.get("viento_kmh", 0),
        "direccion_viento": weather.get("direccion_viento", "--"),
        "alerta_smn": "verde",
    }

    semaforo = calcular_semaforo(data)

    if semaforo == "ROJO":
        interpretacion = (
            "Alta probabilidad de anegamiento. El sistema puede entrar en "
            "sobrecarga y conviene tomar medidas preventivas inmediatas."
        )
        conclusion = "ROJO: evitar desplazamientos innecesarios y proteger accesos bajos."
    elif semaforo == "AMARILLO":
        interpretacion = (
            "El sistema está bajo estrés moderado. Puede haber anegamientos "
            "puntuales si se intensifica la lluvia o sube el río."
        )
        conclusion = "AMARILLO: reforzar monitoreo y revisar desagües cercanos."
    else:
        interpretacion = (
            "Las condiciones son estables. No hay señales de sobrecarga "
            "relevante del sistema de drenaje en este momento."
        )
        conclusion = "VERDE: monitoreo normal, sin acción preventiva especial por ahora."

    checklist = [
        f"Alerta oficial: {data['alerta_smn'].upper()}",
        f"Lluvia actual: {data['lluvia_actual_mm']} mm",
        f"Lluvia últimas 24 h: {data['lluvia_24h_mm']} mm",
        f"Intensidad estimada: {data['intensidad_mm_h']} mm/h",
        f"Lluvia acumulada 3 días: {data['lluvia_3dias_mm']} mm",
        (
            f"Nivel del río: {data['nivel_rio_m']} m"
            if data["nivel_rio_m"] is not None
            else "Nivel del río: sin dato"
        ),
        f"Viento: {data['direccion_viento']} {data['viento_kmh']} km/h",
    ]

    return {
        "semaforo": semaforo,
        "interpretacion": interpretacion,
        "checklist": checklist,
        "conclusion": conclusion,
        "datos": data,
        "meta": {
            "fuentes": fuentes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "zona": "Sarandí / Avellaneda",
            "errores_fuentes": errors,
        },
    }