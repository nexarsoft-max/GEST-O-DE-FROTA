const API_MONITORAMENTO = "/api/monitoramento/resumo";

let MONITOR_DATA = [];

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function statusLabel(status) {
  if (status === "moving") return "Em Movimento";
  if (status === "stopped") return "Parado";
  return "Offline";
}

function speedText(v) {
  const n = Number(v.velocidade_kmh);
  return Number.isFinite(n) ? `${n} km/h` : "0 km/h";
}

function updatedText(v) {
  return v.ultima_atualizacao_label || v.ultima_atualizacao || "Aguardando última localização";
}

function motoristaText(v) {
  return v.motoristaNome || "Aguardando vínculo do app";
}

function filtrar(lista, termo) {
  const t = (termo || "").trim().toLowerCase();
  if (!t) return lista;

  return lista.filter(v => {
    return [
      v.modelo,
      v.nome,
      v.placa,
      v.motoristaNome,
      v.cidade
    ].some(campo => String(campo || "").toLowerCase().includes(t));
  });
}

function atualizarContadores(listaTotal) {
  const total = listaTotal.length;
  const moving = listaTotal.filter(v => v.status === "moving").length;
  const stopped = listaTotal.filter(v => v.status === "stopped").length;
  const offline = listaTotal.filter(v => v.status === "offline").length;

  const totalEl = document.getElementById("m_total");
  const movingEl = document.getElementById("m_moving");
  const stoppedEl = document.getElementById("m_stopped");
  const offlineEl = document.getElementById("m_offline");

  if (totalEl) totalEl.textContent = total;
  if (movingEl) movingEl.textContent = moving;
  if (stoppedEl) stoppedEl.textContent = stopped;
  if (offlineEl) offlineEl.textContent = offline;
}

function cardVeiculo(v) {
  return `
    <article class="vcard" data-status="${escapeHtml(v.status)}">
      <div class="vcard-header">
        <div class="vcard-left">
          <div class="vicon" title="Veículo">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 11l1.4-4.2A2 2 0 0 1 8.3 5h7.4a2 2 0 0 1 1.9 1.8L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v3h2m14-5a2 2 0 0 1 2 2v3h-2m-11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4"/>
            </svg>
          </div>

          <div class="vtitle">
            <strong>${escapeHtml(v.modelo || "Veículo")}</strong>
            <span>${escapeHtml(v.cidade || "Sem cidade")}</span>
          </div>
        </div>

        <div class="vstatus">
          <span class="vdot"></span>
          <span>${escapeHtml(statusLabel(v.status))}</span>
        </div>
      </div>

      <div class="vplate">${escapeHtml(v.placa || "—")}</div>

      <div class="vinfo">
        <div class="vrow"><span>Motorista</span> <b>${escapeHtml(motoristaText(v))}</b></div>
        <div class="vrow"><span>Velocidade</span> <b>${escapeHtml(speedText(v))}</b></div>
        <div class="vrow"><span>Última atualização</span> <b>${escapeHtml(updatedText(v))}</b></div>
      </div>

      <div class="vactions vactions-single">
        <a class="vbtn secondary" href="/localizacao/${encodeURIComponent(v.id)}">Ver localização</a>
      </div>
    </article>
  `;
}

function render(lista) {
  const grid = document.getElementById("monitorGrid");
  const empty = document.getElementById("monitorEmpty");
  const pill = document.getElementById("m_pill");

  if (!grid) return;

  if (pill) {
    pill.textContent = `${lista.length} veículo${lista.length === 1 ? "" : "s"}`;
  }

  if (!lista.length) {
    grid.innerHTML = "";
    if (empty) empty.style.display = "block";
    return;
  }

  if (empty) empty.style.display = "none";
  grid.innerHTML = lista.map(cardVeiculo).join("");
}

function aplicarBusca() {
  const input = document.getElementById("monitorSearch");
  const termo = input ? input.value : "";
  const filtrados = filtrar(MONITOR_DATA, termo);
  render(filtrados);
}

async function carregarMonitoramento() {
  try {
    const resp = await fetch(API_MONITORAMENTO, {
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    });

    if (resp.status === 401) {
      alert("Sua sessão expirou. Faça login novamente.");
      window.location.assign("/");
      return;
    }

    const data = await resp.json().catch(() => []);

    MONITOR_DATA = Array.isArray(data) ? data : [];
    atualizarContadores(MONITOR_DATA);
    aplicarBusca();
  } catch (err) {
    console.error("Erro ao carregar monitoramento:", err);
    MONITOR_DATA = [];
    atualizarContadores(MONITOR_DATA);
    aplicarBusca();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("monitorSearch");
  if (input) {
    input.addEventListener("input", aplicarBusca);
  }

  carregarMonitoramento();
});