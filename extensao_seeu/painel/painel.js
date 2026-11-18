// APTO - painel no SEEU: página da extensão dentro da aba do processo (moldura). Pede a análise ao service worker,
// mostra e avisa a página do SEEU (recolher e contagem da lingueta). Nada aqui fala com o SEEU.
"use strict";
const C = self.APTO_PAINEL_CORE;
const processo = decodeURIComponent((location.hash.match(/p=([^&]+)/) || [])[1] || "");
const $ = (id) => document.getElementById(id);
let atual = null;

function avisarPagina(d) {
  // só para a página que contém a moldura (a do SEEU); ela confere a origem da extensão
  try { parent.postMessage(Object.assign({ apto: "" }, d), "https://seeu.pje.jus.br"); } catch (e) { /* segue */ }
}

function pintar(res) {
  atual = res;
  $("corpo").innerHTML = C.html(res);
  const p = (res && res.painel) || {};
  $("proc").textContent = processo + (p.nome ? " · " + p.nome : "");
  const ok = res && (res.estado === "confere" || res.estado === "diverge");
  $("copiar").disabled = !ok;
  avisarPagina({ apto: "contagem", c: ok ? p.contagem : { crit: 0, urg: 0, med: 0 } });
}

async function analisar(forcar) {
  const b = $("atualizar");
  b.setAttribute("aria-busy", "true");
  b.disabled = true;
  const primeira = !(await chrome.storage.session.get("painelMotorPronto")).painelMotorPronto;
  if (forcar || !atual) pintar({ estado: "carregando", primeira });
  let res;
  try { res = await chrome.runtime.sendMessage({ tipo: "painelAnalisar", processo, forcar: !!forcar }); } catch (e) { res = null; }
  res = res || { estado: "erro", motivo: "a extensão não respondeu: recarregue a página do SEEU" };
  if (res.estado === "confere" || res.estado === "diverge") await chrome.storage.session.set({ painelMotorPronto: true });
  pintar(res);
  b.removeAttribute("aria-busy");
  b.disabled = false;
}

$("atualizar").addEventListener("click", () => analisar(true));
$("recolher").addEventListener("click", () => avisarPagina({ apto: "recolher" }));
$("abrirApto").addEventListener("click", async () => {
  const r = await chrome.runtime.sendMessage({ tipo: "painelAbrirApto", processo }).catch(() => null);
  if (!r || !r.ok) pintar({ estado: "sem_apto" });
});
$("copiar").addEventListener("click", async () => {
  if (!atual) return;
  try { await navigator.clipboard.writeText(C.resumo(atual)); $("copiar").textContent = "Copiado ✓"; } catch (e) { $("copiar").textContent = "Não copiou"; }
  setTimeout(() => { $("copiar").textContent = "Copiar resumo"; }, 2000);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") avisarPagina({ apto: "recolher" }); });
$("proc").textContent = processo;
analisar(false);
