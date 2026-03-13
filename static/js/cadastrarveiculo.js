async function cadastrarVeiculo(){
  const modelo = document.getElementById("modelo").value.trim();
  const placa = document.getElementById("placa").value.trim();
  const renavam = document.getElementById("renavam").value.trim();
  const cidade = document.getElementById("cidade").value.trim();

  if(!modelo || !placa || !cidade){
    alert("Preencha Modelo, Placa e Cidade.");
    return;
  }

  try{
    const resp = await fetch("/api/veiculos", {
      method: "POST",
      headers: { "Content-Type":"application/json", "Accept":"application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ modelo, placa, renavam, cidade })
    });

    const data = await resp.json().catch(()=> ({}));

    if(resp.status === 401){
      alert("Sua sessão expirou. Faça login novamente.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      alert(data.erro || `Erro ao cadastrar veículo (HTTP ${resp.status})`);
      return;
    }

    alert("Veículo cadastrado com sucesso!");
    location.assign("/dentroveiculo");
  }catch(e){
    console.error(e);
    alert("Erro de conexão com o servidor");
  }
}
window.cadastrarVeiculo = cadastrarVeiculo;