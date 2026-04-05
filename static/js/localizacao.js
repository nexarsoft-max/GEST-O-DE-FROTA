(function init() {
  const MAPTILER_KEY = "5nbVfauzMVPTkqi3q0iz";
  let mapaIndividual = null;
  let marcadorVeiculo = null;

  let v = null;
  const dataEl = document.getElementById("loc-data");

  if (dataEl?.dataset?.veiculo) {
    try {
      v = JSON.parse(dataEl.dataset.veiculo);
    } catch (e) {
      console.error("Erro ao ler JSON data-veiculo:", e);
    }
  }

  if (!v && window.VEICULO_ATUAL) {
    v = window.VEICULO_ATUAL;
  }

  if (!v) {
    v = {};
  }

  const nome = v?.nome || v?.modelo || "Veículo";
  const ano = v?.ano || v?.ano_modelo || "";
  const placa = v?.placa || v?.plate || "—";
  const sub = [ano ? String(ano) : null, placa].filter(Boolean).join(" • ");

  const status = String(v?.status || v?.situacao || "offline").trim();
  const motorista = v?.motoristaNome || v?.motorista || v?.driver || "Aguardando vínculo do app";
  const velocidade = asNum(v?.velocidade_kmh ?? v?.velocidade ?? v?.speed);
  const ultima = v?.ultima_atualizacao_label || v?.ultima_atualizacao || v?.atualizado_em || v?.updated_at || "Sem atualização";

  const endereco = v?.endereco || v?.address || "Localização indisponível no momento";
  const lat = asNum(v?.lat ?? v?.latitude);
  const lng = asNum(v?.lng ?? v?.lon ?? v?.longitude);

  byId("vehNome").textContent = nome;
  byId("vehSub").textContent = sub || placa;

  byId("motoristaValue").textContent = motorista;
  byId("velocidadeValue").textContent = Number.isFinite(velocidade) ? String(Math.round(velocidade)) : "0";
  byId("ultimaValue").textContent = formatDateTime(ultima);
  byId("enderecoText").textContent = endereco;
  byId("enderecoMini").textContent = endereco;

  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    byId("coordsValue").textContent = `${lat.toFixed(5)} , ${lng.toFixed(5)}`;
  } else {
    byId("coordsValue").textContent = "—";
  }

  applyStatus(status);
  setMap(lat, lng, endereco, nome, placa, status);
  configurarBotoesAcao(lat, lng, v?.id);

  window.addEventListener("resize", () => {
    if (mapaIndividual) {
      mapaIndividual.invalidateSize();
    }
  });

  function byId(id) {
    return document.getElementById(id);
  }

  function asNum(x) {
    if (x === null || x === undefined || x === "") return NaN;
    const n = Number(String(x).replace(",", "."));
    return Number.isFinite(n) ? n : NaN;
  }

  function formatDateTime(val) {
    try {
      const d = new Date(val);
      if (!isNaN(d.getTime())) {
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const yy = d.getFullYear();
        const hh = String(d.getHours()).padStart(2, "0");
        const mi = String(d.getMinutes()).padStart(2, "0");
        return `${dd}/${mm}/${yy}, ${hh}:${mi}`;
      }
    } catch (e) {}
    return String(val ?? "—");
  }

  function applyStatus(s) {
    const pill = byId("statusPill");
    const dot = byId("statusDot");
    const text = byId("statusText");
    const pin = byId("mapPinIcon");

    const statusNorm = String(s || "").toLowerCase();

    let bg = "rgba(239,68,68,.10)";
    let bd = "rgba(239,68,68,.30)";
    let cor = "#dc2626";
    let label = "Offline";

    if (statusNorm === "moving" || statusNorm === "em movimento") {
      bg = "rgba(34,197,94,.10)";
      bd = "rgba(34,197,94,.30)";
      cor = "#16a34a";
      label = "Em Movimento";
    } else if (statusNorm === "stopped" || statusNorm === "parado") {
      bg = "rgba(245,158,11,.12)";
      bd = "rgba(245,158,11,.30)";
      cor = "#b45309";
      label = "Parado";
    }

    if (pill) {
      pill.style.background = bg;
      pill.style.borderColor = bd;
      pill.style.color = cor;
    }

    if (dot) {
      dot.style.background = cor;
    }

    if (text) {
      text.textContent = label;
    }

    if (pin) {
      pin.innerHTML = `
        <div style="
          width:54px;
          height:54px;
          border-radius:18px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:rgba(255,255,255,.12);
          border:1px solid rgba(255,255,255,.18);
          backdrop-filter:blur(8px);
          box-shadow:0 12px 24px rgba(0,0,0,.18);
        ">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
            <path d="M3 13.2V18a1 1 0 0 0 1 1h1.2a1 1 0 0 0 1-1v-1h11.6v1a1 1 0 0 0 1 1H21a1 1 0 0 0 1-1v-4.8a2.2 2.2 0 0 0-1.4-2.05l-1.56-5.2A2.2 2.2 0 0 0 16.93 4H7.07a2.2 2.2 0 0 0-2.11 1.95l-1.56 5.2A2.2 2.2 0 0 0 3 13.2Z" stroke="${cor}" stroke-width="1.8"/>
            <path d="M6.5 16.5h.01M17.5 16.5h.01" stroke="${cor}" stroke-width="3" stroke-linecap="round"/>
          </svg>
        </div>
      `;
    }
  }

  function corStatusMapa(statusAtual) {
    const s = String(statusAtual || "").toLowerCase();

    if (s === "moving" || s === "em movimento") return "#16a34a";
    if (s === "stopped" || s === "parado") return "#d97706";
    return "#dc2626";
  }

  function criarIconeCarro(statusAtual) {
  const cor = corStatusMapa(statusAtual);

  return L.divIcon({
    className: "marcador-veiculo-individual",
    html: `
      <div style="
        position: relative;
        width: 56px;
        height: 56px;
        display:flex;
        align-items:center;
        justify-content:center;
      ">
        <div style="
          position:absolute;
          inset:8px;
          border-radius:999px;
          background: radial-gradient(circle at 30% 30%, #ffffff 0%, #f8fafc 55%, #e2e8f0 100%);
          border: 2px solid ${cor};
          box-shadow:
            0 18px 28px rgba(15, 23, 42, 0.22),
            inset 0 1px 0 rgba(255,255,255,0.95);
        "></div>

        <div style="
          position:absolute;
          bottom:2px;
          width:26px;
          height:8px;
          border-radius:999px;
          background: rgba(15,23,42,0.18);
          filter: blur(4px);
        "></div>

        <svg viewBox="0 0 64 64" width="28" height="28" aria-hidden="true" style="position:relative;z-index:2;display:block;">
          <defs>
            <linearGradient id="carBodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="${cor}"/>
              <stop offset="100%" stop-color="#111827"/>
            </linearGradient>
          </defs>
          <path d="M18 38h28l3-9c.6-1.9-.8-3.9-2.8-3.9H23.8c-1.3 0-2.5.8-2.9 2L18 38z" fill="url(#carBodyGrad)"/>
          <path d="M14 39h36c2.2 0 4 1.8 4 4v5h-4a5 5 0 0 0-10 0H24a5 5 0 0 0-10 0h-4v-5c0-2.2 1.8-4 4-4z" fill="${cor}"/>
          <path d="M24 27h16c1 0 1.9.5 2.4 1.4L45 33H19l2.4-4.6c.5-.9 1.4-1.4 2.6-1.4z" fill="#dbeafe"/>
          <circle cx="19" cy="48" r="4.5" fill="#111827"/>
          <circle cx="45" cy="48" r="4.5" fill="#111827"/>
          <circle cx="19" cy="48" r="2" fill="#94a3b8"/>
          <circle cx="45" cy="48" r="2" fill="#94a3b8"/>
        </svg>
      </div>
    `,
    iconSize: [56, 56],
    iconAnchor: [28, 28],
    popupAnchor: [0, -20]
  });
}

  function setMap(latAtual, lngAtual, enderecoAtual, nomeAtual, placaAtual, statusAtual) {
    const mapArea = byId("mapArea");
    const mapBox = byId("mapaIndividual");
    const semGpsTexto = byId("semGpsTexto");

    if (!mapArea || !mapBox) return;

    if (!Number.isFinite(latAtual) || !Number.isFinite(lngAtual)) {
      mapArea.classList.add("sem-gps");
      if (semGpsTexto) semGpsTexto.style.display = "block";
      byId("enderecoText").textContent = enderecoAtual || "Localização indisponível no momento";
      return;
    }

    mapArea.classList.remove("sem-gps");
    if (semGpsTexto) semGpsTexto.style.display = "none";

    mapaIndividual = L.map("mapaIndividual", {
      zoomControl: true
    }).setView([latAtual, lngAtual], 16);

    L.tileLayer(`https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=${MAPTILER_KEY}`, {
      tileSize: 512,
      zoomOffset: -1,
      maxZoom: 20,
      attribution: '&copy; MapTiler &copy; OpenStreetMap contributors'
    }).addTo(mapaIndividual);

    marcadorVeiculo = L.marker([latAtual, lngAtual], {
      icon: criarIconeCarro(statusAtual)
    }).addTo(mapaIndividual);

    marcadorVeiculo.bindPopup(`
      <div style="min-width:220px;">
        <strong style="display:block;font-size:14px;color:#0f172a;">${escapeHtml(nomeAtual || "Veículo")}</strong>
        <div style="margin-top:6px;font-size:12px;color:#475569;"><b>Placa:</b> ${escapeHtml(placaAtual || "—")}</div>
        <div style="margin-top:4px;font-size:12px;color:#475569;"><b>Status:</b> ${escapeHtml(byId("statusText").textContent || "Offline")}</div>
        <div style="margin-top:4px;font-size:12px;color:#475569;"><b>Endereço:</b> ${escapeHtml(enderecoAtual || "Localização indisponível")}</div>
      </div>
    `);

    marcadorVeiculo.openPopup();

    setTimeout(() => {
      mapaIndividual.invalidateSize();
    }, 200);
  }

  function configurarBotoesAcao(latAtual, lngAtual, veiculoId) {
  const btnPercursoAgora = byId("btnPercursoAgora");
  const btnPorOndePassou = byId("btnPorOndePassou");

  if (btnPercursoAgora) {
    if (Number.isFinite(latAtual) && Number.isFinite(lngAtual)) {
      btnPercursoAgora.href = `https://www.google.com/maps/dir/?api=1&destination=${latAtual},${lngAtual}`;
      btnPercursoAgora.target = "_blank";
      btnPercursoAgora.rel = "noopener";
    } else {
      btnPercursoAgora.href = "#";
      btnPercursoAgora.addEventListener("click", function (e) {
        e.preventDefault();
        alert("Ainda não existe posição real do veículo para gerar a rota até ele.");
      });
    }
  }

  if (btnPorOndePassou) {
    if (veiculoId) {
      btnPorOndePassou.href = `/percurso/${veiculoId}`;
    } else {
      btnPorOndePassou.href = "#";
      btnPorOndePassou.addEventListener("click", function (e) {
        e.preventDefault();
        alert("Veículo inválido para consultar o histórico.");
      });
    }
  }
}

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
})();