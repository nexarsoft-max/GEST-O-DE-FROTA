from conexao import get_db

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()

    # =========================
    # USUARIOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        email VARCHAR(150) UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # MOTORISTAS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motoristas (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        cpf VARCHAR(20),
        telefone VARCHAR(20),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # VEICULOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id SERIAL PRIMARY KEY,
        modelo VARCHAR(100) NOT NULL,
        placa VARCHAR(20) UNIQUE NOT NULL,
        motorista_id INTEGER REFERENCES motoristas(id) ON DELETE SET NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # POSTOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postos (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        endereco VARCHAR(200),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # POSTO_PRECOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posto_precos (
        id SERIAL PRIMARY KEY,
        posto_id INTEGER REFERENCES postos(id) ON DELETE CASCADE,
        tipo_combustivel VARCHAR(50) NOT NULL,
        preco NUMERIC(10,2) NOT NULL,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # ABASTECIMENTOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS abastecimentos (
        id SERIAL PRIMARY KEY,
        motorista_id INTEGER REFERENCES motoristas(id) ON DELETE SET NULL,
        veiculo_id INTEGER REFERENCES veiculos(id) ON DELETE SET NULL,
        posto_id INTEGER REFERENCES postos(id) ON DELETE SET NULL,
        litros NUMERIC(10,2) NOT NULL,
        valor_total NUMERIC(10,2) NOT NULL,
        data_abastecimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("Todas as tabelas foram criadas com sucesso.")

if __name__ == "__main__":
    criar_tabelas()
