import socket
import threading
import re
import binascii
from datetime import datetime

from conexao import get_db

HOST = "0.0.0.0"
PORT = 5023
BUFFER_SIZE = 4096
RAW_LOG_FILE = "tcp_raw.log"


def log_raw(msg: str):
    try:
        with open(RAW_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {msg}\n")
    except Exception as e:
        print("ERRO log_raw:", e, flush=True)


# =========================
# 🔥 NOVO: DECODIFICADOR GT06
# =========================
def decode_gt06(data: bytes):
    try:
        hex_data = binascii.hexlify(data).decode()

        if len(hex_data) < 20:
            return None

        if not (hex_data.startswith("7878") or hex_data.startswith("7979")):
            return None

        protocol = hex_data[6:8]

        # LOGIN (IMEI)
        if protocol == "01":
            imei_hex = hex_data[8:24]
            imei = str(int(imei_hex))
            return {"imei": imei}

        # LOCALIZAÇÃO
        if protocol in ["12", "22"]:
            lat_hex = hex_data[16:24]
            lng_hex = hex_data[24:32]

            lat = int(lat_hex, 16) / 1800000
            lng = int(lng_hex, 16) / 1800000

            return {
                "latitude": lat,
                "longitude": lng
            }

        return None

    except Exception as e:
        print("ERRO decode_gt06:", e, flush=True)
        return None


def buscar_vinculo_rastreador(imei: str):
    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                r.usuario_id,
                r.veiculo_id,
                r.ativo
            FROM rastreadores r
            WHERE r.imei = %s
            LIMIT 1
        """, (imei,))

        row = cur.fetchone()
        if not row:
            return None

        usuario_id, veiculo_id, ativo = row
        if not ativo:
            return None

        return {
            "usuario_id": int(usuario_id),
            "veiculo_id": int(veiculo_id),
            "ativo": bool(ativo)
        }

    except Exception as e:
        print("ERRO buscar_vinculo_rastreador:", e, flush=True)
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def salvar_localizacao(usuario_id, veiculo_id, latitude, longitude, velocidade_kmh=None, endereco=None):
    conn = cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

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
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            int(usuario_id),
            int(veiculo_id),
            float(latitude),
            float(longitude),
            float(velocidade_kmh) if velocidade_kmh is not None else None,
            endereco
        ))

        conn.commit()

        print(
            f"LOCALIZAÇÃO SALVA | usuario_id={usuario_id} | veiculo_id={veiculo_id} | "
            f"lat={latitude} | lng={longitude} | vel={velocidade_kmh}",
            flush=True
        )

    except Exception as e:
        if conn:
            conn.rollback()
        print("ERRO salvar_localizacao:", e, flush=True)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def extrair_imei(texto: str):
    if not texto:
        return None

    m = re.search(r'IMEI\s*[:=]\s*([0-9]{10,20})', texto, re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r'\b([0-9]{14,20})\b', texto)
    if m:
        return m.group(1)

    return None


def extrair_lat_lng_vel(texto: str):
    if not texto:
        return None, None, None

    lat = None
    lng = None
    vel = None

    lat_match = re.search(r'(?:LAT|LATITUDE)\s*[:=]\s*(-?\d+(?:\.\d+)?)', texto, re.IGNORECASE)
    lng_match = re.search(r'(?:LNG|LON|LONG|LONGITUDE)\s*[:=]\s*(-?\d+(?:\.\d+)?)', texto, re.IGNORECASE)
    vel_match = re.search(r'(?:SPD|SPEED|VEL|VELOCIDADE)\s*[:=]\s*(-?\d+(?:\.\d+)?)', texto, re.IGNORECASE)

    if lat_match:
        lat = float(lat_match.group(1))
    if lng_match:
        lng = float(lng_match.group(1))
    if vel_match:
        vel = float(vel_match.group(1))

    if lat is None or lng is None:
        return None, None, None

    return lat, lng, vel


def parsear_pacote_generico(texto: str):
    imei = extrair_imei(texto)
    lat, lng, vel = extrair_lat_lng_vel(texto)

    if not imei:
        return None

    return {
        "imei": imei,
        "latitude": lat,
        "longitude": lng,
        "velocidade_kmh": vel
    }


def processar_pacote_texto(texto: str, addr):
    log_raw(f"{addr} -> TEXTO -> {texto}")

    pacote = parsear_pacote_generico(texto)

    if not pacote:
        print(f"PACOTE TEXTO SEM PARSER | origem={addr}", flush=True)
        return

    vinculo = buscar_vinculo_rastreador(pacote["imei"])
    if not vinculo:
        return

    if pacote["latitude"] is None:
        return

    salvar_localizacao(
        usuario_id=vinculo["usuario_id"],
        veiculo_id=vinculo["veiculo_id"],
        latitude=pacote["latitude"],
        longitude=pacote["longitude"],
        velocidade_kmh=pacote["velocidade_kmh"]
    )


# =========================
# 🔥 BINÁRIO COM ESTADO (IMEI)
# =========================
def processar_pacote_binario(data: bytes, addr, estado):
    hex_data = binascii.hexlify(data).decode()
    log_raw(f"{addr} -> HEX -> {hex_data}")

    print(f"BINÁRIO HEX: {hex_data}", flush=True)

    decoded = decode_gt06(data)

    if not decoded:
        return

    if "imei" in decoded:
        estado["imei"] = decoded["imei"]
        print(f"IMEI CAPTURADO: {decoded['imei']}", flush=True)
        return

    if "latitude" in decoded and estado.get("imei"):
        vinculo = buscar_vinculo_rastreador(estado["imei"])
        if not vinculo:
            return

        salvar_localizacao(
            usuario_id=vinculo["usuario_id"],
            veiculo_id=vinculo["veiculo_id"],
            latitude=decoded["latitude"],
            longitude=decoded["longitude"]
        )


def responder_ack(conn):
    try:
        conn.sendall(b"\x78\x78\x05\x01\x00\x01\xd9\xdc")
    except:
        pass


def handle_client(conn, addr):
    print(f"NOVA CONEXÃO TCP: {addr}", flush=True)

    estado = {"imei": None}

    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break

            try:
                texto = data.decode("utf-8", errors="ignore").strip()
            except:
                texto = ""

            if texto and any(c.isalnum() for c in texto):
                processar_pacote_texto(texto, addr)
            else:
                processar_pacote_binario(data, addr, estado)

            responder_ack(conn)

    except Exception as e:
        print("ERRO:", e, flush=True)

    finally:
        conn.close()


def start_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(100)

    print(f"TCP SERVER RODANDO EM {HOST}:{PORT}", flush=True)

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_tcp_server()