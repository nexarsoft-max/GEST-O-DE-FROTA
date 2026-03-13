// ===============================
// ABAS: Abastecimento / Monitoramento
// ===============================
(function tabsInit() {
  const abas = document.querySelectorAll(".aba[data-tab]");
  const paineis = {
    abastecimento: document.getElementById("tab-abastecimento"),
    monitoramento: document.getElementById("tab-monitoramento"),
  };

  function ativar(nome) {
    abas.forEach(b => b.classList.toggle("ativa", b.dataset.tab === nome));
    Object.keys(paineis).forEach(k => paineis[k].classList.toggle("ativo", k === nome));
  }

  abas.forEach(btn => {
    btn.addEventListener("click", () => ativar(btn.dataset.tab));
  });
})();

// ===============================
// DADOS (troque isso para vir do Flask depois)
// Você pode injetar via Jinja também:
// <script>window.MONITOR_VEICULOS = {{ veiculos|tojson }};</script>
// ===============================
const VEICULOS = window.MONITOR_VEICULOS || [
  {
    nome: "Toyota Corolla",
    ano: "GLI 2024",
    placa: "ABC-1234",
    motorista: "João Silva",
    status: "moving", // moving | stopped | offline
    velocidade_kmh: 65,
    combustivel_pct: 78,
    atualizado: "14:32",
  },
  {
    nome: "Honda HR-V",
    ano: "EX 2024",
    placa: "DEF-5678",
    motorista: "Maria Santos",
    status: "stopped",
    velocidade_kmh: null,
    combustivel_pct: 45,
    atualizado: "14:15",
  },
  {
    nome: "Volkswagen Amarok",
    ano: "Highline 2023",
    placa: "GHI-9012",
    motorista: "Carlos Oliveira",
    status: "offline",
    velocidade_kmh: null,
    combustivel_pct: 92,
    atualizado: "13:45",
  },
  {
    nome: "Chevrolet Onix",
    ano: "Premier 2024",
    placa: "JKL-3456",
    motorista: "Ana Costa",
    status: "moving",
    velocidade_kmh: 52,
    combustivel_pct: 63,
    atualizado: "14:30",
  },
];

// ===============================
// RENDER
// ===============================
const grid = document.getElementById("monitorGrid");
const inputSearch = document.getElementById("monitorSearch");

function statusLabel(status) {
  if (status === "moving") return "Em Movimento";
  if (status === "stopped") return "Parado";
  return "Offline";
}

function filtrar(lista, termo) {
  const t = (termo || "").trim().toLowerCase();
  if (!t) return lista;
  return lista.filter(v =>
    (v.nome || "").toLowerCase().includes(t) ||
    (v.ano || "").toLowerCase().includes(t) ||
    (v.placa || "").toLowerCase().includes(t) ||
    (v.motorista || "").toLowerCase().includes(t)
  );
}

function atualizarContadores(listaTotal) {
  const total = listaTotal.length;
  const moving = listaTotal.filter(v => v.status === "moving").length;
  const stopped = listaTotal.filter(v => v.status === "stopped").length;
  const offline = listaTotal.filter(v => v.status === "offline").length;

  document.getElementById("m_total").textContent = total;
  document.getElementById("m_moving").textContent = moving;
  document.getElementById("m_stopped").textContent = stopped;
  document.getElementById("m_offline").textContent = offline;
  document.getElementById("m_pill").textContent = `${total} veículos`;
}

function cardVeiculo(v) {
  const velocidade = (v.status === "moving" && typeof v.velocidade_kmh === "number")
    ? `${v.velocidade_kmh} km/h`
    : "—";

  const fuel = Math.max(0, Math.min(100, Number(v.combustivel_pct || 0)));

  return `
    <article class="vcard" data-status="${v.status}">
      <div class="vcard-header">
        <div class="vcard-left">
          <div class="vicon" title="Veículo">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 11l1.4-4.2A2 2 0 0 1 8.3 5h7.4a2 2 0 0 1 1.9 1.8L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v3h2m14-5a2 2 0 0 1 2 2v3h-2m-11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4"/>
            </svg>
          </div>
          <div class="vtitle">
            <strong>${v.nome || "—"}</strong>
            <span>${v.ano || ""}</span>
          </div>
        </div>

        <div class="vstatus">
          <span class="vdot"></span>
          <span>${statusLabel(v.status)}</span>
        </div>
      </div>

      <div class="vplate">${v.placa || "—"}</div>

      <div class="vinfo">
        <div class="vrow"><span>Motorista</span> <b>${v.motorista || "—"}</b></div>
        <div class="vrow"><span>Velocidade</span> <b>${velocidade}</b></div>

        <div class="vrow"><span>Combustível</span> <b>${fuel}%</b></div>
        <div class="vbar" aria-label="Combustível">
          <i style="width:${fuel}%"></i>
        </div>

        <div class="vrow"><span>Atualizado</span> <b>${v.atualizado ? `às ${v.atualizado}` : "—"}</b></div>
      </div>

      <button class="vbtn" type="button" data-placa="${v.placa || ""}">
        Ver Localização
      </button>
    </article>
  `;
}

function render(lista) {
  atualizarContadores(lista);
  grid.innerHTML = lista.map(cardVeiculo).join("");

  // clique do botão "Ver Localização" -> abre a página individual
  grid.querySelectorAll(".vbtn").forEach(btn => {
    btn.addEventListener("click", () => {
      const placa = btn.getAttribute("data-placa");
      if (!placa) return;

      window.location.href = `/localizacao/${encodeURIComponent(placa)}`;
    });
  });
}

// init
render(VEICULOS);

// busca
if (inputSearch) {
  inputSearch.addEventListener("input", () => {
    const lista = filtrar(VEICULOS, inputSearch.value);
    render(lista);
  });
}