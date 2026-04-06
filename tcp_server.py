import socket

HOST = "0.0.0.0"
PORT = 5001  # depois você pode mudar

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print(f"🔥 TCP Server rodando em {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    print("📡 Conectado:", addr)

    data = conn.recv(4096)
    print("📦 Dados recebidos:", data)

    conn.close()