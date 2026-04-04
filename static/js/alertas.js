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
let abaAtual = "ativos";

function inserirAbasSeNaoExistirem() {
  return;
}

function aplicarEstiloAbasSeNaoExistir() {
  if (document.getElementById("estiloAbasAlertasJs")) return;

  const style = document.createElement("style");
  style.id = "estiloAbasAlertasJs";
  style.textContent = `
    .abas-alertas{
      display:flex;
      gap:10px;
      margin-top:14px;
      flex-wrap:wrap;
    }
    .aba-alerta{
      min-height:42px;
      padding:0 16px;
      border-radius:12px;
      border:1px solid #e7e2f4;
      background:#fff;
      color:#322d44;
      font-size:13px;
      font-weight:800;
      cursor:pointer;
      transition:.18s ease;
    }
    .aba-alerta:hover{
      background:#f8f5ff;
      border-color:#d8cbff;
    }
    .aba-alerta.ativa{
      background:linear-gradient(135deg, #6f2cff, #9b5cff);
      color:#fff;
      border-color:transparent;
      box-shadow:0 12px 22px rgba(111,44,255,0.18);
    }
    .btn-pdf{
      min-width:132px;
      min-height:44px;
      border-radius:14px;
      padding:0 16px;
      border:1px solid #e2dff0;
      background:#ffffff;
      color:#27233a;
      font-size:13px;
      font-weight:800;
      cursor:pointer;
      transition:.18s ease;
    }
    .btn-pdf:hover{
      background:#f7f4fd;
      transform:translateY(-1px);
    }
  `;
  document.head.appendChild(style);
}

function obterTipoDaUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("tipo") || "";
}

function obterResolvidos() {
  return {};
}

function aplicarEstadoResolvido(alertas) {
  return alertas.map((alerta) => ({
    ...alerta,
    resolvido: alerta.resolvido === true
  }));
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
  return valor || "-";
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



async function carregarAlertas() {
  const response = await fetch("/api/alertas", {
    headers: { Accept: "application/json" }
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

  if (countColaboradoresAtivos) countColaboradoresAtivos.textContent = countByType("colaboradores_ativos") || "--";
  if (countVeiculosEmUso) countVeiculosEmUso.textContent = countByType("veiculos_em_uso") || "--";
  if (countChecklistFaltando) countChecklistFaltando.textContent = countByType("checklist_faltando") || "--";
  if (countVeiculoDanificado) countVeiculoDanificado.textContent = countByType("veiculo_danificado") || "--";
  if (countObservacoes) countObservacoes.textContent = countByType("observacoes") || "--";
  if (countPendentes) countPendentes.textContent = countByType("pendentes") || "--";

  if (heroCriticosQtd) {
    heroCriticosQtd.textContent =
      countByType("checklist_faltando") +
      countByType("veiculo_danificado") +
      countByType("pendentes");
  }
}

function obterAlertasFiltrados() {
  const termo = normalizarTexto(searchInput ? searchInput.value : "");
  const tipo = typeFilter ? typeFilter.value : "";

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
    const matchAba = abaAtual === "ativos" ? !alerta.resolvido : alerta.resolvido;

    return matchTexto && matchTipo && matchAba;
  });
}

function atualizarTextoTopo() {
  const tipoAtual = typeFilter ? typeFilter.value : "";

  if (!tipoAtual) {
    if (heroFiltroAtual) heroFiltroAtual.textContent = "Todos os alertas";
    if (heroFiltroDescricao) {
      heroFiltroDescricao.textContent =
        abaAtual === "ativos"
          ? "Exibição dos alertas não resolvidos."
          : "Exibição do histórico de alertas resolvidos.";
    }
    return;
  }

  if (heroFiltroAtual) heroFiltroAtual.textContent = nomeTipo[tipoAtual] || "Filtro aplicado";
  if (heroFiltroDescricao) {
    heroFiltroDescricao.textContent =
      abaAtual === "ativos"
        ? "Lista exibida conforme o tipo de alerta selecionado."
        : "Histórico exibido conforme o tipo de alerta selecionado.";
  }
}

function atualizarResumoHighlight() {
  const tipoAtual = typeFilter ? typeFilter.value : "";

  resumoCards.forEach((card) => {
    card.classList.remove("ativo", "piscando");
    if (card.dataset.filter === tipoAtual) {
      card.classList.add("ativo", "piscando");
    }
  });
}

function irParaColaboradores(alerta) {
  if (!alerta?.expediente_id) return;
  const url = `/colaboradores?expediente_id=${encodeURIComponent(alerta.expediente_id)}&tipo=${encodeURIComponent(alerta.tipo || "")}`;
  window.location.href = url;
}

function gerarPdfAlerta(alerta) {
  if (!alerta || !alerta.expediente_id) {
    console.error("Alerta inválido para PDF", alerta);
    alert("Não foi possível gerar o PDF deste alerta.");
    return;
  }

  const url = `/api/alertas/pdf/${encodeURIComponent(alerta.expediente_id)}`;
  window.location.href = url;
}

async function resolverNoBackend(alerta) {
  const response = await fetch("/api/alertas/resolver", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json"
    },
    body: JSON.stringify({
      alerta_id: String(alerta.id),
      tipo: String(alerta.tipo || ""),
      expediente_id: alerta.expediente_id || null
    })
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok || data.sucesso === false) {
    throw new Error(data.erro || "Falha ao resolver alerta no backend");
  }

  return data;
}


async function desresolverNoBackend(alertaId) {
  const response = await fetch(`/api/alertas/resolver/${encodeURIComponent(alertaId)}`, {
    method: "DELETE",
    headers: {
      "Accept": "application/json"
    }
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok || data.sucesso === false) {
    throw new Error(data.erro || "Falha ao desresolver alerta no backend");
  }

  return data;
}

function criarCard(alerta) {
  const critico = classificaCritico(alerta.tipo);
  const card = document.createElement("article");

  card.className = [
    "alert-card",
    critico ? "critico" : "",
    alerta.resolvido ? "resolvido" : "",
    typeFilter && typeFilter.value && alerta.tipo === typeFilter.value ? "destacado piscando" : ""
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
      <button class="${botaoOkClasse}" data-action="toggle-ok" data-id="${alerta.id}">
        ${botaoOkTexto}
      </button>

      ${critico ? `
        <button class="btn-pdf" data-action="pdf" data-id="${alerta.id}">
          Gerar PDF
        </button>
      ` : `<div></div>`}

      <button class="btn-ver" data-action="go" data-id="${alerta.id}">
        Abrir registro
      </button>
    </div>
  `;

  return card;
}

function renderizarAlertas() {
  const filtrados = obterAlertasFiltrados();

  if (alertList) alertList.innerHTML = "";

  atualizarTextoTopo();
  atualizarResumoHighlight();

  if (!filtrados.length) {
    if (emptyState) emptyState.classList.remove("hidden");
    if (resultadoTexto) {
      resultadoTexto.textContent =
        abaAtual === "ativos"
          ? "Nenhum alerta não resolvido encontrado com os filtros atuais."
          : "Nenhum alerta resolvido encontrado com os filtros atuais.";
    }
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");

  const ativos = filtrados.filter((a) => !a.resolvido).length;
  const resolvidos = filtrados.filter((a) => a.resolvido).length;

  if (resultadoTexto) {
    resultadoTexto.textContent =
      `${filtrados.length} alerta(s) encontrados · ${ativos} ativo(s) · ${resolvidos} concluído(s)`;
  }

  filtrados.forEach((alerta) => {
    if (alertList) alertList.appendChild(criarCard(alerta));
  });
}

async function alternarResolvido(id) {
  const alerta = obterAlertaPorId(id);
  if (!alerta) return;

  try {
    if (alerta.resolvido) {
      await desresolverNoBackend(String(id));
      abaAtual = "ativos";
    } else {
      await resolverNoBackend(alerta);
      abaAtual = "historico";
    }

    alertasBase = await carregarAlertas();
    atualizarResumo(alertasBase);
    renderizarAlertas();

    document.querySelectorAll(".aba-alerta").forEach((btn) => {
      btn.classList.remove("ativa");
      if (btn.dataset.tab === abaAtual) {
        btn.classList.add("ativa");
      }
    });
  } catch (e) {
    console.error("Erro ao alternar alerta resolvido:", e);
    alert("Não foi possível atualizar o alerta.");
  }
}

function obterAlertaPorId(id) {
  return alertasBase.find((item) => String(item.id) === String(id)) || null;
}

function configurarEventos() {
  if (searchInput) searchInput.addEventListener("input", renderizarAlertas);
  if (typeFilter) typeFilter.addEventListener("change", renderizarAlertas);

  if (statusFilter) {
    statusFilter.addEventListener("change", () => {
      renderizarAlertas();
    });
  }

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      if (typeFilter) typeFilter.value = "";
      if (statusFilter) statusFilter.value = "";
      abaAtual = "ativos";

      document.querySelectorAll(".aba-alerta").forEach((btn) => {
        btn.classList.remove("ativa");
        if (btn.dataset.tab === "ativos") btn.classList.add("ativa");
      });

      renderizarAlertas();
      window.history.replaceState({}, "", window.location.pathname);
    });
  }

  resumoCards.forEach((card) => {
    card.addEventListener("click", () => {
      if (typeFilter) typeFilter.value = card.dataset.filter || "";
      renderizarAlertas();
      window.history.replaceState({}, "", `${window.location.pathname}?tipo=${typeFilter ? typeFilter.value : ""}`);
    });
  });

  document.querySelectorAll(".aba-alerta").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".aba-alerta").forEach((b) => b.classList.remove("ativa"));
      btn.classList.add("ativa");
      abaAtual = btn.dataset.tab || "ativos";
      renderizarAlertas();
    });
  });

  if (alertList) {
    alertList.addEventListener("click", async (event) => {
      const botao = event.target.closest("button");
      const card = event.target.closest(".alert-card");

      if (botao) {
        const action = botao.dataset.action;
        const id = botao.dataset.id;
        const alerta = obterAlertaPorId(id);

        if (action === "toggle-ok") {
          event.stopPropagation();
          await alternarResolvido(id);
          return;
        }

        if (action === "go") {
          event.stopPropagation();
          irParaColaboradores(alerta);
          return;
        }

        if (action === "pdf") {
          event.stopPropagation();
          gerarPdfAlerta(alerta);
          return;
        }
      }

      if (card && card.dataset.alertId) {
        const alerta = obterAlertaPorId(card.dataset.alertId);
        irParaColaboradores(alerta);
      }
    });
  }
}

async function iniciar() {
  try {
    inserirAbasSeNaoExistirem();
    aplicarEstiloAbasSeNaoExistir();

    alertasBase = await carregarAlertas();

    if (tipoDestacado && typeFilter) {
      typeFilter.value = tipoDestacado;
    }

    atualizarResumo(alertasBase);
    configurarEventos();
    renderizarAlertas();
  } catch (e) {
    console.error("Erro ao iniciar alertas:", e);
    if (alertList) alertList.innerHTML = "";
    if (emptyState) emptyState.classList.remove("hidden");
    if (resultadoTexto) resultadoTexto.textContent = "Não foi possível carregar os alertas.";
    if (heroFiltroAtual) heroFiltroAtual.textContent = "Falha no carregamento";
    if (heroFiltroDescricao) heroFiltroDescricao.textContent = "A API de alertas não respondeu corretamente.";
    if (heroCriticosQtd) heroCriticosQtd.textContent = "--";
  }
}

iniciar();