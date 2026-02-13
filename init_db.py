from conexao import get_db

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()

    # USUARIOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id BIGSERIAL PRIMARY KEY,
        email VARCHAR(150) UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # VEICULOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id BIGSERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        placa VARCHAR(20),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # MOTORISTAS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motoristas (
        id BIGSERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # POSTOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postos (
        id BIGSERIAL PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        endereco TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # POSTO_COMBUSTIVEIS (A QUE ESTAVA FALTANDO)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posto_combustiveis (
        id BIGSERIAL PRIMARY KEY,
        posto_id BIGINT NOT NULL,
        tipo TEXT NOT NULL,
        preco NUMERIC(10,2) NOT NULL,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE CASCADE
    );
    """)

    # ABASTECIMENTOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS abastecimentos (
        id BIGSERIAL PRIMARY KEY,
        veiculo_id BIGINT,
        motorista_id BIGINT,
        posto_id BIGINT,
        tipo_combustivel TEXT,
        litros NUMERIC(10,2),
        valor_total NUMERIC(10,2),
        data DATE,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # MANUTENCOES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manutencoes (
        id BIGSERIAL PRIMARY KEY,
        veiculo_id BIGINT,
        descricao TEXT,
        valor NUMERIC(10,2),
        data DATE,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Todas as tabelas criadas com sucesso.")

if __name__ == "__main__":
    criar_tabelas()
