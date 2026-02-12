import os
import psycopg2

def get_db():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL não configurada")

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    return conn
