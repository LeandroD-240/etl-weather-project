import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from src.extract import CityPayload

logger = logging.getLogger(__name__)

# Mismos límites que los CHECK de sql/schema.sql, mantenidos en un solo lugar
# para no tener que sincronizar dos definiciones a mano.
RANGES = {
    "temperature_c":    (-90.0, 60.0),
    "humidity_pct":     (0.0, 100.0),
    "precipitation_mm": (0.0, None),
    "wind_speed_kmh":   (0.0, None),
}

HOURLY_FIELD_MAP = {
    "temperature_2m": "temperature_c",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
}


@dataclass(frozen=True)
class ValidRow:
    city_id: int
    observed_at: datetime
    temperature_c: float | None
    humidity_pct: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None


@dataclass(frozen=True)
class QuarantinedRow:
    city_id: int | None
    observed_at: datetime | None
    temperature_c: float | None
    humidity_pct: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None
    rejection_reason: str


@dataclass(frozen=True)
class TransformResult:
    valid_rows: list[ValidRow]
    quarantined_rows: list[QuarantinedRow]
    rows_seen: int          # todo lo que llegó de la API, incluyendo horas futuras
    rows_future_skipped: int  # horas futuras descartadas (no son un error)


def _parse_observed_at(raw_time: str) -> datetime:
    """La API devuelve, p.ej., '2026-09-21T14:00'. Con timezone=UTC en la
    request, ese instante YA está en UTC; solo falta declarar el offset."""
    return datetime.fromisoformat(raw_time).replace(tzinfo=timezone.utc)


def _validate_ranges(values: dict[str, float | None]) -> str | None:
    """Devuelve el motivo de rechazo, o None si todo está dentro de rango."""
    for field, value in values.items():
        if value is None:
            continue
        low, high = RANGES[field]
        if low is not None and value < low:
            return f"{field}={value} por debajo del mínimo ({low})"
        if high is not None and value > high:
            return f"{field}={value} por encima del máximo ({high})"
    return None


def transform_payload(payload: CityPayload, now: datetime) -> TransformResult:
    hourly = payload.hourly
    times = hourly["time"]
    valid_rows: list[ValidRow] = []
    quarantined_rows: list[QuarantinedRow] = []
    future_skipped = 0

    for idx, raw_time in enumerate(times):
        try:
            observed_at = _parse_observed_at(raw_time)
        except ValueError as exc:
            quarantined_rows.append(QuarantinedRow(
                city_id=payload.city.city_id, observed_at=None,
                temperature_c=None, humidity_pct=None,
                precipitation_mm=None, wind_speed_kmh=None,
                rejection_reason=f"timestamp inválido '{raw_time}': {exc}",
            ))
            continue

        if observed_at > now:
            future_skipped += 1
            continue

        values = {}
        for api_field, column in HOURLY_FIELD_MAP.items():
            raw_value = hourly.get(api_field, [None] * len(times))[idx]
            values[column] = float(raw_value) if raw_value is not None else None

        reason = _validate_ranges(values)
        if reason is not None:
            quarantined_rows.append(QuarantinedRow(
                city_id=payload.city.city_id, observed_at=observed_at,
                rejection_reason=reason, **values,
            ))
            continue

        valid_rows.append(ValidRow(
            city_id=payload.city.city_id, observed_at=observed_at, **values,
        ))

    return TransformResult(
        valid_rows=valid_rows,
        quarantined_rows=quarantined_rows,
        rows_seen=len(times),
        rows_future_skipped=future_skipped,
    )


def transform_all(payloads: list[CityPayload], now: datetime | None = None) -> TransformResult:
    now = now or datetime.now(timezone.utc)
    valid_rows: list[ValidRow] = []
    quarantined_rows: list[QuarantinedRow] = []
    rows_seen = 0
    future_skipped = 0

    for payload in payloads:
        result = transform_payload(payload, now)
        valid_rows.extend(result.valid_rows)
        quarantined_rows.extend(result.quarantined_rows)
        rows_seen += result.rows_seen
        future_skipped += result.rows_future_skipped

        if result.quarantined_rows:
            logger.warning(
                "%s: %d fila(s) en cuarentena", payload.city.name, len(result.quarantined_rows)
            )

    logger.info(
        "Transform: %d filas vistas, %d futuras omitidas, %d válidas, %d en cuarentena",
        rows_seen, future_skipped, len(valid_rows), len(quarantined_rows),
    )
    return TransformResult(valid_rows, quarantined_rows, rows_seen, future_skipped)


# ------------------------------------------------------------- smoke test manual
if __name__ == "__main__":
    from datetime import date

    from src.db import get_connection
    from src.extract import compute_past_days, extract_weather, get_cities, get_last_observed
    from src.config import get_api_config
    from src.logging_config import setup_logging

    setup_logging()
    cfg = get_api_config()

    with get_connection() as conn:
        cities = get_cities(conn)
        last_by_city = get_last_observed(conn)

    past_days = compute_past_days(
        cities, last_by_city, date.today(), cfg.initial_past_days, cfg.lookback_days
    )
    payloads = extract_weather(cities, past_days)
    result = transform_all(payloads)

    print(f"\nVálidas: {len(result.valid_rows)}")
    if result.valid_rows:
        print("Ejemplo:", result.valid_rows[0])
    print(f"Cuarentena: {len(result.quarantined_rows)}")
    for row in result.quarantined_rows[:5]:
        print(" -", row)