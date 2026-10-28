// Robô do SAJ Defensorias (painel-saj.ms.def.br) - versão 0.2: SÓ CONFERE, NÃO PETICIONA.
// Roda como favorito (bookmarklet) na aba do Painel de Tarefas, fila "Para peticionar > Intimação".
// Para cada tarefa: abre ("Continuar"), lê a peça e as Propriedades, aplica as conferências e fecha o editor.
// Não digita, não altera campo, não marca nem desmarca caixa, não clica em Peticionar/Devolver/Excluir.
// Só três botões podem ser clicados (lista PERMITIDOS); qualquer outro clique é recusado pelo próprio código.
(function () {
  "use strict";

  const VERSAO = "0.2.0";
  const HOST = "painel-saj.ms.def.br";
  const CHAVE_SESSAO = "roboSAJ_resultados";

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

  // ------------------------------------------------------------ regras (as do prompt)
  const PERFIS = {
    A: { /* nº começa com 0 (SAJ) */
      tarja: "SAJ",
      movLabel: "920198 - Manifestação", movPai: "920281-ATOS FINALÍSTICOS",
      evento: "Manifestação do Autor",
      tipoDoc: "9934 - Manifestação da Defensoria", tipoDocCod: "9934",
    },
    B: { /* nº começa com 5 (EPROC) */
      tarja: "EPROC",
      movLabel: "1000150 - Petição Intermediária TJ", movPai: "1000000-MOVIMENTAÇÕES DE SISTEMA",
      evento: "PETIÇÃO",
      tipoDoc: "13 - PETIÇÃO", tipoDocCod: "13",
    },
  };
  const COMUM = { sigilo: "0 - Público", defensor: "Cahuê Duarte e Urdiales", certificado: "CAHUE DUARTE E URDIALES" };
  const TARJAS_ACEITAS = ["1º grau", "2º grau", "EPROC", "SAJ"].map(chave);

  // título do modelo (canto superior esquerdo do editor) -> categoria. Fora daqui = "Outros" = pula.
  // A primeira regra que casar vale. Modelos de devolver/finalizar nunca são peticionados.
  const CATEGORIAS = [
    [/DEVOLV|ADV(OGADO)? PARTICULAR|FINALIZ/, "Outros"],
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

  const RE_CNJ = /\d{7}\s*-?\s*\d{2}\s*\.?\s*\d{4}\s*\.?\s*\d\s*\.?\s*\d{2}\s*\.?\s*\d{4}/g;
  const fmtCNJ = (d) => d.replace(/^(\d{7})(\d{2})(\d{4})(\d)(\d{2})(\d{4})$/, "$1-$2.$3.$4.$5.$6");

  // ------------------------------------------------------------ cliques permitidos
  const PERMITIDOS = new Set(["btn-atividade-generic", "action-menu-propriedades", "action-emissao-expediente-close-btn"]);
  function clicar(el) {
    const t = el && el.getAttribute("data-testid");
    if (!PERMITIDOS.has(t)) throw new Error("clique recusado pelo robô: " + (t || "botão sem identificação"));
    if (el.disabled || el.getAttribute("aria-disabled") === "true") throw new Error("botão desabilitado: " + t);
    el.click();
  }

  // ------------------------------------------------------------ painel do SAJ
  function contagem(testid) {
    const c = q(`[data-testid="${testid}"] [data-testid="count-value"]`);
    return c ? texto(c) : "?";
  }
  function contagens() {
    const porRotulo = (rot) => {
      const p = qa('[data-testid="collapse-option-header"] p[aria-label]').find((x) => x.getAttribute("aria-label") === rot);
      const v = p && p.parentElement && q('[data-testid="count-value"]', p.parentElement);
      return v ? texto(v) : "?";
    };
    return { intimacao: contagem("count-content-27_Intimacao"), emProcessamento: porRotulo("Em processamento"), falhas: contagem("count-content-falhas") };
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
    return qa('[data-testid="container-card"]').map((cont) => {
      const card = q('[data-testid^="card-"][aria-selected]', cont) || q('[data-testid^="card-"]', cont);
      const num = texto(q('[data-testid="num-processo-label"]', cont));
      const rotulo = (sel, pref) => {
        const el = q(sel, cont);
        const a = (el && el.getAttribute("aria-label")) || "";
        return a.replace(pref, "").replace(/\.\s*Clique para copiar\.?$/i, "").trim() || texto(el);
      };
      return {
        num,
        testid: card ? card.getAttribute("data-testid") : "",
        tipo: texto(q('[data-testid="tipo-documento"]', cont)),
        botao: texto(q('[data-testid="btn-atividade-generic"]', cont)),
        ativa: rotulo('[data-testid="wrapper-parte-ativa"]', /^Parte ativa:\s*/i),
        passiva: rotulo('[data-testid="wrapper-parte-passiva"]', /^Parte passiva:\s*/i),
        demaisPassivas: qa('[data-testid="wrapper-mais-parte-passiva"] [data-testid^="name-parte-passiva-"]', cont).map(texto).filter(Boolean),
        tarjas: qa('[data-testid="stamp-group"] [role="listitem"]', cont).map((x) => x.getAttribute("aria-label") || texto(x)),
        textoCard: texto(cont),
      };
    });
  }

  // ------------------------------------------------------------ editor
  const editorAberto = () => q('[data-testid="editor-container"]');
  // diálogo que não seja o editor (aviso, confirmação, "aberta por outro usuário"...)
  function dialogoEstranho() {
    return qa('[role="dialog"], [role="alertdialog"]').find((d) => d.getAttribute("data-testid") !== "editor-container" && d.offsetParent !== null && !d.closest("#robo-saj-host")) || null;
  }
  function corpoEditor() {
    const ifr = q('[data-testid="editor-container"] iframe.tox-edit-area__iframe');
    const doc = ifr && ifr.contentDocument;
    return doc && doc.body ? { doc, body: doc.body, win: ifr.contentWindow } : null;
  }
  const valorSelect = (raiz) => texto(raiz && q('[class*="__single-value"]', raiz));

  function lerPropriedades() {
    const r = q('[data-testid="propriedades-root"]');
    if (!r) return null;
    const mov = q('[data-testid="select-tree-movimentacao"]', r);
    const def = q('input[aria-label="Defensor responsável"]', r);
    const cb = (n) => { const i = q(`input[name="${n}"]`, r); return i ? i.checked : null; };
    const oculto = (n) => { const i = q(`input[name="${n}"]`, r); return i ? i.value.trim() : ""; };
    return {
      movLabel: texto(mov && q('[data-testid="option-label"]', mov)),
      movPai: texto(mov && q('[data-testid="option-parent"]', mov)),
      evento: valorSelect(q('[data-testid="select-petition"]', r)),
      tipoDoc: valorSelect(q('[data-testid="select-tipo-documento"]', r)),
      tipoDocCod: oculto("tipoDocumento"),
      sigilo: valorSelect(q('[data-testid="select-sigilo-documento"]', r)),
      liminar: cb("urgente"),
      redistribuir: cb("redistribuir"),
      defensor: valorSelect(def && def.closest('[class*="__control"]')),
      certificado: valorSelect(q('[data-testid="propriedades-certificado"]', r)),
    };
  }

  // ------------------------------------------------------------ conferências da peça
  const RE_ANEXO = /segue[m]?\s+anex|em\s+anexo|junta[- ]se|anexa[- ]se|documentos?\s+anexos?|conforme\s+anexo/i;
  const RE_RASCUNHO = /\?\?\?|\[\s*VERIFICAR\s*\]|\[\s*COMPLETAR\s*\]|\bPENDENTE\b|x{4,}/i;
  const RE_PEDE = /\b(requer|requerer|requeiro|impugn|pugna|postula|pleiteia)/i;

  function marcasVisuais(c) {
    const achados = [];
    if (q("[data-mce-annotation], [data-mce-annotation-uid], .mce-annotation", c.body)) achados.push("comentário na peça");
    if (q("mark", c.body)) achados.push("texto marcado");
    const cor = (s) => { const m = String(s).match(/\d+(\.\d+)?/g); return m ? m.map(Number) : null; };
    // cor de marca-texto: saturada (amarelo, verde, ciano, rosa...); cinzas e tons pálidos de tabela/moldura não contam
    const saturada = (c) => { if (!c || (c.length === 4 && c[3] < 0.3)) return false; const mx = Math.max(c[0], c[1], c[2]), mn = Math.min(c[0], c[1], c[2]); return mx > 60 && (mx - mn) / mx > 0.4; };
    const hex = (c) => "#" + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
    const trecho = (el) => '"' + texto(el).replace(/\s+/g, " ").slice(0, 50) + '"';
    let fundo = null, verm = null;
    for (const el of qa("*", c.body)) {
      if (!Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      // campos automáticos do SAJ (não editáveis) e os dois colchetes previstos não contam
      if (el.closest('[contenteditable="false"], .mceNonEditable')) continue;
      if (/^\[\s*(data atual do sistema|nome do defensor)/.test(norm(texto(el)))) continue;
      const cs = c.win.getComputedStyle(el);
      const f = cor(cs.backgroundColor), l = cor(cs.color);
      if (!fundo && saturada(f)) fundo = `texto com marca-texto ${hex(f)}: ${trecho(el)}`;
      if (!verm && l && l[0] > 150 && l[1] < 110 && l[2] < 110) verm = `texto em vermelho: ${trecho(el)}`;
      if (fundo && verm) break;
    }
    if (fundo) achados.push(fundo);
    if (verm) achados.push(verm);
    return achados;
  }

  // XXX solto (rascunho), sem confundir com inciso XXX/XXXV etc.
  function temXXX(t) {
    const re = /\bXXX\b/g;
    let m;
    while ((m = re.exec(t))) {
      const antes = t.slice(Math.max(0, m.index - 25), m.index);
      if (!/(inciso|inc\.|art\.?\s*\d+[ºo°]?\s*,?|,)\s*$/i.test(antes)) return true;
    }
    return false;
  }

  // devolve {categoria, perfil, motivos[], ajustes[], obs[]}; motivos vazio = a tarefa passaria na conferência.
  // ajustes = o que a versão que peticiona mudaria nas Propriedades; obs = avisos que não impedem.
  function conferir(card, titulo, corpo, props) {
    const motivos = [], ajustes = [], obs = [];
    const num = card.num, dig = soDig(num);
    const perfil = dig[0] === "5" ? "B" : dig[0] === "0" ? "A" : "";
    const cat = categoria(titulo);

    if (dig.length !== 20) motivos.push("nº do processo do card ilegível");
    if (!perfil) motivos.push('nº não começa com "0" nem com "5"');
    if (cat === "Outros") motivos.push(`modelo "${titulo || "sem título"}" fora da lista de categorias`);

    const tarjas = card.tarjas.map(chave);
    const estranhas = card.tarjas.filter((t) => !TARJAS_ACEITAS.includes(chave(t)));
    if (estranhas.length) motivos.push("tarja no card: " + estranhas.join(", "));
    if (/sigil|segredo de justica|reu preso/.test(norm(card.textoCard))) motivos.push("card indica sigilo/segredo/réu preso");
    if (perfil && !tarjas.includes(chave(PERFIS[perfil].tarja))) motivos.push(`nº de perfil ${perfil}, mas o card não tem a tarja ${PERFIS[perfil].tarja}`);

    // ---- corpo
    const t = corpo ? texto(corpo.body) : "";
    if (!corpo) motivos.push("não consegui ler o texto da peça");
    else {
      if (t.length < 300) motivos.push("peça vazia ou muito curta");
      const fim = norm(t.slice(-500));
      if (t.length >= 300 && !/defensor|\[nome do defensor/.test(fim)) motivos.push("fim da peça sem assinatura do Defensor (pode estar cortada)");
      const nums = Array.from(new Set((t.match(RE_CNJ) || []).map(soDig)));
      if (!nums.length) motivos.push("nº do processo não aparece no corpo");
      const outros = nums.filter((n) => n !== dig);
      if (outros.length) motivos.push("outro nº de processo no corpo: " + outros.map(fmtCNJ).join(", "));
      const colch = (t.match(/\[[^\]\n]{0,200}\]/g) || []).filter((c) => !/^\[\s*(data atual do sistema|nome do defensor)/.test(norm(c)) && !/^\[\s*\d{1,3}\s*\]$/.test(c));
      if (colch.length) motivos.push("campo entre colchetes: " + colch.slice(0, 2).join(" "));
      if (RE_RASCUNHO.test(t) || temXXX(t)) motivos.push("marca de rascunho (XXX, ???, PENDENTE, [VERIFICAR]...)");
      for (const m of marcasVisuais(corpo)) motivos.push(m);
      if (RE_ANEXO.test(t)) motivos.push("a peça menciona anexo (conferir a aba Anexos à mão)");
      const nt = norm(t);
      // a peça pode não nomear as partes (modelos curtos): só avisa. Peça de outro processo é pega pelo nº.
      if (card.ativa && !nt.includes(norm(card.ativa))) obs.push(`parte ativa (${card.ativa}) não aparece na peça`);
      const passivas = [card.passiva].concat(card.demaisPassivas || []).filter(Boolean)
        .map((p) => chave(p.replace(/\s*[\/-]\s*MS\s*$/i, "")).split(" ").slice(0, 4).join(" "));
      if (passivas.length && !passivas.some((p) => chave(t).includes(p))) obs.push(`nenhuma parte passiva do card (${card.passiva}${(card.demaisPassivas || []).length ? " e demais" : ""}) aparece na peça`);
      if (cat === "Ciência" && RE_PEDE.test(t)) motivos.push("título CIÊNCIA, mas o texto pede ou impugna algo");
    }

    // ---- propriedades
    if (!props) motivos.push("não consegui ler a aba Propriedades");
    else if (perfil) {
      const P = PERFIS[perfil];
      const igual = (a, b) => chave(a) === chave(b);
      // campos que o prompt manda deixar no perfil: divergência vira ajuste (a versão que peticiona troca e confere)
      if (!igual(props.movLabel, P.movLabel) || !chave(props.movPai).startsWith(chave(P.movPai))) ajustes.push(`Movimentação → ${P.movLabel} (veio ${props.movLabel || "vazia"})`);
      if (!igual(props.evento, P.evento)) ajustes.push(`Evento → ${P.evento} (veio ${props.evento || "vazio"})`);
      if (!chave(props.tipoDoc).startsWith(chave(P.tipoDoc)) || (props.tipoDocCod && props.tipoDocCod !== P.tipoDocCod)) ajustes.push(`Tipo de documento → ${P.tipoDoc} (veio ${props.tipoDoc || "vazio"})`);
      if (!igual(props.defensor, COMUM.defensor)) ajustes.push(`Defensor → ${COMUM.defensor} (veio ${props.defensor || "vazio"})`);
      if (props.certificado && !igual(props.certificado, COMUM.certificado)) ajustes.push(`Certificado → ${COMUM.certificado} (veio ${props.certificado})`);
      // sigilo não se altera: diferente de Público = pula
      if (!igual(props.sigilo, COMUM.sigilo)) motivos.push(`Sigilo veio "${props.sigilo || "vazio"}"`);
      if (props.liminar === null || props.redistribuir === null) motivos.push("não achei as caixas Liminar/Redistribuir");
      if (props.liminar) ajustes.push("desmarcar Liminar");
      if (props.redistribuir) ajustes.push("desmarcar Redistribuir");
      if (!props.certificado) ajustes.push("escolher o certificado");
    }
    return { categoria: cat, perfil, motivos, ajustes, obs };
  }

  // ------------------------------------------------------------ rodada
  const estado = { rodando: false, parar: false, resultados: [], acoes: 0, pausa: null };
  function salvar() { try { sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(estado.resultados)); } catch (e) { /* sem armazenamento */ } }
  function carregar() { try { return JSON.parse(sessionStorage.getItem(CHAVE_SESSAO) || "[]"); } catch (e) { return []; } }

  // para e espera o usuário clicar em "Continuar a rodada" no painel do robô
  function pausar(msg) {
    ui.aviso(msg + " Resolva na tela do SAJ e clique em \"Continuar a rodada\" (ou \"Parar\").", true);
    return new Promise((res) => { estado.pausa = res; ui.botaoRetomar(true); });
  }

  async function fecharEditor() {
    const b = q('[data-testid="action-emissao-expediente-close-btn"]');
    if (!b) return !editorAberto();
    clicar(b); estado.acoes++;
    const ok = await aguardar(() => !editorAberto(), 8000);
    if (ok) return true;
    const d = dialogoEstranho();
    await pausar(`Ao fechar o editor apareceu: "${d ? texto(d).slice(0, 300) : "o editor não fechou"}". Saia SEM salvar e SEM peticionar.`);
    return !editorAberto();
  }

  async function tratar(card) {
    const r = { num: card.num, perfil: "", categoria: "", titulo: "", resultado: "", ajustes: [] };
    const cont = qa('[data-testid="container-card"]').find((c) => texto(q('[data-testid="num-processo-label"]', c)) === card.num);
    if (!cont) { r.resultado = "PULADO – card sumiu da fila"; return r; }
    if (norm(card.tipo) !== "intimacao") { r.resultado = `PULADO – card não é Intimação (${card.tipo})`; return r; }
    const btn = q('[data-testid="btn-atividade-generic"]', cont);
    if (!btn || norm(texto(btn)) !== "continuar") { r.resultado = "PULADO – card sem o botão Continuar"; return r; }

    clicar(btn); estado.acoes++;
    const aberto = await aguardar(() => editorAberto() || dialogoEstranho(), 20000);
    if (!aberto || !editorAberto()) {
      const d = dialogoEstranho();
      r.resultado = "PARADO – " + (d ? `apareceu: "${texto(d).slice(0, 200)}"` : "o editor não abriu em 20 s");
      return r;
    }
    // o card aberto fica com aria-selected="true": confere que é o mesmo processo
    const sel = q('[data-testid^="card-"][aria-selected="true"]');
    if (!sel || sel.getAttribute("data-testid") !== "card-" + card.num) {
      r.resultado = "PULADO – o editor abriu para outro card (" + (sel ? sel.getAttribute("data-testid").slice(5) : "?") + ")";
      await fecharEditor(); return r;
    }
    // espera o texto da peça carregar e parar de mudar
    let ant = "";
    const corpo = await aguardar(() => {
      const c = corpoEditor();
      const t = c ? texto(c.body) : "";
      const estavel = t.length > 50 && t === ant;
      ant = t;
      return estavel ? c : null;
    }, 20000, 700);
    if (!q('[data-testid="propriedades-root"]')) {
      const b = q('[data-testid="action-menu-propriedades"]');
      if (b) { clicar(b); estado.acoes++; }
      await aguardar(() => q('[data-testid="propriedades-root"]'), 8000);
    }
    await esperar(400);
    const titulo = texto(q('[data-testid="editor-container"] p[role="banner"]'));
    const props = lerPropriedades();
    const c = conferir(card, titulo, corpo, props);
    Object.assign(r, { perfil: c.perfil, categoria: c.categoria, titulo, ajustes: c.ajustes, obs: c.obs });
    r.resultado = c.motivos.length ? "PULARIA – " + c.motivos.join("; ") : "OK – pronta para peticionar";
    await fecharEditor();
    return r;
  }

  async function rodar(limite) {
    if (estado.rodando) return;
    if (location.host !== HOST && !window.__roboSAJ_teste) { ui.aviso(`Abra o Painel de Tarefas em ${HOST} e clique no favorito lá.`, true); return; }
    if (editorAberto()) { ui.aviso("Feche o editor que está aberto (sem salvar) e clique em Iniciar de novo.", true); return; }
    const f = filaSelecionada();
    if (!f.ok) { ui.aviso("Não comecei: " + f.motivo + ".", true); return; }
    const feitos = new Set(estado.resultados.map((x) => x.num));
    const cards = lerCards().filter((c) => !feitos.has(c.num));
    if (!cards.length) { ui.aviso("Nenhuma tarefa nova nesta página da fila.", true); return; }
    estado.rodando = true; estado.parar = false; estado.inicio = contagens();
    ui.estadoBotoes();
    let falhasSeguidas = 0;
    try {
      for (const card of cards.slice(0, limite)) {
        if (estado.parar) break;
        const fila = filaSelecionada();
        if (!fila.ok) { ui.aviso("Parei: " + fila.motivo + ".", true); break; }
        ui.aviso(`Conferindo ${card.num}...`);
        let r;
        try { r = await tratar(card); } catch (e) { r = { num: card.num, perfil: "", categoria: "", titulo: "", ajustes: [], resultado: "PARADO – erro do robô: " + e.message }; }
        estado.resultados.push(r); salvar(); ui.tabela();
        if (r.resultado.startsWith("PARADO")) {
          falhasSeguidas++;
          if (editorAberto() || dialogoEstranho() || falhasSeguidas >= 2) { ui.aviso("Parei em " + card.num + ": " + r.resultado.slice(9), true); break; }
        } else falhasSeguidas = 0;
        await esperar(800);
      }
    } finally {
      estado.rodando = false; estado.fim = contagens(); ui.estadoBotoes();
      if (!estado.parar && !ui.temAvisoFixo()) ui.aviso("Rodada concluída. Nada foi peticionado nem alterado.");
    }
  }

  function relatorioTexto() {
    const linhas = ["| # | Processo | Perfil | Categoria | Modelo | Resultado | Ajustes que faria | Observações |", "|---|---|---|---|---|---|---|---|"];
    estado.resultados.forEach((r, i) => linhas.push(`| ${i + 1} | ${r.num} | ${r.perfil} | ${r.categoria} | ${r.titulo} | ${r.resultado} | ${(r.ajustes || []).join("; ")} | ${(r.obs || []).join("; ")} |`));
    const ok = estado.resultados.filter((r) => r.resultado.startsWith("OK")).length;
    const pul = estado.resultados.filter((r) => r.resultado.startsWith("PUL")).length;
    const par = estado.resultados.filter((r) => r.resultado.startsWith("PARADO")).length;
    linhas.push("", `${ok} prontas, ${pul} pulariam, ${par} paradas. Robô ${VERSAO}, só conferência (nada peticionado).`);
    const fmt = (c) => (c ? `Intimação ${c.intimacao}, Em processamento ${c.emProcessamento}, Falhas ${c.falhas}` : "-");
    linhas.push(`Menu no início: ${fmt(estado.inicio)}. No fim: ${fmt(estado.fim)}.`);
    return linhas.join("\n");
  }

  // ------------------------------------------------------------ interface (fica num shadow DOM, sem mexer no SAJ)
  const ui = (() => {
    let host, raiz, el = {}, fixo = false;
    function criar() {
      host = document.createElement("div");
      host.id = "robo-saj-host";
      host.style.cssText = "position:fixed;top:70px;right:16px;z-index:2147483647;";
      raiz = host.attachShadow({ mode: "open" });
      const css = document.createElement("style");
      css.textContent = `
        .p{width:440px;max-height:80vh;display:flex;flex-direction:column;background:#fff;color:#1d2433;border:2px solid #03508D;border-radius:8px;
           box-shadow:0 6px 24px rgba(0,0,0,.25);font:13px/1.4 Segoe UI,Arial,sans-serif}
        .t{background:#03508D;color:#fff;padding:8px 10px;font-weight:600;display:flex;justify-content:space-between;align-items:center}
        .t button{background:none;border:0;color:#fff;font-size:16px;cursor:pointer}
        .c{padding:10px;overflow:auto}
        .f{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
        button.b{border:1px solid #03508D;background:#03508D;color:#fff;border-radius:4px;padding:5px 10px;cursor:pointer;font:inherit}
        button.s{background:#fff;color:#03508D}
        button:disabled{opacity:.45;cursor:default}
        input{width:52px;padding:3px;font:inherit}
        .a{padding:6px 8px;border-radius:4px;background:#eef4fa;margin-bottom:8px;white-space:pre-wrap}
        .a.e{background:#fdecea;color:#8a1c12}
        table{border-collapse:collapse;width:100%;font-size:12px}
        td,th{border-bottom:1px solid #dde3ea;padding:4px;text-align:left;vertical-align:top}
        .ok{color:#1b6e2d;font-weight:600}.pu{color:#8a5a00}.pa{color:#8a1c12;font-weight:600}
        .n{font-size:11px;color:#5b6472;margin-top:6px}`;
      const p = document.createElement("div"); p.className = "p";
      const t = document.createElement("div"); t.className = "t";
      const tt = document.createElement("span"); tt.textContent = `Robô SAJ ${VERSAO} · só conferência`;
      const x = document.createElement("button"); x.textContent = "×"; x.title = "Fechar o painel"; x.onclick = () => (host.style.display = "none");
      t.append(tt, x);
      const c = document.createElement("div"); c.className = "c";
      const f = document.createElement("div"); f.className = "f";
      const lab = document.createElement("label"); lab.textContent = "Tarefas: ";
      el.limite = document.createElement("input"); el.limite.type = "number"; el.limite.min = "1"; el.limite.max = "15"; el.limite.value = "5";
      lab.append(el.limite);
      const bt = (txt, cls, fn) => { const b = document.createElement("button"); b.className = "b " + (cls || ""); b.textContent = txt; b.onclick = fn; return b; };
      el.iniciar = bt("Iniciar", "", () => rodar(Math.max(1, Math.min(15, parseInt(el.limite.value, 10) || 5))));
      el.parar = bt("Parar", "s", () => { estado.parar = true; aviso("Vou parar depois da tarefa em andamento."); if (estado.pausa) { const r = estado.pausa; estado.pausa = null; botaoRetomar(false); r(); } });
      el.retomar = bt("Continuar a rodada", "", () => { const r = estado.pausa; estado.pausa = null; botaoRetomar(false); fixo = false; if (r) r(); });
      el.retomar.style.display = "none";
      el.copiar = bt("Copiar relatório", "s", async () => { try { await navigator.clipboard.writeText(relatorioTexto()); aviso("Relatório copiado. Cole na conversa."); } catch (e) { aviso(relatorioTexto(), true); } });
      el.limpar = bt("Zerar lista", "s", () => { estado.resultados = []; salvar(); tabela(); aviso("Lista zerada."); });
      f.append(lab, el.iniciar, el.parar, el.retomar, el.copiar, el.limpar);
      el.aviso = document.createElement("div"); el.aviso.className = "a";
      el.tab = document.createElement("div");
      const n = document.createElement("div"); n.className = "n";
      n.textContent = "Esta versão abre cada tarefa, confere e fecha. Não peticiona, não altera campos e não salva nada. Deixe a aba à vista enquanto roda.";
      c.append(f, el.aviso, el.tab, n);
      p.append(t, c);
      raiz.append(css, p);
      document.body.appendChild(host);
    }
    function aviso(msg, erro) { el.aviso.textContent = msg; el.aviso.className = "a" + (erro ? " e" : ""); fixo = !!erro; }
    function temAvisoFixo() { return fixo; }
    function botaoRetomar(v) { el.retomar.style.display = v ? "" : "none"; }
    function estadoBotoes() { el.iniciar.disabled = estado.rodando; el.limpar.disabled = estado.rodando; }
    function tabela() {
      el.tab.textContent = "";
      if (!estado.resultados.length) return;
      const tb = document.createElement("table");
      const h = tb.insertRow(); ["#", "Processo", "Perfil/Cat.", "Resultado"].forEach((x) => { const th = document.createElement("th"); th.textContent = x; h.appendChild(th); });
      estado.resultados.forEach((r, i) => {
        const tr = tb.insertRow();
        [String(i + 1), r.num, [r.perfil, r.categoria].filter(Boolean).join(" · ") + (r.titulo ? "\n" + r.titulo : ""), r.resultado + ((r.ajustes || []).length ? "\nFaria: " + r.ajustes.join("; ") : "") + ((r.obs || []).length ? "\nObs.: " + r.obs.join("; ") : "")].forEach((v, k) => {
          const td = tr.insertCell(); td.textContent = v; td.style.whiteSpace = "pre-wrap";
          if (k === 3) td.className = r.resultado.startsWith("OK") ? "ok" : r.resultado.startsWith("PARADO") ? "pa" : "pu";
        });
      });
      el.tab.appendChild(tb);
    }
    function mostrar() { if (!host) criar(); host.style.display = ""; }
    return { criar, aviso, temAvisoFixo, botaoRetomar, estadoBotoes, tabela, mostrar };
  })();

  estado.resultados = carregar();
  window.__roboSAJ = { mostrar: ui.mostrar, conferir, categoria, lerCards, lerPropriedades, filaSelecionada, contagens, relatorioTexto, estado, VERSAO };
  ui.mostrar();
  ui.tabela();
  const f = filaSelecionada();
  if (location.host !== HOST && !window.__roboSAJ_teste) ui.aviso(`Esta aba não é o SAJ (${HOST}).`, true);
  else ui.aviso(f.ok ? `Fila certa: Para peticionar › Intimação. Contagens: ${JSON.stringify(contagens())}. Clique em Iniciar.` : "Atenção: " + f.motivo + ".", !f.ok);
})();
