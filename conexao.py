import psycopg2

def get_db():
    database_url = "postgresql://gestaodefrota_user:pJTUfCEABoDQPK1FtF19zOTgJJLh3aPv@dpg-d7h59ppkh4rs73aj85qg-a/gestaodefrota"

    conn = psycopg2.connect(
        database_url,
        sslmode="require"
    )

    return conn