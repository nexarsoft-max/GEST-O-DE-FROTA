console.log("login.js carregado");

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("formLogin");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = document.getElementById("email").value.trim();
    const senha = document.getElementById("senha").value;

    try {
      const resposta = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email, senha }),
      });

      // ✅ se por algum motivo não vier JSON, evita quebrar tudo
      const data = await resposta.json().catch(() => null);

      if (!resposta.ok || !data || data.sucesso !== true) {
        alert((data && data.erro) ? data.erro : "E-mail ou senha inválidos");
        return;
      }

      window.location.replace("/dashboard");
    } catch (erro) {
      console.error("Erro:", erro);
      alert("Erro ao conectar com o servidor");
    }
  });
});
