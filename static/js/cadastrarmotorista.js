async function cadastrarMotorista(){
  const nome = document.getElementById("nome").value.trim();
  const cpf = document.getElementById("cpf").value.trim();
  const email = document.getElementById("email").value.trim();
  const senha = document.getElementById("senha").value;
  const nascimento = document.getElementById("nascimento").value;
  const endereco = document.getElementById("endereco").value.trim();

  if(!nome || !cpf || !endereco || !email || !senha){
    alert("Preencha todos os campos obrigatórios.");
    return;
  }

  try{
    const resp = await fetch("/api/motoristas", {
      method: "POST",
      headers: {
        "Content-Type":"application/json"
      },
      body: JSON.stringify({
        nome,
        cpf,
        nascimento,
        endereco,
        email,
        senha
      })
    });

    const data = await resp.json();

    if(!resp.ok){
      alert(data.erro || "Erro ao cadastrar");
      return;
    }

    alert("Motorista criado com login!");
    location.assign("/dentromotorista");

  }catch(e){
    alert("Erro de conexão");
  }
}

window.cadastrarMotorista = cadastrarMotorista;