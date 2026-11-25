// =====================================================================
// Painel MtM — lê os CSVs da pasta "dados/" e monta números, gráficos
// e tabelas. Não há servidor: o GitHub Pages só entrega arquivos, e
// todo o trabalho acontece aqui, no navegador de quem abre a página.
// =====================================================================

// ---------- 1. Formatação de números no padrão brasileiro ----------
const fmtReais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const fmtReaisCurto = new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 2,
});
const fmtNumero = (casas) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const fmtTaxa = (t) => fmtNumero(2).format(t * 100) + "%";               // 0.1555 -> "15,55%"
const fmtData = (iso) => iso.split("-").reverse().join("/");             // 2026-11-19 -> 19/11/2026
const classeSinal = (v) => (v > 0 ? "positivo" : v < 0 ? "negativo" : "");

// ---------- 2. Leitura de CSV ----------
// Lê um CSV e devolve uma lista de objetos: [{coluna: valor, ...}, ...].
// Trata textos entre aspas (que podem ter vírgula dentro).
async function lerCsv(caminho) {
  const resposta = await fetch(caminho);
  if (!resposta.ok) throw new Error(`Não consegui abrir ${caminho}`);
  const texto = (await resposta.text()).replace(/^﻿/, ""); // remove o BOM do Excel

  const linhas = [];
  let campo = "", linha = [], dentroDeAspas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (dentroDeAspas) {
      if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
      else if (c === '"') dentroDeAspas = false;
      else campo += c;
    } else if (c === '"') dentroDeAspas = true;
    else if (c === ",") { linha.push(campo); campo = ""; }
    else if (c === "\n") { linha.push(campo); linhas.push(linha); linha = []; campo = ""; }
    else if (c !== "\r") campo += c;
  }
  if (campo || linha.length) { linha.push(campo); linhas.push(linha); }

  const [cabecalho, ...dados] = linhas;
  return dados.map((valores) => {
    const obj = {};
    cabecalho.forEach((col, i) => {
      const v = valores[i];
      // Converte para número quando o valor é numérico
      obj[col] = v !== "" && !isNaN(v) ? Number(v) : v;
    });
    return obj;
  });
}

// ---------- 3. Estado da página ----------
let dados = {};       // CSVs carregados
let graficos = {};    // gráficos Chart.js já criados (para atualizar no filtro)

// ---------- 4. Início ----------
async function iniciar() {
  try {
    const [resumo, fato, carteiras, qualidade] = await Promise.all([
      lerCsv("dados/vw_resumo_carteira.csv"),
      lerCsv("dados/fato_posicao_mtm.csv"),
      lerCsv("dados/dim_carteira.csv"),
      lerCsv("dados/vw_qualidade_dados.csv"),
    ]);
    dados = { resumo, fato, carteiras, qualidade };
  } catch (erro) {
    document.querySelector("main").innerHTML =
      `<div class="cartao"><h2>Não foi possível carregar os dados</h2>
       <p class="nota">${erro.message}. Se abriu o arquivo direto no computador, rode
       <code>python -m http.server</code> dentro da pasta <code>docs</code> e acesse
       <code>http://localhost:8000</code>.</p></div>`;
    return;
  }

  // Preenche o filtro de carteiras
  const filtro = document.getElementById("filtro-carteira");
  dados.carteiras.forEach((c) => filtro.add(new Option(c.nome_carteira, c.codigo_carteira)));
  filtro.addEventListener("change", () => desenhar(filtro.value));

  mostrarQualidade();
  verificarPbix();
  desenhar("TODAS");
}

// ---------- 5. Desenha tudo para a carteira escolhida ----------
function desenhar(carteira) {
  const todas = carteira === "TODAS";
  const resumo = dados.resumo.filter((r) => todas || r.codigo_carteira === carteira);
  const fato = dados.fato.filter((r) => todas || r.codigo_carteira === carteira);

  // Soma as carteiras por data (quando o filtro é "Todas")
  const porData = new Map();
  for (const r of resumo) {
    const d = porData.get(r.data_base) || { curva: 0, mtm: 0, agio: 0, pnl: 0, dv01: 0, durPeso: 0 };
    d.curva += r.pl_curva;
    d.mtm += r.pl_mtm;
    d.agio += r.agio_desagio_total;
    d.pnl += r.pnl_dia_total;
    d.dv01 += r.dv01_total;
    d.durPeso += r.duration_ponderada * r.pl_mtm; // duration ponderada pelo valor de cada carteira
    porData.set(r.data_base, d);
  }
  const datas = [...porData.keys()].sort();
  const ultimaData = datas[datas.length - 1];
  const hoje = porData.get(ultimaData);

  // KPIs
  document.getElementById("data-base").textContent = "Data-base: " + fmtData(ultimaData);
  document.getElementById("kpi-mtm").textContent = fmtReaisCurto.format(hoje.mtm);
  document.getElementById("kpi-curva").textContent = fmtReaisCurto.format(hoje.curva);
  preencherComSinal("kpi-agio", hoje.agio, fmtReais.format(hoje.agio));
  preencherComSinal("kpi-pnl", hoje.pnl, fmtReais.format(hoje.pnl));
  document.getElementById("kpi-dv01").textContent = fmtReais.format(hoje.dv01);
  document.getElementById("kpi-duration").textContent = fmtNumero(2).format(hoje.durPeso / hoje.mtm);

  // Gráfico 1: evolução do PL
  criarOuAtualizar("graf-evolucao", {
    type: "line",
    data: {
      labels: datas.map(fmtData),
      datasets: [
        { label: "PL na Curva", data: datas.map((d) => porData.get(d).curva), borderColor: "#6fa3ff", pointRadius: 0, borderWidth: 2 },
        { label: "PL a Mercado", data: datas.map((d) => porData.get(d).mtm), borderColor: "#1f4fd1", pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: opcoesBase({ eixoY: (v) => fmtReaisCurto.format(v) }),
  });

  // Gráfico 2: ágio/deságio na última data (por carteira, ou por título se filtrou uma carteira)
  const posHoje = fato.filter((r) => r.data_base === ultimaData);
  let rotulos, valores;
  if (todas) {
    const nomes = Object.fromEntries(dados.carteiras.map((c) => [c.codigo_carteira, c.nome_carteira]));
    const somas = {};
    posHoje.forEach((r) => (somas[r.codigo_carteira] = (somas[r.codigo_carteira] || 0) + r.agio_desagio));
    rotulos = Object.keys(somas).map((k) => nomes[k]);
    valores = Object.values(somas);
    document.getElementById("titulo-agio").textContent = "Ágio / Deságio por carteira";
  } else {
    rotulos = posHoje.map((r) => r.codigo_titulo);
    valores = posHoje.map((r) => r.agio_desagio);
    document.getElementById("titulo-agio").textContent = "Ágio / Deságio por título";
  }
  criarOuAtualizar("graf-agio", {
    type: "bar",
    data: {
      labels: rotulos,
      datasets: [{ label: "Ágio / Deságio", data: valores, backgroundColor: valores.map((v) => (v >= 0 ? "#1a8a4a" : "#c0392b")) }],
    },
    options: { ...opcoesBase({ eixoX: (v) => fmtReaisCurto.format(v) }), indexAxis: "y", plugins: { legend: { display: false } } },
  });

  // Gráfico 3: curva de juros (sempre com todos os títulos, não depende do filtro)
  const ultimaGeral = dados.fato.reduce((m, r) => (r.data_base > m ? r.data_base : m), "");
  const taxas = {};
  dados.fato.filter((r) => r.data_base === ultimaGeral).forEach((r) => (taxas[r.codigo_titulo] = r.taxa_mercado));
  const vencimentos = Object.keys(taxas).sort();
  criarOuAtualizar("graf-curva", {
    type: "line",
    data: {
      labels: vencimentos.map((t) => t.replace("LTN_", "").slice(0, 7).split("-").reverse().join("/")),
      datasets: [{ label: "Taxa de mercado", data: vencimentos.map((t) => taxas[t] * 100), borderColor: "#1f4fd1", backgroundColor: "#1f4fd1", pointRadius: 5 }],
    },
    options: { ...opcoesBase({ eixoY: (v) => fmtNumero(1).format(v) + "%" }), plugins: { legend: { display: false } } },
  });

  // Gráfico 4: P&L diário
  const pnl = datas.map((d) => porData.get(d).pnl);
  criarOuAtualizar("graf-pnl", {
    type: "bar",
    data: {
      labels: datas.map(fmtData),
      datasets: [{ label: "P&L do dia", data: pnl, backgroundColor: pnl.map((v) => (v >= 0 ? "#1a8a4a" : "#c0392b")) }],
    },
    options: { ...opcoesBase({ eixoY: (v) => fmtReaisCurto.format(v) }), plugins: { legend: { display: false } } },
  });

  // Tabela de posições
  const nomes = Object.fromEntries(dados.carteiras.map((c) => [c.codigo_carteira, c.nome_carteira]));
  document.querySelector("#tabela-posicoes tbody").innerHTML = posHoje
    .map((r) => `<tr>
      <td>${nomes[r.codigo_carteira]}</td><td>${r.codigo_titulo}</td>
      <td class="num">${fmtNumero(0).format(r.quantidade)}</td>
      <td class="num">${fmtTaxa(r.taxa_compra)}</td><td class="num">${fmtTaxa(r.taxa_mercado)}</td>
      <td class="num">${fmtNumero(2).format(r.pu_curva)}</td><td class="num">${fmtNumero(2).format(r.pu_mtm)}</td>
      <td class="num">${fmtReais.format(r.valor_mtm)}</td>
      <td class="num ${classeSinal(r.agio_desagio)}">${fmtReais.format(r.agio_desagio)}</td>
      <td class="num">${fmtReais.format(r.dv01)}</td></tr>`)
    .join("");
}

// ---------- 6. Qualidade de dados (só a execução mais recente) ----------
function mostrarQualidade() {
  const ultimoRun = Math.max(...dados.qualidade.map((r) => r.run_id));
  const regras = dados.qualidade.filter((r) => r.run_id === ultimoRun);
  const todasOk = regras.every((r) => r.status_regra === "OK");

  const selo = document.getElementById("selo-dq");
  selo.textContent = todasOk ? `Qualidade: ${regras.length}/${regras.length} OK` : "Qualidade: há falhas";
  selo.className = "selo " + (todasOk ? "ok" : "falha");

  document.querySelector("#tabela-dq tbody").innerHTML = regras
    .map((r) => `<tr><td>${r.regra}</td><td>${r.severidade}</td>
      <td class="${r.status_regra === "OK" ? "positivo" : "negativo"}">${r.status_regra}</td>
      <td class="num">${r.linhas_afetadas}</td><td>${r.detalhe}</td></tr>`)
    .join("");
}

// ---------- 7. Mostra o link do .pbix só se o arquivo existir ----------
async function verificarPbix() {
  try {
    const r = await fetch("dados/painel_mtm.pbix", { method: "HEAD" });
    if (r.ok) document.getElementById("link-pbix").hidden = false;
  } catch { /* arquivo não existe: o link continua escondido */ }
}

// ---------- 8. Ajudantes de gráfico ----------
function preencherComSinal(id, valor, texto) {
  const el = document.getElementById(id);
  el.textContent = texto;
  el.className = "valor " + classeSinal(valor);
}

function opcoesBase({ eixoX, eixoY } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: { ticks: { maxTicksLimit: 8, ...(eixoX && { callback: eixoX }) }, grid: { display: false } },
      y: { ticks: { ...(eixoY && { callback: eixoY }) } },
    },
  };
}

// Apaga o gráfico antigo (se existir) e desenha de novo com os dados do filtro atual
function criarOuAtualizar(id, config) {
  if (graficos[id]) graficos[id].destroy();
  graficos[id] = new Chart(document.getElementById(id), config);
}

iniciar();
