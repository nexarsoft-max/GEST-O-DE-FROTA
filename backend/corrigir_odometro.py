from conexao import get_db

def corrigir_odometro():
    conn = get_db()
    cur = conn.cursor()

    print("Corrigindo coluna odometro...")

    cur.execute("""
        ALTER TABLE abastecimentos
        ALTER COLUMN odometro TYPE BIGINT
        USING ROUND(COALESCE(odometro, 0))::BIGINT;
    """)

    conn.commit()

    cur.close()
    conn.close()

    print("OK - coluna corrigida.")

if __name__ == "__main__":
    corrigir_odometro()