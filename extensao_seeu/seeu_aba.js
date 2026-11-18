// APTO - SEEU: na aba do SEEU já logada, atende o botão "Ler a Mesa" do APTO. Pergunta ao APTO a cada 3 s se há pedido; quando
// há, pede ao service worker que abra a Triagem da Mesa do Defensor (a mesma página da extensão, em segundo plano, sem iniciar
// prazo), que lê a Mesa e os processos com as abas e filtros guardados e entrega ao APTO. Nada é clicado ou enviado ao SEEU.
(function () {
  "use strict";
  if (window.__aptoSeeuAba || window !== window.top) return;
  window.__aptoSeeuAba = true;
  const enviar = (m) => chrome.runtime.sendMessage(m).catch(() => null);
  async function perguntar() {
    const r = await enviar({ tipo: "seeuComando" });
    const c = r && r.cmd;
    if (!c) return;
    let resp;
    if (c.tipo === "lerMesa") resp = (await enviar({ tipo: "seeuAbrirTriagem", opcoes: c.opcoes || {} })) || { erro: "a extensão não abriu a triagem" };
    else if (c.tipo === "pararMesa") resp = (await enviar({ tipo: "seeuPararTriagem" })) || { ok: true };
    else resp = { erro: "pedido desconhecido" };
    await enviar({ tipo: "seeuResposta", id: c.id, resposta: resp });
  }
  setInterval(perguntar, 3000);
  perguntar();
})();
