from flask import Flask, request, jsonify, session
from flask_cors import CORS
import psycopg2
import os
import re
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
CORS(app, supports_credentials=True)


# ==========================================================
# 🔐 AUTH HELPERS
# ==========================================================

def usuario_id_atual():
    return session.get("usuario_id")


def proteger_api():
    if not usuario_id_atual():
        return jsonify({"sucesso": False, "erro": "Não autenticado"}), 401
    return None


# ==========================================================
# 🗄️ DATABASE
# ==========================================================

def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        port=os.environ.get("DB_PORT", 5432)
    )


# ==========================================================
# 🔧 FUNÇÕES AUXILIARES
# ==========================================================

def parse_odometro(valor):
    if not valor:
        return None
    digits = re.sub(r"[^\d]", "", str(valor))
    return int(digits) if digits else None


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def month_bounds(d: date):
    start = date(d.year, d.month, 1)
    if d.month == 12:
        end = date(d.year + 1, 1, 1)
    else:
        end = date(d.year, d.month + 1, 1)
    return start, end


def prev_month(d: date):
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


# ==========================================================
# ⛽ ABASTECIMENTOS
# ==========================================================

@app.route("/api/abastecimentos", methods=["GET", "POST"])
def api_abastecimentos():

    r = proteger_api()
    if r:
        return r

    uid = usuario_id_atual()
    conn = cur = None

    try:
        conn = get_db()
        cur = conn.cursor()

        # ================= GET =================
        if request.method == "GET":

            cur.execute("""
                SELECT id, data, hora,
                       motorista_id, veiculo_id, posto_id,
                       combustivel_tipo,
                       litros, preco_total, preco_unitario,
                       odometro, pago,
                       COALESCE(obs,''), COALESCE(comprovante_url,'')
                FROM abastecimentos
                WHERE usuario_id = %s
                ORDER BY data DESC, hora DESC, id DESC
            """, (uid,))

            rows = cur.fetchall()
            data = []

            for row in rows:
                data.append({
                    "id": row[0],
                    "tipo": "abastecimento",
                    "data": row[1].isoformat() if row[1] else "",
                    "hora": row[2].strftime("%H:%M") if row[2] else "",
                    "motoristaId": row[3],
                    "veiculoId": row[4],
                    "postoId": row[5],
                    "combustivel": row[6],
                    "litros": safe_float(row[7]),
                    "preco": safe_float(row[8]),
                    "precoUnitario": safe_float(row[9]),
                    "odometro": str(row[10]) if row[10] else "",
                    "pago": bool(row[11]),
                    "obs": row[12],
                    "comprovante": row[13]
                })

            return jsonify(data), 200

        # ================= POST =================
        dados = request.get_json()

        data_ = dados.get("data")
        hora = dados.get("hora")
        motorista_id = dados.get("motorista_id")
        veiculo_id = dados.get("veiculo_id")
        posto_id = dados.get("posto_id")
        combustivel = dados.get("combustivel")

        litros = safe_float(dados.get("litros"))
        preco_total = safe_float(dados.get("preco_total"))
        preco_unitario = safe_float(dados.get("preco_unitario"))
        odometro = parse_odometro(dados.get("odometro"))

        pago = bool(dados.get("pago", False))
        obs = dados.get("obs", "")
        comprovante = dados.get("comprovante", "")

        if not all([data_, hora, motorista_id, veiculo_id, posto_id, combustivel]):
            return jsonify({"sucesso": False, "erro": "Campos obrigatórios faltando"}), 400

        # valida pertencimento
        cur.execute("SELECT 1 FROM motoristas WHERE id=%s AND usuario_id=%s", (motorista_id, uid))
        if not cur.fetchone():
            return jsonify({"erro": "Motorista inválido"}), 400

        cur.execute("SELECT 1 FROM veiculos WHERE id=%s AND usuario_id=%s", (veiculo_id, uid))
        if not cur.fetchone():
            return jsonify({"erro": "Veículo inválido"}), 400

        cur.execute("SELECT 1 FROM postos WHERE id=%s AND usuario_id=%s", (posto_id, uid))
        if not cur.fetchone():
            return jsonify({"erro": "Posto inválido"}), 400

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
            odometro, pago, obs, comprovante
        ))

        new_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({"sucesso": True, "id": new_id}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO ABASTECIMENTO:", e)
        return jsonify({"sucesso": False, "erro": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# ==========================================================
# 🔧 MANUTENÇÕES
# ==========================================================

@app.route("/api/manutencoes", methods=["GET", "POST"])
def api_manutencoes():

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
                SELECT id, data, hora,
                       motorista_id, veiculo_id,
                       valor, COALESCE(prestador,''),
                       pago, COALESCE(obs,''), COALESCE(comprovante_url,'')
                FROM manutencoes
                WHERE usuario_id = %s
                ORDER BY data DESC, hora DESC, id DESC
            """, (uid,))

            rows = cur.fetchall()
            data = []

            for row in rows:
                data.append({
                    "id": row[0],
                    "tipo": "manutencao",
                    "data": row[1].isoformat() if row[1] else "",
                    "hora": row[2].strftime("%H:%M") if row[2] else "",
                    "motoristaId": row[3],
                    "veiculoId": row[4],
                    "valor": safe_float(row[5]),
                    "prestador": row[6],
                    "pago": bool(row[7]),
                    "obs": row[8],
                    "comprovante": row[9]
                })

            return jsonify(data), 200

        dados = request.get_json()

        data_ = dados.get("data")
        hora = dados.get("hora")
        motorista_id = dados.get("motorista_id")
        veiculo_id = dados.get("veiculo_id")
        valor = safe_float(dados.get("valor"))
        prestador = dados.get("prestador", "").strip()
        pago = bool(dados.get("pago", False))
        obs = dados.get("obs", "")
        comprovante = dados.get("comprovante", "")

        if not all([data_, hora, motorista_id, veiculo_id, prestador]):
            return jsonify({"erro": "Campos obrigatórios faltando"}), 400

        cur.execute("""
            INSERT INTO manutencoes (
                usuario_id, data, hora,
                motorista_id, veiculo_id,
                valor, prestador, pago, obs, comprovante_url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            uid, data_, hora,
            motorista_id, veiculo_id,
            valor, prestador, pago, obs, comprovante
        ))

        conn.commit()
        return jsonify({"sucesso": True}), 201

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO MANUTENÇÃO:", e)
        return jsonify({"erro": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# ==========================================================
# 📊 DASHBOARD SIMPLIFICADO (funcional e estável)
# ==========================================================

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

        hoje = date.today()
        inicio, fim = month_bounds(hoje)

        cur.execute("""
            SELECT COALESCE(SUM(preco_total),0)
            FROM abastecimentos
            WHERE usuario_id=%s AND data >= %s AND data < %s
        """, (uid, inicio, fim))
        total_abastec = safe_float(cur.fetchone()[0])

        cur.execute("""
            SELECT COALESCE(SUM(valor),0)
            FROM manutencoes
            WHERE usuario_id=%s AND data >= %s AND data < %s
        """, (uid, inicio, fim))
        total_manut = safe_float(cur.fetchone()[0])

        return jsonify({
            "total_mensal": round(total_abastec + total_manut, 2),
            "total_abastecimentos": round(total_abastec, 2),
            "total_manutencoes": round(total_manut, 2)
        })

    except Exception as e:
        print("ERRO DASHBOARD:", e)
        return jsonify({"erro": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# ==========================================================
# 🚀 RUN
# ==========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
