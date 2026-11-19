// APTO - resumo para o assistido aberto para imprimir: o painel guarda o PDF na sessão do navegador e abre esta página; ela o
// mostra no visualizador de PDF do navegador (que tem imprimir e baixar) e já chama a impressão. O PDF sai da sessão ao abrir.
"use strict";
(async () => {
  const id = location.hash.slice(1);
  const ch = "resumoImprimir:" + id;
  const g = (await chrome.storage.session.get(ch))[ch];
  await chrome.storage.session.remove(ch);
  const quadro = document.getElementById("pdf");
  if (!g || !g.b64) {
    quadro.remove();
    document.body.insertAdjacentHTML("beforeend", '<p class="msg">O resumo não está mais disponível. Gere de novo pelo painel do APTO no SEEU.</p>');
    return;
  }
  document.title = "Resumo - " + (g.nome || "assistido");
  const bin = atob(g.b64), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  quadro.addEventListener("load", () => {
    // o visualizador precisa de um instante para montar a página antes de imprimir
    setTimeout(() => {
      try { quadro.contentWindow.focus(); quadro.contentWindow.print(); document.body.dataset.impressao = "pedida"; }
      catch (e) { document.body.dataset.impressao = "falhou"; }   // segue aberto: o botão de imprimir do visualizador resolve
    }, 600);
  }, { once: true });
  quadro.src = url;
})();
