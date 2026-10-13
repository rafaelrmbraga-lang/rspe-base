"use strict";
const $ = (id) => document.getElementById(id);
const enviar = (msg) => chrome.runtime.sendMessage(msg);
let cfg = null;

function hora(t) {
  const d = new Date(t);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function estado(txt, erro) {
  const e = $("estado");
  e.textContent = txt;
  e.className = "estado " + (erro ? "erro" : "ok");
}

async function carregar() {
  const st = await enviar({ tipo: "estado" });
  cfg = st.cfg;
  $("ativo").checked = !!cfg.ativo;
  $("ativoTxt").textContent = cfg.ativo ? "ligada" : "desligada";
  $("raiz").value = cfg.raiz;
  $("aviso").checked = !!cfg.avisoNaPagina;
  $("dlRaiz").textContent = "Downloads\\" + cfg.raiz;
  const sel = $("base");
  sel.textContent = "";
  const sem = new Option("(sem subpasta: direto em Downloads\\" + cfg.raiz + ")", "");
  sel.add(sem);
  for (const b of cfg.bases) sel.add(new Option(b, b));
  sel.value = cfg.base || "";
  $("destino").textContent = "Salva em: Downloads\\" + cfg.raiz + (cfg.base ? "\\" + cfg.base : "") + "\\<nº do processo>_<data>.pdf" +
    (cfg.base ? "" : " - sem subpasta, a pasta vigiada do APTO ignora o arquivo; escolha uma base.");
  $("hoje").textContent = st.hoje ? `(${st.hoje} hoje)` : "";
  const ul = $("log");
  ul.textContent = "";
  if (!st.log.length) {
    const li = document.createElement("li");
    li.innerHTML = '<span class="m">Nenhum download ainda.</span>';
    ul.appendChild(li);
  }
  for (const x of st.log) {
    const li = document.createElement("li");
    const q = document.createElement("span"); q.className = "q"; q.textContent = hora(x.quando);
    const t = document.createElement("span");
    t.className = x.status === "ok" ? "" : "e";
    t.textContent = (x.processo || "processo ?") + (x.base ? " · " + x.base : "") + (x.status === "ok" ? (x.manual ? " · pelo botão do SEEU" : "") : " · " + (x.msg || "erro"));
    li.append(q, t);
    ul.appendChild(li);
  }
  const p = $("pausa");
  if (st.pausadoAte > Date.now()) {
    p.innerHTML = "";
    const b = document.createElement("button");
    b.textContent = "Pausada após falhas · retomar";
    b.onclick = async () => { await enviar({ tipo: "retomar" }); carregar(); };
    p.appendChild(b);
  } else p.textContent = "";
}

async function salvar(parcial) {
  cfg = await enviar({ tipo: "salvarCfg", cfg: Object.assign({}, cfg, parcial) });
  await carregar();
}

$("ativo").onchange = (e) => salvar({ ativo: e.target.checked });
$("aviso").onchange = (e) => salvar({ avisoNaPagina: e.target.checked });
$("base").onchange = (e) => salvar({ base: e.target.value });
$("raiz").onchange = (e) => salvar({ raiz: e.target.value });
$("add").onclick = () => {
  const n = $("nova").value.trim();
  if (!n) return;
  $("nova").value = "";
  salvar({ bases: cfg.bases.concat([n]), base: n });
};
$("nova").onkeydown = (e) => { if (e.key === "Enter") $("add").click(); };
$("rem").onclick = () => {
  const b = $("base").value;
  if (!b) return;
  salvar({ bases: cfg.bases.filter((x) => x !== b), base: "" });
};
$("limpar").onclick = async () => { await enviar({ tipo: "limparHistorico" }); carregar(); };

$("agora").onclick = async () => {
  const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!aba || !/^https:\/\/seeu\.pje\.jus\.br\//.test(aba.url || "")) return estado("Abra um processo no SEEU nesta aba.", true);
  if (!cfg.ativo) return estado("A extensão está desligada.", true);
  // só a moldura que tem o link do RSPE responde
  let r = null;
  try {
    r = await chrome.tabs.sendMessage(aba.id, { tipo: "procurar", forcar: true });
  } catch (e) {
    r = null;
  }
  if (!r || !r.achou) return estado("O link do RSPE não foi encontrado nesta página (se a extensão acabou de ser instalada, recarregue a página). " +
    "Clique em \"Situação Carcerária\" no SEEU: a extensão salva o RSPE na pasta da base.", true);
  if (r.ok) estado("Baixando: Downloads\\" + r.arquivo.replace(/\//g, "\\"));
  else estado(r.motivo || "Não foi possível baixar.", true);
  setTimeout(carregar, 2500);
};

// ---- lote ----
function numerosDe(txt) {
  return [...new Set((String(txt || "").match(/\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}/g) || []).map((x) => x.replace(/\D/g, "")))];
}
async function desenharLote() {
  const L = await enviar({ tipo: "loteEstado" });
  const est = $("loteEst"), ul = $("loteLista");
  ul.textContent = "";
  if (!L) { est.className = "estado"; return; }
  const n = (s) => L.itens.filter((x) => x.status === s).length;
  const feitos = L.itens.length - n("fila") - n("rodando");
  est.className = "estado " + (n("erro") ? "erro" : "ok");
  est.textContent = (L.rodando ? "Em andamento: " : (L.parou ? "Parado: " : "Concluído: ")) + `${feitos} de ${L.itens.length} · salvos ${n("ok")} · já baixados hoje ${n("repetido")} · erros ${n("erro")} · base ${L.base}`;
  for (const x of L.itens.filter((x) => x.status !== "fila").slice(-60).reverse()) {
    const li = document.createElement("li");
    const t = document.createElement("span");
    t.className = x.status === "erro" ? "e" : x.status === "ok" ? "" : "m";
    t.textContent = x.n + " · " + ({ ok: "salvo", repetido: "já baixado hoje", rodando: "baixando…", erro: x.msg || "erro" })[x.status];
    li.appendChild(t);
    ul.appendChild(li);
  }
  if (L.rodando) $("loteBox").open = true;
}
$("loteArq").onchange = async (e) => {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  const txt = await f.text();
  const nums = numerosDe(txt);
  // com nºs de processo: lista de processos (SEEU); sem nºs: lista de nomes (SIAPEN), como veio
  $("loteTxt").value = nums.length ? nums.map((x) => x.replace(/^(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})$/, "$1-$2.$3.$4.$5.$6")).join("\n") : txt.replace(/,/g, ";");
};
$("loteIni").onclick = async () => {
  const texto = $("loteTxt").value;
  const nums = numerosDe(texto);
  const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
  const siapen = aba && /^https:\/\/app\.siapen\.ms\.gov\.br/.test(aba.url || "");
  if (!siapen && !nums.length) { $("loteEst").className = "estado erro"; $("loteEst").textContent = "Nenhum nº de processo válido na lista."; return; }
  const r = await enviar({ tipo: "loteIniciar", numeros: nums, texto });
  if (!r.ok) { $("loteEst").className = "estado erro"; $("loteEst").textContent = r.motivo; return; }
  desenharLote();
};
$("lotePar").onclick = async () => { await enviar({ tipo: "loteParar" }); setTimeout(desenharLote, 800); };
setInterval(desenharLote, 2000);

carregar();
desenharLote();
