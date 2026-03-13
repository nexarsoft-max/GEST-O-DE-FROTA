
async function cadastrarMotorista(){
  const nome = document.getElementById("nome").value.trim();
  const cpf = document.getElementById("cpf").value.trim();
  const nascimento = document.getElementById("nascimento").value;
  const endereco = document.getElementById("endereco").value.trim();

  if(!nome || !cpf || !endereco){
    alert("Preencha Nome, CPF e Endereço.");
    return;
  }

  try{
    const resp = await fetch("/api/motoristas", {
      method: "POST",
      headers: {
        "Content-Type":"application/json",
        "Accept":"application/json"
      },
      body: JSON.stringify({ nome, cpf, nascimento, endereco })
    });

    const data = await resp.json().catch(()=> ({}));

    if(resp.status === 401){
      alert("Sua sessão expirou. Faça login novamente.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      alert(data.erro || `Erro ao cadastrar motorista (HTTP ${resp.status})`);
      return;
    }

    alert("Motorista cadastrado!");
    // vai para a listagem
    window.location.assign("/dentromotorista");

  }catch(err){
    console.error(err);
    alert("Erro de conexão com o servidor");
  }
}
window.cadastrarMotorista = cadastrarMotorista;
