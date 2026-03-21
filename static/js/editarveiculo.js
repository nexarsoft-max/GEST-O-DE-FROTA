const VEICULO_ID = Number(document.body.dataset.veiculoId);

async function carregar() {
  if (!VEICULO_ID || Number.isNaN(VEICULO_ID)) {
    alert("ID do veículo inválido");
    history.back();
    return;
  }

  try {
    const resp = await fetch(`/api/veiculos/${VEICULO_ID}`);
    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      alert(data.erro || "Erro ao carregar veículo");
      history.back();
      return;
    }

    document.getElementById("modelo").value = data.modelo || "";
    document.getElementById("placa").value = data.placa || "";
    document.getElementById("renavam").value = data.renavam || "";
    document.getElementById("cidade").value = data.cidade || "";
  } catch (erro) {
    alert("Erro de conexão ao carregar veículo");
    console.error(erro);
  }
}

async function salvar() {
  if (!VEICULO_ID || Number.isNaN(VEICULO_ID)) {
    alert("ID do veículo inválido");
    return;
  }

  const modelo = document.getElementById("modelo").value.trim();
  const placa = document.getElementById("placa").value.trim();
  const renavam = document.getElementById("renavam").value.trim();
  const cidade = document.getElementById("cidade").value.trim();

  try {
    const resp = await fetch(`/api/veiculos/${VEICULO_ID}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        modelo,
        placa,
        renavam,
        cidade
      })
    });

    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      alert(data.erro || "Erro ao salvar");
      return;
    }

    alert("Veículo atualizado com sucesso");
    location.assign("/dentroveiculo");
  } catch (erro) {
    alert("Erro de conexão ao salvar");
    console.error(erro);
  }
}

async function excluir() {
  if (!VEICULO_ID || Number.isNaN(VEICULO_ID)) {
    alert("ID do veículo inválido");
    return;
  }

  if (!confirm("Excluir veículo?")) {
    return;
  }

  try {
    const resp = await fetch(`/api/veiculos/${VEICULO_ID}`, {
      method: "DELETE"
    });

    const data = await resp.json().catch(() => ({}));

    if (resp.status === 401) {
      alert("Sessão expirada");
      location.assign("/");
      return;
    }

    if (!resp.ok) {
      alert(data.erro || "Erro ao excluir");
      return;
    }

    alert("Veículo excluído com sucesso");
    location.assign("/dentroveiculo");
  } catch (erro) {
    alert("Erro de conexão ao excluir");
    console.error(erro);
  }
}

carregar();