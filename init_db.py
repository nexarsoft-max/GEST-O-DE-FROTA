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
    # VEICULOS (alinhado ao app.py)
    # colunas esperadas: usuario_id, modelo, placa, renavam, cidade
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

    # Migração segura caso já exista tabela antiga (nome, placa, etc)
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS placa VARCHAR(20);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS renavam VARCHAR(50);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # Se você tinha a coluna antiga "nome", aproveita e copia pro "modelo" quando estiver vazio
    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='veiculos' AND column_name='nome'
        ) THEN
            UPDATE veiculos
            SET modelo = COALESCE(modelo, nome)
            WHERE modelo IS NULL;
        END IF;
    END$$;
    """)

    # Garante NOT NULL onde precisa (somente se não quebrar registros existentes)
    # (Se já tiver dados antigos sem usuario_id/modelo/cidade, você vai precisar ajustar manualmente esses registros.)
    # Mesmo assim, seu app vai funcionar para novos cadastros.

    # Unique por usuário + placa (evita duplicar placa no mesmo usuário)
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = 'ux_veiculos_usuario_placa'
        ) THEN
            CREATE UNIQUE INDEX ux_veiculos_usuario_placa ON veiculos (usuario_id, placa);
        END IF;
    END$$;
    """)

    # FK usuario_id -> usuarios (se ainda não existir)
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_veiculos_usuario'
        ) THEN
            ALTER TABLE veiculos
            ADD CONSTRAINT fk_veiculos_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        -- ignora
        NULL;
    END$$;
    """)

    # =========================
    # MOTORISTAS (alinhado ao app.py)
    # colunas esperadas: usuario_id, nome, cpf, nascimento, endereco
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

    # Migração segura
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nome VARCHAR(100);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS cpf VARCHAR(30);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nascimento DATE;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS endereco TEXT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_motoristas_usuario'
        ) THEN
            ALTER TABLE motoristas
            ADD CONSTRAINT fk_motoristas_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    # =========================
    # POSTOS (alinhado ao seu app: usa usuario_id nas queries)
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

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_postos_usuario'
        ) THEN
            ALTER TABLE postos
            ADD CONSTRAINT fk_postos_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    # =========================
    # POSTO_COMBUSTIVEIS
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
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # =========================
    # ABASTECIMENTOS (já deixo alinhado pro próximo passo)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS abastecimentos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        veiculo_id BIGINT,
        motorista_id BIGINT,
        posto_id BIGINT,
        tipo_combustivel TEXT,
        litros NUMERIC(10,2),
        valor_total NUMERIC(10,2),
        data DATE,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE SET NULL
    );
    """)
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")

    # =========================
    # MANUTENCOES (já deixo alinhado pro próximo passo)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manutencoes (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        veiculo_id BIGINT,
        descricao TEXT,
        valor NUMERIC(10,2),
        data DATE,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL
    );
    """)
    cur.execute("""ALTER TABLE manutencoes ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")

    conn.commit()
    cur.close()
    conn.close()

    print("✅ init_db.py: tabelas criadas/alinhadas com sucesso.")

if __name__ == "__main__":
    criar_tabelas()
