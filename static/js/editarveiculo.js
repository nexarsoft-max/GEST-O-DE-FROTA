const VEICULO_ID = Number("{{ veiculo_id|int }}");

async function carregar(){
  const resp = await fetch(`/api/veiculos/${VEICULO_ID}`);
  const data = await resp.json().catch(()=> ({}));

  if(resp.status === 401){
    alert("Sessão expirada");
    location.assign("/");
    return;
  }

  if(!resp.ok){
    alert("Erro ao carregar veículo");
    history.back();
    return;
  }

  document.getElementById("modelo").value = data.modelo || "";
  document.getElementById("placa").value = data.placa || "";
  document.getElementById("renavam").value = data.renavam || "";
  document.getElementById("cidade").value = data.cidade || "";
}

async function salvar(){
  const modelo = document.getElementById("modelo").value.trim();
  const placa = document.getElementById("placa").value.trim();
  const renavam = document.getElementById("renavam").value.trim();
  const cidade = document.getElementById("cidade").value.trim();

  const resp = await fetch(`/api/veiculos/${VEICULO_ID}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ modelo, placa, renavam, cidade })
  });

  if(!resp.ok){
    alert("Erro ao salvar");
    return;
  }

  location.assign("/dentroveiculo");
}

async function excluir(){
  if(!confirm("Excluir veículo?")) return;

  const resp = await fetch(`/api/veiculos/${VEICULO_ID}`, {
    method: "DELETE"
  });

  if(!resp.ok){
    alert("Erro ao excluir");
    return;
  }

  location.assign("/dentroveiculo");
}

carregar();