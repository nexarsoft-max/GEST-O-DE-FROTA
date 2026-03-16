import psycopg2

def get_db():
    database_url = "postgresql://banconovo_8p1m_user:Px0f4HjzpddxtuwvoY1dNpr94Wzlp6tc@dpg-d6s6beh5pdvs73fg7cs0-a.oregon-postgres.render.com/banconovo_8p1m"

    conn = psycopg2.connect(
        database_url,
        sslmode="require"
    )

    return conn