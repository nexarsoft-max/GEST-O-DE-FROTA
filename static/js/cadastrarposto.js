document.getElementById("formPosto").addEventListener("submit", async function(e){
  e.preventDefault(); // 🚨 impede reload

  const nome = document.getElementById("nomePosto").value.trim();
  const endereco = document.getElementById("enderecoPosto").value.trim();
  const gasolina = document.getElementById("gasolina").value.trim();
  const etanol = document.getElementById("etanol").value.trim();
  const diesel = document.getElementById("diesel").value.trim();

  if(!nome || !endereco){
    alert("Preencha Nome e Endereço.");
    return;
  }

  try{
    const resp = await fetch("/api/postos", {
      method: "POST",
      headers: {
        "Content-Type":"application/json",
        "Accept":"application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({ nome, endereco, gasolina, etanol, diesel })
    });

    const data = await resp.json().catch(()=> ({}));

    if(resp.status === 401){
      alert("Sessão expirada.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      alert(data.erro || `Erro HTTP ${resp.status}`);
      return;
    }

    alert("Posto cadastrado com sucesso!");
    location.assign("/dentroposto");

  }catch(e){
    console.error(e);
    alert("Erro de conexão");
  }
});