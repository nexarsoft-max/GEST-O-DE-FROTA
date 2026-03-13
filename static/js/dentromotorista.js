async function carregar(){
  const container = document.getElementById("lista");
  container.innerHTML = "";

  try{
    const resp = await fetch("/api/motoristas", { headers: { "Accept":"application/json" } });
    const data = await resp.json().catch(()=> ([]));

    if(resp.status === 401){
      alert("Sua sessão expirou. Faça login novamente.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      container.innerHTML = `<div class="vazio">Erro ao carregar motoristas</div>`;
      return;
    }

    if(!Array.isArray(data) || data.length === 0){
      container.innerHTML = `<div class="vazio">Nenhum motorista cadastrado</div>`;
      return;
    }

    data.forEach(m=>{
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <h3>${m.nome}</h3>
        <p>CPF: ${m.cpf}</p>
        <p>Endereço: ${m.endereco}</p>
        <div style="margin-top:14px; display:flex; gap:10px;">
          <button style="flex:1;height:42px;border-radius:12px;border:none;cursor:pointer;background:#8b1cf6;color:#fff"
            onclick="location.assign('/editarmotorista/${m.id}')">Editar</button>
        </div>
      `;
      container.appendChild(div);
    });

  }catch(e){
    container.innerHTML = `<div class="vazio">Erro ao carregar motoristas</div>`;
    console.error(e);
  }
}
carregar();