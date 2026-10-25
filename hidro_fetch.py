import math
import re
from datetime import datetime, timedelta, timezone

import requests
from lxml import html


URL = "https://www.hidro.gov.ar/Oceanografia/AlturasHorarias.asp"
ARGENTINA = timezone(timedelta(hours=-3))
REFERENCIA = "Plano Único de Reducción de Sondajes del Río de la Plata"


def calcular_tendencia(actual, anterior):
    if actual is None or anterior is None:
        return "sin dato"

    diferencia = round(actual - anterior, 2)

    if abs(diferencia) < 0.01:
        return "invariable"

    return "crece" if diferencia > 0 else "baja"


def convertir_nivel(texto):
    texto = texto.strip().replace(",", ".")

    try:
        valor = float(texto)
        return valor if math.isfinite(valor) else None
    except ValueError:
        return None


def extraer_fecha(texto):
    # El HTML puede unir fecha y hora sin ningún espacio.
    coincidencia = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})",
        " ".join(texto.split()),
    )

    if not coincidencia:
        return None

    try:
        fecha = datetime.strptime(
            " ".join(coincidencia.groups()),
            "%d/%m/%Y %H:%M",
        )
        return fecha.replace(tzinfo=ARGENTINA)
    except ValueError:
        return None


def fetch_hidro():
    try:
        respuesta = requests.get(
            URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 HydroGuard"},
        )
        respuesta.raise_for_status()
        consultado = datetime.now(timezone.utc)
        tree = html.fromstring(respuesta.content)

        filas = tree.xpath(
            '//tr[.//a[@data-nombre="Buenos Aires"]]'
        )
        if not filas:
            raise ValueError("No se encontró la fila de Buenos Aires")

        fila = filas[0]
        tablas = fila.xpath("ancestor::table[1]")
        if not tablas:
            raise ValueError("No se encontró la tabla del mareógrafo")

        celdas = fila.xpath("./th|./td")
        encabezados = None

        for candidata in tablas[0].xpath(".//tr"):
            posibles = candidata.xpath("./th|./td")
            if len(posibles) != len(celdas):
                continue

            fechas = [
                extraer_fecha(celda.text_content())
                for celda in posibles
            ]
            if sum(fecha is not None for fecha in fechas) >= 2:
                encabezados = fechas
                break

        if encabezados is None:
            raise ValueError(
                "No se pudieron asociar las alturas con sus fechas"
            )

        lecturas = [
            (fecha, convertir_nivel(celda.text_content()))
            for celda, fecha in zip(celdas, encabezados)
            if fecha is not None
        ]
        lecturas.sort(key=lambda lectura: lectura[0], reverse=True)

        if not lecturas:
            raise ValueError("No hay columnas de mediciones reconocibles")

        fecha_actual, actual = lecturas[0]
        if actual is None:
            raise ValueError(
                "La medición más reciente de Buenos Aires no tiene dato"
            )

        if fecha_actual > consultado + timedelta(minutes=5):
            raise ValueError("La fuente informa una medición futura")

        fecha_anterior, anterior = (
            lecturas[1] if len(lecturas) > 1 else (None, None)
        )

        variacion = (
            round(actual - anterior, 2)
            if anterior is not None
            else None
        )
        intervalo = (
            round(
                (fecha_actual - fecha_anterior).total_seconds() / 3600,
                2,
            )
            if fecha_anterior is not None
            else None
        )

        data = {
            "source": "hidro_html",
            "source_name": "Servicio de Hidrografía Naval",
            "source_url": URL,
            "station": "Buenos Aires",
            "reference": REFERENCIA,
            "unit": "m",
            "value_m": actual,
            "observed_at": fecha_actual.isoformat(),
            "previous_value_m": anterior,
            "previous_observed_at": (
                fecha_anterior.isoformat()
                if fecha_anterior is not None
                else None
            ),
            "variacion_m": variacion,
            "interval_hours": intervalo,
            "tendencia": calcular_tendencia(actual, anterior),
            "fetched_at": consultado.isoformat(),

            # Compatibilidad: timestamp es la hora de consulta.
            # observed_at es la hora real de medición.
            "timestamp": consultado.isoformat(),
        }

        print(f"OK Hidro: {data}")
        return data

    except Exception as error:
        print(f"[Hidro] error: {error}")
        return None