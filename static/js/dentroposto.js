function precoDo(p, tipo){
  const alvo = String(tipo || "").toLowerCase().trim();

  if (Array.isArray(p.combustiveis)) {
    const item = p.combustiveis.find(c => String(c.tipo||"").toLowerCase().trim() === alvo);
    return item ? Number(item.preco || 0).toFixed(2) : "0.00";
  }

  if (alvo === "gasolina") return Number(p.gasolina || 0).toFixed(2);
  if (alvo === "etanol") return Number(p.etanol || 0).toFixed(2);
  if (alvo === "diesel") return Number(p.diesel || 0).toFixed(2);
  return "0.00";
}

async function carregar(){
  const container = document.getElementById("lista");
  container.innerHTML = "";

  try{
    const resp = await fetch("/api/postos", { headers: { "Accept":"application/json" } });
    const data = await resp.json().catch(()=> ([]));

    if(resp.status === 401){
      alert("Sua sessão expirou. Faça login novamente.");
      location.assign("/");
      return;
    }

    if(!resp.ok){
      container.innerHTML = `<div class="vazio">Erro ao carregar postos</div>`;
      return;
    }

    if(!Array.isArray(data) || data.length === 0){
      container.innerHTML = `<div class="vazio">Nenhum posto cadastrado</div>`;
      return;
    }

    data.forEach(p=>{
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <h3>${p.nome || ""}</h3>
        <p>${p.endereco || ""}</p>
        <p>Gasolina: R$ ${precoDo(p,"gasolina")}</p>
        <p>Etanol: R$ ${precoDo(p,"etanol")}</p>
        <p>Diesel: R$ ${precoDo(p,"diesel")}</p>

        <div style="margin-top:14px; display:flex; gap:10px;">
          <button class="btn" onclick="location.assign('/editarposto/${p.id}')">Editar</button>
        </div>
      `;
      container.appendChild(div);
    });

  }catch(e){
    console.error(e);
    container.innerHTML = `<div class="vazio">Erro ao carregar postos</div>`;
  }
}

// garante que só roda depois que a página carregar
document.addEventListener("DOMContentLoaded", carregar);