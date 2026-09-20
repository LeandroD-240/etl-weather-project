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