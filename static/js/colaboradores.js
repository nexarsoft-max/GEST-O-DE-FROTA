const registrosColaboradores = [];

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

const adjustModal = document.getElementById("adjustModal");
const closeAdjustModal = document.getElementById("closeAdjustModal");
const cancelAdjustModal = document.getElementById("cancelAdjustModal");
const adjustForm = document.getElementById("adjustForm");
const adjustCollaboratorName = document.getElementById("adjustCollaboratorName");
const adjustCollaboratorInfo = document.getElementById("adjustCollaboratorInfo");
const adjustDate = document.getElementById("adjustDate");
const adjustEntry = document.getElementById("adjustEntry");
const adjustExit = document.getElementById("adjustExit");
const adjustStatus = document.getElementById("adjustStatus");
const adjustReason = document.getElementById("adjustReason");

let registroSelecionadoParaAjuste = null;

function formatarTextoStatus(status) {
  if (status === "finalizado") return "Finalizado";
  if (status === "em_andamento") return "Em andamento";
  if (status === "pendente") return "Pendente";
  return "Status";
}

function formatarClasseStatus(status) {
  if (status === "finalizado") return "status-finalizado";
  if (status === "em_andamento") return "status-em_andamento";
  if (status === "pendente") return "status-pendente";
  return "status-default";
}

function calcularResumoCards(lista) {
  const colaboradoresUnicos = new Set(
    lista.map((item) => item.colaborador?.trim()).filter((item) => item)
  ).size;

  const checklistsRealizados = lista.filter(
    (item) => item.checklistDisponivel === true
  ).length;

  const entradasRegistradas = lista.filter(
    (item) => item.horaEntrada && item.horaEntrada.trim() !== ""
  ).length;

  const saidasRegistradas = lista.filter(
    (item) => item.horaSaida && item.horaSaida.trim() !== ""
  ).length;

  const veiculosUnicos = new Set(
    lista
      .map((item) => `${item.veiculo || ""}-${item.placa || ""}`.trim())
      .filter((item) => item && item !== "-")
  ).size;

  const pendencias = lista.filter((item) => item.status === "pendente").length;

  cardColaboradoresAtivos.textContent = colaboradoresUnicos || "--";
  cardChecklistsRealizados.textContent = checklistsRealizados || "--";
  cardEntradasRegistradas.textContent = entradasRegistradas || "--";
  cardSaidasRegistradas.textContent = saidasRegistradas || "--";
  cardVeiculosEmUso.textContent = veiculosUnicos || "--";
  cardPendencias.textContent = pendencias || "--";
}

function criarBotaoChecklist() {
  return `<button class="action-btn outline" type="button">Ver checklist</button>`;
}

function criarBotaoFoto(rotulo) {
  return `<button class="action-btn ghost" type="button">${rotulo}</button>`;
}

function renderizarTabelaPrincipal(lista) {
  mainTableBody.innerHTML = "";

  if (!lista.length) {
    mainEmptyState.classList.remove("hidden");
    return;
  }

  mainEmptyState.classList.add("hidden");

  lista.forEach((registro, index) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>
        <div class="user-cell">
          <div class="avatar">
            <i class="fa-solid fa-user"></i>
          </div>
          <div>
            <strong>${registro.colaborador || "-"}</strong>
            <span>${registro.setor || "Setor não informado"}</span>
          </div>
        </div>
      </td>
      <td>${registro.veiculo || "-"}${registro.placa ? ` - ${registro.placa}` : ""}</td>
      <td>${registro.data || "-"}</td>
      <td>${registro.horaEntrada || "-"}</td>
      <td>${registro.horaSaida || "-"}</td>
      <td>
        <span class="status-badge ${formatarClasseStatus(registro.status)}">
          ${formatarTextoStatus(registro.status)}
        </span>
      </td>
      <td>${criarBotaoChecklist()}</td>
      <td>${criarBotaoFoto("Ver foto entrada")}</td>
      <td>${criarBotaoFoto("Ver foto saída")}</td>
      <td>
        <div class="table-actions">
          <button
            class="icon-btn adjust-point-btn"
            type="button"
            title="Ajustar ponto"
            data-index="${index}"
          >
            <i class="fa-solid fa-pen-to-square"></i>
          </button>
        </div>
      </td>
    `;

    mainTableBody.appendChild(tr);
  });

  ativarBotoesAjuste(lista, "principal");
}

function renderizarResultadosHistorico(lista) {
  historyResultsBody.innerHTML = "";

  if (!lista.length) {
    historyEmptyState.classList.remove("hidden");
    return;
  }

  historyEmptyState.classList.add("hidden");

  lista.forEach((registro, index) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${registro.colaborador || "-"}</td>
      <td>${registro.veiculo || "-"}</td>
      <td>${registro.placa || "-"}</td>
      <td>${registro.data || "-"}</td>
      <td>${registro.horaEntrada || "-"}</td>
      <td>${registro.horaSaida || "-"}</td>
      <td>
        <span class="status-badge ${formatarClasseStatus(registro.status)}">
          ${formatarTextoStatus(registro.status)}
        </span>
      </td>
      <td>${criarBotaoChecklist()}</td>
      <td>${criarBotaoFoto("Ver foto entrada")}</td>
      <td>${criarBotaoFoto("Ver foto saída")}</td>
      <td>
        <div class="table-actions">
          <button
            class="icon-btn adjust-point-btn"
            type="button"
            title="Ajustar ponto"
            data-index="${index}"
          >
            <i class="fa-solid fa-pen-to-square"></i>
          </button>
        </div>
      </td>
    `;

    historyResultsBody.appendChild(tr);
  });

  ativarBotoesAjuste(lista, "historico");
}

function atualizarCardsHistorico(lista) {
  const total = lista.length;
  const finalizados = lista.filter((item) => item.status === "finalizado").length;
  const emAndamento = lista.filter((item) => item.status === "em_andamento").length;
  const pendentes = lista.filter((item) => item.status === "pendente").length;

  historyResultCount.textContent = total || "--";
  historyFinishedCount.textContent = finalizados || "--";
  historyInProgressCount.textContent = emAndamento || "--";
  historyPendingCount.textContent = pendentes || "--";
}

function normalizarTexto(valor) {
  return (valor || "")
    .toString()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function filtrarRegistros(lista, filtros) {
  return lista.filter((registro) => {
    const nome = normalizarTexto(registro.colaborador);
    const setor = normalizarTexto(registro.setor);
    const veiculo = normalizarTexto(registro.veiculo);
    const placa = normalizarTexto(registro.placa);
    const data = registro.data || "";
    const status = registro.status || "";

    const filtroPessoa = normalizarTexto(filtros.pessoa);
    const filtroVeiculo = normalizarTexto(filtros.veiculo);
    const filtroData = filtros.data || "";
    const filtroStatus = filtros.status || "";

    const passouPessoa =
      !filtroPessoa ||
      nome.includes(filtroPessoa) ||
      setor.includes(filtroPessoa);

    const passouVeiculo =
      !filtroVeiculo ||
      veiculo.includes(filtroVeiculo) ||
      placa.includes(filtroVeiculo);

    const passouData = !filtroData || data === filtroData;
    const passouStatus = !filtroStatus || status === filtroStatus;

    return passouPessoa && passouVeiculo && passouData && passouStatus;
  });
}

function aplicarFiltrosTabelaPrincipal() {
  const termo = normalizarTexto(mainSearchInput.value);
  const status = mainStatusFilter.value;

  const listaFiltrada = registrosColaboradores.filter((registro) => {
    const nome = normalizarTexto(registro.colaborador);
    const setor = normalizarTexto(registro.setor);
    const veiculo = normalizarTexto(registro.veiculo);
    const placa = normalizarTexto(registro.placa);

    const atendeBusca =
      !termo ||
      nome.includes(termo) ||
      setor.includes(termo) ||
      veiculo.includes(termo) ||
      placa.includes(termo);

    const atendeStatus = !status || registro.status === status;

    return atendeBusca && atendeStatus;
  });

  renderizarTabelaPrincipal(listaFiltrada);
}

function montarResumoFiltrosHistorico(filtros) {
  const partes = [];

  if (filtros.pessoa) partes.push(`Colaborador: ${filtros.pessoa}`);
  if (filtros.data) partes.push(`Data: ${filtros.data}`);
  if (filtros.veiculo) partes.push(`Veículo/placa: ${filtros.veiculo}`);
  if (filtros.status) partes.push(`Status: ${formatarTextoStatus(filtros.status)}`);

  if (!partes.length) {
    return "Nenhum filtro aplicado";
  }

  return partes.join(" • ");
}

function aplicarFiltrosHistorico() {
  const filtros = {
    pessoa: historyPerson.value,
    data: historyDate.value,
    veiculo: historyVehicle.value,
    status: historyStatus.value
  };

  const resultados = filtrarRegistros(registrosColaboradores, filtros);

  historyAppliedFilterText.textContent = montarResumoFiltrosHistorico(filtros);
  atualizarCardsHistorico(resultados);
  renderizarResultadosHistorico(resultados);
}

function limparFiltrosHistorico() {
  historyPerson.value = "";
  historyDate.value = "";
  historyVehicle.value = "";
  historyStatus.value = "";

  historyAppliedFilterText.textContent = "Nenhum filtro aplicado";
  atualizarCardsHistorico([]);
  renderizarResultadosHistorico([]);
}

function abrirModalAjuste(registro) {
  registroSelecionadoParaAjuste = registro;

  adjustCollaboratorName.textContent = registro.colaborador || "Registro selecionado";
  adjustCollaboratorInfo.textContent =
    `${registro.veiculo || "Veículo"}${registro.placa ? ` - ${registro.placa}` : ""} • ${registro.data || "Data não informada"}`;

  adjustDate.value = registro.data || "";
  adjustEntry.value = registro.horaEntrada || "";
  adjustExit.value = registro.horaSaida || "";
  adjustStatus.value = "solicitado";
  adjustReason.value = "";

  adjustModal.classList.add("active");
}

function fecharModalAjuste() {
  adjustModal.classList.remove("active");
  registroSelecionadoParaAjuste = null;
  adjustForm.reset();
}

function ativarBotoesAjuste(lista, origem) {
  const seletor =
    origem === "principal"
      ? "#mainTableBody .adjust-point-btn"
      : "#historyResultsBody .adjust-point-btn";

  document.querySelectorAll(seletor).forEach((botao) => {
    botao.addEventListener("click", () => {
      const index = Number(botao.dataset.index);
      const registro = lista[index];

      if (registro) {
        abrirModalAjuste(registro);
      }
    });
  });
}

mainSearchInput.addEventListener("input", aplicarFiltrosTabelaPrincipal);
mainStatusFilter.addEventListener("change", aplicarFiltrosTabelaPrincipal);

filterHistoryButton.addEventListener("click", aplicarFiltrosHistorico);
clearHistoryButton.addEventListener("click", limparFiltrosHistorico);

closeAdjustModal.addEventListener("click", fecharModalAjuste);
cancelAdjustModal.addEventListener("click", fecharModalAjuste);

adjustModal.addEventListener("click", (event) => {
  if (event.target === adjustModal) {
    fecharModalAjuste();
  }
});

adjustForm.addEventListener("submit", (event) => {
  event.preventDefault();
  fecharModalAjuste();
});

calcularResumoCards(registrosColaboradores);
renderizarTabelaPrincipal(registrosColaboradores);
atualizarCardsHistorico([]);
renderizarResultadosHistorico([]);