import os
import re
from datetime import timedelta, date, datetime

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash
from psycopg2 import errors

from conexao import get_db

print(">>> APP.PY CARREGADO:", __file__, flush=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

app.config["SECRET_KEY"] = "gorota-dev"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False  # localhost sem https
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)  # 1 ano


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


def _posto_completo_por_id(cur, usuario_id: int, posto_id: int):
    cur.execute("""
        SELECT
            p.id, p.nome, p.endereco,
            pc.tipo, pc.preco
        FROM postos p
        LEFT JOIN posto_combustiveis pc ON pc.posto_id = p.id
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


# =========================
# ✅ CORREÇÃO DO ODÔMETRO (segura)
# =========================
def _odometro_to_int(odometro):
    """
    Normaliza odômetro para KM inteiro.

    Regras:
    - "000580" -> 580
    - "580.00"/"580,00" -> 580  (evita virar 58000)
    - Mantém INT puro como INT (NÃO divide por 100 automaticamente!)
      => correção do bug x100 é feita na hora de calcular o TRECHO (km),
         com heurística segura (km > 5000 e múltiplo de 100).
    """
    if odometro is None:
        return None

    # número vindo do banco
    if isinstance(odometro, int):
        return odometro

    if isinstance(odometro, float):
        try:
            return int(round(odometro))
        except Exception:
            return None

    s = str(odometro).strip()
    if not s:
        return None

    # caso "580.00" / "580,00"
    m = re.match(r"^\s*(\d+)\s*([.,])\s*(\d{1,2})\s*$", s)
    if m:
        inteiro = m.group(1)
        dec = m.group(3).ljust(2, "0")
        try:
            val = float(f"{inteiro}.{dec}")
            return int(round(val))
        except Exception:
            return None

    # fallback: só dígitos
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return None

    try:
        return int(digits)
    except Exception:
        return None


def _odometro_to_str6(odometro):
    """
    Mostra com zeros à esquerda até 6 dígitos (se <= 6).
    """
    n = _odometro_to_int(odometro)
    if n is None:
        return ""
    s = str(n)
    return s.zfill(6) if len(s) <= 6 else s


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
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        modo = "form"
    else:
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
            data_out = [{"id": i, "modelo": m, "placa": p, "renavam": rnv, "cidade": c} for (i, m, p, rnv, c) in rows]
            return jsonify(data_out), 200
        except Exception as e:
            print("ERRO api_veiculos GET:", e, flush=True)
            return jsonify({"sucesso": False, "erro": str(e)}), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    dados = request.get_json(silent=True) or {}
    modelo = (dados.get("modelo") or "").strip()
    placa = (dados.get("placa") or "").strip().upper()
    cidade = (dados.get("cidade") or "").strip()
    renavam = (dados.get("renavam") or "").strip()

    if not modelo or not placa or not cidade:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios: modelo, placa, cidade"}), 400

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
            modelo = (dados.get("modelo") or "").strip()
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
                SELECT id, nome, cpf, nascimento, endereco
                FROM motoristas
                WHERE usuario_id = %s
                ORDER BY id DESC
            """, (uid,))
            rows = cur.fetchall()

            data_out = []
            for (i, nome, cpf, nasc, end) in rows:
                data_out.append({
                    "id": i,
                    "nome": nome,
                    "cpf": cpf,
                    "nascimento": (nasc.isoformat() if nasc else ""),
                    "endereco": end,
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

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    nascimento = (dados.get("nascimento") or "").strip()
    endereco = (dados.get("endereco") or "").strip()

    if not nome or not cpf or not endereco:
        return jsonify({"sucesso": False, "erro": "Campos obrigatórios: nome, cpf, endereco"}), 400

    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO motoristas (usuario_id, nome, cpf, nascimento, endereco)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (uid, nome, cpf, nascimento if nascimento else None, endereco))
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
                SELECT id, nome, cpf, nascimento, endereco
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
                "endereco": row[4]
            }), 200

        if request.method == "PUT":
            dados = request.get_json(silent=True) or {}
            nome = (dados.get("nome") or "").strip()
            cpf = (dados.get("cpf") or "").strip()
            nascimento = (dados.get("nascimento") or "").strip()
            endereco = (dados.get("endereco") or "").strip()

            if not nome or not cpf or not endereco:
                return jsonify({"sucesso": False, "erro": "Campos obrigatórios"}), 400

            cur.execute("""
                UPDATE motoristas
                SET nome = %s,
                    cpf = %s,
                    nascimento = %s,
                    endereco = %s
                WHERE id = %s AND usuario_id = %s
            """, (
                nome,
                cpf,
                nascimento if nascimento else None,
                endereco,
                motorista_id,
                uid
            ))

            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"sucesso": False, "erro": "Motorista não encontrado"}), 404

            conn.commit()
            return jsonify({"sucesso": True}), 200

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
            cur.execute("""
                SELECT
                    p.id, p.nome, p.endereco,
                    pc.tipo, pc.preco
                FROM postos p
                LEFT JOIN posto_combustiveis pc ON pc.posto_id = p.id
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

        cur.execute("""
            INSERT INTO posto_combustiveis (posto_id, tipo, preco)
            VALUES
                (%s, %s, %s),
                (%s, %s, %s),
                (%s, %s, %s)
        """, (
            posto_id, "gasolina", gasolina,
            posto_id, "etanol", etanol,
            posto_id, "diesel", diesel
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

            cur.execute("""
                DELETE FROM posto_combustiveis
                WHERE posto_id = %s AND tipo IN ('gasolina','etanol','diesel')
            """, (posto_id,))

            cur.execute("""
                INSERT INTO posto_combustiveis (posto_id, tipo, preco)
                VALUES
                    (%s, %s, %s),
                    (%s, %s, %s),
                    (%s, %s, %s)
            """, (
                posto_id, "gasolina", gasolina,
                posto_id, "etanol", etanol,
                posto_id, "diesel", diesel
            ))

            conn.commit()
            return jsonify({"sucesso": True}), 200

        cur.execute("DELETE FROM posto_combustiveis WHERE posto_id = %s", (posto_id,))
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
# ✅ API - CATÁLOGO PARA ABASTECIMENTO
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

        cur.execute("""
            SELECT id, nome
            FROM motoristas
            WHERE usuario_id = %s
            ORDER BY id DESC
        """, (uid,))
        motoristas = [{"id": i, "nome": n} for (i, n) in cur.fetchall()]

        cur.execute("""
            SELECT id, placa, modelo
            FROM veiculos
            WHERE usuario_id = %s
            ORDER BY id DESC
        """, (uid,))
        veiculos = [{"id": i, "placa": p, "modelo": m} for (i, p, m) in cur.fetchall()]

        cur.execute("""
            SELECT
                p.id, p.nome, p.endereco,
                pc.tipo, pc.preco
            FROM postos p
            LEFT JOIN posto_combustiveis pc ON pc.posto_id = p.id
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
                    "odometro": _odometro_to_str6(odometro),
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
                "odometro": _odometro_to_str6(odometro),
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
                "odometro": _odometro_to_str6(odometro),
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

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
# ✅✅✅ NOVA LÓGICA CORRETA (EXATAMENTE COMO VOCÊ PEDIU)
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

        # abastecimentos
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
                "odometro": _odometro_to_int(odometro),       # usado pra calcular
                "odometro_str": _odometro_to_str6(odometro),  # exibição
                "pago": bool(pago),
                "obs": obs,
                "comprovante": comprovante_url
            })

        # manutencoes
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
                "valor": float(valor) if valor is not None else 0.0,
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

        # ✅ trechos corretos
        trechos_mes = _compute_trechos_por_veiculo(abastec_mes)
        trechos_prev = _compute_trechos_por_veiculo(abastec_prev)

        # ✅ KM rodados no mês = soma dos trechos
        km_mes = sum(t["km"] for t in trechos_mes)
        km_prev = sum(t["km"] for t in trechos_prev)

        # ✅ litros válidos (somente abastecimentos que entraram nos trechos)
        litros_mes_valid = sum(t["litros"] for t in trechos_mes)
        litros_prev_valid = sum(t["litros"] for t in trechos_prev)

        # ✅ custo válido (somente abastecimentos que entraram nos trechos)
        custo_mes_valid = sum(t["custo"] for t in trechos_mes)
        custo_prev_valid = sum(t["custo"] for t in trechos_prev)

        # ✅ MÉDIAS GERAIS (do jeito certo: total/total)
        consumo_l_km = (litros_mes_valid / km_mes) if km_mes > 0 else 0.0
        consumo_prev = (litros_prev_valid / km_prev) if km_prev > 0 else 0.0

        custo_r_km = (custo_mes_valid / km_mes) if km_mes > 0 else 0.0
        custo_prev = (custo_prev_valid / km_prev) if km_prev > 0 else 0.0

        # total mensal geral (mantém seu comportamento: abastec + manut)
        total_abastec_mes = sum(a["preco"] for a in abastec_mes)
        total_abastec_prev = sum(a["preco"] for a in abastec_prev)

        total_manut_mes = sum(m["valor"] for m in manuts_mes)
        total_manut_prev = sum(m["valor"] for m in manuts_prev)

        total_mes = total_abastec_mes + total_manut_mes
        total_prev = total_abastec_prev + total_manut_prev

        nao_pago_mes = (
            sum(a["preco"] for a in abastec_mes if not a["pago"]) +
            sum(m["valor"] for m in manuts_mes if not m["pago"])
        )
        ja_pago_mes = (
            sum(a["preco"] for a in abastec_mes if a["pago"]) +
            sum(m["valor"] for m in manuts_mes if m["pago"])
        )

        litros_mes_total = sum(a["litros"] for a in abastec_mes)

        qtd_abastec_mes = len(abastec_mes)
        qtd_manut_mes = len(manuts_mes)

        count_por_veic = {}
        for a in abastec_mes:
            count_por_veic[a["veiculoId"]] = count_por_veic.get(a["veiculoId"], 0) + 1

        top_abastec = sorted(
            [{"veiculoId": k, "qtd": v} for k, v in count_por_veic.items()],
            key=lambda x: x["qtd"],
            reverse=True
        )[:3]

        # top piores custo/km (por trechos)
        custo_km_por_veic = {}
        km_por_veic = {}
        custo_por_veic = {}
        for t in trechos_mes:
            vid = t["veiculoId"]
            km_por_veic[vid] = km_por_veic.get(vid, 0) + t["km"]
            custo_por_veic[vid] = custo_por_veic.get(vid, 0.0) + t["custo"]

        for vid in km_por_veic:
            kmv = km_por_veic.get(vid, 0)
            cv = custo_por_veic.get(vid, 0.0)
            custo_km_por_veic[vid] = (cv / kmv) if kmv > 0 else 0.0

        top_piores = sorted(
            [{
                "veiculoId": vid,
                "custo_km": custo_km_por_veic[vid],
                "km": km_por_veic.get(vid, 0),
                "custo": custo_por_veic.get(vid, 0.0)
            } for vid in custo_km_por_veic],
            key=lambda x: x["custo_km"],
            reverse=True
        )[:3]

        # resumo por veiculo (tabela de baixo)
        resumo_veiculos = []
        veic_ids = set([a["veiculoId"] for a in abastec_mes] + [m["veiculoId"] for m in manuts_mes])

        for vid in veic_ids:
            ab_v = [a for a in abastec_mes if a["veiculoId"] == vid]
            ma_v = [m for m in manuts_mes if m["veiculoId"] == vid]
            tre_v = [t for t in trechos_mes if t["veiculoId"] == vid]

            kmv = sum(t["km"] for t in tre_v)
            litv_valid = sum(t["litros"] for t in tre_v)
            custv_valid = sum(t["custo"] for t in tre_v)

            cust_total = sum(a["preco"] for a in ab_v) + sum(m["valor"] for m in ma_v)
            litros_total = sum(a["litros"] for a in ab_v)

            resumo_veiculos.append({
                "veiculoId": vid,
                "qtd_abastec": len(ab_v),
                "qtd_manut": len(ma_v),
                "km": kmv,
                "litros_valid": litv_valid,
                "litros_total": litros_total,
                "custo_valid": custv_valid,
                "custo_total": cust_total,
                "consumo_l_km": (litv_valid / kmv) if kmv > 0 else 0.0,
                "custo_km": (custv_valid / kmv) if kmv > 0 else 0.0,
            })

        resumo_motoristas = []
        mot_ids = set([a["motoristaId"] for a in abastec_mes] + [m["motoristaId"] for m in manuts_mes])

        for mid in mot_ids:
            ab_m = [a for a in abastec_mes if a["motoristaId"] == mid]
            ma_m = [m for m in manuts_mes if m["motoristaId"] == mid]
            tre_m = [t for t in trechos_mes if t["motoristaId"] == mid]

            kmx = sum(t["km"] for t in tre_m)
            litx_valid = sum(t["litros"] for t in tre_m)
            custx_valid = sum(t["custo"] for t in tre_m)

            cust_total = sum(a["preco"] for a in ab_m) + sum(m["valor"] for m in ma_m)
            litros_total = sum(a["litros"] for a in ab_m)

            resumo_motoristas.append({
                "motoristaId": mid,
                "qtd_abastec": len(ab_m),
                "qtd_manut": len(ma_m),
                "km": kmx,
                "litros_valid": litx_valid,
                "litros_total": litros_total,
                "custo_valid": custx_valid,
                "custo_total": cust_total,
                "consumo_l_km": (litx_valid / kmx) if kmx > 0 else 0.0,
                "custo_km": (custx_valid / kmx) if kmx > 0 else 0.0,
            })

        resumo_veiculos.sort(key=lambda x: x["custo_total"], reverse=True)
        resumo_motoristas.sort(key=lambda x: x["custo_total"], reverse=True)

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
                "litros_mes": _format_money(litros_mes_total),
                "qtd_abastec_mes": int(qtd_abastec_mes),
                "qtd_manut_mes": int(qtd_manut_mes),
            },
            "top3_abastecimentos": top_abastec,
            "top3_piores_custo_km": top_piores,
            "resumo_veiculos": resumo_veiculos,
            "resumo_motoristas": resumo_motoristas,
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
