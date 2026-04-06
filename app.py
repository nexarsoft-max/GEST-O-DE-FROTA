import os
import re
import hashlib
import secrets 
import json
from datetime import timedelta, date, datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from psycopg2 import errors
from io import BytesIO
from urllib.request import Request, urlopen

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from conexao import get_db

print(">>> APP.PY CARREGADO:", __file__, flush=True)

import boto3
from botocore.config import Config

# =========================
# R2 CONFIG (FORÇADO P/ TESTE)
# =========================
R2_ACCESS_KEY_ID = "066d4a5c98cff2006d82521b6a5d97ac"
R2_SECRET_ACCESS_KEY = "ebd7c1c570887cf5fa7bf23b471ab8416947a261fd030e0332cd9f84bc16ad76"
R2_ENDPOINT = "https://99db8fa8481df243709f145dff6147e1.r2.cloudflarestorage.com"
R2_BUCKET_NAME = "gorota-vehicle-photos"
R2_PUBLIC_BASE_URL = "https://pub-561cfae6f6e84157963a7bee03def00e.r2.dev"

print("R2_ACCESS_KEY_ID:", repr(R2_ACCESS_KEY_ID), flush=True)
print("R2_SECRET_ACCESS_KEY:", repr(R2_SECRET_ACCESS_KEY[:8] + "..."), flush=True)
print("R2_ENDPOINT:", repr(R2_ENDPOINT), flush=True)
print("R2_BUCKET_NAME:", repr(R2_BUCKET_NAME), flush=True)
print("R2_PUBLIC_BASE_URL:", repr(R2_PUBLIC_BASE_URL), flush=True)

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
    config=Config(signature_version="s3v4")
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

def _safe_json_loads(valor, default=None):
    if default is None:
        default = {}
    if valor is None:
        return default
    if isinstance(valor, (dict, list)):
        return valor
    texto = str(valor).strip()
    if not texto:
        return default
    try:
        return json.loads(texto)
    except Exception:
        return default


def _lista_fotos_dano_saida(row_or_dict):
    """
    Normaliza as 3 colunas novas de foto do dano em uma lista.
    Aceita tuple/list (row do banco) ou dict.
    """
    if isinstance(row_or_dict, dict):
        candidatos = [
            row_or_dict.get("foto_dano_saida_url_1"),
            row_or_dict.get("foto_dano_saida_url_2"),
            row_or_dict.get("foto_dano_saida_url_3"),
        ]
    else:
        candidatos = list(row_or_dict)

    return [str(url).strip() for url in candidatos if url and str(url).strip()]


def _normalizar_checklist_colaboradores(valor):
    """
    Mantém compatibilidade com checklist antigo.
    """
    if not valor:
        return []

    try:
        if isinstance(valor, str):
            valor = json.loads(valor)

        if isinstance(valor, dict):
            return valor.get("itens_marcados", []) or valor.get("itens", []) or []

        if isinstance(valor, list):
            return valor
    except Exception:
        pass

    return []


def _normalizar_checklist_detalhe_colaboradores(valor):
    """
    Mantém o formato que o seu front já espera no modal.
    """
    if not valor:
        return {
            "itens": [],
            "itens_marcados": [],
            "veiculo_perfeito": None,
            "observacao": "",
            "quantidade_cones": "",
            "trabalhando_em_dupla_ou_mais": None,
            "nomes_dupla_ou_mais": "",
            "confirmacao_veracidade": False
        }

    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except Exception:
            valor = [valor]

    if isinstance(valor, list):
        itens = [str(item) for item in valor]
        return {
            "itens": itens,
            "itens_marcados": itens,
            "veiculo_perfeito": None,
            "observacao": "",
            "quantidade_cones": "",
            "trabalhando_em_dupla_ou_mais": None,
            "nomes_dupla_ou_mais": "",
            "confirmacao_veracidade": False
        }

    if isinstance(valor, dict):
        itens = valor.get("itens", []) if isinstance(valor.get("itens"), list) else []
        itens_marcados = valor.get("itens_marcados", []) if isinstance(valor.get("itens_marcados"), list) else itens

        return {
            "itens": [str(item) for item in itens],
            "itens_marcados": [str(item) for item in itens_marcados],
            "veiculo_perfeito": valor.get("veiculo_perfeito"),
            "observacao": str(valor.get("observacao") or "").strip(),
            "quantidade_cones": str(valor.get("quantidade_cones") or "").strip(),
            "trabalhando_em_dupla_ou_mais": valor.get("trabalhando_em_dupla_ou_mais"),
            "nomes_dupla_ou_mais": str(valor.get("nomes_dupla_ou_mais") or "").strip(),
            "confirmacao_veracidade": bool(valor.get("confirmacao_veracidade"))
        }

    return {
        "itens": [],
        "itens_marcados": [],
        "veiculo_perfeito": None,
        "observacao": "",
        "quantidade_cones": "",
        "trabalhando_em_dupla_ou_mais": None,
        "nomes_dupla_ou_mais": "",
        "confirmacao_veracidade": False
    }


def _upload_foto_dano_saida(expediente_id: int, indice: int, arquivo_storage) -> str:
    """
    Sobe foto de dano da saída para o storage externo e devolve URL pública.
    indice: 1, 2 ou 3
    """
    if not arquivo_storage:
        return ""

    nome_original = (arquivo_storage.filename or "").strip()
    extensao = os.path.splitext(nome_original)[1].lower() or ".jpg"
    if extensao not in [".jpg", ".jpeg", ".png", ".webp"]:
        extensao = ".jpg"

    chave = f"expedientes/{expediente_id}/dano_saida_{indice}_{secrets.token_hex(8)}{extensao}"

    content_type = arquivo_storage.mimetype or "image/jpeg"

    s3.upload_fileobj(
        arquivo_storage,
        R2_BUCKET_NAME,
        chave,
        ExtraArgs={"ContentType": content_type}
    )

    return montar_url_publica_r2(chave)

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

import math

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000  # raio da terra em metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c  # metros

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
    return render_template("mapageral.html")


@app.route("/mapageral")
def mapageral():
    r = proteger_pagina()
    if r:
        return r
    return render_template("mapageral.html")

@app.get("/colaboradores")
def colaboradores():
    r = proteger_pagina()
    if r:
        return r
    return render_template("colaboradores.html")



@app.get("/alertas")
def alertas():
    r = proteger_pagina()
    if r:
        return r
    return render_template("alertas.html")

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
            WHERE v.id = %s
              AND v.usuario_id = %s
            LIMIT 1
        """, (veiculo_id, uid))

        row = cur.fetchone()
        if not row:
            return redirect(url_for("monitoramento"))

        veiculo_id_db, modelo, placa, cidade, motorista_id, motorista_nome = row

        cur.execute("""
            SELECT
                latitude,
                longitude,
                velocidade_kmh,
                endereco,
                recebido_em
            FROM veiculos_localizacao
            WHERE veiculo_id = %s
              AND usuario_id = %s
              AND recebido_em >= (CURRENT_TIMESTAMP - INTERVAL '24 hours')
            ORDER BY recebido_em ASC
        """, (veiculo_id_db, uid))

        pontos = [_normalizar_ponto_localizacao(r) for r in cur.fetchall()]
        resumo = _resumir_pontos_localizacao(pontos)
        ultimo_ponto = pontos[-1] if pontos else None
        recebido_em = resumo["ultimo_recebido_em"]

        veiculo = {
            "id": int(veiculo_id_db),
            "nome": modelo,
            "modelo": modelo,
            "placa": placa,
            "cidade": cidade,
            "status": resumo["status"],
            "motoristaNome": motorista_nome if motorista_nome else "Aguardando vínculo do app",
            "velocidade_kmh": resumo["velocidade_atual_kmh"],
            "velocidade_media_kmh": resumo["velocidade_media_kmh"],
            "combustivel_pct": None,
            "ultima_atualizacao": recebido_em.isoformat() if recebido_em else "Sem atualização",
            "ultima_atualizacao_label": _formatar_data_label(recebido_em),
            "endereco": (ultimo_ponto["endereco"] if ultimo_ponto and ultimo_ponto["endereco"] else "Localização indisponível no momento"),
            "lat": ultimo_ponto["lat"] if ultimo_ponto else None,
            "lng": ultimo_ponto["lng"] if ultimo_ponto else None,
            "latitude": ultimo_ponto["lat"] if ultimo_ponto else None,
            "longitude": ultimo_ponto["lng"] if ultimo_ponto else None,
            "telefone_motorista": "",
            "distancia_total_km_24h": resumo["distancia_total_km"],
            "tempo_total_segundos_24h": resumo["tempo_total_segundos"],
            "pontos_validos_24h": resumo["pontos_validos"],
        }

        return render_template(
            "localizacao.html",
            veiculo_json=json.dumps(veiculo),
            veiculo_id=veiculo_id_db
        )

    except Exception as e:
        print("ERRO localizacao_veiculo:", e, flush=True)
        return redirect(url_for("monitoramento"))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.post("/api/alertas/resolver")
def api_alertas_resolver():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    dados = request.get_json(silent=True) or {}

    alerta_id = str(dados.get("alerta_id") or "").strip()
    alerta_tipo = str(dados.get("tipo") or "").strip()
    expediente_id = dados.get("expediente_id")

    if not alerta_id:
        return jsonify({
            "sucesso": False,
            "erro": "alerta_id é obrigatório"
        }), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO alertas_resolvidos (
                usuario_id,
                alerta_id,
                alerta_tipo,
                expediente_id,
                resolvido_em
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (usuario_id, alerta_id)
            DO UPDATE SET
                alerta_tipo = EXCLUDED.alerta_tipo,
                expediente_id = EXCLUDED.expediente_id,
                resolvido_em = CURRENT_TIMESTAMP
        """, (
            uid,
            alerta_id,
            alerta_tipo if alerta_tipo else None,
            int(expediente_id) if expediente_id else None
        ))

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_alertas_resolver:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.delete("/api/alertas/resolver/<path:alerta_id>")
def api_alertas_desresolver(alerta_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    alerta_id = str(alerta_id or "").strip()

    if not alerta_id:
        return jsonify({
            "sucesso": False,
            "erro": "alerta_id inválido"
        }), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM alertas_resolvidos
            WHERE usuario_id = %s
              AND alerta_id = %s
        """, (uid, alerta_id))

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_alertas_desresolver:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

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

            # pega histórico recente suficiente para calcular velocidade real e status
            cur.execute("""
                SELECT
                    latitude,
                    longitude,
                    velocidade_kmh,
                    endereco,
                    recebido_em
                FROM veiculos_localizacao
                WHERE veiculo_id = %s
                  AND usuario_id = %s
                  AND recebido_em >= (CURRENT_TIMESTAMP - INTERVAL '24 hours')
                ORDER BY recebido_em ASC
            """, (veiculo_id, uid))

            pontos_rows = cur.fetchall()

            pontos = []
            for p in pontos_rows:
                pontos.append({
                    "lat": float(p[0]) if p[0] is not None else None,
                    "lng": float(p[1]) if p[1] is not None else None,
                    "velocidade_bruta_kmh": float(p[2]) if p[2] is not None else None,
                    "endereco": p[3],
                    "recebido_em": _garantir_dt_utc(p[4]) if p[4] else None,
                })

            resumo = _resumir_pontos_localizacao(pontos)

            ultimo_ponto = pontos[-1] if pontos else None
            recebido_em = resumo["ultimo_recebido_em"]

            data_out.append({
                "id": int(veiculo_id),
                "nome": modelo,
                "modelo": modelo,
                "placa": placa,
                "cidade": cidade,
                "status": resumo["status"],
                "motoristaNome": motorista_nome if motorista_nome else None,

                # AGORA É REAL: vem do último trecho válido, não de valor fixo
                "velocidade_kmh": resumo["velocidade_atual_kmh"],
                "velocidade_media_kmh": resumo["velocidade_media_kmh"],

                "combustivel_pct": None,
                "ultima_atualizacao": recebido_em.isoformat() if recebido_em else None,
                "ultima_atualizacao_label": _formatar_data_label(recebido_em) if recebido_em else None,

                "lat": ultimo_ponto["lat"] if ultimo_ponto else None,
                "lng": ultimo_ponto["lng"] if ultimo_ponto else None,
                "latitude": ultimo_ponto["lat"] if ultimo_ponto else None,
                "longitude": ultimo_ponto["lng"] if ultimo_ponto else None,

                "endereco": ultimo_ponto["endereco"] if ultimo_ponto else None,
                "telefone_motorista": None,

                # extras úteis para evolução futura
                "distancia_total_km_24h": resumo["distancia_total_km"],
                "tempo_total_segundos_24h": resumo["tempo_total_segundos"],
                "pontos_validos_24h": resumo["pontos_validos"]
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

    def ajustar_fuso(dt):
        if not dt:
            return None

        try:
            tz_br = ZoneInfo("America/Sao_Paulo")
            tz_utc = ZoneInfo("UTC")

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz_utc)

            return dt.astimezone(tz_br)
        except Exception:
            return dt

    def formatar_hora(dt):
        dt = ajustar_fuso(dt)
        return dt.strftime("%H:%M") if dt else ""

    def _checklist_vazio():
        return {
            "itens": [],
            "veiculo_perfeito": None,
            "observacao": "",
            "quantidade_cones": "",
            "trabalhando_em_dupla_ou_mais": None,
            "nomes_dupla_ou_mais": "",
            "confirmacao_veracidade": False
        }

    def _normalizar_checklist(valor):
        try:
            if valor is None:
                return _checklist_vazio()

            if isinstance(valor, str):
                texto = valor.strip()
                if not texto:
                    return _checklist_vazio()

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
                    "itens": [str(item).strip() for item in valor if str(item).strip()],
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
                        and str(chave).strip() not in (
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

        except Exception as erro_normalizacao:
            print("ERRO _normalizar_checklist:", erro_normalizacao, flush=True)
            return _checklist_vazio()

    def _lista_fotos_dano_saida(f1, f2, f3):
        return [
            str(url).strip()
            for url in [f1, f2, f3]
            if url and str(url).strip()
        ]

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_odometro_entrada_url'
            LIMIT 1
        """)
        tem_foto_odometro = cur.fetchone() is not None

        campo_foto_odometro = (
            "COALESCE(foto_odometro_entrada_url, '')"
            if tem_foto_odometro
            else "''"
        )

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'veiculo_danificado_saida'
            LIMIT 1
        """)
        tem_dano_saida = cur.fetchone() is not None

        if tem_dano_saida:
            campos_dano_saida = """
                COALESCE(veiculo_danificado_saida, FALSE),
                COALESCE(observacao_dano_saida, ''),
                COALESCE(foto_dano_saida_url_1, ''),
                COALESCE(foto_dano_saida_url_2, ''),
                COALESCE(foto_dano_saida_url_3, '')
            """
        else:
            campos_dano_saida = """
                FALSE,
                '',
                '',
                '',
                ''
            """

        cur.execute(f"""
            SELECT
                checklist_entrada,
                checklist_saida,
                COALESCE(foto_entrada_url, ''),
                COALESCE(foto_saida_url, ''),
                {campo_foto_odometro} AS foto_odometro,
                horario_inicio,
                horario_fim,
                COALESCE(ajustado, FALSE),
                COALESCE(motivo_ajuste, ''),
                {campos_dano_saida}
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

        fotos_dano_saida = _lista_fotos_dano_saida(row[11], row[12], row[13])

        return jsonify({
            "sucesso": True,
            "checklist_entrada": checklist_entrada["itens"],
            "checklist_saida": checklist_saida["itens"],
            "checklist_entrada_detalhe": checklist_entrada,
            "checklist_saida_detalhe": checklist_saida,
            "fotoEntrada": row[2] or "",
            "fotoSaida": row[3] or "",
            "fotoOdometro": row[4] or "",
            "horaEntrada": formatar_hora(row[5]),
            "horaSaida": formatar_hora(row[6]),
            "ajustado": bool(row[7]),
            "motivoAjuste": row[8] or "",
            "veiculoDanificadoSaida": bool(row[9]),
            "observacaoDanoSaida": row[10] or "",
            "fotosDanoSaida": fotos_dano_saida,
            "fotoDanoSaida": fotos_dano_saida[0] if fotos_dano_saida else ""
        }), 200

    except Exception as e:
        print("ERRO api_detalhe_expediente:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": f"Erro ao carregar detalhe do expediente: {str(e)}"
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
# =========================
# API COLABORADORES (AGORA COM FOTOS)
# =========================

def ajustar_fuso(dt):
    if not dt:
        return None

    tz_br = ZoneInfo("America/Sao_Paulo")
    tz_utc = ZoneInfo("UTC")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz_utc)

    return dt.astimezone(tz_br)


def formatar_hora(dt):
    dt = ajustar_fuso(dt)
    return dt.strftime("%H:%M") if dt else ""


def formatar_data(inicio, fim):
    dt = ajustar_fuso(inicio) or ajustar_fuso(fim)
    return dt.date().isoformat() if dt else ""

CHECKLIST_PADRAO_ALERTAS = [
    "power meet pon",
    "Step",
    "Cones",
    "bobina de fibra",
    "Escada principal",
    "Escada de alumínio",
    "martelete",
    "kit FTTH",
    "KIT EPI COMPLETO"
]

def _normalizar_texto_alerta(valor):
    if valor is None:
        return ""
    texto = str(valor).strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto
def _parse_datahora_registro(data_str, hora_str):
    if not data_str or not hora_str:
        return None

    try:
        data_base = str(data_str).split("T")[0]
        hora_base = str(hora_str)[:5]
        dt = datetime.strptime(f"{data_base} {hora_base}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    except Exception:
        return None

def _registro_aberto_alerta(registro):
    if registro.get("horaSaida"):
        return False
    if str(registro.get("status") or "").strip().lower() == "finalizado":
        return False
    return bool(registro.get("horaEntrada"))

def _horas_aberto_alerta(registro):
    inicio = _parse_datahora_registro(registro.get("data"), registro.get("horaEntrada"))
    if not inicio:
        return 0.0
    

def _obter_nomes_dupla_alerta(registro):
    detalhe = registro.get("checklistEntradaDetalhe") or {}

    dupla_ativa = (
        detalhe.get("trabalhando_em_dupla_ou_mais") is True
        or registro.get("trabalhandoEmDuplaOuMais") is True
    )

    nomes_brutos = (
        registro.get("nomesDuplaOuMais")
        or detalhe.get("nomes_dupla_ou_mais")
        or ""
    )

    if not dupla_ativa or not nomes_brutos:
        return []

    return [
        nome.strip()
        for nome in re.split(r"[,;/|]+", str(nomes_brutos))
        if nome and str(nome).strip()
    ]

def _itens_faltando_alerta(registro):
    detalhe = registro.get("checklistEntradaDetalhe") or {}

    itens = []
    if isinstance(detalhe.get("itens_marcados"), list):
        itens = detalhe.get("itens_marcados")
    elif isinstance(detalhe.get("itens"), list):
        itens = detalhe.get("itens")
    elif isinstance(registro.get("checklistEntrada"), list):
        itens = registro.get("checklistEntrada")

    itens_normalizados = {_normalizar_texto_alerta(item) for item in itens if str(item).strip()}

    faltando = []
    for item_padrao in CHECKLIST_PADRAO_ALERTAS:
        if _normalizar_texto_alerta(item_padrao) not in itens_normalizados:
            faltando.append(item_padrao)

    return faltando

def _tem_observacao_alerta(registro):
    detalhe = registro.get("checklistEntradaDetalhe") or {}

    observacao_entrada = (
        registro.get("observacaoEntrada")
        or detalhe.get("observacao")
        or ""
    ).strip()

    observacao_saida = (
        registro.get("observacaoDanoSaida")
        or ""
    ).strip()

    return observacao_entrada, observacao_saida

def _titulo_data_hora_br(registro):
    dt = _parse_datahora_registro(registro.get("data"), registro.get("horaEntrada"))
    if not dt:
        return registro.get("data") or "-"
    return dt.strftime("%d/%m/%Y às %H:%M")

def _buscar_registros_colaboradores(uid):
    conn = cur = None

    def _status_calculado(status_db, horario_inicio, horario_fim):
        status_db = (status_db or "").strip().lower()

        if horario_inicio and horario_fim:
            return "finalizado"

        if horario_inicio and not horario_fim:
            return "em_andamento"

        if status_db in ("finalizado", "em_andamento", "pendente"):
            return status_db

        return "pendente"

    def _extrair_observacao_entrada(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return ""
        return str(checklist_detalhe.get("observacao") or "").strip()

    def _extrair_dupla(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return {
                "trabalhando_em_dupla_ou_mais": None,
                "nomes_dupla_ou_mais": ""
            }

        return {
            "trabalhando_em_dupla_ou_mais": checklist_detalhe.get("trabalhando_em_dupla_ou_mais"),
            "nomes_dupla_ou_mais": str(checklist_detalhe.get("nomes_dupla_ou_mais") or "").strip()
        }

    def _veiculo_danificado_entrada(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return False

        veiculo_perfeito = checklist_detalhe.get("veiculo_perfeito")
        estado_veiculo = str(checklist_detalhe.get("estado_veiculo") or "").strip().lower()

        if veiculo_perfeito is False:
            return True

        if estado_veiculo == "danificado":
            return True

        return False

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_odometro_entrada_url'
            LIMIT 1
        """)
        tem_foto_odometro = cur.fetchone() is not None

        campo_foto_odometro = (
            "COALESCE(e.foto_odometro_entrada_url, '')"
            if tem_foto_odometro
            else "''"
        )

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'veiculo_danificado_saida'
            LIMIT 1
        """)
        tem_dano_saida = cur.fetchone() is not None

        if tem_dano_saida:
            campos_dano_saida = """
                COALESCE(e.veiculo_danificado_saida, FALSE),
                COALESCE(e.observacao_dano_saida, ''),
                COALESCE(e.foto_dano_saida_url_1, ''),
                COALESCE(e.foto_dano_saida_url_2, ''),
                COALESCE(e.foto_dano_saida_url_3, '')
            """
        else:
            campos_dano_saida = """
                FALSE,
                '',
                '',
                '',
                ''
            """

        cur.execute(f"""
            SELECT
                e.id,
                COALESCE(m.nome, '') AS colaborador_nome,
                COALESCE(v.modelo, '') AS veiculo_modelo,
                COALESCE(v.placa, '') AS veiculo_placa,
                e.horario_inicio,
                e.horario_fim,
                COALESCE(e.status, '') AS status_db,
                e.checklist_entrada,
                e.checklist_saida,
                COALESCE(e.foto_entrada_url, '') AS foto_entrada_url,
                COALESCE(e.foto_saida_url, '') AS foto_saida_url,
                {campo_foto_odometro} AS foto_odometro,
                COALESCE(e.ajustado, FALSE) AS ajustado,
                COALESCE(e.motivo_ajuste, '') AS motivo_ajuste,
                {campos_dano_saida}
            FROM expedientes e
            LEFT JOIN motoristas m
                ON m.id = COALESCE(e.colaborador_id, e.motorista_id)
            LEFT JOIN veiculos v
                ON v.id = e.veiculo_id
            WHERE e.usuario_id = %s
            ORDER BY e.id DESC
        """, (uid,))

        rows = cur.fetchall()
        data = []

        for row in rows:
            checklist_entrada_raw = row[7]
            checklist_saida_raw = row[8]

            checklist_entrada_lista = _normalizar_checklist_colaboradores(checklist_entrada_raw)
            checklist_saida_lista = _normalizar_checklist_colaboradores(checklist_saida_raw)

            checklist_entrada_detalhe = _normalizar_checklist_detalhe_colaboradores(checklist_entrada_raw)
            checklist_saida_detalhe = _normalizar_checklist_detalhe_colaboradores(checklist_saida_raw)

            fotos_dano_saida = _lista_fotos_dano_saida([row[16], row[17], row[18]])

            dupla_info = _extrair_dupla(checklist_entrada_detalhe)
            observacao_entrada = _extrair_observacao_entrada(checklist_entrada_detalhe)
            veiculo_danificado_entrada = _veiculo_danificado_entrada(checklist_entrada_detalhe)

            horario_inicio = row[4]
            horario_fim = row[5]
            status_final = _status_calculado(row[6], horario_inicio, horario_fim)

            data.append({
                "id": row[0],
                "colaborador": row[1] or "",
                "veiculo": row[2] or "",
                "placa": row[3] or "",

                "data": formatar_data(horario_inicio, horario_fim),
                "horaEntrada": formatar_hora(horario_inicio),
                "horaSaida": formatar_hora(horario_fim),
                "status": status_final,

                "checklistEntrada": checklist_entrada_lista,
                "checklistSaida": checklist_saida_lista,

                "checklistEntradaDetalhe": checklist_entrada_detalhe,
                "checklistSaidaDetalhe": checklist_saida_detalhe,

                "fotoEntrada": row[9] or "",
                "fotoSaida": row[10] or "",
                "fotoOdometro": row[11] or "",

                "ajustado": bool(row[12]),
                "motivoAjuste": row[13] or "",

                "veiculoDanificadoEntrada": bool(veiculo_danificado_entrada),
                "veiculoDanificadoSaida": bool(row[14]),
                "observacaoEntrada": observacao_entrada,
                "observacaoDanoSaida": row[15] or "",

                "trabalhandoEmDuplaOuMais": dupla_info["trabalhando_em_dupla_ou_mais"],
                "nomesDuplaOuMais": dupla_info["nomes_dupla_ou_mais"],

                "fotosDanoSaida": fotos_dano_saida,
                "fotoDanoSaida": fotos_dano_saida[0] if fotos_dano_saida else ""
            })

        return data

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.get("/api/colaboradores/registros")
def api_colaboradores_registros():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    def ajustar_fuso(dt):
        if not dt:
            return None

        tz_br = ZoneInfo("America/Sao_Paulo")

        # Se vier sem timezone, assume UTC para não jogar o registro no dia errado
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        return dt.astimezone(tz_br)

    def formatar_hora(dt):
        dt = ajustar_fuso(dt)
        return dt.strftime("%H:%M") if dt else ""

    def formatar_data(inicio, fim):
        dt = ajustar_fuso(inicio) or ajustar_fuso(fim)
        return dt.date().isoformat() if dt else ""

    def _status_calculado(status_db, horario_inicio, horario_fim):
        status_db = (status_db or "").strip().lower()

        if horario_inicio and horario_fim:
            return "finalizado"

        if horario_inicio and not horario_fim:
            return "em_andamento"

        if status_db in ("finalizado", "em_andamento", "pendente"):
            return status_db

        return "pendente"

    def _extrair_observacao_entrada(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return ""
        return str(checklist_detalhe.get("observacao") or "").strip()

    def _extrair_dupla(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return {
                "trabalhando_em_dupla_ou_mais": None,
                "nomes_dupla_ou_mais": ""
            }

        return {
            "trabalhando_em_dupla_ou_mais": checklist_detalhe.get("trabalhando_em_dupla_ou_mais"),
            "nomes_dupla_ou_mais": str(checklist_detalhe.get("nomes_dupla_ou_mais") or "").strip()
        }

    def _veiculo_danificado_entrada(checklist_detalhe):
        if not isinstance(checklist_detalhe, dict):
            return False

        veiculo_perfeito = checklist_detalhe.get("veiculo_perfeito")
        estado_veiculo = str(checklist_detalhe.get("estado_veiculo") or "").strip().lower()

        if veiculo_perfeito is False:
            return True

        if estado_veiculo == "danificado":
            return True

        return False

    def _itens_faltando_checklist(checklist_detalhe):
        checklist_padrao = [
            "power meet pon",
            "Step",
            "Cones",
            "bobina de fibra",
            "Escada principal",
            "Escada de alumínio",
            "martelete",
            "kit FTTH",
            "KIT EPI COMPLETO"
        ]

        if not isinstance(checklist_detalhe, dict):
            return []

        itens_marcados = checklist_detalhe.get("itens_marcados") or checklist_detalhe.get("itens") or []
        if not isinstance(itens_marcados, list):
            itens_marcados = []

        def norm(txt):
            return str(txt or "").strip().lower()

        marcados_norm = {norm(item) for item in itens_marcados if str(item).strip()}

        faltando = []
        for item in checklist_padrao:
            if norm(item) not in marcados_norm:
                faltando.append(item)

        return faltando

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_odometro_entrada_url'
            LIMIT 1
        """)
        tem_foto_odometro = cur.fetchone() is not None

        campo_foto_odometro = (
            "COALESCE(e.foto_odometro_entrada_url, '')"
            if tem_foto_odometro
            else "''"
        )

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'veiculo_danificado_saida'
            LIMIT 1
        """)
        tem_dano_saida = cur.fetchone() is not None

        if tem_dano_saida:
            campos_dano_saida = """
                COALESCE(e.veiculo_danificado_saida, FALSE),
                COALESCE(e.observacao_dano_saida, ''),
                COALESCE(e.foto_dano_saida_url_1, ''),
                COALESCE(e.foto_dano_saida_url_2, ''),
                COALESCE(e.foto_dano_saida_url_3, '')
            """
        else:
            campos_dano_saida = """
                FALSE,
                '',
                '',
                '',
                ''
            """

        cur.execute(f"""
            SELECT
                e.id,
                COALESCE(m.nome, '') AS colaborador_nome,
                COALESCE(v.modelo, '') AS veiculo_modelo,
                COALESCE(v.placa, '') AS veiculo_placa,
                e.horario_inicio,
                e.horario_fim,
                COALESCE(e.status, '') AS status_db,
                e.checklist_entrada,
                e.checklist_saida,
                COALESCE(e.foto_entrada_url, '') AS foto_entrada_url,
                COALESCE(e.foto_saida_url, '') AS foto_saida_url,
                {campo_foto_odometro} AS foto_odometro,
                COALESCE(e.ajustado, FALSE) AS ajustado,
                COALESCE(e.motivo_ajuste, '') AS motivo_ajuste,
                {campos_dano_saida}
            FROM expedientes e
            LEFT JOIN motoristas m
                ON m.id = COALESCE(e.colaborador_id, e.motorista_id)
            LEFT JOIN veiculos v
                ON v.id = e.veiculo_id
            WHERE e.usuario_id = %s
            ORDER BY e.id DESC
        """, (uid,))

        rows = cur.fetchall()
        data = []

        for row in rows:
            checklist_entrada_raw = row[7]
            checklist_saida_raw = row[8]

            checklist_entrada_lista = _normalizar_checklist_colaboradores(checklist_entrada_raw)
            checklist_saida_lista = _normalizar_checklist_colaboradores(checklist_saida_raw)

            checklist_entrada_detalhe = _normalizar_checklist_detalhe_colaboradores(checklist_entrada_raw)
            checklist_saida_detalhe = _normalizar_checklist_detalhe_colaboradores(checklist_saida_raw)

            fotos_dano_saida = _lista_fotos_dano_saida([row[16], row[17], row[18]])

            dupla_info = _extrair_dupla(checklist_entrada_detalhe)
            observacao_entrada = _extrair_observacao_entrada(checklist_entrada_detalhe)
            veiculo_danificado_entrada = _veiculo_danificado_entrada(checklist_entrada_detalhe)
            itens_faltando = _itens_faltando_checklist(checklist_entrada_detalhe)

            horario_inicio = row[4]
            horario_fim = row[5]
            status_final = _status_calculado(row[6], horario_inicio, horario_fim)

            data.append({
                "id": row[0],
                "colaborador": row[1] or "",
                "veiculo": row[2] or "",
                "placa": row[3] or "",

                "data": formatar_data(horario_inicio, horario_fim),
                "horaEntrada": formatar_hora(horario_inicio),
                "horaSaida": formatar_hora(horario_fim),
                "status": status_final,

                "checklistEntrada": checklist_entrada_lista,
                "checklistSaida": checklist_saida_lista,

                "checklistEntradaDetalhe": checklist_entrada_detalhe,
                "checklistSaidaDetalhe": checklist_saida_detalhe,

                "fotoEntrada": row[9] or "",
                "fotoSaida": row[10] or "",
                "fotoOdometro": row[11] or "",

                "ajustado": bool(row[12]),
                "motivoAjuste": row[13] or "",

                "veiculoDanificadoEntrada": bool(veiculo_danificado_entrada),
                "veiculoDanificadoSaida": bool(row[14]),
                "observacaoEntrada": observacao_entrada,
                "observacaoDanoSaida": row[15] or "",

                "trabalhandoEmDuplaOuMais": dupla_info["trabalhando_em_dupla_ou_mais"],
                "nomesDuplaOuMais": dupla_info["nomes_dupla_ou_mais"],

                "itensFaltandoChecklist": itens_faltando,
                "temChecklistFaltando": len(itens_faltando) > 0,

                "fotosDanoSaida": fotos_dano_saida,
                "fotoDanoSaida": fotos_dano_saida[0] if fotos_dano_saida else ""
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
    

@app.get("/api/alertas")
def api_alertas():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    conn = cur = None
    try:
        registros = _buscar_registros_colaboradores(uid)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT alerta_id
            FROM alertas_resolvidos
            WHERE usuario_id = %s
        """, (uid,))
        resolvidos_ids = {str(row[0]) for row in cur.fetchall()}

        alertas = []
        alertas_ids = set()

        def _parse_datahora_registro(data_str, hora_str):
            if not data_str or not hora_str:
                return None

            try:
                data_base = str(data_str).split("T")[0]
                hora_base = str(hora_str)[:5]
                dt = datetime.strptime(f"{data_base} {hora_base}", "%Y-%m-%d %H:%M")
                return dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            except Exception:
                return None

        def _registro_aberto_alerta(registro):
            if registro.get("horaSaida"):
                return False
            if str(registro.get("status") or "").strip().lower() == "finalizado":
                return False
            return bool(registro.get("horaEntrada"))

        def _horas_aberto_alerta(registro):
            inicio = _parse_datahora_registro(registro.get("data"), registro.get("horaEntrada"))
            if not inicio:
                return 0.0

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            return (agora - inicio).total_seconds() / 3600.0
        
        def _obter_nomes_dupla_alerta(registro):
            detalhe = registro.get("checklistEntradaDetalhe") or {}

            dupla_ativa = (
                detalhe.get("trabalhando_em_dupla_ou_mais") is True
                or registro.get("trabalhandoEmDuplaOuMais") is True
            )

            nomes_brutos = (
                registro.get("nomesDuplaOuMais")
                or detalhe.get("nomes_dupla_ou_mais")
                or ""
            )

            if not dupla_ativa or not nomes_brutos:
                return []

            return [
                nome.strip()
                for nome in re.split(r"[,/|;]+", str(nomes_brutos))
                if nome and str(nome).strip()
            ]

        def add_alerta(
            alerta_id,
            tipo,
            expediente_id,
            titulo,
            texto,
            data_hora,
            colaborador="",
            veiculo="",
            placa="",
            critico=False,
            resolvivel=False,
        ):
            alerta_id = str(alerta_id)

            if alerta_id in alertas_ids:
                return

            alertas_ids.add(alerta_id)

            alertas.append({
                "id": alerta_id,
                "tipo": tipo,
                "expediente_id": int(expediente_id),
                "titulo": titulo,
                "texto": texto,
                "dataHora": ajustar_fuso(data_hora).strftime("%d/%m/%Y %H:%M") if data_hora else "",
                "critico": bool(critico),
                "resolvivel": bool(resolvivel),
                "resolvido": alerta_id in resolvidos_ids,
                "meta": {
                    "colaborador": colaborador or "",
                    "veiculo": veiculo or "",
                    "placa": placa or ""
                }
            })

        for reg in registros:
            colaborador = reg.get("colaborador") or "Colaborador"
            veiculo = reg.get("veiculo") or "Veículo"
            placa = reg.get("placa") or ""
            expediente_id = reg.get("id")

            if not expediente_id:
                continue

            data_hora_inicio = _parse_datahora_registro(reg.get("data"), reg.get("horaEntrada"))
            data_hora_saida = _parse_datahora_registro(reg.get("data"), reg.get("horaSaida")) or data_hora_inicio

            if _registro_aberto_alerta(reg):
                nomes_dupla = _obter_nomes_dupla_alerta(reg)
                if nomes_dupla:
                    texto = (
                        f"{colaborador} iniciou expediente em {reg.get('data')} às {reg.get('horaEntrada')} "
                        f"e está em dupla com {', '.join(nomes_dupla)}."
                    )
                else:
                    texto = f"{colaborador} iniciou expediente em {reg.get('data')} às {reg.get('horaEntrada')}."

                add_alerta(
                    alerta_id=f"colaborador-ativo-{expediente_id}",
                    tipo="colaboradores_ativos",
                    expediente_id=expediente_id,
                    titulo="Expediente em andamento",
                    texto=texto,
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=False,
                    resolvivel=False
                )

            if _registro_aberto_alerta(reg):
                texto = f"O veículo {veiculo} {f'({placa})' if placa else ''} está vinculado a expediente em aberto."
                add_alerta(
                    alerta_id=f"veiculo-uso-{expediente_id}",
                    tipo="veiculos_em_uso",
                    expediente_id=expediente_id,
                    titulo="Veículo em uso",
                    texto=texto.strip(),
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=False,
                    resolvivel=False
                )

            itens_faltando = reg.get("itensFaltandoChecklist") or []
            if itens_faltando:
                texto = f"No checklist de entrada de {colaborador}, faltaram os itens: {', '.join(itens_faltando)}."
                add_alerta(
                    alerta_id=f"checklist-{expediente_id}",
                    tipo="checklist_faltando",
                    expediente_id=expediente_id,
                    titulo="Checklist faltando equipamento",
                    texto=texto,
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=True,
                    resolvivel=True
                )

            if reg.get("veiculoDanificadoEntrada") is True:
                texto = f"No início do expediente de {colaborador}, o veículo foi informado como danificado."
                add_alerta(
                    alerta_id=f"dano-entrada-{expediente_id}",
                    tipo="veiculo_danificado",
                    expediente_id=expediente_id,
                    titulo="Veículo danificado",
                    texto=texto,
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=True,
                    resolvivel=True
                )

            if reg.get("veiculoDanificadoSaida") is True:
                texto = (
                    f"No encerramento do expediente de {colaborador}, o veículo foi informado novamente como danificado."
                    if reg.get("veiculoDanificadoEntrada") is True
                    else f"No encerramento do expediente de {colaborador}, o veículo foi informado como danificado."
                )
                add_alerta(
                    alerta_id=f"dano-saida-{expediente_id}",
                    tipo="veiculo_danificado",
                    expediente_id=expediente_id,
                    titulo="Veículo danificado",
                    texto=texto,
                    data_hora=data_hora_saida,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=True,
                    resolvivel=True
                )

            observacao_entrada = str(reg.get("observacaoEntrada") or "").strip()
            observacao_saida = str(reg.get("observacaoDanoSaida") or "").strip()

            if observacao_entrada:
                add_alerta(
                    alerta_id=f"obs-entrada-{expediente_id}",
                    tipo="observacoes",
                    expediente_id=expediente_id,
                    titulo="Observação registrada",
                    texto=f'{colaborador} registrou a observação: "{observacao_entrada}".',
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=False,
                    resolvivel=False
                )

            if observacao_saida:
                add_alerta(
                    alerta_id=f"obs-saida-{expediente_id}",
                    tipo="observacoes",
                    expediente_id=expediente_id,
                    titulo="Observação registrada",
                    texto=f'{colaborador} registrou a observação: "{observacao_saida}".',
                    data_hora=data_hora_saida,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=False,
                    resolvivel=False
                )

            if _registro_aberto_alerta(reg) and _horas_aberto_alerta(reg) >= 11:
                texto = f"O expediente de {colaborador} permanece aberto há mais de 11 horas sem encerramento."
                add_alerta(
                    alerta_id=f"pendente-{expediente_id}",
                    tipo="pendentes",
                    expediente_id=expediente_id,
                    titulo="Expediente pendente",
                    texto=texto,
                    data_hora=data_hora_inicio,
                    colaborador=colaborador,
                    veiculo=veiculo,
                    placa=placa,
                    critico=True,
                    resolvivel=True
                )

        alertas.sort(key=lambda a: a.get("dataHora") or "", reverse=True)

        return jsonify({
            "sucesso": True,
            "alertas": alertas
        }), 200

    except Exception as e:
        print("ERRO api_alertas:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/api/alertas/pdf/<int:alerta_id>")
def gerar_pdf_alerta(alerta_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    def _baixar_imagem_para_bytes(url):
        try:
            if not url:
                return None
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=15) as resp:
                return BytesIO(resp.read())
        except Exception as e:
            print("ERRO ao baixar imagem para PDF:", e, flush=True)
            return None

    def _fmt_datahora(dt):
        if not dt:
            return "-"
        try:
            tz_br = ZoneInfo("America/Sao_Paulo")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            dt = dt.astimezone(tz_br)
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(dt)

    def _fmt_bool(valor):
        return "Sim" if valor is True else "Não" if valor is False else "-"

    def _texto(v):
        return str(v or "").strip() or "-"

    def _normalizar_checklist_pdf(valor):
        detalhe = _normalizar_checklist_detalhe_colaboradores(valor)
        itens = detalhe.get("itens_marcados") or detalhe.get("itens") or []
        if not isinstance(itens, list):
            itens = []
        return {
            "itens": [str(i).strip() for i in itens if str(i).strip()],
            "veiculo_perfeito": detalhe.get("veiculo_perfeito"),
            "observacao": str(detalhe.get("observacao") or "").strip(),
            "quantidade_cones": str(detalhe.get("quantidade_cones") or "").strip(),
            "trabalhando_em_dupla_ou_mais": detalhe.get("trabalhando_em_dupla_ou_mais"),
            "nomes_dupla_ou_mais": str(detalhe.get("nomes_dupla_ou_mais") or "").strip(),
            "confirmacao_veracidade": bool(detalhe.get("confirmacao_veracidade"))
        }

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_odometro_entrada_url'
            LIMIT 1
        """)
        tem_foto_odometro = cur.fetchone() is not None

        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_dano_saida_url_1'
            LIMIT 1
        """)
        tem_dano_saida = cur.fetchone() is not None

        campo_foto_odometro = (
            "COALESCE(e.foto_odometro_entrada_url, '')"
            if tem_foto_odometro else "''"
        )

        if tem_dano_saida:
            campos_dano_saida = """
                COALESCE(e.foto_dano_saida_url_1, ''),
                COALESCE(e.foto_dano_saida_url_2, ''),
                COALESCE(e.foto_dano_saida_url_3, '')
            """
        else:
            campos_dano_saida = """
                '',
                '',
                ''
            """

        cur.execute(f"""
            SELECT
                e.id,
                COALESCE(m.nome, '') AS colaborador_nome,
                COALESCE(m.cpf, '') AS colaborador_cpf,
                COALESCE(m.email, '') AS colaborador_email,
                COALESCE(v.modelo, '') AS veiculo_modelo,
                COALESCE(v.placa, '') AS veiculo_placa,
                e.horario_inicio,
                e.horario_fim,
                e.checklist_entrada,
                e.checklist_saida,
                COALESCE(e.foto_entrada_url, '') AS foto_entrada_url,
                COALESCE(e.foto_saida_url, '') AS foto_saida_url,
                {campo_foto_odometro} AS foto_odometro_url,
                COALESCE(e.veiculo_danificado_saida, FALSE) AS veiculo_danificado_saida,
                COALESCE(e.observacao_dano_saida, '') AS observacao_dano_saida,
                COALESCE(e.motivo_ajuste, '') AS motivo_ajuste,
                COALESCE(e.ajustado, FALSE) AS ajustado,
                {campos_dano_saida}
            FROM expedientes e
            LEFT JOIN motoristas m
                ON m.id = COALESCE(e.colaborador_id, e.motorista_id)
            LEFT JOIN veiculos v
                ON v.id = e.veiculo_id
            WHERE e.id = %s
              AND e.usuario_id = %s
            LIMIT 1
        """, (alerta_id, uid))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Registro não encontrado"
            }), 404

        checklist_entrada = _normalizar_checklist_pdf(row[8])
        checklist_saida = _normalizar_checklist_pdf(row[9])

        fotos_dano = [
            str(url).strip()
            for url in [row[17], row[18], row[19]]
            if url and str(url).strip()
        ]

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.6 * cm,
            leftMargin=1.6 * cm,
            topMargin=1.3 * cm,
            bottomMargin=1.3 * cm
        )

        styles = getSampleStyleSheet()
        style_title = ParagraphStyle(
            "TitleNexar",
            parent=styles["Title"],
            fontSize=21,
            leading=24,
            textColor=colors.HexColor("#24163A"),
            spaceAfter=10
        )
        style_h2 = ParagraphStyle(
            "H2Nexar",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#6F2CFF"),
            spaceBefore=10,
            spaceAfter=8
        )
        style_body = ParagraphStyle(
            "BodyNexar",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#2B2438")
        )
        style_small = ParagraphStyle(
            "SmallNexar",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#5F5870")
        )

        story = []

        logo_path = os.path.join(STATIC_DIR, "img", "logo.png")
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=1.9 * cm, height=1.9 * cm)
            titulo_bloco = Paragraph(
                "<b>Agência Nexar</b><br/><font size='9' color='#5F5870'>Relatório completo do expediente e ocorrência</font>",
                style_body
            )
            header = Table([[logo, titulo_bloco]], colWidths=[2.3 * cm, 13.5 * cm])
            header.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header)
        else:
            story.append(Paragraph("<b>Agência Nexar</b>", style_title))

        story.append(Spacer(1, 0.35 * cm))
        story.append(Paragraph(f"Ocorrência Nº {alerta_id}", style_title))
        story.append(Spacer(1, 0.25 * cm))

        resumo = Table([
            ["Colaborador", _texto(row[1]), "CPF", _texto(row[2])],
            ["Email", _texto(row[3]), "Veículo", _texto(row[4])],
            ["Placa", _texto(row[5]), "Ajustado", _fmt_bool(bool(row[16]))],
            ["Entrada", _fmt_datahora(row[6]), "Saída", _fmt_datahora(row[7])],
        ], colWidths=[2.8 * cm, 5.2 * cm, 2.2 * cm, 5.6 * cm])
        resumo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F4FD")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DDD3F7")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E9E1FB")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2B2438")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(resumo)
        story.append(Spacer(1, 0.35 * cm))

        story.append(Paragraph("Checklist de entrada", style_h2))
        entrada_texto = "<br/>".join([f"- {item}" for item in checklist_entrada["itens"]]) if checklist_entrada["itens"] else "- Nenhum item marcado"
        story.append(Paragraph(
            f"<b>Estado do veículo:</b> {_fmt_bool(False if checklist_entrada['veiculo_perfeito'] is False else True if checklist_entrada['veiculo_perfeito'] is True else None)}<br/>"
            f"<b>Observação entrada:</b> {_texto(checklist_entrada['observacao'])}<br/>"
            f"<b>Cones:</b> {_texto(checklist_entrada['quantidade_cones'])}<br/>"
            f"<b>Dupla:</b> {_fmt_bool(checklist_entrada['trabalhando_em_dupla_ou_mais'])}<br/>"
            f"<b>Nomes dupla:</b> {_texto(checklist_entrada['nomes_dupla_ou_mais'])}<br/>"
            f"<b>Confirmação de veracidade:</b> {_fmt_bool(checklist_entrada['confirmacao_veracidade'])}",
            style_body
        ))
        story.append(Spacer(1, 0.12 * cm))
        story.append(Paragraph(f"<b>Itens marcados:</b><br/>{entrada_texto}", style_body))
        story.append(Spacer(1, 0.25 * cm))

        story.append(Paragraph("Checklist / condição na saída", style_h2))
        saida_texto = "<br/>".join([f"- {item}" for item in checklist_saida["itens"]]) if checklist_saida["itens"] else "- Nenhum item marcado"
        story.append(Paragraph(
            f"<b>Veículo danificado:</b> {_fmt_bool(bool(row[13]))}<br/>"
            f"<b>Observação do dano:</b> {_texto(row[14])}<br/>"
            f"<b>Motivo de ajuste:</b> {_texto(row[15])}",
            style_body
        ))
        story.append(Spacer(1, 0.12 * cm))
        story.append(Paragraph(f"<b>Itens de saída:</b><br/>{saida_texto}", style_body))
        story.append(Spacer(1, 0.25 * cm))

        story.append(Paragraph("Fotos anexadas", style_h2))

        fotos_bloco = [
            ("Foto de entrada", row[10]),
            ("Foto de saída", row[11]),
            ("Foto do odômetro", row[12]),
        ]

        for titulo, url in fotos_bloco:
            story.append(Paragraph(f"<b>{titulo}:</b> {_texto(url)}", style_small))
            img_bytes = _baixar_imagem_para_bytes(url)
            if img_bytes:
                try:
                    story.append(Image(img_bytes, width=7.2 * cm, height=5.2 * cm))
                except Exception as e:
                    print("ERRO ao inserir imagem no PDF:", e, flush=True)
            story.append(Spacer(1, 0.18 * cm))

        if fotos_dano:
            story.append(Paragraph("<b>Fotos do dano:</b>", style_small))
            for idx, url in enumerate(fotos_dano, start=1):
                story.append(Paragraph(f"Foto do dano {idx}: {_texto(url)}", style_small))
                img_bytes = _baixar_imagem_para_bytes(url)
                if img_bytes:
                    try:
                        story.append(Image(img_bytes, width=7.2 * cm, height=5.2 * cm))
                    except Exception as e:
                        print("ERRO ao inserir foto de dano no PDF:", e, flush=True)
                story.append(Spacer(1, 0.18 * cm))

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Contato: contatoagencianexar@gmail.com", style_small))

        doc.build(story)
        buffer.seek(0)

        nome_pdf = f"Ocorrencia_{alerta_id}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=nome_pdf,
            mimetype="application/pdf"
        )

    except Exception as e:
        print("ERRO PDF:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": f"Erro ao gerar PDF: {str(e)}"
        }), 500

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

    conn = cur = None

    try:
        content_type = (request.content_type or "").lower()

        payload = {}
        arquivos_dano = []

        if "multipart/form-data" in content_type:
            payload_raw = request.form.get("payload") or "{}"
            try:
                payload = json.loads(payload_raw)
            except Exception:
                return jsonify({
                    "sucesso": False,
                    "erro": "Payload inválido no multipart"
                }), 400

            for chave in ["foto_dano_1", "foto_dano_2", "foto_dano_3"]:
                arquivo = request.files.get(chave)
                if arquivo and (arquivo.filename or "").strip():
                    arquivos_dano.append(arquivo)
        else:
            payload = request.get_json(silent=True) or {}

        expediente_id = payload.get("id")
        entrada = payload.get("entrada")
        saida = payload.get("saida")
        checklist_entrada = payload.get("checklistEntrada")
        checklist_saida = payload.get("checklistSaida")  # mantido por compatibilidade temporária
        motivo = payload.get("motivo")

        veiculo_danificado_saida = payload.get("veiculoDanificadoSaida")
        observacao_dano_saida = (payload.get("observacaoDanoSaida") or "").strip()

        if not expediente_id:
            return jsonify({
                "sucesso": False,
                "erro": "id é obrigatório"
            }), 400

        if veiculo_danificado_saida is True and not observacao_dano_saida:
            return jsonify({
                "sucesso": False,
                "erro": "Observação do dano é obrigatória quando o veículo estiver danificado"
            }), 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                horario_inicio,
                horario_fim,
                status,
                data,
                COALESCE(foto_dano_saida_url_1, ''),
                COALESCE(foto_dano_saida_url_2, ''),
                COALESCE(foto_dano_saida_url_3, '')
            FROM expedientes
            WHERE id = %s
            LIMIT 1
        """, (expediente_id,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Expediente não encontrado"
            }), 404

        (
            horario_inicio_atual,
            horario_fim_atual,
            status_atual,
            data_expediente,
            foto1_atual,
            foto2_atual,
            foto3_atual
        ) = row

        def _parse_hora_texto(hora_str):
            if hora_str is None:
                return None

            texto = str(hora_str).strip()
            if not texto:
                return None

            try:
                return datetime.strptime(texto, "%H:%M").time()
            except ValueError:
                raise ValueError("Horário inválido. Use o formato HH:MM.")

        def _combinar_data_com_hora(data_base, hora_str, dt_base=None):
            hora_obj = _parse_hora_texto(hora_str)
            if not hora_obj:
                return None

            tz_br = ZoneInfo("America/Sao_Paulo")
            tz_utc = ZoneInfo("UTC")

            if isinstance(data_base, datetime):
                data_ref = data_base.date()
            elif isinstance(data_base, date):
                data_ref = data_base
            elif isinstance(dt_base, datetime):
                data_ref = dt_base.date()
            else:
                data_ref = date.today()

            dt_local = datetime.combine(data_ref, hora_obj).replace(tzinfo=tz_br)
            dt_utc = dt_local.astimezone(tz_utc)

            # salva como TIMESTAMP sem timezone no banco
            return dt_utc.replace(tzinfo=None)

        campos = []
        valores = []

        novo_horario_inicio = None
        novo_horario_fim = None

        if entrada:
            novo_horario_inicio = _combinar_data_com_hora(
                data_base=data_expediente,
                hora_str=entrada,
                dt_base=horario_inicio_atual or horario_fim_atual
            )
            if novo_horario_inicio is not None:
                campos.append("horario_inicio = %s")
                valores.append(novo_horario_inicio)

        if saida:
            novo_horario_fim = _combinar_data_com_hora(
                data_base=data_expediente,
                hora_str=saida,
                dt_base=horario_fim_atual or horario_inicio_atual
            )
            if novo_horario_fim is not None:
                campos.append("horario_fim = %s")
                valores.append(novo_horario_fim)

        if checklist_entrada is not None:
            checklist_entrada_json = _parse_checklist_json(checklist_entrada)
            campos.append("checklist_entrada = %s")
            valores.append(json.dumps(checklist_entrada_json))

        if checklist_saida is not None:
            checklist_saida_json = _parse_checklist_json(checklist_saida)
            campos.append("checklist_saida = %s")
            valores.append(json.dumps(checklist_saida_json))

        if motivo is not None:
            campos.append("motivo_ajuste = %s")
            valores.append((motivo or "").strip())

        if veiculo_danificado_saida is not None:
            campos.append("veiculo_danificado_saida = %s")
            valores.append(bool(veiculo_danificado_saida))

            if bool(veiculo_danificado_saida):
                campos.append("observacao_dano_saida = %s")
                valores.append(observacao_dano_saida)
            else:
                campos.append("observacao_dano_saida = %s")
                valores.append("")
                campos.append("foto_dano_saida_url_1 = %s")
                valores.append("")
                campos.append("foto_dano_saida_url_2 = %s")
                valores.append("")
                campos.append("foto_dano_saida_url_3 = %s")
                valores.append("")

        urls_finais = [foto1_atual or "", foto2_atual or "", foto3_atual or ""]

        if arquivos_dano:
            limite = 3
            novas_urls = []
            for indice, arquivo in enumerate(arquivos_dano[:limite], start=1):
                nova_url = _upload_foto_dano_saida(expediente_id, indice, arquivo)
                if nova_url:
                    novas_urls.append(nova_url)

            while len(novas_urls) < 3:
                novas_urls.append("")

            urls_finais = novas_urls[:3]

            campos.append("foto_dano_saida_url_1 = %s")
            valores.append(urls_finais[0])

            campos.append("foto_dano_saida_url_2 = %s")
            valores.append(urls_finais[1])

            campos.append("foto_dano_saida_url_3 = %s")
            valores.append(urls_finais[2])

        campos.append("ajustado = TRUE")

        horario_fim_resultante = novo_horario_fim if novo_horario_fim is not None else horario_fim_atual

        if horario_fim_resultante:
            campos.append("status = 'finalizado'")
        else:
            campos.append("status = 'em_andamento'")

        if not campos:
            return jsonify({
                "sucesso": False,
                "erro": "Nenhum dado enviado para ajuste"
            }), 400

        query = f"""
            UPDATE expedientes
            SET {", ".join(campos)}
            WHERE id = %s
        """

        valores.append(expediente_id)
        cur.execute(query, valores)
        conn.commit()

        return jsonify({
            "sucesso": True,
            "mensagem": "Ajuste salvo com sucesso",
            "fotosDanoSaida": urls_finais
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
    
@app.post("/api/rastreador/localizacao")
def receber_localizacao():
    conn = cur = None
    try:
        data = request.get_json(silent=True) or {}

        imei = str(data.get("imei") or "").strip()
        placa = str(data.get("placa") or "").strip().upper()
        lat = data.get("lat")
        lng = data.get("lng")
        velocidade = data.get("velocidade")
        endereco = str(data.get("endereco") or "").strip() or None
        timestamp_raw = data.get("timestamp")

        if lat is None or lng is None:
            return jsonify({"sucesso": False, "erro": "lat e lng são obrigatórios"}), 400

        try:
            lat = float(lat)
            lng = float(lng)
        except Exception:
            return jsonify({"sucesso": False, "erro": "lat/lng inválidos"}), 400

        velocidade_float = None
        try:
            if velocidade is not None and str(velocidade).strip() != "":
                velocidade_float = float(velocidade)
        except Exception:
            velocidade_float = None

        recebido_em_utc = None
        if timestamp_raw:
            recebido_em_utc = _parse_datetime_local_para_utc(timestamp_raw)
            if recebido_em_utc is None:
                try:
                    recebido_em_utc = _garantir_dt_utc(datetime.fromisoformat(str(timestamp_raw)))
                except Exception:
                    recebido_em_utc = None

        conn = get_db()
        cur = conn.cursor()

        row = None

        if imei:
            cur.execute("""
                SELECT veiculo_id, usuario_id
                FROM rastreadores
                WHERE imei = %s
                  AND ativo = TRUE
                LIMIT 1
            """, (imei,))
            row = cur.fetchone()

        if not row and placa:
            cur.execute("""
                SELECT id, usuario_id
                FROM veiculos
                WHERE placa = %s
                LIMIT 1
            """, (placa,))
            row = cur.fetchone()

        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Rastreador não vinculado e placa não encontrada"
            }), 404

        veiculo_id, usuario_id = row

        if recebido_em_utc:
            cur.execute("""
                INSERT INTO veiculos_localizacao (
                    usuario_id,
                    veiculo_id,
                    latitude,
                    longitude,
                    velocidade_kmh,
                    endereco,
                    recebido_em
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                usuario_id,
                veiculo_id,
                lat,
                lng,
                velocidade_float,
                endereco,
                recebido_em_utc
            ))
        else:
            cur.execute("""
                INSERT INTO veiculos_localizacao (
                    usuario_id,
                    veiculo_id,
                    latitude,
                    longitude,
                    velocidade_kmh,
                    endereco
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                usuario_id,
                veiculo_id,
                lat,
                lng,
                velocidade_float,
                endereco
            ))

        conn.commit()

        return jsonify({
            "sucesso": True,
            "veiculo_id": int(veiculo_id),
            "usuario_id": int(usuario_id)
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO GPS:", e, flush=True)
        return jsonify({"sucesso": False, "erro": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    

@app.get("/debug/gps")
def debug_gps():
    r = proteger_pagina()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        # veículos do usuário para popular o select
        cur.execute("""
            SELECT id, modelo, placa, cidade
            FROM veiculos
            WHERE usuario_id = %s
            ORDER BY modelo ASC, placa ASC
        """, (uid,))
        veiculos_rows = cur.fetchall()

        veiculos = []
        for row in veiculos_rows:
            veiculos.append({
                "id": int(row[0]),
                "modelo": row[1],
                "placa": row[2],
                "cidade": row[3]
            })

        # vínculos de rastreadores
        cur.execute("""
            SELECT
                r.id,
                r.imei,
                r.veiculo_id,
                r.ativo,
                r.criado_em,
                v.modelo,
                v.placa,
                v.cidade
            FROM rastreadores r
            INNER JOIN veiculos v
                ON v.id = r.veiculo_id
            WHERE r.usuario_id = %s
            ORDER BY r.id DESC
        """, (uid,))
        rastreadores_rows = cur.fetchall()

        rastreadores = []
        for row in rastreadores_rows:
            rastreadores.append({
                "id": int(row[0]),
                "imei": row[1],
                "veiculo_id": int(row[2]),
                "ativo": bool(row[3]),
                "criado_em": _formatar_data_label(row[4]) if row[4] else "",
                "modelo": row[5],
                "placa": row[6],
                "cidade": row[7]
            })

        # histórico gps
        cur.execute("""
            SELECT
                vl.latitude,
                vl.longitude,
                vl.velocidade_kmh,
                COALESCE(vl.endereco, ''),
                vl.recebido_em,
                COALESCE(v.modelo, 'Veículo'),
                COALESCE(v.placa, ''),
                COALESCE(r.imei, '')
            FROM veiculos_localizacao vl
            LEFT JOIN veiculos v
                ON v.id = vl.veiculo_id
            LEFT JOIN rastreadores r
                ON r.veiculo_id = vl.veiculo_id
               AND r.usuario_id = vl.usuario_id
               AND r.ativo = TRUE
            WHERE vl.usuario_id = %s
            ORDER BY vl.recebido_em DESC
            LIMIT 100
        """, (uid,))

        rows = cur.fetchall()

        dados = []
        for row in rows:
            latitude, longitude, velocidade_kmh, endereco, recebido_em, modelo, placa, imei = row

            dados.append({
                "latitude": float(latitude) if latitude is not None else None,
                "longitude": float(longitude) if longitude is not None else None,
                "velocidade_kmh": float(velocidade_kmh) if velocidade_kmh is not None else 0.0,
                "endereco": endereco or "",
                "recebido_em": _formatar_data_label(recebido_em) if recebido_em else "",
                "modelo": modelo or "Veículo",
                "placa": placa or "",
                "imei": imei or "",
            })

        return render_template(
            "debug_gps.html",
            dados=dados,
            veiculos=veiculos,
            rastreadores=rastreadores
        )

    except Exception as e:
        print("ERRO debug_gps:", e, flush=True)
        return f"Erro ao abrir debug GPS: {str(e)}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

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

@app.post("/api/colaboradores/<int:expediente_id>/upload-fotos-dano")
def api_upload_fotos_dano_saida(expediente_id):
    r = proteger_api()
    if r:
        return r

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id
            FROM expedientes
            WHERE id = %s
              AND usuario_id = %s
            LIMIT 1
        """, (expediente_id, usuario_id_atual()))

        row = cur.fetchone()
        if not row:
            return jsonify({
                "sucesso": False,
                "erro": "Expediente não encontrado"
            }), 404

        arquivos = []
        for chave in ["foto_dano_1", "foto_dano_2", "foto_dano_3"]:
            arquivo = request.files.get(chave)
            if arquivo and (arquivo.filename or "").strip():
                arquivos.append(arquivo)

        if not arquivos:
            return jsonify({
                "sucesso": False,
                "erro": "Envie ao menos uma foto"
            }), 400

        urls = []
        for indice, arquivo in enumerate(arquivos[:3], start=1):
            url = _upload_foto_dano_saida(expediente_id, indice, arquivo)
            if url:
                urls.append(url)

        while len(urls) < 3:
            urls.append("")

        cur.execute("""
            UPDATE expedientes
            SET
                foto_dano_saida_url_1 = %s,
                foto_dano_saida_url_2 = %s,
                foto_dano_saida_url_3 = %s
            WHERE id = %s
        """, (urls[0], urls[1], urls[2], expediente_id))

        conn.commit()

        return jsonify({
            "sucesso": True,
            "fotosDanoSaida": urls
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_upload_fotos_dano_saida:", e, flush=True)
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

    if not veiculo_id:
        return jsonify({
            "sucesso": False,
            "erro": "veiculo_id é obrigatório"
        }), 400

    if not foto:
        return jsonify({
            "sucesso": False,
            "erro": "foto é obrigatória"
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

        # fecha expediente antigo do mesmo colaborador
        cur.execute("""
            UPDATE expedientes
            SET
                horario_fim = CURRENT_TIMESTAMP,
                status = 'finalizado'
            WHERE colaborador_id = %s
              AND status = 'em_andamento'
        """, (motorista_id,))

        # fecha expediente antigo do mesmo veículo
        cur.execute("""
            UPDATE expedientes
            SET
                horario_fim = CURRENT_TIMESTAMP,
                status = 'finalizado'
            WHERE veiculo_id = %s
              AND status = 'em_andamento'
        """, (veiculo_id,))

        # encerra vínculos antigos do motorista
        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND ativo = TRUE
        """, (motorista_id,))

        # encerra vínculos antigos do veículo
        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE veiculo_id = %s
              AND ativo = TRUE
        """, (veiculo_id,))

        # cria vínculo novo
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

        # verifica se a coluna existe
        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'expedientes'
              AND column_name = 'foto_odometro_entrada_url'
            LIMIT 1
        """)
        tem_coluna_odometro = cur.fetchone() is not None

        if tem_coluna_odometro:
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
                json.dumps(checklist),
            ))
        else:
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
                json.dumps(checklist),
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
            "erro": f"Erro ao iniciar expediente: {str(e)}"
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
    foto = request.files.get("foto")

    checklist_raw = request.form.get("checklist")
    veiculo_danificado_raw = request.form.get("veiculo_danificado")
    observacao_dano = (request.form.get("observacao_dano") or "").strip()

    foto_dano_1 = request.files.get("foto_dano_1")
    foto_dano_2 = request.files.get("foto_dano_2")
    foto_dano_3 = request.files.get("foto_dano_3")

    if not foto:
        return jsonify({
            "sucesso": False,
            "erro": "foto é obrigatória"
        }), 400

    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        expediente_id_int = None

        if expediente_id:
            try:
                expediente_id_int = int(expediente_id)
            except (TypeError, ValueError):
                return jsonify({
                    "sucesso": False,
                    "erro": "expediente_id inválido"
                }), 400
        else:
            cur.execute("""
                SELECT id
                FROM expedientes
                WHERE colaborador_id = %s
                  AND status = 'em_andamento'
                ORDER BY horario_inicio DESC, id DESC
                LIMIT 1
            """, (motorista_id,))
            row = cur.fetchone()

            if not row:
                return jsonify({
                    "sucesso": False,
                    "erro": "Nenhum expediente em andamento encontrado para finalizar"
                }), 404

            expediente_id_int = int(row[0])

        cur.execute("""
            SELECT id, veiculo_id
            FROM expedientes
            WHERE id = %s
              AND colaborador_id = %s
              AND status = 'em_andamento'
            LIMIT 1
        """, (expediente_id_int, motorista_id))

        expediente_row = cur.fetchone()

        if not expediente_row:
            return jsonify({
                "sucesso": False,
                "erro": "Expediente não encontrado ou já finalizado"
            }), 404

        _, veiculo_id = expediente_row

        # =========================
        # CHECKLIST SAÍDA
        # =========================
        try:
            checklist_saida = _parse_checklist_json(checklist_raw)
        except ValueError as e:
            return jsonify({
                "sucesso": False,
                "erro": str(e)
            }), 400

        veiculo_danificado = str(veiculo_danificado_raw or "").strip().lower() == "true"

        # =========================
        # FOTO SAÍDA
        # =========================
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"saida/{motorista_id}_{timestamp}.jpg"

        s3.upload_fileobj(
            foto,
            R2_BUCKET_NAME,
            filename,
            ExtraArgs={"ContentType": foto.content_type or "image/jpeg"}
        )

        url_foto = montar_url_publica_r2(filename)

        # =========================
        # FOTOS DE DANO
        # =========================
        foto_dano_url_1 = ""
        foto_dano_url_2 = ""
        foto_dano_url_3 = ""

        if veiculo_danificado:
            if not foto_dano_1:
                return jsonify({
                    "sucesso": False,
                    "erro": "Ao marcar veículo danificado, a foto_dano_1 é obrigatória"
                }), 400

            foto_dano_url_1 = _upload_foto_dano_saida(expediente_id_int, 1, foto_dano_1)
            foto_dano_url_2 = _upload_foto_dano_saida(expediente_id_int, 2, foto_dano_2)
            foto_dano_url_3 = _upload_foto_dano_saida(expediente_id_int, 3, foto_dano_3)

        # =========================
        # UPDATE EXPEDIENTE
        # =========================
        cur.execute("""
            UPDATE expedientes
            SET
                foto_saida_url = %s,
                horario_fim = CURRENT_TIMESTAMP,
                checklist_saida = %s,
                veiculo_danificado_saida = %s,
                observacao_dano_saida = %s,
                foto_dano_saida_url_1 = %s,
                foto_dano_saida_url_2 = %s,
                foto_dano_saida_url_3 = %s,
                status = 'finalizado'
            WHERE id = %s
              AND colaborador_id = %s
        """, (
            url_foto,
            json.dumps(checklist_saida),
            veiculo_danificado,
            observacao_dano,
            foto_dano_url_1,
            foto_dano_url_2,
            foto_dano_url_3,
            expediente_id_int,
            motorista_id
        ))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({
                "sucesso": False,
                "erro": "Não foi possível finalizar o expediente"
            }), 400

        cur.execute("""
            UPDATE veiculos_uso
            SET ativo = FALSE,
                finalizado_em = CURRENT_TIMESTAMP
            WHERE motorista_id = %s
              AND veiculo_id = %s
              AND ativo = TRUE
        """, (motorista_id, veiculo_id))

        conn.commit()

        return jsonify({
            "sucesso": True,
            "expediente_id": expediente_id_int,
            "foto_url": url_foto,
            "veiculo_danificado": veiculo_danificado,
            "observacao_dano": observacao_dano,
            "foto_dano_1": foto_dano_url_1,
            "foto_dano_2": foto_dano_url_2,
            "foto_dano_3": foto_dano_url_3
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO finalizar expediente:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": f"Erro ao finalizar expediente: {str(e)}"
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


            
@app.get("/api/veiculos/<int:veiculo_id>/percurso")
def percurso_veiculo(veiculo_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()

    inicio_raw = (request.args.get("inicio") or "").strip()
    fim_raw = (request.args.get("fim") or "").strip()

    inicio_utc = _parse_datetime_local_para_utc(inicio_raw)
    fim_utc = _parse_datetime_local_para_utc(fim_raw)

    if not inicio_utc or not fim_utc:
        return jsonify({
            "sucesso": False,
            "erro": "inicio e fim são obrigatórios"
        }), 400

    if fim_utc < inicio_utc:
        return jsonify({
            "sucesso": False,
            "erro": "A data final não pode ser menor que a inicial"
        }), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1
            FROM veiculos
            WHERE id = %s
              AND usuario_id = %s
            LIMIT 1
        """, (veiculo_id, uid))

        if not cur.fetchone():
            return jsonify({
                "sucesso": False,
                "erro": "Veículo não encontrado"
            }), 404

        cur.execute("""
            SELECT
                latitude,
                longitude,
                velocidade_kmh,
                endereco,
                recebido_em
            FROM veiculos_localizacao
            WHERE veiculo_id = %s
              AND usuario_id = %s
              AND recebido_em BETWEEN %s AND %s
            ORDER BY recebido_em ASC
        """, (veiculo_id, uid, inicio_utc, fim_utc))

        pontos = [_normalizar_ponto_localizacao(r) for r in cur.fetchall()]
        resumo = _resumir_pontos_localizacao(pontos)

        pontos_saida = [
            {
                "lat": p["lat"],
                "lng": p["lng"],
                "velocidade": p["velocidade_bruta_kmh"] if p["velocidade_bruta_kmh"] is not None else 0,
                "endereco": p["endereco"],
                "data": p["recebido_em"].isoformat() if p["recebido_em"] else None
            }
            for p in pontos
        ]

        return jsonify({
            "sucesso": True,
            "pontos": pontos_saida,
            "resumo": {
                "distancia_total_m": resumo["distancia_total_m"],
                "distancia_total_km": resumo["distancia_total_km"],
                "tempo_total_segundos": resumo["tempo_total_segundos"],
                "velocidade_media_kmh": resumo["velocidade_media_kmh"],
                "velocidade_atual_kmh": resumo["velocidade_atual_kmh"],
                "status": resumo["status"],
                "pontos_validos": resumo["pontos_validos"],
                "ultimo_recebido_em": resumo["ultimo_recebido_em"].isoformat() if resumo["ultimo_recebido_em"] else None
            }
        }), 200

    except Exception as e:
        print("ERRO percurso_veiculo:", e, flush=True)
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
# API RASTREADORES (IMEI -> VEÍCULO)
# =========================
@app.get("/api/rastreadores")
def api_rastreadores_listar():
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
                r.id,
                r.imei,
                r.veiculo_id,
                r.usuario_id,
                r.ativo,
                r.criado_em,
                v.modelo,
                v.placa,
                v.cidade
            FROM rastreadores r
            INNER JOIN veiculos v
                ON v.id = r.veiculo_id
            WHERE r.usuario_id = %s
            ORDER BY r.id DESC
        """, (uid,))

        rows = cur.fetchall()

        data_out = []
        for row in rows:
            data_out.append({
                "id": int(row[0]),
                "imei": row[1],
                "veiculo_id": int(row[2]),
                "usuario_id": int(row[3]),
                "ativo": bool(row[4]),
                "criado_em": row[5].isoformat() if row[5] else None,
                "modelo": row[6],
                "placa": row[7],
                "cidade": row[8]
            })

        return jsonify({
            "sucesso": True,
            "rastreadores": data_out
        }), 200

    except Exception as e:
        print("ERRO api_rastreadores_listar:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.post("/api/rastreadores")
def api_rastreadores_salvar():
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    dados = request.get_json(silent=True) or {}

    imei = str(dados.get("imei") or "").strip()
    veiculo_id = dados.get("veiculo_id")
    ativo = bool(dados.get("ativo", True))

    if not imei:
        return jsonify({
            "sucesso": False,
            "erro": "IMEI é obrigatório"
        }), 400

    if not veiculo_id:
        return jsonify({
            "sucesso": False,
            "erro": "veiculo_id é obrigatório"
        }), 400

    # aceita só números no IMEI
    imei = re.sub(r"\D", "", imei)

    if len(imei) < 8:
        return jsonify({
            "sucesso": False,
            "erro": "IMEI inválido"
        }), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # garante que o veículo pertence ao usuário
        cur.execute("""
            SELECT id
            FROM veiculos
            WHERE id = %s
              AND usuario_id = %s
            LIMIT 1
        """, (int(veiculo_id), uid))

        if not cur.fetchone():
            return jsonify({
                "sucesso": False,
                "erro": "Veículo não encontrado"
            }), 404

        # se já existir o imei, atualiza o vínculo
        cur.execute("""
            INSERT INTO rastreadores (
                imei,
                veiculo_id,
                usuario_id,
                ativo
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (imei)
            DO UPDATE SET
                veiculo_id = EXCLUDED.veiculo_id,
                usuario_id = EXCLUDED.usuario_id,
                ativo = EXCLUDED.ativo
            RETURNING id
        """, (
            imei,
            int(veiculo_id),
            uid,
            ativo
        ))

        rastreador_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({
            "sucesso": True,
            "id": int(rastreador_id),
            "imei": imei
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_rastreadores_salvar:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.delete("/api/rastreadores/<int:rastreador_id>")
def api_rastreadores_excluir(rastreador_id):
    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM rastreadores
            WHERE id = %s
              AND usuario_id = %s
        """, (rastreador_id, uid))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({
                "sucesso": False,
                "erro": "Rastreador não encontrado"
            }), 404

        conn.commit()

        return jsonify({
            "sucesso": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO api_rastreadores_excluir:", e, flush=True)
        return jsonify({
            "sucesso": False,
            "erro": str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.get("/percurso/<int:veiculo_id>")
def pagina_percurso_veiculo(veiculo_id):
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
            WHERE id = %s
              AND usuario_id = %s
            LIMIT 1
        """, (veiculo_id, uid))

        row = cur.fetchone()
        if not row:
            return redirect(url_for("monitoramento"))

        return render_template(
            "percurso.html",
            veiculo_id=row[0],
            veiculo_modelo=row[1],
            veiculo_placa=row[2],
            veiculo_cidade=row[3]
        )

    except Exception as e:
        print("ERRO pagina_percurso_veiculo:", e, flush=True)
        return redirect(url_for("monitoramento"))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.post("/api/rastreamento/salvar")
def salvar_localizacao():
    r = proteger_api_mobile()
    if r:
        return r

    dados = request.get_json() or {}

    lat = dados.get("lat")
    lng = dados.get("lng")

    if lat is None or lng is None:
        return jsonify({"erro": "Lat/Lng obrigatórios"}), 400

    motorista_id = g.mobile_auth["motorista_id"]
    usuario_id = g.mobile_auth["usuario_id"]

    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        # pegar veículo em uso
        cur.execute("""
            SELECT veiculo_id
            FROM veiculos_uso
            WHERE motorista_id = %s
              AND ativo = TRUE
            LIMIT 1
        """, (motorista_id,))
        row = cur.fetchone()

        if not row:
            return jsonify({"erro": "Nenhum veículo em uso"}), 400

        veiculo_id = row[0]

        # pegar último ponto
        cur.execute("""
            SELECT latitude, longitude, recebido_em
            FROM veiculos_localizacao
            WHERE veiculo_id = %s
            ORDER BY recebido_em DESC
            LIMIT 1
        """, (veiculo_id,))
        ultimo = cur.fetchone()

        velocidade = 0

        if ultimo:
            lat1, lon1, t1 = ultimo
            lat2, lon2 = float(lat), float(lng)
            t2 = datetime.utcnow()

            distancia = calcular_distancia(lat1, lon1, lat2, lon2)
            tempo = (t2 - t1).total_seconds()

            if tempo > 0:
                velocidade = (distancia / 1000) / (tempo / 3600)

        # salvar
        cur.execute("""
            INSERT INTO veiculos_localizacao (
                usuario_id, veiculo_id, latitude, longitude, velocidade_kmh
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id, veiculo_id, lat, lng, velocidade))

        conn.commit()

        return jsonify({"sucesso": True})

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO rastreamento:", e)
        return jsonify({"erro": str(e)}), 500

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
# HELPERS RASTREAMENTO REAL
# =========================
TZ_BR = ZoneInfo("America/Sao_Paulo")
TZ_UTC = ZoneInfo("UTC")

STATUS_MOVING_KMH = 5.0
STATUS_OFFLINE_MINUTOS = 10
MAX_SEGMENTO_MINUTOS = 120
MAX_SEGMENTO_DISTANCIA_METROS = 200000  # 200 km


def _agora_utc():
    return datetime.now(TZ_UTC)


def _garantir_dt_utc(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ_UTC)
    return dt.astimezone(TZ_UTC)


def _formatar_data_label(dt):
    if not dt:
        return "Sem atualização"
    try:
        dt = _garantir_dt_utc(dt).astimezone(TZ_BR)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        try:
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return "Sem atualização"


def _parse_datetime_local_para_utc(valor):
    """
    Recebe string do input datetime-local (sem timezone), assume horário do Brasil
    e devolve datetime UTC para consultar no banco.
    """
    texto = str(valor or "").strip()
    if not texto:
        return None

    formatos = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formatos:
        try:
            dt_local = datetime.strptime(texto, fmt).replace(tzinfo=TZ_BR)
            return dt_local.astimezone(TZ_UTC)
        except Exception:
            pass

    return None


def _normalizar_ponto_localizacao(row):
    """
    row esperado:
    (latitude, longitude, velocidade_kmh, endereco, recebido_em)
    """
    lat = float(row[0]) if row[0] is not None else None
    lng = float(row[1]) if row[1] is not None else None
    velocidade_bruta = float(row[2]) if row[2] is not None else None
    endereco = row[3] if len(row) > 3 else None
    recebido_em = _garantir_dt_utc(row[4]) if len(row) > 4 else None

    return {
        "lat": lat,
        "lng": lng,
        "velocidade_bruta_kmh": velocidade_bruta,
        "endereco": endereco,
        "recebido_em": recebido_em,
        "data": recebido_em.isoformat() if recebido_em else None,
    }


def _resumir_pontos_localizacao(pontos):
    """
    Calcula:
    - distância total real
    - tempo total válido
    - velocidade média real
    - velocidade do último trecho válido
    - status real
    """
    if not pontos:
        return {
            "distancia_total_m": 0.0,
            "distancia_total_km": 0.0,
            "tempo_total_segundos": 0.0,
            "velocidade_media_kmh": 0.0,
            "velocidade_atual_kmh": 0.0,
            "ultimo_trecho_kmh": 0.0,
            "status": "offline",
            "pontos_validos": 0,
            "ultimo_recebido_em": None,
        }

    pontos_ordenados = sorted(
        pontos,
        key=lambda p: p["recebido_em"] or datetime.min.replace(tzinfo=TZ_UTC)
    )

    distancia_total_m = 0.0
    tempo_total_segundos = 0.0
    ultimo_trecho_kmh = 0.0
    pontos_validos = 0

    for i in range(1, len(pontos_ordenados)):
        a = pontos_ordenados[i - 1]
        b = pontos_ordenados[i]

        if (
            a["lat"] is None or a["lng"] is None or
            b["lat"] is None or b["lng"] is None or
            not a["recebido_em"] or not b["recebido_em"]
        ):
            continue

        delta_s = (b["recebido_em"] - a["recebido_em"]).total_seconds()
        if delta_s <= 0:
            continue

        distancia_m = calcular_distancia(a["lat"], a["lng"], b["lat"], b["lng"])

        # evita trechos absurdos por salto, queda de sinal ou lacunas muito grandes
        if delta_s > (MAX_SEGMENTO_MINUTOS * 60):
            continue
        if distancia_m > MAX_SEGMENTO_DISTANCIA_METROS:
            continue

        velocidade_trecho_kmh = (distancia_m / 1000.0) / (delta_s / 3600.0)

        distancia_total_m += distancia_m
        tempo_total_segundos += delta_s
        ultimo_trecho_kmh = velocidade_trecho_kmh
        pontos_validos += 1

    velocidade_media_kmh = 0.0
    if tempo_total_segundos > 0:
        velocidade_media_kmh = (distancia_total_m / 1000.0) / (tempo_total_segundos / 3600.0)

    ultimo_recebido_em = pontos_ordenados[-1]["recebido_em"]
    status = "offline"

    if ultimo_recebido_em:
        minutos_sem_atualizacao = (_agora_utc() - ultimo_recebido_em).total_seconds() / 60.0

        if minutos_sem_atualizacao > STATUS_OFFLINE_MINUTOS:
            status = "offline"
        elif ultimo_trecho_kmh >= STATUS_MOVING_KMH:
            status = "moving"
        else:
            status = "stopped"

    return {
        "distancia_total_m": round(distancia_total_m, 2),
        "distancia_total_km": round(distancia_total_m / 1000.0, 3),
        "tempo_total_segundos": int(tempo_total_segundos),
        "velocidade_media_kmh": round(velocidade_media_kmh, 2),
        "velocidade_atual_kmh": round(ultimo_trecho_kmh, 2),
        "ultimo_trecho_kmh": round(ultimo_trecho_kmh, 2),
        "status": status,
        "pontos_validos": pontos_validos,
        "ultimo_recebido_em": ultimo_recebido_em,
    }


def _buscar_pontos_veiculo(cur, usuario_id, veiculo_id, limite=200, inicio_utc=None, fim_utc=None):
    sql = """
        SELECT
            latitude,
            longitude,
            velocidade_kmh,
            endereco,
            recebido_em
        FROM veiculos_localizacao
        WHERE veiculo_id = %s
          AND usuario_id = %s
    """
    params = [veiculo_id, usuario_id]

    if inicio_utc is not None:
        sql += " AND recebido_em >= %s"
        params.append(inicio_utc)

    if fim_utc is not None:
        sql += " AND recebido_em <= %s"
        params.append(fim_utc)

    sql += " ORDER BY recebido_em ASC"

    if limite:
        sql += " LIMIT %s"
        params.append(limite)

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    return [_normalizar_ponto_localizacao(row) for row in rows]

            # =========================
# AJUSTE HELPERS
# =========================
def _combinar_data_com_hora(base_dt, hora_str):
    """
    Recebe uma base datetime e uma hora no formato HH:MM
    e devolve um datetime combinando a data da base com a nova hora.
    """
    if hora_str is None:
        return None

    texto = str(hora_str).strip()
    if not texto:
        return None

    try:
        hora_obj = datetime.strptime(texto, "%H:%M").time()
    except ValueError:
        raise ValueError("Horário inválido. Use o formato HH:MM.")

    base = base_dt if isinstance(base_dt, datetime) else datetime.utcnow()
    return datetime.combine(base.date(), hora_obj)
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