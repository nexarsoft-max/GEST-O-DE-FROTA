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
  configurarBotaoPercurso(lat, lng);

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
          width: 44px;
          height: 44px;
          border-radius: 999px;
          background: #ffffff;
          border: 2px solid ${cor};
          box-shadow: 0 10px 22px rgba(15, 23, 42, 0.20);
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" style="display:block;">
            <path fill="${cor}" d="M5 11l1.4-4.2A2 2 0 0 1 8.3 5h7.4a2 2 0 0 1 1.9 1.8L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v3h2m14-5a2 2 0 0 1 2 2v3h-2m-11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4"/>
          </svg>
        </div>
      `,
      iconSize: [44, 44],
      iconAnchor: [22, 22],
      popupAnchor: [0, -18]
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

  function configurarBotaoPercurso(latAtual, lngAtual) {
    const btn = byId("btnPercurso");
    if (!btn) return;

    if (Number.isFinite(latAtual) && Number.isFinite(lngAtual)) {
      btn.href = `https://www.google.com/maps/dir/?api=1&destination=${latAtual},${lngAtual}`;
      btn.target = "_blank";
      btn.rel = "noopener";
      return;
    }

    btn.href = "#";
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      alert("Ainda não existe posição real do veículo para gerar o percurso.");
    });
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