import socket
import threading
import re
import binascii
from datetime import datetime

from conexao import get_db

HOST = "0.0.0.0"
PORT = 5001
BUFFER_SIZE = 4096
RAW_LOG_FILE = "tcp_raw.log"


def log_raw(msg: str):
    try:
        with open(RAW_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {msg}\n")
    except Exception as e:
        print("ERRO log_raw:", e, flush=True)


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
    """
    Tenta achar IMEI em formatos comuns:
    IMEI:123456789012345
    imei=123456789012345
    ...123456789012345...
    """
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
    """
    Parser provisório e tolerante.
    Aceita exemplos como:
    LAT:-7.2301;LNG:-35.8811;SPD:42
    lat=-7.2301 lon=-35.8811 speed=42
    latitude:-7.2301 longitude:-35.8811
    """
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
    """
    Retorna dict com:
    {
        "imei": "...",
        "latitude": ...,
        "longitude": ...,
        "velocidade_kmh": ...
    }
    ou None se não conseguiu parsear.
    """
    imei = extrair_imei(texto)
    lat, lng, vel = extrair_lat_lng_vel(texto)

    if not imei:
        return None

    if lat is None or lng is None:
        return {
            "imei": imei,
            "latitude": None,
            "longitude": None,
            "velocidade_kmh": vel
        }

    return {
        "imei": imei,
        "latitude": lat,
        "longitude": lng,
        "velocidade_kmh": vel
    }


def processar_pacote_texto(texto: str, addr):
    """
    Fluxo antigo preservado:
    1) loga bruto
    2) tenta extrair IMEI
    3) cruza com rastreadores
    4) se tiver lat/lng, salva em veiculos_localizacao
    """
    log_raw(f"{addr} -> TEXTO -> {texto}")

    pacote = parsear_pacote_generico(texto)

    if not pacote:
        print(f"PACOTE TEXTO SEM PARSER | origem={addr} | bruto={texto}", flush=True)
        return

    imei = pacote["imei"]
    latitude = pacote["latitude"]
    longitude = pacote["longitude"]
    velocidade_kmh = pacote["velocidade_kmh"]

    print(
        f"PACOTE PARSEADO | origem={addr} | imei={imei} | lat={latitude} | lng={longitude} | vel={velocidade_kmh}",
        flush=True
    )

    vinculo = buscar_vinculo_rastreador(imei)
    if not vinculo:
        print(f"IMEI NÃO VINCULADO OU INATIVO | imei={imei}", flush=True)
        return

    usuario_id = vinculo["usuario_id"]
    veiculo_id = vinculo["veiculo_id"]

    if latitude is None or longitude is None:
        print(
            f"IMEI VINCULADO, MAS PACOTE SEM LAT/LNG | imei={imei} | usuario_id={usuario_id} | veiculo_id={veiculo_id}",
            flush=True
        )
        return

    salvar_localizacao(
        usuario_id=usuario_id,
        veiculo_id=veiculo_id,
        latitude=latitude,
        longitude=longitude,
        velocidade_kmh=velocidade_kmh,
        endereco=None
    )


def processar_pacote_binario(data: bytes, addr):
    """
    Novo fluxo para o J16 Ultra / binário:
    - grava HEX cru
    - tenta mostrar texto legível
    - não quebra o servidor
    - prepara a próxima etapa de decodificação
    """
    hex_data = binascii.hexlify(data).decode("ascii", errors="ignore")
    log_raw(f"{addr} -> HEX -> {hex_data}")

    print(f"PACOTE BINÁRIO | origem={addr} | hex={hex_data}", flush=True)

    try:
        texto_legivel = data.decode("utf-8", errors="ignore").strip()
    except Exception:
        texto_legivel = ""

    if texto_legivel:
        print(f"PACOTE BINÁRIO COM TEXTO | origem={addr} | texto={texto_legivel}", flush=True)

        # Se por acaso vier um pacote híbrido com IMEI/LAT/LNG em texto,
        # reaproveita o fluxo antigo sem quebrar nada.
        if extrair_imei(texto_legivel):
            processar_pacote_texto(texto_legivel, addr)


def responder_ack(conn, data: bytes):
    """
    ACK genérico.
    Mantido para não quebrar o fluxo atual.
    """
    try:
        conn.sendall(b"OK")
    except Exception as e:
        print("ERRO responder_ack:", e, flush=True)


def handle_client(conn, addr):
    print(f"NOVA CONEXÃO TCP: {addr}", flush=True)

    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break

            print(f"DADOS RECEBIDOS: {data[:120]!r}", flush=True)

            # Primeiro tenta interpretar como texto
            try:
                texto = data.decode("utf-8", errors="ignore").strip()
            except Exception:
                texto = ""

            # Se vier texto claro e útil, usa o fluxo antigo
            if texto and any(ch.isalnum() for ch in texto):
                print(f"PACOTE RECEBIDO | origem={addr} | bruto={texto}", flush=True)
                processar_pacote_texto(texto, addr)
            else:
                # Caso contrário, trata como binário/hex
                processar_pacote_binario(data, addr)

            responder_ack(conn, data)

    except Exception as e:
        print(f"ERRO handle_client {addr}: {e}", flush=True)

    finally:
        try:
            conn.close()
        except Exception:
            pass

        print(f"CONEXÃO ENCERRADA: {addr}", flush=True)


def start_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(100)

    print(f"TCP SERVER RODANDO EM {HOST}:{PORT}", flush=True)

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    start_tcp_server()