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
        IF to_regclass('public."veículos"') IS NOT NULL
           AND to_regclass('public.veiculos') IS NULL THEN
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
    # 2) VEICULOS
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

    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS placa VARCHAR(20);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS renavam VARCHAR(50);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);""")
    cur.execute("""ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'veiculos'
              AND column_name = 'nome'
        ) THEN
            EXECUTE 'UPDATE veiculos
                     SET nome = COALESCE(nome, modelo, ''SEM NOME'')
                     WHERE nome IS NULL';
            BEGIN
                EXECUTE 'ALTER TABLE veiculos ALTER COLUMN nome DROP NOT NULL';
            EXCEPTION WHEN others THEN
                NULL;
            END;
        END IF;
    END$$;
    """)

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
        NULL;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_veiculos_usuario_placa'
        ) THEN
            CREATE UNIQUE INDEX ux_veiculos_usuario_placa
            ON veiculos (usuario_id, placa);
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
        email VARCHAR(150),
        senha_hash TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nome VARCHAR(100);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS cpf VARCHAR(30);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS nascimento DATE;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS endereco TEXT;""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS email VARCHAR(150);""")
    cur.execute("""ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS senha_hash TEXT;""")
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

    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_motoristas_usuario_email'
        ) THEN
            DROP INDEX ux_motoristas_usuario_email;
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_motoristas_email'
        ) THEN
            CREATE UNIQUE INDEX ux_motoristas_email
            ON motoristas (email)
            WHERE email IS NOT NULL;
        END IF;
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
    # 5) POSTO_COMBUSTIVEIS
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

    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS posto_id BIGINT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS tipo TEXT;""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS preco NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE posto_combustiveis ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    UPDATE posto_combustiveis pc
    SET usuario_id = p.usuario_id
    FROM postos p
    WHERE pc.posto_id = p.id
      AND pc.usuario_id IS NULL;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_pc_usuario'
        ) THEN
            ALTER TABLE posto_combustiveis
            ADD CONSTRAINT fk_pc_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_pc_posto'
        ) THEN
            ALTER TABLE posto_combustiveis
            ADD CONSTRAINT fk_pc_posto
            FOREIGN KEY (posto_id) REFERENCES postos(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_pc_usuario_posto_tipo'
        ) THEN
            CREATE UNIQUE INDEX ux_pc_usuario_posto_tipo
            ON posto_combustiveis (usuario_id, posto_id, tipo);
        END IF;
    END$$;
    """)

    # =========================
    # 6) ABASTECIMENTOS
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

    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS data DATE;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS hora TIME;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS posto_id BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS combustivel_tipo TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS litros NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS preco_total NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS preco_unitario NUMERIC(10,2);""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS odometro BIGINT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS pago BOOLEAN DEFAULT FALSE;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS obs TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS comprovante_url TEXT;""")
    cur.execute("""ALTER TABLE abastecimentos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    # =========================
    # 7) MANUTENCOES
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

    # =========================
    # 8) SESSOES MOBILE DOS MOTORISTAS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motorista_sessoes_mobile (
        id BIGSERIAL PRIMARY KEY,
        motorista_id BIGINT NOT NULL,
        token_hash TEXT NOT NULL,
        dispositivo VARCHAR(200),
        expira_em TIMESTAMP NOT NULL,
        ultimo_uso_em TIMESTAMP,
        revogado_em TIMESTAMP,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS token_hash TEXT;""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS dispositivo VARCHAR(200);""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS expira_em TIMESTAMP;""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS ultimo_uso_em TIMESTAMP;""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS revogado_em TIMESTAMP;""")
    cur.execute("""ALTER TABLE motorista_sessoes_mobile ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_motorista_sessoes_mobile_token_hash'
        ) THEN
            CREATE UNIQUE INDEX ux_motorista_sessoes_mobile_token_hash
            ON motorista_sessoes_mobile (token_hash);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_motorista_sessoes_mobile_motorista'
        ) THEN
            CREATE INDEX ix_motorista_sessoes_mobile_motorista
            ON motorista_sessoes_mobile (motorista_id);
        END IF;
    END$$;
    """)

    # =========================
    # 9) TERMOS ACEITOS NO MOBILE
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS motorista_termos_aceites (
        id BIGSERIAL PRIMARY KEY,
        motorista_id BIGINT NOT NULL,
        usuario_id BIGINT NOT NULL,
        termos_versao VARCHAR(30) NOT NULL,
        texto_termos TEXT NOT NULL,
        aceito_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ip_aceite VARCHAR(100),
        dispositivo VARCHAR(200),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS termos_versao VARCHAR(30);""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS texto_termos TEXT;""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS aceito_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS ip_aceite VARCHAR(100);""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS dispositivo VARCHAR(200);""")
    cur.execute("""ALTER TABLE motorista_termos_aceites ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_motorista_termos_aceites_motorista'
        ) THEN
            CREATE UNIQUE INDEX ux_motorista_termos_aceites_motorista
            ON motorista_termos_aceites (motorista_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_motorista_termos_aceites_usuario'
        ) THEN
            CREATE INDEX ix_motorista_termos_aceites_usuario
            ON motorista_termos_aceites (usuario_id);
        END IF;
    END$$;
    """)

    # =========================
    # 10) VÍNCULO MOTORISTA-VEÍCULO EM USO
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos_uso (
        id BIGSERIAL PRIMARY KEY,
        motorista_id BIGINT NOT NULL,
        veiculo_id BIGINT NOT NULL,
        usuario_id BIGINT NOT NULL,
        ativo BOOLEAN DEFAULT TRUE,
        iniciado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finalizado_em TIMESTAMP,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS iniciado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS finalizado_em TIMESTAMP;""")
    cur.execute("""ALTER TABLE veiculos_uso ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_veiculos_uso_motorista'
        ) THEN
            CREATE INDEX ix_veiculos_uso_motorista
            ON veiculos_uso (motorista_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_veiculos_uso_veiculo'
        ) THEN
            CREATE INDEX ix_veiculos_uso_veiculo
            ON veiculos_uso (veiculo_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_veiculos_uso_usuario'
        ) THEN
            CREATE INDEX ix_veiculos_uso_usuario
            ON veiculos_uso (usuario_id);
        END IF;
    END$$;
    """)

       # =========================
    # 11) EXPEDIENTES
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expedientes (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        colaborador_id BIGINT,
        motorista_id BIGINT,
        veiculo_id BIGINT,

        data DATE DEFAULT CURRENT_DATE,

        horario_inicio TIMESTAMP,
        horario_fim TIMESTAMP,

        checklist_entrada JSONB,
        checklist_saida JSONB,

        foto_entrada_url TEXT,
        foto_saida_url TEXT,
        foto_odometro_entrada_url TEXT,

        -- =========================
        -- DANOS NA ENTRADA
        -- =========================
        foto_dano_entrada_url_1 TEXT,
        foto_dano_entrada_url_2 TEXT,
        foto_dano_entrada_url_3 TEXT,

        -- =========================
        -- DANOS NA SAÍDA
        -- =========================
        veiculo_danificado_saida BOOLEAN DEFAULT FALSE,
        observacao_dano_saida TEXT,
        foto_dano_saida_url_1 TEXT,
        foto_dano_saida_url_2 TEXT,
        foto_dano_saida_url_3 TEXT,

        status VARCHAR(30) DEFAULT 'em_andamento',
        ajustado BOOLEAN DEFAULT FALSE,
        motivo_ajuste TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    # garante colunas caso já exista tabela antiga
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS colaborador_id BIGINT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS motorista_id BIGINT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")

    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS data DATE DEFAULT CURRENT_DATE;""")

    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS horario_inicio TIMESTAMP;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS horario_fim TIMESTAMP;""")

    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS checklist_entrada JSONB;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS checklist_saida JSONB;""")

    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_entrada_url TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_saida_url TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_odometro_entrada_url TEXT;""")

    # =========================
    # DANOS NA ENTRADA
    # =========================
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_entrada_url_1 TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_entrada_url_2 TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_entrada_url_3 TEXT;""")

    # =========================
    # DANOS NA SAÍDA
    # =========================
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS veiculo_danificado_saida BOOLEAN DEFAULT FALSE;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS observacao_dano_saida TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_saida_url_1 TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_saida_url_2 TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS foto_dano_saida_url_3 TEXT;""")

    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'em_andamento';""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS ajustado BOOLEAN DEFAULT FALSE;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS motivo_ajuste TEXT;""")
    cur.execute("""ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_expedientes_usuario'
        ) THEN
            ALTER TABLE expedientes
            ADD CONSTRAINT fk_expedientes_usuario
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'colaborador_id'
        ) AND EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'motoristas'
        ) THEN
            BEGIN
                ALTER TABLE expedientes
                ADD CONSTRAINT fk_expedientes_colaborador
                FOREIGN KEY (colaborador_id) REFERENCES motoristas(id) ON DELETE SET NULL;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'motorista_id'
        ) AND EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'motoristas'
        ) THEN
            BEGIN
                ALTER TABLE expedientes
                ADD CONSTRAINT fk_expedientes_motorista
                FOREIGN KEY (motorista_id) REFERENCES motoristas(id) ON DELETE SET NULL;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'veiculo_id'
        ) AND EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'veiculos'
        ) THEN
            BEGIN
                ALTER TABLE expedientes
                ADD CONSTRAINT fk_expedientes_veiculo
                FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_usuario'
        ) THEN
            CREATE INDEX ix_expedientes_usuario
            ON expedientes (usuario_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_colaborador'
        ) THEN
            CREATE INDEX ix_expedientes_colaborador
            ON expedientes (colaborador_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_motorista'
        ) THEN
            CREATE INDEX ix_expedientes_motorista
            ON expedientes (motorista_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_veiculo'
        ) THEN
            CREATE INDEX ix_expedientes_veiculo
            ON expedientes (veiculo_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_status'
        ) THEN
            CREATE INDEX ix_expedientes_status
            ON expedientes (status);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_expedientes_data'
        ) THEN
            CREATE INDEX ix_expedientes_data
            ON expedientes (data);
        END IF;
    END$$;
    """)
    # =========================
    # 11) LOCALIZAÇÕES DOS VEÍCULOS (RASTREAMENTO)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS veiculos_localizacao (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        veiculo_id BIGINT NOT NULL,
        latitude NUMERIC(10,6) NOT NULL,
        longitude NUMERIC(10,6) NOT NULL,
        velocidade_kmh NUMERIC(10,2),
        endereco TEXT,
        recebido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS ix_localizacao_veiculo
    ON veiculos_localizacao (veiculo_id);
    """)

    # =========================
    # 12) RASTREADORES
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rastreadores (
        id BIGSERIAL PRIMARY KEY,
        imei VARCHAR(50) UNIQUE NOT NULL,
        veiculo_id BIGINT NOT NULL,
        usuario_id BIGINT NOT NULL,
        ativo BOOLEAN DEFAULT TRUE,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE rastreadores ADD COLUMN IF NOT EXISTS imei VARCHAR(50);""")
    cur.execute("""ALTER TABLE rastreadores ADD COLUMN IF NOT EXISTS veiculo_id BIGINT;""")
    cur.execute("""ALTER TABLE rastreadores ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE rastreadores ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;""")
    cur.execute("""ALTER TABLE rastreadores ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_rastreadores_imei'
        ) THEN
            CREATE INDEX ix_rastreadores_imei
            ON rastreadores (imei);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_localizacao_usuario_veiculo_recebido_em'
        ) THEN
            CREATE INDEX ix_localizacao_usuario_veiculo_recebido_em
            ON veiculos_localizacao (usuario_id, veiculo_id, recebido_em DESC);
        END IF;
    END$$;
    """)

    # =========================
    # 13) ALERTAS RESOLVIDOS
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alertas_resolvidos (
        id BIGSERIAL PRIMARY KEY,
        usuario_id BIGINT NOT NULL,
        alerta_id TEXT NOT NULL,
        alerta_tipo TEXT,
        expediente_id BIGINT,
        resolvido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""ALTER TABLE alertas_resolvidos ADD COLUMN IF NOT EXISTS usuario_id BIGINT;""")
    cur.execute("""ALTER TABLE alertas_resolvidos ADD COLUMN IF NOT EXISTS alerta_id TEXT;""")
    cur.execute("""ALTER TABLE alertas_resolvidos ADD COLUMN IF NOT EXISTS alerta_tipo TEXT;""")
    cur.execute("""ALTER TABLE alertas_resolvidos ADD COLUMN IF NOT EXISTS expediente_id BIGINT;""")
    cur.execute("""ALTER TABLE alertas_resolvidos ADD COLUMN IF NOT EXISTS resolvido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ux_alertas_resolvidos_usuario_alerta'
        ) THEN
            CREATE UNIQUE INDEX ux_alertas_resolvidos_usuario_alerta
            ON alertas_resolvidos (usuario_id, alerta_id);
        END IF;
    END$$;
    """)

    cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'ix_alertas_resolvidos_usuario'
        ) THEN
            CREATE INDEX ix_alertas_resolvidos_usuario
            ON alertas_resolvidos (usuario_id);
        END IF;
    END$$;
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ init_db.py: tabelas criadas/alinhadas com sucesso.")


if __name__ == "__main__":
    criar_tabelas()