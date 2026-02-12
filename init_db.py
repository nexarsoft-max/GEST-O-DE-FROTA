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
    # EMPRESAS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS empresas (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # MOTORISTAS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motoristas (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        nome VARCHAR(150) NOT NULL,
        cpf VARCHAR(20) NOT NULL,
        nascimento DATE,
        endereco TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        empresa_id INTEGER,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
    );
    """)

    # =========================
    # POSTOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postos (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        nome VARCHAR(150) NOT NULL,
        endereco TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        empresa_id INTEGER,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
    );
    """)

    # =========================
    # VEICULOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        modelo VARCHAR(150) NOT NULL,
        placa VARCHAR(20) NOT NULL,
        renavam VARCHAR(30),
        cidade VARCHAR(100),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        empresa_id INTEGER,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
    );
    """)

    # =========================
    # REGISTROS (ABASTECIMENTO / DESPESAS)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registros (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        data DATE NOT NULL,
        hora TIME NOT NULL,
        motorista_id INTEGER NOT NULL,
        veiculo_id INTEGER NOT NULL,
        posto_id INTEGER,
        combustivel VARCHAR(50),
        litros NUMERIC,
        preco_total NUMERIC,
        preco_unitario NUMERIC,
        odometro INTEGER,
        valor NUMERIC,
        prestador VARCHAR(150),
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE SET NULL
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("🔥 Todas as tabelas criadas com sucesso!")

if __name__ == "__main__":
    criar_tabelas()
