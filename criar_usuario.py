import re
import secrets
import string
from werkzeug.security import generate_password_hash
from conexao import get_db

def email_valido(email: str) -> bool:
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email) is not None

def gerar_senha_forte(tamanho: int = 14) -> str:
    # Gera senha com letras, números e símbolos
    alfabeto = string.ascii_letters + string.digits + "!@#$%&*?-_"
    while True:
        senha = "".join(secrets.choice(alfabeto) for _ in range(tamanho))
        if (any(c.islower() for c in senha)
            and any(c.isupper() for c in senha)
            and any(c.isdigit() for c in senha)
            and any(c in "!@#$%&*?-_" for c in senha)):
            return senha

def criar_usuario(email: str, senha: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,))
        if cur.fetchone():
            print("❌ Já existe um usuário com esse email.")
            return

        senha_hash = generate_password_hash(senha)

        cur.execute(
            "INSERT INTO usuarios (email, senha_hash) VALUES (%s, %s)",
            (email, senha_hash)
        )
        conn.commit()
        print("✅ Usuário criado com sucesso!")
        print(f"Email: {email}")
        print(f"Senha: {senha}")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    email = input("Email do cliente: ").strip().lower()

    if not email_valido(email):
        print("❌ Email inválido (formato).")
        raise SystemExit(1)

    escolha = input("Gerar senha forte automaticamente? (s/n): ").strip().lower()

    if escolha == "s":
        senha = gerar_senha_forte()
    else:
        senha = input("Digite a senha: ").strip()

    if len(senha) < 10:
        print("❌ Senha fraca. Use pelo menos 10 caracteres.")
        raise SystemExit(1)

    criar_usuario(email, senha)