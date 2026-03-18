// ===============================
// MONITORAMENTO REAL (SEM FAKE)
// ===============================

const API_BASE = "";

// ===============================
// FETCH
// ===============================
async function tryFetch(url){
  try{
    const r = await fetch(url, {
      headers: { "Accept":"application/json" },
      credentials: "same-origin"
    });

    if(r.status === 401){
      alert("Sessão expirada");
      location.assign("/");
      return [];
    }

    if(!r.ok) return [];
    return await r.json();

  }catch(e){
    console.error("Erro:", e);
    return [];
  }
}

// ===============================
// CARREGAR DADOS REAIS
// ===============================
async function carregarDados(){

  const [veiculos, motoristas, abastecimentos] = await Promise.all([
    tryFetch("/api/veiculos"),
    tryFetch("/api/motoristas"),
    tryFetch("/api/abastecimentos")
  ]);

  return {
    veiculos: Array.isArray(veiculos) ? veiculos : [],
    motoristas: Array.isArray(motoristas) ? motoristas : [],
    abastecimentos: Array.isArray(abastecimentos) ? abastecimentos : []
  };
}

// ===============================
// MAPA POR ID
// ===============================
function mapPorId(lista){
  return new Map(lista.map(i => [Number(i.id), i]));
}

// ===============================
// STATUS (preparado pro rastreador)
// ===============================
function calcularStatus(abastecimentos){
  const agora = Date.now();

  return abastecimentos.map(a => {
    const data = new Date(`${a.data}T${a.hora || "00:00"}`).getTime();

    const diffMin = (agora - data) / 60000;

    let status = "offline";

    if(diffMin < 60){
      status = "moving";
    } else if(diffMin < 180){
      status = "stopped";
    }

    return {
      veiculoId: a.veiculoId,
      status
    };
  });
}

// ===============================
// CONTADORES
// ===============================
function atualizarContadores(lista){

  const total = lista.length;
  const moving = lista.filter(v => v.status === "moving").length;
  const stopped = lista.filter(v => v.status === "stopped").length;
  const offline = lista.filter(v => v.status === "offline").length;

  document.getElementById("m_total").textContent = total;
  document.getElementById("m_moving").textContent = moving;
  document.getElementById("m_stopped").textContent = stopped;
  document.getElementById("m_offline").textContent = offline;
}

// ===============================
// LABEL STATUS
// ===============================
function statusLabel(s){
  if(s === "moving") return "Em Movimento";
  if(s === "stopped") return "Parado";
  return "Offline";
}

// ===============================
// RENDER VEICULOS
// ===============================
function render(lista, motoristas){

  const grid = document.getElementById("monitorGrid");

  if(!grid) return;

  if(!lista.length){
    grid.innerHTML = "<p>Nenhum veículo cadastrado ainda.</p>";
    return;
  }

  const mapMotoristas = mapPorId(motoristas);

  grid.innerHTML = lista.map(v => {

    const motorista = mapMotoristas.get(v.motoristaId);

    return `
      <div class="vcard" data-status="${v.status}">

        <h3>${v.placa} - ${v.modelo}</h3>

        <p>Status: ${statusLabel(v.status)}</p>

        <p>Motorista: ${
          motorista ? motorista.nome : "Aguardando vínculo"
        }</p>

      </div>
    `;

  }).join("");
}

// ===============================
// INIT
// ===============================
async function init(){

  const { veiculos, motoristas, abastecimentos } = await carregarDados();

  const statusList = calcularStatus(abastecimentos);

  // junta status no veículo
  const veiculosComStatus = veiculos.map(v => {

    const st = statusList.find(s => s.veiculoId == v.id);

    return {
      ...v,
      status: st ? st.status : "offline",
      motoristaId: null // preparado para futuro vínculo
    };
  });

  atualizarContadores(veiculosComStatus);

  render(veiculosComStatus, motoristas);
}

document.addEventListener("DOMContentLoaded", init);