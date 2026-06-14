import psycopg2
from psycopg2.extensions import connection

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "vitalstream",
    "user": "vitalstream",
    "password": "vitalstream",
}


def get_connection() -> connection:
    return psycopg2.connect(**DB_CONFIG)
