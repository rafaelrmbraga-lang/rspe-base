// APTO - SEI da Defensoria (sei.defensoria.ms.def.br): na aba do SEI, já logada pela pessoa, guarda o endereço do Controle de
// Processos (cada link do SEI é assinado na sessão; a leitura do SEI começa dele). Só lê o endereço da página; nada é clicado,
// digitado ou enviado ao SEI. O endereço fica na sessão do navegador (some ao fechar o navegador).
(function () {
  "use strict";
  if (window.__aptoSeiAba || window !== window.top) return;
  window.__aptoSeiAba = true;
  const u = new URL(location.href);
  if (u.pathname !== "/sei/controlador.php" || u.searchParams.get("acao") !== "procedimento_controlar" || !u.searchParams.get("infra_hash")) return;
  if (!document.getElementById("frmProcedimentoControlar")) return;
  chrome.runtime.sendMessage({ tipo: "seiEntrada", url: location.href }).catch(() => {});
})();
