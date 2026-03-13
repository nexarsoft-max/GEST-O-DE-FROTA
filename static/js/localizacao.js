(function init(){
  // 1) Pega dados do veículo via dataset
  let v = null;
  const dataEl = document.getElementById("loc-data");
  if (dataEl?.dataset?.veiculo) {
    try { v = JSON.parse(dataEl.dataset.veiculo); }
    catch(e){ console.error("Erro ao ler JSON data-veiculo:", e); }
  }

  // fallback (se você já usa isso em algum lugar)
  if (!v && window.VEICULO_ATUAL) v = window.VEICULO_ATUAL;

  // 2) Normaliza campos
  const nome = v?.nome || v?.modelo || "Veículo";
  const ano = v?.ano || v?.ano_modelo || "";
  const placa = v?.placa || v?.plate || "—";
  const sub = [ano ? String(ano) : null, placa].filter(Boolean).join(" • ");

  const status = (v?.status || v?.situacao || "Offline").trim();
  const motorista = v?.motorista || v?.driver || "—";
  const velocidade = (v?.velocidade ?? v?.speed ?? 0);
  const combustivel = clampPercent(v?.combustivel ?? v?.fuel ?? 0);
  const ultima = v?.ultima_atualizacao || v?.atualizado_em || v?.updated_at || "—";

  const endereco = v?.endereco || v?.address || "—";
  const lat = asNum(v?.lat ?? v?.latitude);
  const lng = asNum(v?.lng ?? v?.lon ?? v?.longitude);

  // 3) Preenche UI
  byId("vehNome").textContent = nome;
  byId("vehSub").textContent = sub;

  byId("motoristaValue").textContent = motorista;
  byId("velocidadeValue").textContent = String(velocidade ?? "—");
  byId("combValue").textContent = `${combustivel}%`;
  byId("combBar").style.width = `${combustivel}%`;
  byId("ultimaValue").textContent = formatDateTime(ultima);

  byId("enderecoText").textContent = endereco;
  byId("enderecoMini").textContent = endereco;

  // coords
  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    byId("coordsValue").textContent = `${lat.toFixed(5)} , ${lng.toFixed(5)}`;
  } else {
    byId("coordsValue").textContent = "—";
  }

  // 4) Status pill + ícones
  applyStatus(status);

  // 5) Mapa (OSM embed)
  setMap(lat, lng);

  // 6) botão contato (WhatsApp)
  const tel = normalizePhone(v?.telefone_motorista || v?.telefone || v?.phone);
  const msg = encodeURIComponent(`Olá ${motorista}! Pode me atualizar sua posição?`);
  const contato = tel
    ? `https://wa.me/${tel}?text=${msg}`
    : `https://wa.me/?text=${encodeURIComponent(`Olá! ${msg}`)}`;

  const btnContato = byId("btnContato");
  if (btnContato) btnContato.href = contato;

  // helpers
  function byId(id){ return document.getElementById(id); }

  function clampPercent(x){
    const n = asNum(x);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, Math.round(n)));
  }

  function asNum(x){
    if (x === null || x === undefined) return NaN;
    const n = Number(String(x).replace(",", "."));
    return Number.isFinite(n) ? n : NaN;
  }

  function normalizePhone(p){
    if (!p) return "";
    const digits = String(p).replace(/\D/g, "");
    if (!digits) return "";
    return digits.startsWith("55") ? digits : ("55" + digits);
  }

  function formatDateTime(val){
    try{
      const d = new Date(val);
      if (!isNaN(d.getTime())){
        const dd = String(d.getDate()).padStart(2,"0");
        const mm = String(d.getMonth()+1).padStart(2,"0");
        const yy = d.getFullYear();
        const hh = String(d.getHours()).padStart(2,"0");
        const mi = String(d.getMinutes()).padStart(2,"0");
        return `${dd}/${mm}/${yy}, ${hh}:${mi}`;
      }
    }catch(e){}
    return String(val ?? "—");
  }

  function applyStatus(s){
    const pill = byId("statusPill");
    const dot = byId("statusDot");
    const text = byId("statusText");
    const pin = byId("mapPinIcon");

    const statusNorm = (s || "").toLowerCase();

    // defaults (parado)
    let bg = "rgba(245,158,11,.12)";
    let bd = "rgba(245,158,11,.35)";
    let tx = "#b45309";
    let dotColor = "#f59e0b";
    let label = "Parado";
    let iconSvg = mapPinSvg("#6f2cff");
    let pinBg = "rgba(245,158,11,.18)";

    if (statusNorm.includes("mov")) {
      bg = "rgba(34,197,94,.12)";
      bd = "rgba(34,197,94,.35)";
      tx = "#15803d";
      dotColor = "#22c55e";
      label = "Em Movimento";
      iconSvg = navSvg("#6f2cff");
      pinBg = "rgba(34,197,94,.18)";
    } else if (statusNorm.includes("off")) {
      bg = "rgba(239,68,68,.12)";
      bd = "rgba(239,68,68,.35)";
      tx = "#b91c1c";
      dotColor = "#ef4444";
      label = "Offline";
      iconSvg = wifiOffSvg("#6f2cff");
      pinBg = "rgba(239,68,68,.18)";
    } else if (statusNorm.includes("par")) {
      label = "Parado";
      iconSvg = mapPinSvg("#6f2cff");
      pinBg = "rgba(245,158,11,.18)";
    }

    if (pill){
      pill.style.background = bg;
      pill.style.borderColor = bd;
      pill.style.color = tx;
    }
    if (dot) dot.style.background = dotColor;
    if (text) text.textContent = label;

    if (pin){
      pin.style.background = pinBg;
      pin.style.border = "1px solid rgba(255,255,255,.12)";
      pin.innerHTML = iconSvg;
    }
  }

  function setMap(lat, lng){
    const frame = document.getElementById("mapFrame");
    if (!frame) return;

    const latUse = Number.isFinite(lat) ? lat : -23.5505;
    const lngUse = Number.isFinite(lng) ? lng : -46.6333;

    const delta = 0.01;
    const left = (lngUse - delta).toFixed(6);
    const right = (lngUse + delta).toFixed(6);
    const top = (latUse + delta).toFixed(6);
    const bottom = (latUse - delta).toFixed(6);

    const src = `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${latUse}%2C${lngUse}`;
    frame.src = src;
  }

  // SVGs
  function navSvg(color){
    return `
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M3 11.5 21 3l-8.5 18-2.2-7.1L3 11.5Z" stroke="${color}" stroke-width="1.8" stroke-linejoin="round"/>
      </svg>
    `;
  }

  function mapPinSvg(color){
    return `
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 21s7-4.4 7-11a7 7 0 1 0-14 0c0 6.6 7 11 7 11Z" stroke="${color}" stroke-width="1.8"/>
        <path d="M12 13.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" stroke="${color}" stroke-width="1.8"/>
      </svg>
    `;
  }

  function wifiOffSvg(color){
    return `
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M2 8.5c5.5-5 14.5-5 20 0" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M5 12c3.8-3.4 10.2-3.4 14 0" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M8.5 15.5c2-1.8 5-1.8 7 0" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M4 4l16 16" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M12 19h0" stroke="${color}" stroke-width="4" stroke-linecap="round"/>
      </svg>
    `;
  }
})();