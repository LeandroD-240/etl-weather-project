import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}. Revisa tu archivo .env")
    return value


def get_db_config() -> DBConfig:
    return DBConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=_require("POSTGRES_DB"),
        user=_require("POSTGRES_USER"),
        password=_require("POSTGRES_PASSWORD"),
    )


@dataclass(frozen=True)
class APIConfig:
    base_url: str
    batch_size: int
    initial_past_days: int
    lookback_days: int
    max_retries: int
    backoff_base: float


def get_api_config() -> APIConfig:
    return APIConfig(
        base_url=os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"),
        batch_size=int(os.getenv("API_BATCH_SIZE", "10")),
        initial_past_days=int(os.getenv("INITIAL_PAST_DAYS", "3")),
        lookback_days=int(os.getenv("LOOKBACK_DAYS", "1")),
        max_retries=int(os.getenv("MAX_RETRIES", "4")),
        backoff_base=float(os.getenv("BACKOFF_BASE_SECONDS", "2.0")),
    )