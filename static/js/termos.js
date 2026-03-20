const estadoApiTermos = document.getElementById("estadoApiTermos");
const listaColaboradoresTermos = document.getElementById("listaColaboradoresTermos");
const resumoAceitaram = document.getElementById("resumoAceitaram");
const resumoNaoAceitaram = document.getElementById("resumoNaoAceitaram");
const resumoTotal = document.getElementById("resumoTotal");
const btnAtualizarTermos = document.getElementById("btnAtualizarTermos");

function formatarDataHora(dataIso) {
  if (!dataIso) return "--";

  const data = new Date(dataIso);
  if (Number.isNaN(data.getTime())) return "--";

  return data.toLocaleString("pt-BR");
}

function escaparHtml(texto) {
  return String(texto ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderizarResumo(resumo) {
  resumoAceitaram.textContent = resumo?.aceitaram ?? 0;
  resumoNaoAceitaram.textContent = resumo?.nao_aceitaram ?? 0;
  resumoTotal.textContent = resumo?.total_cadastrados ?? 0;
}

function criarCardColaborador(colaborador) {
  const aceitou = colaborador.termo_aceito === true;

  if (aceitou) {
    return `
      <article class="card-colaborador-termo">
        <div class="linha-superior-colaborador">
          <div>
            <h3>${escaparHtml(colaborador.nome || "--")}</h3>
            <p>Email: ${escaparHtml(colaborador.email || "--")}</p>
          </div>

          <span class="status-termo aceito">Aceitou os termos</span>
        </div>

        <div class="meta-colaborador-termo">
          <span>Data de aceite: ${escaparHtml(formatarDataHora(colaborador.aceito_em))}</span>
          <span>Versão: ${escaparHtml(colaborador.termos_versao || "--")}</span>
          <span>Dispositivo: ${escaparHtml(colaborador.dispositivo || "--")}</span>
        </div>

        <details class="detalhes-termos">
          <summary>Visualizar termos aceitos</summary>
          <div class="conteudo-termo-mobile">${escaparHtml(colaborador.texto_termos || "Sem texto disponível.")}</div>
        </details>
      </article>
    `;
  }

  return `
    <article class="card-colaborador-termo">
      <div class="linha-superior-colaborador">
        <div>
          <h3>${escaparHtml(colaborador.nome || "--")}</h3>
          <p>Email: ${escaparHtml(colaborador.email || "--")}</p>
        </div>

        <span class="status-termo pendente">Não aceitou os termos</span>
      </div>

      <div class="meta-colaborador-termo">
        <span>Data de aceite: --</span>
        <span>Versão: --</span>
        <span>Dispositivo: --</span>
      </div>

      <div class="bloco-sem-aceite">
        <strong>Status atual:</strong>
        <p>Este colaborador ainda não confirmou os termos no aplicativo mobile.</p>
        <button type="button" class="botao-termo-desabilitado">Termos ainda não aceitos</button>
      </div>
    </article>
  `;
}

function renderizarLista(colaboradores) {
  if (!Array.isArray(colaboradores) || colaboradores.length === 0) {
    listaColaboradoresTermos.innerHTML = `
      <div class="vazio-termos">
        Nenhum colaborador cadastrado foi encontrado para este gestor.
      </div>
    `;
    return;
  }

  listaColaboradoresTermos.innerHTML = colaboradores
    .map(criarCardColaborador)
    .join("");
}

async function carregarTermosColaboradores() {
  estadoApiTermos.textContent = "Carregando dados dos termos...";
  estadoApiTermos.className = "estado-api-termos";

  try {
    const resposta = await fetch("/api/termos/colaboradores", {
      method: "GET",
      headers: {
        "Accept": "application/json"
      },
      credentials: "same-origin"
    });

    const dados = await resposta.json();

    if (!resposta.ok || !dados.sucesso) {
      throw new Error(dados.erro || "Não foi possível carregar os termos.");
    }

    renderizarResumo(dados.resumo);
    renderizarLista(dados.colaboradores);

    estadoApiTermos.textContent = "Dados carregados com sucesso.";
    estadoApiTermos.className = "estado-api-termos sucesso";
  } catch (erro) {
    resumoAceitaram.textContent = "0";
    resumoNaoAceitaram.textContent = "0";
    resumoTotal.textContent = "0";

    listaColaboradoresTermos.innerHTML = `
      <div class="vazio-termos">
        Erro ao carregar os dados dos termos dos colaboradores.
      </div>
    `;

    estadoApiTermos.textContent = erro.message || "Erro ao carregar os termos.";
    estadoApiTermos.className = "estado-api-termos erro";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  carregarTermosColaboradores();

  if (btnAtualizarTermos) {
    btnAtualizarTermos.addEventListener("click", carregarTermosColaboradores);
  }
});