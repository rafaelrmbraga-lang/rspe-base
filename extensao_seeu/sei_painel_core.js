// APTO - Painel do SEI: o motor (funções puras, sem DOM e sem rede). Testado no node (extensao_seeu_testes/teste_sei_painel.mjs).
// Recebe os processos que o sei_painel.js leu da tela do Controle de Processos e calcula o que o painel mostra: prazo de cada
// processo, categoria (ícone e cor), urgência, filtros, busca rápida, contagens e a planilha. Nada aqui fala com o SEI.
(function (raiz) {
  "use strict";

  const DIA = 86400000;

  // texto comparável: sem acento, sem maiúscula, pontuação vira espaço (12.345 acha 12345)
  function norm(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[./\-_]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }

  // argumentos de infraTooltipMostrar('texto','título') (aspas simples ou duplas, com \' escapado)
  function argsDica(s) {
    const r = [];
    for (const m of String(s || "").matchAll(/'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"/g)) {
      r.push((m[1] ?? m[2]).replace(/\\(.)/g, (x, c) => ({ n: "\n", t: " " }[c] ?? c)));
    }
    return r;
  }

  function dataBR(d, m, a) {
    let ano = Number(a);
    if (ano < 100) ano += 2000;
    const dt = new Date(ano, Number(m) - 1, Number(d));
    return dt.getFullYear() === ano && dt.getMonth() === Number(m) - 1 && dt.getDate() === Number(d) ? dt : null;
  }
  const meiaNoite = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diasEntre = (a, b) => Math.round((meiaNoite(b) - meiaNoite(a)) / DIA);
  const fmt = (d) => `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;

  // Prazo do processo, a partir dos textos da linha (marcadores, anotação, retorno programado, controle de prazo, especificação):
  //  - "até 20/11/2026", "prazo 20/11/2026", "vence 20/11", "retorno programado ... 20/11/2026" -> vencimento (quanto falta);
  //  - só uma data num marcador -> "parado desde" (há quantos dias).
  // Vale o vencimento mais próximo; sem vencimento, a data mais antiga dos marcadores.
  const RE_VENCE = /\b(?:ate|prazo|vence|vencimento|venc|retorno|devolver|responder|entregar)\b[^0-9]{0,24}(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/gi;
  const RE_DATA = /\b(\d{1,2})\/(\d{1,2})\/(\d{2,4})\b/g;
  function prazoDe(fontes, hoje, cfg) {
    hoje = hoje || new Date();
    const alerta = (cfg && cfg.alertaDias) ?? 5;
    const critico = (cfg && cfg.criticoDias) ?? 2;
    let vence = null;
    let desde = null;
    for (const f of fontes || []) {
      const t = String(f.texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
      const ehPrazo = f.origem === "prazo" || f.origem === "retorno";
      for (const m of t.matchAll(RE_VENCE)) {
        const d = dataBR(m[1], m[2], m[3] || hoje.getFullYear());
        if (d && (!vence || d < vence.data)) vence = { data: d, origem: f.origem };
      }
      if (ehPrazo && !vence) {
        const m = RE_DATA.exec(t); RE_DATA.lastIndex = 0;
        const d = m && dataBR(m[1], m[2], m[3]);
        if (d) vence = { data: d, origem: f.origem };
      }
      if (f.origem === "marcador") {
        for (const m of t.matchAll(RE_DATA)) {
          const d = dataBR(m[1], m[2], m[3]);
          if (d && d <= hoje && (!desde || d < desde.data)) desde = { data: d, origem: f.origem };
        }
      }
    }
    if (vence) {
      const dias = diasEntre(hoje, vence.data);
      const nivel = dias < 0 ? "vencido" : dias <= critico ? "critico" : dias <= alerta ? "alerta" : "ok";
      const rotulo = dias < 0 ? `vencido há ${-dias} d` : dias === 0 ? "vence hoje" : dias === 1 ? "vence amanhã" : `vence em ${dias} d`;
      return { tipo: "vence", data: fmt(vence.data), dias, nivel, rotulo, origem: vence.origem };
    }
    if (desde) {
      const dias = diasEntre(desde.data, hoje);
      return { tipo: "desde", data: fmt(desde.data), dias, nivel: "parado", rotulo: dias === 0 ? "desde hoje" : `há ${dias} d`, origem: desde.origem };
    }
    return null;
  }

  // Categorias (ícone e cor do processo). As regras da pessoa (palavra -> cor) vêm antes das do APTO.
  const CATEGORIAS = [
    { id: "execucao", rotulo: "Execução penal", icone: "balanca", cor: "#1D5A3B",
      palavras: ["execucao penal", "execucao", "progressao", "livramento", "indulto", "comutacao", "remicao", "detracao", "unificacao", "seeu", "pena", "saida temporaria"] },
    { id: "prisional", rotulo: "Unidade prisional", icone: "predio", cor: "#7A4E12",
      palavras: ["prisional", "presidio", "penitenciaria", "inspecao", "estabelecimento penal", "cadeia", "epmf", "agepen", "carcer"] },
    { id: "atendimento", rotulo: "Atendimento", icone: "pessoa", cor: "#2B5797",
      palavras: ["atendimento", "assistido", "requerimento", "solicitacao", "familiar", "visita", "pedido de providencia"] },
    { id: "oficio", rotulo: "Comunicação", icone: "envelope", cor: "#6B3FA0",
      palavras: ["oficio", "memorando", "comunicacao", "correspondencia", "notificacao", "intimacao", "circular", "e-mail", "email"] },
    { id: "administrativo", rotulo: "Administrativo", icone: "pasta", cor: "#5C6660",
      palavras: ["administra", "pessoal", "ferias", "diaria", "compra", "contrat", "licitac", "patrimonio", "orcament", "folha"] },
  ];
  const GERAL = { id: "geral", rotulo: "Outros", icone: "documento", cor: "#8E958F" };

  function categoria(proc, regras) {
    const alvo = " " + norm([proc.tipo, proc.especificacao].join(" ")) + " ";
    for (const r of regras || []) {
      const p = norm(r.palavra);
      if (p && alvo.includes(p)) return { id: "regra:" + p, rotulo: r.rotulo || r.palavra, icone: r.icone || "etiqueta", cor: r.cor || "#B42318", regra: true };
    }
    // o tipo do processo decide; a especificação só quando o tipo não diz nada (um Ofício que cita a AGEPEN continua Ofício)
    for (const texto of [" " + norm(proc.tipo) + " ", alvo]) for (const c of CATEGORIAS) if (c.palavras.some((p) => texto.includes(norm(p)))) return c;
    return GERAL;
  }

  // "palavra: #cor" (ou "palavra = cor"), uma por linha -> regras; linhas inválidas são ignoradas
  function regrasDoTexto(txt) {
    const r = [];
    for (const l of String(txt || "").split(/\r?\n/)) {
      const m = /^\s*([^:=#]+?)\s*[:=]\s*(#[0-9a-f]{3}(?:[0-9a-f]{3})?|[a-z]+)\s*$/i.exec(l);
      if (m) r.push({ palavra: m[1], cor: m[2] });
    }
    return r;
  }

  const urgente = (proc) => /\burgent/i.test(norm([proc.especificacao, proc.anotacao, ...(proc.marcadores || []).map((m) => m.nome + " " + m.texto)].join(" ")));

  // tudo o que a busca rápida olha (número, tipo, especificação, atribuição, interessados, marcadores, anotação, dicas)
  function textoBusca(p) {
    return norm([p.numero, String(p.numero || "").replace(/\D/g, ""), p.tipo, p.especificacao, p.atribuicao, (p.interessados || []).join(" "),
      (p.marcadores || []).map((m) => m.nome + " " + m.texto).join(" "), p.anotacao, (p.dicas || []).join(" "),
      p.prazo ? p.prazo.rotulo : "", p.categoria ? p.categoria.rotulo : ""].join(" "));
  }

  // completa cada processo com prazo, categoria e urgência
  function enriquecer(procs, opc) {
    const o = opc || {};
    return procs.map((p) => {
      const fontes = [...(p.marcadores || []).map((m) => ({ texto: m.nome + " " + m.texto, origem: "marcador" })),
        { texto: p.anotacao, origem: "anotacao" }, ...(p.prazos || []).map((t) => ({ texto: t, origem: "prazo" })),
        ...(p.retornos || []).map((t) => ({ texto: t, origem: "retorno" })), { texto: p.especificacao, origem: "especificacao" }];
      const q = { ...p, prazo: prazoDe(fontes, o.hoje, o), categoria: categoria(p, o.regras), urgente: urgente(p), monitorado: !!(o.monitorados && o.monitorados[p.numero]) };
      q.busca = textoBusca(q);
      return q;
    });
  }

  // Filtros do painel (um de cada vez, como um clique num cartão ou numa barra) + busca rápida (3+ caracteres, todas as palavras)
  const FILTROS = {
    todos: () => true,
    naoVisualizados: (p) => p.naoVisualizado,
    vencidos: (p) => p.prazo && p.prazo.nivel === "vencido",
    vencendo: (p) => p.prazo && (p.prazo.nivel === "critico" || p.prazo.nivel === "alerta"),
    comPrazo: (p) => p.prazo && p.prazo.tipo === "vence",
    urgentes: (p) => p.urgente,
    semAtribuicao: (p) => !p.atribuicao,
    monitorados: (p) => p.monitorado,
    comAnotacao: (p) => !!p.anotacao,
  };
  function passa(p, filtro, busca) {
    if (filtro) {
      if (filtro.campo === "tipo" && p.tipo !== filtro.valor) return false;
      if (filtro.campo === "categoria" && p.categoria.id !== filtro.valor) return false;
      if (filtro.campo === "atribuicao" && (p.atribuicao || "") !== filtro.valor) return false;
      if (filtro.campo === "marcador" && !(p.marcadores || []).some((m) => m.nome === filtro.valor)) return false;
      if (filtro.campo === "rapido" && FILTROS[filtro.valor] && !FILTROS[filtro.valor](p)) return false;
    }
    const b = norm(busca);
    if (b.length >= 3) for (const w of b.split(" ")) if (w && !p.busca.includes(w)) return false;
    return true;
  }

  function contar(lista, chave) {
    const m = new Map();
    for (const p of lista) for (const k of [].concat(chave(p))) if (k !== undefined && k !== null) m.set(k, (m.get(k) || 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), "pt-BR"));
  }

  function resumo(procs) {
    const n = (f) => procs.filter(FILTROS[f]).length;
    return {
      total: procs.length,
      naoVisualizados: n("naoVisualizados"), vencidos: n("vencidos"), vencendo: n("vencendo"), comPrazo: n("comPrazo"),
      urgentes: n("urgentes"), semAtribuicao: n("semAtribuicao"), monitorados: n("monitorados"), comAnotacao: n("comAnotacao"),
      porCategoria: contar(procs, (p) => p.categoria.id).map(([id, q]) => { const c = procs.find((p) => p.categoria.id === id).categoria; return { id, rotulo: c.rotulo, cor: c.cor, icone: c.icone, q }; }),
      porTipo: contar(procs, (p) => p.tipo || "(sem tipo)"),
      porAtribuicao: contar(procs, (p) => p.atribuicao || ""),
      porMarcador: contar(procs, (p) => (p.marcadores || []).map((m) => m.nome)),
    };
  }

  // ordem por prazo: vencidos primeiro, depois o que vence antes; sem prazo no fim (mantém a ordem do SEI entre iguais)
  function chavePrazo(p) {
    if (!p.prazo) return 1e9;
    return p.prazo.tipo === "vence" ? p.prazo.dias : 1e6 - p.prazo.dias;
  }

  function csv(procs) {
    const c = (v) => { const s = String(v ?? ""); return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    const cab = ["Processo", "Tipo", "Especificação", "Atribuição", "Interessados", "Marcadores", "Anotação", "Prazo", "Data do prazo", "Categoria", "Urgente", "Não visualizado"];
    const lin = procs.map((p) => [p.numero, p.tipo, p.especificacao, p.atribuicao, (p.interessados || []).join(", "), (p.marcadores || []).map((m) => m.nome).join(", "),
      p.anotacao, p.prazo ? p.prazo.rotulo : "", p.prazo ? p.prazo.data : "", p.categoria ? p.categoria.rotulo : "", p.urgente ? "sim" : "", p.naoVisualizado ? "sim" : ""].map(c).join(";"));
    return "﻿" + [cab.join(";"), ...lin].join("\r\n");
  }

  // histórico de processos visitados: o mais recente no topo, sem repetir, até 60
  function registrarVisita(hist, p, quando) {
    const h = (hist || []).filter((x) => x.numero !== p.numero);
    h.unshift({ numero: p.numero, tipo: p.tipo || "", especificacao: p.especificacao || "", quando: quando || Date.now() });
    return h.slice(0, 60);
  }

  const PADRAO = { ligado: true, temaEscuro: false, contadorAba: true, mostrarEspecificacao: true, mostrarAnotacao: true, alertaDias: 5, criticoDias: 2, regrasTexto: "", recolhido: false };

  const API = { norm, argsDica, prazoDe, categoria, CATEGORIAS, regrasDoTexto, urgente, enriquecer, passa, FILTROS, resumo, chavePrazo, csv, registrarVisita, PADRAO };
  if (typeof module === "object" && module.exports) module.exports = API;
  else raiz.AptoSeiPainel = API;
})(typeof globalThis !== "undefined" ? globalThis : this);
