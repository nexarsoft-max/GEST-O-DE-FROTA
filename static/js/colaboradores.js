// =========================
// ESTADO GLOBAL
// =========================
const registrosColaboradores = [];

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

const historyResultCount = document.getElementById("historyResultCount");
const historyFinishedCount = document.getElementById("historyFinishedCount");
const historyInProgressCount = document.getElementById("historyInProgressCount");
const historyPendingCount = document.getElementById("historyPendingCount");

const cardColaboradoresAtivos = document.getElementById("cardColaboradoresAtivos");
const cardEntradasRegistradas = document.getElementById("cardEntradasRegistradas");
const cardSaidasRegistradas = document.getElementById("cardSaidasRegistradas");
const cardVeiculosEmUso = document.getElementById("cardVeiculosEmUso");
const cardPendencias = document.getElementById("cardPendencias");

// =========================
// CARREGAR DADOS (API)
// =========================
async function carregarRegistros() {
  try {
    const res = await fetch("/api/colaboradores/registros");
    const data = await res.json();

    registrosColaboradores.length = 0;
    registrosColaboradores.push(...data);

    renderizarTabelaPrincipal(registrosColaboradores);
    calcularResumoCards(registrosColaboradores);
    renderizarHistorico([]);
  } catch (e) {
    console.error("Erro ao carregar registros:", e);
  }
}

// =========================
// FORMATADORES
// =========================
function formatarTextoStatus(status) {
  if (status === "finalizado") return "Encerrou o ciclo";
  if (status === "em_andamento") return "Faltando fechar";
  if (status === "pendente") return "Faltando fechar";
  return "Status";
}

function formatarClasseStatus(status) {
  if (status === "finalizado") return "status-finalizado";
  if (status === "em_andamento") return "status-em_andamento";
  if (status === "pendente") return "status-pendente";
  return "status-default";
}

// =========================
// CARDS
// =========================
function calcularResumoCards(lista) {
  const colaboradoresUnicos = new Set(
    lista.map((item) => item.colaborador).filter(Boolean)
  ).size;

  const entradas = lista.filter((item) => item.horaEntrada).length;
  const saidas = lista.filter((item) => item.horaSaida).length;

  const veiculos = new Set(
    lista
      .filter((item) => item.veiculo || item.placa)
      .map((item) => `${item.veiculo || ""}-${item.placa || ""}`)
  ).size;

  // expediente aberto = pendência operacional
  const pendencias = lista.filter((item) => item.status === "em_andamento").length;

  cardColaboradoresAtivos.textContent = colaboradoresUnicos || "--";
  cardEntradasRegistradas.textContent = entradas || "--";
  cardSaidasRegistradas.textContent = saidas || "--";
  cardVeiculosEmUso.textContent = veiculos || "--";
  cardPendencias.textContent = pendencias || "--";
}

// =========================
// TABELA PRINCIPAL
// =========================
function renderizarTabelaPrincipal(lista) {
  mainTableBody.innerHTML = "";

  if (!lista.length) {
    mainEmptyState.classList.remove("hidden");
    return;
  }

  mainEmptyState.classList.add("hidden");

  lista.forEach((registro) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${registro.colaborador || "-"}</td>
      <td>${registro.veiculo || "-"} ${registro.placa || ""}</td>
      <td>${registro.data || "-"}</td>
      <td>${registro.horaEntrada || "-"}</td>
      <td>${registro.horaSaida || "-"}</td>
      <td>
        <span class="status-badge ${formatarClasseStatus(registro.status)}">
          ${formatarTextoStatus(registro.status)}
        </span>
      </td>

      <td>-</td>

      <td>
        ${registro.fotoEntrada
          ? `<a href="${registro.fotoEntrada}" target="_blank" rel="noopener noreferrer">Ver</a>`
          : "-"}
      </td>

      <td>
        ${registro.fotoSaida
          ? `<a href="${registro.fotoSaida}" target="_blank" rel="noopener noreferrer">Ver</a>`
          : "-"}
      </td>

      <td>${registro.ajustado ? "Ajustado" : "-"}</td>
    `;

    mainTableBody.appendChild(tr);
  });
}

// =========================
// FILTRO BUSCA
// =========================
function normalizarTexto(valor) {
  return (valor || "")
    .toString()
    .toLowerCase()
    .trim();
}

function aplicarFiltrosTabelaPrincipal() {
  const termo = normalizarTexto(mainSearchInput.value);
  const status = mainStatusFilter.value;

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
  historyResultsBody.innerHTML = "";

  if (!lista.length) {
    historyEmptyState.classList.remove("hidden");
    return;
  }

  historyEmptyState.classList.add("hidden");

  lista.forEach((r) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${r.colaborador || "-"}</td>
      <td>${r.veiculo || "-"}</td>
      <td>${r.placa || "-"}</td>
      <td>${r.data || "-"}</td>
      <td>${r.horaEntrada || "-"}</td>
      <td>${r.horaSaida || "-"}</td>
      <td>${formatarTextoStatus(r.status)}</td>
      <td>-</td>
      <td>${r.fotoEntrada ? `<a href="${r.fotoEntrada}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}</td>
      <td>${r.fotoSaida ? `<a href="${r.fotoSaida}" target="_blank" rel="noopener noreferrer">Ver</a>` : "-"}</td>
      <td>${r.ajustado ? "Ajustado" : "-"}</td>
    `;

    historyResultsBody.appendChild(tr);
  });
}

function aplicarFiltrosHistorico() {
  const filtros = {
    pessoa: normalizarTexto(historyPerson.value),
    data: historyDate.value,
    veiculo: normalizarTexto(historyVehicle.value),
    status: historyStatus.value
  };

  const resultados = registrosColaboradores.filter((r) => {
    const colaborador = normalizarTexto(r.colaborador);
    const veiculo = normalizarTexto(r.veiculo);
    const placa = normalizarTexto(r.placa);

    return (
      (!filtros.pessoa || colaborador.includes(filtros.pessoa)) &&
      (!filtros.data || r.data === filtros.data) &&
      (!filtros.veiculo || veiculo.includes(filtros.veiculo) || placa.includes(filtros.veiculo)) &&
      (!filtros.status || r.status === filtros.status)
    );
  });

  renderizarHistorico(resultados);

  historyResultCount.textContent = resultados.length;
  historyFinishedCount.textContent = resultados.filter((r) => r.status === "finalizado").length;
  historyInProgressCount.textContent = resultados.filter((r) => r.status === "em_andamento").length;
  historyPendingCount.textContent = resultados.filter((r) => r.status === "em_andamento").length;
}

// =========================
// EVENTOS
// =========================
mainSearchInput.addEventListener("input", aplicarFiltrosTabelaPrincipal);
mainStatusFilter.addEventListener("change", aplicarFiltrosTabelaPrincipal);

filterHistoryButton.addEventListener("click", aplicarFiltrosHistorico);
clearHistoryButton.addEventListener("click", () => {
  historyPerson.value = "";
  historyDate.value = "";
  historyVehicle.value = "";
  historyStatus.value = "";
  renderizarHistorico([]);
  historyResultCount.textContent = "--";
  historyFinishedCount.textContent = "--";
  historyInProgressCount.textContent = "--";
  historyPendingCount.textContent = "--";
});

// =========================
// INICIALIZAÇÃO
// =========================
document.addEventListener("DOMContentLoaded", () => {
  carregarRegistros();
});