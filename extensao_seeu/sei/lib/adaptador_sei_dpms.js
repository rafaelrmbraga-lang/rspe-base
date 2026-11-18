// Adaptador do SEI da Defensoria Pública de MS (sei.defensoria.ms.def.br, SEI 4.x), calibrado pela ESTRUTURA de uma sessão
// gravada (HAR) em 18/11/2026: nomes das ações, ids, classes e o formato da árvore. Nenhum conteúdo real foi usado: os testes
// usam páginas sintéticas com a mesma estrutura (teste/sei_dpms.test.mjs). Só LEITURA, mesmo contrato do adaptador fictício.
//
// Como o SEI da Defensoria funciona (o que muda em relação ao fictício):
//  - todo link interno leva uma assinatura (infra_hash) feita pelo próprio SEI na sessão da pessoa: o leitor NÃO monta endereços,
//    só segue os links que a página traz. O ponto de partida é o Controle de Processos aberto na aba do SEI (a extensão guarda o
//    endereço dele quando a pessoa o abre, já logada: sei_aba.js);
//  - Controle de Processos (acao=procedimento_controlar): linhas <tr id="P<id>"> com o link do processo (classe
//    processoVisualizado / processoNaoVisualizado) para procedimento_trabalhar; especificação e tipo na dica do link
//    (infraTooltipMostrar('<especificação>','<tipo>')); total na legenda "Processos (N registros):";
//  - página do processo (procedimento_trabalhar): a árvore vem na moldura ifrArvore (src = procedimento_visualizar);
//  - árvore (procedimento_visualizar): nós em JavaScript, Nos[i] = new infraArvoreNo("DOCUMENTO", id, idPai, link, alvo, dica,
//    rótulo, ...); o conteúdo do documento em Nos[i].src (documento_visualizar);
//  - documento (documento_visualizar): HTML do próprio documento (classes Texto_*), com a assinatura eletrônica no fim.
// Paginação da lista: não observada (a lista coube numa página); se o SEI paginar, o leitor lê a primeira página e avisa.
import { EstruturaInesperada, SessaoAusente } from "./erros.js";

export const ACOES_PERMITIDAS = new Set(["procedimento_controlar", "procedimento_trabalhar", "procedimento_visualizar", "documento_visualizar"]);
export const HOST = "sei.defensoria.ms.def.br";

const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", ordm: "º", ordf: "ª", deg: "°", sect: "§", ndash: "–", mdash: "—",
  laquo: "«", raquo: "»", ldquo: "“", rdquo: "”", lsquo: "‘", rsquo: "’", hellip: "…", middot: "·" };
for (const [l, b] of Object.entries({ a: "aáàâãä", e: "eéèêë", i: "iíìîï", o: "oóòôõö", u: "uúùûü", c: "cç", n: "nñ" })) {
  const nomes = { "á": "acute", "à": "grave", "â": "circ", "ã": "tilde", "ä": "uml", "é": "acute", "è": "grave", "ê": "circ", "ë": "uml", "í": "acute", "ì": "grave",
    "î": "circ", "ï": "uml", "ó": "acute", "ò": "grave", "ô": "circ", "õ": "tilde", "ö": "uml", "ú": "acute", "ù": "grave", "û": "circ", "ü": "uml", "ç": "cedil", "ñ": "tilde" };
  for (const ch of b.slice(1)) { ENT[l + nomes[ch]] = ch; ENT[l.toUpperCase() + nomes[ch]] = ch.toUpperCase(); }
}
export function decodificar(t) {
  return String(t || "").replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === "#") { const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
    return ENT[e] ?? m;
  });
}
const semTags = (h) => decodificar(String(h || "").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
const acaoDe = (href) => { const m = /[?&]acao=([a-z_]+)/.exec(String(href || "")); return m ? m[1] : ""; };
// argumentos de uma chamada JS: "texto", 'texto', null, true, números
function argumentos(s) {
  const r = [];
  const re = /"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|\b(null|true|false)\b|(-?\d+(?:\.\d+)?)/g;
  for (const m of s.matchAll(re)) {
    if (m[1] !== undefined || m[2] !== undefined) r.push((m[1] ?? m[2]).replace(/\\(u[0-9a-fA-F]{4}|.)/g, (x, c) => (c.length === 5 ? String.fromCharCode(parseInt(c.slice(1), 16)) : { n: "\n", t: "\t", r: "" }[c] ?? c)));
    else if (m[3]) r.push(m[3] === "null" ? null : m[3] === "true");
    else r.push(Number(m[4]));
  }
  return r;
}

// especificação e tipo de cada processo, vistos na lista (a página do processo não os repete)
const daLista = new Map();

export const adaptadorSeiDpms = {
  nome: "sei-dpms",
  versao: "1.0-har-2026-11-18",
  temVersao: false, // o SEI não informa versão do documento: a mudança é vista pelo hash do texto
  ativo: true,
  entrada: "", // endereço (assinado) do Controle de Processos aberto na aba do SEI; vem da extensão (sei_aba.js)
  avisos: [],
  permitido(url) {
    const u = new URL(url);
    return u.hostname === HOST && u.pathname === "/sei/controlador.php" && ACOES_PERMITIDAS.has(u.searchParams.get("acao"));
  },
  urlLista(base, pagina) {
    if (pagina > 0) throw new EstruturaInesperada("o SEI paginou a lista de processos (ainda não calibrado)");
    if (!this.entrada) throw new SessaoAusente("abra o SEI no Controle de Processos, numa aba, já logado, e volte aqui");
    return this.entrada;
  },
  ehLogin: (html) => /id="frmLogin"|name="txtUsuario"|\/sip\/login\.php/i.test(html) && !/id="frmProcedimentoControlar"|ifrArvore|infraArvoreNo/.test(html),
  listarProcessos(html) {
    if (!/id="frmProcedimentoControlar"/.test(html)) throw new EstruturaInesperada("Controle de Processos não encontrado (abra o Controle de Processos no SEI)");
    const itens = [];
    const vistos = new Set();
    for (const m of html.matchAll(/<tr[^>]*\bid="P(\d+)"[^>]*>([\s\S]*?)<\/tr>/g)) {
      const a = /<a\b[^>]*class="processo(?:Visualizado|NaoVisualizado)[^"]*"[^>]*>[\s\S]*?<\/a>/.exec(m[2]);
      if (!a) continue;
      const href = decodificar((/href="([^"]+)"/.exec(a[0]) || [])[1] || "");
      if (acaoDe(href) !== "procedimento_trabalhar" || vistos.has(m[1])) continue;
      vistos.add(m[1]);
      const numero = semTags(a[0]);
      const dica = /infraTooltipMostrar\(([\s\S]*?)\);/.exec(a[0]);
      const [espec, tipo] = dica ? argumentos(decodificar(dica[1])) : [];
      daLista.set(m[1], { especificacao: String(espec || ""), tipo: String(tipo || "") });
      itens.push({ id: m[1], numero, mov: "", href });
    }
    const total = Number((/Processos\s*\((\d+)\s*registros?\)/i.exec(html) || [])[1] || 0);
    if (!itens.length && total) throw new EstruturaInesperada("a lista diz ter processos, mas nenhum link de processo foi reconhecido");
    if (total > itens.length) this.avisos.push(`o SEI mostrou ${itens.length} de ${total} processos na página: só esses foram lidos`);
    return { itens, proxima: null, total };
  },
  lerProcesso(html) {
    const ifr = /<iframe\b[^>]*\bid="ifrArvore"[^>]*\bsrc="([^"]+)"/.exec(html);
    if (!ifr) throw new EstruturaInesperada("árvore do processo não encontrada");
    const arvore = decodificar(ifr[1]);
    if (acaoDe(arvore) !== "procedimento_visualizar") throw new EstruturaInesperada("árvore do processo com endereço inesperado");
    const id = (/[?&]id_procedimento=(\d+)/.exec(arvore) || [])[1] || "";
    const l = daLista.get(id) || {};
    const unidade = semTags((/<a\b[^>]*id="lnkInfraUnidade"[^>]*>([\s\S]*?)<\/a>/.exec(html) || [])[1] || "");
    return { numero: null, especificacao: [l.tipo, l.especificacao].filter(Boolean).join(" — "), arvore, unidade };
  },
  listarDocumentos(html) {
    const nos = new Map();
    for (const m of html.matchAll(/Nos\[(\d+)\]\s*=\s*new\s+infraArvoreNo\(([\s\S]*?)\);/g)) nos.set(m[1], argumentos(m[2]));
    if (!nos.size) throw new EstruturaInesperada("árvore de documentos não encontrada");
    const src = new Map();
    for (const m of html.matchAll(/Nos\[(\d+)\]\.src\s*=\s*(?:'([^']*)'|"([^"]*)")\s*;/g)) src.set(m[1], decodificar(m[2] ?? m[3]));
    const docs = [];
    for (const [i, a] of nos) {
      if (a[0] !== "DOCUMENTO") continue;
      const href = src.get(i) || "";
      if (acaoDe(href) !== "documento_visualizar") continue; // anexo externo (PDF etc.): ainda não lido
      docs.push({ id: String(a[1]), versao: "", titulo: decodificar(String(a[6] || a[5] || "")).trim(), href });
    }
    return docs;
  },
  lerDocumento(html) {
    if (!/<body[\s>]/i.test(html)) return null;
    const corpo = String(html).replace(/\r\n?/g, "\n").replace(/<(script|style|head)\b[\s\S]*?<\/\1>/gi, " ")
      .replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|tr|li|h\d|table)>/gi, "\n").replace(/<td\b[^>]*>/gi, " ");
    const texto = decodificar(corpo.replace(/<[^>]+>/g, "")).replace(/[ \t ]+/g, " ").replace(/ *\n */g, "\n").replace(/\n{2,}/g, "\n").trim();
    return texto || null;
  },
};
