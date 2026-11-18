// APTO Atendimentos - funções comuns ao SAP (content script) e ao painel.
// Tudo fica guardado no próprio navegador (storage.local). Nada sai do computador.
(function () {
  "use strict";
  let ext = globalThis.browser || globalThis.chrome;
  // fora da extensão (página de teste aberta como arquivo): imita o storage com o localStorage
  if (!ext || !ext.storage || !ext.storage.local) {
    const ouvintes = [];
    const LS = "aptoAtdTeste";
    const tudo = () => { try { return JSON.parse(localStorage.getItem(LS) || "{}"); } catch (e) { return {}; } };
    ext = {
      teste: true,
      storage: {
        local: {
          get: async (ks) => { const t = tudo(); const r = {}; for (const k of [].concat(ks)) if (k in t) r[k] = t[k]; return r; },
          set: async (o) => { const t = Object.assign(tudo(), o); localStorage.setItem(LS, JSON.stringify(t)); ouvintes.forEach((f) => f(Object.fromEntries(Object.keys(o).map((k) => [k, { newValue: o[k] }])), "local")); },
        },
        onChanged: { addListener: (f) => ouvintes.push(f) },
      },
      runtime: { getURL: (p) => p, sendMessage: async () => null, onMessage: { addListener() {} } },
      tabs: { getCurrent: async () => null },
    };
  }

  // colunas da tabela CONTROLE - 3ª DPEP (a 1ª, Atendimentos, é contada pelos atendimentos do dia)
  const COLUNAS = [
    ["ATEND", "Atendimentos"],
    ["PP", "Pedido de Providência"],
    ["AGEX", "AgEx"],
    ["HC", "HC"],
    ["ED", "ED"],
    ["MANIF", "Manifestações"],
    ["ST", "Saída Temporária"],
    ["PROG", "Progressão"],
    ["LC", "LC"],
    ["INDULTO", "Indulto"],
    ["COMUT", "Comutação"],
    ["PRESC", "Prescrição"],
    ["EXT", "Extinção"],
    ["MONIT", "Flex. Monitoramento"],
    ["DOMIC", "Domiciliar"],
    ["REMICAO", "Remição"],
    ["DETRACAO", "Detração"],
    ["PRD", "Subs. PRD"],
    ["JUST", "Justificativas"],
    ["CIENCIA", "Ciência"],
    ["OFICIO", "Ofícios"],
  ];
  const TIPOS = COLUNAS.filter((c) => c[0] !== "ATEND");
  const nomeTipo = (k) => (COLUNAS.find((c) => c[0] === k) || [k, k])[1];

  // palavras do texto do atendimento que sugerem a peça (só sugestão; quem marca é a pessoa)
  const SUGESTOES = [
    [/ser[aá] impetrado|habeas/i, "HC"],
    [/impugna/i, "MANIF"],
    [/sa[ií]da tempor/i, "ST"],
    [/progress[aã]o/i, "PROG"],
    [/livramento|\bLC\b/i, "LC"],
    [/indulto/i, "INDULTO"],
    [/comuta[cç]/i, "COMUT"],
    [/prescri/i, "PRESC"],
    [/extin[cç][aã]o/i, "EXT"],
    [/monitoramento|tornozeleira/i, "MONIT"],
    [/domiciliar/i, "DOMIC"],
    [/remi[cç][aã]o/i, "REMICAO"],
    [/detra[cç][aã]o/i, "DETRACAO"],
    [/\bPRD\b|presta[cç][aã]o de servi/i, "PRD"],
    [/justifica|acostad/i, "JUST"],
    [/parcelamento|parcelar|PSC para PP|substitui[cç][aã]o da PSC/i, "PRD"],
    [/oficia|of[ií]cio/i, "OFICIO"],
    [/agravo/i, "AGEX"],
    [/habeas/i, "HC"],
    [/embargos de declara/i, "ED"],
    [/manifestad|manifesta[cç]/i, "MANIF"],
    [/pedido de provid/i, "PP"],
  ];
  function sugerir(texto) {
    const r = [];
    for (const [re, k] of SUGESTOES) if (re.test(texto || "") && !r.includes(k)) r.push(k);
    return r;
  }

  // quem foi atendido: rótulo e como entra no relatório ("ao genitor do assistido", "a genitora da assistida")
  const QUEM = [
    ["assistido", ""],
    ["genitora", "a genitora"],
    ["genitor", "ao genitor"],
    ["genitores", "aos genitores"],
    ["esposa", "a esposa"],
    ["companheira", "a companheira"],
    ["madrasta", "a madrasta"],
    ["irmã", "a irmã"],
    ["irmão", "ao irmão"],
    ["avó", "a avó"],
    ["avô", "ao avô"],
    ["filha", "a filha"],
    ["filho", "ao filho"],
    ["tia", "a tia"],
    ["advogado", "ao advogado"],
  ];
  // "ao genitor do assistido" / "a assistida"
  function quemFrase(quem, assistida) {
    const q = QUEM.find((x) => x[0] === (quem || "assistido")) || QUEM[0];
    if (!q[1]) return assistida ? "a assistida" : "ao assistido";
    return `${q[1]} ${assistida ? "da assistida" : "do assistido"}`;
  }
  // feminino de quem foi atendido ({o} das frases prontas: orientado/orientada)
  const FEMININO = new Set(["genitora", "esposa", "companheira", "madrasta", "irmã", "avó", "filha", "tia"]);
  function generoAtendido(quem, assistida) {
    if (!quem || quem === "assistido") return assistida ? "a" : "o";
    if (quem === "genitores") return "os";
    return FEMININO.has(quem) ? "a" : "o";
  }
  // "Jose (pai - somente ligação)" -> genitor
  const PARENTESCO = [
    [/\bmadrasta\b/i, "madrasta"],
    [/\b(pais|genitores)\b/i, "genitores"],
    [/\b(m[aã]e|genitora)\b/i, "genitora"],
    [/\b(pai|genitor)\b/i, "genitor"],
    [/\b(esposa|mulher)\b/i, "esposa"],
    [/\b(companheira|namorada|convivente)\b/i, "companheira"],
    [/\birm[aã]\b/i, "irmã"],
    [/\birm[aã]o\b/i, "irmão"],
    [/\bav[oó]\b/i, "avó"],
    [/\bfilha\b/i, "filha"],
    [/\bfilho\b/i, "filho"],
    [/\btia\b/i, "tia"],
    [/\b(pr[oó]prio|assistido)\b/i, "assistido"],
  ];
  function parentesco(texto) {
    for (const [re, q] of PARENTESCO) if (re.test(texto || "")) return q;
    return "";
  }

  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim().toUpperCase();
  // nome sem as anotações entre parênteses do SAP, ex.: "(Usar este perfil)"
  const chaveNome = (s) => norm(s).replace(/\([^)]*\)?/g, " ").replace(/\s+/g, " ").trim();
  const dig = (s) => String(s || "").replace(/\D/g, "");

  function cnj(s) {
    const d = dig(s);
    if (d.length !== 20) return "";
    return `${d.slice(0, 7)}-${d.slice(7, 9)}.${d.slice(9, 13)}.${d.slice(13, 14)}.${d.slice(14, 16)}.${d.slice(16)}`;
  }
  function cnjsNoTexto(texto) {
    const r = [];
    for (const m of String(texto || "").matchAll(/\b\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}\b/g)) {
      const c = cnj(m[0]);
      if (c && !r.includes(c)) r.push(c);
    }
    return r;
  }

  // "Nome Sobrenome DA SILVA" -> "Nome Sobrenome da Silva" (o SAP traz em maiúsculas)
  const MINUSC = new Set(["DA", "DE", "DO", "DAS", "DOS", "E"]);
  function nomeProprio(s) {
    const t = String(s || "").replace(/\s+/g, " ").trim();
    if (t !== t.toUpperCase()) return t; // já está misto: respeita
    return t.toLowerCase().split(" ").map((w, i) => (i > 0 && MINUSC.has(w.toUpperCase()) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
  }

  const pad = (n) => String(n).padStart(2, "0");
  function hojeISO(d) {
    d = d || new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  // "17/11/2026" -> "2026-11-17"
  function isoDeBr(s) {
    const m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(String(s || ""));
    return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
  }
  const horaDe = (s) => (/(\d{2}:\d{2})/.exec(String(s || "")) || ["", ""])[1];
  const brDeIso = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
  const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

  const novoId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

  // ---- dados guardados ----
  // atendimentos: [{id, data, hora, nome, processos[], contato, quem, forma, abertura, corpo, status, fato, origem, tentativas}]
  // pecas: [{id, tipo, processo, nome, data, status: "pendente"|"feito", feitoEm, origem: "atendimento"|"fluxo", atendimentoId, obs, prazo}]
  // ajustes: {"2026-11-17|HC": +1}   modelos: [{titulo, texto}]
  const CHAVES = ["atendimentos", "pecas", "ajustes", "modelos", "config"];
  async function ler() {
    const r = await ext.storage.local.get(CHAVES);
    const d = {
      atendimentos: r.atendimentos || [],
      pecas: r.pecas || [],
      ajustes: r.ajustes || {},
      modelos: r.modelos || null,
      config: r.config || {},
    };
    // dados da versão 1.0.0: forma telefone/whatsapp/vídeo vira "virtual"; pendência sem fila vai para "A fazer"
    for (const a of d.atendimentos) if (a.forma && a.forma !== "presencial" && a.forma !== "virtual") a.forma = "virtual";
    for (const p of d.pecas) if (p.status === "pendente" && !p.coluna) p.coluna = "fazer";
    return d;
  }

  // filas do kanban de pendências
  const FILAS = [["doc", "Aguardando documento"], ["fazer", "A fazer"], ["naoEnc", "Não encaminhou"]];

  // "encaminhe a documentação necessária até 13/11" -> "2026-11-13" (ano do atendimento; se a data já passou, ano seguinte)
  function prazoNoTexto(texto, dataBase) {
    const m = /\bat[eé]\s+(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/i.exec(texto || "");
    if (!m) return "";
    const base = dataBase || hojeISO();
    let ano = m[3] ? (m[3].length === 2 ? "20" + m[3] : m[3]) : base.slice(0, 4);
    let iso = `${ano}-${pad(m[2])}-${pad(m[1])}`;
    if (!m[3] && iso < base && base.slice(5, 7) === "12" && m[2] === "1") iso = `${Number(ano) + 1}-${pad(m[2])}-${pad(m[1])}`;
    return /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(iso) ? iso : "";
  }
  // pede documento ao assistido? (vai para "Aguardando documento")
  const pedeDocumento = (t) => /(encaminh|envi|traz|apresent)\w*\s.*\bat[eé]\s+\d{1,2}\/\d{1,2}|solicitad[oa] (que )?(encaminh|envi|traz)/i.test(t || "");
  async function gravar(parcial) {
    await ext.storage.local.set(parcial);
  }

  // junta (ou cria) o atendimento do dia pelo nome; nunca apaga o que a pessoa já escreveu
  function mesclar(lista, dado) {
    const k = chaveNome(dado.nome);
    let a = lista.find((x) => x.data === dado.data && chaveNome(x.nome) === k);
    if (!a) {
      a = { id: novoId(), data: dado.data, hora: "", nome: nomeProprio(String(dado.nome).replace(/\([^)]*\)?/g, " ").replace(/\s+/g, " ").trim()),
        processos: [], contato: "", quem: "", assistida: false, forma: "presencial", formaManual: false, abertura: true, corpo: "",
        status: "agendado", fato: null, origem: "sap", criadoEm: Date.now() };
      lista.push(a);
    }
    if (dado.hora && !a.hora) a.hora = dado.hora;
    if (dado.rk) a.rk = dado.rk;
    if (dado.unidade) a.unidade = dado.unidade;
    if (dado.statusSap) a.statusSap = dado.statusSap;
    // forma do agendamento (P/V da fila ou o botão Presencial/Virtual do SAP), se você não trocou à mão
    if (dado.forma && !a.formaManual) a.forma = dado.forma;
    // recepção marcou a chegada (linha amarela, status PRESENTE no SAP) = presente, esperando ser chamado
    if (dado.chegada || /PRESENTE/i.test(dado.statusSap || "")) {
      if (dado.chegada) a.chegada = dado.chegada;
      if (a.status === "agendado") a.status = "presente";
    }
    if (dado.fato) {
      a.fato = dado.fato;
      if (!a.processos.length && dado.fato.processos.length) a.processos = dado.fato.processos.slice();
      if (!a.contato && dado.fato.contato) a.contato = dado.fato.contato;
      if (!a.quem && dado.fato.quem) a.quem = dado.fato.quem;
      if (!dado.forma && dado.fato.virtual && !a.formaManual) a.forma = "virtual";
    }
    if (dado.fatoLido) a.fatoLido = dado.fatoLido;
    return a;
  }

  self.ATD = { ext, COLUNAS, TIPOS, nomeTipo, sugerir, QUEM, quemFrase, generoAtendido, FILAS, prazoNoTexto, pedeDocumento, parentesco, norm, chaveNome,
    dig, cnj, cnjsNoTexto, nomeProprio, pad, hojeISO, isoDeBr, horaDe, brDeIso, MESES, novoId, ler, gravar, mesclar };
})();
