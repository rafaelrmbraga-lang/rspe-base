// APTO - painel no SEEU: página da extensão dentro da aba do processo (moldura). Sem resultado guardado, pede à página do
// SEEU (que lê as abas em segundo plano) o HTML das abas e entrega ao motor; mostra o resultado e avisa a página (recolher e
// contagem da lingueta). Nada aqui fala com o SEEU diretamente.
"use strict";
const C = self.APTO_PAINEL_CORE;
const processo = decodeURIComponent((location.hash.match(/p=([^&]+)/) || [])[1] || "");
const $ = (id) => document.getElementById(id);
const SEEU = "https://seeu.pje.jus.br";
let atual = null, esperandoAbas = null;

function avisarPagina(d) {
  try { parent.postMessage(d, SEEU); } catch (e) { /* segue */ }
}

function pintar(res) {
  atual = res;
  $("corpo").innerHTML = C.html(res);
  $("corpo").setAttribute("aria-busy", res && res.estado === "carregando" ? "true" : "false");
  const p = (res && res.painel) || {};
  if (p.nome) $("nome").textContent = p.nome;
  const ok = res && res.estado === "ok";
  const c = ok ? p.contagem : { verde: 0, amarelo: 0 };
  $("copiar").disabled = !ok;
  $("lg-v").innerHTML = ok ? C.ICO.verde + " " + c.verde + " confere" : "";
  $("lg-a").innerHTML = ok ? C.ICO.amarelo + " " + c.amarelo + " conferir" : "";
  $("lg-v").hidden = $("lg-a").hidden = !ok;
  avisarPagina({ apto: "contagem", c });
}

window.addEventListener("message", (ev) => {
  if (ev.origin !== SEEU || ev.source !== parent) return;
  const d = ev.data || {};
  if (d.apto === "progresso" && atual && atual.estado === "carregando") pintar(Object.assign({}, atual, { etapa: d.etapa }));
  if (d.apto === "abas" && esperandoAbas) { esperandoAbas(d); esperandoAbas = null; }
});

function pedirAbas() {
  return new Promise((ok) => { esperandoAbas = ok; avisarPagina({ apto: "lerAbas" }); });
}

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
    pintar({ estado: "carregando", primeira, etapa: "Lendo as abas do processo" });
    chrome.runtime.sendMessage({ tipo: "painelPreparar" }).catch(() => null);   // o motor carrega enquanto as abas chegam
    const d = await pedirAbas();
    if (!d.abas) return pintar({ estado: "sem_dados", motivo: d.erro ? "Não foi possível ler as abas: " + d.erro : "" });
    pintar(Object.assign({}, atual, { etapa: "Calculando com as regras do APTO" }));
    let res;
    try { res = await chrome.runtime.sendMessage({ tipo: "painelAnalisar", processo, abas: d.abas }); } catch (e) { res = null; }
    res = res || { estado: "erro", motivo: "a extensão não respondeu: recarregue a página do SEEU" };
    if (res.estado === "ok") await chrome.storage.session.set({ painelMotorPronto: true });
    pintar(res);
  } finally {
    b.removeAttribute("aria-busy");
    b.disabled = false;
  }
}

$("atualizar").addEventListener("click", () => analisar(true));
$("recolher").addEventListener("click", () => avisarPagina({ apto: "recolher" }));
$("copiar").addEventListener("click", async () => {
  if (!atual) return;
  try { await navigator.clipboard.writeText(C.resumo(atual)); $("copiar").textContent = "Copiado"; } catch (e) { $("copiar").textContent = "Não copiou"; }
  setTimeout(() => { $("copiar").textContent = "Copiar resumo"; }, 2000);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") avisarPagina({ apto: "recolher" }); });
$("proc").textContent = processo;
analisar(false);
