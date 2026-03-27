// =========================
// ESTADO GLOBAL
// =========================
const registrosColaboradores = [];

let ajusteExpedienteId = null;
let ajusteChecklistEntradaDetalhe = {};
let ajusteChecklistSaidaDetalhe = {};

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
  "KIT EPI COMPLETO"
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
  if (status === "em_andamento") return "status-em_andamento";
  if (status === "pendente") return "status-pendente";
  return "status-default";
}

function montarTextoFiltrosHistorico(filtros) {
  const partes = [];

  if (filtros.pessoaOriginal) partes.push(`colaborador: ${filtros.pessoaOriginal}`);
  if (filtros.data) partes.push(`data: ${filtros.data}`);
  if (filtros.veiculoOriginal) partes.push(`veículo/placa: ${filtros.veiculoOriginal}`);
  if (filtros.status) partes.push(`status: ${formatarTextoStatus(filtros.status)}`);

  return partes.length ? partes.join(" | ") : "Nenhum filtro aplicado";
}

function escaparAspas(texto) {
  return String(texto || "").replace(/'/g, "\\'");
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

function valorBooleanSelect(valor) {
  if (valor === true) return "true";
  if (valor === false) return "false";
  return "";
}

function normalizarChecklistDetalhe(valor) {
  if (!valor) {
    return {
      itens: [],
      itens_marcados: [],
      veiculo_perfeito: null,
      observacao: "",
      quantidade_cones: "",
      trabalhando_em_dupla_ou_mais: null,
      nomes_dupla_ou_mais: "",
      confirmacao_veracidade: false
    };
  }

  if (Array.isArray(valor)) {
    const itens = valor.map((item) => String(item));
    return {
      itens,
      itens_marcados: itens,
      veiculo_perfeito: null,
      observacao: "",
      quantidade_cones: "",
      trabalhando_em_dupla_ou_mais: null,
      nomes_dupla_ou_mais: "",
      confirmacao_veracidade: false
    };
  }

  if (typeof valor === "object") {
    const itens = Array.isArray(valor.itens)
      ? valor.itens.map((item) => String(item))
      : [];

    const itensMarcados = Array.isArray(valor.itens_marcados)
      ? valor.itens_marcados.map((item) => String(item))
      : itens;

    return {
      itens,
      itens_marcados: itensMarcados,
      veiculo_perfeito: valor.veiculo_perfeito,
      observacao: (valor.observacao || "").toString().trim(),
      quantidade_cones: valor.quantidade_cones || "",
      trabalhando_em_dupla_ou_mais: valor.trabalhando_em_dupla_ou_mais,
      nomes_dupla_ou_mais: valor.nomes_dupla_ou_mais || "",
      confirmacao_veracidade: valor.confirmacao_veracidade === true
    };
  }

  return {
    itens: [String(valor)],
    itens_marcados: [String(valor)],
    veiculo_perfeito: null,
    observacao: "",
    quantidade_cones: "",
    trabalhando_em_dupla_ou_mais: null,
    nomes_dupla_ou_mais: "",
    confirmacao_veracidade: false
  };
}

function montarItensChecklistHtml(lista) {
  if (!Array.isArray(lista) || !lista.length) {
    return `<li class="checklist-vazio">Nenhum item marcado.</li>`;
  }

  return lista
    .map(
      (item) => `
        <li>
          <span class="check-icon"><i class="fa-solid fa-check"></i></span>
          <span>${escaparHtml(item)}</span>
        </li>
      `
    )
    .join("");
}

function aplicarEstado(elemento, valor) {
  if (!elemento) return;

  elemento.classList.remove("bom", "ruim", "neutro");

  if (valor === true) {
    elemento.textContent = "Veículo OK";
    elemento.classList.add("estado-badge", "bom");
  } else if (valor === false) {
    elemento.textContent = "Com problema";
    elemento.classList.add("estado-badge", "ruim");
  } else {
    elemento.textContent = "Não informado";
    elemento.classList.add("estado-badge", "neutro");
  }
}

function aplicarEstadoAjuste(elemento, valor) {
  aplicarEstado(elemento, valor);
}

// =========================
// MODAL IMAGEM
// =========================
function abrirModalImagem(url, titulo = "Visualizar imagem") {
  const modal = document.getElementById("modalImagem");
  const img = document.getElementById("imagemModalPreview");
  const tituloEl = document.getElementById("imagemModalTitulo");

  if (!modal || !img || !url) return;

  if (tituloEl) tituloEl.textContent = titulo;
  img.src = url;
  img.alt = titulo;

  modal.classList.remove("hidden");
  modal.style.display = "flex";
  document.body.style.overflow = "hidden";
}

function fecharModalImagem() {
  const modal = document.getElementById("modalImagem");
  const img = document.getElementById("imagemModalPreview");

  if (img) {
    img.src = "";
    img.alt = "";
  }

  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }

  document.body.style.overflow = "";
}

// =========================
// MODAL CHECKLIST
// =========================
function fecharModalChecklist() {
  const modal = document.getElementById("modalChecklist");
  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }

  document.body.style.overflow = "";
}

async function verChecklist(id) {
  try {
    const res = await fetch(`/api/colaboradores/${id}/detalhe`);
    const data = await res.json();

    if (!res.ok || data.sucesso === false) {
      throw new Error(data.erro || "Erro ao carregar checklist");
    }

    const entrada = normalizarChecklistDetalhe(data.checklist_entrada_detalhe);
    const saida = normalizarChecklistDetalhe(data.checklist_saida_detalhe);

    const listaEntrada = document.getElementById("listaChecklistEntrada");
    const listaSaida = document.getElementById("listaChecklistSaida");

    const estadoEntrada = document.getElementById("checklistEstadoEntrada");
    const estadoSaida = document.getElementById("checklistEstadoSaida");

    const observacaoEntrada = document.getElementById("checklistObservacaoEntrada");
    const observacaoSaida = document.getElementById("checklistObservacaoSaida");

    const horaEntrada = document.getElementById("checklistHoraEntrada");
    const horaSaida = document.getElementById("checklistHoraSaida");

    const modal = document.getElementById("modalChecklist");

    const itensEntrada = entrada.itens_marcados || entrada.itens || [];
    const itensSaida = saida.itens_marcados || saida.itens || [];

    if (listaEntrada) listaEntrada.innerHTML = montarItensChecklistHtml(itensEntrada);
    if (listaSaida) listaSaida.innerHTML = montarItensChecklistHtml(itensSaida);

    aplicarEstado(estadoEntrada, entrada.veiculo_perfeito);
    aplicarEstado(estadoSaida, saida.veiculo_perfeito);

    if (observacaoEntrada) {
      observacaoEntrada.textContent = entrada.observacao || "Sem observação.";
    }

    if (observacaoSaida) {
      observacaoSaida.textContent = saida.observacao || "Sem observação.";
    }

    if (horaEntrada) horaEntrada.textContent = data.horaEntrada || "-";
    if (horaSaida) horaSaida.textContent = data.horaSaida || "-";

    const conesEntrada = document.getElementById("checklistConesEntrada");
    const duplaEntrada = document.getElementById("checklistDuplaEntrada");
    const nomesEntrada = document.getElementById("checklistNomesEntrada");
    const veracidadeEntrada = document.getElementById("checklistVeracidadeEntrada");

    if (conesEntrada) {
      conesEntrada.textContent = entrada.quantidade_cones || "-";
    }

    if (duplaEntrada) {
      duplaEntrada.textContent =
        entrada.trabalhando_em_dupla_ou_mais === true ? "Sim" :
        entrada.trabalhando_em_dupla_ou_mais === false ? "Não" : "-";
    }

    if (nomesEntrada) {
      nomesEntrada.textContent = entrada.nomes_dupla_ou_mais || "-";
    }

    if (veracidadeEntrada) {
      veracidadeEntrada.textContent =
        entrada.confirmacao_veracidade ? "Confirmado" : "Não confirmado";
    }

    const conesSaida = document.getElementById("checklistConesSaida");
    const duplaSaida = document.getElementById("checklistDuplaSaida");
    const nomesSaida = document.getElementById("checklistNomesSaida");
    const veracidadeSaida = document.getElementById("checklistVeracidadeSaida");

    if (conesSaida) {
      conesSaida.textContent = saida.quantidade_cones || "-";
    }

    if (duplaSaida) {
      duplaSaida.textContent =
        saida.trabalhando_em_dupla_ou_mais === true ? "Sim" :
        saida.trabalhando_em_dupla_ou_mais === false ? "Não" : "-";
    }

    if (nomesSaida) {
      nomesSaida.textContent = saida.nomes_dupla_ou_mais || "-";
    }

    if (veracidadeSaida) {
      veracidadeSaida.textContent =
        saida.confirmacao_veracidade ? "Confirmado" : "Não confirmado";
    }

    if (modal) {
      modal.classList.remove("hidden");
      modal.style.display = "flex";
    }

    document.body.style.overflow = "hidden";
  } catch (e) {
    console.error("Erro checklist:", e);
    alert(e.message || "Erro ao carregar checklist.");
  }
}

// =========================
// CARREGAR REGISTROS
// =========================
async function carregarRegistros() {
  try {
    const res = await fetch("/api/colaboradores/registros");
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.erro || "Erro ao carregar registros");
    }

    registrosColaboradores.length = 0;

    if (Array.isArray(data)) {
      registrosColaboradores.push(...data);
    }

    renderizarTabelaPrincipal(registrosColaboradores);
    renderizarHistorico([]);
    calcularResumoCards(registrosColaboradores);
    resetarCardsHistorico();
  } catch (e) {
    console.error("Erro ao carregar registros:", e);
    registrosColaboradores.length = 0;
    renderizarTabelaPrincipal([]);
    renderizarHistorico([]);
    calcularResumoCards([]);
    resetarCardsHistorico();
  }
}

// =========================
// CARDS SUPERIORES
// =========================
function calcularResumoCards(lista) {
  const colaboradoresUnicos = new Set(
    lista.map((item) => normalizarTexto(item.colaborador)).filter(Boolean)
  ).size;

  const checklistsRealizados = lista.filter((item) => {
    return (Array.isArray(item.checklistEntrada) && item.checklistEntrada.length > 0)
      || (Array.isArray(item.checklistSaida) && item.checklistSaida.length > 0);
  }).length;

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
      <button type="button" class="action-btn action-btn-view" onclick="verChecklist(${r.id})">
        <i class="fa-solid fa-clipboard-check"></i>
        <span>Ver checklist</span>
      </button>
    `;

    const ajusteBotao = `
      <button type="button" class="action-btn action-btn-adjust" onclick="abrirAjuste(${r.id})">
        <i class="fa-solid fa-pen-to-square"></i>
        <span>${r.ajustado ? "Ajustado" : "Ajustar"}</span>
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
        ${r.fotoEntrada
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoEntrada)}', 'Foto de entrada')">Ver</button>`
          : "-"}
      </td>

      <td>
        ${r.fotoSaida
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoSaida)}', 'Foto de saída')">Ver</button>`
          : "-"}
      </td>

      <td>
        ${r.fotoOdometro
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoOdometro)}', 'Foto do odômetro')">Ver</button>`
          : "-"}
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
        ${r.fotoEntrada
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoEntrada)}', 'Foto de entrada')">Ver</button>`
          : "-"}
      </td>
      <td>
        ${r.fotoSaida
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoSaida)}', 'Foto de saída')">Ver</button>`
          : "-"}
      </td>
      <td>
        ${r.fotoOdometro
          ? `<button type="button" class="btn-link-action" onclick="abrirModalImagem('${escaparAspas(r.fotoOdometro)}', 'Foto do odômetro')">Ver</button>`
          : "-"}
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
    pessoaOriginal: historyPerson ? historyPerson.value.trim() : "",
    data: historyDate ? historyDate.value : "",
    veiculo: normalizarTexto(historyVehicle ? historyVehicle.value : ""),
    veiculoOriginal: historyVehicle ? historyVehicle.value.trim() : "",
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
// AJUSTE
// =========================
function renderizarPreviewFoto(containerId, url, titulo) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!url || !String(url).trim()) {
    container.innerHTML = `<span class="preview-foto-vazio">Nenhuma imagem disponível.</span>`;
    return;
  }

  container.innerHTML = `
    <div class="preview-foto-card">
      <button
        type="button"
        class="btn-link-action"
        onclick="abrirModalImagem('${escaparAspas(url)}', '${escaparAspas(titulo || "Foto")}')"
      >
        Ver imagem
      </button>
    </div>
  `;
}

function renderizarChecklistEditavel(containerId, detalhe = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const itensMarcados = Array.isArray(detalhe.itens_marcados)
    ? detalhe.itens_marcados
    : Array.isArray(detalhe.itens)
    ? detalhe.itens
    : [];

  container.innerHTML = checklistPadrao
    .map((item) => {
      const marcado = itensMarcados.includes(item);

      return `
        <label class="item-ajuste-checklist">
          <input type="checkbox" value="${escaparHtml(item)}" ${marcado ? "checked" : ""}>
          <span>${escaparHtml(item)}</span>
        </label>
      `;
    })
    .join("");
}

function coletarChecklistEditavel(containerId, detalheOriginal = {}, prefixo = "") {
  const container = document.getElementById(containerId);
  const checks = container ? [...container.querySelectorAll('input[type="checkbox"]')] : [];
  const itensMarcados = checks.filter((i) => i.checked).map((i) => i.value);

  const observacao = document.getElementById(`ajusteObservacao${prefixo}`)?.value?.trim() || "";
  const quantidadeCones = document.getElementById(`ajusteCones${prefixo}`)?.value?.trim() || "";
  const duplaValor = document.getElementById(`ajusteDupla${prefixo}`)?.value ?? "";
  const nomes = document.getElementById(`ajusteNomes${prefixo}`)?.value?.trim() || "";
  const veracidadeValor = document.getElementById(`ajusteVeracidade${prefixo}`)?.value ?? "false";

  let trabalhandoEmDupla = null;
  if (duplaValor === "true") trabalhandoEmDupla = true;
  if (duplaValor === "false") trabalhandoEmDupla = false;

  return {
    ...detalheOriginal,
    itens: itensMarcados,
    itens_marcados: itensMarcados,
    observacao,
    quantidade_cones: quantidadeCones,
    trabalhando_em_dupla_ou_mais: trabalhandoEmDupla,
    nomes_dupla_ou_mais: nomes,
    confirmacao_veracidade: veracidadeValor === "true"
  };
}

async function abrirAjuste(id) {
  try {
    const res = await fetch(`/api/colaboradores/${id}/detalhe`);
    const data = await res.json();

    if (!res.ok || data.sucesso === false) {
      throw new Error(data.erro || "Erro ao carregar ajuste");
    }

    ajusteExpedienteId = id;

    ajusteChecklistEntradaDetalhe = normalizarChecklistDetalhe(data.checklist_entrada_detalhe || {});
    ajusteChecklistSaidaDetalhe = normalizarChecklistDetalhe(data.checklist_saida_detalhe || {});

    document.getElementById("ajusteHoraEntrada").value = data.horaEntrada || "";
    document.getElementById("ajusteHoraSaida").value = data.horaSaida || "";
    document.getElementById("ajusteMotivo").value = "";

    renderizarChecklistEditavel("ajusteChecklistEntrada", ajusteChecklistEntradaDetalhe);
    renderizarChecklistEditavel("ajusteChecklistSaida", ajusteChecklistSaidaDetalhe);

    document.getElementById("ajusteObservacaoEntrada").value = ajusteChecklistEntradaDetalhe.observacao || "";
    document.getElementById("ajusteConesEntrada").value = ajusteChecklistEntradaDetalhe.quantidade_cones || "";
    document.getElementById("ajusteDuplaEntrada").value = valorBooleanSelect(ajusteChecklistEntradaDetalhe.trabalhando_em_dupla_ou_mais);
    document.getElementById("ajusteNomesEntrada").value = ajusteChecklistEntradaDetalhe.nomes_dupla_ou_mais || "";
    document.getElementById("ajusteVeracidadeEntrada").value = ajusteChecklistEntradaDetalhe.confirmacao_veracidade ? "true" : "false";

    document.getElementById("ajusteObservacaoSaida").value = ajusteChecklistSaidaDetalhe.observacao || "";
    document.getElementById("ajusteConesSaida").value = ajusteChecklistSaidaDetalhe.quantidade_cones || "";
    document.getElementById("ajusteDuplaSaida").value = valorBooleanSelect(ajusteChecklistSaidaDetalhe.trabalhando_em_dupla_ou_mais);
    document.getElementById("ajusteNomesSaida").value = ajusteChecklistSaidaDetalhe.nomes_dupla_ou_mais || "";
    document.getElementById("ajusteVeracidadeSaida").value = ajusteChecklistSaidaDetalhe.confirmacao_veracidade ? "true" : "false";

    aplicarEstadoAjuste(
      document.getElementById("ajusteEstadoEntradaTexto"),
      ajusteChecklistEntradaDetalhe.veiculo_perfeito
    );

    aplicarEstadoAjuste(
      document.getElementById("ajusteEstadoSaidaTexto"),
      ajusteChecklistSaidaDetalhe.veiculo_perfeito
    );

    renderizarPreviewFoto("fotoEntradaPreview", data.fotoEntrada, "Foto de entrada");
    renderizarPreviewFoto("fotoSaidaPreview", data.fotoSaida, "Foto de saída");
    renderizarPreviewFoto("fotoOdometroPreview", data.fotoOdometro, "Foto do odômetro");

    const modal = document.getElementById("modalAjuste");
    if (modal) {
      modal.classList.remove("hidden");
      modal.style.display = "flex";
    }

    document.body.style.overflow = "hidden";
  } catch (e) {
    console.error("Erro ao abrir ajuste:", e);
    alert(e.message || "Erro ao carregar ajuste");
  }
}

function fecharAjuste() {
  const modal = document.getElementById("modalAjuste");
  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }

  ajusteExpedienteId = null;
  ajusteChecklistEntradaDetalhe = {};
  ajusteChecklistSaidaDetalhe = {};
  document.body.style.overflow = "";
}

async function salvarAjuste() {
  try {
    const payload = {
      id: ajusteExpedienteId,
      entrada: document.getElementById("ajusteHoraEntrada").value || null,
      saida: document.getElementById("ajusteHoraSaida").value || null,
      motivo: document.getElementById("ajusteMotivo").value.trim(),
      checklistEntrada: coletarChecklistEditavel(
        "ajusteChecklistEntrada",
        ajusteChecklistEntradaDetalhe,
        "Entrada"
      ),
      checklistSaida: coletarChecklistEditavel(
        "ajusteChecklistSaida",
        ajusteChecklistSaidaDetalhe,
        "Saida"
      )
    };

    const res = await fetch("/api/colaboradores/ajuste", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok || data.sucesso === false) {
      throw new Error(data.erro || "Erro ao salvar ajuste");
    }

    fecharAjuste();
    await carregarRegistros();
    aplicarFiltrosTabelaPrincipal();
    aplicarFiltrosHistorico();
  } catch (e) {
    console.error("Erro ao salvar ajuste:", e);
    alert(e.message || "Erro ao salvar ajuste");
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

document.addEventListener("DOMContentLoaded", () => {
  carregarRegistros();
});

document.addEventListener("click", (event) => {
  const modalImagem = document.getElementById("modalImagem");
  const modalChecklist = document.getElementById("modalChecklist");
  const modalAjuste = document.getElementById("modalAjuste");

  if (modalImagem && event.target === modalImagem) {
    fecharModalImagem();
  }

  if (modalChecklist && event.target === modalChecklist) {
    fecharModalChecklist();
  }

  if (modalAjuste && event.target === modalAjuste) {
    fecharAjuste();
  }
});

// =========================
// WINDOW
// =========================
window.abrirModalImagem = abrirModalImagem;
window.fecharModalImagem = fecharModalImagem;
window.abrirAjuste = abrirAjuste;
window.fecharAjuste = fecharAjuste;
window.verChecklist = verChecklist;
window.fecharModalChecklist = fecharModalChecklist;
window.salvarAjuste = salvarAjuste;