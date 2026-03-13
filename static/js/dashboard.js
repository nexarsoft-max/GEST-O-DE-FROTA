const API_BASE = "";

/* helpers */
const fmtBRL = (n) => (Number(n || 0)).toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
const fmtPct = (n) => `${(Number(n||0)).toFixed(1).replace(".",",")}%`;
const fmtNum = (n, dec=0) => (Number(n||0)).toFixed(dec).replace(".",",");
const fmtKm  = (n) => `${fmtNum(n,0)} km`;
const fmtL   = (n) => `${fmtNum(n,0)} L`;

function parseDT(data, hora){
  const h = (hora && String(hora).trim()) ? hora : "00:00";
  return new Date(`${data}T${h}`);
}
function ymKey(d){
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,"0");
  return `${y}-${m}`;
}
function monthLabel(d){
  return d.toLocaleString("pt-BR",{month:"long",year:"numeric"});
}
function normOdo(x){
  const n = Number(String(x ?? "").replace(/[^\d]/g, ""));
  return Number.isFinite(n) ? n : NaN;
}

async function tryFetchJSON(url){
  try{
    const r = await fetch(url, { headers:{ "Accept":"application/json" }});
    if(!r.ok) return null;
    return await r.json();
  }catch(_){ return null; }
}
function getLS(key, fallback){
  try{
    const v = JSON.parse(localStorage.getItem(key));
    return (v === null || v === undefined) ? fallback : v;
  }catch(_){ return fallback; }
}
async function carregarDados(){
  const [apiReg, apiVei, apiMot, apiPos] = await Promise.all([
    tryFetchJSON(`${API_BASE}/api/registros`),
    tryFetchJSON(`${API_BASE}/api/veiculos`),
    tryFetchJSON(`${API_BASE}/api/motoristas`),
    tryFetchJSON(`${API_BASE}/api/postos`)
  ]);

  const registros  = Array.isArray(apiReg) ? apiReg : getLS("registros", []);
  const veiculos   = Array.isArray(apiVei) ? apiVei : getLS("veiculos", []);
  const motoristas = Array.isArray(apiMot) ? apiMot : getLS("motoristas", []);
  const postos     = Array.isArray(apiPos) ? apiPos : getLS("postos", []);

  return { registros, veiculos, motoristas, postos };
}

/* ✅ remove registros sem veículo válido (e salva limpo no localStorage) */
function filtrarRegistrosPorVeiculosExistentes(registros, veiculos){
  const ids = new Set((veiculos || []).map(v => Number(v.id)));

  const filtrados = (registros || []).filter(r => {
    const vid = r?.veiculoId;
    if(vid === undefined || vid === null || vid === "") return false;
    return ids.has(Number(vid));
  });

  try { localStorage.setItem("registros", JSON.stringify(filtrados)); } catch(e){}

  return filtrados;
}

/* cálculos */
function valorRegistro(r){
  if(r?.tipo === "abastecimento") return Number(r.preco || 0);
  if(r?.tipo === "manutencao") return Number(r.valor || 0);
  return 0;
}
function registrosDoMes(registros, keyYm){
  return registros.filter(r=>{
    if(!r?.data) return false;
    const dt = parseDT(r.data, r.hora);
    return ymKey(dt) === keyYm;
  });
}
function somaPorPago(registros){
  let pago = 0, naoPago = 0, total = 0;
  for(const r of registros){
    const v = valorRegistro(r);
    total += v;
    if(r.pago === true) pago += v;
    else naoPago += v;
  }
  return { total, pago, naoPago };
}

/* ===========================
   ✅ TRECHOS POR ODÔMETRO (CORRIGIDO)
   - Consumo (L/km): NÃO depende de preço
   - Custo (R$/km): só soma trechos que têm preço > 0
   - Resumo por veículo: usa a MESMA lógica do seu exemplo (litros do abastecimento atual / km desde o anterior)
   =========================== */

function abastecimentosNormalizados(registros){
  return (registros || [])
    .filter(r =>
      r?.tipo === "abastecimento" &&
      r?.veiculoId &&
      r?.data &&
      r?.odometro !== undefined &&
      r?.odometro !== null &&
      Number(r.litros || 0) > 0
    )
    .map(r => ({
      veiculoId: Number(r.veiculoId),
      litros: Number(r.litros || 0),
      valor: Number(r.preco || 0), // pode ser 0 (não quebra consumo)
      odo: normOdo(r.odometro),
      dt: parseDT(r.data, r.hora)
    }))
    .filter(r => Number.isFinite(r.odo) && r.odo >= 0 && r.litros > 0);
}

function agruparPorVeiculo(lista){
  const byV = new Map();
  for(const r of lista){
    if(!byV.has(r.veiculoId)) byV.set(r.veiculoId, []);
    byV.get(r.veiculoId).push(r);
  }
  return byV;
}

function somarTrechos(list){
  // list já é de 1 veículo
  list.sort((a,b)=> a.dt - b.dt);

  let kmTrechos = 0;
  let litrosTrechos = 0;
  let kmTrechosComValor = 0;
  let valorTrechos = 0;

  for(let i=1;i<list.length;i++){
    const prev = list[i-1];
    const cur  = list[i];
    const deltaKm = cur.odo - prev.odo;

    if(deltaKm > 0){
      kmTrechos += deltaKm;
      litrosTrechos += cur.litros;

      // custo só conta se tiver preço > 0
      if(Number(cur.valor || 0) > 0){
        kmTrechosComValor += deltaKm;
        valorTrechos += Number(cur.valor || 0);
      }
    }
  }

  return { kmTrechos, litrosTrechos, kmTrechosComValor, valorTrechos };
}

function baseFrotaTrechos(registros){
  const abs = abastecimentosNormalizados(registros);
  const byV = agruparPorVeiculo(abs);

  let totalKm = 0;
  let totalLitros = 0;

  let totalKmCusto = 0;
  let totalValor = 0;

  for(const list of byV.values()){
    const t = somarTrechos(list);
    totalKm += t.kmTrechos;
    totalLitros += t.litrosTrechos;

    totalKmCusto += t.kmTrechosComValor;
    totalValor += t.valorTrechos;
  }

  return { totalKm, totalLitros, totalKmCusto, totalValor };
}

function consumoMedioLitrosPorKmTrechos(registros){
  const { totalKm, totalLitros } = baseFrotaTrechos(registros);
  if(totalKm <= 0) return 0;
  return totalLitros / totalKm;
}
function custoMedioReaisPorKmTrechos(registros){
  const { totalKmCusto, totalValor } = baseFrotaTrechos(registros);
  if(totalKmCusto <= 0) return 0;
  return totalValor / totalKmCusto;
}

/* ✅ KM rodados no mês: soma dos trechos válidos (coerente com o consumo) */
function kmRodadosFrotaPorTrechosNoMes(regMesAtual){
  const abs = abastecimentosNormalizados(regMesAtual);
  const byV = agruparPorVeiculo(abs);
  let km = 0;
  for(const list of byV.values()){
    km += somarTrechos(list).kmTrechos;
  }
  return km;
}

function topMaiorQtdAbastecimentos(regMesAtual, veiculos, topN){
  const map = new Map();
  for(const r of regMesAtual){
    if(r?.tipo !== "abastecimento") continue;
    if(!r?.veiculoId) continue;
    const id = Number(r.veiculoId);
    if(!map.has(id)) map.set(id, {qtd:0, gasto:0, odos:[]});
    const o = map.get(id);
    o.qtd += 1;
    o.gasto += Number(r.preco||0);
    if(r.odometro !== undefined && r.odometro !== null){
      const odo = normOdo(r.odometro);
      if(Number.isFinite(odo)) o.odos.push(odo);
    }
  }

  /* ✅ se veículo não existe mais, não entra no ranking */
  const arr = Array.from(map.entries())
    .map(([id, o])=>{
      const v = veiculos.find(x=>Number(x.id)===Number(id));
      if(!v) return null;

      const nome = `${v.placa || ""} - ${v.modelo || "Veículo"}`.trim();

      let km = 0;
      if(o.odos.length >= 2){
        km = Math.max(...o.odos) - Math.min(...o.odos);
        km = km > 0 ? km : 0;
      }
      const rpk = (km > 0) ? (o.gasto / km) : 0;

      return { veiculoId:id, nome, qtd:o.qtd, gasto:o.gasto, km, rpk };
    })
    .filter(Boolean);

  arr.sort((a,b)=> b.qtd - a.qtd || b.gasto - a.gasto);
  return arr.slice(0, topN);
}

/* ✅ RESUMO VEÍCULO: agora usa TRECHOS (corrige o erro que fazia litros/km ficar gigante) */
function resumoMensalPorVeiculoRodados(regMesAtual, veiculos){
  const vMap = new Map();
  for(const v of veiculos){
    const nome = `${v.placa || ""} - ${v.modelo || "Veículo"}`.trim();
    vMap.set(Number(v.id), { veiculoId:Number(v.id), nome, gastoMensal:0, custoCombMes:0, litrosMes:0, kmRodados:0, qtdAbastecimentos:0 });
  }

  // gasto mensal + contagens
  for(const r of regMesAtual){
    if(!r?.veiculoId) continue;
    const id = Number(r.veiculoId);
    if(!vMap.has(id)) continue;

    const row = vMap.get(id);
    row.gastoMensal += valorRegistro(r);

    if(r?.tipo === "abastecimento"){
      row.custoCombMes += Number(r.preco||0);
      row.litrosMes += Number(r.litros||0);
      row.qtdAbastecimentos += 1;
    }
  }

  // trechos por veículo (para kmRodados + lpk/rpk corretos)
  const abs = abastecimentosNormalizados(regMesAtual);
  const byV = agruparPorVeiculo(abs);

  const trechosPorVeiculo = new Map();
  for(const [vid, list] of byV.entries()){
    if(!vMap.has(vid)) continue;
    trechosPorVeiculo.set(vid, somarTrechos(list));
  }

  const out = Array.from(vMap.values()).map(x=>{
    const t = trechosPorVeiculo.get(x.veiculoId) || { kmTrechos:0, litrosTrechos:0, kmTrechosComValor:0, valorTrechos:0 };

    const kmRodados = t.kmTrechos; // ✅ igual ao seu exemplo (480-200 = 280)
    const lpk = (t.kmTrechos > 0) ? (t.litrosTrechos / t.kmTrechos) : 0; // ✅ 26/280 = 0,093
    const rpk = (t.kmTrechosComValor > 0) ? (t.valorTrechos / t.kmTrechosComValor) : 0;

    return { ...x, kmRodados, lpk, rpk };
  });

  out.sort((a,b)=> b.gastoMensal - a.gastoMensal);
  return out;
}

function topPioresCustoPorKm(regMesAtual, veiculos, topN){
  const rows = resumoMensalPorVeiculoRodados(regMesAtual, veiculos)
    .filter(x => x.kmRodados > 0 && x.rpk > 0);

  rows.sort((a,b)=> b.rpk - a.rpk);
  return rows.slice(0, topN).map(x=>({ veiculoId:x.veiculoId, nome:x.nome, rpk:x.rpk, km:x.kmRodados, custo:x.custoCombMes }));
}

function resumoMensalPorMotorista(regMesAtual, motoristas){
  const mMap = new Map();

  const nomeMotorista = (id)=>{
    const m = motoristas.find(x=>Number(x.id)===Number(id));
    if(!m) return `Motorista ${id}`;
    return (m.nome || m.name || m.motorista || m.fullname || `Motorista ${id}`);
  };

  for(const r of regMesAtual){
    const mid = r?.motoristaId ?? r?.motorista_id ?? r?.idMotorista;
    if(!mid) continue;

    const id = Number(mid);
    if(!mMap.has(id)){
      mMap.set(id, { motoristaId:id, nome:nomeMotorista(id), gasto:0, qtdAb:0, qtdMn:0 });
    }
    const row = mMap.get(id);

    row.gasto += valorRegistro(r);
    if(r?.tipo === "abastecimento") row.qtdAb += 1;
    if(r?.tipo === "manutencao") row.qtdMn += 1;
  }

  const out = Array.from(mMap.values());
  out.sort((a,b)=> b.gasto - a.gasto);
  return out;
}

/* render */
function setDonut(el, parts){
  const total = parts.reduce((s,p)=> s + Number(p.value||0), 0);
  if(!el) return;

  if(total <= 0){
    el.style.background = "conic-gradient(#e5e5ea 0% 100%)";
    el.title = "Sem dados suficientes";
    return;
  }

  let acc = 0;
  const stops = parts.map(p=>{
    const v = Number(p.value||0);
    const start = (acc/total)*100;
    acc += v;
    const end = (acc/total)*100;
    return `${p.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
  });

  el.style.background = `conic-gradient(${stops.join(",")})`;
}

function setLegendDotColor(dotEl, color){
  if(dotEl) dotEl.style.background = color;
}

function preencherResumoMensalVeiculos(container, rows){
  if(!container) return;

  container.innerHTML = "";

  if(!rows.length){
    container.innerHTML = `<div style="color:#777;font-size:13px;">Sem dados ainda. Registre abastecimentos/manutenções para ver o resumo mensal por veículo.</div>`;
    return;
  }

  const tabela = document.createElement("div");
  tabela.className = "tabela-box tabela-veiculos";

  tabela.innerHTML = `
    <div class="cabecalho">
      <div>Veículo</div>
      <div class="c2">Litros/km</div>
      <div class="c3">R$/km</div>
      <div class="c4">Gasto mensal</div>
      <div class="c5">Km (Rodados)</div>
      <div class="c6">Abastecimentos</div>
    </div>
  `;

  for(const r of rows){
    // ✅ 3 casas para bater com 0,093 / 0,089 / 0,104
    const lpkTxt = r.kmRodados > 0 ? `${fmtNum(r.lpk, 3)} L/km` : "—";
    const rpkTxt = r.kmRodados > 0 && r.rpk > 0 ? `R$ ${fmtNum(r.rpk, 2)}/km` : "—";
    const gastoTxt = fmtBRL(r.gastoMensal);
    const kmTxt = r.kmRodados > 0 ? fmtKm(r.kmRodados) : "—";
    const abTxt = String(r.qtdAbastecimentos || 0);

    const linha = document.createElement("div");
    linha.className = "linha";
    linha.innerHTML = `
      <div class="nome" title="${r.nome}">${r.nome}</div>
      <div class="c2"><span class="pill">${lpkTxt}</span></div>
      <div class="c3"><span class="pill">${rpkTxt}</span></div>
      <div class="c4"><span class="pill">${gastoTxt}</span></div>
      <div class="c5"><span class="pill">${kmTxt}</span></div>
      <div class="c6"><span class="pill">${abTxt}</span></div>
    `;
    tabela.appendChild(linha);
  }

  container.appendChild(tabela);
}

function preencherResumoMensalMotoristas(container, rows){
  if(!container) return;

  container.innerHTML = "";

  if(!rows.length){
    container.innerHTML = `<div style="color:#777;font-size:13px;">Sem dados de motoristas no mês. (Precisa ter motoristaId nos registros.)</div>`;
    return;
  }

  const tabela = document.createElement("div");
  tabela.className = "tabela-box tabela-motoristas";

  tabela.innerHTML = `
    <div class="cabecalho">
      <div>Motorista</div>
      <div class="m2">Gasto</div>
      <div class="m3">Abastecimentos</div>
      <div class="m4">Manutenções</div>
    </div>
  `;

  for(const r of rows){
    const linha = document.createElement("div");
    linha.className = "linha";
    linha.innerHTML = `
      <div class="nome" title="${r.nome}">${r.nome}</div>
      <div class="m2"><span class="pill">${fmtBRL(r.gasto)}</span></div>
      <div class="m3"><span class="pill">${r.qtdAb}</span></div>
      <div class="m4"><span class="pill">${r.qtdMn}</span></div>
    `;
    tabela.appendChild(linha);
  }

  container.appendChild(tabela);
}

/* cards */
function atualizarCards({regMesAtual, regMesAnterior}){
  const now = new Date();
  const label = monthLabel(now);
  const mesEl = document.getElementById("cardMesAtual");
  if(mesEl) mesEl.textContent = label;

  const sAt = somaPorPago(regMesAtual);

  const cardTotal = document.getElementById("cardTotalMensal");
  const cardNao = document.getElementById("cardNaoPago");
  const cardJa  = document.getElementById("cardJaPago");
  if(cardTotal) cardTotal.textContent = fmtBRL(sAt.total);
  if(cardNao)   cardNao.textContent   = fmtBRL(sAt.naoPago);
  if(cardJa)    cardJa.textContent    = fmtBRL(sAt.pago);

  const cAt = consumoMedioLitrosPorKmTrechos(regMesAtual);
  const cAn = consumoMedioLitrosPorKmTrechos(regMesAnterior);
  const cardCons = document.getElementById("cardConsumoMedio");
  if(cardCons) cardCons.textContent = `${fmtNum(cAt, 3)} L/km`;

  let delta = 0;
  if(cAn > 0) delta = ((cAt - cAn) / cAn) * 100;
  const deltaEl = document.getElementById("cardConsumoDelta");
  if(deltaEl){
    const sinal = delta > 0 ? "+" : "";
    deltaEl.textContent = `${sinal}${fmtPct(delta)} vs mês anterior`;
  }

  const kAt = custoMedioReaisPorKmTrechos(regMesAtual);
  const kAn = custoMedioReaisPorKmTrechos(regMesAnterior);
  const cardCusto = document.getElementById("cardCustoMedio");
  if(cardCusto) cardCusto.textContent = `R$ ${fmtNum(kAt, 2)}/km`;

  let deltaK = 0;
  if(kAn > 0) deltaK = ((kAt - kAn) / kAn) * 100;
  const deltaKEl = document.getElementById("cardCustoDelta");
  if(deltaKEl){
    const sinal = deltaK > 0 ? "+" : "";
    deltaKEl.textContent = `${sinal}${fmtPct(deltaK)} vs mês anterior`;
  }

  // ✅ KM rodados: soma dos trechos (coerente com consumo do seu exemplo)
  const kmFrota = kmRodadosFrotaPorTrechosNoMes(regMesAtual);
  const kmEl = document.getElementById("cardKmMes");
  if(kmEl) kmEl.textContent = fmtKm(kmFrota);

  const litrosMes = regMesAtual
    .filter(r=> r?.tipo==="abastecimento")
    .reduce((s,r)=> s + Number(r.litros||0), 0);

  const litrosEl = document.getElementById("cardLitrosMes");
  if(litrosEl) litrosEl.textContent = fmtL(litrosMes);

  const qtdAb = regMesAtual.filter(r=> r?.tipo==="abastecimento").length;
  const qtdMn = regMesAtual.filter(r=> r?.tipo==="manutencao").length;

  const abEl = document.getElementById("cardQtdAbastecMes");
  if(abEl) abEl.textContent = String(qtdAb);

  const mnEl = document.getElementById("cardQtdManutMes");
  if(mnEl) mnEl.textContent = `Manutenções: ${qtdMn}`;
}

/* tooltip donut */
function bindTooltipDonut(donutEl, parts, formatterValue){
  if(!donutEl) return;
  donutEl.title = "Passe o mouse nas cores abaixo para ver os detalhes";

  donutEl.onmousemove = (ev)=>{
    const rect = donutEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top  + rect.height / 2;

    const dx = ev.clientX - cx;
    const dy = ev.clientY - cy;

    let ang = Math.atan2(dy, dx) * 180 / Math.PI;
    ang = (ang + 90 + 360) % 360;

    const total = parts.reduce((s,p)=> s + Number(p.value||0), 0);
    if(total <= 0){
      donutEl.title = "Sem dados suficientes";
      return;
    }

    let acc = 0;
    let found = null;
    for(const p of parts){
      const v = Number(p.value||0);
      const start = (acc/total)*360;
      acc += v;
      const end = (acc/total)*360;
      if(ang >= start && ang < end){
        found = p;
        break;
      }
    }

    donutEl.title = found ? `${found.label}\n${formatterValue(found)}` : "—";
  };

  donutEl.onmouseleave = ()=>{
    donutEl.title = "Passe o mouse nas cores abaixo para ver os detalhes";
  };
}

function atualizarGraficos({regMesAtual, veiculos}){
  const top3Qtd = topMaiorQtdAbastecimentos(regMesAtual, veiculos, 3);

  const parts1 = [
    { value: top3Qtd[0]?.qtd || 0, color: "#7a3cff", label: top3Qtd[0]?.nome || "—", meta: top3Qtd[0] },
    { value: top3Qtd[1]?.qtd || 0, color: "#f59e0b", label: top3Qtd[1]?.nome || "—", meta: top3Qtd[1] },
    { value: top3Qtd[2]?.qtd || 0, color: "#14a44d", label: top3Qtd[2]?.nome || "—", meta: top3Qtd[2] },
  ];

  const g1 = document.getElementById("graficoTop3Abastecimento");
  setDonut(g1, parts1);

  bindTooltipDonut(g1, parts1, (p)=>{
    const qtd = Number(p.value||0);
    const m = p.meta;
    const rpkTxt = (m && m.km > 0 && m.rpk > 0) ? ` | R$ ${fmtNum(m.rpk,2)}/km` : "";
    return `Abastecimentos: ${qtd}${rpkTxt}`;
  });

  const legA1 = document.querySelector('[data-leg="a1"]');
  const legA2 = document.querySelector('[data-leg="a2"]');
  const legA3 = document.querySelector('[data-leg="a3"]');
  if(legA1) legA1.textContent = top3Qtd[0]?.nome ? `${top3Qtd[0].nome}` : "—";
  if(legA2) legA2.textContent = top3Qtd[1]?.nome ? `${top3Qtd[1].nome}` : "—";
  if(legA3) legA3.textContent = top3Qtd[2]?.nome ? `${top3Qtd[2].nome}` : "—";

  const dotA1 = document.querySelector('[data-dot-a="a1"]');
  const dotA2 = document.querySelector('[data-dot-a="a2"]');
  const dotA3 = document.querySelector('[data-dot-a="a3"]');
  setLegendDotColor(dotA1, parts1[0].color);
  setLegendDotColor(dotA2, parts1[1].color);
  setLegendDotColor(dotA3, parts1[2].color);

  const tipAb = (x)=>{
    if(!x) return "—";
    const rpkTxt = (x.km > 0 && x.rpk > 0) ? `R$ ${fmtNum(x.rpk,2)}/km` : "R$/km: —";
    return `${x.nome}\nAbastecimentos: ${x.qtd}\n${rpkTxt}`;
  };
  if(dotA1) dotA1.title = tipAb(top3Qtd[0]);
  if(dotA2) dotA2.title = tipAb(top3Qtd[1]);
  if(dotA3) dotA3.title = tipAb(top3Qtd[2]);

  const top3Piores = topPioresCustoPorKm(regMesAtual, veiculos, 3);

  const colors2 = ["#ef4444", "#f59e0b", "#a78bfa"];
  const parts2 = [
    { value: top3Piores[0]?.rpk || 0, color: colors2[0], label: top3Piores[0]?.nome || "—", meta: top3Piores[0] },
    { value: top3Piores[1]?.rpk || 0, color: colors2[1], label: top3Piores[1]?.nome || "—", meta: top3Piores[1] },
    { value: top3Piores[2]?.rpk || 0, color: colors2[2], label: top3Piores[2]?.nome || "—", meta: top3Piores[2] },
  ];

  const g2 = document.getElementById("graficoTop3Eficiencia");
  setDonut(g2, parts2);

  bindTooltipDonut(g2, parts2, (p)=>{
    const v = Number(p.value||0);
    return `Custo por KM: R$ ${fmtNum(v,2)}/km`;
  });

  const le1 = document.querySelector('[data-leg="e1"]');
  const le2 = document.querySelector('[data-leg="e2"]');
  const le3 = document.querySelector('[data-leg="e3"]');
  if(le1) le1.textContent = top3Piores[0]?.nome ? `${top3Piores[0].nome}` : "—";
  if(le2) le2.textContent = top3Piores[1]?.nome ? `${top3Piores[1].nome}` : "—";
  if(le3) le3.textContent = top3Piores[2]?.nome ? `${top3Piores[2].nome}` : "—";

  const d1 = document.querySelector('[data-dot="e1"]');
  const d2 = document.querySelector('[data-dot="e2"]');
  const d3 = document.querySelector('[data-dot="e3"]');
  setLegendDotColor(d1, colors2[0]);
  setLegendDotColor(d2, colors2[1]);
  setLegendDotColor(d3, colors2[2]);

  const tipPk = (x)=>{
    if(!x) return "—";
    return `${x.nome}\nCusto por KM: R$ ${fmtNum(x.rpk,2)}/km`;
  };
  if(d1) d1.title = tipPk(top3Piores[0]);
  if(d2) d2.title = tipPk(top3Piores[1]);
  if(d3) d3.title = tipPk(top3Piores[2]);
}

function atualizarResumoVeiculos({regMesAtual, veiculos}){
  const rows = resumoMensalPorVeiculoRodados(regMesAtual, veiculos);
  preencherResumoMensalVeiculos(document.getElementById("listaCustoVeiculo"), rows);
}
function atualizarResumoMotoristas({regMesAtual, motoristas}){
  const rows = resumoMensalPorMotorista(regMesAtual, motoristas);
  preencherResumoMensalMotoristas(document.getElementById("listaMotoristas"), rows);
}

/* ajuda modal */
function abrirAjuda(titulo, texto){
  const modal = document.getElementById("modalAjuda");
  const t = document.getElementById("modalAjudaTitulo");
  const c = document.getElementById("modalAjudaTexto");
  if(t) t.textContent = titulo || "Ajuda";
  if(c) c.textContent = texto || "";
  modal.classList.add("ativo");
}
function fecharAjuda(){
  document.getElementById("modalAjuda").classList.remove("ativo");
}
function fecharAjudaSeFundo(e){
  if(e.target && e.target.id === "modalAjuda") fecharAjuda();
}
document.addEventListener("keydown", (e)=>{
  if(e.key === "Escape"){
    const m = document.getElementById("modalAjuda");
    if(m.classList.contains("ativo")) fecharAjuda();
  }
});

/* init */
(async function initDashboard(){
  document.querySelectorAll(".ajuda-card").forEach(btn=>{
    btn.addEventListener("click", (e)=>{
      e.stopPropagation();
      abrirAjuda(btn.getAttribute("data-help-title"), btn.getAttribute("data-help"));
    });
  });

  /* ✅ carrega e filtra registros por veículos existentes */
  const { registros: regsBrutos, veiculos, motoristas } = await carregarDados();
  const registros = filtrarRegistrosPorVeiculosExistentes(regsBrutos, veiculos);

  const now = new Date();
  const keyAtual = ymKey(now);
  const prev = new Date(now.getFullYear(), now.getMonth()-1, 1);
  const keyAnterior = ymKey(prev);

  const regMesAtual = registrosDoMes(registros, keyAtual);
  const regMesAnterior = registrosDoMes(registros, keyAnterior);

  atualizarCards({ regMesAtual, regMesAnterior });
  atualizarGraficos({ regMesAtual, veiculos });
  atualizarResumoVeiculos({ regMesAtual, veiculos });
  atualizarResumoMotoristas({ regMesAtual, motoristas });

  window.addEventListener("focus", async ()=>{
    /* ✅ também filtra no refresh */
    const { registros: r2Bruto, veiculos: v2, motoristas: m2 } = await carregarDados();
    const r2 = filtrarRegistrosPorVeiculosExistentes(r2Bruto, v2);

    const at2 = registrosDoMes(r2, keyAtual);
    const an2 = registrosDoMes(r2, keyAnterior);

    atualizarCards({ regMesAtual: at2, regMesAnterior: an2 });
    atualizarGraficos({ regMesAtual: at2, veiculos: v2 });
    atualizarResumoVeiculos({ regMesAtual: at2, veiculos: v2 });
    atualizarResumoMotoristas({ regMesAtual: at2, motoristas: m2 });
  });
})();

// ==============================
// CHAT IA NEXAR (FINAL - SEM DUPLICAÇÃO)
// ==============================

document.addEventListener("DOMContentLoaded", () => {
  const inputChat = document.querySelector(".nexar-chat-input input");
  const chatBody = document.querySelector(".nexar-chat-body");

  // Se não existir no DOM, não roda (evita erro no console)
  if (!inputChat || !chatBody) return;

  // adiciona mensagem no chat
  function adicionarMensagem(texto, tipo) {
    const div = document.createElement("div");
    div.classList.add("nexar-message", tipo); // tipo: "user" ou "bot"
    div.innerHTML = texto;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  // loader (bolinhas)
  function mostrarLoading() {
    if (document.getElementById("loading")) return;

    const div = document.createElement("div");
    div.classList.add("nexar-message", "bot");
    div.id = "loading";
    div.innerHTML = `
      <div class="nexar-typing">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function removerLoading() {
    const loading = document.getElementById("loading");
    if (loading) loading.remove();
  }

  // envia mensagem
  async function enviarMensagem() {
    const texto = (inputChat.value || "").trim();
    if (!texto) return;

    adicionarMensagem(texto, "user");
    inputChat.value = "";

    mostrarLoading();

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: texto })
      });

      // tenta ler json mesmo se der erro HTTP
      let data = {};
      try {
        data = await response.json();
      } catch (e) {
        data = {};
      }

      removerLoading();

      // se a API voltar algo do tipo Erro: 429... etc
      if (!response.ok) {
        const msg = data?.resposta || data?.erro || `Erro HTTP ${response.status}`;
        adicionarMensagem(msg, "bot");
        return;
      }

      adicionarMensagem(data.resposta || "Sem resposta do servidor.", "bot");
    } catch (error) {
      removerLoading();
      adicionarMensagem("Erro ao conectar com o servidor.", "bot");
    }
  }

  // ENTER envia
  inputChat.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      enviarMensagem();
    }
  });
});