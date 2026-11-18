// Adaptador de paginas do SEI FICTICIO (laboratorio). A estrutura do SEI real NAO e conhecida
// aqui: o adaptador real (adaptador_sei_real.js) esta DESLIGADO e marcado "calibrar".
// Sem DOM (regex) para rodar igual no Node e no navegador. So LEITURA.
//
// CONTRATO de um adaptador (os testes em teste/contrato.test.mjs valem para todos):
//   nome, versao, temVersao (o SEI informa versao do documento?), ativo
//   permitido(url)            -> true so para URLs de LEITURA conhecidas (lista fixa)
//   urlLista(base, pagina)    -> URL da pagina de lista
//   ehLogin(html)             -> true se a pagina e a de login
//   listarProcessos(html)     -> {itens:[{id,numero,mov,href}], proxima} ou lanca EstruturaInesperada
//   lerProcesso(html)         -> {numero, especificacao, arvore}
//   listarDocumentos(html)    -> [{id,versao,titulo,href}]
//   lerDocumento(html)        -> texto (string) ou null se a estrutura nao for a esperada

import { EstruturaInesperada } from "./erros.js";

const ENTIDADES = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'" };
const decodificar = (t) => t.replace(/&(amp|lt|gt|quot|#39);/g, (m) => ENTIDADES[m]);

// Acoes de LEITURA permitidas. Qualquer outra e recusada (nunca escreve no SEI).
export const ACOES_PERMITIDAS = new Set([
  "procedimento_controlar",
  "procedimento_trabalhar",
  "arvore_visualizar",
  "documento_visualizar",
]);

export const adaptadorFicticio = {
  nome: "sei-ficticio",
  versao: "1.1",
  temVersao: true,
  ativo: true,
  permitido(url) {
    const u = new URL(url);
    return u.pathname === "/sei/controlador.php" && ACOES_PERMITIDAS.has(u.searchParams.get("acao"));
  },
  urlLista: (base, pagina) =>
    `${base}/sei/controlador.php?acao=procedimento_controlar&pagina=${pagina}`,
  ehLogin: (html) => /id="frmLogin"/.test(html),
  listarProcessos(html) {
    if (!/id="lista"/.test(html)) throw new EstruturaInesperada("lista de processos não encontrada");
    const itens = [];
    const re =
      /<a class="processo" data-id="(\d+)" data-numero="([^"]+)" data-mov="([^"]+)" href="([^"]+)"/g;
    for (const m of html.matchAll(re)) {
      itens.push({ id: m[1], numero: m[2], mov: m[3], href: decodificar(m[4]) });
    }
    const prox = html.match(/<a rel="next" href="([^"]+)"/);
    return { itens, proxima: prox ? decodificar(prox[1]) : null };
  },
  lerProcesso(html) {
    const numero = (html.match(/<h1 id="numero">([^<]+)</) || [])[1];
    if (!numero) throw new EstruturaInesperada("número do processo não encontrado");
    const espec = (html.match(/<p id="espec">([^<]*)</) || [])[1] || "";
    const arv = html.match(/<a id="arvore" href="([^"]+)"/);
    return { numero, especificacao: decodificar(espec), arvore: arv ? decodificar(arv[1]) : null };
  },
  listarDocumentos(html) {
    if (!/id="arvore-docs"/.test(html)) throw new EstruturaInesperada("árvore de documentos não encontrada");
    const docs = [];
    const re =
      /<a class="doc" data-id="(\d+)" data-versao="([^"]+)" data-titulo="([^"]+)" href="([^"]+)"/g;
    for (const m of html.matchAll(re)) {
      docs.push({ id: m[1], versao: m[2], titulo: decodificar(m[3]), href: decodificar(m[4]) });
    }
    return docs;
  },
  lerDocumento(html) {
    const m = html.match(/<div id="conteudo">([\s\S]*?)<\/div>/);
    return m ? decodificar(m[1]) : null;
  },
};
