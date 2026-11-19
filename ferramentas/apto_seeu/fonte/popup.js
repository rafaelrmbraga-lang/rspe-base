"use strict";
const $ = (id) => document.getElementById(id);
let cfg = {};
async function carregar() {
  cfg = (await chrome.runtime.sendMessage({ tipo: "cfg" })) || {};
  $("painel").checked = cfg.painel !== false;
  $("docMonitor2").checked = !!cfg.docMonitor2;
}
async function salvar(parcial) {
  cfg = await chrome.runtime.sendMessage({ tipo: "salvarCfg", cfg: Object.assign({}, cfg, parcial) });
  await carregar();
}
$("painel").onchange = (e) => salvar({ painel: e.target.checked });
$("docMonitor2").onchange = (e) => salvar({ docMonitor2: e.target.checked });
$("versao").textContent = "Versão " + chrome.runtime.getManifest().version + " · os dados ficam neste computador";
carregar();
