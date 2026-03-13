const MOTORISTA_ID = Number("{{ motorista_id|int }}");

async function carregar(){
  const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`);
  const data = await resp.json().catch(()=> ({}));

  if(resp.status === 401){
    alert("Sessão expirada");
    location.assign("/");
    return;
  }

  if(!resp.ok){
    alert("Erro ao carregar motorista");
    history.back();
    return;
  }

  document.getElementById("nome").value = data.nome || "";
  document.getElementById("cpf").value = data.cpf || "";
  document.getElementById("nascimento").value = data.nascimento || "";
  document.getElementById("endereco").value = data.endereco || "";
}

async function salvar(){
  const nome = document.getElementById("nome").value.trim();
  const cpf = document.getElementById("cpf").value.trim();
  const nascimento = document.getElementById("nascimento").value;
  const endereco = document.getElementById("endereco").value.trim();

  const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ nome, cpf, nascimento, endereco })
  });

  if(!resp.ok){
    alert("Erro ao salvar");
    return;
  }

  location.assign("/dentromotorista");
}

async function excluir(){
  if(!confirm("Excluir motorista?")) return;

  const resp = await fetch(`/api/motoristas/${MOTORISTA_ID}`, {
    method: "DELETE"
  });

  if(!resp.ok){
    alert("Erro ao excluir");
    return;
  }

  location.assign("/dentromotorista");
}

carregar();