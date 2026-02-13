from conexao import get_db

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()

    # =========================
    # USUARIOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id BIGSERIAL PRIMARY KEY,
        email VARCHAR(150) UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # VEICULOS (app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        modelo VARCHAR(100) NOT NULL,
        placa VARCHAR(20) NOT NULL,
        renavam VARCHAR(50),
        cidade VARCHAR(120) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS placa VARCHAR(20);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS renavam VARCHAR(50);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # Index único (usuario_id, placa)
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname='public' AND indexname='ux_veiculos_usuario_placa'
        ) THEN
            CREATE UNIQUE INDEX ux_veiculos_usuario_placa ON veiculos (usuario_id, placa);
        END IF;
    END$$;
    """)

    # =========================
    # MOTORISTAS (app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motoristas (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        nome VARCHAR(100) NOT NULL,
        cpf VARCHAR(30) NOT NULL,
        nascimento DATE,
        endereco TEXT NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nome VARCHAR(100);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS cpf VARCHAR(30);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nascimento DATE;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS endereco TEXT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # =========================
    # POSTOS (app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        nome VARCHAR(150) NOT NULL,
        endereco TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""ALTER TABLE postos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE postos ADD COLUMN IF NOT EXISTS nome VARCHAR(150);""")
    cur.execute("""ALTER TABLE postos ADD COLUMN IF NOT EXISTS endereco TEXT;""")
    cur.execute("""ALTER TABLE postos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # =========================
    # POSTO_COMBUSTIVEIS (SEM usuario_id)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posto_combustiveis (
        id BIGSERIAL PRIMARY KEY,
        posto_id BIGINT NOT NULL,
        tipo TEXT NOT NULL,
        preco NUMERIC(10,2) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE CASCADE
    );
    """)
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS posto_id BIGINT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS tipo TEXT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS preco NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # =========================
    # ABASTECIMENTOS (app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS abastecimentos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        data DATE NOT NULL,
        hora TIME NOT NULL,
        motorista_id BIGINT NOT NULL,
        veiculo_id BIGINT NOT NULL,
        posto_id BIGINT NOT NULL,
        combustivel_tipo TEXT NOT NULL,
        litros NUMERIC(10,2) NOT NULL,
        preco_total NUMERIC(10,2) NOT NULL,
        preco_unitario NUMERIC(10,4) NOT NULL,
        odometro BIGINT,
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        comprovante_url TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE SET NULL
    );
    """)

    # migração segura (se tabela já existe com nomes antigos)
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS data DATE;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS hora TIME;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS posto_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS combustivel_tipo TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS litros NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS preco_total NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS preco_unitario NUMERIC(10,4);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS odometro BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS pago BOOLEAN DEFAULT FALSE;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS obs TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS comprovante_url TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # Se sua tabela antiga tinha tipo_combustivel/valor_total, copia para os nomes novos
    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='abastecimentos' AND column_name='tipo_combustivel'
        ) THEN
            UPDATE abastecimentos
            SET combustivel_tipo = COALESCE(combustivel_tipo, tipo_combustivel)
            WHERE combustivel_tipo IS NULL;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='abastecimentos' AND column_name='valor_total'
        ) THEN
            UPDATE abastecimentos
            SET preco_total = COALESCE(preco_total, valor_total)
            WHERE preco_total IS NULL;
        END IF;
    END$$;
    """)

    # =========================
    # MANUTENCOES (app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manutencoes (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        data DATE NOT NULL,
        hora TIME NOT NULL,
        motorista_id BIGINT NOT NULL,
        veiculo_id BIGINT NOT NULL,
        valor NUMERIC(10,2) NOT NULL,
        prestador TEXT NOT NULL,
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        comprovante_url TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL
    );
    """)

    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS data DATE;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS hora TIME;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS valor NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS prestador TEXT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS pago BOOLEAN DEFAULT FALSE;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS obs TEXT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS comprovante_url TEXT;""")
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    conn.commit()
    cur.close()
    conn.close()

    print("✅ init_db.py: tabelas criadas/alinhadas com sucesso (app.py).")


if __name__ == "__main__":
    criar_tabelas()
