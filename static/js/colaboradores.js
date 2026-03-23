// =========================
// ESTADO GLOBAL
// =========================
const registrosColaboradores = [];
let expedienteSelecionado = null;
let checklistAtual = [];

// =========================
// ELEMENTOS DOM
// =========================
const mainTableBody = document.getElementById("mainTableBody");
const mainEmptyState = document.getElementById("mainEmptyState");
const mainSearchInput = document.getElementById("mainSearchInput");
const mainStatusFilter = document.getElementById("mainStatusFilter");

const historyPerson = document.getElementById("historyPerson");
const historyDate = document.getElementById("historyDate");
const historyVehicle = document.getElementById("historyVehicle");
const historyStatus = document.getElementById("historyStatus");
const filterHistoryButton = document.getElementById("filterHistoryButton");
const clearHistoryButton = document.getElementById("clearHistoryButton");
const historyResultsBody = document.getElementById("historyResultsBody");
const historyEmptyState = document.getElementById("historyEmptyState");
const historyAppliedFilterText = document.getElementById("historyAppliedFilterText");

const historyResultCount = document.getElementById("historyResultCount");
const historyFinishedCount = document.getElementById("historyFinishedCount");
const historyInProgressCount = document.getElementById("historyInProgressCount");
const historyPendingCount = document.getElementById("historyPendingCount");

const cardColaboradoresAtivos = document.getElementById("cardColaboradoresAtivos");
const cardChecklistsRealizados = document.getElementById("cardChecklistsRealizados");
const cardEntradasRegistradas = document.getElementById("cardEntradasRegistradas");
const cardSaidasRegistradas = document.getElementById("cardSaidasRegistradas");
const cardVeiculosEmUso = document.getElementById("cardVeiculosEmUso");
const cardPendencias = document.getElementById("cardPendencias");

// =========================
// CHECKLIST PADRÃO
// =========================
const checklistPadrao = [
  "power meet pon",
  "Step",
  "Cones",
  "bobina de fibra",
  "Escada principal",
  "Escada de alumínio",
  "martelete",
  "kit FTTH",
  "Kit EPI"
];

// =========================
// HELPERS
// =========================
function normalizarTexto(valor) {
  return (valor || "")
    .toString()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatarTextoStatus(status) {
  if (status === "finalizado") return "Encerrou o ciclo";
  if (status === "em_andamento") return "Em andamento";
  if (status === "pendente") return "Faltando fechar";
  return status || "-";
}

function formatarClasseStatus(status) {
  if (status === "finalizado") return "status-finalizado";
  if (status === "em_andamento") return "status-andamento";
  if (status === "pendente") return "status-pendente";
  return "";
}

function montarTextoFiltrosHistorico(filtros) {
  const partes = [];

  if (filtros.pessoa) partes.push(`colaborador: ${filtros.pessoa}`);
  if (filtros.data) partes.push(`data: ${filtros.data}`);
  if (filtros.veiculo) partes.push(`veículo/placa: ${filtros.veiculo}`);
  if (filtros.status) partes.push(`status: ${formatarTextoStatus(filtros.status)}`);

  return partes.length ? partes.join(" | ") : "Nenhum filtro aplicado";
}

function escaparHtml(texto) {
  return (texto || "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// =========================
// CARREGAR REGISTROS
// =========================
async function carregarRegistros() {
  try {
    const res = await fetch("/api/colaboradores/registros");
    const data = await res.json();

    registrosColaboradores.length = 0;
    registrosColaboradores.push(...data);

    renderizarTabelaPrincipal(registrosColaboradores);
    renderizarHistorico([]);
    calcularResumoCards(registrosColaboradores);
    resetarCardsHistorico();
  } catch (e) {
    console.error("Erro ao carregar registros:", e);
  }
}

// =========================
// CARDS SUPERIORES
// =========================
function calcularResumoCards(lista) {
  const colaboradoresUnicos = new Set(
    lista.map((item) => normalizarTexto(item.colaborador)).filter(Boolean)
  ).size;

  const checklistsRealizados = lista.filter((item) => item.checklistDisponivel === true).length;
  const entradas = lista.filter((item) => item.horaEntrada).length;
  const saidas = lista.filter((item) => item.horaSaida).length;

  const veiculos = new Set(
    lista
      .filter((item) => item.veiculo || item.placa)
      .map((item) => `${normalizarTexto(item.veiculo)}|${normalizarTexto(item.placa)}`)
  ).size;

  const pendencias = lista.filter((item) => item.status === "pendente").length;

  if (cardColaboradoresAtivos) cardColaboradoresAtivos.textContent = colaboradoresUnicos || "--";
  if (cardChecklistsRealizados) cardChecklistsRealizados.textContent = checklistsRealizados || "--";
  if (cardEntradasRegistradas) cardEntradasRegistradas.textContent = entradas || "--";
  if (cardSaidasRegistradas) cardSaidasRegistradas.textContent = saidas || "--";
  if (cardVeiculosEmUso) cardVeiculosEmUso.textContent = veiculos || "--";
  if (cardPendencias) cardPendencias.textContent = pendencias || "--";
}

// =========================
// TABELA PRINCIPAL
// =========================
function renderizarTabelaPrincipal(lista) {
  if (!mainTableBody) return;

  mainTableBody.innerHTML = "";

  if (!lista.length) {
    if (mainEmptyState) mainEmptyState.style.display = "flex";
    return;
  }

  if (mainEmptyState) mainEmptyState.style.display = "none";

  lista.forEach((r) => {
    const tr = document.createElement("tr");

    const checklistBotao = `
      <button type="button" class="btn-link-action" onclick="verChecklist(${r.id})">
        Ver
      </button>
    `;

    const ajusteBotao = `
      <button type="button" class="btn-link-action" onclick="abrirAjuste(${r.id})">
        ${r.ajustado ? "Ajustado" : "Ajustar"}
      </button>
    `;

    tr.innerHTML = `
      <td>${escaparHtml(r.colaborador || "-")}</td>
      <td>${escaparHtml(`${r.veiculo || "-"} ${r.placa || ""}`.trim())}</td>
      <td>${escaparHtml(r.data || "-")}</td>
      <td>${escaparHtml(r.horaEntrada || "-")}</td>
      <td>${escaparHtml(r.horaSaida || "-")}</td>
      <td>
        <span class="status-badge ${formatarClasseStatus(r.status)}">
          ${formatarTextoStatus(r.status)}
        </span>
      </td>
      <td>${checklistBotao}</td>
      <td>
        ${r.fotoEntrada ? `<a href="${r.fotoEntrada}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}
      </td>
      <td>
        ${r.fotoSaida ? `<a href="${r.fotoSaida}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}
      </td>
      <td>${ajusteBotao}</td>
    `;

    mainTableBody.appendChild(tr);
  });
}

// =========================
// FILTRO TABELA PRINCIPAL
// =========================
function aplicarFiltrosTabelaPrincipal() {
  const termo = normalizarTexto(mainSearchInput ? mainSearchInput.value : "");
  const status = mainStatusFilter ? mainStatusFilter.value : "";

  const listaFiltrada = registrosColaboradores.filter((r) => {
    const nome = normalizarTexto(r.colaborador);
    const veiculo = normalizarTexto(r.veiculo);
    const placa = normalizarTexto(r.placa);

    const matchBusca =
      !termo ||
      nome.includes(termo) ||
      veiculo.includes(termo) ||
      placa.includes(termo);

    const matchStatus = !status || r.status === status;

    return matchBusca && matchStatus;
  });

  renderizarTabelaPrincipal(listaFiltrada);
}

// =========================
// HISTÓRICO
// =========================
function renderizarHistorico(lista) {
  if (!historyResultsBody) return;

  historyResultsBody.innerHTML = "";

  if (!lista.length) {
    if (historyEmptyState) historyEmptyState.style.display = "flex";
    return;
  }

  if (historyEmptyState) historyEmptyState.style.display = "none";

  lista.forEach((r) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${escaparHtml(r.colaborador || "-")}</td>
      <td>${escaparHtml(r.veiculo || "-")}</td>
      <td>${escaparHtml(r.placa || "-")}</td>
      <td>${escaparHtml(r.data || "-")}</td>
      <td>${escaparHtml(r.horaEntrada || "-")}</td>
      <td>${escaparHtml(r.horaSaida || "-")}</td>
      <td>
        <span class="status-badge ${formatarClasseStatus(r.status)}">
          ${formatarTextoStatus(r.status)}
        </span>
      </td>
      <td>
        <button type="button" class="btn-link-action" onclick="verChecklist(${r.id})">Ver</button>
      </td>
      <td>
        ${r.fotoEntrada ? `<a href="${r.fotoEntrada}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}
      </td>
      <td>
        ${r.fotoSaida ? `<a href="${r.fotoSaida}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}
      </td>
      <td>
        <button type="button" class="btn-link-action" onclick="abrirAjuste(${r.id})">
          ${r.ajustado ? "Ajustado" : "Ajustar"}
        </button>
      </td>
    `;

    historyResultsBody.appendChild(tr);
  });
}

function resetarCardsHistorico() {
  if (historyResultCount) historyResultCount.textContent = "--";
  if (historyFinishedCount) historyFinishedCount.textContent = "--";
  if (historyInProgressCount) historyInProgressCount.textContent = "--";
  if (historyPendingCount) historyPendingCount.textContent = "--";
  if (historyAppliedFilterText) historyAppliedFilterText.textContent = "Nenhum filtro aplicado";
}

function aplicarFiltrosHistorico() {
  const filtros = {
    pessoa: normalizarTexto(historyPerson ? historyPerson.value : ""),
    data: historyDate ? historyDate.value : "",
    veiculo: normalizarTexto(historyVehicle ? historyVehicle.value : ""),
    status: historyStatus ? historyStatus.value : ""
  };

  const resultados = registrosColaboradores.filter((r) => {
    const nome = normalizarTexto(r.colaborador);
    const veiculo = normalizarTexto(r.veiculo);
    const placa = normalizarTexto(r.placa);

    const matchPessoa = !filtros.pessoa || nome.includes(filtros.pessoa);
    const matchData = !filtros.data || r.data === filtros.data;
    const matchVeiculo =
      !filtros.veiculo ||
      veiculo.includes(filtros.veiculo) ||
      placa.includes(filtros.veiculo);
    const matchStatus = !filtros.status || r.status === filtros.status;

    return matchPessoa && matchData && matchVeiculo && matchStatus;
  });

  renderizarHistorico(resultados);

  if (historyResultCount) historyResultCount.textContent = resultados.length || 0;
  if (historyFinishedCount) {
    historyFinishedCount.textContent =
      resultados.filter((r) => r.status === "finalizado").length || 0;
  }
  if (historyInProgressCount) {
    historyInProgressCount.textContent =
      resultados.filter((r) => r.status === "em_andamento").length || 0;
  }
  if (historyPendingCount) {
    historyPendingCount.textContent =
      resultados.filter((r) => r.status === "pendente").length || 0;
  }
  if (historyAppliedFilterText) {
    historyAppliedFilterText.textContent = montarTextoFiltrosHistorico(filtros);
  }
}

// =========================
// HELPER PARA NORMALIZAR CHECKLIST
// =========================
function normalizarChecklistParaLista(valor) {
  if (valor == null) return [];

  if (Array.isArray(valor)) {
    return valor.map((item) => String(item));
  }

  if (typeof valor === "string") {
    const texto = valor.trim();
    if (!texto) return [];

    try {
      return normalizarChecklistParaLista(JSON.parse(texto));
    } catch {
      return [texto];
    }
  }

  if (typeof valor === "object") {
    const chavesPreferidas = [
      "itens",
      "items",
      "checklist",
      "checklist_entrada",
      "checklist_saida"
    ];

    for (const chave of chavesPreferidas) {
      if (Array.isArray(valor[chave])) {
        return valor[chave].map((item) => String(item));
      }
    }

    const marcados = [];
    for (const [chave, v] of Object.entries(valor)) {
      const valorTexto = String(v).trim().toLowerCase();

      if (
        v === true ||
        valorTexto === "ok" ||
        valorTexto === "sim" ||
        valorTexto === "true" ||
        valorTexto === "1" ||
        valorTexto === "conforme"
      ) {
        marcados.push(String(chave));
      }
    }

    return marcados;
  }

  return [String(valor)];
}

// =========================
// VER CHECKLIST
// =========================
async function verChecklist(id) {
  try {
    const res = await fetch(`/api/colaboradores/${id}/detalhe`);
    const data = await res.json();

    if (!res.ok || data.sucesso === false) {
      throw new Error(data.erro || "Erro ao carregar checklist");
    }

    const entrada = normalizarChecklistParaLista(data.checklist_entrada);
    const saida = normalizarChecklistParaLista(data.checklist_saida);

    const listaEntrada = document.getElementById("listaChecklistEntrada");
    const listaSaida = document.getElementById("listaChecklistSaida");

    listaEntrada.innerHTML = "";
    listaSaida.innerHTML = "";

    if (entrada.length === 0) {
      listaEntrada.innerHTML = "<li>Sem checklist</li>";
    } else {
      entrada.forEach(item => {
        listaEntrada.innerHTML += `<li>✔ ${item}</li>`;
      });
    }

    if (saida.length === 0) {
      listaSaida.innerHTML = "<li>Sem checklist</li>";
    } else {
      saida.forEach(item => {
        listaSaida.innerHTML += `<li>✔ ${item}</li>`;
      });
    }

    document.getElementById("modalChecklist").classList.remove("hidden");

  } catch (e) {
    console.error(e);
    alert("Erro ao carregar checklist");
  }
}

function fecharModalChecklist() {
  document.getElementById("modalChecklist").classList.add("hidden");
}
// =========================
// ABRIR AJUSTE
// =========================
async function abrirAjuste(id) {
  try {
    expedienteSelecionado = id;

    const res = await fetch(`/api/colaboradores/${id}/detalhe`);
    const data = await res.json();

    if (!res.ok || data.sucesso === false) {
      throw new Error(data.erro || "Erro ao abrir ajuste");
    }

    checklistAtual = normalizarChecklistParaLista(data.checklist_entrada);

    const inputEntrada = document.getElementById("ajusteEntrada");
    const inputSaida = document.getElementById("ajusteSaida");
    const inputMotivo = document.getElementById("ajusteMotivo");

    if (inputEntrada) inputEntrada.value = data.horaEntrada || "";
    if (inputSaida) inputSaida.value = data.horaSaida || "";
    if (inputMotivo) inputMotivo.value = "";

    const fotoEntradaPreview = document.getElementById("fotoEntradaPreview");
    const fotoSaidaPreview = document.getElementById("fotoSaidaPreview");

    if (fotoEntradaPreview) {
      fotoEntradaPreview.innerHTML = data.fotoEntrada
        ? `<a href="${data.fotoEntrada}" target="_blank" rel="noopener noreferrer">Ver foto entrada</a>`
        : "-";
    }

    if (fotoSaidaPreview) {
      fotoSaidaPreview.innerHTML = data.fotoSaida
        ? `<a href="${data.fotoSaida}" target="_blank" rel="noopener noreferrer">Ver foto saída</a>`
        : "-";
    }

    renderChecklistModal();

    const modal = document.getElementById("modalAjuste");
    if (modal) modal.classList.remove("hidden");
  } catch (e) {
    console.error("Erro ao abrir ajuste:", e);
    alert(e.message || "Erro ao abrir ajuste.");
  }
}

// =========================
// RENDER CHECKLIST NO MODAL
// =========================
function renderChecklistModal() {
  const container = document.getElementById("checklistContainer");
  if (!container) return;

  container.innerHTML = checklistPadrao
    .map(
      (item) => `
        <label style="display:block; margin-bottom:8px;">
          <input
            type="checkbox"
            value="${item}"
            ${checklistAtual.includes(item) ? "checked" : ""}
          >
          ${item}
        </label>
      `
    )
    .join("");
}

// =========================
// FECHAR MODAL
// =========================
function fecharModal() {
  const modal = document.getElementById("modalAjuste");
  if (modal) modal.classList.add("hidden");

  expedienteSelecionado = null;
  checklistAtual = [];
}

// =========================
// SALVAR AJUSTE
// =========================
async function salvarAjuste() {
  try {
    const entrada = document.getElementById("ajusteEntrada")?.value || "";
    const saida = document.getElementById("ajusteSaida")?.value || "";
    const motivo = document.getElementById("ajusteMotivo")?.value || "";

    const checkboxes = document.querySelectorAll("#checklistContainer input:checked");
    const checklist = Array.from(checkboxes).map((cb) => cb.value);

    const res = await fetch("/api/colaboradores/ajuste", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        id: expedienteSelecionado,
        entrada,
        saida,
        checklist,
        motivo
      })
    });

    const data = await res.json();

    if (!res.ok || data.sucesso !== true) {
      throw new Error(data.erro || "Erro ao salvar ajuste");
    }

    fecharModal();
    await carregarRegistros();
    aplicarFiltrosTabelaPrincipal();
    aplicarFiltrosHistorico();
  } catch (e) {
    console.error("Erro ao salvar ajuste:", e);
    alert(e.message || "Erro ao salvar ajuste.");
  }
}

// =========================
// EVENTOS
// =========================
if (mainSearchInput) {
  mainSearchInput.addEventListener("input", aplicarFiltrosTabelaPrincipal);
}

if (mainStatusFilter) {
  mainStatusFilter.addEventListener("change", aplicarFiltrosTabelaPrincipal);
}

if (filterHistoryButton) {
  filterHistoryButton.addEventListener("click", aplicarFiltrosHistorico);
}

if (clearHistoryButton) {
  clearHistoryButton.addEventListener("click", () => {
    if (historyPerson) historyPerson.value = "";
    if (historyDate) historyDate.value = "";
    if (historyVehicle) historyVehicle.value = "";
    if (historyStatus) historyStatus.value = "";

    renderizarHistorico([]);
    resetarCardsHistorico();
  });
}

// =========================
// INIT
// =========================
document.addEventListener("DOMContentLoaded", () => {
  carregarRegistros();
});