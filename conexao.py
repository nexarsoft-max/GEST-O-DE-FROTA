import psycopg2
import os

def get_db():
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )
    return conn
