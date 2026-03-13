async function carregar(){
  const container = document.getElementById("lista");
  container.innerHTML = "";

  try{
    const resp = await fetch("/api/veiculos", { headers: { "Accept":"application/json" } });
    const data = await resp.json().catch(()=> ([]));

    if(resp.status === 401){
      alert("Sua sessão expirou. Faça login novamente.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      container.innerHTML = `<div class="vazio">Erro ao carregar veículos</div>`;
      return;
    }

    if(!Array.isArray(data) || data.length === 0){
      container.innerHTML = `<div class="vazio">Nenhum veículo cadastrado</div>`;
      return;
    }

    data.forEach(v=>{
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <h3>${v.modelo}</h3>
        <p>Placa: ${v.placa}</p>
        <p>Cidade: ${v.cidade}</p>
        <div style="margin-top:14px; display:flex; gap:10px;">
          <button style="flex:1;height:42px;border-radius:12px;border:none;cursor:pointer;background:#8b1cf6;color:#fff"
            onclick="location.assign('/editarveiculo/${v.id}')">Editar</button>
        </div>
      `;
      container.appendChild(div);
    });

  }catch(e){
    container.innerHTML = `<div class="vazio">Erro ao carregar veículos</div>`;
    console.error(e);
  }
}
carregar();