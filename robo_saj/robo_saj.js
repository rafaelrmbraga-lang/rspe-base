// Robô do SAJ Defensorias (painel-saj.ms.def.br) - versão 0.3: acerta a Movimentação interna, escolhe o certificado
// e peticiona as tarefas da fila "Para peticionar > Intimação". As peças já estão prontas: o texto não é conferido.
// Liminar e Redistribuir ficam sempre como estão (o robô não toca nessas caixas).
// Roda como favorito (bookmarklet) na aba do Painel de Tarefas. Três modos:
//   Conferir  - abre, lê as Propriedades e fecha; não altera nada
//   Preparar  - acerta Movimentação e certificado e fecha SEM peticionar (teste sem assinar)
//   Peticionar- faz o mesmo, clica UMA vez em Peticionar, espera a caixa verde e a fecha
// Cada clique passa por clicar(el, tipo), que recusa qualquer elemento fora da lista de tipos.
(function () {
  "use strict";

  const VERSAO = "0.3.1";
  const HOST = "painel-saj.ms.def.br";
  const CHAVE_SESSAO = "roboSAJ_resultados";
  const ESPERA_ENVIO_MS = 180000; // tempo para digitar o PIN e o SAJ responder

  if (window.__roboSAJ && window.__roboSAJ.mostrar && !window.__roboSAJ_teste) { window.__roboSAJ.mostrar(); return; }

  // ------------------------------------------------------------ utilidades
  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
  const semAcento = (s) => String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "");
  const norm = (s) => semAcento(s).toLowerCase().replace(/\s+/g, " ").trim();
  const chave = (s) => norm(s).replace(/[^a-z0-9]+/g, " ").trim();
  const soDig = (s) => String(s || "").replace(/\D/g, "");
  const texto = (el) => (el ? (el.innerText != null ? el.innerText : el.textContent) || "" : "").replace(/ /g, " ").trim();
  const q = (sel, raiz) => (raiz || document).querySelector(sel);
  const qa = (sel, raiz) => Array.from((raiz || document).querySelectorAll(sel));
  const visivel = (el) => !!el && el.isConnected && (el.offsetParent !== null || getComputedStyle(el).position === "fixed");

  async function aguardar(fn, ms, passo) {
    const fim = Date.now() + (ms || 10000);
    for (;;) {
      let v = null;
      try { v = fn(); } catch (e) { v = null; }
      if (v) return v;
      if (Date.now() > fim) return null;
      await esperar(passo || 250);
    }
  }

  // ------------------------------------------------------------ regras
  const PERFIS = {
    A: { /* nº começa com 0 (SAJ) */
      tarja: "SAJ",
      movCod: "920198", movLabel: "920198 - Manifestação", movPai: "920281",
      evento: "Manifestação do Autor", tipoDoc: "9934 - Manifestação da Defensoria",
    },
    B: { /* nº começa com 5 (EPROC) */
      tarja: "EPROC",
      movCod: "1000150", movLabel: "1000150 - Petição Intermediária TJ", movPai: "1000000",
      evento: "PETIÇÃO", tipoDoc: "13 - PETIÇÃO",
    },
  };
  const SIGILO = "0 - Público";
  const DEFENSOR = "Cahuê Duarte e Urdiales";
  const CERTIFICADO = "CAHUE DUARTE E URDIALES";
  const igual = (a, b) => chave(a) === chave(b);
  const comeca = (a, b) => chave(a).startsWith(chave(b));

  const CATEGORIAS = [
    [/ADV(OGADO)? PARTICULAR/, "Adv. particular"],
    [/^CIENCIA\b/, "Ciência"],
    [/^IMPUG/, "Impugnação"],
    [/^MANIF/, "Manifestação"],
    [/^(CUMPR|BLOQ)|SEQUESTRO|BLOQUEIO/, "Cumprimento/bloqueio"],
    [/^CONTRARR/, "Contrarrazões"],
    [/^(RECURSO|RI\b)/, "Recurso"],
  ];
  function categoria(titulo) {
    const t = semAcento(titulo).toUpperCase().replace(/\s+/g, " ").trim();
    for (const [re, c] of CATEGORIAS) if (re.test(t)) return c;
    return "Outros";
  }

  // ------------------------------------------------------------ cliques permitidos
  const naCaixaVerde = (el) => !!el.closest('.MuiSnackbar-root, [class*="notistack"], [class*="Snackbar"]');
  const PERMITIDOS = {
    continuar: (el) => el.getAttribute("data-testid") === "btn-atividade-generic",
    propriedades: (el) => el.getAttribute("data-testid") === "action-menu-propriedades",
    fecharEditor: (el) => el.getAttribute("data-testid") === "action-emissao-expediente-close-btn",
    peticionar: (el) => el.getAttribute("data-testid") === "action-emissao-expediente-peticionar-btn" && estado.modo === "peticionar" && estado.autorizado,
    fecharAviso: (el) => naCaixaVerde(el) && !el.closest('[data-testid="editor-container"]'),
    abrirLista: (el) => /(movement-type-select|certificado)__control/.test(String(el.className)),
    opcao: (el) => !!el.closest('[class*="movement-type-select__menu"], [class*="certificado__menu"]'),
  };
  function clicar(el, tipo) {
    if (!el || !PERMITIDOS[tipo] || !PERMITIDOS[tipo](el)) throw new Error(`clique recusado pelo robô (${tipo})`);
    if (el.disabled || el.getAttribute("aria-disabled") === "true") throw new Error("botão desabilitado (" + tipo + ")");
    estado.acoes++;
    if (tipo === "abrirLista") { el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, button: 0 })); return; }
    el.click();
  }

  // ------------------------------------------------------------ painel do SAJ
  function contagens() {
    const val = (testid) => { const c = q(`[data-testid="${testid}"] [data-testid="count-value"]`); return c ? texto(c) : "?"; };
    const porRotulo = (rot) => {
      const p = qa('[data-testid="collapse-option-header"] p[aria-label]').find((x) => x.getAttribute("aria-label") === rot);
      const v = p && p.parentElement && q('[data-testid="count-value"]', p.parentElement);
      return v ? texto(v) : "?";
    };
    return { intimacao: val("count-content-27_Intimacao"), emProcessamento: porRotulo("Em processamento"), falhas: val("count-content-falhas") };
  }

  // A fila selecionada é o único subitem do menu com estilo diferente dos demais.
  function filaSelecionada() {
    const itens = qa('li[data-testid="option-container-datatestid"]');
    if (!itens.length) return { ok: false, motivo: "não achei o menu lateral de tarefas" };
    const freq = {};
    for (const li of itens) freq[li.className] = (freq[li.className] || 0) + 1;
    const diferentes = itens.filter((li) => freq[li.className] === 1);
    const alvo = q('[data-testid="count-content-27_Intimacao"]');
    const liAlvo = alvo && alvo.closest('li[data-testid="option-container-datatestid"]');
    if (!liAlvo) return { ok: false, motivo: 'não achei "Para peticionar › Intimação" no menu (expanda "Para peticionar")' };
    if (diferentes.length === 1 && diferentes[0] === liAlvo) return { ok: true };
    const nome = diferentes.length === 1 ? texto(q("p", diferentes[0])) : "nenhum ou mais de um";
    return { ok: false, motivo: `o item destacado no menu não é "Para peticionar › Intimação" (destacado: ${nome})` };
  }

  function lerCards() {
    return qa('[data-testid="container-card"]').map((cont) => ({
      num: texto(q('[data-testid="num-processo-label"]', cont)),
      tipo: texto(q('[data-testid="tipo-documento"]', cont)),
      tarjas: qa('[data-testid="stamp-group"] [role="listitem"]', cont).map((x) => x.getAttribute("aria-label") || texto(x)),
      textoCard: texto(cont),
    }));
  }
  const contDoCard = (num) => qa('[data-testid="container-card"]').find((c) => texto(q('[data-testid="num-processo-label"]', c)) === num);

  // ------------------------------------------------------------ editor e propriedades
  const editorAberto = () => q('[data-testid="editor-container"]');
  function dialogoEstranho() {
    return qa('[role="dialog"], [role="alertdialog"]').find((d) => d.getAttribute("data-testid") !== "editor-container" && visivel(d) && !d.closest("#robo-saj-host")) || null;
  }
  const raizProps = () => q('[data-testid="propriedades-root"]');
  const valorSelect = (raiz) => texto(raiz && q('[class*="__single-value"]', raiz));

  function lerPropriedades() {
    const r = raizProps();
    if (!r) return null;
    const mov = q('[data-testid="select-tree-movimentacao"]', r);
    const def = q('input[aria-label="Defensor responsável"]', r);
    const cb = (n) => { const i = q(`input[name="${n}"]`, r); return i ? i.checked : null; };
    return {
      movLabel: texto(mov && q('[data-testid="option-label"]', mov)),
      movPai: texto(mov && q('[data-testid="option-parent"]', mov)),
      evento: valorSelect(q('[data-testid="select-petition"]', r)),
      tipoDoc: valorSelect(q('[data-testid="select-tipo-documento"]', r)),
      sigilo: valorSelect(q('[data-testid="select-sigilo-documento"]', r)),
      liminar: cb("urgente"),
      redistribuir: cb("redistribuir"),
      defensor: valorSelect(def && def.closest('[class*="__control"]')),
      certificado: valorSelect(q('[data-testid="propriedades-certificado"]', r)),
    };
  }
  const movCerta = (p, P) => igual(p.movLabel, P.movLabel) && comeca(p.movPai, P.movPai);

  // --- escolher uma opção numa lista do SAJ (react-select): abre, digita o código, clica na única opção que casar.
  // Se a lista não abrir pelo clique, usa a própria função de escolha do componente (mesmo efeito do clique).
  function digitar(input, valor) {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(input, valor);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function fecharLista(input) {
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
  }
  function propsDoSelect(el) {
    const k = Object.keys(el).find((x) => x.startsWith("__reactFiber$") || x.startsWith("__reactInternalInstance$"));
    for (let f = k ? el[k] : null, n = 0; f && n < 40; f = f.return, n++) {
      const p = f.memoizedProps;
      if (p && typeof p.onChange === "function" && Array.isArray(p.options)) return p;
    }
    return null;
  }
  function folhas(opcoes, saida) {
    for (const o of opcoes || []) {
      if (!o || typeof o !== "object") continue;
      const filhos = [o.options, o.children, o.filhos, o.items].find(Array.isArray);
      if (filhos && filhos.length) folhas(filhos, saida); else saida.push(o);
    }
    return saida;
  }
  const textoOpcao = (o) => Object.values(o).filter((v) => typeof v === "string" || typeof v === "number").join(" ");

  async function escolherNaLista(prefixo, raiz, codigo, rotulo) {
    const input = q(`input.${prefixo}__input`, raiz) || q(`[class*="${prefixo}__control"] input`, raiz);
    const controle = q(`[class*="${prefixo}__control"]`, raiz);
    if (!input || !controle) return "não achei a lista";
    const casa = (t) => { const c = chave(t); return c.includes(chave(codigo)) && c.includes(chave(rotulo)); };
    clicar(controle, "abrirLista");
    await esperar(300);
    digitar(input, codigo);
    const menuSel = `[class*="${prefixo}__menu"]`;
    const ops = await aguardar(() => {
      const m = q(menuSel);
      if (!m) return null;
      const o = qa(`[class*="${prefixo}__option"]`, m);
      return o.length ? o : null;
    }, 5000);
    if (ops) {
      // só opções-folha (a de dentro do grupo), que tenham o código e o nome
      const cand = ops.filter((o) => casa(texto(o)) && !q(`[class*="${prefixo}__option"]`, o));
      if (cand.length === 1) { clicar(cand[0], "opcao"); await esperar(500); return ""; }
      fecharLista(input);
      return cand.length ? `${cand.length} opções parecidas com ${codigo}` : `a opção ${codigo} não aparece na lista`;
    }
    fecharLista(input);
    const p = propsDoSelect(input) || propsDoSelect(controle);
    if (!p) return "a lista não abriu";
    const cand = folhas(p.options, []).filter((o) => casa(textoOpcao(o)));
    if (cand.length !== 1) return cand.length ? `${cand.length} opções parecidas com ${codigo}` : `a opção ${codigo} não existe na lista`;
    p.onChange(cand[0], { action: "select-option", option: cand[0], name: p.name });
    await esperar(500);
    return "";
  }

  // ------------------------------------------------------------ caixa verde (aviso do SAJ)
  function avisos() {
    return qa('.MuiSnackbar-root, [role="alert"]')
      .filter((el) => visivel(el) && !el.closest('[data-testid="editor-container"]') && !el.closest("#robo-saj-host"))
      .map((el) => ({ el: el.closest(".MuiSnackbar-root") || el, t: norm(texto(el)) }))
      .filter((a) => a.t);
  }
  const ehSucesso = (t) => /peticao/.test(t) && /enviad|sucesso|protocolad/.test(t);
  const ehErro = (t) => /erro|falha|nao foi possivel|invalid|recusad|expirad/.test(t);
  async function fecharAvisos() {
    for (const a of avisos()) {
      const b = q('button[aria-label="Close"], button[aria-label="Fechar"], button[title="Close"], button[title="Fechar"]', a.el) || (qa("button", a.el).length === 1 ? q("button", a.el) : null);
      if (b) { clicar(b, "fecharAviso"); await esperar(400); }
    }
    return avisos().length === 0;
  }

  // ------------------------------------------------------------ rodada
  const estado = { rodando: false, parar: false, resultados: [], acoes: 0, pausa: null, modo: "conferir", autorizado: false };
  function salvar() { try { sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(estado.resultados)); } catch (e) { /* sem armazenamento */ } }
  function carregar() { try { return JSON.parse(sessionStorage.getItem(CHAVE_SESSAO) || "[]"); } catch (e) { return []; } }

  function pausar(msg) {
    ui.aviso(msg + ' Resolva na tela do SAJ e clique em "Continuar a rodada" (ou "Parar").', true);
    return new Promise((res) => { estado.pausa = res; ui.botaoRetomar(true); });
  }

  async function fecharEditor() {
    const b = q('[data-testid="action-emissao-expediente-close-btn"]');
    if (!b) return !editorAberto();
    clicar(b, "fecharEditor");
    if (await aguardar(() => !editorAberto(), 8000)) return true;
    const d = dialogoEstranho();
    await pausar(`Ao fechar o editor apareceu: "${d ? texto(d).slice(0, 300) : "o editor não fechou"}". NÃO peticione.`);
    return !editorAberto();
  }

  // r.resultado começa com: CONFERIDA, PREPARADA, PETICIONADO, PULADO ou PARADO
  async function tratar(card) {
    const r = { num: card.num, perfil: "", categoria: "", titulo: "", resultado: "", feito: [] };
    const cont = contDoCard(card.num);
    if (!cont) { r.resultado = "PULADO – card sumiu da fila"; return r; }
    if (norm(card.tipo) !== "intimacao") { r.resultado = `PULADO – card não é Intimação (${card.tipo})`; return r; }
    const dig = soDig(card.num);
    r.perfil = dig.length === 20 && dig[0] === "5" ? "B" : dig.length === 20 && dig[0] === "0" ? "A" : "";
    if (!r.perfil) { r.resultado = 'PULADO – nº não começa com "0" nem com "5"'; return r; }
    const P = PERFIS[r.perfil];
    if (!card.tarjas.some((t) => igual(t, P.tarja))) { r.resultado = `PULADO – nº de perfil ${r.perfil}, mas o card não tem a tarja ${P.tarja}`; return r; }
    if (/sigil|segredo de justica|reu preso/.test(norm(card.textoCard))) { r.resultado = "PULADO – card indica sigilo/segredo/réu preso"; return r; }
    const btn = q('[data-testid="btn-atividade-generic"]', cont);
    if (!btn || norm(texto(btn)) !== "continuar") { r.resultado = "PULADO – card sem o botão Continuar"; return r; }

    clicar(btn, "continuar");
    const aberto = await aguardar(() => editorAberto() || dialogoEstranho(), 20000);
    if (!aberto || !editorAberto()) {
      const d = dialogoEstranho();
      r.resultado = "PARADO – " + (d ? `apareceu: "${texto(d).slice(0, 200)}"` : "o editor não abriu em 20 s");
      return r;
    }
    const sel = q('[data-testid^="card-"][aria-selected="true"]');
    if (!sel || sel.getAttribute("data-testid") !== "card-" + card.num) {
      r.resultado = "PULADO – o editor abriu para outro card (" + (sel ? sel.getAttribute("data-testid").slice(5) : "?") + ")";
      await fecharEditor(); return r;
    }
    // espera o documento carregar (o texto parar de mudar)
    let ant = "";
    await aguardar(() => {
      const ifr = q('[data-testid="editor-container"] iframe.tox-edit-area__iframe');
      const b = ifr && ifr.contentDocument && ifr.contentDocument.body;
      const t = b ? texto(b) : "";
      const ok = t.length > 50 && t === ant; ant = t; return ok;
    }, 20000, 700);
    if (!raizProps()) {
      const b = q('[data-testid="action-menu-propriedades"]');
      if (b) clicar(b, "propriedades");
      await aguardar(raizProps, 8000);
    }
    await esperar(400);
    r.titulo = texto(q('[data-testid="editor-container"] p[role="banner"]'));
    r.categoria = categoria(r.titulo);
    const sair = async (res) => { r.resultado = res; await fecharEditor(); return r; };

    let p = lerPropriedades();
    if (!p) return sair("PULADO – não consegui ler a aba Propriedades");
    if (!igual(p.sigilo, SIGILO)) return sair(`PULADO – Sigilo veio "${p.sigilo || "vazio"}" (não altero sigilo)`);

    if (estado.modo === "conferir") {
      const faria = [];
      if (!movCerta(p, P)) faria.push(`Movimentação → ${P.movLabel} (veio ${p.movLabel || "vazia"})`);
      if (!igual(p.certificado, CERTIFICADO)) faria.push("escolher o certificado");
      if (!igual(p.evento, P.evento)) faria.push(`ATENÇÃO: Evento veio "${p.evento || "vazio"}"`);
      if (!comeca(p.tipoDoc, P.tipoDoc)) faria.push(`ATENÇÃO: Tipo de documento veio "${p.tipoDoc || "vazio"}"`);
      r.feito = faria;
      return sair("CONFERIDA");
    }

    // 1) Movimentação interna
    if (!movCerta(p, P)) {
      const erro = await escolherNaLista("movement-type-select", q('[data-testid="select-tree-movimentacao"]', raizProps()).parentElement, P.movCod, P.movLabel.replace(/^\d+\s*-\s*/, ""));
      p = lerPropriedades();
      if (erro || !movCerta(p, P)) return sair(`PULADO – não consegui pôr a Movimentação ${P.movLabel}: ${erro || "veio " + p.movLabel}`);
      if (dialogoEstranho()) { r.resultado = `PARADO – ao trocar a Movimentação apareceu: "${texto(dialogoEstranho()).slice(0, 200)}"`; return r; }
      r.feito.push("Movimentação acertada");
      await esperar(800); // Evento e Tipo de documento podem mudar junto
      p = lerPropriedades();
    }
    // 2) campos que o robô não mexe: têm de estar certos
    p = lerPropriedades();
    if (!igual(p.evento, P.evento)) return sair(`PULADO – Evento veio "${p.evento || "vazio"}" (esperado ${P.evento})`);
    if (!comeca(p.tipoDoc, P.tipoDoc)) return sair(`PULADO – Tipo de documento veio "${p.tipoDoc || "vazio"}" (esperado ${P.tipoDoc})`);
    if (!igual(p.defensor, DEFENSOR)) return sair(`PULADO – Defensor veio "${p.defensor || "vazio"}"`);
    // 3) certificado
    if (!igual(p.certificado, CERTIFICADO)) {
      const erro = await escolherNaLista("certificado", q('[data-testid="propriedades-certificado"]', raizProps()).parentElement, CERTIFICADO, CERTIFICADO);
      p = lerPropriedades();
      if (erro || !igual(p.certificado, CERTIFICADO)) {
        r.resultado = `PARADO – certificado não escolhido: ${erro || "veio " + (p.certificado || "vazio")}. O assinador está aberto e o token conectado?`;
        await fecharEditor(); return r;
      }
      if (dialogoEstranho()) { r.resultado = `PARADO – ao escolher o certificado apareceu: "${texto(dialogoEstranho()).slice(0, 200)}"`; return r; }
      r.feito.push("certificado escolhido");
    }
    if (!movCerta(p, P)) return sair("PULADO – a Movimentação mudou depois de escolher o certificado");

    if (estado.modo === "preparar") return sair("PREPARADA (não peticionada)");

    // 4) Peticionar: uma vez só
    if (!(await fecharAvisos())) { r.resultado = "PARADO – há uma caixa de aviso do SAJ que não consegui fechar"; return r; }
    const pet = await aguardar(() => { const b = q('[data-testid="action-emissao-expediente-peticionar-btn"]'); return b && !b.disabled && b.getAttribute("aria-disabled") !== "true" ? b : null; }, 8000);
    if (!pet) return sair("PULADO – o botão Peticionar continuou desativado");
    estado.peticionados.add(card.num);
    clicar(pet, "peticionar");
    r.feito.push("Peticionar clicado");
    ui.aviso(`Peticionando ${card.num}. Se o assinador pedir o PIN, digite. Não clique em Peticionar de novo.`);
    const fim = await aguardar(() => {
      for (const a of avisos()) { if (ehErro(a.t)) return { erro: a.t }; if (ehSucesso(a.t)) return { ok: a.t }; }
      const d = dialogoEstranho();
      if (d && !/certificado|pin|senha|assinad/.test(norm(texto(d)))) return { erro: "apareceu: " + texto(d).slice(0, 200) };
      return null;
    }, ESPERA_ENVIO_MS, 500);
    if (!fim) { r.resultado = "PARADO – sem caixa de sucesso nem de erro em 3 min depois de Peticionar. Confira em Em processamento/Falhas"; return r; }
    if (fim.erro) { r.resultado = "PARADO – o SAJ avisou: " + fim.erro; return r; }
    await fecharAvisos();
    if (!(await aguardar(() => !editorAberto(), 15000))) { r.resultado = "PARADO – a caixa de sucesso apareceu, mas o editor não fechou"; return r; }
    r.resultado = "PETICIONADO";
    return r;
  }

  async function rodar(limite) {
    if (estado.rodando) return;
    if (location.host !== HOST && !window.__roboSAJ_teste) { ui.aviso(`Abra o Painel de Tarefas em ${HOST} e clique no favorito lá.`, true); return; }
    if (estado.modo === "peticionar" && !estado.autorizado) { ui.aviso('Para peticionar, marque "Autorizo peticionar".', true); return; }
    if (editorAberto()) { ui.aviso("Feche o editor que está aberto (sem peticionar) e clique em Iniciar de novo.", true); return; }
    const f = filaSelecionada();
    if (!f.ok) { ui.aviso("Não comecei: " + f.motivo + ".", true); return; }
    estado.rodando = true; estado.parar = false; estado.inicio = contagens();
    ui.estadoBotoes();
    let falhasSeguidas = 0, feitos = 0;
    const vistos = new Set(estado.resultados.filter((x) => x.modo === estado.modo || x.resultado.startsWith("PETICIONADO")).map((x) => x.num));
    try {
      while (feitos < limite && !estado.parar) {
        const fila = filaSelecionada();
        if (!fila.ok) { ui.aviso("Parei: " + fila.motivo + ".", true); break; }
        const cards = lerCards();
        const volta = cards.find((c) => estado.peticionados.has(c.num));
        if (volta && estado.modo === "peticionar") {
          // a tarefa peticionada pode levar uns segundos para sair da fila
          if (await aguardar(() => !lerCards().some((c) => c.num === volta.num), 20000)) continue;
          ui.aviso(`Parei: ${volta.num} foi peticionado e continua na fila. Confira antes de seguir.`, true); break;
        }
        const card = cards.find((c) => !vistos.has(c.num));
        if (!card) break;
        vistos.add(card.num);
        ui.aviso(`${estado.modo === "conferir" ? "Conferindo" : estado.modo === "preparar" ? "Preparando" : "Peticionando"} ${card.num}...`);
        const falhasAntes = contagens().falhas;
        let r;
        try { r = await tratar(card); } catch (e) { r = { num: card.num, perfil: "", categoria: "", titulo: "", feito: [], resultado: "PARADO – erro do robô: " + e.message }; }
        r.modo = estado.modo;
        estado.resultados.push(r); salvar(); ui.tabela(); feitos++;
        if (r.resultado.startsWith("PARADO")) {
          falhasSeguidas++;
          if (estado.modo === "peticionar" || editorAberto() || dialogoEstranho() || falhasSeguidas >= 2) { ui.aviso("Parei em " + card.num + ": " + r.resultado.slice(9), true); break; }
        } else falhasSeguidas = 0;
        await esperar(1500);
        const falhasDepois = contagens().falhas;
        if (falhasAntes !== "?" && falhasDepois !== "?" && Number(falhasDepois) > Number(falhasAntes)) { ui.aviso(`Parei: "Falhas" subiu de ${falhasAntes} para ${falhasDepois}.`, true); break; }
      }
    } finally {
      estado.rodando = false; estado.fim = contagens(); ui.estadoBotoes();
      if (!ui.temAvisoFixo()) ui.aviso(estado.parar ? "Parado a seu pedido." : "Rodada concluída. Clique em \"Copiar relatório\".");
    }
  }

  function relatorioTexto() {
    const rs = estado.resultados;
    const linhas = ["| # | Processo | Perfil | Categoria | Modelo | Resultado | O que fez / faria |", "|---|---|---|---|---|---|---|"];
    rs.forEach((r, i) => linhas.push(`| ${i + 1} | ${r.num} | ${r.perfil} | ${r.categoria} | ${r.titulo} | ${r.resultado} | ${(r.feito || []).join("; ")} |`));
    const conta = (p) => rs.filter((r) => r.resultado.startsWith(p)).length;
    const porCat = {};
    rs.filter((r) => r.resultado.startsWith("PETICIONADO")).forEach((r) => (porCat[r.categoria] = (porCat[r.categoria] || 0) + 1));
    const cats = Object.keys(porCat);
    if (cats.length) {
      linhas.push("", "| Categoria | Qtde |", "|---|---|");
      cats.forEach((c) => linhas.push(`| ${c} | ${porCat[c]} |`));
      linhas.push(`| Total | ${conta("PETICIONADO")} |`);
    }
    linhas.push("", `${conta("PETICIONADO")} peticionadas, ${conta("PREPARADA")} preparadas, ${conta("CONFERIDA")} conferidas, ${conta("PULADO")} puladas, ${conta("PARADO")} paradas. Robô ${VERSAO}; ${estado.acoes} cliques.`);
    const fmt = (c) => (c ? `Intimação ${c.intimacao}, Em processamento ${c.emProcessamento}, Falhas ${c.falhas}` : "-");
    linhas.push(`Menu no início: ${fmt(estado.inicio)}. No fim: ${fmt(estado.fim)}.`);
    return linhas.join("\n");
  }

  // ------------------------------------------------------------ interface (shadow DOM, sem mexer no SAJ)
  const ui = (() => {
    let host, el = {}, fixo = false;
    function criar() {
      host = document.createElement("div");
      host.id = "robo-saj-host";
      host.style.cssText = "position:fixed;top:70px;right:16px;z-index:2147483647;";
      const raiz = host.attachShadow({ mode: "open" });
      const css = document.createElement("style");
      css.textContent = `
        .p{width:460px;max-height:80vh;display:flex;flex-direction:column;background:#fff;color:#1d2433;border:2px solid #03508D;border-radius:8px;
           box-shadow:0 6px 24px rgba(0,0,0,.25);font:13px/1.4 Segoe UI,Arial,sans-serif}
        .t{background:#03508D;color:#fff;padding:8px 10px;font-weight:600;display:flex;justify-content:space-between;align-items:center}
        .t button{background:none;border:0;color:#fff;font-size:16px;cursor:pointer}
        .c{padding:10px;overflow:auto}
        .f{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
        button.b{border:1px solid #03508D;background:#03508D;color:#fff;border-radius:4px;padding:5px 10px;cursor:pointer;font:inherit}
        button.s{background:#fff;color:#03508D}
        button:disabled{opacity:.45;cursor:default}
        input[type=number]{width:48px;padding:3px;font:inherit}
        select{font:inherit;padding:3px}
        .aut{color:#8a1c12;font-weight:600}
        .a{padding:6px 8px;border-radius:4px;background:#eef4fa;margin-bottom:8px;white-space:pre-wrap}
        .a.e{background:#fdecea;color:#8a1c12}
        table{border-collapse:collapse;width:100%;font-size:12px}
        td,th{border-bottom:1px solid #dde3ea;padding:4px;text-align:left;vertical-align:top}
        .ok{color:#1b6e2d;font-weight:600}.pu{color:#8a5a00}.pa{color:#8a1c12;font-weight:600}
        .n{font-size:11px;color:#5b6472;margin-top:6px}`;
      const p = document.createElement("div"); p.className = "p";
      const t = document.createElement("div"); t.className = "t";
      const tt = document.createElement("span"); tt.textContent = `Robô SAJ ${VERSAO}`;
      const x = document.createElement("button"); x.textContent = "×"; x.title = "Fechar o painel"; x.onclick = () => (host.style.display = "none");
      t.append(tt, x);
      const c = document.createElement("div"); c.className = "c";
      const mk = (tag, props) => Object.assign(document.createElement(tag), props || {});
      const bt = (txt, cls, fn) => { const b = mk("button", { className: "b " + (cls || ""), textContent: txt }); b.onclick = fn; return b; };

      const f1 = mk("div", { className: "f" });
      el.modo = mk("select");
      [["conferir", "Conferir (não altera nada)"], ["preparar", "Preparar (acerta campos, não peticiona)"], ["peticionar", "Peticionar"]].forEach(([v, r]) => el.modo.append(mk("option", { value: v, textContent: r })));
      el.modo.onchange = () => { estado.modo = el.modo.value; el.autLab.style.display = estado.modo === "peticionar" ? "" : "none"; if (estado.modo !== "peticionar") { el.aut.checked = false; estado.autorizado = false; } };
      el.limite = mk("input", { type: "number", min: "1", max: "30", value: "5" });
      const lab = mk("label", { textContent: " Tarefas: " }); lab.append(el.limite);
      f1.append(el.modo, lab);

      const f2 = mk("div", { className: "f" });
      el.aut = mk("input", { type: "checkbox" });
      el.aut.onchange = () => (estado.autorizado = el.aut.checked);
      el.autLab = mk("label", { className: "aut" }); el.autLab.append(el.aut, document.createTextNode(" Autorizo peticionar (é irreversível)"));
      el.autLab.style.display = "none";
      f2.append(el.autLab);

      const f3 = mk("div", { className: "f" });
      el.iniciar = bt("Iniciar", "", () => rodar(Math.max(1, Math.min(30, parseInt(el.limite.value, 10) || 5))));
      el.parar = bt("Parar", "s", () => { estado.parar = true; aviso("Vou parar depois da tarefa em andamento."); if (estado.pausa) { const r = estado.pausa; estado.pausa = null; botaoRetomar(false); r(); } });
      el.retomar = bt("Continuar a rodada", "", () => { const r = estado.pausa; estado.pausa = null; botaoRetomar(false); fixo = false; if (r) r(); });
      el.retomar.style.display = "none";
      el.copiar = bt("Copiar relatório", "s", async () => { try { await navigator.clipboard.writeText(relatorioTexto()); aviso("Relatório copiado. Cole na conversa."); } catch (e) { aviso(relatorioTexto(), true); } });
      el.limpar = bt("Zerar lista", "s", () => { estado.resultados = []; estado.peticionados.clear(); salvar(); tabela(); aviso("Lista zerada."); });
      f3.append(el.iniciar, el.parar, el.retomar, el.copiar, el.limpar);

      el.aviso = mk("div", { className: "a" });
      el.tab = mk("div");
      const n = mk("div", { className: "n", textContent: "O robô só mexe na Movimentação interna e no certificado, e clica em Peticionar uma vez por tarefa. Liminar, Redistribuir e o texto da peça ficam como estão. Deixe a aba à vista enquanto roda." });
      c.append(f1, f2, f3, el.aviso, el.tab, n);
      p.append(t, c);
      raiz.append(css, p);
      document.body.appendChild(host);
    }
    function aviso(msg, erro) { el.aviso.textContent = msg; el.aviso.className = "a" + (erro ? " e" : ""); fixo = !!erro; }
    function temAvisoFixo() { return fixo; }
    function botaoRetomar(v) { el.retomar.style.display = v ? "" : "none"; }
    function estadoBotoes() { [el.iniciar, el.limpar, el.modo].forEach((b) => (b.disabled = estado.rodando)); }
    function tabela() {
      el.tab.textContent = "";
      if (!estado.resultados.length) return;
      const tb = document.createElement("table");
      const h = tb.insertRow(); ["#", "Processo", "Perfil/Cat.", "Resultado"].forEach((x) => { const th = document.createElement("th"); th.textContent = x; h.appendChild(th); });
      estado.resultados.forEach((r, i) => {
        const tr = tb.insertRow();
        [String(i + 1), r.num, [r.perfil, r.categoria].filter(Boolean).join(" · ") + (r.titulo ? "\n" + r.titulo : ""), r.resultado + ((r.feito || []).length ? "\n" + r.feito.join("; ") : "")].forEach((v, k) => {
          const td = tr.insertCell(); td.textContent = v; td.style.whiteSpace = "pre-wrap";
          if (k === 3) td.className = /^(PETICIONADO|PREPARADA|CONFERIDA)/.test(r.resultado) ? "ok" : r.resultado.startsWith("PARADO") ? "pa" : "pu";
        });
      });
      el.tab.appendChild(tb);
    }
    function mostrar() { if (!host) criar(); host.style.display = ""; }
    return { aviso, temAvisoFixo, botaoRetomar, estadoBotoes, tabela, mostrar };
  })();

  estado.resultados = carregar();
  estado.peticionados = new Set(estado.resultados.filter((r) => /PETICIONADO|Peticionar clicado/.test(r.resultado + (r.feito || []).join())).map((r) => r.num));
  window.__roboSAJ = { mostrar: ui.mostrar, categoria, lerCards, lerPropriedades, filaSelecionada, contagens, relatorioTexto, estado, VERSAO, PERMITIDOS };
  ui.mostrar();
  ui.tabela();
  const f = filaSelecionada();
  if (location.host !== HOST && !window.__roboSAJ_teste) ui.aviso(`Esta aba não é o SAJ (${HOST}).`, true);
  else ui.aviso(f.ok ? `Fila certa: Para peticionar › Intimação. ${JSON.stringify(contagens())}. Escolha o modo e clique em Iniciar.` : "Atenção: " + f.motivo + ".", !f.ok);
})();
