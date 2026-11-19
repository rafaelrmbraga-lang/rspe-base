// APTO - painel no SEEU: página da extensão dentro da aba do processo (moldura). Sem resultado guardado, pede à página do
// SEEU (que busca em segundo plano o RSPE que o próprio SEEU gera) o PDF do relatório e o entrega ao motor; mostra o resultado
// e avisa a página (recolher e contagem da lingueta). Nada aqui fala com o SEEU diretamente.
"use strict";
const C = self.APTO_PAINEL_CORE;
const processo = decodeURIComponent((location.hash.match(/p=([^&]+)/) || [])[1] || "");
const $ = (id) => document.getElementById(id);
const SEEU = "https://seeu.pje.jus.br";
let atual = null, esperandoRspe = null, ultimoRspe = null;

function avisarPagina(d) {
  try { parent.postMessage(d, SEEU); } catch (e) { /* segue */ }
}

function pintar(res) {
  if (res && res.diag) res.ext = chrome.runtime.getManifest().version;
  atual = res;
  $("corpo").innerHTML = C.html(res);
  $("corpo").setAttribute("aria-busy", res && res.estado === "carregando" ? "true" : "false");
  const p = (res && res.painel) || {};
  if (p.nome) $("nome").textContent = p.nome;
  const ok = res && res.estado === "ok";
  const c = ok ? p.contagem : { verde: 0, amarelo: 0 };
  $("copiar").disabled = !ok;
  $("resumo").disabled = !ok;
  $("lg-v").innerHTML = ok ? C.ICO.verde + " " + c.verde + " confere" : "";
  $("lg-a").innerHTML = ok ? C.ICO.amarelo + " " + c.amarelo + " conferir" : "";
  $("lg-v").hidden = $("lg-a").hidden = !ok;
  avisarPagina({ apto: "contagem", c });
}

window.addEventListener("message", (ev) => {
  if (ev.origin !== SEEU || ev.source !== parent) return;
  const d = ev.data || {};
  if (d.apto === "progresso" && atual && atual.estado === "carregando") pintar(Object.assign({}, atual, { etapa: d.etapa }));
  if (d.apto === "rspe" && esperandoRspe) { esperandoRspe(d); esperandoRspe = null; }
});

function pedirRspe(novo) {
  return new Promise((ok) => { esperandoRspe = ok; avisarPagina({ apto: "lerRspe", novo: !!novo }); });
}
const FALHA_RSPE = {
  sem_link: ["sem_rspe", "O link do relatório da situação processual não está nesta página do SEEU. Abra o processo pela consulta e clique em Ler de novo."],
  http: ["sem_dados", "O SEEU não entregou o relatório da situação processual (erro no SEEU ou sessão expirada). Recarregue a página e clique em Ler de novo."],
  nao_pdf: ["sem_dados", "O SEEU não devolveu o relatório em PDF (sessão expirada?). Recarregue a página do SEEU e clique em Ler de novo."],
  sem_resposta: ["sem_dados", "O SEEU não respondeu ao pedido do relatório. Confira a conexão e clique em Ler de novo."],
};

async function analisar(forcar) {
  const b = $("atualizar");
  b.setAttribute("aria-busy", "true");
  b.disabled = true;
  try {
    if (!forcar) {
      const g = await chrome.runtime.sendMessage({ tipo: "painelGuardado", processo }).catch(() => null);
      if (g) return pintar(g);
    }
    const primeira = !(await chrome.storage.session.get("painelMotorPronto")).painelMotorPronto;
    pintar({ estado: "carregando", primeira, etapa: "Buscando o relatório da situação processual no SEEU" });
    chrome.runtime.sendMessage({ tipo: "painelPreparar" }).catch(() => null);   // o motor carrega enquanto o relatório chega
    const d = forcar === "ficha" && ultimoRspe ? ultimoRspe : await pedirRspe(forcar === true);
    if (!d.b64) {
      const [estado, motivo] = FALHA_RSPE[d.erro] || ["sem_dados", ""];
      return pintar({ estado, motivo, diag: d.diag || null });
    }
    ultimoRspe = d;
    pintar(Object.assign({}, atual, { etapa: "Lendo o relatório e calculando com as regras do APTO" }));
    let res;
    try { res = await chrome.runtime.sendMessage({ tipo: "painelAnalisar", processo, b64: d.b64 }); } catch (e) { res = null; }
    if (res && res.estado !== "ok") res.diag = Object.assign({}, d.diag || {}, { motor: res.estado });
    res = res || { estado: "erro", motivo: "a extensão não respondeu: recarregue a página do SEEU" };
    if (res.estado === "ok") await chrome.storage.session.set({ painelMotorPronto: true });
    pintar(res);
  } finally {
    b.removeAttribute("aria-busy");
    b.disabled = false;
  }
}

$("atualizar").addEventListener("click", () => analisar(true));

// ---------- ficha disciplinar: carregar (botão ou arrastar) e retirar; a ficha só é lida neste computador
function aviso(t) {
  const el = $("toast");
  el.textContent = t;
  el.hidden = false;
  clearTimeout(aviso._t);
  aviso._t = setTimeout(() => { el.hidden = true; }, 4500);
}
async function enviarFicha(arq) {
  if (!arq) return;
  if (!/\.pdf$/i.test(arq.name) && arq.type !== "application/pdf") return aviso("Escolha o PDF da ficha disciplinar do SIAPEN.");
  if (arq.size > 15 * 1024 * 1024) return aviso("PDF grande demais para uma ficha disciplinar.");
  pintar({ estado: "carregando", etapa: "Lendo a ficha disciplinar" });
  const bytes = new Uint8Array(await arq.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  const r = await chrome.runtime.sendMessage({ tipo: "painelFicha", processo, b64: btoa(bin), arquivo: arq.name }).catch(() => null);
  if (!r || !r.ok) aviso("Ficha não lida: " + ((r && r.erro) || "a extensão não respondeu"));
  else aviso("Ficha de " + (r.resumo.nome || "?") + (r.resumo.impressa ? ", impressa em " + r.resumo.impressa : "") + ", lida.");
  analisar("ficha");
}
$("corpo").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-acao]");
  if (!b) return;
  if (b.dataset.acao === "ficha-carregar") $("arquivoFicha").click();
  if (b.dataset.acao === "copiar-diag") {
    const campo = $("corpo").querySelector(".diag textarea");
    aviso((await copiar(campo ? campo.value : "", campo)) ? "Diagnóstico copiado (sem dados pessoais)." : "Selecione o texto do diagnóstico e copie com Ctrl+C.");
  }
  if (b.dataset.acao === "ficha-retirar") {
    await chrome.runtime.sendMessage({ tipo: "painelFichaRetirar", processo }).catch(() => null);
    aviso("Ficha retirada do painel.");
    analisar("ficha");
  }
});
$("arquivoFicha").addEventListener("change", (e) => { enviarFicha(e.target.files[0]); e.target.value = ""; });
let arrastando = 0;
document.addEventListener("dragenter", (e) => { if ([...(e.dataTransfer.types || [])].includes("Files")) { arrastando++; $("soltar").hidden = false; } });
document.addEventListener("dragleave", () => { if (--arrastando <= 0) { arrastando = 0; $("soltar").hidden = true; } });
document.addEventListener("dragover", (e) => { e.preventDefault(); });
document.addEventListener("drop", (e) => {
  e.preventDefault();
  arrastando = 0;
  $("soltar").hidden = true;
  enviarFicha(e.dataTransfer.files && e.dataTransfer.files[0]);
});
$("recolher").addEventListener("click", () => avisarPagina({ apto: "recolher" }));
// copiar: a área de transferência pela API e, se a página do SEEU não deixar, pelo comando de cópia sobre um campo de texto
async function copiar(txt, campo) {
  try { await navigator.clipboard.writeText(txt); return true; } catch (e) { /* segue para o comando de cópia */ }
  let el = campo, temp = false;
  if (!el) { el = document.createElement("textarea"); el.value = txt; el.setAttribute("readonly", ""); el.style.cssText = "position:fixed;left:-9999px;top:0"; document.body.appendChild(el); temp = true; }
  el.focus();
  el.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  if (temp) el.remove();
  return ok;
}
$("copiar").addEventListener("click", async () => {
  if (!atual) return;
  $("copiar").textContent = (await copiar(C.resumo(atual))) ? "Copiado" : "Não copiou";
  setTimeout(() => { $("copiar").textContent = "Copiar"; }, 2000);
});

// ---------- resumo para o assistido (o texto do APTO, conferido aqui; o PDF pelo mesmo gerador do APTO)
const R = self.APTO_RESUMO;
let res = null;   // o resumo em edição
function modoResumo(on) {
  ["resumo", "copiar"].forEach((id) => { $(id).hidden = on; });
  ["resVoltar", "resPdf"].forEach((id) => { $(id).hidden = !on; });
  $("lg-v").hidden = $("lg-a").hidden = on || !(atual && atual.estado === "ok");
  $("atualizar").disabled = on;
}
function pintarResumo() {
  $("corpo").innerHTML = R.tela(res);
  $("corpo").setAttribute("aria-busy", "false");
  $("resPdf").disabled = !res.onde;
  $("resPdf").title = res.onde ? "Abre o resumo numa aba do navegador e já pede a impressão" : "Escolha antes onde é o atendimento";
}
async function abrirResumo() {
  modoResumo(true);
  $("corpo").innerHTML = C.html({ estado: "carregando", etapa: "Montando o resumo para o assistido" });
  let r = await chrome.runtime.sendMessage({ tipo: "painelResumo", processo }).catch(() => null);
  if (r && !r.ok && r.erro === "sem_analise") {   // o motor foi reiniciado: refaz a análise e tenta de novo
    modoResumo(false);
    await analisar(true);
    modoResumo(true);
    r = await chrome.runtime.sendMessage({ tipo: "painelResumo", processo }).catch(() => null);
  }
  if (!r || !r.ok) { modoResumo(false); pintar(atual); return aviso("Resumo não montado: " + ((r && r.erro) || "a extensão não respondeu")); }
  res = Object.assign(r.d, { onde: "" });   // onde é o atendimento: a pessoa escolhe sempre
  pintarResumo();
  $("corpo").scrollTop = 0;
}
$("resumo").addEventListener("click", abrirResumo);
$("resVoltar").addEventListener("click", () => { res = null; modoResumo(false); pintar(atual); });
$("corpo").addEventListener("change", (e) => {
  if (!res) return;
  const t = e.target;
  if (t.name === "resOnde" || t.name === "resVs") { R.ler(res, $("corpo")); pintarResumo(); }
  if (t.dataset && t.dataset.prov) { R.ler(res, $("corpo")); R.prov(res, t.dataset.prov, t.checked); pintarResumo(); }
});
$("corpo").addEventListener("click", (e) => {
  const b = res && e.target.closest("[data-mais]");
  if (!b) return;
  R.ler(res, $("corpo"));
  res.secoes[+b.dataset.mais].itens.push("");
  pintarResumo();
});
$("resPdf").addEventListener("click", async () => {
  if (!res) return;
  R.ler(res, $("corpo"));
  if (!res.onde) return aviso("Escolha onde é o atendimento.");
  const b = $("resPdf");
  b.disabled = true;
  b.setAttribute("aria-busy", "true");
  b.textContent = "Gerando o PDF…";
  try {
    const r = await chrome.runtime.sendMessage({ tipo: "painelResumoPdf", d: R.saida(res), canhoto: res.onde === "unidade" }).catch(() => null);
    if (!r || !r.ok) return aviso("PDF não gerado: " + ((r && r.erro) || "a extensão não respondeu"));
    // abre o resumo numa aba do navegador, já pedindo a impressão (o visualizador de PDF também deixa baixar)
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    await chrome.storage.session.set({ ["resumoImprimir:" + id]: { b64: r.b64, nome: res.nome || "" } });
    await chrome.tabs.create({ url: chrome.runtime.getURL("painel/imprimir.html#" + id), active: true });
    aviso("Resumo aberto para imprimir" + (res.onde === "unidade" && !r.canhoto ? " (sem o canhoto: o texto não coube em uma folha com ele)" : "") +
      (r.verso ? " · com o verso: imprima frente e verso" : "") + ".");
  } finally {
    b.disabled = false;
    b.removeAttribute("aria-busy");
    b.textContent = "Imprimir";
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (res) { res = null; modoResumo(false); pintar(atual); } else avisarPagina({ apto: "recolher" });
});
$("proc").textContent = processo;
analisar(false);
