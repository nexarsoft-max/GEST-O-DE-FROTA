from conexao import get_db

def criar_tabelas():
    conn = get_db()
    cur = conn.cursor()

    # =========================
    # 0) CORREÇÃO: tabela antiga com acento ("veículos") -> veiculos
    # =========================
    cur.execute("""
    DO $$
    BEGIN
        IF to_regclass('public."veículos"') IS NOT NULL AND to_regclass('public.veiculos') IS NULL THEN
            EXECUTE 'ALTER TABLE "veículos" RENAME TO veiculos';
        END IF;
    END$$;
    """)

    # =========================
    # 1) USUARIOS
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
    # 2) VEICULOS (schema oficial do app)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        modelo VARCHAR(100) NOT NULL,
        placa VARCHAR(20) NOT NULL,
        renavam VARCHAR(50),
        cidade VARCHAR(120) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Garante colunas novas/antigas
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS placa VARCHAR(20);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS renavam VARCHAR(50);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # Se existir coluna antiga "nome", não deixa ela quebrar inserts (NOT NULL)
    # - copia modelo -> nome quando nome estiver NULL
    # - derruba NOT NULL do nome (pra nunca mais quebrar)
    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='veiculos' AND column_name='nome'
        ) THEN
            EXECUTE 'UPDATE veiculos SET nome = COALESCE(nome, modelo, ''SEM NOME'') WHERE nome IS NULL';
            BEGIN
                EXECUTE 'ALTER TABLE veiculos ALTER COLUMN nome DROP NOT NULL';
            EXCEPTION WHEN others THEN
                NULL;
            END;
        END IF;
    END$$;
    """)

    # FK veiculos.usuario_id
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_veiculos_usuario'
        ) THEN
            ALTER TABLE veiculos
            ADD CONSTRAINT fk_veiculos_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    # Unique usuario_id + placa
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
    # 3) MOTORISTAS
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

    # migração segura
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
            SELECT 1 FROM information_schema.table_constraints
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
    # 4) POSTOS
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
            SELECT 1 FROM information_schema.table_constraints
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
    # 5) POSTO_COMBUSTIVEIS (ALINHADO COM app.py)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posto_combustiveis (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        posto_id BIGINT NOT NULL,
        tipo TEXT NOT NULL,
        preco NUMERIC(10,2) NOT NULL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE CASCADE
    );
    """)

    # garante colunas
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS posto_id BIGINT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS tipo TEXT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS preco NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # ✅ Corrige linhas antigas: se usuario_id está NULL, puxa de postos.usuario_id
    cur.execute("""
    UPDATE posto_combustiveis pc
    SET usuario_id = p.usuario_id
    FROM postos p
    WHERE pc.posto_id = p.id
      AND pc.usuario_id IS NULL;
    """)

    # FK usuario_id
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_pc_usuario'
        ) THEN
            ALTER TABLE posto_combustiveis
            ADD CONSTRAINT fk_pc_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END$$;
    """)

    # FK posto_id
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_pc_posto'
        ) THEN
            ALTER TABLE posto_combustiveis
            ADD CONSTRAINT fk_pc_posto
            FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END$$;
    """)

    # Unique usuario_id + posto_id + tipo
    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname='public' AND indexname='ux_pc_usuario_posto_tipo'
        ) THEN
            CREATE UNIQUE INDEX ux_pc_usuario_posto_tipo
            ON posto_combustiveis (usuario_id, posto_id, tipo);
        END IF;
    END$$;
    """)

    # =========================
    # 6) ABASTECIMENTOS (alinhado com app.py)
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
        preco_unitario NUMERIC(10,2) NOT NULL,
        odometro BIGINT,
        pago BOOLEAN DEFAULT FALSE,
        obs TEXT,
        comprovante_url TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE RESTRICT,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE RESTRICT,
        FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE RESTRICT
    );
    """)

    # =========================
    # 7) MANUTENCOES (alinhado com app.py)
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
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE RESTRICT,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE RESTRICT
    );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ init_db.py: tabelas criadas/alinhadas com sucesso.")

if __name__ == "__main__":
    criar_tabelas()
