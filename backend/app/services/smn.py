"""Consulta pública de alertas CAP del SMN.

Sin credenciales ni dependencias adicionales.

La cobertura es deliberadamente conservadora: rectángulo regional que
incluye Sarandí y las cuencas cercanas. No representa un límite de cuenca.

No convierte severidad CAP en un supuesto color oficial del SMN.
"""

import copy
import math
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse


FEEDS = {
    "alertas": "https://ssl.smn.gob.ar/CAP/AR.php",
    "acp": (
        "https://ssl.smn.gob.ar/feeds/CAP/"
        "avisocortoplazo/rss_acpCAP.xml"
    ),
}

NS = {
    "c": "urn:oasis:names:tc:emergency:cap:1.2",
}

# Sur, oeste, norte, este.
# Filtro regional amplio, no catastro hidrológico.
REGION = (-35.10, -58.60, -34.55, -58.10)

TTL_SECONDS = 300

# Criterio operativo propio de HydroGuard, no del SMN.
MAX_FEED_AGE_SECONDS = 7200

_LOCK = threading.Lock()
_CACHE = None
_CACHE_TIME = 0.0


def _date(value):
    if not value:
        raise ValueError("Fecha ausente")

    try:
        result = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
    except ValueError:
        result = parsedate_to_datetime(value)

    if result.tzinfo is None:
        raise ValueError("Fecha sin zona horaria")

    return result


def _xml(url):
    parsed = urlparse(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname != "ssl.smn.gob.ar"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError(
            "Enlace CAP fuera del origen oficial esperado"
        )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HydroGuard/1.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=12,
    ) as response:
        final = urlparse(response.geturl())

        if (
            final.scheme != "https"
            or final.hostname != "ssl.smn.gob.ar"
        ):
            raise ValueError(
                "Redirección fuera del origen oficial"
            )

        raw = response.read(2_000_001)

    if (
        len(raw) > 2_000_000
        or b"<!DOCTYPE" in raw.upper()
    ):
        raise ValueError("Documento XML no admitido")

    return ET.fromstring(raw)


def _regional(area):
    """Intersección de envolventes de polígonos.

    Prioriza no omitir avisos cercanos.

    Puede incluir avisos cuyo polígono real no intersecte
    la región. Esta aproximación se informa en la respuesta.
    """
    polygons = area.findall("c:polygon", NS)

    if not polygons:
        raise ValueError(
            "Área CAP sin polígono: cobertura no verificable"
        )

    hit = False

    for polygon in polygons:
        points = []

        for pair in (polygon.text or "").split():
            lat, lon = map(float, pair.split(","))

            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                raise ValueError(
                    "Coordenada CAP inválida"
                )

            points.append((lat, lon))

        if (
            len(points) < 4
            or points[0] != points[-1]
        ):
            raise ValueError(
                "Polígono CAP incompleto"
            )

        south, west, north, east = REGION

        hit |= (
            min(p[0] for p in points) <= north
            and max(p[0] for p in points) >= south
            and min(p[1] for p in points) <= east
            and max(p[1] for p in points) >= west
        )

    return hit


def _cap(url):
    root = _xml(url)

    if root.tag != "{" + NS["c"] + "}alert":
        raise ValueError(
            "Documento no es CAP 1.2"
        )

    def field(name):
        return root.findtext(
            "c:" + name,
            default="",
            namespaces=NS,
        )

    identifier = field("identifier")

    if not identifier:
        raise ValueError(
            "CAP sin identificador"
        )

    sent = _date(field("sent"))

    return (
        root,
        identifier,
        sent,
        field("status"),
        field("msgType"),
        field("references"),
    )


def _collect(now):
    errors = []
    records = []
    feeds = []
    links = {}

    for kind, url in FEEDS.items():
        try:
            channel = _xml(url).find("channel")

            if channel is None:
                raise ValueError(
                    "RSS sin canal"
                )

            built = _date(
                channel.findtext("lastBuildDate")
            )

            age = (
                now - built
            ).total_seconds()

            if not (
                -300 <= age <= MAX_FEED_AGE_SECONDS
            ):
                raise ValueError(
                    "RSS atrasado o con fecha futura"
                )

            items = channel.findall("item")

            if not items:
                raise ValueError(
                    "RSS vacío sin confirmación explícita"
                )

            for item in items:
                description = " ".join(
                    (
                        item.findtext("description") or ""
                    ).lower().split()
                )

                if (
                    kind == "acp"
                    and "no se han emitido avisos"
                    in description
                ):
                    continue

                link = item.findtext("link")

                if not link:
                    raise ValueError(
                        "Ítem RSS sin enlace CAP"
                    )

                links[link] = kind

            feeds.append(
                {
                    "tipo": kind,
                    "url": url,
                    "publicado_at": built.isoformat(),
                }
            )

        except Exception as error:
            errors.append(
                kind + ": " + str(error)
            )

    documents = []

    with ThreadPoolExecutor(
        max_workers=4
    ) as pool:
        jobs = [
            (
                url,
                pool.submit(_cap, url),
            )
            for url in links
        ]

        for url, job in jobs:
            try:
                documents.append(
                    (
                        url,
                        job.result(),
                    )
                )

            except Exception as error:
                errors.append(
                    url + ": " + str(error)
                )

    superseded = set()

    for _, document in documents:
        (
            _,
            _,
            sent,
            status,
            message,
            references,
        ) = document

        if (
            status == "Actual"
            and sent <= now
            and message in {"Update", "Cancel"}
        ):
            for reference in references.split():
                parts = reference.split(",")

                if len(parts) == 3:
                    superseded.add(parts[1])

    for url, document in documents:
        (
            root,
            identifier,
            sent,
            status,
            message,
            _,
        ) = document

        if (
            status != "Actual"
            or identifier in superseded
            or message == "Cancel"
        ):
            continue

        if (
            message not in {"Alert", "Update"}
            or sent > now
        ):
            errors.append(
                identifier
                + ": tipo o emisión CAP no evaluable"
            )
            continue

        try:
            infos = root.findall(
                "c:info",
                NS,
            )

            if not infos:
                raise ValueError(
                    "CAP sin información"
                )

            for info in infos:

                def field(name):
                    return info.findtext(
                        "c:" + name,
                        default="",
                        namespaces=NS,
                    )

                expires = _date(
                    field("expires")
                )

                if expires <= now:
                    continue

                effective = _date(
                    field("effective")
                    or sent.isoformat()
                )

                onset = _date(
                    field("onset")
                    or effective.isoformat()
                )

                areas = info.findall(
                    "c:area",
                    NS,
                )

                if not areas:
                    raise ValueError(
                        "CAP vigente sin áreas"
                    )

                matches = [
                    _regional(area)
                    for area in areas
                ]

                if not any(matches):
                    continue

                severity = field("severity")

                if severity not in {
                    "Minor",
                    "Moderate",
                    "Severe",
                    "Extreme",
                }:
                    raise ValueError(
                        "Severidad CAP no evaluable"
                    )

                records.append(
                    {
                        "id": identifier,
                        "tipo": links[url],
                        "evento": field("event"),
                        "severidad_cap": severity,
                        "color_oficial": None,
                        "emitido_at": sent.isoformat(),
                        "efectivo_at": (
                            effective.isoformat()
                        ),
                        "inicio_at": onset.isoformat(),
                        "vence_at": expires.isoformat(),
                        "periodo": (
                            "previsto"
                            if onset > now
                            else "en vigencia"
                        ),
                        "descripcion": (
                            field("description")
                        ),
                        "instrucciones": (
                            field("instruction")
                        ),
                        "url": url,
                    }
                )

        except Exception as error:
            errors.append(
                identifier + ": " + str(error)
            )

    return {
        "verificado": (
            not errors
            and len(feeds) == len(FEEDS)
        ),
        "consultado_at": now.isoformat(),
        "avisos": records,
        "fuentes": feeds,
        "errores": errors,
        "cobertura": (
            "Filtro regional amplio por envolventes, "
            "no límite exacto de cuencas; "
            "puede incluir avisos vecinos."
        ),
        "region_sur_oeste_norte_este": list(
            REGION
        ),
        "max_antiguedad_rss_segundos": (
            MAX_FEED_AGE_SECONDS
        ),
    }


def fetch_smn():
    """Devuelve evidencia y fallas.

    Nunca transforma errores en ausencia de avisos.
    """
    global _CACHE, _CACHE_TIME

    with _LOCK:
        if (
            _CACHE is not None
            and time.monotonic() - _CACHE_TIME
            < TTL_SECONDS
        ):
            return copy.deepcopy(_CACHE)

        result = _collect(
            datetime.now(timezone.utc)
        )

        _CACHE = result
        _CACHE_TIME = time.monotonic()

        return copy.deepcopy(result)