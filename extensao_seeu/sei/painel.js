// Painel da leitura do SEI (vindo do NUSPEN). No APTO, o "serviço" roda nesta mesma página (servico.js) e entrega à função SEI
// do APTO. Textos de dados entram por textContent (nunca innerHTML).
import {
  estadoConexao, MODOS_PAINEL, estimativa, fasePainel, percentual, tempoRestante, formatarTempo,
  mensagemErro, textoResultado,
} from "./lib/estado.js";
import { sanitizar } from "./lib/estrutura.js";
import { enviar, aoSnapshot } from "./servico.js";

const EM_DEMO = !(globalThis.chrome && chrome.runtime && chrome.runtime.id) && /[?&]demo=/.test(location.search);
if (EM_DEMO) await import("./demo/shim_chrome.js");

const $ = (id) => document.getElementById(id);
let S = null; // ultima resposta de "estado"
let permissaoOk = false;
let estruturaSaida = "";
let temporizador = null;

const ICONE = { ok: "✓", aviso: "!", erro: "✕", neutro: "…" };

function pintarEstado(el, txt, e) {
  el.className = `estado ${e.tom}`;
  el.firstElementChild.textContent = ICONE[e.tom];
  txt.textContent = e.rotulo;
}

function linhasSelecionadas() {
  return $("selecionados").value.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
}

function desenhar() {
  if (!S) return;
  const cfg = S.config;
  const con = estadoConexao({ appOk: S.conexao.appOk, pareado: S.conexao.pareado, sessaoSei: S.conexao.pareado ? S.sessao : null, destinoFicticio: S.conexao.ficticio || S.adaptador.nome === "sei-ficticio" });
  $("faixa-lab").hidden = !con.destinoFicticio;
  pintarEstado($("estado-app"), $("txt-app"), con.app);
  pintarEstado($("estado-sessao"), $("txt-sessao"), con.sessao);
  $("proxima").hidden = !con.acaoSeguinte;
  $("proxima").textContent = con.acaoSeguinte ? `Próximo passo: ${con.acaoSeguinte}` : "";

  $("btn-revogar").hidden = true; // no APTO o código é renovado sozinho a cada abertura do programa
  $("validade").hidden = !S.conexao.expira;
  if (S.conexao.expira) $("validade").textContent = `O código vale até ${new Date(S.conexao.expira).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}.`;

  if (document.activeElement !== $("endereco")) $("endereco").value = cfg.baseSei || "";
  $("txt-permissao").textContent = !cfg.baseSei ? "Informe o endereço do SEI." : permissaoOk ? "Acesso permitido para este endereço." : "Ainda sem permissão para este endereço: use Permitir acesso.";

  const modo = $("modo").value || "todos";
  const m = MODOS_PAINEL.find((x) => x.id === modo);
  $("ajuda-modo").textContent = m.ajuda;
  $("bloco-selecionados").hidden = !(modo === "selecionados" || modo === "um");
  const est = estimativa({ modo, processosConhecidos: S.conexao.conhecidos.processos, tetoProcessos: cfg.tetoProcessos > 0 ? cfg.tetoProcessos : null, selecionados: linhasSelecionadas().length, pausaMs: cfg.pausaMs, limitePorMinuto: cfg.limitePorMinuto });
  $("estimativa").textContent = `Estimativa: ${est.texto}`;

  const snap = S.snapshot;
  const fase = fasePainel(snap);
  const emAndamento = fase === "lendo" || fase === "pausado";
  $("btn-iniciar").disabled = emAndamento;
  $("btn-retomar").hidden = !(snap && snap.fase === "parada" && textoResultado(snap).retomavel && snap.sessao);
  $("teto").value = cfg.tetoProcessos;
  $("limite").value = cfg.limitePorMinuto;

  $("progresso").hidden = !emAndamento;
  $("resultado").hidden = !(snap && ["concluida", "concluida_com_falhas", "parada", "erro"].includes(fase));
  if (emAndamento) desenharProgresso(snap, fase);
  if (!$("resultado").hidden) desenharResultado(snap, fase);
  $("faixa-erro").hidden = !(snap && snap.erro && fase === "erro");
  if (snap && snap.erro) { const e = mensagemErro(snap.erro); $("faixa-erro").textContent = `${e.titulo}. ${e.oQueFazer}`; }

  $("rodape").textContent = `Extensão versão ${S.versaoExtensao} · Leitor: ${S.adaptador.nome} ${S.adaptador.versao}${S.adaptador.ativo ? "" : " (desligado)"}`;
}

function desenharProgresso(snap, fase) {
  const total = ["todos", "documentos_novos"].includes(snap.modo) ? S.conexao.conhecidos.processos : 0;
  const pct = percentual(snap, total);
  const barra = $("barra");
  barra.classList.toggle("indeterminada", pct === null);
  barra.firstElementChild.style.setProperty("--p", String(pct ?? 0));
  if (pct === null) barra.removeAttribute("aria-valuenow"); else barra.setAttribute("aria-valuenow", String(pct));
  $("txt-progresso").textContent = fase === "pausado" ? "Leitura pausada. Nada é lido enquanto estiver assim." : pct === null ? "Lendo… o total não é conhecido de antemão." : `Lendo… ${pct}% dos processos conhecidos.`;
  const itens = [["Processos lidos", snap.processos], ["Documentos lidos", snap.documentosLidos], ["Novos", snap.novos], ["Modificados", snap.modificados], ["Já conhecidos", snap.documentosPulados], ["Falhas", snap.falhas, true], ["Inacessíveis", snap.indisponiveis, true]];
  const c = $("contagens");
  c.replaceChildren(...itens.map(([r, v, prob]) => {
    const d = document.createElement("div");
    if (prob && v) d.className = "problema";
    const s1 = document.createElement("strong"); s1.textContent = String(v || 0);
    const s2 = document.createElement("span"); s2.textContent = r;
    d.append(s1, s2);
    return d;
  }));
  const dec = snap.decorridoMs ?? (snap.iniciadoEm ? Date.now() - snap.iniciadoEm : 0);
  const resta = tempoRestante({ ...snap, decorridoMs: dec }, total);
  $("txt-tempo").textContent = `Decorrido: ${formatarTempo(dec / 1000)} · Restante estimado: ${resta === null ? "ainda não dá para estimar" : formatarTempo(resta)}`;
  $("btn-pausar").hidden = fase === "pausado";
  $("btn-continuar").hidden = fase !== "pausado";
}

async function desenharResultado(snap, fase) {
  const r = textoResultado(snap);
  $("txt-resultado").textContent = fase === "parada" || fase === "erro"
    ? `${mensagemErro(snap.parada || snap.erro).titulo}. ${mensagemErro(snap.parada || snap.erro).oQueFazer} ${r.resumo}.`
    : `Leitura concluída: ${r.resumo}.`;
  $("txt-problemas").textContent = r.problemas ? `Atenção: ${r.problemas}.` : "Nenhum item com erro ou inacessível.";

  const reg = (await enviar({ tipo: "registro" })).registro || [];
  const itens = reg.filter((e) => e.evento === "falha" || e.evento === "indisponivel").slice(-20);
  $("lista-problemas").replaceChildren(...itens.map((e) => { const li = document.createElement("li"); li.textContent = `${e.evento === "falha" ? "Falha" : "Inacessível"}: ${e.tipo} ${e.id}${e.codigo ? ` (código ${e.codigo})` : ""}`; return li; }));
}

async function atualizar() {
  S = await enviar({ tipo: "estado" });
  const cfg = S.config;
  if (cfg.baseSei) {
    try { permissaoOk = await chrome.permissions.contains({ origins: [`${new URL(cfg.baseSei).origin}/*`] }); } catch { permissaoOk = false; }
  }
  desenhar();
  const andando = S.snapshot && ["lendo", "iniciando"].includes(S.snapshot.fase);
  clearTimeout(temporizador);
  if (andando || S.rodando) temporizador = setTimeout(atualizar, 1000);
}

// ---------------------------------------------------------------- eventos
$("modo").replaceChildren(...MODOS_PAINEL.map((m) => { const o = document.createElement("option"); o.value = m.id; o.textContent = m.rotulo; return o; }));
$("modo").addEventListener("change", desenhar);
$("selecionados").addEventListener("input", desenhar);
$("btn-verificar").addEventListener("click", atualizar);

$("btn-parear").addEventListener("click", async () => {
  await enviar({ tipo: "parear", codigo: $("codigo").value });
  $("codigo").value = "";
  await atualizar();
});
$("btn-revogar").addEventListener("click", async () => { await enviar({ tipo: "revogar" }); await atualizar(); });

$("btn-permitir").addEventListener("click", async () => {
  let url;
  try { url = new URL($("endereco").value.trim()); } catch { $("txt-permissao").textContent = "Endereço inválido. Exemplo: https://sei.suainstituicao.gov.br"; return; }
  if (!["http:", "https:"].includes(url.protocol)) { $("txt-permissao").textContent = "Use um endereço que comece com http:// ou https://."; return; }
  const ok = await chrome.permissions.request({ origins: [`${url.origin}/*`] });
  if (ok) await enviar({ tipo: "config", config: { baseSei: url.origin } });
  await atualizar();
  $("txt-permissao").textContent = ok ? "Acesso permitido para este endereço." : "Você não permitiu o acesso. Sem isso a extensão não lê nada.";
});

$("btn-iniciar").addEventListener("click", () => {
  const con = estadoConexao({ appOk: S.conexao.appOk, pareado: S.conexao.pareado, sessaoSei: S.sessao });
  const modo = $("modo").value;
  const faltaEnd = !S.config.baseSei || !permissaoOk;
  if (!con.pronto || faltaEnd) {
    $("faixa-erro").hidden = false;
    $("faixa-erro").textContent = faltaEnd ? "Falta informar o endereço do SEI e permitir o acesso." : `Ainda não dá para ler. ${con.acaoSeguinte}`;
    return;
  }
  if ((modo === "selecionados" || modo === "um") && linhasSelecionadas().length === 0) { $("faixa-erro").hidden = false; $("faixa-erro").textContent = "Informe pelo menos um número de processo."; return; }
  $("faixa-erro").hidden = true;
  const est = estimativa({ modo, processosConhecidos: S.conexao.conhecidos.processos, tetoProcessos: S.config.tetoProcessos > 0 ? S.config.tetoProcessos : null, selecionados: linhasSelecionadas().length, pausaMs: S.config.pausaMs, limitePorMinuto: S.config.limitePorMinuto });
  $("t-conf").textContent = `Vai ler: ${MODOS_PAINEL.find((m) => m.id === modo).rotulo}. ${est.texto} A leitura é somente leitura e você pode pausar ou cancelar a qualquer momento. Confirmar?`;
  $("confirmacao").hidden = false;
  $("btn-confirmar").focus();
});
$("btn-voltar").addEventListener("click", () => { $("confirmacao").hidden = true; $("btn-iniciar").focus(); });
$("btn-confirmar").addEventListener("click", async () => {
  $("confirmacao").hidden = true;
  const modo = $("modo").value;
  enviar({ tipo: "iniciar", modo, selecionados: linhasSelecionadas() });
  setTimeout(atualizar, 400);
});
$("btn-retomar").addEventListener("click", () => { enviar({ tipo: "iniciar", modo: S.snapshot.modo, selecionados: [], retomar: S.snapshot.sessao }); setTimeout(atualizar, 400); });
$("btn-pausar").addEventListener("click", async () => { await enviar({ tipo: "pausar" }); await atualizar(); });
$("btn-continuar").addEventListener("click", async () => { await enviar({ tipo: "continuar" }); await atualizar(); });
$("btn-cancelar").addEventListener("click", async () => { await enviar({ tipo: "cancelar" }); await atualizar(); });

$("btn-salvar-config").addEventListener("click", async () => {
  const teto = Math.min(100000, Math.max(0, Number($("teto").value) || 0));
  const limite = Math.min(120, Math.max(1, Number($("limite").value) || 30));
  await enviar({ tipo: "config", config: { tetoProcessos: teto, limitePorMinuto: limite } });
  await atualizar();
});

$("btn-coletar").addEventListener("click", async () => {
  $("previa-estrutura").hidden = false;
  try {
    const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!aba || !/^https?:/.test(aba.url || "")) throw new Error("abra a página do SEI em uma aba comum");
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: aba.id }, func: () => document.documentElement.outerHTML });
    const r = sanitizar(result || "");
    estruturaSaida = r.saida;
    $("txt-previa").textContent = `${r.resumo.descricao} Marcas: ${r.resumo.tags}. Caracteres de texto trocados por marcadores: ${r.resumo.caracteresMascarados}. Atributos mantidos: ${r.resumo.atributosMantidos.join(", ") || "nenhum"}.`;
    $("pre-previa").textContent = r.saida.slice(0, 2500) + (r.saida.length > 2500 ? "\n… (o arquivo tem o resto, no mesmo formato)" : "");
    $("btn-gravar").disabled = false;
  } catch (e) {
    estruturaSaida = "";
    $("txt-previa").textContent = `Não foi possível coletar: ${e.message}.`;
    $("pre-previa").textContent = "";
    $("btn-gravar").disabled = true;
  }
});
$("btn-gravar").addEventListener("click", async () => {
  if (!estruturaSaida) return;
  const blob = new Blob([estruturaSaida], { type: "text/html" });
  if (globalThis.showSaveFilePicker) {
    try {
      const h = await showSaveFilePicker({ suggestedName: "estrutura-sanitizada.html", types: [{ description: "Estrutura sanitizada (HTML)", accept: { "text/html": [".html"] } }] });
      const w = await h.createWritable(); await w.write(blob); await w.close();
      $("txt-previa").textContent = "Arquivo gravado no computador, na pasta que você escolheu. Revise antes de entregar.";
      return;
    } catch { /* cancelado: cai para o download normal */ }
  }
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "estrutura-sanitizada.html"; a.click();
});

aoSnapshot((s) => { if (S) { S.snapshot = s; desenhar(); } });
// a coleta de estrutura precisa ler a aba do SEI (permissão "scripting", que a extensão do APTO não pede): fica para quando
// for calibrar o leitor do SEI real
if (!chrome.scripting) $("det-estrutura").hidden = true;
await atualizar();
if (EM_DEMO) globalThis.__painelPronto = true;
