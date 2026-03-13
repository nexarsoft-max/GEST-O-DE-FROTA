const POSTO_ID = Number(document.body.dataset.postoId);

function setMsg(t){ document.getElementById("msg").textContent = t || ""; }

function precoDo(p, tipo){
  const alvo = String(tipo||"").toLowerCase().trim();
  const arr = Array.isArray(p.combustiveis) ? p.combustiveis : [];
  const item = arr.find(c => String(c.tipo||"").toLowerCase().trim() === alvo);
  return item ? (Number(item.preco || 0).toFixed(2)) : "0.00";
}

async function carregar(){
  setMsg("Carregando...");
  const resp = await fetch(`/api/postos/${POSTO_ID}`, { headers: { "Accept":"application/json" }});
  const data = await resp.json().catch(()=> ({}));

  if(resp.status === 401){
    alert("Sessão expirada. Faça login novamente.");
    location.assign("/");
    return;
  }
  if(!resp.ok){
    setMsg(data.erro || "Erro ao carregar posto");
    return;
  }

  document.getElementById("nome").value = data.nome || "";
  document.getElementById("endereco").value = data.endereco || "";
  document.getElementById("gasolina").value = precoDo(data,"gasolina");
  document.getElementById("etanol").value = precoDo(data,"etanol");
  document.getElementById("diesel").value = precoDo(data,"diesel");
  setMsg("");
}

async function salvar(){
  const nome = document.getElementById("nome").value.trim();
  const endereco = document.getElementById("endereco").value.trim();
  const gasolina = document.getElementById("gasolina").value;
  const etanol = document.getElementById("etanol").value;
  const diesel = document.getElementById("diesel").value;

  if(!nome || !endereco){
    alert("Preencha Nome e Endereço.");
    return;
  }

  setMsg("Salvando...");
  const resp = await fetch(`/api/postos/${POSTO_ID}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ nome, endereco, gasolina, etanol, diesel })
  });
  const data = await resp.json().catch(()=> ({}));

  if(resp.status === 401){
    alert("Sessão expirada. Faça login novamente.");
    location.assign("/");
    return;
  }
  if(!resp.ok){
    setMsg("");
    alert(data.erro || `Erro ao salvar (HTTP ${resp.status})`);
    return;
  }

  setMsg("Salvo com sucesso!");
  setTimeout(()=> location.assign("/dentroposto"), 300);
}

function abrirModal(){ document.getElementById("modal").style.display = "flex"; }
function fecharModal(e){
  if(!e || e.target.id === "modal"){
    document.getElementById("modal").style.display = "none";
  }
}

async function excluir(){
  setMsg("Excluindo...");
  const resp = await fetch(`/api/postos/${POSTO_ID}`, { method: "DELETE" });
  const data = await resp.json().catch(()=> ({}));

  if(resp.status === 401){
    alert("Sessão expirada. Faça login novamente.");
    location.assign("/");
    return;
  }
  if(!resp.ok){
    setMsg("");
    alert(data.erro || `Erro ao excluir (HTTP ${resp.status})`);
    return;
  }

  location.assign("/dentroposto");
}

carregar();