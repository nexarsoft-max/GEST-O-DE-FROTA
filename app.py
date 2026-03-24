import os
import re
import hashlib
import secrets 
import json
from datetime import timedelta, date, datetime

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from werkzeug.security import check_password_hash, generate_password_hash
from psycopg2 import errors

from conexao import get_db

print(">>> APP.PY CARREGADO:", __file__, flush=True)

# =========================
# R2 CONFIG (Render ENV)
# =========================
import boto3
import os

R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL")

print("R2 ENDPOINT:", R2_ENDPOINT, flush=True)
print("R2 BUCKET:", R2_BUCKET_NAME, flush=True)
print("R2 PUBLIC URL:", R2_PUBLIC_BASE_URL, flush=True)

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto"
)

def montar_url_publica_r2(chave_arquivo: str) -> str:
    return f"{R2_PUBLIC_BASE_URL}/{chave_arquivo.lstrip('/')}"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

# ✅ cria/alinha tabelas ao subir
from init_db import criar_tabelas

with app.app_context():
    criar_tabelas()

app.config["SECRET_KEY"] = "gorota-dev"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # localhost sem https
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)  # 1 ano


from flask import request, jsonify
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def pergunta_valida(pergunta):
    palavras_permitidas = [
        "abastecimento", "combustivel", "litros", "km", "odometro",
        "veiculo", "motorista", "posto", "custo", "gasto",
        "media", "dashboard", "consumo", "manutencao"
    ]

    pergunta = (pergunta or "").lower()
    return any(p in pergunta for p in palavras_permitidas)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    pergunta = (data.get("message") or data.get("mensagem") or "").strip()

    # ✅ Resposta simples para saudações
    if pergunta.lower() in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"):
        return jsonify({
            "resposta": "Oi! 😊 Me diga sua dúvida sobre abastecimentos, veículos, motoristas, postos, manutenção ou dashboard."
        })

    # ❌ bloqueia perguntas fora do sistema
    if not pergunta_valida(pergunta):
        return jsonify({
            "resposta": "Só posso ajudar com dados da frota (abastecimentos, veículos, motoristas, postos, manutenção e dashboard)."
        })

    def _cols(cur, table_name: str):
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        return {r[0] for r in cur.fetchall()}

    def _pick(existing_cols, candidates, default=None):
        for c in candidates:
            if c in existing_cols:
                return c
        return default

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cols_ab = _cols(cur, "abastecimentos")
        cols_v = _cols(cur, "veiculos")
        cols_m = _cols(cur, "motoristas")
        cols_p = _cols(cur, "postos")

        # ✅ escolhe automaticamente os nomes reais das colunas
        col_data = _pick(cols_ab, ["data", "criado_em"], default="criado_em")
        col_litros = _pick(cols_ab, ["litros"], default=None)
        col_valor = _pick(cols_ab, ["valor_total", "preco_total", "valor", "preco"], default=None)
        col_comb = _pick(cols_ab, ["tipo_combustivel", "combustivel_tipo"], default=None)

        # ids (pra fazer join)
        col_veic_id = _pick(cols_ab, ["veiculo_id"], default=None)
        col_mot_id = _pick(cols_ab, ["motorista_id"], default=None)
        col_posto_id = _pick(cols_ab, ["posto_id"], default=None)

        # nomes nas tabelas relacionadas
        col_veic_nome = _pick(cols_v, ["nome", "modelo", "placa"], default=None)
        col_mot_nome = _pick(cols_m, ["nome"], default=None)
        col_posto_nome = _pick(cols_p, ["nome"], default=None)

        # ✅ monta SELECT sem referenciar coluna que não existe
        select_parts = [f"a.{col_data} AS data"]

        # Veículo
        if col_veic_id and col_veic_nome:
            select_parts.append(f"COALESCE(v.{col_veic_nome}::text,'') AS veiculo")
        else:
            select_parts.append("'' AS veiculo")

        # Motorista
        if col_mot_id and col_mot_nome:
            select_parts.append(f"COALESCE(m.{col_mot_nome}::text,'') AS motorista")
        else:
            select_parts.append("'' AS motorista")

        # Posto
        if col_posto_id and col_posto_nome:
            select_parts.append(f"COALESCE(p.{col_posto_nome}::text,'') AS posto")
        else:
            select_parts.append("'' AS posto")

        # Combustível
        if col_comb:
            select_parts.append(f"COALESCE(a.{col_comb}::text,'') AS combustivel")
        else:
            select_parts.append("'' AS combustivel")

        # Litros
        if col_litros:
            select_parts.append(f"COALESCE(a.{col_litros},0) AS litros")
        else:
            select_parts.append("0 AS litros")

        # Valor total
        if col_valor:
            select_parts.append(f"COALESCE(a.{col_valor},0) AS valor_total")
        else:
            select_parts.append("0 AS valor_total")

        select_sql = ",\n                ".join(select_parts)

        joins = []
        if col_veic_id and col_veic_nome:
            joins.append("LEFT JOIN veiculos v ON v.id = a.veiculo_id")
        if col_mot_id and col_mot_nome:
            joins.append("LEFT JOIN motoristas m ON m.id = a.motorista_id")
        if col_posto_id and col_posto_nome:
            joins.append("LEFT JOIN postos p ON p.id = a.posto_id")

        joins_sql = "\n            ".join(joins)

        sql = f"""
            SELECT
                {select_sql}
            FROM abastecimentos a
            {joins_sql}
            ORDER BY a.id DESC
            LIMIT 30
        """

        cur.execute(sql)
        dados = cur.fetchall()

        if not dados:
            return jsonify({"resposta": "Ainda não existem abastecimentos cadastrados no sistema."})

        contexto = "\n".join([
            f"Data: {str(d[0])} | Veículo: {d[1]} | Motorista: {d[2]} | Posto: {d[3]} | Combustível: {d[4]} | Litros: {d[5]} | Valor: R$ {d[6]}"
            for d in dados
        ])

        prompt = f"""
Você é a assistente Nexar do sistema de gestão de frota.

REGRAS (obrigatório):
- Responda SOMENTE sobre o sistema (abastecimentos, veículos, motoristas, postos, manutenção, dashboard).
- Use APENAS os dados fornecidos abaixo.
- NÃO invente informações.
- Se a pergunta não puder ser respondida com os dados, diga: "Não há dados suficientes para responder."

DADOS DISPONÍVEIS (últimos 30 abastecimentos):
{contexto}

PERGUNTA DO USUÁRIO:
{pergunta}
"""

        # ✅ CHAMADA OPENAI (com tratamento de erro)
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Responda apenas com base nos dados. Não invente nada."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            return jsonify({"resposta": resposta.choices[0].message.content})

        except Exception as e:
            msg = str(e)

            # ✅ 429 / sem créditos / quota
            if ("Error code: 429" in msg) or ("insufficient_quota" in msg) or ("quota" in msg.lower()):
                return jsonify({
                    "resposta": "Seu Assistente de métricas está indisponível no momento, entre em contato com o suporte."
                })

            # ✅ 401 / chave inválida
            if ("401" in msg) or ("authentication" in msg.lower()) or ("api key" in msg.lower()):
                return jsonify({
                    "resposta": "Seu Assistente de métricas está indisponível no momento, entre em contato com o suporte."
                })

            # ✅ qualquer outro erro da IA
            return jsonify({
                "resposta": "Seu Assistente de métricas está indisponível no momento, entre em contato com o suporte."
            })

    except Exception as e:
        # erro geral (banco/sql/etc)
        return jsonify({"resposta": f"Erro: {str(e)}"})

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
# =========================
# LOG
# =========================
@app.before_request
def log_requests():
    print(f"[REQ] {request.method} {request.path}", flush=True)


# =========================
# HELPERS
# =========================
def email_valido(email: str) -> bool:
    regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(regex, email) is not None


def logado() -> bool:
    return "usuario_id" in session


def usuario_id_atual() -> int:
    return int(session["usuario_id"])


def proteger_pagina():
    if not logado():
        return redirect(url_for("home"))
    return None


def proteger_api():
    if not logado():
        return jsonify({"sucesso": False, "erro": "Sessão expirada. Faça login novamente."}), 401
    return None

# =========================
# MOBILE AUTH HELPERS
# =========================
MOBILE_SESSION_DAYS = 90

def _hash_mobile_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _gerar_mobile_token() -> str:
    return secrets.token_urlsafe(48)

def _mobile_bearer_token():
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    return token or None

def proteger_api_mobile():
    token = _mobile_bearer_token()
    if not token:
        return jsonify({
            "sucesso": False,
            "erro": "Token ausente"
        }), 401

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        token_hash = _hash_mobile_token(token)

        cur.execute("""
            SELECT
                s.id,
                s.motorista_id,
                m.usuario_id,
                m.nome,
                COALESCE(m.email, ''),
                s.expira_em,
                s.revogado_em
            FROM motorista_sessoes_mobile s
            INNER JOIN motoristas m
                ON m.id = s.motorista_id
            WHERE s.token_hash = %s
            LIMIT 1
        """, (token_hash,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Token inválido"
            }), 401

        sessao_id, motorista_id, usuario_id, nome, email, expira_em, revogado_em = row

        if revogado_em is not None:
            return jsonify({
                "sucesso": False,
                "erro": "Sessão encerrada"
            }), 401

        if expira_em is None or expira_em <= datetime.utcnow():
            return jsonify({
                "sucesso": False,
                "erro": "Sessão expirada"
            }), 401

        cur.execute("""
            UPDATE motorista_sessoes_mobile
            SET ultimo_uso_em = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (sessao_id,))
        conn.commit()

        g.mobile_auth = {
            "sessao_id": int(sessao_id),
            "motorista_id": int(motorista_id),
            "usuario_id": int(usuario_id),
            "nome": nome,
            "email": email,
        }
        return None

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO proteger_api_mobile:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro interno na autenticação mobile"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def _posto_completo_por_id(cur, usuario_id: int, posto_id: int):
    # ✅ ALINHADO COM init_db.py:
    # posto_combustiveis TEM usuario_id => filtra também por pc.usuario_id
    cur.execute("""
        SELECT
            p.id, p.nome, p.endereco,
            pc.tipo, pc.preco
        FROM postos p
        LEFT JOIN posto_combustiveis pc
            ON pc.posto_id = p.id
           AND pc.usuario_id = p.usuario_id
        WHERE p.id = %s AND p.usuario_id = %s
        ORDER BY pc.tipo ASC
    """, (posto_id, usuario_id))
    rows = cur.fetchall()
    if not rows:
        return None

    pid, nome, endereco, _, _ = rows[0]
    posto = {"id": pid, "nome": nome, "endereco": endereco, "combustiveis": []}
    for _, _, _, tipo, preco in rows:
        if tipo is not None:
            posto["combustiveis"].append({
                "tipo": str(tipo),
                "preco": float(preco) if preco is not None else 0.0
            })
    return posto


def _odometro_to_int(odometro):
    # aceita "12.345", "12,345", "12345 km" etc
    odo_digits = re.sub(r"[^\d]", "", str(odometro or ""))
    return int(odo_digits) if odo_digits else None

def _parse_checklist_json(raw_checklist):
    """
    Aceita:
    - None / vazio -> {}
    - dict já pronto -> dict
    - string JSON válida -> dict/list
    Rejeita string inválida.
    """
    if raw_checklist is None:
        return {}

    if isinstance(raw_checklist, (dict, list)):
        return raw_checklist

    texto = str(raw_checklist).strip()
    if not texto:
        return {}

    try:
        return json.loads(texto)
    except Exception:
        raise ValueError("Checklist inválido. Envie um JSON válido.")
# =========================
# LOGIN (compatível com JSON e FORM)
# =========================
@app.get("/")
def home():
    return render_template("login.html")


@app.get("/login")
def login_get():
    return render_template("login.html")


@app.post("/login")
def login():
    dados = request.get_json(silent=True)

    if dados is None:
        # FORM
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        modo = "form"
    else:
        # JSON
        email = (dados.get("email") or "").strip().lower()
        senha = dados.get("senha") or ""
        modo = "json"

    if not email or not senha:
        if modo == "form":
            return redirect(url_for("home"))
        return jsonify({"sucesso": False, "erro": "Email e senha obrigatórios"}), 400

    if not email_valido(email):
        if modo == "form":
            return redirect(url_for("home"))
        return jsonify({"sucesso": False, "erro": "Email inválido"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, senha_hash FROM usuarios WHERE email = %s", (email,))
        usuario = cur.fetchone()

        if not usuario:
            if modo == "form":
                return redirect(url_for("home"))
            return jsonify({"sucesso": False, "erro": "E-mail ou senha inválidos"}), 401

        user_id, senha_hash = usuario

        if check_password_hash(senha_hash, senha):
            session.clear()
            session["usuario_id"] = int(user_id)
            session["email"] = email
            session.permanent = True

            if modo == "form":
                return redirect(url_for("dashboard"))
            return jsonify({"sucesso": True}), 200

        if modo == "form":
            return redirect(url_for("home"))
        return jsonify({"sucesso": False, "erro": "E-mail ou senha inválidos"}), 401

    except Exception as e:
        print("ERRO LOGIN:", e, flush=True)
        if modo == "form":
            return redirect(url_for("home"))
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# PÁGINAS
# =========================
@app.get("/dashboard")
def dashboard():
    r = proteger_pagina()
    if r:
        return r
    return render_template("dashboard.html")


@app.get("/monitoramento")
def monitoramento():
    r = proteger_pagina()
    if r:
        return r
    return render_template("monitoramento.html")

@app.get("/colaboradores")
def colaboradores():
    r = proteger_pagina()
    if r:
        return r
    return render_template("colaboradores.html")

@app.get("/mapa-geral")
def mapa_geral():
    r = proteger_pagina()
    if r:
        return r
    return render_template("mapa_geral.html")


@app.get("/localizacao/<int:veiculo_id>")
def localizacao_veiculo(veiculo_id):
    r = proteger_pagina()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, modelo, placa, cidade
            FROM veiculos
            WHERE id = %s AND usuario_id = %s
        """, (veiculo_id, uid))

        row = cur.fetchone()
        if not row:
            return redirect(url_for("monitoramento"))

        veiculo = {
            "id": row[0],
            "modelo": row[1],
            "placa": row[2],
            "cidade": row[3],
            "status": "offline",
            "motoristaNome": "Aguardando vínculo do app",
            "velocidade_kmh": None,
            "combustivel_pct": None,
            "ultima_atualizacao": "Sem atualização",
            "endereco": "Localização indisponível no momento",
            "lat": None,
            "lng": None,
            "telefone_motorista": ""
        }

        import json
        return render_template("localizacao.html", veiculo_json=json.dumps(veiculo))

    except Exception as e:
        print("ERRO localizacao_veiculo:", e, flush=True)
        return redirect(url_for("monitoramento"))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
@app.get("/api/monitoramento/resumo")
def api_monitoramento_resumo():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                v.id,
                v.modelo,
                v.placa,
                v.cidade,
                vu.motorista_id,
                m.nome
            FROM veiculos v
            LEFT JOIN veiculos_uso vu
                ON vu.veiculo_id = v.id
               AND vu.ativo = TRUE
            LEFT JOIN motoristas m
                ON m.id = vu.motorista_id
            WHERE v.usuario_id = %s
            ORDER BY v.id DESC
        """, (uid,))

        veiculos_rows = cur.fetchall()

        data_out = []

        for row in veiculos_rows:
            veiculo_id, modelo, placa, cidade, motorista_id, motorista_nome = row

            data_out.append({
                "id": int(veiculo_id),
                "nome": modelo,
                "modelo": modelo,
                "placa": placa,
                "cidade": cidade,

                # continua dependendo do rastreador depois
                "status": "offline",
                "motoristaNome": motorista_nome if motorista_nome else None,
                "velocidade_kmh": None,
                "combustivel_pct": None,
                "ultima_atualizacao": None,
                "ultima_atualizacao_label": None,
                "lat": None,
                "lng": None,
                "endereco": None,
                "telefone_motorista": None
            })

        return jsonify(data_out), 200

    except Exception as e:
        print("ERRO api_monitoramento_resumo:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/geralinformacao", endpoint="geral_informacao")
def geral_informacao_page():
    r = proteger_pagina()
    if r:
        return r
    return render_template("geralinformacao.html")


@app.get("/geral_informacao")
def geral_informacao_alias():
    r = proteger_pagina()
    if r:
        return r
    return redirect("/geralinformacao")


@app.get("/editarmotorista/<int:motorista_id>")
def editarmotorista(motorista_id):
    r = proteger_pagina()
    if r:
        return r
    return render_template("editarmotorista.html", motorista_id=motorista_id)


@app.get("/abastecimento")
def abastecimento():
    r = proteger_pagina()
    if r:
        return r
    return render_template("abastecimento.html")


@app.get("/editarveiculo/<int:veiculo_id>")
def editarveiculo(veiculo_id):
    r = proteger_pagina()
    if r:
        return r
    return render_template("editarveiculo.html", veiculo_id=veiculo_id)


@app.get("/cadastro")
def cadastro():
    r = proteger_pagina()
    if r:
        return r
    return render_template("cadastro.html")


@app.get("/ajuda")
def ajuda():
    r = proteger_pagina()
    if r:
        return r
    return render_template("ajuda.html")


@app.get("/dentroveiculo")
def dentroveiculo():
    r = proteger_pagina()
    if r:
        return r
    return render_template("dentroveiculo.html")


@app.get("/dentromotorista")
def dentromotorista():
    r = proteger_pagina()
    if r:
        return r
    return render_template("dentromotorista.html")


@app.get("/dentroposto")
def dentroposto():
    r = proteger_pagina()
    if r:
        return r
    return render_template("dentroposto.html")


@app.get("/cadastrarveiculo")
def cadastrarveiculo():
    r = proteger_pagina()
    if r:
        return r
    return render_template("cadastrarveiculo.html")


@app.get("/cadastrarmotorista")
def cadastrarmotorista():
    r = proteger_pagina()
    if r:
        return r
    return render_template("cadastrarmotorista.html")


@app.get("/cadastrarposto")
def cadastrarposto():
    r = proteger_pagina()
    if r:
        return r
    return render_template("cadastrarposto.html")


@app.get("/editarposto/<int:posto_id>")
def editarposto(posto_id: int):
    r = proteger_pagina()
    if r:
        return r
    return render_template("editarposto.html", posto_id=posto_id)


# ✅✅✅ CORREÇÃO DO ERRO: endpoint "termos" EXISTE AGORA
@app.get("/termos")
def termos():
    r = proteger_pagina()
    if r:
        return r
    return render_template("termos.html")


# =========================
# ✅ API REGISTROS
# =========================
@app.get("/api/registros")
def api_registros_get():
    r = proteger_api()
    if r:
        return r
    return api_historico()


# =========================
# API VEÍCULOS
# =========================
@app.route("/api/veiculos", methods=["GET", "POST"], strict_slashes=False)
def api_veiculos():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    if request.method == "GET":
        conn = cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, modelo, placa, renavam, cidade
                FROM veiculos
                WHERE usuario_id = %s
                ORDER BY id DESC
            """, (uid,))
            rows = cur.fetchall()
            data = [{"id": i, "modelo": m, "placa": p, "renavam": rnv, "cidade": c} for (i, m, p, rnv, c) in rows]
            return jsonify(data), 200
        except Exception as e:
            print("ERRO api_veiculos GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    dados = request.get_json(silent=True) or {}

    # ✅ compatibilidade: alguns front-ends antigos mandam "nome" ao invés de "modelo"
    modelo = (dados.get("modelo") or dados.get("nome") or "").strip()
    placa = (dados.get("placa") or "").strip().upper()
    cidade = (dados.get("cidade") or "").strip()
    renavam = (dados.get("renavam") or "").strip()

    if not modelo or not placa or not cidade:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios: modelo (ou nome), placa, cidade"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO veiculos (usuario_id, modelo, placa, renavam, cidade)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (uid, modelo, placa, renavam if renavam else None, cidade))
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "id": new_id}), 201
    except errors.UniqueViolation:
        if conn:
            conn.rollback()
        return jsonify({"sucesso": False, "erro": "Já existe um veículo com essa placa para este usuário."}), 409
    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_veiculos POST:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/veiculos/<int:veiculo_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False)
def api_veiculo_por_id(veiculo_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute("""
                SELECT id, modelo, placa, renavam, cidade
                FROM veiculos
                WHERE id = %s AND usuario_id = %s
            """, (veiculo_id, uid))

            row = cur.fetchone()
            if not row:
                return jsonify({"sucesso": False, "erro": "Veículo não encontrado"}), 404

            return jsonify({
                "id": row[0],
                "modelo": row[1],
                "placa": row[2],
                "renavam": row[3],
                "cidade": row[4]
            }), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}

            # ✅ compatibilidade: aceita "nome" também
            modelo = (dados.get("modelo") or dados.get("nome") or "").strip()
            placa = (dados.get("placa") or "").strip().upper()
            renavam = (dados.get("renavam") or "").strip()
            cidade = (dados.get("cidade") or "").strip()

            if not modelo or not placa or not cidade:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios"}), 400

            cur.execute("""
                UPDATE veiculos
                SET modelo = %s,
                    placa = %s,
                    renavam = %s,
                    cidade = %s
                WHERE id = %s AND usuario_id = %s
            """, (modelo, placa, renavam or None, cidade, veiculo_id, uid))

            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Veículo não encontrado"}), 404

            conn.commit()
            return jsonify({"sucesso": True}), 200

        # DELETE
        cur.execute("""
            DELETE FROM veiculos
            WHERE id = %s AND usuario_id = %s
        """, (veiculo_id, uid))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Veículo não encontrado"}), 404

        conn.commit()
        return jsonify({"sucesso": True}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_veiculo_por_id:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# API MOTORISTAS
# =========================
@app.route("/api/motoristas", methods=["GET", "POST"], strict_slashes=False)
def api_motoristas():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    if request.method == "GET":
        conn = cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nome, cpf, nascimento, endereco, COALESCE(email, '')
                FROM motoristas
                WHERE usuario_id = %s
                ORDER BY id DESC
            """, (uid,))
            rows = cur.fetchall()

            data_out = []
            for (i, nome, cpf, nasc, end, email) in rows:
                data_out.append({
                    "id": i,
                    "nome": nome,
                    "cpf": cpf,
                    "nascimento": (nasc.isoformat() if nasc else ""),
                    "endereco": end,
                    "email": email,
                })
            return jsonify(data_out), 200

        except Exception as e:
            print("ERRO api_motoristas GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # POST
    dados = request.get_json(silent=True) or {}

    nome = (dados.get("nome") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    nascimento = (dados.get("nascimento") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = (dados.get("senha") or "").strip()

    if not nome or not cpf or not endereco or not email or not senha:
        return jsonify({
            "sucesso": False,
            "erro": "Campos obrigatórios: nome, cpf, endereco, email, senha"
        }), 400

    if not email_valido(email):
        return jsonify({"sucesso": False, "erro": "Email inválido"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # email global único para login mobile
        cur.execute("""
            SELECT 1
            FROM motoristas
            WHERE email = %s
        """, (email,))
        if cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Email já cadastrado para outro motorista"}), 409

        senha_hash = generate_password_hash(senha)

        cur.execute("""
            INSERT INTO motoristas (usuario_id, nome, cpf, nascimento, endereco, email, senha_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            uid,
            nome,
            cpf,
            nascimento if nascimento else None,
            endereco,
            email,
            senha_hash
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "id": new_id}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_motoristas POST:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/motoristas/<int:motorista_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False)
def api_motorista_por_id(motorista_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute("""
                SELECT id, nome, cpf, nascimento, endereco, COALESCE(email, '')
                FROM motoristas
                WHERE id = %s AND usuario_id = %s
            """, (motorista_id, uid))

            row = cur.fetchone()
            if not row:
                return jsonify({"sucesso": False, "erro": "Motorista não encontrado"}), 404

            return jsonify({
                "id": row[0],
                "nome": row[1],
                "cpf": row[2],
                "nascimento": row[3].isoformat() if row[3] else "",
                "endereco": row[4],
                "email": row[5]
            }), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}

            nome = (dados.get("nome") or "").strip()
            cpf = (dados.get("cpf") or "").strip()
            nascimento = (dados.get("nascimento") or "").strip()
            endereco = (dados.get("endereco") or "").strip()
            email = (dados.get("email") or "").strip().lower()
            senha = (dados.get("senha") or "").strip()

            if not nome or not cpf or not endereco or not email:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios: nome, cpf, endereco, email"}), 400

            if not email_valido(email):
                return jsonify({"sucesso": False, "erro": "Email inválido"}), 400

            # email global único para login mobile
            cur.execute("""
                SELECT 1
                FROM motoristas
                WHERE email = %s
                  AND id <> %s
            """, (email, motorista_id))

            if cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Email já cadastrado para outro motorista"}), 409

            if senha:
                senha_hash = generate_password_hash(senha)

                cur.execute("""
                    UPDATE motoristas
                    SET nome = %s,
                        cpf = %s,
                        nascimento = %s,
                        endereco = %s,
                        email = %s,
                        senha_hash = %s
                    WHERE id = %s AND usuario_id = %s
                """, (
                    nome,
                    cpf,
                    nascimento if nascimento else None,
                    endereco,
                    email,
                    senha_hash,
                    motorista_id,
                    uid
                ))

                motorista_atualizado = cur.rowcount

                # derruba todas as sessões mobile ao trocar senha
                cur.execute("""
                    UPDATE motorista_sessoes_mobile
                    SET revogado_em = CURRENT_TIMESTAMP
                    WHERE motorista_id = %s
                      AND revogado_em IS NULL
                """, (motorista_id,))
            else:
                cur.execute("""
                    UPDATE motoristas
                    SET nome = %s,
                        cpf = %s,
                        nascimento = %s,
                        endereco = %s,
                        email = %s
                    WHERE id = %s AND usuario_id = %s
                """, (
                    nome,
                    cpf,
                    nascimento if nascimento else None,
                    endereco,
                    email,
                    motorista_id,
                    uid
                ))

                motorista_atualizado = cur.rowcount

            if motorista_atualizado == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Motorista não encontrado"}), 404

            conn.commit()
            return jsonify({"sucesso": True}), 200

        # DELETE
        cur.execute("""
            DELETE FROM motoristas
            WHERE id = %s AND usuario_id = %s
        """, (motorista_id, uid))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Motorista não encontrado"}), 404

        conn.commit()
        return jsonify({"sucesso": True}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_motorista_por_id:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    
    
# =========================
# API MOBILE - LOGIN
# =========================
@app.post("/api/mobile/login")
def api_mobile_login():
    dados = request.get_json(silent=True) or {}

    email = (dados.get("email") or "").strip().lower()
    senha = (dados.get("senha") or "").strip()
    dispositivo = (dados.get("dispositivo") or "").strip()

    if not email or not senha:
        return jsonify({
            "sucesso": False,
            "erro": "Email e senha são obrigatórios"
        }), 400

    if not email_valido(email):
        return jsonify({
            "sucesso": False,
            "erro": "Email inválido"
        }), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, usuario_id, nome, COALESCE(email, ''), senha_hash
            FROM motoristas
            WHERE email = %s
            LIMIT 1
        """, (email,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "E-mail ou senha inválidos"
            }), 401

        motorista_id, usuario_id, nome, email_db, senha_hash = row

        if not senha_hash:
            return jsonify({
                "sucesso": False,
                "erro": "Este colaborador ainda não possui acesso mobile configurado"
            }), 403

        if not check_password_hash(senha_hash, senha):
            return jsonify({
                "sucesso": False,
                "erro": "E-mail ou senha inválidos"
            }), 401

        cur.execute("""
            UPDATE motorista_sessoes_mobile
            SET revogado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND revogado_em IS NULL
              AND expira_em <= CURRENT_TIMESTAMP
        """, (motorista_id,))

        token = _gerar_mobile_token()
        token_hash = _hash_mobile_token(token)

        cur.execute("""
            INSERT INTO motorista_sessoes_mobile (
                motorista_id,
                token_hash,
                dispositivo,
                expira_em,
                ultimo_uso_em
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '90 days', CURRENT_TIMESTAMP)
            RETURNING id, expira_em, criado_em
        """, (
            motorista_id,
            token_hash,
            dispositivo if dispositivo else None
        ))

        sessao_id, expira_em, criado_em = cur.fetchone()
        conn.commit()

        return jsonify({
            "sucesso": True,
            "token": token,
            "token_type": "Bearer",
            "expira_em": expira_em.isoformat() if expira_em else None,
            "sessao": {
                "id": int(sessao_id),
                "criado_em": criado_em.isoformat() if criado_em else None
            },
            "motorista": {
                "id": int(motorista_id),
                "usuario_id": int(usuario_id),
                "nome": nome,
                "email": email_db
            }
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_mobile_login:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro interno ao autenticar no mobile"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/api/colaboradores/<int:expediente_id>/detalhe")
def api_detalhe_expediente(expediente_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    def _normalizar_checklist(valor):
        if valor is None:
            return {
                "itens": [],
                "veiculo_perfeito": None,
                "observacao": "",
                "quantidade_cones": "",
                "trabalhando_em_dupla_ou_mais": None,
                "nomes_dupla_ou_mais": "",
                "confirmacao_veracidade": False
            }

        if isinstance(valor, str):
            texto = valor.strip()
            if not texto:
                return {
                    "itens": [],
                    "veiculo_perfeito": None,
                    "observacao": "",
                    "quantidade_cones": "",
                    "trabalhando_em_dupla_ou_mais": None,
                    "nomes_dupla_ou_mais": "",
                    "confirmacao_veracidade": False
                }

            try:
                valor = json.loads(texto)
            except Exception:
                return {
                    "itens": [texto],
                    "veiculo_perfeito": None,
                    "observacao": "",
                    "quantidade_cones": "",
                    "trabalhando_em_dupla_ou_mais": None,
                    "nomes_dupla_ou_mais": "",
                    "confirmacao_veracidade": False
                }

        if isinstance(valor, list):
            return {
                "itens": [str(item) for item in valor],
                "veiculo_perfeito": None,
                "observacao": "",
                "quantidade_cones": "",
                "trabalhando_em_dupla_ou_mais": None,
                "nomes_dupla_ou_mais": "",
                "confirmacao_veracidade": False
            }

        if isinstance(valor, dict):
            itens_lista = []

            if isinstance(valor.get("itens_marcados"), list):
                itens_lista = [
                    str(item).strip()
                    for item in valor.get("itens_marcados", [])
                    if str(item).strip()
                ]

            elif isinstance(valor.get("itens"), dict):
                itens_lista = [
                    str(chave).strip()
                    for chave, marcado in valor.get("itens", {}).items()
                    if (
                        marcado is True
                        or str(marcado).strip().lower() in ("ok", "sim", "true", "1", "conforme")
                    )
                    and str(chave).strip()
                ]

            elif isinstance(valor.get("itens"), list):
                itens_lista = [
                    str(item).strip()
                    for item in valor.get("itens", [])
                    if str(item).strip()
                ]

            elif isinstance(valor.get("checklist"), list):
                itens_lista = [
                    str(item).strip()
                    for item in valor.get("checklist", [])
                    if str(item).strip()
                ]

            elif isinstance(valor.get("items"), list):
                itens_lista = [
                    str(item).strip()
                    for item in valor.get("items", [])
                    if str(item).strip()
                ]

            else:
                itens_lista = [
                    str(chave).strip()
                    for chave, marcado in valor.items()
                    if (
                        marcado is True
                        or str(marcado).strip().lower() in ("ok", "sim", "true", "1", "conforme")
                    )
                    and str(chave).strip()
                    and chave not in (
                        "veiculo_perfeito",
                        "observacao",
                        "tipo",
                        "placa",
                        "modelo",
                        "quantidade_cones",
                        "trabalhando_em_dupla_ou_mais",
                        "nomes_dupla_ou_mais",
                        "confirmacao_veracidade",
                        "veiculo_danificado",
                        "estado_veiculo"
                    )
                ]

            return {
                "itens": itens_lista,
                "veiculo_perfeito": valor.get("veiculo_perfeito"),
                "observacao": str(valor.get("observacao") or "").strip(),
                "quantidade_cones": str(valor.get("quantidade_cones") or "").strip(),
                "trabalhando_em_dupla_ou_mais": valor.get("trabalhando_em_dupla_ou_mais"),
                "nomes_dupla_ou_mais": str(valor.get("nomes_dupla_ou_mais") or "").strip(),
                "confirmacao_veracidade": bool(valor.get("confirmacao_veracidade"))
            }

        return {
            "itens": [str(valor).strip()] if str(valor).strip() else [],
            "veiculo_perfeito": None,
            "observacao": "",
            "quantidade_cones": "",
            "trabalhando_em_dupla_ou_mais": None,
            "nomes_dupla_ou_mais": "",
            "confirmacao_veracidade": False
        }

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                checklist_entrada,
                checklist_saida,
                foto_entrada_url,
                foto_saida_url,
                horario_inicio,
                horario_fim
            FROM expedientes
            WHERE id = %s
              AND usuario_id = %s
            LIMIT 1
        """, (expediente_id, uid))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Expediente não encontrado"
            }), 404

        checklist_entrada = _normalizar_checklist(row[0])
        checklist_saida = _normalizar_checklist(row[1])

        return jsonify({
            "sucesso": True,
            "checklist_entrada": checklist_entrada["itens"],
            "checklist_saida": checklist_saida["itens"],
            "checklist_entrada_detalhe": checklist_entrada,
            "checklist_saida_detalhe": checklist_saida,
            "fotoEntrada": row[2] or "",
            "fotoSaida": row[3] or "",
            "horaEntrada": row[4].strftime("%H:%M") if row[4] else "",
            "horaSaida": row[5].strftime("%H:%M") if row[5] else ""
        }), 200

    except Exception as e:
        print("ERRO api_detalhe_expediente:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao carregar detalhe do expediente"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/api/mobile/terms/status")
def api_mobile_terms_status():
    r = proteger_api_mobile()
    if r:
        return r

    motorista_id = int(g.mobile_auth["motorista_id"])

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                termos_versao,
                aceito_em,
                COALESCE(ip_aceite, ''),
                COALESCE(dispositivo, ''),
                COALESCE(texto_termos, '')
            FROM motorista_termos_aceites
            WHERE motorista_id = %s
            LIMIT 1
        """, (motorista_id,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": True,
                "accepted": False,
                "terms_version": TERMOS_MOBILE_VERSAO_ATUAL,
                "accepted_at": None,
                "terms_text": TERMOS_MOBILE_TEXTO
            }), 200

        termos_versao, aceito_em, ip_aceite, dispositivo, texto_termos = row

        return jsonify({
            "sucesso": True,
            "accepted": True,
            "terms_version": termos_versao or TERMOS_MOBILE_VERSAO_ATUAL,
            "accepted_at": aceito_em.isoformat() if aceito_em else None,
            "ip": ip_aceite or "",
            "dispositivo": dispositivo or "",
            "terms_text": texto_termos or TERMOS_MOBILE_TEXTO
        }), 200

    except Exception as e:
        print("ERRO api_mobile_terms_status:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao consultar status dos termos"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()






# =========================
# API MOBILE - TERMOS (CONFIG)
# =========================
TERMOS_MOBILE_VERSAO_ATUAL = "1.0"

TERMOS_MOBILE_TEXTO = """
1. Direitos Autorais
Todos os direitos reservados pela agência Nexar. Este aplicativo e todo seu conteúdo, incluindo mas não se limitando a texto, gráficos, logotipos, ícones e imagens, são propriedade da Nexar e estão protegidos por leis de direitos autorais nacionais e internacionais.

2. Suporte e Contato
Caso haja alguma dúvida referente à aplicação, entre em contato diretamente com o gestor responsável. Nossa equipe está disponível para esclarecer questões técnicas, funcionais ou operacionais relacionadas ao uso do GoRota.

3. Privacidade e Segurança de Dados
Todos os dados são monitorados pela aplicação conforme regras internas de segurança e rastreabilidade. Isso inclui, mas não se limita a:

Registros de ponto (entrada e saída)
Checklists de veículos e ferramentas
Fotografias e documentação relacionada
Localização e dados de uso do aplicativo
4. Uso Responsável
Ao utilizar o GoRota, você concorda em usar o aplicativo de forma responsável e em conformidade com todas as políticas internas da empresa. O uso inadequado ou não autorizado do sistema pode resultar em sanções conforme as normas trabalhistas e políticas organizacionais.

5. Atualizações dos Termos
A Nexar se reserva o direito de atualizar estes termos a qualquer momento. Os usuários serão notificados sobre alterações significativas e deverão aceitar os novos termos para continuar utilizando o aplicativo.

6. Autorização de Uso de Imagem
Ao aceitar estes termos, o usuário autoriza, de forma expressa e irrevogável, o uso de sua imagem que possa ser capturada durante a utilização do aplicativo GoRota, incluindo mas não se limitando a fotografias de vistoria de veículos, registros de atividades operacionais e documentação de processos internos.

Esta autorização abrange a captação, armazenamento, processamento e utilização da imagem para finalidades exclusivamente relacionadas ao controle de jornada, segurança operacional, auditoria interna e cumprimento de regulamentações trabalhistas vigentes.

O usuário declara estar ciente de que as imagens coletadas poderão ser armazenadas em servidores seguros e acessadas por gestores autorizados para fins de supervisão, análise de conformidade e resolução de eventuais divergências operacionais, sempre respeitando os princípios de privacidade e proteção de dados pessoais.

7. Responsabilidade do Usuário e Limitação de Responsabilidade
O usuário é integralmente responsável pela veracidade, exatidão e completude das informações registradas no aplicativo GoRota, incluindo mas não se limitando a registros de ponto, checklists de veículos, relatórios de atividades e demais dados inseridos durante a operação do sistema.

A Nexar e seus representantes não se responsabilizam por quaisquer danos, prejuízos, acidentes, multas, sanções ou perdas decorrentes de:

Preenchimento incorreto, incompleto ou fraudulento dos checklists de veículos e ferramentas
Omissão de informações relevantes sobre condições do veículo ou equipamentos
Utilização de veículos ou equipamentos em condições inadequadas identificadas ou não reportadas no checklist
Registros de jornada imprecisos ou manipulados pelo usuário
Má utilização do aplicativo em desconformidade com as diretrizes operacionais estabelecidas
O aplicativo GoRota é uma ferramenta de auxílio ao controle de jornada e vistoria operacional, não substituindo a responsabilidade individual do usuário pela inspeção física adequada dos veículos, cumprimento das normas de segurança e veracidade dos dados informados. O usuário reconhece que a aprovação automática de checklists pelo sistema não exime sua obrigação de reportar imediatamente qualquer irregularidade identificada aos superiores competentes.

A Nexar não se responsabiliza por incompatibilidades, falhas de desempenho ou impossibilidade de utilização do aplicativo decorrentes de dispositivos móveis que não atendam aos requisitos mínimos de sistema operacional, capacidade de processamento, memória ou conectividade de rede. É de responsabilidade exclusiva do usuário e/ou da empresa contratante garantir que os dispositivos utilizados sejam compatíveis e estejam em condições adequadas de funcionamento para operação do GoRota.
""".strip()


def _ip_request():
    forwarded = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.remote_addr or "").strip()

# =========================
# API COLABORADORES (AGORA COM FOTOS)
# =========================
@app.get("/api/colaboradores/registros")
def api_colaboradores_registros():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    def normalizar_checklist(valor):
        if not valor:
            return []

        try:
            if isinstance(valor, str):
                valor = json.loads(valor)

            if isinstance(valor, dict):
                return valor.get("itens_marcados", [])

            if isinstance(valor, list):
                return valor

        except:
            pass

        return []

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                e.id,
                m.nome,
                v.modelo,
                v.placa,
                e.horario_inicio,
                e.horario_fim,
                e.status,
                e.checklist_entrada,
                e.checklist_saida,
                e.foto_entrada_url,
                e.foto_saida_url,
                e.ajustado
            FROM expedientes e
            LEFT JOIN motoristas m ON m.id = e.colaborador_id
            LEFT JOIN veiculos v ON v.id = e.veiculo_id
            WHERE e.usuario_id = %s
            ORDER BY e.id DESC
        """, (uid,))

        rows = cur.fetchall()

        data = []

        for r in rows:
            checklist_inicio = normalizar_checklist(r[7])
            checklist_fim = normalizar_checklist(r[8])

            data.append({
                "id": r[0],
                "colaborador": r[1],
                "veiculo": r[2],
                "placa": r[3],

                "data": r[4].date().isoformat() if r[4] else "",

                "horaEntrada": r[4].strftime("%H:%M") if r[4] else "",
                "horaSaida": r[5].strftime("%H:%M") if r[5] else "",

                "status": r[6],

                # 🔥 CHECKLIST AGORA FUNCIONA
                "checklistEntrada": checklist_inicio,
                "checklistSaida": checklist_fim,

                # 🔥 FOTOS
                "fotoEntrada": r[9],
                "fotoSaida": r[10],

                # 🔥 AJUSTE
                "ajustado": bool(r[11])
            })

        return jsonify(data), 200

    except Exception as e:
        print("ERRO api_colaboradores_registros:", e, flush=True)
        return jsonify({"erro": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
# =========================
# API COLABORADORES - PENDÊNCIAS
# =========================
@app.get("/api/colaboradores/pendencias")
def api_colaboradores_pendencias():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = None
    cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*)
            FROM veiculos_uso
            WHERE usuario_id = %s
            AND ativo = TRUE
        """, (uid,))

        total = cur.fetchone()[0]

        return jsonify({"pendencias": total}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# API COLABORADORES - AJUSTE (CORRETO)
# =========================
# =========================
# API COLABORADORES - AJUSTE (CORRETO E VALIDANDO JSON)
# =========================
@app.post("/api/colaboradores/ajuste")
def api_ajustar_ponto():
    r = proteger_api()
    if r:
        return r

    dados = request.get_json(silent=True) or {}

    expediente_id = dados.get("id")
    entrada = dados.get("entrada")
    saida = dados.get("saida")
    checklist = dados.get("checklist")
    motivo = dados.get("motivo")

    if not expediente_id:
        return jsonify({
            "sucesso": False,
            "erro": "id é obrigatório"
        }), 400

    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        campos = []
        valores = []

        if entrada:
            campos.append("horario_inicio = %s")
            valores.append(entrada)

        if saida:
            campos.append("horario_fim = %s")
            valores.append(saida)

        if checklist is not None:
            checklist_json = _parse_checklist_json(checklist)
            campos.append("checklist_entrada = %s")
            valores.append(json.dumps(checklist_json))

        if motivo:
            campos.append("motivo_ajuste = %s")
            valores.append(motivo)

        campos.append("ajustado = TRUE")

        if saida:
            campos.append("status = 'finalizado'")

        query = f"""
            UPDATE expedientes
            SET {", ".join(campos)}
            WHERE id = %s
        """

        valores.append(expediente_id)

        cur.execute(query, valores)

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except ValueError as e:
        if conn:
            conn.rollback()
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 400

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO ajuste:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =========================
# API UPLOAD FOTO (S3)
# =========================
@app.post("/api/upload/foto")
def api_upload_foto():
    r = proteger_api_mobile()
    if r:
        return r

    file = request.files.get("foto")

    if not file:
        return jsonify({"sucesso": False, "erro": "Foto não enviada"}), 400

    nome = f"expedientes/{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.jpg"

    try:
        s3.upload_fileobj(
            file,
            R2_BUCKET_NAME,
            nome,
            ExtraArgs={"ContentType": file.content_type or "image/jpeg"}
        )

        url = montar_url_publica_r2(nome)

        return jsonify({
            "sucesso": True,
            "url": url
        }), 200

    except Exception as e:
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500
    
@app.post("/api/mobile/terms/accept")
def api_mobile_terms_accept():
    r = proteger_api_mobile()
    if r:
        return r

    dados = request.get_json(silent=True) or {}

    motorista_id = int(g.mobile_auth["motorista_id"])
    usuario_id = int(g.mobile_auth["usuario_id"])

    termos_versao = (dados.get("terms_version") or TERMOS_MOBILE_VERSAO_ATUAL).strip()
    texto_termos = (dados.get("terms_text") or TERMOS_MOBILE_TEXTO).strip()
    dispositivo = (dados.get("dispositivo") or "").strip()
    ip_aceite = _ip_request()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO motorista_termos_aceites (
                motorista_id,
                usuario_id,
                termos_versao,
                texto_termos,
                ip_aceite,
                dispositivo
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (motorista_id) DO NOTHING
            RETURNING id, aceito_em
        """, (
            motorista_id,
            usuario_id,
            termos_versao,
            texto_termos,
            ip_aceite if ip_aceite else None,
            dispositivo if dispositivo else None
        ))

        inserted = cur.fetchone()

        if inserted:
            aceite_id, aceito_em = inserted
            conn.commit()

            return jsonify({
                "sucesso": True,
                "accepted": True,
                "already_accepted": False,
                "id": int(aceite_id),
                "terms_version": termos_versao,
                "accepted_at": aceito_em.isoformat() if aceito_em else None
            }), 201

        cur.execute("""
            SELECT
                id,
                termos_versao,
                aceito_em,
                COALESCE(texto_termos, '')
            FROM motorista_termos_aceites
            WHERE motorista_id = %s
            LIMIT 1
        """, (motorista_id,))

        existente = cur.fetchone()
        conn.commit()

        return jsonify({
            "sucesso": True,
            "accepted": True,
            "already_accepted": True,
            "id": int(existente[0]) if existente else None,
            "terms_version": existente[1] if existente and existente[1] else TERMOS_MOBILE_VERSAO_ATUAL,
            "accepted_at": existente[2].isoformat() if existente and existente[2] else None,
            "terms_text": existente[3] if existente and existente[3] else TERMOS_MOBILE_TEXTO
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_mobile_terms_accept:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao registrar aceite dos termos"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# API WEB - TERMOS DOS COLABORADORES
# =========================
@app.get("/api/termos/colaboradores")
def api_termos_colaboradores():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                m.id,
                m.nome,
                COALESCE(m.email, ''),
                t.id,
                t.termos_versao,
                t.texto_termos,
                t.aceito_em,
                COALESCE(t.ip_aceite, ''),
                COALESCE(t.dispositivo, '')
            FROM motoristas m
            LEFT JOIN motorista_termos_aceites t
                ON t.motorista_id = m.id
            WHERE m.usuario_id = %s
            ORDER BY m.id DESC
        """, (uid,))

        rows = cur.fetchall()

        colaboradores = []
        aceitaram = 0
        nao_aceitaram = 0

        for row in rows:
            motorista_id, nome, email, aceite_id, termos_versao, texto_termos, aceito_em, ip_aceite, dispositivo = row
            aceitou = aceite_id is not None

            if aceitou:
                aceitaram += 1
            else:
                nao_aceitaram += 1

            colaboradores.append({
                "id": int(motorista_id),
                "nome": nome,
                "email": email,
                "termo_aceito": aceitou,
                "status": "aceito" if aceitou else "pendente",
                "termos_versao": termos_versao if termos_versao else TERMOS_MOBILE_VERSAO_ATUAL,
                "texto_termos": texto_termos if texto_termos else "",
                "aceito_em": aceito_em.isoformat() if aceito_em else None,
                "ip_aceite": ip_aceite or "",
                "dispositivo": dispositivo or ""
            })

        return jsonify({
            "sucesso": True,
            "resumo": {
                "total_cadastrados": len(colaboradores),
                "aceitaram": aceitaram,
                "nao_aceitaram": nao_aceitaram
            },
            "versao_atual_termos": TERMOS_MOBILE_VERSAO_ATUAL,
            "colaboradores": colaboradores
        }), 200

    except Exception as e:
        print("ERRO api_termos_colaboradores:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao listar termos dos colaboradores"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =========================
# API MOBILE - ME
# =========================
@app.get("/api/mobile/me")
def api_mobile_me():
    r = proteger_api_mobile()
    if r:
        return r

    return jsonify({
        "sucesso": True,
        "motorista": {
            "id": g.mobile_auth["motorista_id"],
            "usuario_id": g.mobile_auth["usuario_id"],
            "nome": g.mobile_auth["nome"],
            "email": g.mobile_auth["email"]
        }
    }), 200


# =========================
# API MOBILE - VEÍCULOS DISPONÍVEIS (COM STATUS)
# =========================
@app.get("/api/mobile/veiculos")
def api_mobile_veiculos():
    r = proteger_api_mobile()
    if r:
        return r

    usuario_id = int(g.mobile_auth["usuario_id"])

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                v.id,
                v.modelo,
                v.placa,
                COALESCE(v.renavam, ''),
                v.cidade,

                vu.motorista_id,
                m.nome

            FROM veiculos v

            LEFT JOIN veiculos_uso vu
                ON vu.veiculo_id = v.id
               AND vu.ativo = TRUE

            LEFT JOIN motoristas m
                ON m.id = vu.motorista_id

            WHERE v.usuario_id = %s
            ORDER BY v.id DESC
        """, (usuario_id,))

        rows = cur.fetchall()

        veiculos = []
        for row in rows:
            veiculo_id, modelo, placa, renavam, cidade, motorista_id, motorista_nome = row

            veiculos.append({
                "id": int(veiculo_id),
                "modelo": modelo,
                "placa": placa,
                "renavam": renavam or "",
                "cidade": cidade,

                # 🔥 NOVO
                "em_uso": motorista_id is not None,
                "motorista_nome": motorista_nome if motorista_nome else None
            })

        return jsonify({
            "sucesso": True,
            "veiculos": veiculos
        }), 200

    except Exception as e:
        print("ERRO api_mobile_veiculos:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao carregar veículos"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
# =========================
# API MOBILE - VALIDAR SESSAO
# =========================
@app.get("/api/mobile/session")
def api_mobile_session():
    r = proteger_api_mobile()
    if r:
        return r

    return jsonify({
        "sucesso": True,
        "autenticado": True,
        "motorista": {
            "id": g.mobile_auth["motorista_id"],
            "nome": g.mobile_auth["nome"],
            "email": g.mobile_auth["email"]
        }
    }), 200


# =========================
# API MOBILE - LOGOUT
# =========================
@app.post("/api/mobile/logout")
def api_mobile_logout():
    token = _mobile_bearer_token()
    if not token:
        return jsonify({
            "sucesso": False,
            "erro": "Token ausente"
        }), 401

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        token_hash = _hash_mobile_token(token)

        cur.execute("""
            UPDATE motorista_sessoes_mobile
            SET revogado_em = CURRENT_TIMESTAMP
            WHERE token_hash = %s
              AND revogado_em IS NULL
        """, (token_hash,))

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_mobile_logout:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro interno ao encerrar sessão"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# API MOBILE - LOGOUT DE TODAS AS SESSOES
# =========================
@app.post("/api/mobile/logout-all")
def api_mobile_logout_all():
    r = proteger_api_mobile()
    if r:
        return r

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE motorista_sessoes_mobile
            SET revogado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND revogado_em IS NULL
        """, (g.mobile_auth["motorista_id"],))

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_mobile_logout_all:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro interno ao encerrar todas as sessões"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            
# =========================
# API MOBILE - INICIAR EXPEDIENTE (COM FOTO)
# =========================
@app.post("/api/mobile/expediente/iniciar")
def api_mobile_iniciar_expediente_completo():
    r = proteger_api_mobile()
    if r:
        return r

    motorista_id = int(g.mobile_auth["motorista_id"])
    usuario_id = int(g.mobile_auth["usuario_id"])

    veiculo_id = request.form.get("veiculo_id")
    raw_checklist = request.form.get("checklist")
    foto = request.files.get("foto")
    foto_odometro = request.files.get("foto_odometro")

    if not veiculo_id or not foto:
        return jsonify({
            "sucesso": False,
            "erro": "veiculo_id e foto são obrigatórios"
        }), 400

    try:
        veiculo_id = int(veiculo_id)
    except (TypeError, ValueError):
        return jsonify({
            "sucesso": False,
            "erro": "veiculo_id inválido"
        }), 400

    try:
        checklist = _parse_checklist_json(raw_checklist)
    except ValueError as e:
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 400

    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE expedientes
            SET
                horario_fim = CURRENT_TIMESTAMP,
                status = 'finalizado'
            WHERE colaborador_id = %s
              AND status = 'em_andamento'
        """, (motorista_id,))

        cur.execute("""
            UPDATE expedientes
            SET
                horario_fim = CURRENT_TIMESTAMP,
                status = 'finalizado'
            WHERE veiculo_id = %s
              AND status = 'em_andamento'
        """, (veiculo_id,))

        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND ativo = TRUE
        """, (motorista_id,))

        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE veiculo_id = %s
              AND ativo = TRUE
        """, (veiculo_id,))

        cur.execute("""
            INSERT INTO veiculos_uso (
                motorista_id,
                veiculo_id,
                usuario_id,
                ativo
            )
            VALUES (%s, %s, %s, TRUE)
        """, (
            motorista_id,
            veiculo_id,
            usuario_id
        ))

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

        filename_entrada = f"entrada/{veiculo_id}_{motorista_id}_{timestamp}.jpg"
        s3.upload_fileobj(
            foto,
            R2_BUCKET_NAME,
            filename_entrada,
            ExtraArgs={"ContentType": foto.content_type or "image/jpeg"}
        )
        url_foto_entrada = montar_url_publica_r2(filename_entrada)

        url_foto_odometro = None
        if foto_odometro:
            filename_odometro = f"odometro/entrada_{veiculo_id}_{motorista_id}_{timestamp}.jpg"
            s3.upload_fileobj(
                foto_odometro,
                R2_BUCKET_NAME,
                filename_odometro,
                ExtraArgs={"ContentType": foto_odometro.content_type or "image/jpeg"}
            )
            url_foto_odometro = montar_url_publica_r2(filename_odometro)

        try:
            cur.execute("""
                INSERT INTO expedientes (
                    usuario_id,
                    colaborador_id,
                    veiculo_id,
                    foto_entrada_url,
                    foto_odometro_entrada_url,
                    checklist_entrada,
                    horario_inicio,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'em_andamento')
                RETURNING id
            """, (
                usuario_id,
                motorista_id,
                veiculo_id,
                url_foto_entrada,
                url_foto_odometro,
                json.dumps(checklist)
            ))
        except Exception:
            conn.rollback()
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO expedientes (
                    usuario_id,
                    colaborador_id,
                    veiculo_id,
                    foto_entrada_url,
                    checklist_entrada,
                    horario_inicio,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'em_andamento')
                RETURNING id
            """, (
                usuario_id,
                motorista_id,
                veiculo_id,
                url_foto_entrada,
                json.dumps(checklist)
            ))

        expediente_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({
            "sucesso": True,
            "expediente_id": int(expediente_id),
            "foto_url": url_foto_entrada,
            "foto_odometro_url": url_foto_odometro
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO iniciar expediente:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao iniciar expediente"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =========================
# API MOBILE - FINALIZAR EXPEDIENTE (COM FOTO)
# =========================
@app.post("/api/mobile/expediente/finalizar")
def api_mobile_finalizar_expediente():
    r = proteger_api_mobile()
    if r:
        return r

    motorista_id = int(g.mobile_auth["motorista_id"])

    expediente_id = request.form.get("expediente_id")
    raw_checklist = request.form.get("checklist")
    foto = request.files.get("foto")

    if not expediente_id or not foto:
        return jsonify({
            "sucesso": False,
            "erro": "expediente_id e foto são obrigatórios"
        }), 400

    try:
        checklist = _parse_checklist_json(raw_checklist)
    except ValueError as e:
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 400

    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"saida/{motorista_id}_{timestamp}.jpg"

        s3.upload_fileobj(
            foto,
            R2_BUCKET_NAME,
            filename,
            ExtraArgs={"ContentType": foto.content_type or "image/jpeg"}
        )

        url_foto = montar_url_publica_r2(filename)

        cur.execute("""
            UPDATE expedientes
            SET
                foto_saida_url = %s,
                checklist_saida = %s,
                horario_fim = CURRENT_TIMESTAMP,
                status = 'finalizado'
            WHERE id = %s
        """, (
            url_foto,
            json.dumps(checklist),
            expediente_id
        ))

        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND ativo = TRUE
        """, (motorista_id,))

        conn.commit()

        return jsonify({
            "sucesso": True,
            "foto_url": url_foto
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO finalizar expediente:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao finalizar expediente"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()            
            
            # =========================
# API MOBILE - EXPEDIENTE ATUAL
# =========================
@app.get("/api/mobile/expediente-atual")
def api_mobile_expediente_atual():
    r = proteger_api_mobile()
    if r:
        return r

    motorista_id = int(g.mobile_auth["motorista_id"])

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                e.id,
                e.veiculo_id,
                e.horario_inicio,
                v.modelo,
                v.placa,
                v.cidade
            FROM expedientes e
            INNER JOIN veiculos v
                ON v.id = e.veiculo_id
            WHERE e.colaborador_id = %s
              AND e.status = 'em_andamento'
            ORDER BY e.horario_inicio DESC, e.id DESC
            LIMIT 1
        """, (motorista_id,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": True,
                "expediente_ativo": False,
                "expediente": None
            }), 200

        expediente_id, veiculo_id, horario_inicio, modelo, placa, cidade = row

        return jsonify({
            "sucesso": True,
            "expediente_ativo": True,
            "expediente": {
                "id": int(expediente_id),
                "veiculo_id": int(veiculo_id),
                "modelo": modelo,
                "placa": placa,
                "cidade": cidade,
                "horario_inicio": horario_inicio.isoformat() if horario_inicio else None
            }
        }), 200

    except Exception as e:
        print("ERRO api_mobile_expediente_atual:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": "Erro ao consultar expediente atual"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
             
# =========================
# API POSTOS
# =========================
@app.route("/api/postos", methods=["GET", "POST"], strict_slashes=False)
def api_postos():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    if request.method == "GET":
        conn = cur = None
        try:
            conn = get_db()
            cur = conn.cursor()

            # ✅ ALINHADO COM init_db.py:
            # posto_combustiveis TEM usuario_id => join filtra por pc.usuario_id
            cur.execute("""
                SELECT
                    p.id, p.nome, p.endereco,
                    pc.tipo, pc.preco
                FROM postos p
                LEFT JOIN posto_combustiveis pc
                    ON pc.posto_id = p.id
                   AND pc.usuario_id = p.usuario_id
                WHERE p.usuario_id = %s
                ORDER BY p.id DESC, pc.tipo ASC
            """, (uid,))
            rows = cur.fetchall()

            postos = {}
            for pid, nome, endereco, tipo, preco in rows:
                if pid not in postos:
                    postos[pid] = {"id": pid, "nome": nome, "endereco": endereco, "combustiveis": []}
                if tipo is not None:
                    postos[pid]["combustiveis"].append({
                        "tipo": str(tipo),
                        "preco": float(preco) if preco is not None else 0.0
                    })

            return jsonify(list(postos.values())), 200

        except Exception as e:
            print("ERRO api_postos GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # POST (3 combustíveis fixos)
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    gasolina = dados.get("gasolina")
    etanol = dados.get("etanol")
    diesel = dados.get("diesel")

    if not nome or not endereco:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios: nome, endereco"}), 400

    try:
        gasolina = float(gasolina)
        etanol = float(etanol)
        diesel = float(diesel)
    except Exception:
        return jsonify({"sucesso": False, "erro": "Preços inválidos"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO postos (usuario_id, nome, endereco)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (uid, nome, endereco))
        posto_id = cur.fetchone()[0]

        # ✅ ALINHADO COM init_db.py:
        # posto_combustiveis TEM usuario_id => inserir com usuario_id
        cur.execute("""
            INSERT INTO posto_combustiveis (usuario_id, posto_id, tipo, preco)
            VALUES
                (%s, %s, %s, %s),
                (%s, %s, %s, %s),
                (%s, %s, %s, %s)
        """, (
            uid, posto_id, "gasolina", gasolina,
            uid, posto_id, "etanol", etanol,
            uid, posto_id, "diesel", diesel
        ))

        conn.commit()
        return jsonify({"sucesso": True, "id": posto_id}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_postos POST:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/postos/<int:posto_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False)
def api_posto_por_id(posto_id: int):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "GET":
            posto = _posto_completo_por_id(cur, uid, posto_id)
            if not posto:
                return jsonify({"sucesso": False, "erro": "Posto não encontrado"}), 404
            return jsonify(posto), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}
            nome = (dados.get("nome") or "").strip()
            endereco = (dados.get("endereco") or "").strip()
            gasolina = dados.get("gasolina")
            etanol = dados.get("etanol")
            diesel = dados.get("diesel")

            if not nome or not endereco:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios: nome, endereco"}), 400

            try:
                gasolina = float(gasolina)
                etanol = float(etanol)
                diesel = float(diesel)
            except Exception:
                return jsonify({"sucesso": False, "erro": "Preços inválidos"}), 400

            cur.execute("""
                UPDATE postos
                SET nome = %s, endereco = %s
                WHERE id = %s AND usuario_id = %s
            """, (nome, endereco, posto_id, uid))

            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Posto não encontrado"}), 404

            # ✅ ALINHADO COM init_db.py:
            # apaga combustíveis do posto daquele usuário
            cur.execute("""
                DELETE FROM posto_combustiveis
                WHERE usuario_id = %s AND posto_id = %s AND tipo IN ('gasolina','etanol','diesel')
            """, (uid, posto_id))

            cur.execute("""
                INSERT INTO posto_combustiveis (usuario_id, posto_id, tipo, preco)
                VALUES
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s)
            """, (
                uid, posto_id, "gasolina", gasolina,
                uid, posto_id, "etanol", etanol,
                uid, posto_id, "diesel", diesel
            ))

            conn.commit()
            return jsonify({"sucesso": True}), 200

        # DELETE
        cur.execute("DELETE FROM posto_combustiveis WHERE usuario_id = %s AND posto_id = %s", (uid, posto_id))
        cur.execute("DELETE FROM postos WHERE id = %s AND usuario_id = %s", (posto_id, uid))
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Posto não encontrado"}), 404

        conn.commit()
        return jsonify({"sucesso": True}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_posto_por_id:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# LOGOUT + NO CACHE
# =========================
@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith("/api/") or request.path in ("/", "/login", "/logout"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# =========================
# ✅ API - CATÁLOGO PARA ABASTECIMENTO (motoristas/veiculos/postos)
# =========================
@app.get("/api/catalogo")
def api_catalogo():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # motoristas
        cur.execute("""
            SELECT id, nome
            FROM motoristas
            WHERE usuario_id = %s
            ORDER BY id DESC
        """, (uid,))
        motoristas = [{"id": i, "nome": n} for (i, n) in cur.fetchall()]

        # veiculos
        cur.execute("""
            SELECT id, placa, modelo
            FROM veiculos
            WHERE usuario_id = %s
            ORDER BY id DESC
        """, (uid,))
        veiculos = [{"id": i, "placa": p, "modelo": m} for (i, p, m) in cur.fetchall()]

        # postos + combustiveis
        cur.execute("""
            SELECT
                p.id, p.nome, p.endereco,
                pc.tipo, pc.preco
            FROM postos p
            LEFT JOIN posto_combustiveis pc
                ON pc.posto_id = p.id
               AND pc.usuario_id = p.usuario_id
            WHERE p.usuario_id = %s
            ORDER BY p.id DESC, pc.tipo ASC
        """, (uid,))
        rows = cur.fetchall()

        postos_map = {}
        for pid, nome, endereco, tipo, preco in rows:
            if pid not in postos_map:
                postos_map[pid] = {"id": pid, "nome": nome, "endereco": endereco, "combustiveis": []}
            if tipo is not None:
                postos_map[pid]["combustiveis"].append({
                    "tipo": str(tipo),
                    "preco": float(preco) if preco is not None else 0.0
                })
        postos = list(postos_map.values())

        return jsonify({"motoristas": motoristas, "veiculos": veiculos, "postos": postos}), 200

    except Exception as e:
        print("ERRO api_catalogo:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# ✅ API - ABASTECIMENTOS
# =========================
@app.route("/api/abastecimentos", methods=["GET", "POST"], strict_slashes=False)
def api_abastecimentos():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    # GET
    if request.method == "GET":
        conn = cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    a.id, a.data, a.hora,
                    a.motorista_id, a.veiculo_id, a.posto_id,
                    a.combustivel_tipo,
                    a.litros, a.preco_total, a.preco_unitario,
                    a.odometro, a.pago,
                    COALESCE(a.obs, ''),
                    COALESCE(a.comprovante_url, '')
                FROM abastecimentos a
                WHERE a.usuario_id = %s
                ORDER BY a.data DESC, a.hora DESC, a.id DESC
            """, (uid,))
            rows = cur.fetchall()

            data_out = []
            for row in rows:
                (i, data_, hora_, motorista_id, veiculo_id, posto_id, combustivel,
                 litros, preco_total, preco_unitario, odometro, pago, obs, comprovante_url) = row

                data_out.append({
                    "id": i,
                    "tipo": "abastecimento",
                    "data": data_.isoformat() if data_ else "",
                    "hora": hora_.strftime("%H:%M") if hora_ else "",
                    "motoristaId": motorista_id,
                    "veiculoId": veiculo_id,
                    "postoId": posto_id,
                    "combustivel": combustivel,
                    "litros": float(litros) if litros is not None else 0.0,
                    "preco": float(preco_total) if preco_total is not None else 0.0,
                    "precoUnitario": float(preco_unitario) if preco_unitario is not None else 0.0,
                    "odometro": str(odometro) if odometro is not None else "",
                    "pago": bool(pago),
                    "obs": obs,
                    "comprovante": comprovante_url
                })

            return jsonify(data_out), 200

        except Exception as e:
            print("ERRO api_abastecimentos GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # POST
    dados = request.get_json(silent=True) or {}

    data_ = dados.get("data")
    hora = dados.get("hora")
    motorista_id = dados.get("motorista_id")
    veiculo_id = dados.get("veiculo_id")
    posto_id = dados.get("posto_id")
    combustivel = dados.get("combustivel")
    litros = dados.get("litros")
    preco_total = dados.get("preco_total")
    preco_unitario = dados.get("preco_unitario")
    odometro = dados.get("odometro")
    pago = bool(dados.get("pago", False))
    obs = dados.get("obs") or ""
    comprovante_url = dados.get("comprovante") or ""

    if not data_ or not hora or not motorista_id or not veiculo_id or not posto_id or not combustivel:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios faltando"}), 400

    try:
        litros = float(litros)
        preco_total = float(preco_total)
        preco_unitario = float(preco_unitario)
    except Exception:
        return jsonify({"sucesso": False, "erro": "Valores numéricos inválidos"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # valida pertencimento
        cur.execute("SELECT 1 FROM motoristas WHERE id=%s AND usuario_id=%s", (motorista_id, uid))
        if not cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Motorista inválido"}), 400

        cur.execute("SELECT 1 FROM veiculos WHERE id=%s AND usuario_id=%s", (veiculo_id, uid))
        if not cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Veículo inválido"}), 400

        cur.execute("SELECT 1 FROM postos WHERE id=%s AND usuario_id=%s", (posto_id, uid))
        if not cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Posto inválido"}), 400

        cur.execute("""
            INSERT INTO abastecimentos (
                usuario_id, data, hora,
                motorista_id, veiculo_id, posto_id,
                combustivel_tipo,
                litros, preco_total, preco_unitario,
                odometro, pago, obs, comprovante_url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            uid, data_, hora,
            motorista_id, veiculo_id, posto_id,
            combustivel,
            litros, preco_total, preco_unitario,
            _odometro_to_int(odometro),
            pago, obs, comprovante_url
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "id": new_id}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_abastecimentos POST:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# =========================
# ✅ API - MANUTENÇÕES
# =========================
@app.route("/api/manutencoes", methods=["GET", "POST"], strict_slashes=False)
def api_manutencoes():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    # GET
    if request.method == "GET":
        conn = cur = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    m.id, m.data, m.hora,
                    m.motorista_id, m.veiculo_id,
                    m.valor, COALESCE(m.prestador,''),
                    m.pago, COALESCE(m.obs,''),
                    COALESCE(m.comprovante_url,'')
                FROM manutencoes m
                WHERE m.usuario_id = %s
                ORDER BY m.data DESC, m.hora DESC, m.id DESC
            """, (uid,))
            rows = cur.fetchall()

            data_out = []
            for row in rows:
                (i, data_, hora_, motorista_id, veiculo_id, valor, prestador, pago, obs, comprovante_url) = row
                data_out.append({
                    "id": i,
                    "tipo": "manutencao",
                    "data": data_.isoformat() if data_ else "",
                    "hora": hora_.strftime("%H:%M") if hora_ else "",
                    "motoristaId": motorista_id,
                    "veiculoId": veiculo_id,
                    "valor": float(valor) if valor is not None else 0.0,
                    "prestador": prestador,
                    "pago": bool(pago),
                    "obs": obs,
                    "comprovante": comprovante_url
                })

            return jsonify(data_out), 200

        except Exception as e:
            print("ERRO api_manutencoes GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # POST
    dados = request.get_json(silent=True) or {}

    data_ = dados.get("data")
    hora = dados.get("hora")
    motorista_id = dados.get("motorista_id")
    veiculo_id = dados.get("veiculo_id")
    valor = dados.get("valor")
    prestador = (dados.get("prestador") or "").strip()
    pago = bool(dados.get("pago", False))
    obs = dados.get("obs") or ""
    comprovante_url = dados.get("comprovante") or ""

    if not data_ or not hora or not motorista_id or not veiculo_id or not prestador:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios faltando"}), 400

    try:
        valor = float(valor)
    except Exception:
        return jsonify({"sucesso": False, "erro": "Valor inválido"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM motoristas WHERE id=%s AND usuario_id=%s", (motorista_id, uid))
        if not cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Motorista inválido"}), 400

        cur.execute("SELECT 1 FROM veiculos WHERE id=%s AND usuario_id=%s", (veiculo_id, uid))
        if not cur.fetchone():
            return jsonify({"sucesso": False, "erro": "Veículo inválido"}), 400

        cur.execute("""
            INSERT INTO manutencoes (
                usuario_id, data, hora,
                motorista_id, veiculo_id,
                valor, prestador, pago, obs, comprovante_url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            uid, data_, hora,
            motorista_id, veiculo_id,
            valor, prestador, pago, obs, comprovante_url
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"sucesso": True, "id": new_id}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_manutencoes POST:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# ✅ API - ABASTECIMENTO POR ID (EDITAR / EXCLUIR)
# =========================
@app.route("/api/abastecimentos/<int:abastecimento_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False)
def api_abastecimento_por_id(abastecimento_id: int):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute("""
                SELECT
                    id, data, hora,
                    motorista_id, veiculo_id, posto_id,
                    combustivel_tipo,
                    litros, preco_total, preco_unitario,
                    odometro, pago,
                    COALESCE(obs,''), COALESCE(comprovante_url,'')
                FROM abastecimentos
                WHERE id = %s AND usuario_id = %s
            """, (abastecimento_id, uid))
            row = cur.fetchone()
            if not row:
                return jsonify({"sucesso": False, "erro": "Abastecimento não encontrado"}), 404

            (i, data_, hora_, motorista_id, veiculo_id, posto_id, combustivel,
             litros, preco_total, preco_unitario, odometro, pago, obs, comprovante_url) = row

            return jsonify({
                "id": i,
                "tipo": "abastecimento",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "postoId": posto_id,
                "combustivel": combustivel,
                "litros": float(litros) if litros is not None else 0.0,
                "preco": float(preco_total) if preco_total is not None else 0.0,
                "precoUnitario": float(preco_unitario) if preco_unitario is not None else 0.0,
                "odometro": str(odometro) if odometro is not None else "",
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            }), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}

            data_ = dados.get("data")
            hora = dados.get("hora")
            motorista_id = dados.get("motorista_id")
            veiculo_id = dados.get("veiculo_id")
            posto_id = dados.get("posto_id")
            combustivel = dados.get("combustivel")
            litros = dados.get("litros")
            preco_total = dados.get("preco_total")
            preco_unitario = dados.get("preco_unitario")
            odometro = dados.get("odometro")
            pago = bool(dados.get("pago", False))
            obs = dados.get("obs") or ""
            comprovante_url = dados.get("comprovante") or ""

            if not data_ or not hora or not motorista_id or not veiculo_id or not posto_id or not combustivel:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios faltando"}), 400

            try:
                litros = float(litros)
                preco_total = float(preco_total)
                preco_unitario = float(preco_unitario)
            except Exception:
                return jsonify({"sucesso": False, "erro": "Valores numéricos inválidos"}), 400

            cur.execute("SELECT 1 FROM motoristas WHERE id=%s AND usuario_id=%s", (motorista_id, uid))
            if not cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Motorista inválido"}), 400

            cur.execute("SELECT 1 FROM veiculos WHERE id=%s AND usuario_id=%s", (veiculo_id, uid))
            if not cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Veículo inválido"}), 400

            cur.execute("SELECT 1 FROM postos WHERE id=%s AND usuario_id=%s", (posto_id, uid))
            if not cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Posto inválido"}), 400

            cur.execute("""
                UPDATE abastecimentos
                SET
                    data = %s,
                    hora = %s,
                    motorista_id = %s,
                    veiculo_id = %s,
                    posto_id = %s,
                    combustivel_tipo = %s,
                    litros = %s,
                    preco_total = %s,
                    preco_unitario = %s,
                    odometro = %s,
                    pago = %s,
                    obs = %s,
                    comprovante_url = %s
                WHERE id = %s AND usuario_id = %s
            """, (
                data_, hora,
                motorista_id, veiculo_id, posto_id,
                combustivel,
                litros, preco_total, preco_unitario,
                _odometro_to_int(odometro),
                pago, obs, comprovante_url,
                abastecimento_id, uid
            ))

            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Abastecimento não encontrado"}), 404

            conn.commit()
            return jsonify({"sucesso": True}), 200

        # DELETE
        cur.execute("DELETE FROM abastecimentos WHERE id = %s AND usuario_id = %s", (abastecimento_id, uid))
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Abastecimento não encontrado"}), 404

        conn.commit()
        return jsonify({"sucesso": True}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_abastecimento_por_id:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# ✅ API - MANUTENÇÃO POR ID (EDITAR / EXCLUIR)
# =========================
@app.route("/api/manutencoes/<int:manutencao_id>", methods=["GET", "PUT", "DELETE"], strict_slashes=False)
def api_manutencao_por_id(manutencao_id: int):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute("""
                SELECT
                    id, data, hora,
                    motorista_id, veiculo_id,
                    valor, COALESCE(prestador,''),
                    pago, COALESCE(obs,''), COALESCE(comprovante_url,'')
                FROM manutencoes
                WHERE id = %s AND usuario_id = %s
            """, (manutencao_id, uid))
            row = cur.fetchone()
            if not row:
                return jsonify({"sucesso": False, "erro": "Manutenção não encontrada"}), 404

            (i, data_, hora_, motorista_id, veiculo_id, valor, prestador, pago, obs, comprovante_url) = row

            return jsonify({
                "id": i,
                "tipo": "manutencao",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "valor": float(valor) if valor is not None else 0.0,
                "prestador": prestador,
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            }), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}

            data_ = dados.get("data")
            hora = dados.get("hora")
            motorista_id = dados.get("motorista_id")
            veiculo_id = dados.get("veiculo_id")
            valor = dados.get("valor")
            prestador = (dados.get("prestador") or "").strip()
            pago = bool(dados.get("pago", False))
            obs = dados.get("obs") or ""
            comprovante_url = dados.get("comprovante") or ""

            if not data_ or not hora or not motorista_id or not veiculo_id or not prestador:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios faltando"}), 400

            try:
                valor = float(valor)
            except Exception:
                return jsonify({"sucesso": False, "erro": "Valor inválido"}), 400

            cur.execute("SELECT 1 FROM motoristas WHERE id=%s AND usuario_id=%s", (motorista_id, uid))
            if not cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Motorista inválido"}), 400

            cur.execute("SELECT 1 FROM veiculos WHERE id=%s AND usuario_id=%s", (veiculo_id, uid))
            if not cur.fetchone():
                return jsonify({"sucesso": False, "erro": "Veículo inválido"}), 400

            cur.execute("""
                UPDATE manutencoes
                SET
                    data = %s,
                    hora = %s,
                    motorista_id = %s,
                    veiculo_id = %s,
                    valor = %s,
                    prestador = %s,
                    pago = %s,
                    obs = %s,
                    comprovante_url = %s
                WHERE id = %s AND usuario_id = %s
            """, (
                data_, hora,
                motorista_id, veiculo_id,
                valor, prestador,
                pago, obs, comprovante_url,
                manutencao_id, uid
            ))

            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Manutenção não encontrada"}), 404

            conn.commit()
            return jsonify({"sucesso": True}), 200

        # DELETE
        cur.execute("DELETE FROM manutencoes WHERE id = %s AND usuario_id = %s", (manutencao_id, uid))
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Manutenção não encontrada"}), 404

        conn.commit()
        return jsonify({"sucesso": True}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_manutencao_por_id:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



# =========================
# ✅ API - HISTÓRICO (ABAST + MANUT)
# =========================
@app.get("/api/historico")
def api_historico():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # abastecimentos
        cur.execute("""
            SELECT
                id, data, hora,
                motorista_id, veiculo_id, posto_id,
                combustivel_tipo,
                litros, preco_total, preco_unitario,
                odometro, pago, COALESCE(obs,''), COALESCE(comprovante_url,'')
            FROM abastecimentos
            WHERE usuario_id = %s
        """, (uid,))
        abastec_rows = cur.fetchall()

        abastecs = []
        for row in abastec_rows:
            (i, data_, hora_, motorista_id, veiculo_id, posto_id, combustivel,
             litros, preco_total, preco_unitario, odometro, pago, obs, comprovante_url) = row
            abastecs.append({
                "id": i,
                "tipo": "abastecimento",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "postoId": posto_id,
                "combustivel": combustivel,
                "litros": float(litros) if litros is not None else 0.0,
                "preco": float(preco_total) if preco_total is not None else 0.0,
                "precoUnitario": float(preco_unitario) if preco_unitario is not None else 0.0,
                "odometro": str(odometro) if odometro is not None else "",
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

        # manutencoes
        cur.execute("""
            SELECT
                id, data, hora,
                motorista_id, veiculo_id,
                valor, COALESCE(prestador,''),
                pago, COALESCE(obs,''), COALESCE(comprovante_url,'')
            FROM manutencoes
            WHERE usuario_id = %s
        """, (uid,))
        manut_rows = cur.fetchall()

        manuts = []
        for row in manut_rows:
            (i, data_, hora_, motorista_id, veiculo_id, valor, prestador, pago, obs, comprovante_url) = row
            manuts.append({
                "id": i,
                "tipo": "manutencao",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "valor": float(valor) if valor is not None else 0.0,
                "prestador": prestador,
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

        tudo = abastecs + manuts
        tudo.sort(key=lambda r: f"{r.get('data','')}T{r.get('hora','00:00')}", reverse=True)

        return jsonify(tudo), 200

    except Exception as e:
        print("ERRO api_historico:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# =========================
# DASHBOARD HELPERS
# =========================
def _month_bounds(d: date):
    start = date(d.year, d.month, 1)
    if d.month == 12:
        end = date(d.year + 1, 1, 1)
    else:
        end = date(d.year, d.month + 1, 1)
    return start, end


def _prev_month(d: date):
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _dt_key(data_str, hora_str):
    try:
        return datetime.fromisoformat(f"{data_str}T{hora_str or '00:00'}")
    except Exception:
        return datetime.min


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _filtrar_mes(registros, start: date, end: date):
    out = []
    for r in registros:
        ds = r.get("data") or ""
        try:
            d = date.fromisoformat(ds)
        except Exception:
            continue
        if start <= d < end:
            out.append(r)
    return out


def _format_money(v):
    return round(float(v or 0.0), 2)


def _pct_delta(atual, anterior):
    atual = float(atual or 0.0)
    anterior = float(anterior or 0.0)
    if anterior == 0:
        return 0.0
    return ((atual - anterior) / anterior) * 100.0


# =========================================================
# ✅✅✅ NOVA LÓGICA CORRETA 
# =========================================================
def _compute_trechos_por_veiculo(abastecs):
    """
    Trechos corretos por veículo:

    - Agrupa abastecimentos por veículo
    - Ordena por data/hora (sequência real)
    - O primeiro abastecimento NÃO entra no cálculo
    - Para cada abastecimento atual:
        km = odometro_atual - odometro_anterior
        litros do trecho = litros do abastecimento ATUAL
        custo do trecho  = preco_total do abastecimento ATUAL

    Correção segura do bug x100:
    Se km > 5000 e múltiplo de 100, assume bug e divide por 100.
    """
    por_veic = {}
    for a in abastecs:
        por_veic.setdefault(a["veiculoId"], []).append(a)

    trechos = []

    for veic_id, lista in por_veic.items():
        lista_sorted = sorted(lista, key=lambda r: _dt_key(r.get("data", ""), r.get("hora", "")))

        odometro_anterior = None

        for a in lista_sorted:
            odometro_atual = _odometro_to_int(a.get("odometro"))

            if odometro_anterior is not None and odometro_atual is not None:
                km = odometro_atual - odometro_anterior

                # ✅ correção x100 (segura)
                if km > 5000 and (km % 100 == 0):
                    km = km // 100

                if km > 0:
                    trechos.append({
                        "veiculoId": veic_id,
                        "motoristaId": a.get("motoristaId"),
                        "km": int(km),
                        "litros": _safe_float(a.get("litros"), 0.0),
                        "custo": _safe_float(a.get("preco"), 0.0),
                        "data": a.get("data", ""),
                    })

            if odometro_atual is not None:
                odometro_anterior = odometro_atual

    return trechos


@app.get("/api/dashboard")
def api_dashboard():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # -----------------------------
        # ABASTECIMENTOS
        # -----------------------------
        cur.execute("""
            SELECT
                a.id, a.data, a.hora,
                a.motorista_id, a.veiculo_id, a.posto_id,
                a.combustivel_tipo,
                a.litros, a.preco_total, a.preco_unitario,
                a.odometro, a.pago,
                COALESCE(a.obs, ''),
                COALESCE(a.comprovante_url, '')
            FROM abastecimentos a
            WHERE a.usuario_id = %s
        """, (uid,))
        abastec_rows = cur.fetchall()

        abastecs = []
        for row in abastec_rows:
            (i, data_, hora_, motorista_id, veiculo_id, posto_id, combustivel,
             litros, preco_total, preco_unitario, odometro, pago, obs, comprovante_url) = row

            odo_int = int(str(odometro).lstrip("0") or "0")

            abastecs.append({
                "id": i,
                "tipo": "abastecimento",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "postoId": posto_id,
                "combustivel": combustivel,
                "litros": float(litros or 0),
                "preco": float(preco_total or 0),
                "precoUnitario": float(preco_unitario or 0),
                "odometro": odo_int,
                "odometro_str": f"{odo_int:06d}",
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

        # -----------------------------
        # MANUTENÇÕES
        # -----------------------------
        cur.execute("""
            SELECT
                m.id, m.data, m.hora,
                m.motorista_id, m.veiculo_id,
                m.valor, COALESCE(m.prestador,''),
                m.pago, COALESCE(m.obs,''), COALESCE(m.comprovante_url,'')
            FROM manutencoes m
            WHERE m.usuario_id = %s
        """, (uid,))
        manut_rows = cur.fetchall()

        manuts = []
        for row in manut_rows:
            (i, data_, hora_, motorista_id, veiculo_id, valor, prestador, pago, obs, comprovante_url) = row
            manuts.append({
                "id": i,
                "tipo": "manutencao",
                "data": data_.isoformat() if data_ else "",
                "hora": hora_.strftime("%H:%M") if hora_ else "",
                "motoristaId": motorista_id,
                "veiculoId": veiculo_id,
                "valor": float(valor or 0),
                "prestador": prestador,
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

        hoje = date.today()
        ini, fim = _month_bounds(hoje)
        ini_prev, fim_prev = _month_bounds(_prev_month(hoje))

        abastec_mes = _filtrar_mes(abastecs, ini, fim)
        abastec_prev = _filtrar_mes(abastecs, ini_prev, fim_prev)

        manuts_mes = _filtrar_mes(manuts, ini, fim)
        manuts_prev = _filtrar_mes(manuts, ini_prev, fim_prev)

        # -----------------------------
        # TRECHOS CORRETOS
        # -----------------------------
        trechos_mes = _compute_trechos_por_veiculo(abastec_mes)
        trechos_prev = _compute_trechos_por_veiculo(abastec_prev)

        km_mes = sum(t["km"] for t in trechos_mes)
        km_prev = sum(t["km"] for t in trechos_prev)

        litros_mes_valid = sum(t["litros"] for t in trechos_mes)
        litros_prev_valid = sum(t["litros"] for t in trechos_prev)

        custo_mes_valid = sum(t["custo"] for t in trechos_mes)
        custo_prev_valid = sum(t["custo"] for t in trechos_prev)

        consumo_l_km = (litros_mes_valid / km_mes) if km_mes > 0 else 0.0
        consumo_prev = (litros_prev_valid / km_prev) if km_prev > 0 else 0.0

        custo_r_km = (custo_mes_valid / km_mes) if km_mes > 0 else 0.0
        custo_prev = (custo_prev_valid / km_prev) if km_prev > 0 else 0.0

        total_abastec_mes = sum(a["preco"] for a in abastec_mes)
        total_manut_mes = sum(m["valor"] for m in manuts_mes)

        total_mes = total_abastec_mes + total_manut_mes

        nao_pago_mes = (
            sum(a["preco"] for a in abastec_mes if not a["pago"]) +
            sum(m["valor"] for m in manuts_mes if not m["pago"])
        )

        ja_pago_mes = (
            sum(a["preco"] for a in abastec_mes if a["pago"]) +
            sum(m["valor"] for m in manuts_mes if m["pago"])
        )

        payload = {
            "periodo": {"mes_inicio": ini.isoformat(), "mes_fim": fim.isoformat()},
            "cards": {
                "consumo_medio_l_km": consumo_l_km,
                "consumo_delta_pct": _pct_delta(consumo_l_km, consumo_prev),
                "custo_medio_r_km": custo_r_km,
                "custo_delta_pct": _pct_delta(custo_r_km, custo_prev),
                "total_mensal": _format_money(total_mes),
                "nao_pago": _format_money(nao_pago_mes),
                "ja_pago": _format_money(ja_pago_mes),
                "km_mes": int(km_mes),
                "litros_mes": _format_money(sum(a["litros"] for a in abastec_mes)),
                "qtd_abastec_mes": len(abastec_mes),
                "qtd_manut_mes": len(manuts_mes),
            },
            "top3_abastecimentos": [],
            "top3_piores_custo_km": [],
            "resumo_veiculos": [],
            "resumo_motoristas": [],
        }

        return jsonify(payload), 200

    except Exception as e:
        print("ERRO api_dashboard:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# START
# =========================
if __name__ == "__main__":
    print(">>> APP.PY ATIVO:", __file__, flush=True)
    print("TEMPLATES_DIR:", TEMPLATES_DIR, flush=True)
    print("STATIC_DIR:", STATIC_DIR, flush=True)
    print(app.url_map, flush=True)
    app.run(host="127.0.0.1", port=7778, debug=True, use_reloader=False)