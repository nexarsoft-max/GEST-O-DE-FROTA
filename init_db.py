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
        usuario_id BIGINT NOT NULL,
        nome VARCHAR(100) NOT NULL,
        placa VARCHAR(20),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # MOTORISTAS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motoristas (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        nome VARCHAR(100) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # POSTOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        nome VARCHAR(150) NOT NULL,
        endereco TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # POSTO_COMBUSTIVEIS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posto_combustiveis (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        posto_id BIGINT NOT NULL,
        tipo TEXT NOT NULL,
        preco NUMERIC(10,2) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ABASTECIMENTOS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS abastecimentos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        data DATE NOT NULL,
        hora TIME NOT NULL,
        motorista_id BIGINT,
        veiculo_id BIGINT,
        posto_id BIGINT,
        combustivel_tipo TEXT,
        litros NUMERIC(10,2),
        preco_total NUMERIC(10,2),
        preco_unitario NUMERIC(10,2),
        odometro NUMERIC(10,2),
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        comprovante_url TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # MANUTENCOES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manutencoes (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        data DATE NOT NULL,
        hora TIME NOT NULL,
        veiculo_id BIGINT,
        descricao TEXT,
        valor NUMERIC(10,2),
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        comprovante_url TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Banco 100% alinhado com arquitetura nova")

if __name__ == "__main__":
    criar_tabelas()
