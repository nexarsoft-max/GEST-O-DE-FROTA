const MOTORISTA_ID = Number("{{ motorista_id|int }}");

function mostrarErroPadrao(msg) {
  alert(msg || "Ocorreu um erro na operação.");
}

async function carregar() {
  try {
    const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`, {
      headers: { "Accept": "application/json" }
    });

    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      mostrarErroPadrao(data.erro || "Erro ao carregar motorista");
      history.back();
      return;
    }

    document.getElementById("nome").value = data.nome || "";
    document.getElementById("cpf").value = data.cpf || "";
    document.getElementById("email").value = data.email || "";
    document.getElementById("nascimento").value = data.nascimento || "";
    document.getElementById("endereco").value = data.endereco || "";
    document.getElementById("senha").value = "";
  } catch (e) {
    console.error(e);
    mostrarErroPadrao("Erro de conexão ao carregar motorista");
  }
}

async function salvar() {
  const nome = document.getElementById("nome").value.trim();
  const cpf = document.getElementById("cpf").value.trim();
  const email = document.getElementById("email").value.trim().toLowerCase();
  const senha = document.getElementById("senha").value;
  const nascimento = document.getElementById("nascimento").value;
  const endereco = document.getElementById("endereco").value.trim();

  if (!nome || !cpf || !email || !endereco) {
    alert("Preencha nome, CPF, email e endereço.");
    return;
  }

  try {
    const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({
        nome,
        cpf,
        email,
        senha,
        nascimento,
        endereco
      })
    });

    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      mostrarErroPadrao(data.erro || "Erro ao salvar");
      return;
    }

    alert("Motorista atualizado com sucesso!");
    location.assign("/dentromotorista");
  } catch (e) {
    console.error(e);
    mostrarErroPadrao("Erro de conexão ao salvar motorista");
  }
}

async function excluir() {
  if (!confirm("Excluir motorista?")) return;

  try {
    const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`, {
      method: "DELETE",
      headers: { "Accept": "application/json" }
    });

    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      mostrarErroPadrao(data.erro || "Erro ao excluir");
      return;
    }

    location.assign("/dentromotorista");
  } catch (e) {
    console.error(e);
    mostrarErroPadrao("Erro de conexão ao excluir motorista");
  }
}

carregar();