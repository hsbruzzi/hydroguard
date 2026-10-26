import math
from datetime import datetime, timedelta, timezone

from app.services.providers import fetch_weather, fetch_river
from app.services.smn import fetch_smn


ARGENTINA = timezone(timedelta(hours=-3))
MAX_RIVER_MINUTES = 180
MAX_WEATHER_MINUTES = 120


def numero(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        valor = float(value)
        return valor if math.isfinite(valor) else None
    except (TypeError, ValueError):
        return None


def fecha_iso(value):
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


def fecha_argentina(value):
    fecha = fecha_iso(value)
    if fecha is None:
        return "sin fecha y zona horaria verificables"
    return fecha.astimezone(ARGENTINA).strftime(
        "%d/%m/%Y %H:%M:%S (Argentina)"
    )


def antiguedad_minutos(value):
    fecha = fecha_iso(value)
    if fecha is None:
        return None
    minutos = (
        datetime.now(timezone.utc) - fecha
    ).total_seconds() / 60
    return round(minutos, 1) if minutos >= 0 else None


def texto_antiguedad(minutos):
    if minutos is None:
        return "desconocida"
    horas, resto = divmod(int(minutos), 60)
    return f"{horas} h {resto:02d} min"


def medida(value, unidad):
    valor = numero(value)
    return "sin dato" if valor is None else f"{valor:g} {unidad}"


def estado_dato(valor, edad, limite):
    if numero(valor) is None:
        return "sin dato"
    if edad is None:
        return "antigüedad no verificable"
    if edad > limite:
        return "dato atrasado"
    return "vigente según criterio operativo de HydroGuard"


def evaluar_smn(resultado):
    """Color propio de HydroGuard; no es un color oficial del SMN."""
    now = datetime.now(timezone.utc)
    avisos = []
    problemas = list(resultado.get("errores") or [])

    consulta = fecha_iso(resultado.get("consultado_at"))

    if (
        consulta is None
        or not 0 <= (now - consulta).total_seconds() <= 600
    ):
        problemas.append(
            "Consulta SMN sin fecha vigente verificable"
        )

    fuentes = resultado.get("fuentes") or []

    for tipo in ("alertas", "acp"):
        feed = next(
            (
                f for f in fuentes
                if f.get("tipo") == tipo
            ),
            {},
        )

        publicado = fecha_iso(feed.get("publicado_at"))

        if (
            publicado is None
            or not -300 <= (
                now - publicado
            ).total_seconds() <= 7200
        ):
            problemas.append(
                "Canal SMN "
                + tipo
                + ": publicación no vigente"
            )

    for aviso in resultado.get("avisos") or []:
        vence = fecha_iso(aviso.get("vence_at"))
        emision = fecha_iso(aviso.get("emitido_at"))
        inicio = fecha_iso(aviso.get("inicio_at"))
        efectivo = fecha_iso(aviso.get("efectivo_at"))

        if vence is not None and vence <= now:
            continue

        if (
            vence is None
            or emision is None
            or inicio is None
            or efectivo is None
            or emision > now
            or inicio >= vence
            or efectivo >= vence
        ):
            problemas.append(
                "Aviso SMN con fechas no evaluables"
            )
            continue

        severidad = aviso.get("severidad_cap")

        if severidad not in {
            "Minor",
            "Moderate",
            "Severe",
            "Extreme",
        }:
            problemas.append(
                "Aviso SMN con severidad no evaluable"
            )
            continue

        avisos.append(aviso)

    verificado = (
        resultado.get("verificado") is True
        and not problemas
    )

    # Un aviso válido mantiene la atención
    # aun si otro canal falla.
    if any(
        a["severidad_cap"] in {"Severe", "Extreme"}
        for a in avisos
    ):
        color = "rojo"
    elif avisos:
        color = "amarillo"
    elif verificado:
        color = "sin avisos regionales"
    else:
        color = "no verificada"

    return color, verificado, avisos, problemas


def calcular_semaforo(data):
    # Sólo los datos con antigüedad verificable participan
    # de la evaluación automática.
    edad_rio = numero(data.get("river_age_minutes"))
    edad_meteo = numero(data.get("weather_age_minutes"))

    rio_vigente = (
        edad_rio is not None
        and 0 <= edad_rio <= MAX_RIVER_MINUTES
    )
    meteo_vigente = (
        edad_meteo is not None
        and 0 <= edad_meteo <= MAX_WEATHER_MINUTES
    )

    nivel = (
        numero(data.get("nivel_rio_m"))
        if rio_vigente else None
    )
    alerta = numero(data.get("alerta_rio_m"))
    evacuacion = numero(data.get("evacuacion_rio_m"))

    lluvia = (
        numero(data.get("lluvia_24h_mm"))
        if meteo_vigente else None
    )
    intensidad = (
        numero(data.get("intensidad_mm_h"))
        if meteo_vigente else None
    )
    acumulado = (
        numero(data.get("lluvia_3dias_mm"))
        if meteo_vigente else None
    )
    direccion = (
        str(data.get("direccion_viento") or "").upper()
        if meteo_vigente else ""
    )
    smn = str(data.get("alerta_smn") or "").lower()

    rojo = (
        smn in {"naranja", "rojo"}
        or (
            nivel is not None
            and evacuacion is not None
            and nivel >= evacuacion
        )
        or (lluvia is not None and lluvia > 80)
        or (intensidad is not None and intensidad > 40)
    )

    if rojo:
        return "ROJO"

    amarillo = (
        smn == "amarillo"
        or (
            nivel is not None
            and alerta is not None
            and nivel >= alerta
        )
        or (lluvia is not None and lluvia > 40)
        or (intensidad is not None and intensidad > 20)
        or (acumulado is not None and acumulado > 50)
        or (
            nivel is not None
            and nivel > 2.5
            and direccion in {"SE", "ESE", "SSE"}
        )
        or (nivel is not None and nivel > 2.0)
    )

    if amarillo:
        return "AMARILLO"

    if data.get("datos_faltantes"):
        return "INFORMACIÓN INSUFICIENTE"

    return "VERDE"


def build_estado():
    errors = []
    fuentes = []

    try:
        weather = fetch_weather() or {}
        fuente = weather.get("weather_source")

        if fuente and fuente != "none":
            fuentes.append(fuente)

    except Exception as error:
        errors.append("weather: " + str(error))
        weather = {}

    try:
        river = fetch_river() or {}
        fuente = river.get("river_source")

        if fuente and fuente != "none":
            fuentes.append(fuente)

        if river.get("thresholds_source"):
            fuentes.append(river["thresholds_source"])

        errors.extend(river.get("river_errors") or [])

    except Exception as error:
        errors.append("river: " + str(error))
        river = {}

    try:
        smn = fetch_smn() or {}
    except Exception as error:
        smn = {
            "verificado": False,
            "errores": [str(error)],
        }

    (
        color_smn,
        smn_ok,
        avisos_smn,
        errores_smn,
    ) = evaluar_smn(smn)

    errors.extend(
        "SMN: " + str(error)
        for error in errores_smn
    )

    fuentes.extend(
        f.get("url")
        for f in smn.get("fuentes", [])
        if f.get("url")
    )

    data = {
        campo: numero(weather.get(campo))
        for campo in [
            "lluvia_actual_mm",
            "lluvia_24h_mm",
            "intensidad_mm_h",
            "lluvia_3dias_mm",
            "viento_kmh",
        ]
    }

    data["direccion_viento"] = weather.get(
        "direccion_viento"
    )
    data["weather_observed_at"] = weather.get(
        "weather_observed_at"
    )
    data["weather_age_minutes"] = antiguedad_minutos(
        data["weather_observed_at"]
    )
    data["pronostico_5dias"] = (
        weather.get("pronostico_5dias") or []
    )

    for campo in [
        "nivel_rio_m",
        "river_previous_value_m",
        "river_variacion_m",
        "river_interval_hours",
        "alerta_rio_m",
        "evacuacion_rio_m",
    ]:
        data[campo] = numero(river.get(campo))

    for campo in [
        "river_tendencia",
        "river_site_name",
        "river_observed_at",
        "river_previous_observed_at",
        "river_fetched_at",
        "river_source",
        "river_source_name",
        "river_source_url",
        "river_reference",
        "river_unit",
    ]:
        data[campo] = river.get(campo)

    data["river_age_minutes"] = antiguedad_minutos(
        data["river_observed_at"]
    )

    data["river_data_status"] = estado_dato(
        data["nivel_rio_m"],
        data["river_age_minutes"],
        MAX_RIVER_MINUTES,
    )

    data["weather_data_status"] = estado_dato(
        data["lluvia_actual_mm"],
        data["weather_age_minutes"],
        MAX_WEATHER_MINUTES,
    )

    data["alerta_smn"] = color_smn
    data["smn_verificado"] = smn_ok
    data["smn_consultado_at"] = smn.get(
        "consultado_at"
    )
    data["smn_avisos"] = avisos_smn
    data["smn_fuentes"] = smn.get("fuentes") or []
    data["smn_cobertura"] = smn.get("cobertura")
    data["smn_errores"] = errores_smn
    data["smn_criterio"] = (
        "Criterio propio de HydroGuard: "
        "CAP Severe/Extreme activa rojo; "
        "Minor/Moderate o ACP evaluable activa amarillo. "
        "No equivale al color oficial del SMN."
    )

    faltantes = []

    if not smn_ok:
        faltantes.append(
            "Consulta de alertas y ACP del SMN "
            "incompleta o atrasada"
        )

    for campo, nombre in [
        ("lluvia_actual_mm", "Lluvia actual"),
        ("lluvia_24h_mm", "Lluvia de 24 horas"),
        ("intensidad_mm_h", "Intensidad"),
        ("lluvia_3dias_mm", "Lluvia de 3 días"),
        ("viento_kmh", "Velocidad del viento"),
        ("nivel_rio_m", "Nivel del río"),
    ]:
        if data[campo] is None:
            faltantes.append(
                nombre + ": sin dato"
            )

    if not data["direccion_viento"]:
        faltantes.append(
            "Dirección del viento: sin dato"
        )

    for nombre, edad, limite in [
        (
            "Río",
            data["river_age_minutes"],
            MAX_RIVER_MINUTES,
        ),
        (
            "Meteorología",
            data["weather_age_minutes"],
            MAX_WEATHER_MINUTES,
        ),
    ]:
        if edad is None:
            faltantes.append(
                nombre + ": antigüedad no verificable"
            )
        elif edad > limite:
            faltantes.append(
                nombre + ": dato atrasado"
            )

    if not data["river_reference"]:
        faltantes.append(
            "Referencia del río no informada"
        )

    if not data["pronostico_5dias"]:
        faltantes.append(
            "Pronóstico no disponible"
        )

    if errors:
        faltantes.append(
            "Hay errores de acceso a fuentes"
        )

    data["datos_faltantes"] = faltantes
    semaforo = calcular_semaforo(data)

    if semaforo == "ROJO":
        interpretacion = (
            "Los datos vigentes superan un criterio de nivel rojo "
            "configurado en HydroGuard. Esta evaluación no confirma "
            "inundaciones en una calle o vivienda."
        )
        conclusion = (
            "ROJO: revisar avisos oficiales y seguir las indicaciones "
            "de las autoridades."
        )

    elif semaforo == "AMARILLO":
        interpretacion = (
            "Los datos vigentes superan un criterio de atención "
            "configurado en HydroGuard. Esto no equivale a una "
            "alerta oficial ni confirma anegamientos."
        )
        conclusion = (
            "AMARILLO: reforzar el seguimiento y consultar "
            "las fuentes oficiales."
        )

    elif semaforo == "INFORMACIÓN INSUFICIENTE":
        interpretacion = (
            "Faltan datos o no se pudo verificar su vigencia. "
            "No es posible confirmar condiciones seguras."
        )
        conclusion = (
            "INFORMACIÓN INSUFICIENTE: consultar las fuentes oficiales "
            "y revisar las limitaciones del checklist."
        )

    else:
        interpretacion = (
            "Los datos evaluados no superan los criterios configurados. "
            "Esto no garantiza ausencia de riesgo local."
        )
        conclusion = (
            "VERDE: continuar el seguimiento de las fuentes oficiales."
        )

    if faltantes and semaforo in {"ROJO", "AMARILLO"}:
        interpretacion += (
            " La evaluación es parcial: también hay información "
            "faltante o no verificada."
        )

    tendencia = str(
        data["river_tendencia"] or "sin dato"
    ).upper()
    variacion = data["river_variacion_m"]
    intervalo = data["river_interval_hours"]

    tendencia_txt = "Tendencia del río: " + tendencia

    if variacion is not None:
        tendencia_txt += f" ({variacion:+.2f} m)"

    if intervalo is not None:
        tendencia_txt += f" en {intervalo:g} h"
    else:
        tendencia_txt += "; intervalo no verificado"

    checklist = [
        "Consulta SMN: " + (
            "ambos canales verificados"
            if smn_ok
            else "verificación incompleta"
        ),
        "Resultado regional SMN: " + (
            str(len(avisos_smn)) + " aviso(s) evaluable(s)"
            if avisos_smn
            else (
                "sin avisos coincidentes en la consulta"
                if smn_ok
                else "no se puede confirmar ausencia de avisos"
            )
        ),
        "Consulta de canales SMN: "
        + fecha_argentina(data["smn_consultado_at"]),
        "Cobertura SMN: "
        + str(data["smn_cobertura"] or "no informada"),
        data["smn_criterio"],
        "Lluvia actual: "
        + medida(data["lluvia_actual_mm"], "mm"),
        "Lluvia últimas 24 h: "
        + medida(data["lluvia_24h_mm"], "mm"),
        "Intensidad estimada: "
        + medida(data["intensidad_mm_h"], "mm/h"),
        "Lluvia acumulada 3 días: "
        + medida(data["lluvia_3dias_mm"], "mm"),
        "Fecha del dato meteorológico del proveedor: "
        + fecha_argentina(data["weather_observed_at"]),
        "Estado de meteorología: "
        + data["weather_data_status"],
        "Nivel del río: "
        + medida(data["nivel_rio_m"], "m"),
        "Estación del río: "
        + str(data["river_site_name"] or "sin dato"),
        "Fuente del río: "
        + str(
            data["river_source_name"]
            or data["river_source"]
            or "sin dato"
        ),
        "Enlace de la fuente: "
        + str(data["river_source_url"] or "sin dato"),
        "Referencia del nivel: "
        + str(data["river_reference"] or "sin dato"),
        "Medición del río: "
        + fecha_argentina(data["river_observed_at"]),
        "Antigüedad del río: "
        + texto_antiguedad(data["river_age_minutes"]),
        "Estado del dato del río: "
        + data["river_data_status"],
        "Consulta de la fuente: "
        + fecha_argentina(data["river_fetched_at"]),
        "Medición anterior: "
        + fecha_argentina(
            data["river_previous_observed_at"]
        ),
        tendencia_txt,
        "Nivel de alerta configurado: "
        + medida(data["alerta_rio_m"], "m"),
        "Nivel de evacuación configurado: "
        + medida(data["evacuacion_rio_m"], "m"),
        "Viento: "
        + str(
            data["direccion_viento"]
            or "dirección sin dato"
        )
        + " "
        + medida(data["viento_kmh"], "km/h"),
        (
            "Vigencia operativa: río hasta 3 horas y meteorología "
            "hasta 2 horas. Son criterios propios de HydroGuard."
        ),
    ]

    for aviso in avisos_smn:
        checklist.append(
            "Aviso oficial SMN: "
            + str(aviso.get("evento") or "sin título")
            + "; severidad CAP "
            + str(aviso["severidad_cap"])
            + "; emisión "
            + fecha_argentina(aviso.get("emitido_at"))
            + "; inicio previsto "
            + fecha_argentina(aviso.get("inicio_at"))
            + "; vence "
            + fecha_argentina(aviso.get("vence_at"))
            + "; alcance regional aproximado; "
            + str(aviso.get("url") or "")
        )

    if avisos_smn:
        interpretacion += (
            " Hay avisos oficiales que coinciden con el filtro "
            "regional amplio; su alcance sobre Sarandí debe "
            "revisarse en el aviso. Pueden corresponder "
            "a períodos futuros."
        )

    checklist.extend(
        "Limitación: " + item
        for item in faltantes
    )

    return {
        "semaforo": semaforo,
        "interpretacion": interpretacion,
        "checklist": checklist,
        "conclusion": conclusion,
        "datos": data,
        "meta": {
            "fuentes": list(dict.fromkeys(fuentes)),
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "zona": "Sarandí / Avellaneda",
            "errores_fuentes": errors,
        },
    }