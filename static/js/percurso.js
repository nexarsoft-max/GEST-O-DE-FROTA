(function () {
 const pageEl = document.getElementById("percursoPage");

const config = {
  veiculoId: pageEl?.dataset.veiculoId || "",
  modelo: pageEl?.dataset.veiculoModelo || "",
  placa: pageEl?.dataset.veiculoPlaca || "",
  cidade: pageEl?.dataset.veiculoCidade || ""
};

const veiculoId = config.veiculoId;

  const elInicio = document.getElementById("inicio");
  const elFim = document.getElementById("fim");
  const elBtnBuscar = document.getElementById("btnBuscarPercurso");
  const elDistancia = document.getElementById("distanciaTotal");
  const elTempo = document.getElementById("tempoTotal");
  const elVelMedia = document.getElementById("velocidadeMedia");
  const elQtd = document.getElementById("quantidadePontos");
  const elTimeline = document.getElementById("timelineList");
  const elTimelineStatus = document.getElementById("timelineStatus");

  let mapa = null;
  let linhaPercurso = null;
  let marcadores = [];

  function initMapa() {
    mapa = L.map("mapaPercurso", {
      zoomControl: true
    }).setView([-7.12, -36.25], 11);

    L.tileLayer("https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=5nbVfauzMVPTkqi3q0iz", {
      tileSize: 512,
      zoomOffset: -1,
      maxZoom: 20,
      attribution: "&copy; MapTiler &copy; OpenStreetMap contributors"
    }).addTo(mapa);
  }

  function limparMapa() {
    if (linhaPercurso) {
      mapa.removeLayer(linhaPercurso);
      linhaPercurso = null;
    }

    marcadores.forEach((m) => mapa.removeLayer(m));
    marcadores = [];
  }

  function formatarDataHora(valor) {
    if (!valor) return "—";
    const d = new Date(valor);
    if (isNaN(d.getTime())) return valor;

    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const aa = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");

    return `${dd}/${mm}/${aa} ${hh}:${mi}`;
  }

  function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;

    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) *
      Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function calcularResumo(pontos) {
    let distanciaMetros = 0;
    let tempoSegundos = 0;

    for (let i = 1; i < pontos.length; i++) {
      const a = pontos[i - 1];
      const b = pontos[i];

      if (
        a.lat == null || a.lng == null ||
        b.lat == null || b.lng == null ||
        !a.data || !b.data
      ) {
        continue;
      }

      distanciaMetros += haversine(a.lat, a.lng, b.lat, b.lng);

      const t1 = new Date(a.data).getTime();
      const t2 = new Date(b.data).getTime();

      if (!isNaN(t1) && !isNaN(t2) && t2 > t1) {
        tempoSegundos += (t2 - t1) / 1000;
      }
    }

    const distanciaKm = distanciaMetros / 1000;
    const velocidadeMedia = tempoSegundos > 0
      ? distanciaKm / (tempoSegundos / 3600)
      : 0;

    elDistancia.textContent = `${distanciaKm.toFixed(2)} km`;
    elTempo.textContent = formatarDuracao(tempoSegundos);
    elVelMedia.textContent = `${velocidadeMedia.toFixed(2)} km/h`;
    elQtd.textContent = String(pontos.length);
  }

  function formatarDuracao(segundos) {
    if (!segundos || segundos <= 0) return "0 min";

    const horas = Math.floor(segundos / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);

    if (horas > 0 && minutos > 0) return `${horas}h ${minutos}min`;
    if (horas > 0) return `${horas}h`;
    return `${minutos} min`;
  }

  function renderTimeline(pontos) {
    if (!pontos.length) {
      elTimeline.innerHTML = `<div class="timeline-empty">Nenhum ponto encontrado no período informado.</div>`;
      elTimelineStatus.textContent = "Nenhum dado encontrado para o período selecionado.";
      return;
    }

    elTimelineStatus.textContent = `${pontos.length} ponto(s) encontrados no período.`;

    elTimeline.innerHTML = pontos.map((ponto, index) => {
      const titulo =
        index === 0 ? "Início do trajeto" :
        index === pontos.length - 1 ? "Último ponto" :
        `Ponto ${index + 1}`;

      const velocidade = Number(ponto.velocidade || 0);

      return `
        <div class="timeline-item">
          <div class="timeline-item-top">
            <strong>${titulo}</strong>
            <span class="timeline-time">${formatarDataHora(ponto.data)}</span>
          </div>
          <p><b>Velocidade:</b> ${velocidade.toFixed(2)} km/h</p>
          <p><b>Endereço:</b> ${ponto.endereco || "Sem endereço informado"}</p>
          <p><b>Coordenadas:</b> ${Number(ponto.lat).toFixed(5)}, ${Number(ponto.lng).toFixed(5)}</p>
        </div>
      `;
    }).join("");
  }

  function renderMapa(pontos) {
    limparMapa();

    const coords = pontos
      .filter((p) => p.lat != null && p.lng != null)
      .map((p) => [p.lat, p.lng]);

    if (!coords.length) return;

    linhaPercurso = L.polyline(coords, {
      color: "#7c3aed",
      weight: 5,
      opacity: 0.95
    }).addTo(mapa);

    const inicioIcon = L.divIcon({
      className: "percurso-marker",
      html: `<div style="width:18px;height:18px;border-radius:999px;background:#16a34a;border:3px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.2)"></div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });

    const fimIcon = L.divIcon({
      className: "percurso-marker",
      html: `<div style="width:18px;height:18px;border-radius:999px;background:#dc2626;border:3px solid #fff;box-shadow:0 4px 12px rgba(0,0,0,.2)"></div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });

    const marcadorInicio = L.marker(coords[0], { icon: inicioIcon })
      .addTo(mapa)
      .bindPopup("Início do percurso");

    const marcadorFim = L.marker(coords[coords.length - 1], { icon: fimIcon })
      .addTo(mapa)
      .bindPopup("Fim do percurso");

    marcadores.push(marcadorInicio, marcadorFim);

    mapa.fitBounds(linhaPercurso.getBounds(), {
      padding: [40, 40]
    });
  }

  async function buscarPercurso() {
    const inicio = (elInicio.value || "").trim();
    const fim = (elFim.value || "").trim();

    if (!inicio || !fim) {
      alert("Escolha a data/hora inicial e final.");
      return;
    }

    try {
      const resp = await fetch(
        `/api/veiculos/${encodeURIComponent(veiculoId)}/percurso?inicio=${encodeURIComponent(inicio)}&fim=${encodeURIComponent(fim)}`,
        {
          headers: { "Accept": "application/json" },
          credentials: "same-origin"
        }
      );

      const data = await resp.json();

      if (!resp.ok || data.sucesso === false) {
        throw new Error(data.erro || "Erro ao carregar percurso");
      }

      const pontos = Array.isArray(data.pontos) ? data.pontos : [];

      calcularResumo(pontos);
      renderTimeline(pontos);
      renderMapa(pontos);
    } catch (err) {
      console.error("Erro ao buscar percurso:", err);
      alert(err.message || "Erro ao buscar percurso.");
    }
  }

  function definirPeriodoInicial() {
    const agora = new Date();
    const umaHoraAtras = new Date(agora.getTime() - (60 * 60 * 1000));

    elFim.value = toDatetimeLocalValue(agora);
    elInicio.value = toDatetimeLocalValue(umaHoraAtras);
  }

  function toDatetimeLocalValue(data) {
    const ano = data.getFullYear();
    const mes = String(data.getMonth() + 1).padStart(2, "0");
    const dia = String(data.getDate()).padStart(2, "0");
    const hora = String(data.getHours()).padStart(2, "0");
    const minuto = String(data.getMinutes()).padStart(2, "0");

    return `${ano}-${mes}-${dia}T${hora}:${minuto}`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    initMapa();
    definirPeriodoInicial();

    elBtnBuscar.addEventListener("click", buscarPercurso);
  });
})();