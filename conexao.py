import os
import psycopg2

def get_db():
    database_url = os.getenv("DATABASE_URL")

    # Se não existir variável de ambiente (rodando local)
    if not database_url:
        database_url = "postgresql://gest_frota_db_user:qiTR2u0e7XTEYLmKFLEJEhLihlFioblR@dpg-d672p00boq4c73atp74g-a.oregon-postgres.render.com/gest_frota_db"

    conn = psycopg2.connect(database_url)
    return conn
