const STORAGE_KEY = "gorota_alertas_resolvidos_v2";

const iconesPorTipo = {
  colaboradores_ativos: "fa-users",
  veiculos_em_uso: "fa-car-side",
  checklist_faltando: "fa-toolbox",
  veiculo_danificado: "fa-triangle-exclamation",
  observacoes: "fa-comment-dots",
  pendentes: "fa-clock"
};

const nomeTipo = {
  colaboradores_ativos: "Colaboradores ativos",
  veiculos_em_uso: "Veículos em uso",
  checklist_faltando: "Check list faltando equipamento",
  veiculo_danificado: "Veículo danificado",
  observacoes: "Observações",
  pendentes: "Pendentes"
};

const tiposCriticos = ["checklist_faltando", "veiculo_danificado", "pendentes"];

const alertList = document.getElementById("alertList");
const emptyState = document.getElementById("emptyState");
const searchInput = document.getElementById("searchInput");
const typeFilter = document.getElementById("typeFilter");
const statusFilter = document.getElementById("statusFilter");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");
const resultadoTexto = document.getElementById("resultadoTexto");

const heroFiltroAtual = document.getElementById("heroFiltroAtual");
const heroFiltroDescricao = document.getElementById("heroFiltroDescricao");
const heroCriticosQtd = document.getElementById("heroCriticosQtd");

const countColaboradoresAtivos = document.getElementById("countColaboradoresAtivos");
const countVeiculosEmUso = document.getElementById("countVeiculosEmUso");
const countChecklistFaltando = document.getElementById("countChecklistFaltando");
const countVeiculoDanificado = document.getElementById("countVeiculoDanificado");
const countObservacoes = document.getElementById("countObservacoes");
const countPendentes = document.getElementById("countPendentes");

const resumoCards = [...document.querySelectorAll(".resumo-card")];

let alertasBase = [];
let tipoDestacado = obterTipoDaUrl();

function obterTipoDaUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("tipo") || "";
}

function obterResolvidos() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function salvarResolvidos(obj) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
}

function escapeHtml(texto) {
  return String(texto || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizarTexto(valor) {
  return String(valor || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatarDataHora(valor) {
  if (!valor) return "-";

  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;

  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function classificaCritico(tipo) {
  return tiposCriticos.includes(tipo);
}

function montarMetaHtml(meta = {}) {
  const itens = [];

  if (meta.colaborador) {
    itens.push(`
      <span class="alert-meta-item">
        <i class="fa-solid fa-user"></i>
        ${escapeHtml(meta.colaborador)}
      </span>
    `);
  }

  if (meta.veiculo) {
    itens.push(`
      <span class="alert-meta-item">
        <i class="fa-solid fa-car"></i>
        ${escapeHtml(meta.veiculo)}
      </span>
    `);
  }

  if (meta.placa) {
    itens.push(`
      <span class="alert-meta-item">
        <i class="fa-solid fa-id-card"></i>
        ${escapeHtml(meta.placa)}
      </span>
    `);
  }

  return itens.join("");
}

function aplicarEstadoResolvido(alertas) {
  const resolvidos = obterResolvidos();

  return alertas.map((alerta) => ({
    ...alerta,
    resolvido: !!resolvidos[String(alerta.id)]
  }));
}

async function carregarAlertas() {
  const response = await fetch("/api/alertas", {
    headers: { "Accept": "application/json" }
  });

  const data = await response.json();

  if (!response.ok || data.sucesso === false) {
    throw new Error(data.erro || "Erro ao carregar alertas");
  }

  const lista = Array.isArray(data.alertas) ? data.alertas : [];
  return aplicarEstadoResolvido(lista);
}

function atualizarResumo(alertas) {
  const ativos = alertas.filter((a) => !a.resolvido);

  const countByType = (tipo) => ativos.filter((a) => a.tipo === tipo).length;

  countColaboradoresAtivos.textContent = countByType("colaboradores_ativos") || "--";
  countVeiculosEmUso.textContent = countByType("veiculos_em_uso") || "--";
  countChecklistFaltando.textContent = countByType("checklist_faltando") || "--";
  countVeiculoDanificado.textContent = countByType("veiculo_danificado") || "--";
  countObservacoes.textContent = countByType("observacoes") || "--";
  countPendentes.textContent = countByType("pendentes") || "--";

  heroCriticosQtd.textContent =
    countByType("checklist_faltando") +
    countByType("veiculo_danificado") +
    countByType("pendentes");
}

function obterAlertasFiltrados() {
  const termo = normalizarTexto(searchInput.value);
  const tipo = typeFilter.value;
  const status = statusFilter.value;

  return alertasBase.filter((alerta) => {
    const textoPesquisa = normalizarTexto([
      alerta.titulo,
      alerta.texto,
      alerta.tipo,
      alerta.meta?.colaborador,
      alerta.meta?.veiculo,
      alerta.meta?.placa
    ].join(" "));

    const matchTexto = !termo || textoPesquisa.includes(termo);
    const matchTipo = !tipo || alerta.tipo === tipo;

    let matchStatus = true;
    if (status === "ativos") matchStatus = !alerta.resolvido;
    if (status === "resolvidos") matchStatus = alerta.resolvido;

    return matchTexto && matchTipo && matchStatus;
  });
}

function atualizarTextoTopo() {
  if (!typeFilter.value) {
    heroFiltroAtual.textContent = "Todos os alertas";
    heroFiltroDescricao.textContent = "Nenhum filtro aplicado no momento.";
    return;
  }

  heroFiltroAtual.textContent = nomeTipo[typeFilter.value] || "Filtro aplicado";
  heroFiltroDescricao.textContent = "Lista exibida conforme o tipo de alerta selecionado.";
}

function atualizarResumoHighlight() {
  resumoCards.forEach((card) => {
    card.classList.remove("ativo", "piscando");
    if (card.dataset.filter === typeFilter.value) {
      card.classList.add("ativo", "piscando");
    }
  });
}

function irParaColaboradores(alerta) {
  if (!alerta?.expediente_id) return;
  const url = `/colaboradores?expediente_id=${encodeURIComponent(alerta.expediente_id)}&tipo=${encodeURIComponent(alerta.tipo || "")}`;
  window.location.href = url;
}

function criarCard(alerta) {
  const critico = classificaCritico(alerta.tipo);
  const card = document.createElement("article");

  card.className = [
    "alert-card",
    critico ? "critico" : "",
    alerta.resolvido ? "resolvido" : "",
    typeFilter.value && alerta.tipo === typeFilter.value ? "destacado piscando" : ""
  ].join(" ").trim();

  card.dataset.alertId = String(alerta.id);
  card.dataset.action = "go";

  const botaoOkClasse = alerta.resolvido ? "btn-ok resolvido" : "btn-ok";
  const botaoOkTexto = alerta.resolvido ? "Reabrir" : "OK";

  card.innerHTML = `
    <div class="alert-icon">
      <i class="fa-solid ${iconesPorTipo[alerta.tipo] || "fa-bell"}"></i>
    </div>

    <div class="alert-body">
      <div class="alert-top">
        <span class="alert-tag ${critico ? "critico" : ""}">
          ${escapeHtml(nomeTipo[alerta.tipo] || alerta.tipo)}
        </span>
        <span class="alert-time">
          <i class="fa-regular fa-clock"></i>
          ${escapeHtml(formatarDataHora(alerta.dataHora))}
        </span>
      </div>

      <div class="alert-title">${escapeHtml(alerta.titulo)}</div>
      <div class="alert-text">${escapeHtml(alerta.texto)}</div>

      <div class="alert-meta">
        ${montarMetaHtml(alerta.meta)}
      </div>
    </div>

    <div class="alert-actions">
      ${alerta.resolvivel ? `
        <button class="${botaoOkClasse}" data-action="toggle-ok" data-id="${alerta.id}">
          ${botaoOkTexto}
        </button>
      ` : `
        <div></div>
      `}
      <button class="btn-ver" data-action="go" data-id="${alerta.id}">
        Abrir registro
      </button>
    </div>
  `;

  return card;
}

function renderizarAlertas() {
  const filtrados = obterAlertasFiltrados();

  alertList.innerHTML = "";

  atualizarTextoTopo();
  atualizarResumoHighlight();

  if (!filtrados.length) {
    emptyState.classList.remove("hidden");
    resultadoTexto.textContent = "Nenhum alerta encontrado com os filtros atuais.";
    return;
  }

  emptyState.classList.add("hidden");

  const ativos = filtrados.filter((a) => !a.resolvido).length;
  const resolvidos = filtrados.filter((a) => a.resolvido).length;

  resultadoTexto.textContent =
    `${filtrados.length} alerta(s) encontrados · ${ativos} ativo(s) · ${resolvidos} concluído(s)`;

  filtrados.forEach((alerta) => {
    alertList.appendChild(criarCard(alerta));
  });
}

function alternarResolvido(id) {
  const resolvidos = obterResolvidos();
  const chave = String(id);

  if (resolvidos[chave]) {
    delete resolvidos[chave];
  } else {
    resolvidos[chave] = true;
  }

  salvarResolvidos(resolvidos);

  alertasBase = alertasBase.map((alerta) => ({
    ...alerta,
    resolvido: !!resolvidos[String(alerta.id)]
  }));

  atualizarResumo(alertasBase);
  renderizarAlertas();
}

function obterAlertaPorId(id) {
  return alertasBase.find((item) => String(item.id) === String(id)) || null;
}

function configurarEventos() {
  searchInput.addEventListener("input", renderizarAlertas);
  typeFilter.addEventListener("change", renderizarAlertas);
  statusFilter.addEventListener("change", renderizarAlertas);

  clearFiltersBtn.addEventListener("click", () => {
    searchInput.value = "";
    typeFilter.value = "";
    statusFilter.value = "ativos";
    renderizarAlertas();
    window.history.replaceState({}, "", window.location.pathname);
  });

  resumoCards.forEach((card) => {
    card.addEventListener("click", () => {
      typeFilter.value = card.dataset.filter || "";
      renderizarAlertas();
      window.history.replaceState({}, "", `${window.location.pathname}?tipo=${typeFilter.value}`);
    });
  });

  alertList.addEventListener("click", (event) => {
    const botao = event.target.closest("button");
    const card = event.target.closest(".alert-card");

    if (botao) {
      const action = botao.dataset.action;
      const id = botao.dataset.id;
      const alerta = obterAlertaPorId(id);

      if (action === "toggle-ok") {
        event.stopPropagation();
        alternarResolvido(id);
        return;
      }

      if (action === "go") {
        event.stopPropagation();
        irParaColaboradores(alerta);
        return;
      }
    }

    if (card && card.dataset.alertId) {
      const alerta = obterAlertaPorId(card.dataset.alertId);
      irParaColaboradores(alerta);
    }
  });
}

async function iniciar() {
  try {
    alertasBase = await carregarAlertas();

    if (tipoDestacado) {
      typeFilter.value = tipoDestacado;
    }

    atualizarResumo(alertasBase);
    configurarEventos();
    renderizarAlertas();
  } catch (e) {
    console.error("Erro ao iniciar alertas:", e);
    alertList.innerHTML = "";
    emptyState.classList.remove("hidden");
    resultadoTexto.textContent = "Não foi possível carregar os alertas.";
    heroFiltroAtual.textContent = "Falha no carregamento";
    heroFiltroDescricao.textContent = "A API de alertas não respondeu corretamente.";
    heroCriticosQtd.textContent = "--";
  }
}

iniciar();