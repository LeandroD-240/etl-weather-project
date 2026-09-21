import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterator

import requests

from src.config import APIConfig, get_api_config
from src.db import get_connection
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]
MAX_PAST_DAYS = 92
REQUEST_TIMEOUT = (5, 30)  # (timeout for connect, timeout for read)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ExtractionError(Exception):
    """Fallo no recuperable durante la extracción."""


@dataclass(frozen=True)
class City:
    city_id: int
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class CityPayload:
    """Datos crudos de una ciudad: el bloque 'hourly' tal como lo entrega la API."""
    city: City
    hourly: dict


# ---------------------------------------------------------------- lecturas en BD
def get_cities(conn) -> list[City]:
    rows = conn.execute(
        "SELECT city_id, name, latitude, longitude FROM dim_city ORDER BY city_id"
    ).fetchall()
    return [City(r[0], r[1], float(r[2]), float(r[3])) for r in rows]


def get_last_observed(conn) -> dict[int, datetime]:
    rows = conn.execute(
        "SELECT city_id, max(observed_at) FROM fact_weather_hourly GROUP BY city_id"
    ).fetchall()
    return dict(rows)


# ------------------------------------------------------- lógica incremental (pura)
def compute_past_days(
    cities: list[City],
    last_by_city: dict[int, datetime],
    today: date,
    initial_past_days: int,
    lookback_days: int,
) -> int:
    """Cuántos días hacia atrás pedir para cubrir a la ciudad más rezagada."""
    needs = []
    for city in cities:
        last = last_by_city.get(city.city_id)
        if last is None:
            needs.append(initial_past_days)  # ciudad nueva: carga inicial
        else:
            days_behind = (today - last.astimezone(timezone.utc).date()).days
            needs.append(days_behind + lookback_days)

    past_days = max(max(needs), 1)
    if past_days > MAX_PAST_DAYS:
        logger.warning(
            f"Se necesitarían {past_days} días pero el máximo es {MAX_PAST_DAYS}. Usa un backfill para el resto."
        )
        past_days = MAX_PAST_DAYS
    return past_days


# ------------------------------------------------------------------- HTTP
def _api_reason(resp: requests.Response) -> str:
    try:
        return str(resp.json().get("reason", resp.text[:200]))
    except ValueError:
        return resp.text[:200]


def _get_with_retries(session: requests.Session, params: dict, cfg: APIConfig) -> requests.Response:
    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = session.get(cfg.base_url, params=params, timeout=REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = f"{type(exc).__name__}"
        else:
            if resp.status_code == 200:
                return resp
            if resp.status_code not in RETRYABLE_STATUS:
                # 400 y similares: el error es nuestro, reintentar no sirve
                raise ExtractionError(
                    f"HTTP {resp.status_code} no recuperable: {_api_reason(resp)}"
                )
            error = f"HTTP {resp.status_code}"

        if attempt == cfg.max_retries:
            raise ExtractionError(f"Agotados {cfg.max_retries} intentos. Último error: {error}")

        delay = cfg.backoff_base * 2 ** (attempt - 1) + random.uniform(0, 1)
        logger.warning(
            f"Intento {attempt}/{cfg.max_retries} falló ({error}). Reintentando en {delay:.1fs}"
        )
        time.sleep(delay)

    raise ExtractionError("Estado inalcanzable")  # para satisfacer a linters


def fetch_batch(
    session: requests.Session, batch: list[City], past_days: int, cfg: APIConfig
) -> list[CityPayload]:
    params = {
        "latitude": ",".join(str(c.latitude) for c in batch),
        "longitude": ",".join(str(c.longitude) for c in batch),
        "hourly": ",".join(HOURLY_VARIABLES),
        "past_days": past_days,
        "forecast_days": 1,
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    resp = _get_with_retries(session, params, cfg)

    try:
        data = resp.json()
    except ValueError as exc:
        raise ExtractionError("La respuesta de la API no es JSON válido") from exc

    # Una ubicación devuelve un objeto; varias, un arreglo
    results = [data] if isinstance(data, dict) else data
    if len(results) != len(batch):
        raise ExtractionError(
            f"Se pidieron {len(batch)} ubicaciones y llegaron {len(results)} resultados"
        )

    payloads = []
    for city, result in zip(batch, results):  # emparejamos por posición
        hourly = result.get("hourly")
        if not hourly or "time" not in hourly:
            raise ExtractionError(f"Respuesta sin bloque 'hourly' para {city.name}")
        payloads.append(CityPayload(city=city, hourly=hourly))
    return payloads


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def extract_weather(cities: list[City], past_days: int) -> list[CityPayload]:
    cfg = get_api_config()
    batches = list(_chunks(cities, cfg.batch_size))
    payloads: list[CityPayload] = []

    with requests.Session() as session:
        session.headers.update({"User-Agent": "mini-etl-weather/0.1 (portfolio project)"})
        for i, batch in enumerate(batches, start=1):
            logger.info(
                f"Lote {i}/{len(batches)}: {len(batch)} ciudades, past_days={past_days}"
            )
            payloads.extend(fetch_batch(session, batch, past_days, cfg))
            if i < len(batches):
                time.sleep(0.5)  # cortesía con la API entre lotes
    return payloads


# ------------------------------------------------------------- smoke test manual
if __name__ == "__main__":
    setup_logging()
    cfg = get_api_config()

    # La conexión se cierra al salir del bloque, antes de hablar con la API
    with get_connection() as conn:
        cities = get_cities(conn)
        last_by_city = get_last_observed(conn)

    past_days = compute_past_days(
        cities,
        last_by_city,
        today=datetime.now(timezone.utc).date(),
        initial_past_days=cfg.initial_past_days,
        lookback_days=cfg.lookback_days,
    )
    payloads = extract_weather(cities, past_days)

    for p in payloads:
        times = p.hourly["time"]
        logger.info("%-15s %3d horas  %s -> %s", p.city.name, len(times), times[0], times[-1])