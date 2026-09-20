import psycopg

from src.config import get_db_config


def get_connection() -> psycopg.Connection:
    cfg = get_db_config()
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=10,
    )