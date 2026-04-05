// ======================================================
// MAPA GERAL - GESTÃO DE FROTA
// Integração real com MapTiler + Leaflet
// Fonte dos dados:
//   GET /api/monitoramento/resumo
// ======================================================

// ------------------------------------------------------
// CONFIGURAÇÕES PRINCIPAIS
// ------------------------------------------------------
const API_MAPAGERAL = "/api/monitoramento/resumo";
const MAPTILER_KEY = "5nbVfauzMVPTkqi3q0iz";

const MAPA_CONFIG = {
  boundsPadrao: [
    [-7.60, -38.90], // sudoeste
    [-4.70, -34.80]  // nordeste
  ],
  zoomFocoVeiculo: 15,
  zoomFocoUnico: 14,
  paddingBounds: [40, 40]
};

// ------------------------------------------------------
// ESTADO GLOBAL
// ------------------------------------------------------
let MAPA_GERAL = null;
let MAPA_GERAL_DATA = [];
let MAPA_GERAL_MARCADORES = [];
let MAPA_GERAL_ITEM_ATIVO = null;

// ======================================================
// UTILITÁRIOS
// ======================================================
function mgEscapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function mgStatusLabel(status) {
  if (status === "moving") return "Em Movimento";
  if (status === "stopped") return "Parado";
  return "Offline";
}

function mgModeloText(veiculo) {
  return veiculo.modelo || veiculo.nome || "Veículo";
}

function mgCidadeText(veiculo) {
  return veiculo.cidade || "Sem cidade";
}

function mgPlacaText(veiculo) {
  return veiculo.placa || "—";
}

function mgMotoristaText(veiculo) {
  return veiculo.motoristaNome || "Aguardando vínculo do app";
}

function mgUpdatedText(veiculo) {
  return (
    veiculo.ultima_atualizacao_label ||
    veiculo.ultima_atualizacao ||
    "Aguardando última localização"
  );
}

function mgSpeedText(veiculo) {
  const velocidade = Number(veiculo.velocidade_kmh);
  return Number.isFinite(velocidade) ? `${velocidade} km/h` : "0 km/h";
}

// ======================================================
// COORDENADAS
// ======================================================
function mgLat(veiculo) {
  const latitude = Number(
    veiculo.latitude ??
    veiculo.lat ??
    veiculo.localizacao_lat ??
    veiculo.latitude_decimal
  );
  return Number.isFinite(latitude) ? latitude : null;
}

function mgLng(veiculo) {
  const longitude = Number(
    veiculo.longitude ??
    veiculo.lng ??
    veiculo.lon ??
    veiculo.localizacao_lng ??
    veiculo.localizacao_lon ??
    veiculo.longitude_decimal
  );
  return Number.isFinite(longitude) ? longitude : null;
}

function mgTemCoordenadas(veiculo) {
  return mgLat(veiculo) !== null && mgLng(veiculo) !== null;
}

// ======================================================
// FILTRO / BUSCA
// ======================================================
function mgFiltrar(lista, termo) {
  const texto = (termo || "").trim().toLowerCase();

  if (!texto) return lista;

  return lista.filter((veiculo) => {
    return [
      veiculo.modelo,
      veiculo.nome,
      veiculo.placa,
      veiculo.motoristaNome,
      veiculo.cidade,
      veiculo.status
    ].some((campo) =>
      String(campo || "").toLowerCase().includes(texto)
    );
  });
}

// ======================================================
// RESUMO
// ======================================================
function mgAtualizarResumo(lista) {
  const total = lista.length;
  const moving = lista.filter((v) => v.status === "moving").length;
  const stopped = lista.filter((v) => v.status === "stopped").length;
  const offline = lista.filter((v) => v.status === "offline").length;

  const totalEl = document.getElementById("mg_total");
  const movingEl = document.getElementById("mg_moving");
  const stoppedEl = document.getElementById("mg_stopped");
  const offlineEl = document.getElementById("mg_offline");
  const pillEl = document.getElementById("mg_pill");

  if (totalEl) totalEl.textContent = total;
  if (movingEl) movingEl.textContent = moving;
  if (stoppedEl) stoppedEl.textContent = stopped;
  if (offlineEl) offlineEl.textContent = offline;

  if (pillEl) {
    pillEl.textContent = `${total} veículo${total === 1 ? "" : "s"}`;
  }
}

// ======================================================
// MARCADOR DE CARRO
// ======================================================
function mgCorStatus(status) {
  if (status === "moving") return "#16a34a";
  if (status === "stopped") return "#d97706";
  return "#dc2626";
}

function mgCriarIconeCarrinho(status) {
  const cor = mgCorStatus(status);

  return L.divIcon({
    className: "mapageral-marker-custom",
    html: `
      <div style="
        width: 42px;
        height: 42px;
        border-radius: 999px;
        background: #ffffff;
        border: 2px solid ${cor};
        box-shadow: 0 10px 22px rgba(15, 23, 42, 0.18);
        display: flex;
        align-items: center;
        justify-content: center;
      ">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style="display:block;">
          <path fill="${cor}" d="M5 11l1.4-4.2A2 2 0 0 1 8.3 5h7.4a2 2 0 0 1 1.9 1.8L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v3h2m14-5a2 2 0 0 1 2 2v3h-2m-11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4"/>
        </svg>
      </div>
    `,
    iconSize: [42, 42],
    iconAnchor: [21, 21],
    popupAnchor: [0, -16]
  });
}

// ======================================================
// POPUP
// ======================================================
function mgPopupHtml(veiculo) {
  return `
    <div class="popup-mapageral">
      <strong>${mgEscapeHtml(mgModeloText(veiculo))}</strong>
      <span class="popup-placa">${mgEscapeHtml(mgPlacaText(veiculo))}</span>

      <div class="popup-info">
        <div><b>Status:</b> ${mgEscapeHtml(mgStatusLabel(veiculo.status))}</div>
        <div><b>Motorista:</b> ${mgEscapeHtml(mgMotoristaText(veiculo))}</div>
        <div><b>Velocidade:</b> ${mgEscapeHtml(mgSpeedText(veiculo))}</div>
        <div><b>Última atualização:</b> ${mgEscapeHtml(mgUpdatedText(veiculo))}</div>
      </div>

      <a href="/localizacao/${encodeURIComponent(veiculo.id)}">
        Ver localização individual
      </a>
    </div>
  `;
}

// ======================================================
// LISTA LATERAL
// ======================================================
function mgListaItemHtml(veiculo) {
  return `
    <article class="mapageral-item" data-id="${mgEscapeHtml(veiculo.id)}">
      <div class="mapageral-item-topo">
        <div class="mapageral-item-titulo">
          <strong>${mgEscapeHtml(mgModeloText(veiculo))}</strong>
          <span>${mgEscapeHtml(mgCidadeText(veiculo))}</span>
        </div>

        <span class="mapageral-badge ${mgEscapeHtml(veiculo.status || "offline")}">
          ${mgEscapeHtml(mgStatusLabel(veiculo.status))}
        </span>
      </div>

      <div class="mapageral-placa">${mgEscapeHtml(mgPlacaText(veiculo))}</div>

      <div class="mapageral-meta">
        <div class="mapageral-meta-linha">
          <span>Motorista</span>
          <b>${mgEscapeHtml(mgMotoristaText(veiculo))}</b>
        </div>

        <div class="mapageral-meta-linha">
          <span>Velocidade</span>
          <b>${mgEscapeHtml(mgSpeedText(veiculo))}</b>
        </div>

        <div class="mapageral-meta-linha">
          <span>Última atualização</span>
          <b>${mgEscapeHtml(mgUpdatedText(veiculo))}</b>
        </div>
      </div>

      <a class="mapageral-link" href="/localizacao/${encodeURIComponent(veiculo.id)}">
        Abrir individual
      </a>
    </article>
  `;
}

function mgMarcarAtivo(id) {
  MAPA_GERAL_ITEM_ATIVO = String(id);

  document.querySelectorAll(".mapageral-item").forEach((elemento) => {
    elemento.classList.toggle("ativo", elemento.dataset.id === MAPA_GERAL_ITEM_ATIVO);
  });
}

function mgFocarVeiculo(id) {
  const veiculo = MAPA_GERAL_DATA.find((v) => String(v.id) === String(id));

  if (!veiculo || !mgTemCoordenadas(veiculo) || !MAPA_GERAL) return;

  const lat = mgLat(veiculo);
  const lng = mgLng(veiculo);

  MAPA_GERAL.setView([lat, lng], MAPA_CONFIG.zoomFocoVeiculo, { animate: true });
  mgMarcarAtivo(id);

  const marcador = MAPA_GERAL_MARCADORES.find((m) => String(m.veiculoId) === String(id));
  if (marcador) marcador.openPopup();
}

function mgRenderLista(lista) {
  const listaEl = document.getElementById("mapageralLista");
  const emptyEl = document.getElementById("mapageralEmpty");

  if (!listaEl) return;

  if (!lista.length) {
    listaEl.innerHTML = "";
    if (emptyEl) emptyEl.style.display = "block";
    return;
  }

  if (emptyEl) emptyEl.style.display = "none";
  listaEl.innerHTML = lista.map(mgListaItemHtml).join("");

  listaEl.querySelectorAll(".mapageral-item").forEach((item) => {
    item.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      mgFocarVeiculo(item.dataset.id);
    });
  });
}

// ======================================================
// MAPA / MARCADORES
// ======================================================
function mgLimparMarcadores() {
  MAPA_GERAL_MARCADORES.forEach((marcador) => {
    if (MAPA_GERAL) MAPA_GERAL.removeLayer(marcador);
  });
  MAPA_GERAL_MARCADORES = [];
}

function mgRenderMapa(lista) {
  if (!MAPA_GERAL) return;

  mgLimparMarcadores();

  const comCoordenadas = lista.filter(mgTemCoordenadas);

  if (!comCoordenadas.length) {
    MAPA_GERAL.fitBounds(MAPA_CONFIG.boundsPadrao, {
      padding: MAPA_CONFIG.paddingBounds
    });
    return;
  }

  const bounds = [];

  comCoordenadas.forEach((veiculo) => {
    const lat = mgLat(veiculo);
    const lng = mgLng(veiculo);

    const marcador = L.marker([lat, lng], {
      icon: mgCriarIconeCarrinho(veiculo.status)
    });

    marcador.veiculoId = veiculo.id;
    marcador.bindPopup(mgPopupHtml(veiculo));
    marcador.addTo(MAPA_GERAL);

    marcador.on("click", () => {
      mgMarcarAtivo(veiculo.id);
    });

    MAPA_GERAL_MARCADORES.push(marcador);
    bounds.push([lat, lng]);
  });

  if (bounds.length === 1) {
    MAPA_GERAL.setView(bounds[0], MAPA_CONFIG.zoomFocoUnico);
  } else {
    MAPA_GERAL.fitBounds(bounds, {
      padding: MAPA_CONFIG.paddingBounds
    });
  }
}

// ======================================================
// BUSCA
// ======================================================
function mgAplicarBusca() {
  const input = document.getElementById("mapageralSearch");
  const termo = input ? input.value : "";

  const filtrados = mgFiltrar(MAPA_GERAL_DATA, termo);

  mgAtualizarResumo(filtrados);
  mgRenderLista(filtrados);
  mgRenderMapa(filtrados);
}

// ======================================================
// MAPA REAL - MAPTILER
// ======================================================
function mgCriarMapa() {
  MAPA_GERAL = L.map("mapaGeral", {
    zoomControl: true,
    maxBounds: MAPA_CONFIG.boundsPadrao,
    maxBoundsViscosity: 0.7
  });

  MAPA_GERAL.fitBounds(MAPA_CONFIG.boundsPadrao, {
    padding: MAPA_CONFIG.paddingBounds
  });

  L.tileLayer(`https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=${MAPTILER_KEY}`, {
    tileSize: 512,
    zoomOffset: -1,
    maxZoom: 20,
    attribution: '&copy; MapTiler &copy; OpenStreetMap contributors'
  }).addTo(MAPA_GERAL);
}

// ======================================================
// DADOS
// ======================================================
async function mgCarregarDados() {
  try {
    const resposta = await fetch(API_MAPAGERAL, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });

    if (resposta.status === 401) {
      alert("Sua sessão expirou. Faça login novamente.");
      window.location.assign("/");
      return;
    }

    const dados = await resposta.json().catch(() => []);
    MAPA_GERAL_DATA = Array.isArray(dados) ? dados : [];

    mgAplicarBusca();
  } catch (erro) {
    console.error("Erro ao carregar mapa geral:", erro);
    MAPA_GERAL_DATA = [];
    mgAplicarBusca();
  }
}

// ======================================================
// INIT
// ======================================================
document.addEventListener("DOMContentLoaded", () => {
  mgCriarMapa();

  const inputBusca = document.getElementById("mapageralSearch");
  if (inputBusca) {
    inputBusca.addEventListener("input", mgAplicarBusca);
  }

  mgCarregarDados();

  window.addEventListener("resize", () => {
    if (MAPA_GERAL) {
      MAPA_GERAL.invalidateSize();
    }
  });
});