import logging
from src.logging_config import setup_logging
from pathlib import Path

from src.db import get_connection

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SQL_FILES = ["schema.sql", "seed_cities.sql"]


def init_db() -> None:
    with get_connection() as conn:
        for filename in SQL_FILES:
            path = SQL_DIR / filename
            logger.info(f"Ejecutando {path.name}")
            conn.execute(path.read_text(encoding="utf-8"))
        n_cities = conn.execute("SELECT count(*) FROM dim_city").fetchone()[0]
    logger.info(f"dim_city contiene {n_cities} ciudades")


if __name__ == "__main__":
    setup_logging()
    init_db()