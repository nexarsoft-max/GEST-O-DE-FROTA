/* =========================================================
   ABASTECIMENTO.JS (COMPLETO E CORRIGIDO)
   - init no DOMContentLoaded
   - seguro contra null.addEventListener
   - criaDivRegistro implementado (histórico volta a aparecer)
   - editar/excluir/salvar via /api/abastecimentos e /api/manutencoes
   ========================================================= */

/* ===== ABAS ===== */
function trocarAba(id, botao){
  document.querySelectorAll(".aba").forEach(b=>b.classList.remove("ativa"));
  if(botao) botao.classList.add("ativa");

  ["abastecimento","manutencao","historico"].forEach(sec=>{
    const el = document.getElementById(sec);
    if(el) el.classList.add("oculto");
  });

  const alvo = document.getElementById(id);
  if(alvo) alvo.classList.remove("oculto");
}

/* ===== DADOS ===== */
let registros = [];
let motoristas = [];
let veiculos = [];
let postos = [];

/* =========================================================
   ✅ ODOMETRO: "0" inicial + normalização por veículo
   ========================================================= */
const KEY_ODO_DIGITS = "odometro_digits_por_veiculo";

function getOdoDigitsMap(){
  try { return JSON.parse(localStorage.getItem(KEY_ODO_DIGITS)) || {}; }
  catch { return {}; }
}
function setOdoDigitsMap(map){
  localStorage.setItem(KEY_ODO_DIGITS, JSON.stringify(map));
}
function onlyDigits(s){ return String(s ?? "").replace(/[^\d]/g, ""); }

function getDigitsForVehicle(veiculoId){
  const map = getOdoDigitsMap();
  const cur = Number(map[String(veiculoId)] || 0);
  return Math.max(cur || 0, 6);
}

function updateDigitsForVehicle(veiculoId, digits){
  const map = getOdoDigitsMap();
  const cur = Number(map[String(veiculoId)] || 0);
  if(digits > cur){
    map[String(veiculoId)] = digits;
    setOdoDigitsMap(map);
  }
}

function normalizarOdometroStr(odometroDigitado, veiculoId){
  const dig = onlyDigits(odometroDigitado);
  if(!dig) return "";
  const pad = Math.max(getDigitsForVehicle(veiculoId), dig.length);
  updateDigitsForVehicle(veiculoId, pad);
  return dig.padStart(pad, "0");
}

function setupOdometerInput(){
  const input = document.getElementById("odometro");
  const selVeiculo = document.getElementById("selectVeiculo");
  if(!input || !selVeiculo) return;

  input.addEventListener("focus", () => {
    if(input.value.trim() === ""){
      input.value = "0";
      requestAnimationFrame(()=> {
        try { input.setSelectionRange(input.value.length, input.value.length); } catch {}
      });
    }
  });

  input.addEventListener("input", () => {
    input.value = onlyDigits(input.value);
  });

  input.addEventListener("blur", () => {
    const veiculoId = parseInt(selVeiculo.value);
    if(!veiculoId) return;
    const norm = normalizarOdometroStr(input.value, veiculoId);
    input.value = norm;
  });
}

/* ===== ORDENAR POR DATA/HORA ===== */
function ordenarMaisRecentePrimeiro(lista){
  return [...lista].sort((a,b)=>{
    const ta = new Date(`${a.data}T${a.hora || "00:00"}`).getTime();
    const tb = new Date(`${b.data}T${b.hora || "00:00"}`).getTime();
    return tb - ta;
  });
}

/* ===== POPULAR SELECTS ===== */
function popular(id,array,placeholder,tipo){
  const sel = document.getElementById(id);
  if(!sel) return;

  sel.innerHTML = "";
  const opt = document.createElement("option");
  opt.value = "";
  opt.textContent = placeholder;
  opt.disabled = true;
  opt.selected = true;
  sel.appendChild(opt);

  array.forEach(item=>{
    const o = document.createElement("option");
    if(tipo==="motorista"){ o.value = item.id; o.textContent = item.nome; }
    else if(tipo==="veiculo"){ o.value = item.id; o.textContent = `${item.placa} - ${item.modelo}`; }
    else if(tipo==="posto"){ o.value = item.id; o.textContent = item.nome; }
    sel.appendChild(o);
  });
}

function popularTudo(){
  ["selectMotorista","selectMotoristaManut","filtroMotorista"]
    .forEach(id=>popular(id,motoristas,"Selecione o motorista","motorista"));

  ["selectVeiculo","selectVeiculoManut","filtroVeiculo"]
    .forEach(id=>popular(id,veiculos,"Selecione o veículo","veiculo"));

  ["selectPosto"]
    .forEach(id=>popular(id,postos,"Posto/Prestador","posto"));
}

/* ===== COMBUSTÍVEL DEPENDENTE DO POSTO ===== */
function montarCombustiveisDoPosto(){
  const selectPosto = document.getElementById("selectPosto");
  const selComb = document.getElementById("selectCombustivel");
  if(!selectPosto || !selComb) return;

  if(selectPosto.dataset.bound === "1") return;
  selectPosto.dataset.bound = "1";

  selectPosto.addEventListener("change", ()=> {
    const postoId = parseInt(selectPosto.value);
    const posto = postos.find(p=>p.id===postoId);

    selComb.innerHTML = '<option value="" disabled selected>Selecione o combustível</option>';

    if(posto){
      (posto.combustiveis || []).forEach(c=>{
        const o = document.createElement("option");
        o.value = c.tipo;
        o.textContent = `${c.tipo} - R$ ${Number(c.preco || 0).toFixed(2)}`;
        selComb.appendChild(o);
      });
    }
    atualizarPreco();
  });
}

function bindPrecoListeners(){
  const litrosEl = document.getElementById("inputLitros");
  const combEl = document.getElementById("selectCombustivel");

  if(litrosEl && litrosEl.dataset.bound !== "1"){
    litrosEl.dataset.bound = "1";
    litrosEl.addEventListener("input", atualizarPreco);
  }
  if(combEl && combEl.dataset.bound !== "1"){
    combEl.dataset.bound = "1";
    combEl.addEventListener("change", atualizarPreco);
  }
}

function atualizarPreco(){
  const litrosEl = document.getElementById("inputLitros");
  const postoEl = document.getElementById("selectPosto");
  const combEl  = document.getElementById("selectCombustivel");
  const inputPreco = document.getElementById("inputPreco");

  if(!litrosEl || !postoEl || !combEl || !inputPreco) return;

  const litros = parseFloat(litrosEl.value);
  const postoId = parseInt(postoEl.value);
  const combustivel = combEl.value;

  if(!postoId || !combustivel || isNaN(litros)){
    inputPreco.value = "";
    return;
  }

  const posto = postos.find(p => p.id === postoId);
  const precoUnitario = posto?.combustiveis?.find(c => c.tipo === combustivel)?.preco || 0;
  inputPreco.value = (litros * precoUnitario).toFixed(2);
}

function calcularPrecoUnitarioAtual(postoId, combustivel){
  const posto = postos.find(p => p.id === postoId);
  const unit = posto?.combustiveis?.find(c => c.tipo === combustivel)?.preco || 0;
  return Number(unit || 0);
}

/* ===== UPLOAD -> BASE64 ===== */
let comprovanteAbastecimentoBase64 = "";
let comprovanteManutencaoBase64 = "";

function lerImagemParaBase64(input, previewId, callback){
  const preview = document.getElementById(previewId);
  if(!input || !preview) return;

  if(input.dataset.bound === "1") return;
  input.dataset.bound = "1";

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if(!file){
      preview.style.display = "none";
      preview.removeAttribute("src");
      callback("");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      preview.src = e.target.result;
      preview.style.display = "block";
      callback(e.target.result);
    };
    reader.readAsDataURL(file);
  });
}

/* ===== RESET ===== */
function resetForm(){
  const campos = document.querySelectorAll(
    "#abastecimento input, #abastecimento select, #abastecimento textarea, " +
    "#manutencao input, #manutencao select, #manutencao textarea"
  );

  campos.forEach(el=>{
    if(el.type === "checkbox"){ el.checked = false; return; }
    if(el.type === "file"){ el.value = ""; return; }
    if(el.tagName === "SELECT"){ el.selectedIndex = 0; }
    else{ el.value = ""; }
  });

  ["previewAbastecimento","previewManutencao"].forEach(id=>{
    const img = document.getElementById(id);
    if(img){
      img.style.display = "none";
      img.removeAttribute("src");
    }
  });

  comprovanteAbastecimentoBase64 = "";
  comprovanteManutencaoBase64 = "";

  const selComb = document.getElementById("selectCombustivel");
  if(selComb){
    selComb.innerHTML = '<option value="" disabled selected>Selecione o combustível</option>';
  }
  const inputPreco = document.getElementById("inputPreco");
  if(inputPreco) inputPreco.value = "";
}

/* =========================================================
   ✅ REGISTRAR ABASTECIMENTO (BANCO)
   ========================================================= */
async function registrarAbastecimento(){
  const dataEl = document.getElementById("data");
  const horaEl = document.getElementById("hora");
  const motoristaEl = document.getElementById("selectMotorista");
  const postoEl = document.getElementById("selectPosto");
  const veiculoEl = document.getElementById("selectVeiculo");
  const odoEl = document.getElementById("odometro");
  const combEl = document.getElementById("selectCombustivel");
  const litrosEl = document.getElementById("inputLitros");
  const precoEl = document.getElementById("inputPreco");
  const obsEl = document.getElementById("obsAbastecimento");
  const pagoEl = document.getElementById("pagoAbastecimento");

  if(!dataEl || !horaEl || !motoristaEl || !postoEl || !veiculoEl || !odoEl || !combEl || !litrosEl || !precoEl || !obsEl || !pagoEl){
    alert("Tela incompleta: alguns campos não foram encontrados.");
    return;
  }

  const data = dataEl.value;
  const hora = horaEl.value;
  const motoristaId = parseInt(motoristaEl.value);
  const postoId = parseInt(postoEl.value);
  const veiculoId = parseInt(veiculoEl.value);

  const odometroBruto = odoEl.value.trim();
  const odometro = normalizarOdometroStr(odometroBruto, veiculoId);

  const combustivel = combEl.value;
  const litros = parseFloat(litrosEl.value);
  const preco = parseFloat(precoEl.value);
  const obs = obsEl.value.trim();
  const pago = pagoEl.checked;

  if(!data || !hora || !motoristaId || !postoId || !veiculoId || !odometro || !combustivel || isNaN(litros) || isNaN(preco)){
    alert("Preencha todos os campos!");
    return;
  }

  const precoUnitario = calcularPrecoUnitarioAtual(postoId, combustivel);

  const payload = {
    data,
    hora,
    motorista_id: motoristaId,
    posto_id: postoId,
    veiculo_id: veiculoId,
    combustivel,
    litros,
    preco_total: preco,
    preco_unitario: precoUnitario,
    odometro,
    pago,
    obs,
    comprovante: comprovanteAbastecimentoBase64 || ""
  };

  const resp = await fetch("/api/abastecimentos", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });

  const json = await resp.json().catch(()=> ({}));
  if(!resp.ok || !json.sucesso){
    alert(json.erro || "Erro ao salvar abastecimento.");
    return;
  }

  alert("Abastecimento registrado!");
  resetForm();

  // ✅ atualiza lista e já abre a aba histórico (pra você VER na hora)
  await carregarHistoricoDoBanco();
  const btnHist = document.querySelector('.aba[onclick*="historico"]');
  trocarAba("historico", btnHist || null);
}

/* =========================================================
   ✅ REGISTRAR MANUTENÇÃO (BANCO)
   ========================================================= */
async function registrarManutencao(){
  const dataEl = document.getElementById("dataManut");
  const horaEl = document.getElementById("horaManut");
  const motoristaEl = document.getElementById("selectMotoristaManut");
  const veiculoEl = document.getElementById("selectVeiculoManut");
  const valorEl = document.getElementById("inputValorManut");
  const prestadorEl = document.getElementById("inputPrestadorManut");
  const obsEl = document.getElementById("obsManutencao");
  const pagoEl = document.getElementById("pagoManutencao");

  if(!dataEl || !horaEl || !motoristaEl || !veiculoEl || !valorEl || !prestadorEl || !obsEl || !pagoEl){
    alert("Tela incompleta: alguns campos não foram encontrados.");
    return;
  }

  const data = dataEl.value;
  const hora = horaEl.value;
  const motoristaId = parseInt(motoristaEl.value);
  const veiculoId = parseInt(veiculoEl.value);
  const valor = parseFloat(valorEl.value);
  const prestador = prestadorEl.value.trim();
  const obs = obsEl.value.trim();
  const pago = pagoEl.checked;

  if(!data || !hora || !motoristaId || !veiculoId || isNaN(valor) || !prestador){
    alert("Preencha todos os campos!");
    return;
  }

  const payload = {
    data,
    hora,
    motorista_id: motoristaId,
    veiculo_id: veiculoId,
    valor,
    prestador,
    pago,
    obs,
    comprovante: comprovanteManutencaoBase64 || ""
  };

  const resp = await fetch("/api/manutencoes", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });

  const json = await resp.json().catch(()=> ({}));
  if(!resp.ok || !json.sucesso){
    alert(json.erro || "Erro ao salvar manutenção.");
    return;
  }

  alert("Manutenção registrada!");
  resetForm();
  await carregarHistoricoDoBanco();
  const btnHist = document.querySelector('.aba[onclick*="historico"]');
  trocarAba("historico", btnHist || null);
}

/* =========================================================
   ✅ HISTÓRICO (BANCO)
   ========================================================= */
async function carregarHistoricoDoBanco(){
  const resp = await fetch("/api/historico", { cache: "no-store" });
  const data = await resp.json().catch(()=> ([]));

  if(!resp.ok){
    console.log("Erro carregar histórico:", data);
    registros = [];
  }else{
    registros = Array.isArray(data) ? data : [];
  }

  atualizarFiltroPostoPrestador();
  carregarHistorico();
}

function carregarHistorico(){
  const lista = document.getElementById("listaHistorico");
  if(!lista) return;

  lista.innerHTML = "";
  const ordenados = ordenarMaisRecentePrimeiro(registros);

  if(!ordenados.length){
    const vazio = document.createElement("div");
    vazio.style.padding = "14px";
    vazio.style.color = "#666";
    vazio.textContent = "Nenhum registro encontrado.";
    lista.appendChild(vazio);
    return;
  }

  ordenados.forEach((r)=>lista.appendChild(criarDivRegistro(r)));
}

/* ===== FILTROS ===== */
function atualizarFiltroPostoPrestador(){
  const sel = document.getElementById("filtroPostoPrestador");
  if(!sel) return;

  const valorAtual = sel.value;

  const prestadores = [...new Set(
    registros
      .filter(r=>r.tipo==="manutencao" && r.prestador)
      .map(r=>(r.prestador || "").trim())
  )].filter(Boolean).sort((a,b)=>a.localeCompare(b));

  sel.innerHTML = "";

  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "Posto/Prestador";
  opt0.selected = true;
  sel.appendChild(opt0);

  postos.forEach(p=>{
    const o = document.createElement("option");
    o.value = `posto:${p.id}`;
    o.textContent = `Posto: ${p.nome}`;
    sel.appendChild(o);
  });

  prestadores.forEach(nome=>{
    const o = document.createElement("option");
    o.value = `prestador:${nome}`;
    o.textContent = `Prestador: ${nome}`;
    sel.appendChild(o);
  });

  if(valorAtual) sel.value = valorAtual;
}

function filtrarHistorico(){
  const dataEl = document.getElementById("filtroData");
  const motoristaEl = document.getElementById("filtroMotorista");
  const veiculoEl = document.getElementById("filtroVeiculo");
  const postoPrestEl = document.getElementById("filtroPostoPrestador");
  const tipoEl = document.getElementById("filtroTipo");
  const pagoEl = document.getElementById("filtroPago");
  const lista = document.getElementById("listaHistorico");

  if(!dataEl || !motoristaEl || !veiculoEl || !postoPrestEl || !tipoEl || !pagoEl || !lista) return;

  const data = dataEl.value;
  const motoristaId = parseInt(motoristaEl.value);
  const veiculoId = parseInt(veiculoEl.value);
  const postoPrestador = postoPrestEl.value;
  const tipo = tipoEl.value;
  const somentePago = pagoEl.checked;

  let filtrados = [...registros];

  if(data) filtrados = filtrados.filter(r => r.data === data);
  if(!isNaN(motoristaId)) filtrados = filtrados.filter(r => Number(r.motoristaId) === motoristaId);
  if(!isNaN(veiculoId)) filtrados = filtrados.filter(r => Number(r.veiculoId) === veiculoId);

  if(tipo === "abastecimento"){
    filtrados = filtrados.filter(r => r.tipo === "abastecimento");
  } else if(tipo === "manutencao"){
    filtrados = filtrados.filter(r => r.tipo === "manutencao");
  } else if(tipo === "abastecimento_nao_pago"){
    filtrados = filtrados.filter(r => r.tipo === "abastecimento" && r.pago === false);
  } else if(tipo === "manutencao_nao_pago"){
    filtrados = filtrados.filter(r => r.tipo === "manutencao" && r.pago === false);
  }

  if(postoPrestador){
    const [kind, val] = postoPrestador.split(":");
    if(kind === "posto"){
      const pid = parseInt(val);
      filtrados = filtrados.filter(r => r.tipo === "abastecimento" && Number(r.postoId) === pid);
    } else if(kind === "prestador"){
      filtrados = filtrados.filter(r => r.tipo === "manutencao" && (r.prestador || "").trim() === val);
    }
  }

  if(somentePago){
    filtrados = filtrados.filter(r => r.pago === true);
  }

  filtrados = ordenarMaisRecentePrimeiro(filtrados);

  lista.innerHTML = "";
  if(!filtrados.length){
    const vazio = document.createElement("div");
    vazio.style.padding = "14px";
    vazio.style.color = "#666";
    vazio.textContent = "Nenhum registro encontrado com esses filtros.";
    lista.appendChild(vazio);
    return;
  }
  filtrados.forEach((r)=>lista.appendChild(criarDivRegistro(r)));
}

function limparFiltros(){
  const d = document.getElementById("filtroData");
  const t = document.getElementById("filtroTipo");
  const p = document.getElementById("filtroPago");

  if(d) d.value = "";
  if(t) t.value = "";
  if(p) p.checked = false;

  const s1 = document.getElementById("filtroMotorista"); if(s1) s1.selectedIndex = 0;
  const s2 = document.getElementById("filtroVeiculo"); if(s2) s2.selectedIndex = 0;
  const s3 = document.getElementById("filtroPostoPrestador"); if(s3) s3.selectedIndex = 0;

  carregarHistorico();
}

/* =========================================================
   ✅ EDITAR / EXCLUIR (BANCO)
   ========================================================= */
function optionsMotoristas(selectedId){
  return motoristas.map(m =>
    `<option value="${m.id}" ${Number(m.id)===Number(selectedId)?"selected":""}>${m.nome}</option>`
  ).join("");
}
function optionsVeiculos(selectedId){
  return veiculos.map(v => {
    const label = `${v.placa} - ${v.modelo}`;
    return `<option value="${v.id}" ${Number(v.id)===Number(selectedId)?"selected":""}>${label}</option>`;
  }).join("");
}
function optionsPostos(selectedId){
  return postos.map(p =>
    `<option value="${p.id}" ${Number(p.id)===Number(selectedId)?"selected":""}>${p.nome}</option>`
  ).join("");
}
function optionsCombustivel(postoId, selected){
  const posto = postos.find(p => Number(p.id) === Number(postoId));
  const lista = (posto?.combustiveis || []);
  const base = `<option value="" disabled ${selected ? "" : "selected"}>Selecione o combustível</option>`;
  const opts = lista.map(c => {
    const tipo = String(c.tipo);
    const label = `${tipo} - R$ ${Number(c.preco || 0).toFixed(2)}`;
    return `<option value="${tipo}" ${tipo===selected?"selected":""}>${label}</option>`;
  }).join("");
  return base + opts;
}

function setEditMode(div, isEdit){
  div.querySelectorAll("[data-view]").forEach(el => el.style.display = isEdit ? "none" : "");
  div.querySelectorAll("[data-edit]").forEach(el => el.style.display = isEdit ? "" : "none");

  const be = div.querySelector(".btn-editar");
  const bx = div.querySelector(".btn-excluir");
  const bs = div.querySelector(".btn-salvar");
  const bc = div.querySelector(".btn-cancelar-edicao");

  if(be) be.style.display = isEdit ? "none" : "";
  if(bx) bx.style.display = isEdit ? "none" : "";
  if(bs) bs.style.display = isEdit ? "" : "none";
  if(bc) bc.style.display = isEdit ? "" : "none";
}

async function excluirRegistroNoBanco(r){
  const ok = confirm("Tem certeza que deseja excluir este registro?");
  if(!ok) return;

  const url = (r.tipo === "abastecimento")
    ? `/api/abastecimentos/${r.id}`
    : `/api/manutencoes/${r.id}`;

  const resp = await fetch(url, { method: "DELETE" });
  const json = await resp.json().catch(()=> ({}));

  if(!resp.ok || !json.sucesso){
    alert(json.erro || "Erro ao excluir.");
    return;
  }

  alert("Registro excluído!");
  await carregarHistoricoDoBanco();
}

async function salvarEdicaoNoBanco(div, r){
  if(r.tipo === "abastecimento"){
    const data = div.querySelector('[data-e="data"]').value;
    const hora = div.querySelector('[data-e="hora"]').value;

    const motorista_id = parseInt(div.querySelector('[data-e="motorista"]').value);
    const veiculo_id = parseInt(div.querySelector('[data-e="veiculo"]').value);
    const posto_id = parseInt(div.querySelector('[data-e="posto"]').value);
    const combustivel = div.querySelector('[data-e="combustivel"]').value;

    const litros = parseFloat(div.querySelector('[data-e="litros"]').value);
    const odometroRaw = (div.querySelector('[data-e="odometro"]').value || "").trim();
    const odometro = normalizarOdometroStr(odometroRaw, veiculo_id);

    const pago = div.querySelector('[data-e="pago"]').checked;
    const obs = (div.querySelector('[data-e="obs"]').value || "").trim();

    if(!data || !hora || !motorista_id || !veiculo_id || !posto_id || !combustivel || isNaN(litros)){
      alert("Preencha os campos obrigatórios.");
      return;
    }

    const preco_unitario = calcularPrecoUnitarioAtual(posto_id, combustivel);
    const preco_total = Number(litros) * Number(preco_unitario);

    const payload = {
      data,
      hora,
      motorista_id,
      veiculo_id,
      posto_id,
      combustivel,
      litros,
      preco_total,
      preco_unitario,
      odometro,
      pago,
      obs,
      comprovante: r.comprovante || ""
    };

    const resp = await fetch(`/api/abastecimentos/${r.id}`,{
      method:"PUT",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });

    const json = await resp.json().catch(()=> ({}));
    if(!resp.ok || !json.sucesso){
      alert(json.erro || "Erro ao salvar edição.");
      return;
    }

    alert("Registro atualizado!");
    await carregarHistoricoDoBanco();
    return;
  }

  // manutencao
  const data = div.querySelector('[data-e="data"]').value;
  const hora = div.querySelector('[data-e="hora"]').value;

  const motorista_id = parseInt(div.querySelector('[data-e="motorista"]').value);
  const veiculo_id = parseInt(div.querySelector('[data-e="veiculo"]').value);

  const valor = parseFloat(div.querySelector('[data-e="valor"]').value);
  const prestador = (div.querySelector('[data-e="prestador"]').value || "").trim();

  const pago = div.querySelector('[data-e="pago"]').checked;
  const obs = (div.querySelector('[data-e="obs"]').value || "").trim();

  if(!data || !hora || !motorista_id || !veiculo_id || !prestador || isNaN(valor)){
    alert("Preencha os campos obrigatórios.");
    return;
  }

  const payload = {
    data,
    hora,
    motorista_id,
    veiculo_id,
    valor,
    prestador,
    pago,
    obs,
    comprovante: r.comprovante || ""
  };

  const resp = await fetch(`/api/manutencoes/${r.id}`,{
    method:"PUT",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });

  const json = await resp.json().catch(()=> ({}));
  if(!resp.ok || !json.sucesso){
    alert(json.erro || "Erro ao salvar edição.");
    return;
  }

  alert("Registro atualizado!");
  await carregarHistoricoDoBanco();
}

/* =========================================================
   ✅ HISTÓRICO UI (AGORA IMPLEMENTADO!)
   ========================================================= */

function nomeMotorista(id){
  const m = motoristas.find(x=>Number(x.id)===Number(id));
  return m ? m.nome : "";
}
function nomeVeiculo(id){
  const v = veiculos.find(x=>Number(x.id)===Number(id));
  return v ? `${v.placa} - ${v.modelo}` : "";
}
function nomePosto(id){
  const p = postos.find(x=>Number(x.id)===Number(id));
  return p ? p.nome : "";
}
function fmtBRL(v){
  const n = Number(v || 0);
  return n.toLocaleString("pt-BR", { style:"currency", currency:"BRL" });
}
function safe(v){ return (v ?? "").toString(); }

function criarDivRegistro(r){
  const div = document.createElement("div");
  div.className = "registro-item";
  div.style.background = "#fff";
  div.style.border = "1px solid #e7e7ef";
  div.style.borderRadius = "14px";
  div.style.padding = "14px";
  div.style.boxShadow = "0 10px 24px rgba(17,17,26,0.06)";
  div.style.marginBottom = "12px";

  const titulo = (r.tipo === "abastecimento") ? "Abastecimento" : "Manutenção";
  const dataHora = `${safe(r.data)} ${safe(r.hora)}`.trim();

  const motoristaTxt = nomeMotorista(r.motoristaId) || `#${r.motoristaId || ""}`;
  const veiculoTxt = nomeVeiculo(r.veiculoId) || `#${r.veiculoId || ""}`;

  const pagoTxt = r.pago ? "Sim" : "Não";

  // --- VIEW LINES ---
  let linhasView = `
    <div style="display:flex; gap:10px; justify-content:space-between; align-items:flex-start; flex-wrap:wrap;">
      <div>
        <div style="font-weight:800; font-size:14px;">${titulo}</div>
        <div style="color:#666; font-size:12px; margin-top:2px;">${dataHora}</div>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <span style="font-size:12px; padding:6px 10px; border-radius:999px; background:${r.pago ? "#e8fff1" : "#fff1f1"}; border:1px solid ${r.pago ? "#bdebd0" : "#ffd0d0"};">
          Já pago: <b>${pagoTxt}</b>
        </span>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin-top:12px;">
      <div><b>Motorista:</b> ${motoristaTxt}</div>
      <div><b>Veículo:</b> ${veiculoTxt}</div>
      ${
        r.tipo === "abastecimento"
        ? `<div><b>Posto:</b> ${nomePosto(r.postoId) || `#${r.postoId||""}`}</div>`
        : `<div><b>Prestador:</b> ${safe(r.prestador) || "-"}</div>`
      }
      ${
        r.tipo === "abastecimento"
        ? `<div><b>Combustível:</b> ${safe(r.combustivel)}</div>`
        : `<div><b>Valor:</b> ${fmtBRL(r.valor)}</div>`
      }
      ${
        r.tipo === "abastecimento"
        ? `<div><b>Litros:</b> ${Number(r.litros||0).toFixed(2)}</div>`
        : `<div><b>Obs:</b> ${safe(r.obs) || "-"}</div>`
      }
      ${
        r.tipo === "abastecimento"
        ? `<div><b>Total:</b> ${fmtBRL(r.preco)}</div>`
        : `<div><b>Comprovante:</b> ${r.comprovante ? "Disponível" : "—"}</div>`
      }
      ${
        r.tipo === "abastecimento"
        ? `<div><b>Odômetro:</b> ${safe(r.odometro) || "-"}</div>`
        : `<div><b>Data/Hora:</b> ${dataHora}</div>`
      }
    </div>

    ${
      safe(r.obs).trim()
        ? `<div style="margin-top:10px;"><b>Observações:</b> ${safe(r.obs)}</div>`
        : ``
    }
  `;

  // comprovante (view)
  const temComprovante = !!(r.comprovante && String(r.comprovante).trim());
  const btnComprovante = temComprovante
    ? `<button class="btn-comprovante" type="button" style="padding:10px 12px;border-radius:10px;border:1px solid #e7e7ef;background:#f7f7fb;cursor:pointer;">Ver comprovante</button>`
    : "";

  // --- EDIT FORM ---
  let htmlEdit = "";

  if(r.tipo === "abastecimento"){
    htmlEdit = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin-top:12px;">
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Data</div>
          <input data-e="data" type="date" value="${safe(r.data)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Hora</div>
          <input data-e="hora" type="time" value="${safe(r.hora)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Motorista</div>
          <select data-e="motorista" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsMotoristas(r.motoristaId)}
          </select>
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Veículo</div>
          <select data-e="veiculo" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsVeiculos(r.veiculoId)}
          </select>
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Posto</div>
          <select data-e="posto" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsPostos(r.postoId)}
          </select>
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Combustível</div>
          <select data-e="combustivel" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsCombustivel(r.postoId, r.combustivel)}
          </select>
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Litros</div>
          <input data-e="litros" type="number" step="0.01" value="${Number(r.litros||0)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>

        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Odômetro</div>
          <input data-e="odometro" value="${safe(r.odometro)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>

        <div style="display:flex;align-items:flex-end;gap:10px;">
          <label style="display:flex;align-items:center;gap:8px;padding:10px 12px;border:1px solid #e7e7ef;border-radius:10px;background:#f7f7fb;width:fit-content;">
            <input data-e="pago" type="checkbox" ${r.pago ? "checked" : ""} />
            Já pago
          </label>
        </div>

        <div style="grid-column:1/-1;">
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Observações</div>
          <textarea data-e="obs" style="width:100%;min-height:70px;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">${safe(r.obs)}</textarea>
        </div>
      </div>
    `;

  } else {
    htmlEdit = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin-top:12px;">
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Data</div>
          <input data-e="data" type="date" value="${safe(r.data)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Hora</div>
          <input data-e="hora" type="time" value="${safe(r.hora)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Motorista</div>
          <select data-e="motorista" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsMotoristas(r.motoristaId)}
          </select>
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Veículo</div>
          <select data-e="veiculo" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">
            ${optionsVeiculos(r.veiculoId)}
          </select>
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Prestador</div>
          <input data-e="prestador" value="${safe(r.prestador)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>
        <div>
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Valor</div>
          <input data-e="valor" type="number" step="0.01" value="${Number(r.valor||0)}" style="width:100%;padding:10px;border:1px solid #e7e7ef;border-radius:10px;" />
        </div>
        <div style="display:flex;align-items:flex-end;gap:10px;">
          <label style="display:flex;align-items:center;gap:8px;padding:10px 12px;border:1px solid #e7e7ef;border-radius:10px;background:#f7f7fb;width:fit-content;">
            <input data-e="pago" type="checkbox" ${r.pago ? "checked" : ""} />
            Já pago
          </label>
        </div>
        <div style="grid-column:1/-1;">
          <div style="font-size:12px;color:#666;margin-bottom:4px;">Observações</div>
          <textarea data-e="obs" style="width:100%;min-height:70px;padding:10px;border:1px solid #e7e7ef;border-radius:10px;">${safe(r.obs)}</textarea>
        </div>
      </div>
    `;
  }

  div.innerHTML = `
    <div data-view>
      ${linhasView}
    </div>

    <div data-edit style="display:none;">
      ${htmlEdit}
    </div>

    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; justify-content:flex-end;">
      ${btnComprovante}

      <button class="btn-editar" type="button" style="padding:10px 12px;border-radius:10px;border:1px solid #e7e7ef;background:#fff;cursor:pointer;">Editar</button>
      <button class="btn-excluir" type="button" style="padding:10px 12px;border-radius:10px;border:1px solid #ffd0d0;background:#fff1f1;cursor:pointer;">Excluir</button>

      <button class="btn-salvar" type="button" style="display:none;padding:10px 12px;border-radius:10px;border:1px solid #cbb8ff;background:#6f2cff;color:#fff;cursor:pointer;">Salvar</button>
      <button class="btn-cancelar-edicao" type="button" style="display:none;padding:10px 12px;border-radius:10px;border:1px solid #e7e7ef;background:#f7f7fb;cursor:pointer;">Cancelar</button>
    </div>
  `;

  // --- listeners ---
  const btnEditar = div.querySelector(".btn-editar");
  const btnExcluir = div.querySelector(".btn-excluir");
  const btnSalvar = div.querySelector(".btn-salvar");
  const btnCancelar = div.querySelector(".btn-cancelar-edicao");
  const btnComp = div.querySelector(".btn-comprovante");

  if(btnEditar){
    btnEditar.addEventListener("click", ()=>{
      setEditMode(div, true);

      // se mudar posto no edit, atualiza combustíveis (abastecimento)
      if(r.tipo === "abastecimento"){
        const selPosto = div.querySelector('[data-e="posto"]');
        const selComb = div.querySelector('[data-e="combustivel"]');
        if(selPosto && selComb && selPosto.dataset.bound !== "1"){
          selPosto.dataset.bound = "1";
          selPosto.addEventListener("change", ()=>{
            selComb.innerHTML = optionsCombustivel(parseInt(selPosto.value), "");
          });
        }
      }
    });
  }

  if(btnCancelar){
    btnCancelar.addEventListener("click", ()=>{
      setEditMode(div, false);
    });
  }

  if(btnSalvar){
    btnSalvar.addEventListener("click", async ()=>{
      await salvarEdicaoNoBanco(div, r);
    });
  }

  if(btnExcluir){
    btnExcluir.addEventListener("click", async ()=>{
      await excluirRegistroNoBanco(r);
    });
  }

  if(btnComp){
    btnComp.addEventListener("click", ()=>{
      abrirModal(r.comprovante);
    });
  }

  return div;
}

/* =========================================================
   ✅ MODAL / ZOOM / ARRASTAR
   ========================================================= */
let zoomLevel = 1;
let posX = 0;
let posY = 0;
let startX = 0;
let startY = 0;
let dragging = false;

function aplicarTransform(){
  const img = document.getElementById("modalImg");
  if(!img) return;
  img.style.transform = `translate(calc(-50% + ${posX}px), calc(-50% + ${posY}px)) scale(${zoomLevel})`;
}

function abrirModal(src){
  const modal = document.getElementById("modalComprovante");
  const img = document.getElementById("modalImg");
  if(!modal || !img) return;

  img.src = src;
  zoomLevel = 1;
  posX = 0;
  posY = 0;
  aplicarTransform();
  modal.classList.add("ativo");
}

function fecharModal(){
  const modal = document.getElementById("modalComprovante");
  if(modal) modal.classList.remove("ativo");
}

function fecharModalSeFundo(e){
  if(e.target && e.target.id === "modalComprovante"){
    fecharModal();
  }
}

function zoomIn(){
  zoomLevel = Math.min(zoomLevel + 0.2, 6);
  aplicarTransform();
}
function zoomOut(){
  zoomLevel = Math.max(zoomLevel - 0.2, 0.6);
  aplicarTransform();
}
function resetZoom(){
  zoomLevel = 1;
  posX = 0;
  posY = 0;
  aplicarTransform();
}

function bindModalEvents(){
  document.addEventListener("keydown", (e)=>{
    if(e.key === "Escape"){
      const modal = document.getElementById("modalComprovante");
      if(modal && modal.classList.contains("ativo")) fecharModal();
    }
  });

  const modalView = document.getElementById("modalView");
  if(!modalView) return;

  if(modalView.dataset.bound === "1") return;
  modalView.dataset.bound = "1";

  modalView.addEventListener("mousedown", (e)=>{
    dragging = true;
    startX = e.clientX - posX;
    startY = e.clientY - posY;
    modalView.classList.add("arrastando");
  });

  window.addEventListener("mousemove", (e)=>{
    if(!dragging) return;
    posX = e.clientX - startX;
    posY = e.clientY - startY;
    aplicarTransform();
  });

  window.addEventListener("mouseup", ()=>{
    dragging = false;
    modalView.classList.remove("arrastando");
  });

  modalView.addEventListener("wheel", (e)=>{
    e.preventDefault();
    const delta = Math.sign(e.deltaY);
    if(delta > 0) zoomOut();
    else zoomIn();
  }, { passive:false });
}

/* =========================================================
   ✅ INIT: carregar catálogo + histórico
   ========================================================= */
async function init(){
  setupOdometerInput();
  bindPrecoListeners();
  bindModalEvents();

  lerImagemParaBase64(
    document.getElementById("comprovanteAbastecimento"),
    "previewAbastecimento",
    (b64)=>comprovanteAbastecimentoBase64=b64
  );

  lerImagemParaBase64(
    document.getElementById("comprovanteManutencao"),
    "previewManutencao",
    (b64)=>comprovanteManutencaoBase64=b64
  );

  const resp = await fetch("/api/catalogo", { cache: "no-store" });
  const json = await resp.json().catch(()=> ({}));

  if(!resp.ok){
    alert(json.erro || "Erro ao carregar catálogo.");
    return;
  }

  motoristas = json.motoristas || [];
  veiculos = json.veiculos || [];
  postos = json.postos || [];

  popularTudo();
  montarCombustiveisDoPosto();
  await carregarHistoricoDoBanco();
}

/* =========================================================
   ✅ DOM Ready
   ========================================================= */
document.addEventListener("DOMContentLoaded", () => {
  init().catch(err => console.error("Erro init:", err));
});

/* =========================================================
   ✅ Expor funções para onclick do HTML
   ========================================================= */
window.trocarAba = trocarAba;
window.resetForm = resetForm;
window.registrarAbastecimento = registrarAbastecimento;
window.registrarManutencao = registrarManutencao;
window.filtrarHistorico = filtrarHistorico;
window.limparFiltros = limparFiltros;

window.abrirModal = abrirModal;
window.fecharModal = fecharModal;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;
window.fecharModalSeFundo = fecharModalSeFundo;