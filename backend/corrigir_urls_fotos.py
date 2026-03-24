from conexao import get_db

def coluna_existe(cur, tabela, coluna):
    cur.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
        LIMIT 1
    """, (tabela, coluna))
    return cur.fetchone() is not None

def main():
    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        url_antiga = "https://gorota-vehicle-photos.s3.us-east-1.amazonaws.com"
        url_nova = "https://pub-561cfae6f6e84157963a7bee03def00e.r2.dev"

        # foto_entrada_url
        if coluna_existe(cur, "expedientes", "foto_entrada_url"):
            cur.execute(f"""
                UPDATE expedientes
                SET foto_entrada_url = REPLACE(
                    foto_entrada_url,
                    %s,
                    %s
                )
                WHERE foto_entrada_url LIKE %s
            """, (url_antiga, url_nova, f"{url_antiga}%"))
            print("foto_entrada_url corrigida.")

        # foto_saida_url
        if coluna_existe(cur, "expedientes", "foto_saida_url"):
            cur.execute(f"""
                UPDATE expedientes
                SET foto_saida_url = REPLACE(
                    foto_saida_url,
                    %s,
                    %s
                )
                WHERE foto_saida_url LIKE %s
            """, (url_antiga, url_nova, f"{url_antiga}%"))
            print("foto_saida_url corrigida.")

        # foto_odometro_entrada_url (só se existir)
        if coluna_existe(cur, "expedientes", "foto_odometro_entrada_url"):
            cur.execute(f"""
                UPDATE expedientes
                SET foto_odometro_entrada_url = REPLACE(
                    foto_odometro_entrada_url,
                    %s,
                    %s
                )
                WHERE foto_odometro_entrada_url LIKE %s
            """, (url_antiga, url_nova, f"{url_antiga}%"))
            print("foto_odometro_entrada_url corrigida.")
        else:
            print("Coluna foto_odometro_entrada_url não existe. Ignorando.")

        conn.commit()
        print("URLs corrigidas com sucesso.")

    except Exception as e:
        if conn:
            conn.rollback()
        print("Erro ao corrigir URLs:", e)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()