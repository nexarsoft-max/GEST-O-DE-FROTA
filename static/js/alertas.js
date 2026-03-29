const STORAGE_KEY = "gorota_alertas_resolvidos";

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
  checklist_faltando: "Checklist faltando equipamento",
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

  if (meta.extra) {
    itens.push(`
      <span class="alert-meta-item">
        <i class="fa-solid fa-circle-info"></i>
        ${escapeHtml(meta.extra)}
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

function gerarAlertasMock() {
  const agora = new Date();
  const menosMinutos = (min) => new Date(agora.getTime() - min * 60000).toISOString();

  return [
    {
      id: 1,
      tipo: "colaboradores_ativos",
      titulo: "Gabriel iniciou o expediente",
      texto: "Gabriel iniciou o expediente em 28/03 às 15:30 e segue com operação em andamento.",
      dataHora: menosMinutos(25),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65",
        placa: "SGH-2E65"
      }
    },
    {
      id: 2,
      tipo: "colaboradores_ativos",
      titulo: "Expediente em dupla registrado",
      texto: "Gabriel iniciou o expediente e está de dupla com Carlos. Ambos devem entrar na leitura de colaboradores ativos.",
      dataHora: menosMinutos(22),
      meta: {
        colaborador: "Gabriel",
        extra: "Dupla com Carlos"
      }
    },
    {
      id: 3,
      tipo: "veiculos_em_uso",
      titulo: "Veículo em uso no momento",
      texto: "O veículo Fiat SGH-2E65 está em uso em um expediente ainda não finalizado.",
      dataHora: menosMinutos(20),
      meta: {
        veiculo: "Fiat SGH-2E65",
        placa: "SGH-2E65",
        colaborador: "Gabriel"
      }
    },
    {
      id: 4,
      tipo: "checklist_faltando",
      titulo: "Checklist de entrada com equipamento faltando",
      texto: "Gabriel informou no checklist de entrada que há equipamento faltando no veículo utilizado.",
      dataHora: menosMinutos(18),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65",
        extra: "Falta de equipamento"
      }
    },
    {
      id: 5,
      tipo: "veiculo_danificado",
      titulo: "Veículo reportado como danificado",
      texto: "Gabriel informou na entrada que o veículo está danificado e requer atenção da gestão.",
      dataHora: menosMinutos(16),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65",
        placa: "SGH-2E65"
      }
    },
    {
      id: 6,
      tipo: "veiculo_danificado",
      titulo: "Dano reiterado no encerramento",
      texto: "Gabriel informou novamente no fim do expediente que o veículo permanece danificado. O alerta continua narrativo, sem duplicar a contagem principal.",
      dataHora: menosMinutos(11),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65",
        extra: "Relatado novamente na saída"
      }
    },
    {
      id: 7,
      tipo: "observacoes",
      titulo: "Nova observação registrada",
      texto: 'Gabriel digitou na observação: "Pneu dianteiro com pressão baixa e material incompleto."',
      dataHora: menosMinutos(9),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65"
      }
    },
    {
      id: 8,
      tipo: "pendentes",
      titulo: "Expediente acima do limite sem fechamento",
      texto: "Gabriel iniciou o expediente há mais de 11 horas e ainda não registrou saída, gerando pendência operacional crítica.",
      dataHora: menosMinutos(5),
      meta: {
        colaborador: "Gabriel",
        veiculo: "Fiat SGH-2E65",
        placa: "SGH-2E65",
        extra: "Acima de 11 horas"
      }
    }
  ];
}

async function carregarAlertas() {
  try {
    const response = await fetch("/api/alertas", {
      headers: { "Accept": "application/json" }
    });

    if (!response.ok) {
      throw new Error("API ainda não disponível");
    }

    const data = await response.json();

    if (Array.isArray(data)) {
      return aplicarEstadoResolvido(data);
    }

    if (Array.isArray(data.alertas)) {
      return aplicarEstadoResolvido(data.alertas);
    }

    throw new Error("Formato inválido");
  } catch {
    return aplicarEstadoResolvido(gerarAlertasMock());
  }
}

function atualizarResumo(alertas) {
  const ativos = alertas.filter((a) => !a.resolvido);

  const countByType = (tipo, semDuplicarReiteracao = false) => {
    let lista = ativos.filter((a) => a.tipo === tipo);

    if (tipo === "veiculo_danificado" && semDuplicarReiteracao) {
      lista = lista.filter((a) => !normalizarTexto(a.titulo).includes("reiterado"));
    }

    return lista.length;
  };

  countColaboradoresAtivos.textContent = countByType("colaboradores_ativos");
  countVeiculosEmUso.textContent = countByType("veiculos_em_uso");
  countChecklistFaltando.textContent = countByType("checklist_faltando");
  countVeiculoDanificado.textContent = countByType("veiculo_danificado", true);
  countObservacoes.textContent = countByType("observacoes");
  countPendentes.textContent = countByType("pendentes");

  heroCriticosQtd.textContent =
    countByType("checklist_faltando") +
    countByType("veiculo_danificado", true) +
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
      alerta.meta?.placa,
      alerta.meta?.extra
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
    heroFiltroDescricao.textContent = "Nenhum card foi selecionado.";
    return;
  }

  heroFiltroAtual.textContent = nomeTipo[typeFilter.value] || "Filtro aplicado";
  heroFiltroDescricao.textContent = "Exibindo alertas relacionados ao card selecionado.";
}

function atualizarResumoHighlight() {
  resumoCards.forEach((card) => {
    card.classList.remove("ativo", "piscando");
    if (card.dataset.filter === typeFilter.value) {
      card.classList.add("ativo", "piscando");
    }
  });
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

  const botaoOkClasse = alerta.resolvido ? "btn-ok resolvido" : "btn-ok";
  const botaoOkTexto = alerta.resolvido ? "Reativar alerta" : "OK";

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
      <button class="${botaoOkClasse}" data-action="toggle-ok" data-id="${alerta.id}">
        ${botaoOkTexto}
      </button>
      <button class="btn-ver" data-action="foco" data-id="${alerta.id}">
        Destacar
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
    `${filtrados.length} alerta(s) encontrados · ${ativos} ativo(s) · ${resolvidos} resolvido(s)`;

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

function destacarCardPorId(id) {
  const card = [...document.querySelectorAll(".alert-card")]
    .find((el) => el.querySelector(`[data-id="${id}"]`));

  if (!card) return;

  card.classList.add("destacado", "piscando");
  card.scrollIntoView({ behavior: "smooth", block: "center" });

  setTimeout(() => {
    card.classList.remove("piscando");
  }, 4000);
}

function configurarEventos() {
  searchInput.addEventListener("input", renderizarAlertas);

  typeFilter.addEventListener("change", () => {
    renderizarAlertas();
  });

  statusFilter.addEventListener("change", renderizarAlertas);

  clearFiltersBtn.addEventListener("click", () => {
    searchInput.value = "";
    typeFilter.value = "";
    statusFilter.value = "ativos";
    renderizarAlertas();
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
    if (!botao) return;

    const action = botao.dataset.action;
    const id = Number(botao.dataset.id);

    if (action === "toggle-ok") {
      alternarResolvido(id);
      return;
    }

    if (action === "foco") {
      destacarCardPorId(id);
    }
  });
}

async function iniciar() {
  alertasBase = await carregarAlertas();

  if (tipoDestacado) {
    typeFilter.value = tipoDestacado;
  }

  atualizarResumo(alertasBase);
  configurarEventos();
  renderizarAlertas();
}

iniciar();