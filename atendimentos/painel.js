// APTO Atendimentos - painel: atendimentos do dia, pendências (kanban), fluxo, controle do mês, modelos e backup.
// Dentro do APTO (ponte.js): roda numa moldura das funções Atendimentos (dia, fluxo, frases), Quadro (pendências) e Relatório
// (controle do mês); dados na base do gabinete, pedidos ao SAP pela extensão, arquivos gravados pelo APTO.
(function () {
  "use strict";
  const A = self.ATD;
  const M = self.MSG;
  const ext = A.ext;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const el = (tag, props, ...filhos) => { const e = document.createElement(tag); Object.assign(e, props || {}); e.append(...filhos.filter((x) => x != null)); return e; };

  let D = { atendimentos: [], pecas: [], ajustes: {}, modelos: [], config: {} };

  const MODELOS_PADRAO = [
    { titulo: "Orientação sobre o cálculo", texto: "Foi orientad{o} sobre o cálculo de pena e sanadas demais dúvidas." },
    { titulo: "Orientação sobre o processo", texto: "Foi orientad{o} sobre o processo." },
    { titulo: "Aguardar apreciação", texto: "Foi orientad{o} a aguardar a apreciação dos pedidos." },
    { titulo: "Extinção: orientação", texto: "Foi orientad{o} sobre a extinção de pena." },
    { titulo: "Extinção pelo cumprimento", texto: "Será requerida a extinção pelo cumprimento." },
    { titulo: "ST: pedido será feito", texto: "Deseja pedir saída temporária. Verificado o preenchimento dos requisitos e apresentada a documentação necessária, o pedido será feito." },
    { titulo: "ST: encaminhar documentos", texto: "Deseja pedir saída temporária. Verificado o preenchimento dos requisitos, solicitou-se que encaminhe a documentação necessária até __/__." },
    { titulo: "ST: não está trabalhando", texto: "Desejava a saída temporária. Foi orientad{o} da impossibilidade momentânea em razão de não estar laborando. Orientad{o} a retornar em 30 dias." },
    { titulo: "Ofício CPAIG: atestado de trabalho", texto: "Será oficiado ao CPAIG solicitando atestado de trabalho." },
    { titulo: "Flexibilização do monitoramento", texto: "Deseja solicitar flexibilização do monitoramento em razão do trabalho. Foi solicitado que encaminhe a documentação necessária até __/__." },
    { titulo: "Justificativa: declaração colhida", texto: "Deseja apresentar justificativa quanto ao não comparecimento. Foi colhida declaração para ser acostada aos autos." },
    { titulo: "Regressão / audiência de justificação", texto: "Foi orientad{o} sobre a regressão. Será requerida a designação de audiência de justificação." },
    { titulo: "Pedido não apreciado: cartório", texto: "Foi informad{o} que o pedido ainda não foi apreciado. Entrei em contato com o cartório da 2ª VEP solicitando andamento." },
    { titulo: "Alteração de endereço", texto: "Deseja informar a alteração de endereço. Foi solicitado que encaminhe comprovante de residência até __/__ para ser acostado aos autos." },
    { titulo: "Transferência de comarca", texto: "Deseja solicitar a transferência do processo. Foi solicitado que encaminhe a documentação necessária até __/__." },
    { titulo: "PSC para PP / alteração da PRD", texto: "Deseja solicitar a alteração da PSC para PP. Foi solicitado que encaminhe a documentação necessária até __/__ para realização do pedido." },
    { titulo: "Alvará do saldo de salário", texto: "Entrei em contato com o cartório da 2ª VEP solicitando a expedição do alvará do saldo de salário." },
  ];
  const aplicarGenero = (t, a) => String(t || "").replace(/\{o\}/g, A.generoAtendido(a.quem, a.assistida));

  // ---------- gravação segura (relê antes de gravar: o SAP grava enquanto o painel está aberto) ----------
  const CAMPOS = ["nome", "hora", "processos", "contato", "quem", "assistida", "forma", "formaManual", "abertura", "corpo", "status", "msg", "concluido", "chamadoEm"];

  // ---------- falar com a aba do SAP ----------
  // tipo "chamarSap": seleciona e chama (o Chamar do botão direito da fila); "selecionarSap": só seleciona. Depois abre a aba do SAP.
  async function noSap(tipo, a) {
    if (ext.apto) {
      try { return (await self.ATD_APTO.pedir("atd_sap", tipo, { nome: a.nome, rk: a.rk || "" })) || { erro: "o SAP não respondeu" }; }
      catch (e) { return { erro: String(e.message || e) }; }
    }
    if (!ext.tabs || !ext.tabs.query) return { erro: "abra o painel pela extensão" };
    let abas = [];
    try { abas = await ext.tabs.query({ url: "https://*.defensoria.ms.def.br/sap/*" }); } catch (e) { abas = []; }
    if (!abas.length) return { erro: "o SAP não está aberto. Abra o SAP na tela de atendimento (Assistidos em Espera)." };
    let r = null, aba = null;
    for (const t of abas) {
      try { r = await ext.tabs.sendMessage(t.id, { tipo, nome: a.nome, rk: a.rk || "" }); } catch (e) { r = { erro: "recarregue a aba do SAP (F5)" }; }
      aba = t;
      if (r && r.ok) break;
    }
    if (r && r.ok && aba) {
      try { await ext.tabs.update(aba.id, { active: true }); if (aba.windowId != null) await ext.windows.update(aba.windowId, { focused: true }); } catch (e) { /* segue */ }
    }
    return r || { erro: "o SAP não respondeu" };
  }
  async function salvarAtd(a) {
    const d = await A.ler();
    const atual = d.atendimentos.find((x) => x.id === a.id);
    if (atual) { for (const k of CAMPOS) if (k in a) atual[k] = a[k]; Object.assign(a, atual); } else d.atendimentos.push(a);
    D.atendimentos = d.atendimentos;
    await A.gravar({ atendimentos: d.atendimentos });
  }
  async function removerAtd(id) {
    const d = await A.ler();
    d.atendimentos = d.atendimentos.filter((x) => x.id !== id);
    d.pecas = d.pecas.filter((p) => !(p.atendimentoId === id && p.status === "pendente"));
    Object.assign(D, { atendimentos: d.atendimentos, pecas: d.pecas });
    await A.gravar({ atendimentos: d.atendimentos, pecas: d.pecas });
  }
  async function mudarPecas(fn) {
    const d = await A.ler();
    const r = fn(d.pecas);
    d.pecas = Array.isArray(r) ? r : d.pecas;
    D.pecas = d.pecas;
    await A.gravar({ pecas: d.pecas });
  }
  const mudarPeca = (id, mud) => mudarPecas((ps) => { const x = ps.find((y) => y.id === id); if (x) Object.assign(x, mud); });
  async function salvarConfig() { await A.gravar({ config: D.config }); }

  // ---------- texto do atendimento ----------
  function aberturaDe(a) {
    const proc = a.processos.length ? ` referente aos autos ${a.processos.join(" e ")}` : "";
    return `Atendimento ${A.quemFrase(a.quem, a.assistida)}${proc}.`;
  }
  function textoFinal(a) {
    const corpo = String(a.corpo || "").trim();
    return (a.abertura ? aberturaDe(a) + (corpo ? " " : "") : "") + corpo;
  }
  const RE_FONES = /\(?\d{2}\)?\s*9?\d{4}[-\s.]?\d{4}/g;
  function semExitoTexto(a, n) {
    const fones = (String(a.contato || "").match(RE_FONES) || []).map((s) => s.trim());
    const quem = a.assistida ? "A assistida" : "O assistido";
    if (fones.length <= 1) {
      return `${quem} possuía atendimento virtual para a presente data. Realizei ${n} tentativas de contato com o telefone informado, qual seja, ${fones[0] || "__"}, todavia não obtive contato.`;
    }
    return `${quem} possuía atendimento virtual para a presente data. Realizei ${n * fones.length} ligações, sendo ${n} em cada número informado, quais sejam, ${fones.join(" / ")}. Todavia, não foi possível firmar contato.`;
  }
  // presença conforme a forma
  const PRESENCA = {
    presencial: [["agendado", "Aguardando"], ["presente", "Presente"], ["atendido", "Atendido"], ["faltou", "Não veio"]],
    virtual: [["agendado", "Aguardando"], ["atendido", "Atendido"], ["semExito", "Sem êxito"]],
  };
  const realizado = (a) => a.status === "atendido" || a.status === "semExito";

  // ---------- abas ----------
  function mostrarAba(nome) {
    $$(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
    $$(".aba").forEach((s) => (s.hidden = s.id !== "aba-" + nome));
    desenharAba(nome);
    try { sessionStorage.setItem("aba", nome); } catch (e) { /* sem importância */ }
  }
  function desenharAba(nome) {
    if (nome === "dia") renderDia();
    if (nome === "pend") renderKanban();
    if (nome === "agenda") renderAgenda();
    if (nome === "fluxo") renderFluxo();
    if (nome === "ctrl") renderControle();
    if (nome === "cfg") renderCfg();
  }
  const abaAtual = () => ($(".abas button.ativa") || {}).dataset.aba || "dia";
  $$(".abas button").forEach((b) => b.addEventListener("click", () => mostrarAba(b.dataset.aba)));
  function contarPend() { $("#nPend").textContent = D.pecas.filter((p) => p.status === "pendente").length || ""; }
  function aviso(sel, texto, ms) {
    const p = $(sel);
    p.textContent = texto; p.hidden = !texto;
    if (texto) setTimeout(() => { if (p.textContent === texto) p.hidden = true; }, ms || 9000);
  }
  async function copiar(texto, botao) {
    try { await navigator.clipboard.writeText(texto); } catch (err) {
      const ta = el("textarea", { value: texto }); document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
    }
    if (botao) { const old = botao.textContent; botao.textContent = "Copiado ✓"; botao.classList.add("ok"); setTimeout(() => { botao.textContent = old; botao.classList.remove("ok"); }, 1600); }
  }
  function segmentado(box, opcoes, valor, aoMudar) {
    box.replaceChildren(...opcoes.map(([v, r]) => {
      const b = el("button", { type: "button", textContent: r });
      b.dataset.v = v;
      b.classList.toggle("on", v === valor);
      b.addEventListener("click", () => { $$("button", box).forEach((x) => x.classList.toggle("on", x === b)); aoMudar(v); });
      return b;
    }));
  }

  // ---------- ATENDIMENTOS DO DIA ----------
  const diaSel = () => $("#dia").value || A.hojeISO();
  // ordem escolhida (fica guardada); o horário desempata sempre
  const ORDEM_SIT = { presente: 0, agendado: 1, atendido: 2, semExito: 3, faltou: 3 };
  function doDia() {
    const ordem = $("#ordemDia").value || "hora";
    const porHora = (a, b) => (a.hora || "99").localeCompare(b.hora || "99") || (a.criadoEm || 0) - (b.criadoEm || 0);
    const chave = {
      hora: () => 0,
      virtual: (a, b) => (a.forma === "virtual" ? 0 : 1) - (b.forma === "virtual" ? 0 : 1),
      presencial: (a, b) => (a.forma === "virtual" ? 1 : 0) - (b.forma === "virtual" ? 1 : 0),
      situacao: (a, b) => (ORDEM_SIT[a.status] || 0) - (ORDEM_SIT[b.status] || 0),
      nome: (a, b) => A.norm(a.nome).localeCompare(A.norm(b.nome)),
    }[ordem] || (() => 0);
    return D.atendimentos.filter((a) => a.data === diaSel()).sort((a, b) => chave(a, b) || porHora(a, b));
  }
  $("#ordemDia").addEventListener("change", async () => { D.config.ordemDia = $("#ordemDia").value; await salvarConfig(); renderDia(); });
  // contadores no topo: também filtram a lista
  let filtroDia = "todos";
  const FILTROS = [
    ["todos", "Na agenda", () => true],
    ["presente", "Presentes", (a) => a.status === "presente"],
    ["agendado", "Aguardando", (a) => a.status === "agendado"],
    ["atendido", "Atendidos", (a) => a.status === "atendido"],
    ["falta", "Não veio / sem êxito", (a) => a.status === "faltou" || a.status === "semExito"],
    ["concluido", "Concluídos", (a) => a.concluido],
  ];
  // cartões abertos (guardados durante a sessão)
  const abertosIds = new Set((() => { try { return JSON.parse(sessionStorage.getItem("abertos") || "[]"); } catch (e) { return []; } })());
  const guardarAbertos = () => { try { sessionStorage.setItem("abertos", JSON.stringify([...abertosIds])); } catch (e) { /* sem importância */ } };
  const ico = (nome) => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("class", "ic"); s.setAttribute("aria-hidden", "true");
    const u = document.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#i-" + nome); s.append(u); return s; };
  function renderDia() {
    const itens = doDia();
    $("#vazioDia").hidden = itens.length > 0;
    $("#contadores").hidden = !itens.length;
    $("#contadores").replaceChildren(...FILTROS.map(([k, rot, f]) => {
      const b = el("button", { type: "button", className: "contador c-" + k + (filtroDia === k ? " on" : "") },
        el("span", { className: "num", textContent: String(itens.filter(f).length) }), el("span", { className: "rot", textContent: rot }));
      b.setAttribute("aria-pressed", String(filtroDia === k));
      b.addEventListener("click", () => { filtroDia = filtroDia === k ? "todos" : k; renderDia(); });
      return b;
    }));
    const passa = (FILTROS.find((x) => x[0] === filtroDia) || FILTROS[0])[2];
    const abertos = itens.filter((a) => !a.concluido && passa(a)), feitos = itens.filter((a) => a.concluido);
    $("#lista").replaceChildren(...abertos.map(card));
    if (filtroDia !== "todos" && filtroDia !== "concluido" && !abertos.length) $("#lista").append(el("p", { className: "vazio", textContent: "Nenhum atendimento nesta situação." }));
    if (filtroDia === "concluido") $("#concluidosBox").open = true;
    $("#concluidosBox").hidden = !feitos.length;
    $("#nConc").textContent = feitos.length ? `(${feitos.length})` : "";
    $("#concluidos").replaceChildren(...feitos.map((a) => {
      const pres = ((PRESENCA[a.forma] || PRESENCA.presencial).find((x) => x[0] === a.status) || ["", a.status === "semExito" ? "Sem êxito" : a.status === "faltou" ? "Não veio" : "Aguardando"])[1];
      const reabrir = el("button", { className: "sec" }, ico("reabrir"), "Reabrir");
      reabrir.addEventListener("click", async () => { a.concluido = false; abertosIds.add(a.id); guardarAbertos(); await salvarAtd(a); renderDia(); });
      const copiarB = el("button", { className: "fantasma", title: "Copiar o texto para o SAP" }, ico("copiar"), "Copiar");
      copiarB.addEventListener("click", () => copiar(textoFinal(a), copiarB));
      return el("div", { className: "concl st-" + a.status },
        el("span", { className: "hora", textContent: a.hora || "—" }),
        el("b", { textContent: a.nome }),
        el("span", { className: "dica", textContent: `${a.forma === "virtual" ? "Virtual" : "Presencial"} · ${pres}` + (a.processos[0] ? ` · ${a.processos[0]}` : "") }),
        el("span", { className: "espaco" }), copiarB, reabrir);
    }));
    contarPend();
  }

  function card(a) {
    const c = $("#tplCard").content.firstElementChild.cloneNode(true);
    c.dataset.id = a.id;
    // linha de resumo: nome, processo, pedido, forma e situação (em texto, não só na cor)
    const ROT_ESTADO = { agendado: "Aguardando", presente: "Presente", atendido: "Atendido", faltou: "Não veio", semExito: "Sem êxito" };
    const resumo = () => {
      $(".nomeTxt", c).textContent = a.nome || "(sem nome)";
      $(".sub", c).textContent = [a.processos[0], a.fato && a.fato.pedido].filter(Boolean).join(" · ") || (a.fatoLido ? "Sem Fato Narrado no SAP" : "Fato Narrado ainda não lido");
      const pf = $(".pillForma", c);
      pf.className = "pill pillForma" + (a.forma === "virtual" ? " virtual" : "");
      pf.replaceChildren(ico(a.forma === "virtual" ? "tela" : "pessoa"), a.forma === "virtual" ? "Virtual" : "Presencial");
      const pe = $(".pillEstado", c);
      pe.className = "pill pillEstado st-" + (a.status || "agendado");
      pe.textContent = ROT_ESTADO[a.status || "agendado"] + (a.status === "presente" && a.chegada ? " · chegou " + a.chegada : "") +
        (a.chamadoEm && (a.status === "presente" || a.status === "agendado") ? " · chamado " + a.chamadoEm : "");
      // Chamar: presencial, de hoje, ainda não atendido
      const cb = $(".chamarBtn", c);
      // sem Chamar o espaço continua reservado, para as etiquetas ficarem alinhadas entre as linhas
      const podeChamar = a.forma !== "virtual" && a.data === A.hojeISO() && (a.status === "presente" || a.status === "agendado");
      cb.classList.toggle("oculto", !podeChamar);
      cb.tabIndex = podeChamar ? 0 : -1;
      cb.setAttribute("aria-hidden", String(!podeChamar));
      cb.classList.toggle("forte", a.status === "presente");
      cb.lastChild.textContent = a.chamadoEm ? "Chamar de novo" : "Chamar";
    };
    async function irAoSap(tipo, botao) {
      const old = botao.disabled; botao.disabled = true;
      const r = await noSap(tipo, a);
      botao.disabled = old;
      if (!r.ok) return aviso("#msgDia", (tipo === "chamarSap" ? "Não chamou: " : "Não abriu no SAP: ") + r.erro, 12000);
      if (tipo === "chamarSap") {
        const d = new Date();
        a.chamadoEm = A.pad(d.getHours()) + ":" + A.pad(d.getMinutes());
        abertosIds.add(a.id); guardarAbertos();
        await salvarAtd(a);
        renderDia();
      }
    }
    $(".chamarBtn", c).addEventListener("click", (e) => irAoSap("chamarSap", e.currentTarget));
    $(".verSap", c).addEventListener("click", (e) => irAoSap("selecionarSap", e.currentTarget));
    const pintar = () => { c.className = "card st-" + (a.status || "agendado") + (a.forma === "virtual" ? " virtual" : "") + (abertosIds.has(a.id) ? " aberto" : ""); resumo(); };
    const linha = $(".linha", c), det = $(".detalhe", c);
    const abrir = (sim) => {
      det.hidden = !sim; linha.setAttribute("aria-expanded", String(sim));
      if (sim) abertosIds.add(a.id); else abertosIds.delete(a.id);
      guardarAbertos(); pintar();
    };
    linha.addEventListener("click", () => abrir(det.hidden));
    det.hidden = !abertosIds.has(a.id);
    linha.setAttribute("aria-expanded", String(!det.hidden));
    pintar();
    $(".hora", c).textContent = a.hora || "—";
    $(".nome", c).value = a.nome;
    let t = null;
    const agendar = () => { clearTimeout(t); t = setTimeout(() => salvarAtd(a), 500); };
    const atualizarAbertura = () => { $(".aberturaTxt", c).textContent = "“" + aberturaDe(a) + "”"; };

    // forma e presença
    const desenharPresenca = () => segmentado($(".presenca", c), PRESENCA[a.forma] || PRESENCA.presencial, a.status || "agendado", (v) => {
      a.status = v; pintar(); salvarAtd(a);
    });
    segmentado($(".forma", c), [["presencial", "Presencial"], ["virtual", "Virtual"]], a.forma || "presencial", (v) => {
      a.forma = v; a.formaManual = true;
      if (v === "virtual" && a.status === "faltou") a.status = "semExito";
      if (v === "presencial" && a.status === "semExito") a.status = "faltou";
      pintar(); desenharPresenca(); salvarAtd(a);
    });
    desenharPresenca();

    // Fato Narrado
    if (a.fato && a.fato.texto) {
      if (a.fato.pedido) { $(".pedido", c).hidden = false; $(".pedido", c).textContent = "Pedido: " + a.fato.pedido; }
      $(".fato", c).hidden = false;
      $(".fato summary", c).textContent = `Fato Narrado do agendamento (${a.fato.data}${a.fato.defensor ? " · " + a.fato.defensor : ""})`;
      $(".fatoTexto", c).textContent = a.fato.texto;
    } else if (a.fatoLido) {
      $(".pedido", c).hidden = false; $(".pedido", c).textContent = "Sem Fato Narrado no SAP.";
    }

    // campos
    $(".processos", c).value = a.processos.join(" ; ");
    $(".contato", c).value = a.contato || "";
    const sq = $(".quem", c);
    sq.append(...A.QUEM.map(([k]) => new Option(k, k)));
    sq.value = a.quem || "assistido";
    $(".assistida", c).checked = !!a.assistida;
    $(".abertura", c).checked = !!a.abertura;
    atualizarAbertura();
    $(".corpo", c).value = a.corpo || "";
    $(".nome", c).addEventListener("input", (e) => { a.nome = e.target.value; resumo(); agendar(); });
    $(".processos", c).addEventListener("input", (e) => {
      a.processos = e.target.value.split(/[;,\n]| e /).map((s) => A.cnj(s) || s.trim()).filter(Boolean);
      atualizarAbertura(); resumo(); agendar();
    });
    $(".contato", c).addEventListener("input", (e) => { a.contato = e.target.value; agendar(); zap.atualizar(); });
    sq.addEventListener("change", (e) => { a.quem = e.target.value; atualizarAbertura(); salvarAtd(a); });
    $(".assistida", c).addEventListener("change", (e) => { a.assistida = e.target.checked; atualizarAbertura(); salvarAtd(a); });
    $(".abertura", c).addEventListener("change", (e) => { a.abertura = e.target.checked; salvarAtd(a); });
    $(".corpo", c).addEventListener("input", (e) => {
      a.corpo = e.target.value;
      if ((a.status === "agendado" || a.status === "presente") && a.corpo.trim()) { a.status = "atendido"; pintar(); desenharPresenca(); }
      agendar();
      sugerirPendencia();
      zap.sugerir();
    });
    const ins = $(".inserir", c);
    for (const [i, m] of D.modelos.entries()) ins.append(new Option(m.titulo, String(i)));
    ins.addEventListener("change", () => {
      const m = D.modelos[Number(ins.value)];
      ins.value = "";
      if (!m) return;
      const ta = $(".corpo", c);
      ta.value = (ta.value.trim() ? ta.value.trim() + " " : "") + aplicarGenero(m.texto, a);
      ta.dispatchEvent(new Event("input"));
      ta.focus();
    });
    $(".semExitoBtn", c).addEventListener("click", () => {
      const fones = (String(a.contato || "").match(RE_FONES) || []).length;
      const n = prompt(fones > 1 ? `Quantas ligações em CADA número (${fones} números)?` : "Quantas tentativas de contato?", "9");
      if (!n || !(Number(n) > 0)) return;
      a.abertura = false; a.status = "semExito"; a.forma = "virtual"; a.formaManual = true;
      a.corpo = semExitoTexto(a, Number(n));
      salvarAtd(a).then(renderDia);
    });
    $(".copiar", c).addEventListener("click", (e) => copiar(textoFinal(a), e.currentTarget));
    $(".concluir", c).addEventListener("click", async () => {
      if ((a.status === "agendado" || a.status === "presente") && !confirm(`Ainda está como ${a.status === "presente" ? "Presente" : "Aguardando"}. Concluir assim mesmo?`)) return;
      a.concluido = true;
      abertosIds.delete(a.id); guardarAbertos();
      await salvarAtd(a);
      renderDia();
    });
    $(".gerarPet", c).addEventListener("click", () => abrirPet({ nome: a.nome, processos: a.processos, assistida: a.assistida }));
    $(".excluir", c).addEventListener("click", () => {
      if (confirm(`Excluir o atendimento de ${a.nome} deste dia? As pendências ainda abertas dele também saem.`)) removerAtd(a.id).then(renderDia);
    });

    // pendência a partir do atendimento
    const pPeca = $(".pPeca", c), pFila = $(".pFila", c), pPrazo = $(".pPrazo", c);
    pPeca.append(new Option("— peça —", ""), ...A.TIPOS.map(([k, r]) => new Option(r, k)));
    pFila.append(...A.FILAS.map(([k, r]) => new Option(r, k)));
    let pMexido = false;
    [pPeca, pFila, pPrazo].forEach((x) => x.addEventListener("change", () => { pMexido = true; }));
    function sugerirPendencia() {
      if (pMexido) return;
      const sug = A.sugerir(a.corpo);
      pPeca.value = sug[0] || "";
      const doc = A.pedeDocumento(a.corpo);
      pFila.value = doc ? "doc" : "fazer";
      pPrazo.value = A.prazoNoTexto(a.corpo, a.data) || "";
    }
    sugerirPendencia();
    // um botão para cada peça sugerida pelo texto (cada uma vira uma pendência e conta separado no mês)
    function sugeridas() {
      const ja = new Set(D.pecas.filter((p) => p.atendimentoId === a.id).map((p) => p.tipo));
      const sug = A.sugerir(a.corpo).filter((k) => !ja.has(k));
      $(".sugPecas", c).hidden = !sug.length;
      $(".sugBotoes", c).replaceChildren(...sug.map((k) => {
        const b = el("button", { className: "chip sugerida", type: "button", textContent: "+ " + A.nomeTipo(k), title: "Criar pendência desta peça (fila e prazo da linha acima)" });
        b.addEventListener("click", () => adicionar(k));
        return b;
      }));
    }
    async function adicionar(tipo) {
      await mudarPecas((ps) => {
        ps.push({ id: A.novoId(), tipo, processo: a.processos[0] || "", nome: a.nome, data: a.data, status: "pendente",
          coluna: pFila.value, prazo: pPrazo.value, obs: "", origem: "atendimento", atendimentoId: a.id, criadoEm: Date.now() });
        return ps;
      });
      pMexido = false;
      tags(); sugeridas(); contarPend();
    }
    $(".corpo", c).addEventListener("input", sugeridas);
    function tags() {
      sugeridas();
      const minhas = D.pecas.filter((p) => p.atendimentoId === a.id);
      $(".tags", c).replaceChildren(...minhas.map((p) => {
        const fila = p.status === "pendente" ? (A.FILAS.find((f) => f[0] === p.coluna) || ["", ""])[1] : p.status === "feito" ? "feita" : "arquivada";
        const tg = el("span", { className: "tag " + (p.status === "pendente" ? "f-" + p.coluna : "fechada"),
          textContent: `${p.tipo ? A.nomeTipo(p.tipo) : "sem peça"} · ${fila}${p.prazo && p.status === "pendente" ? " · até " + A.brDeIso(p.prazo).slice(0, 5) : ""}` });
        if (p.status === "pendente") {
          const x = el("button", { className: "icone", textContent: "×", title: "Tirar das pendências" });
          x.addEventListener("click", async () => { await mudarPecas((ps) => ps.filter((y) => y.id !== p.id)); tags(); contarPend(); });
          tg.append(x);
        }
        return tg;
      }));
    }
    tags();
    $(".pAdd", c).addEventListener("click", () => adicionar(pPeca.value));

    // WhatsApp
    const zap = mensagemZap(c, a, () => salvarAtd(a));
    return c;
  }

  // o WhatsApp abre no navegador (no APTO, pelo programa)
  const abrirZap = (url) => (ext.apto ? self.ATD_APTO.abrirLink(url) : window.open(url, "_blank", "noopener"));

  // caixa de mensagem de WhatsApp de um atendimento
  function mensagemZap(c, a, salvar) {
    a.msg = a.msg || { tipo: "docs", docs: null, outros: [], comPrazo: true, prazo: "" };
    const m = a.msg;
    const box = $(".zap", c);
    const lista = () => M.docs(D.config);
    let editado = false;
    function docsSugeridos() { return m.docs || M.sugerirDocs(a.corpo + " " + ((a.fato && a.fato.pedido) || ""), lista()); }
    function desenharDocs() {
      const marcados = docsSugeridos();
      const caixa = $(".zapDocs", box);
      caixa.hidden = m.tipo !== "docs";
      $(".zapLinha", box).hidden = m.tipo !== "docs";
      caixa.replaceChildren(...lista().map((d) => {
        const ck = el("input", { type: "checkbox", checked: marcados.includes(d.id) });
        ck.addEventListener("change", () => {
          const atual = new Set(docsSugeridos());
          if (ck.checked) atual.add(d.id); else atual.delete(d.id);
          m.docs = [...atual]; editado = false; salvar(); atualizar();
        });
        return el("label", { className: "chk doc", title: d.texto }, ck, " " + d.texto.split(/[,(]/)[0].trim());
      }), ...(m.outros || []).map((o, i) => {
        const x = el("button", { className: "icone", textContent: "×", title: "Tirar" });
        x.addEventListener("click", () => { m.outros.splice(i, 1); salvar(); desenharDocs(); atualizar(); });
        return el("span", { className: "tag" }, o, x);
      }));
    }
    function atualizar() {
      if (!$(".zapPrazo", box).value && !m.prazo) $(".zapPrazo", box).value = A.prazoNoTexto(a.corpo, a.data) || "";
      const prazo = m.prazo || $(".zapPrazo", box).value;
      if (!editado) $(".zapTexto", box).value = M.montar(Object.assign({}, m, { docs: docsSugeridos(), prazo }), D.config);
      const fone = M.foneWhats(a.contato);
      $(".zapFone", box).textContent = fone ? `WhatsApp: +${fone}` : "Sem telefone no contato: copie a mensagem.";
      $(".zapAbrir", box).disabled = !fone;
    }
    segmentado($(".zapTipo", box), [["docs", "Pedir documentos"], ["padrao", "Padrão"], ["baixa", "Baixa"]], m.tipo, (v) => {
      m.tipo = v; editado = false; salvar(); desenharDocs(); atualizar();
    });
    $(".zapComPrazo", box).checked = m.comPrazo !== false;
    $(".zapPrazo", box).value = m.prazo || "";
    $(".zapComPrazo", box).addEventListener("change", (e) => { m.comPrazo = e.target.checked; editado = false; salvar(); atualizar(); });
    $(".zapPrazo", box).addEventListener("change", (e) => { m.prazo = e.target.value; m.comPrazo = !!e.target.value; $(".zapComPrazo", box).checked = m.comPrazo; editado = false; salvar(); atualizar(); });
    $(".zapOutro", box).addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || !e.target.value.trim()) return;
      e.preventDefault();
      m.outros = (m.outros || []).concat(e.target.value.trim()); e.target.value = "";
      editado = false; salvar(); desenharDocs(); atualizar();
    });
    $(".zapTexto", box).addEventListener("input", () => { editado = true; });
    $(".zapCopiar", box).addEventListener("click", (e) => copiar($(".zapTexto", box).value, e.currentTarget));
    $(".zapAbrir", box).addEventListener("click", () => {
      const fone = M.foneWhats(a.contato);
      if (fone) abrirZap(M.linkWhats(fone, $(".zapTexto", box).value));
    });
    box.addEventListener("toggle", () => { if (box.open) { desenharDocs(); atualizar(); } });
    return { atualizar: () => box.open && atualizar(), sugerir: () => { if (box.open && !m.docs) { desenharDocs(); atualizar(); } } };
  }

  $("#hojeBtn").addEventListener("click", () => { $("#dia").value = A.hojeISO(); renderDia(); });
  $("#dia").addEventListener("change", renderDia);
  $("#novoAtd").addEventListener("click", async () => {
    const nome = prompt("Nome do assistido:");
    if (!nome) return;
    const a = { id: A.novoId(), data: diaSel(), hora: "", nome: A.nomeProprio(nome), processos: [], contato: "", quem: "", assistida: false,
      forma: "presencial", formaManual: true, abertura: true, corpo: "", status: "atendido", fato: null, origem: "manual", criadoEm: Date.now() };
    abertosIds.add(a.id); guardarAbertos();
    filtroDia = "todos";
    await salvarAtd(a);
    renderDia();
    const x = $(`.card[data-id="${a.id}"] .processos`);
    if (x) x.focus();
  });
  $("#lerSapBtn").addEventListener("click", async (ev) => {
    if (ext.apto) {
      const b = ev.currentTarget;
      b.disabled = true; b.setAttribute("aria-busy", "true");
      aviso("#msgDia", "Lendo a fila no SAP… Não use a aba do SAP até terminar (o selo verde no canto da página mostra o andamento).", 1200000);
      let r = null;
      try { r = await self.ATD_APTO.pedir("atd_sap", "lerFilaSap", {}); } catch (e) { r = { erro: String(e.message || e) }; }
      b.disabled = false; b.removeAttribute("aria-busy");
      if (!r || r.erro || r.ok === false) return aviso("#msgDia", "Não deu para ler: " + ((r && (r.erro || r.motivo)) || "fila não encontrada"), 20000);
      return aviso("#msgDia", `Lidos ${r.lidos} de ${r.total}.` + (r.erros && r.erros.length ? " Problemas: " + r.erros.join("; ") : ""), 20000);
    }
    if (!ext.tabs || !ext.tabs.query) return aviso("#msgDia", "Abra o SAP e use o botão do selo verde no canto da página.");
    let abas = [];
    try { abas = await ext.tabs.query({ url: "https://*.defensoria.ms.def.br/sap/*" }); } catch (e) { abas = []; }
    if (!abas.length) return aviso("#msgDia", "Não achei o SAP aberto. Abra o SAP na tela de atendimento (Assistidos em Espera) e clique de novo.");
    aviso("#msgDia", "Lendo a fila no SAP… Não use o SAP até terminar (o selo verde mostra o andamento).", 60000);
    let r = null;
    for (const t of abas) {
      try { r = await ext.tabs.sendMessage(t.id, { tipo: "lerFilaSap" }); } catch (e) { r = { ok: false, motivo: "recarregue a aba do SAP (a extensão foi instalada/atualizada depois que ela abriu)" }; }
      if (r && r.ok) break;
    }
    if (!r || !r.ok) return aviso("#msgDia", "Não deu para ler: " + ((r && r.motivo) || "fila não encontrada"));
    aviso("#msgDia", `Lidos ${r.lidos} de ${r.total}.` + (r.erros && r.erros.length ? " Problemas: " + r.erros.join("; ") : ""), 20000);
  });

  // ---------- relatório do dia ----------
  $("#relatorioBtn").addEventListener("click", async () => {
    const dia = diaSel();
    const itens = doDia().filter((a) => realizado(a) && textoFinal(a).trim());
    if (!itens.length) return aviso("#msgDia", "Nenhum atendimento com texto neste dia (marque Veio/Atendido ou Sem êxito e escreva o que foi feito).");
    const [, mes, d] = dia.split("-");
    // como nos relatórios: o telefone só aparece nos atendimentos virtuais
    const blob = await self.DOCX.relatorio(`ATENDIMENTOS – ${d}.${mes}`,
      itens.map((a) => ({ nome: a.nome, processos: a.processos, contato: a.forma === "virtual" ? a.contato : "", texto: textoFinal(a) })));
    const onde = await salvarArquivo(blob, `${d}.${mes}.docx`, Number(mes) - 1);
    const semTexto = doDia().filter((a) => realizado(a) && !textoFinal(a).trim()).length;
    aviso("#msgDia", `Relatório salvo: ${onde}` + (semTexto ? ` · ${semTexto} atendido(s) sem texto ficaram de fora.` : ""));
  });

  function idb() {
    return new Promise((ok, erro) => {
      const r = indexedDB.open("apto-atd", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("kv");
      r.onsuccess = () => ok(r.result);
      r.onerror = () => erro(r.error);
    });
  }
  async function kv(chave, valor) {
    const db = await idb();
    return new Promise((ok, erro) => {
      const tx = db.transaction("kv", valor === undefined ? "readonly" : "readwrite");
      const st = tx.objectStore("kv");
      const r = valor === undefined ? st.get(chave) : valor === null ? st.delete(chave) : st.put(valor, chave);
      r.onsuccess = () => ok(r.result);
      r.onerror = () => erro(r.error);
    });
  }
  async function pastaDoMes(raiz, iMes) {
    const alvo = A.MESES[iMes];
    let numerados = 0;
    for await (const [nome, h] of raiz.entries()) {
      if (h.kind !== "directory") continue;
      if (/^\d+\./.test(nome)) numerados++;
      if (A.norm(nome.replace(/^\d+\.\s*/, "")) === A.norm(alvo)) return h;
    }
    return raiz.getDirectoryHandle(`${numerados + 1}. ${alvo}`, { create: true });
  }
  function baixar(blob, nome) {
    if (ext.apto) {
      const onde = abaAtual() === "cfg" ? "#msgCfg" : abaAtual() === "ctrl" ? "#msgRel" : "#msgDia";
      self.ATD_APTO.salvar(blob, nome, "").then((c) => { if (c) aviso(onde, "Salvo: " + c); })
        .catch((e) => aviso(onde, "Não foi possível salvar: " + (e.message || e)));
      return;
    }
    const url = URL.createObjectURL(blob);
    const l = el("a", { href: url, download: nome });
    document.body.appendChild(l); l.click(); l.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  async function salvarArquivo(blob, nomeArq, iMes) {
    if (ext.apto) return (await self.ATD_APTO.salvar(blob, nomeArq, "relatorio", iMes)) || "não salvo (cancelado)";
    let raiz = null;
    try { raiz = await kv("pasta"); } catch (e) { raiz = null; }
    if (raiz) {
      try {
        let perm = await raiz.queryPermission({ mode: "readwrite" });
        if (perm !== "granted") perm = await raiz.requestPermission({ mode: "readwrite" });
        if (perm === "granted") {
          const pasta = await pastaDoMes(raiz, iMes);
          let nome = nomeArq, existe = false;
          try { await pasta.getFileHandle(nome); existe = true; } catch (e) { existe = false; }
          if (existe && !confirm(`Já existe ${nome} em "${pasta.name}". Substituir?`)) nome = nomeArq.replace(".docx", ` (${new Date().toTimeString().slice(0, 5).replace(":", "h")}).docx`);
          const w = await (await pasta.getFileHandle(nome, { create: true })).createWritable();
          await w.write(blob); await w.close();
          return `${raiz.name}\\${pasta.name}\\${nome}`;
        }
      } catch (e) { console.warn(e); }
    }
    baixar(blob, nomeArq);
    return `Downloads\\${nomeArq}`;
  }

  // ---------- PENDÊNCIAS (kanban) ----------
  const atdDe = (p) => D.atendimentos.find((a) => a.id === p.atendimentoId);
  function renderKanban() {
    const busca = A.norm($("#buscaPend").value);
    const casa = (p) => !busca || A.norm(`${p.nome} ${p.processo} ${A.nomeTipo(p.tipo)} ${p.obs}`).includes(busca);
    const hoje = A.hojeISO();
    $("#kanban").replaceChildren(...A.FILAS.map(([k, rot], iFila) => {
      const itens = D.pecas.filter((p) => p.status === "pendente" && p.coluna === k && casa(p))
        .sort((a, b) => (a.prazo || "9999").localeCompare(b.prazo || "9999") || (a.data || "").localeCompare(b.data || ""));
      const col = el("section", { className: "coluna c-" + k });
      col.append(el("h3", {}, rot + " ", el("span", { className: "cont2", textContent: String(itens.length) })));
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("alvo"); });
      col.addEventListener("dragleave", () => col.classList.remove("alvo"));
      col.addEventListener("drop", async (e) => {
        e.preventDefault(); col.classList.remove("alvo");
        const id = e.dataTransfer.getData("text/plain");
        if (id) { await mudarPeca(id, { coluna: k }); renderKanban(); }
      });
      for (const p of itens) col.append(cartaoPend(p, iFila, hoje));
      if (!itens.length) col.append(el("p", { className: "vazioCol", textContent: "—" }));
      return col;
    }));
    renderArquivo();
    contarPend();
  }
  function cartaoPend(p, iFila, hoje) {
    const a = atdDe(p);
    const k = el("article", { className: "kcard" + (p.prazo && p.prazo < hoje ? " vencido" : ""), draggable: true });
    k.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", p.id); k.classList.add("arrastando"); });
    k.addEventListener("dragend", () => k.classList.remove("arrastando"));
    const peca = el("select", { className: "kpeca" });
    peca.append(new Option("— peça —", ""), ...A.TIPOS.map(([t, r]) => new Option(r, t)));
    peca.value = p.tipo || "";
    peca.addEventListener("change", () => mudarPeca(p.id, { tipo: peca.value }));
    const prazo = el("input", { type: "date", value: p.prazo || "", title: "Prazo" });
    prazo.addEventListener("change", async () => { await mudarPeca(p.id, { prazo: prazo.value }); renderKanban(); });
    const obs = el("input", { className: "kobs", value: p.obs || "", placeholder: "observação" });
    obs.addEventListener("change", () => mudarPeca(p.id, { obs: obs.value }));
    const mover = (d) => async () => { const f = A.FILAS[iFila + d]; if (f) { await mudarPeca(p.id, { coluna: f[0] }); renderKanban(); } };
    const bEsq = el("button", { className: "icone", title: "Fila anterior", ariaLabel: "Mover para a fila anterior", disabled: iFila === 0 }, ico("esq"));
    bEsq.addEventListener("click", mover(-1));
    const bDir = el("button", { className: "icone", title: "Próxima fila", ariaLabel: "Mover para a próxima fila", disabled: iFila === A.FILAS.length - 1 }, ico("dir"));
    bDir.addEventListener("click", mover(1));
    const feita = el("button", { className: "ok", title: "Protocolada: arquiva e conta no controle do mês" }, ico("check"), "Feita");
    feita.addEventListener("click", async () => {
      if (!peca.value) { alert("Escolha a peça antes de marcar como feita (é ela que conta na tabela do mês)."); peca.focus(); return; }
      const q = prompt("Protocolada em (dd/mm/aaaa):", A.brDeIso(A.hojeISO()));
      if (!q) return;
      await mudarPeca(p.id, { status: "feito", feitoEm: A.isoDeBr(q) || A.hojeISO(), tipo: peca.value });
      renderKanban();
    });
    const arq = el("button", { className: "sec", textContent: "Arquivar", title: "Arquiva sem peça (não conta no controle)" });
    arq.addEventListener("click", async () => { await mudarPeca(p.id, { status: "arquivado", feitoEm: A.hojeISO() }); renderKanban(); });
    // WhatsApp: documentos (Aguardando documento) ou baixa (Não encaminhou)
    const fone = a ? M.foneWhats(a.contato) : "";
    let zap = null;
    if (p.coluna === "doc" || p.coluna === "naoEnc") {
      const tipo = p.coluna === "doc" ? "docs" : "baixa";
      const texto = () => {
        const m = Object.assign({ docs: null, outros: [], comPrazo: true }, (a && a.msg) || {}, { tipo, prazo: p.prazo || (a && a.msg && a.msg.prazo) || "" });
        if (!m.docs) m.docs = M.sugerirDocs((a ? a.corpo + " " + ((a.fato && a.fato.pedido) || "") : "") + " " + (p.obs || ""), M.docs(D.config));
        return M.montar(m, D.config);
      };
      zap = el("button", { className: "sec", textContent: tipo === "docs" ? "WhatsApp: documentos" : "WhatsApp: baixa",
        title: fone ? "Abre a conversa com a mensagem pronta (e copia)" : "Sem telefone: só copia a mensagem" });
      zap.addEventListener("click", async () => {
        const t = texto();
        await copiar(t, fone ? null : zap);
        if (fone) abrirZap(M.linkWhats(fone, t));
      });
    }
    const pet = el("button", { className: "sec", textContent: "Petição", title: "Gerar petição com nome e processo" });
    pet.addEventListener("click", () => abrirPet({ nome: p.nome, processos: [p.processo].concat(a ? a.processos : []).filter(Boolean), assistida: a && a.assistida, tipo: p.tipo }));
    const del = el("button", { className: "icone", title: "Excluir a pendência", ariaLabel: "Excluir a pendência" }, ico("lixo"));
    del.addEventListener("click", async () => { if (confirm("Excluir esta pendência?")) { await mudarPecas((ps) => ps.filter((x) => x.id !== p.id)); renderKanban(); } });
    k.append(
      el("div", { className: "ktopo" }, el("b", { textContent: p.nome || "(sem nome)" }), del),
      el("div", { className: "kproc", textContent: (p.processo || "") + (p.data ? ` · ${p.origem === "execucao" || p.origem === "seeu" || p.origem === "sei" ? "enviado" : "atendido"} em ${A.brDeIso(p.data).slice(0, 5)}` : "") + (a && a.contato ? ` · ${a.contato}` : "") }),
      origemPend(p),
      el("div", { className: "klinha" }, peca, prazo),
      obs,
      el("div", { className: "kacoes sec2" }, pet, zap),
      el("div", { className: "kacoes" }, bEsq, bDir, el("span", { className: "espaco" }), arq, feita),
    );
    return k;
  }
  // de onde veio a pendência (o Quadro é um só para Atendimentos, Execução, SEEU e SEI) e o pedido já feito na Execução
  const ORIGEM = { execucao: "Execução", seeu: "Mesa do SEEU", sei: "SEI" };
  function origemPend(p) {
    const t = [ORIGEM[p.origem] ? ORIGEM[p.origem] + (p.base ? " · " + p.base : "") : ""].filter(Boolean);
    const ped = p.etiqueta === "pedido" ? el("span", { className: "kped", textContent: "✓ Pedido feito" + (p.pedidoEm ? " em " + A.brDeIso(p.pedidoEm).slice(0, 5) : "") }) : null;
    if (!t.length && !ped) return null;
    return el("div", { className: "korig" }, t.length ? el("span", { textContent: t[0] }) : null, ped);
  }
  function renderArquivo() {
    const limite = A.hojeISO(new Date(Date.now() - 60 * 864e5));
    const arq = D.pecas.filter((p) => (p.status === "feito" || p.status === "arquivado") && p.origem !== "fluxo" && (p.feitoEm || "") >= limite)
      .sort((a, b) => (b.feitoEm || "").localeCompare(a.feitoEm || ""));
    $("#nArq").textContent = arq.length ? `(${arq.length})` : "";
    $("#tabArq tbody").replaceChildren(...arq.map((p) => {
      const volta = el("button", { className: "icone", textContent: "↺", title: "Voltar para as pendências" });
      volta.addEventListener("click", async () => { await mudarPeca(p.id, { status: "pendente", feitoEm: "", coluna: p.coluna || "fazer" }); renderKanban(); });
      return el("tr", {}, el("td", { textContent: A.brDeIso(p.feitoEm) }), el("td", { textContent: p.nome || "" }), el("td", { textContent: p.processo || "" }),
        el("td", { textContent: p.tipo ? A.nomeTipo(p.tipo) : "—" }), el("td", { textContent: p.status === "feito" ? "feita (conta)" : "arquivada" }), el("td", {}, volta));
    }));
  }
  $("#buscaPend").addEventListener("input", renderKanban);
  $("#novaPend").addEventListener("click", async () => {
    const nome = prompt("Assistido:");
    if (nome === null) return;
    const proc = prompt("Processo (pode deixar em branco):", "") || "";
    await mudarPecas((ps) => { ps.push({ id: A.novoId(), tipo: "", processo: A.cnj(proc) || proc.trim(), nome: A.nomeProprio(nome.trim()), data: A.hojeISO(),
      status: "pendente", coluna: "fazer", prazo: "", obs: "", origem: "manual", atendimentoId: "", criadoEm: Date.now() }); return ps; });
    renderKanban();
  });

  // ---------- AGENDA (7.28): um calendário para o Quadro, a Mesa do SEEU e os prazos validados do SEI ----------
  const ORIG_AG = { quadro: ["Quadro", "q"], seeu: ["SEEU", "s"], sei: ["SEI", "i"] };
  let agMes = null;
  async function renderAgenda() {
    let itens = [];
    if (ext.apto) { try { itens = await self.ATD_APTO.ui("agenda"); } catch (e) { itens = []; } if (!Array.isArray(itens)) itens = []; }
    else itens = D.pecas.filter((p) => p.status === "pendente" && p.prazo).map((p) => ({ data: p.prazo, origem: "quadro", titulo: p.nome, processo: p.processo, id: p.id }));
    const hoje = A.hojeISO();
    if (!agMes) agMes = [Number(hoje.slice(0, 4)), Number(hoje.slice(5, 7)) - 1];
    const [ano, mes] = agMes, ini = new Date(ano, mes, 1), dias = new Date(ano, mes + 1, 0).getDate(), pad = (ini.getDay() + 6) % 7;
    $("#agMes").textContent = ini.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    const por = {};
    for (const x of itens) (por[x.data] = por[x.data] || []).push(x);
    const item = (x) => {
      const [rot, cl] = ORIG_AG[x.origem] || [x.origem, ""];
      const b = el("button", { className: "agIt ag-" + cl + (x.data < hoje ? " venc" : ""), type: "button", title: `${rot}: ${x.titulo} ${x.processo || ""}` },
        el("span", { className: "agOrig", textContent: (x.data < hoje ? "◆ " : "") + rot }), " " + (x.titulo || x.processo || ""));
      b.addEventListener("click", () => { if (x.origem === "quadro") mostrarAba("pend"); else if (ext.apto) self.ATD_APTO.ui("irPara", x.origem, x.id); });
      return b;
    };
    const cab = el("tr", {}, ...["seg", "ter", "qua", "qui", "sex", "sáb", "dom"].map((d) => el("th", { scope: "col", textContent: d })));
    const celulas = [...Array(pad)].map(() => el("td"));
    for (let d = 1; d <= dias; d++) {
      const k = `${ano}-${String(mes + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      celulas.push(el("td", { className: (k === hoje ? "hoje" : "") }, el("span", { className: "agDia", textContent: String(d) }), ...(por[k] || []).map(item)));
    }
    const linhas = [];
    for (let i = 0; i < celulas.length; i += 7) linhas.push(el("tr", {}, ...celulas.slice(i, i + 7)));
    $("#agCal").replaceChildren(el("thead", {}, cab), el("tbody", {}, ...linhas));
    const ate = A.hojeISO(new Date(Date.now() + 30 * 864e5));
    const prox = itens.filter((x) => x.data <= ate);
    $("#agLista").replaceChildren(...(prox.length ? prox.map((x) => el("li", {}, el("b", { textContent: A.brDeIso(x.data) + " " }), item(x))) : [el("li", { className: "vazio", textContent: "Nada nos próximos 30 dias." })]));
  }
  $("#agAnt").addEventListener("click", () => { agMes = agMes[1] === 0 ? [agMes[0] - 1, 11] : [agMes[0], agMes[1] - 1]; renderAgenda(); });
  $("#agProx").addEventListener("click", () => { agMes = agMes[1] === 11 ? [agMes[0] + 1, 0] : [agMes[0], agMes[1] + 1]; renderAgenda(); });

  // ---------- PETIÇÕES ----------
  // palavras do nome do modelo que combinam com cada peça (só para pôr no topo da lista)
  const MODELO_PECA = { ST: /sa[ií]da/i, PROG: /progress/i, LC: /\bLC\b/i, INDULTO: /indulto/i, COMUT: /comuta/i, PRESC: /prescri/i, EXT: /extin/i,
    MONIT: /tornozeleira|monitora/i, DOMIC: /domiciliar/i, REMICAO: /remi[cç]/i, DETRACAO: /detra/i, PRD: /restritiva|PRD/i, JUST: /justifica/i,
    CIENCIA: /ci[eê]ncia/i, AGEX: /agravo/i, HC: /\bHC\b/i, ED: /\bED\b/i, PP: /provid[eê]ncia/i, MANIF: /n[aã]o homologa|cota|reiterar/i };
  let petCtx = null;
  const formatoDe = (m) => (D.config.formatos && D.config.formatos[m.id]) || m.formato;
  async function abrirPet(ctx) {
    petCtx = ctx;
    $("#petNome").value = ctx.nome || "";
    const procs = [...new Set(ctx.processos || [])];
    $("#petProc").value = procs[0] || "";
    $("#petProcs").replaceChildren(...procs.map((p) => el("option", { value: p })));
    $("#petFem").checked = !!ctx.assistida;
    $("#petBusca").value = "";
    $("#petMsg").hidden = true;
    $("#petFundo").hidden = false;
    await listarModelos();
    $("#petBusca").focus();
  }
  async function listarModelos() {
    let cat = [];
    try { cat = await self.PETS.catalogo(); } catch (e) { return aviso("#petMsg", "Não achei os modelos da extensão: " + (e.message || e)); }
    const busca = A.norm($("#petBusca").value);
    const re = petCtx && petCtx.tipo && MODELO_PECA[petCtx.tipo];
    const itens = cat.filter((m) => !busca || A.norm(m.nome + " " + m.grupo).includes(busca))
      .sort((x, y) => (re ? (re.test(y.nome) - re.test(x.nome)) : 0) || (formatoDe(y) === "pdf") - (formatoDe(x) === "pdf") || x.grupo.localeCompare(y.grupo) || x.nome.localeCompare(y.nome, "pt-BR"));
    $("#petLista").replaceChildren(...itens.map((m) => {
      const f = formatoDe(m);
      const bPdf = el("button", { textContent: "PDF" });
      const bDoc = el("button", { className: f === "pdf" ? "sec" : "", textContent: "Word" });
      bPdf.addEventListener("click", () => gerarPet(m, "pdf"));
      bDoc.addEventListener("click", () => gerarPet(m, "docx"));
      const troca = el("button", { className: "icone mini", textContent: f === "pdf" ? "só Word" : "liberar PDF",
        title: f === "pdf" ? "Este modelo precisa de dados do caso: tirar o PDF" : "Este modelo não pede nada além de nome, processo e data: liberar PDF" });
      troca.addEventListener("click", async () => {
        D.config.formatos = Object.assign({}, D.config.formatos, { [m.id]: f === "pdf" ? "docx" : "pdf" });
        await salvarConfig(); listarModelos();
      });
      return el("li", { className: re && re.test(m.nome) ? "sug" : "" },
        el("span", { className: "nm" }, m.nome.replace(/^1\.\s*/, ""), el("small", { textContent: (m.grupo === "Fluxo" ? "Modelos Fluxo" : "3. Modelos") + (f === "pdf" ? " · pronto" : " · revisar no Word") })),
        troca, f === "pdf" ? bPdf : null, bDoc);
    }));
  }
  async function gerarPet(m, formato) {
    const campos = { nome: $("#petNome").value.trim(), processo: A.cnj($("#petProc").value) || $("#petProc").value.trim(), genero: $("#petFem").checked ? "a" : "o" };
    if (!campos.processo) return aviso("#petMsg", "Informe o nº do processo.");
    aviso("#petMsg", "Gerando…", 60000);
    try {
      const r = await self.PETS.gerar(m, campos, formato);
      const nome = self.PETS.nomeArquivo(m.nome, campos.processo, formato);
      const onde = await salvarPeticao(new Blob([r.bytes], { type: r.tipo }), nome);
      const falta = [!r.info.processo && "nº de exemplo não achado", m.grupo !== "Fluxo" && !r.info.nome && "nome de exemplo não achado"].filter(Boolean);
      aviso("#petMsg", `Salvo: ${onde}` + (formato === "docx" ? " · revise os dados do caso de exemplo" : "") + (falta.length ? ` · atenção: ${falta.join(", ")} — confira` : ""), 20000);
    } catch (e) {
      console.error(e);
      aviso("#petMsg", "Não foi possível gerar: " + (e.message || e), 20000);
    }
  }
  async function salvarPeticao(blob, nome) {
    if (ext.apto) return (await self.ATD_APTO.salvar(blob, nome, "peticao")) || "não salvo (cancelado)";
    let pasta = null;
    try { pasta = await kv("pastaPet"); } catch (e) { pasta = null; }
    if (pasta) {
      try {
        let perm = await pasta.queryPermission({ mode: "readwrite" });
        if (perm !== "granted") perm = await pasta.requestPermission({ mode: "readwrite" });
        if (perm === "granted") {
          const w = await (await pasta.getFileHandle(nome, { create: true })).createWritable();
          await w.write(blob); await w.close();
          return `${pasta.name}\\${nome}`;
        }
      } catch (e) { console.warn(e); }
    }
    baixar(blob, nome);
    return `Downloads\\${nome}`;
  }
  $("#petBusca").addEventListener("input", listarModelos);
  function fecharPet() {
    $("#petFundo").hidden = true;
    if (ext.apto && document.body.dataset.grupo === "pet") self.ATD_APTO.ui("petFechada");
  }
  $("#petFechar").addEventListener("click", fecharPet);
  $("#petFundo").addEventListener("click", (e) => { if (e.target.id === "petFundo") fecharPet(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#petFundo").hidden) fecharPet(); });
  // o SEEU abre o mesmo diálogo: nome, processo e a peça sugerida (os modelos dela vão para o topo)
  window.__atdPet = async (ctx) => {
    if (!$("#petFundo").hidden) return; // já aberto (o APTO repete o pedido até a moldura responder)
    await abrirPet(Object.assign({ nome: "", processos: [], assistida: false, tipo: "" }, ctx || {}));
    if (ext.apto) self.ATD_APTO.ui("petAberta");
  };

  // ---------- FLUXO ----------
  const diaFluxo = () => $("#diaFluxo").value || A.hojeISO();
  function renderFluxo() {
    const dia = diaFluxo();
    const cont = contagens(dia.slice(0, 7))[Number(dia.slice(8))] || {};
    $("#fluxo").replaceChildren(...A.COLUNAS.map(([k, rot]) => {
      const meus = D.pecas.filter((p) => p.origem === "fluxo" && p.tipo === k && p.feitoEm === dia);
      const ajuste = D.ajustes[`${dia}|${k}`] || 0;
      const total = (cont[k] || 0) + ajuste;
      const menos = el("button", { className: "menos", title: "Desfazer o último lançamento", ariaLabel: `Desfazer 1 em ${rot}`, disabled: !meus.length }, ico("menos"));
      const mais = el("button", { className: "mais", title: "Lançar 1", ariaLabel: `Lançar 1 em ${rot}` }, ico("mais"));
      menos.addEventListener("click", async () => {
        const ult = meus.sort((a, b) => (b.criadoEm || 0) - (a.criadoEm || 0))[0];
        if (ult) { await mudarPecas((ps) => ps.filter((x) => x.id !== ult.id)); renderFluxo(); }
      });
      mais.addEventListener("click", async () => {
        await mudarPecas((ps) => { ps.push({ id: A.novoId(), tipo: k, processo: "", nome: "", data: dia, status: "feito", feitoEm: dia, origem: "fluxo", atendimentoId: "", criadoEm: Date.now() }); return ps; });
        renderFluxo();
      });
      return el("div", { className: "fcard" + (meus.length ? " tem" : "") },
        el("div", { className: "frotBox" }, el("div", { className: "frot", textContent: rot }),
          el("div", { className: "ftot", textContent: total !== meus.length ? `No mês: ${total}` : "" })),
        el("div", { className: "fbot" }, menos, el("span", { className: "fnum", textContent: String(meus.length) }), mais));
    }));
    const n = D.pecas.filter((p) => p.origem === "fluxo" && p.feitoEm === dia).length;
    $("#totFluxo").textContent = n ? `${n} lançada(s) no fluxo neste dia` : "Nada lançado no fluxo neste dia";
  }
  $("#diaFluxo").value = A.hojeISO();
  $("#diaFluxo").addEventListener("change", renderFluxo);
  $("#hojeFluxo").addEventListener("click", () => { $("#diaFluxo").value = A.hojeISO(); renderFluxo(); });

  // ---------- CONTROLE DO MÊS ----------
  // pedidos e ofícios registrados na Execução (base aberta no APTO), se a pessoa escolher somar: [{data: "dd/mm/aaaa", coluna}]
  let provExec = null;
  async function carregarProvExec() {
    if (!ext.apto) return;
    try { const r = await self.ATD_APTO.ui("providenciasExecucao"); provExec = r && r.itens ? r : { itens: [], base: "" }; }
    catch (e) { provExec = { itens: [], base: "" }; }
  }
  function contagens(mes) {
    const c = {};
    const soma = (dia, k) => { (c[dia] = c[dia] || {})[k] = (c[dia][k] || 0) + 1; };
    if (D.config.somarExecucao && provExec) for (const p of provExec.itens) { const iso = A.isoDeBr(p.data); if (iso.startsWith(mes) && p.coluna) soma(Number(iso.slice(8)), p.coluna); }
    for (const a of D.atendimentos) if (a.data.startsWith(mes) && realizado(a)) soma(Number(a.data.slice(8)), "ATEND");
    for (const p of D.pecas) if (p.status === "feito" && p.tipo && (p.feitoEm || "").startsWith(mes)) soma(Number(p.feitoEm.slice(8)), p.tipo);
    return c;
  }
  function renderControle() {
    if (ext.apto && $("#somarExec")) {
      $("#somarExecBox").hidden = false;
      $("#somarExec").checked = !!D.config.somarExecucao;
      if (D.config.somarExecucao && !provExec) { carregarProvExec().then(renderControle); return; }
      $("#somarExecInfo").textContent = D.config.somarExecucao && provExec
        ? (provExec.base ? `${provExec.itens.length} registrado(s) na base "${provExec.base}" entram na tabela.` : "Nenhuma base aberta em Execução: nada a somar.") : "";
    }
    const mes = $("#mes").value || A.hojeISO().slice(0, 7);
    const [ano, m] = mes.split("-");
    const c = contagens(mes);
    const ajuste = (dia, k) => D.ajustes[`${mes}-${A.pad(dia)}|${k}`] || 0;
    const auto = (dia, k) => (c[dia] && c[dia][k]) || 0;
    const valor = (dia, k) => auto(dia, k) + ajuste(dia, k);
    const tab = el("table", { className: "ctrl" });
    tab.innerHTML = `<thead><tr><th class="dia">Dia</th>${A.COLUNAS.map(([, r]) => `<th><div>${r}</div></th>`).join("")}</tr></thead>`;
    const tb = el("tbody");
    const totais = {};
    for (let dia = 1; dia <= 31; dia++) {
      const tr = el("tr", {}, el("td", { className: "dia", textContent: String(dia) }));
      for (const [k] of A.COLUNAS) {
        const v = valor(dia, k);
        totais[k] = (totais[k] || 0) + v;
        const inp = el("input", { value: v || "", inputMode: "numeric", title: ajuste(dia, k) ? `Corrigido à mão (automático: ${auto(dia, k)})` : "" });
        inp.addEventListener("change", async () => {
          const novo = Math.max(0, Number(inp.value) || 0);
          const d = await A.ler();
          const ch = `${mes}-${A.pad(dia)}|${k}`;
          if (novo - auto(dia, k)) d.ajustes[ch] = novo - auto(dia, k); else delete d.ajustes[ch];
          D.ajustes = d.ajustes;
          await A.gravar({ ajustes: d.ajustes });
          renderControle();
        });
        tr.append(el("td", { className: ajuste(dia, k) ? "ajustada" : "" }, inp));
      }
      tb.append(tr);
    }
    tab.append(tb);
    const tf = el("tfoot");
    tf.innerHTML = `<tr><td class="dia">TOTAL</td>${A.COLUNAS.map(([k]) => `<td>${totais[k] || ""}</td>`).join("")}</tr>`;
    tab.append(tf);
    const tit = el("div", { className: "ctrl-titulo" });
    tit.innerHTML = `<b>CONTROLE - 3ª DPEP</b><span>Mês/Ano: ${m}/${ano}</span>`;
    $("#controle").replaceChildren(tit, tab);
    $("#controle")._csv = () => {
      const linhas = [["Dia", ...A.COLUNAS.map((x) => x[1])]];
      for (let dia = 1; dia <= 31; dia++) linhas.push([dia, ...A.COLUNAS.map(([k]) => valor(dia, k) || "")]);
      linhas.push(["TOTAL", ...A.COLUNAS.map(([k]) => totais[k] || "")]);
      return "﻿" + linhas.map((l) => l.join(";")).join("\r\n");
    };
  }
  if ($("#somarExec")) $("#somarExec").addEventListener("change", async (e) => {
    D.config.somarExecucao = e.target.checked; provExec = null; await salvarConfig(); renderControle();
  });
  $("#mes").value = A.hojeISO().slice(0, 7);
  $("#mes").addEventListener("change", renderControle);
  $("#imprimirBtn").addEventListener("click", () => window.print());
  $("#csvBtn").addEventListener("click", () => baixar(new Blob([$("#controle")._csv()], { type: "text/csv;charset=utf-8" }), `Controle ${$("#mes").value}.csv`));

  // ---------- MODELOS E BACKUP ----------
  async function salvarModelos() { await A.gravar({ modelos: D.modelos }); }
  function renderCfg() {
    $("#nModelos").textContent = String(D.modelos.length);
    $("#modelos").replaceChildren(...D.modelos.map((m, i) => {
      const t = el("input", { value: m.titulo, ariaLabel: "Nome na lista" });
      const x = el("textarea", { value: m.texto, rows: 2, ariaLabel: "Texto inserido" });
      const del = el("button", { className: "icone", title: "Excluir esta frase", ariaLabel: "Excluir esta frase" }, ico("lixo"));
      t.addEventListener("change", () => { m.titulo = t.value; salvarModelos(); });
      x.addEventListener("change", () => { m.texto = x.value; salvarModelos(); });
      del.addEventListener("click", () => { D.modelos.splice(i, 1); salvarModelos(); renderCfg(); });
      return el("div", { className: "modelo" }, t, x, del);
    }));
    const docs = M.docs(D.config);
    $("#docsCfg").replaceChildren(...docs.map((d, i) => {
      const x = el("textarea", { value: d.texto, rows: 2, ariaLabel: "Texto do documento" });
      const g = el("input", { value: d.gatilho || "", placeholder: "ex.: holerite|parcel", ariaLabel: "Marca sozinho quando o texto tiver" });
      const del = el("button", { className: "icone", title: "Excluir este documento", ariaLabel: "Excluir este documento" }, ico("lixo"));
      const salvarDocs = () => { D.config.docs = docs; salvarConfig(); };
      x.addEventListener("change", () => { d.texto = x.value; salvarDocs(); });
      g.addEventListener("change", () => { d.gatilho = g.value; salvarDocs(); });
      del.addEventListener("click", () => { docs.splice(i, 1); salvarDocs(); renderCfg(); });
      return el("div", { className: "modelo docItem" }, x, g, del);
    }));
    const T = M.textos(D.config);
    $("#msgDocsIni").value = T.docsIni; $("#msgDocsFim").value = T.docsFim; $("#msgPadrao").value = T.padrao; $("#msgBaixa").value = T.baixa;
    if (ext.apto) { pastasApto(); return; }
    kv("pasta").then((h) => {
      $("#pastaInfo").textContent = h ? `O relatório vai para "${h.name}\\<mês>\\DD.MM.docx" (a pasta do mês é achada pelo nome, ex.: "8. Novembro", ou criada).`
        : self.showDirectoryPicker ? "Hoje vai para Downloads. Escolha a pasta \"2. Atendimentos\" da rede para gravar direto na pasta do mês."
        : "Este navegador (Firefox) não deixa escolher pasta: o relatório vai para Downloads.";
      $("#pastaBtn").hidden = !self.showDirectoryPicker;
      $("#pastaLimpar").hidden = !h;
    }).catch(() => { $("#pastaInfo").textContent = "Vai para Downloads."; });
    kv("pastaPet").then((h) => {
      $("#pastaPetInfo").textContent = h ? `As petições vão para "${h.name}" (nome: "1. Ciência 6003870.pdf").`
        : self.showDirectoryPicker ? "Hoje vão para Downloads. Escolha uma pasta para gravar direto nela." : "Este navegador (Firefox) não deixa escolher pasta: vão para Downloads.";
      $("#pastaPetBtn").hidden = !self.showDirectoryPicker;
      $("#pastaPetLimpar").hidden = !h;
    }).catch(() => {});
  }
  // no APTO, as pastas são escolhidas pelo programa (valem para este computador)
  async function pastasApto() {
    let p = {};
    try { p = (await self.ATD_APTO.pedir("atd_pastas")) || {}; } catch (e) { p = {}; }
    const r = p.relatorio || {}, q = p.peticoes || {};
    $("#pastaInfo").textContent = r.caminho ? `O relatório vai para "${r.caminho}\\<mês>\\DD.MM.docx" (a pasta do mês é achada pelo nome, ex.: "8. Novembro", ou criada).`
      : 'Sem pasta escolhida: o APTO pergunta onde salvar. Escolha a pasta "2. Atendimentos" da rede para gravar direto na pasta do mês.';
    $("#pastaPetInfo").textContent = q.caminho ? `As petições vão para "${q.caminho}" (nome: "1. Ciência 6003870.pdf").` : "Sem pasta escolhida: o APTO pergunta onde salvar.";
    $("#pastaBtn").hidden = false; $("#pastaPetBtn").hidden = false;
    $("#pastaLimpar").hidden = !r.caminho; $("#pastaPetLimpar").hidden = !q.caminho;
    $("#pastaLimpar").textContent = "Perguntar onde salvar"; $("#pastaPetLimpar").textContent = "Perguntar onde salvar";
  }
  if (ext.apto) {
    const pastaApto = (fn, tipo) => async (e) => { e.stopImmediatePropagation(); try { await self.ATD_APTO.pedir(fn, tipo); } catch (err) { aviso("#msgCfg", String(err.message || err)); } pastasApto(); };
    $("#pastaBtn").addEventListener("click", pastaApto("atd_escolher_pasta", "relatorio"), true);
    $("#pastaPetBtn").addEventListener("click", pastaApto("atd_escolher_pasta", "peticoes"), true);
    $("#pastaLimpar").addEventListener("click", pastaApto("atd_limpar_pasta", "relatorio"), true);
    $("#pastaPetLimpar").addEventListener("click", pastaApto("atd_limpar_pasta", "peticoes"), true);
  }
  $("#pastaPetBtn").addEventListener("click", async () => {
    try { await kv("pastaPet", await self.showDirectoryPicker({ id: "apto-peticoes-atd", mode: "readwrite" })); renderCfg(); }
    catch (e) { if (e.name !== "AbortError") aviso("#msgCfg", "Não deu para usar essa pasta: " + (e.message || e)); }
  });
  $("#pastaPetLimpar").addEventListener("click", async () => { await kv("pastaPet", null); renderCfg(); });
  [["#msgDocsIni", "docsIni"], ["#msgDocsFim", "docsFim"], ["#msgPadrao", "padrao"], ["#msgBaixa", "baixa"]].forEach(([s, k]) =>
    $(s).addEventListener("change", (e) => { D.config.msgs = Object.assign({}, D.config.msgs, { [k]: e.target.value }); salvarConfig(); }));
  $("#msgRestaurar").addEventListener("click", () => { if (confirm("Voltar os quatro textos das mensagens ao original?")) { delete D.config.msgs; salvarConfig(); renderCfg(); } });
  $("#novoModelo").addEventListener("click", () => { D.modelos.push({ titulo: "Nova frase", texto: "" }); salvarModelos(); renderCfg(); });
  $("#novoDoc").addEventListener("click", () => { const docs = M.docs(D.config); docs.push({ id: A.novoId(), texto: "Novo documento", gatilho: "" }); D.config.docs = docs; salvarConfig(); renderCfg(); });
  $("#pastaBtn").addEventListener("click", async () => {
    try { await kv("pasta", await self.showDirectoryPicker({ id: "apto-atendimentos", mode: "readwrite" })); renderCfg(); }
    catch (e) { if (e.name !== "AbortError") aviso("#msgCfg", "Não deu para usar essa pasta: " + (e.message || e)); }
  });
  $("#pastaLimpar").addEventListener("click", async () => { await kv("pasta", null); renderCfg(); });
  $("#exportar").addEventListener("click", async () => {
    const d = await A.ler();
    baixar(new Blob([JSON.stringify(Object.assign({ app: "APTO Atendimentos", exportadoEm: new Date().toISOString() }, d), null, 1)], { type: "application/json" }),
      `APTO Atendimentos ${A.hojeISO()}.json`);
  });
  $("#importar").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    try {
      const x = JSON.parse(await f.text());
      if (x.app !== "APTO Atendimentos") throw new Error("o arquivo não é um backup do APTO Atendimentos");
      const d = await A.ler();
      const junta = (atual, novos) => { const ids = new Set(atual.map((y) => y.id)); return atual.concat((novos || []).filter((y) => y && y.id && !ids.has(y.id))); };
      const antes = d.atendimentos.length + d.pecas.length;
      d.atendimentos = junta(d.atendimentos, x.atendimentos);
      d.pecas = junta(d.pecas, x.pecas);
      d.ajustes = Object.assign({}, x.ajustes || {}, d.ajustes);
      await A.gravar({ atendimentos: d.atendimentos, pecas: d.pecas, ajustes: d.ajustes });
      Object.assign(D, d);
      aviso("#msgCfg", `Importado: ${d.atendimentos.length + d.pecas.length - antes} registro(s) novo(s).`);
    } catch (err) { aviso("#msgCfg", "Não deu para importar: " + (err.message || err)); }
  });

  // ---------- atualização ao vivo ----------
  let pendente = false;
  function atualizarTela() {
    const ativo = document.activeElement;
    // não redesenha enquanto você digita; espera sair do campo
    if (ativo && ativo.closest && ativo.closest("main") && /INPUT|TEXTAREA|SELECT/.test(ativo.tagName) && ativo.type !== "date") { pendente = true; return; }
    // nem com uma mensagem de WhatsApp aberta
    if (abaAtual() === "dia" && $$(".zap[open]").length) { pendente = true; contarPend(); return; }
    pendente = false;
    desenharAba(abaAtual());
  }
  document.addEventListener("focusout", () => setTimeout(() => { if (pendente) atualizarTela(); }, 50));
  document.addEventListener("toggle", () => { if (pendente) setTimeout(atualizarTela, 50); }, true);
  ext.storage.onChanged.addListener(async (mud, area) => {
    if (area !== "local") return;
    const d = await A.ler();
    D = Object.assign(D, d, { modelos: D.modelos, config: D.config });
    if (mud.atendimentos || mud.ajustes || mud.pecas) atualizarTela();
  });
  ext.runtime.onMessage.addListener((msg, _s, responder) => {
    if (msg && msg.tipo === "painelAberto") {
      ext.tabs.getCurrent().then((t) => responder(t ? { tabId: t.id, windowId: t.windowId } : null));
      return true;
    }
  });

  // ---------- dentro do APTO: cada função mostra as suas abas ----------
  const GRUPOS = { atend: ["dia", "fluxo", "cfg"], quadro: ["pend", "agenda"], rel: ["ctrl"], pet: [] };
  window.__atdAba = (grupo, aba) => {
    const abas = GRUPOS[grupo] || GRUPOS.atend;
    document.body.dataset.grupo = grupo;
    if (grupo === "pet") { $(".topo").hidden = true; $$(".aba").forEach((x) => (x.hidden = true)); return; } // só o diálogo de petição (SEEU)
    if (grupo === "rel") provExec = null; // a base aberta na Execução pode ter mudado
    $$(".abas button").forEach((b) => { b.hidden = !abas.includes(b.dataset.aba); });
    $(".topo").hidden = abas.length < 2;
    const alvo = abas.includes(aba) ? aba : abas.includes(abaAtual()) ? abaAtual() : abas[0];
    mostrarAba(alvo);
  };
  // aba do SAP aberta (com a extensão) ou não
  window.__atdSap = (est) => {
    const e = $("#sapStatus");
    if (!e || !est) return;
    const lendo = !!(est.leitura && est.leitura.lendo && Date.now() / 1000 - est.leitura.quando < 120);
    e.hidden = false;
    e.className = "sapStatus " + (est.aberto ? "on" : "off");
    e.querySelector(".sapTxt").textContent = est.aberto ? (lendo ? est.leitura.msg || "Lendo a fila do SAP…" : "SAP aberto") : "SAP não detectado";
    e.title = est.aberto ? "A aba do SAP está aberta com a extensão do APTO: Chamar, Ver no SAP e Ler a fila funcionam daqui."
      : "Abra o SAP na tela de atendimento (Assistidos em Espera), com a extensão do APTO instalada, para ler a fila e chamar daqui.";
    if (!$("#lerSapBtn").hasAttribute("aria-busy")) $("#lerSapBtn").disabled = !est.aberto || lendo;
  };
  if ($("#relDiaBtn")) $("#relDiaBtn").addEventListener("click", () => {
    $("#dia").value = $("#diaRel").value || A.hojeISO();
    $("#relatorioBtn").click();
    const espia = setInterval(() => { const m = $("#msgDia"); if (!m.hidden && m.textContent) { aviso("#msgRel", m.textContent, 15000); clearInterval(espia); } }, 300);
    setTimeout(() => clearInterval(espia), 60000);
  });
  if ($("#relExecBtn")) $("#relExecBtn").addEventListener("click", () => self.ATD_APTO.ui("relatoriosExecucao"));

  // ---------- início ----------
  (async function () {
    D = await A.ler();
    if (!D.modelos) { D.modelos = MODELOS_PADRAO.map((m) => Object.assign({}, m)); await salvarModelos(); }
    // frases novas da versão 1.1 entram junto das que você já tem (sem duplicar nem apagar)
    if ((D.config.modelosVersao || 1) < 2) {
      const tem = new Set(D.modelos.map((m) => A.norm(m.texto)));
      for (const m of MODELOS_PADRAO) if (!tem.has(A.norm(m.texto))) D.modelos.push(Object.assign({}, m));
      D.config.modelosVersao = 2;
      await salvarModelos(); await salvarConfig();
    }
    $("#dia").value = A.hojeISO();
    $("#ordemDia").value = D.config.ordemDia || "hora";
    let aba = "dia";
    try { aba = sessionStorage.getItem("aba") || "dia"; } catch (e) { /* sem importância */ }
    if (ext.apto) {
      $$(".semApto").forEach((x) => (x.hidden = true)); // no APTO: Importar/Exportar únicos, na barra do APTO
      if ($("#diaRel")) $("#diaRel").value = A.hojeISO();
      window.__atdAba(location.hash.slice(1) || "atend", aba);
      if (self.ATD_APTO.sap()) window.__atdSap(self.ATD_APTO.sap());
    } else mostrarAba(aba);
  })();
})();
