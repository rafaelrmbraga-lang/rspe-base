// Coleta de ESTRUTURA sanitizada: para calibrar o adaptador sem expor dados.
// Mantem so a forma da pagina (tags, classes, ids, nomes de atributos e de acoes, formato dos
// enderecos). TODO texto vira marcador de mesmo tamanho; valores de atributos que podem ter dado
// (titulos, data-*, onclick, value, hashes, numeros) sao mascarados. Nada e enviado a lugar nenhum:
// o resultado e gravado em arquivo LOCAL que o usuario revisa antes de entregar a quem calibra.

export const VERSAO_SANITIZADOR = "1";

const mascarar = (s) => s.replace(/\S/g, "x");
const formato = (s) => s.replace(/[0-9]/g, "9").replace(/[a-z]/g, "a").replace(/[A-Z]/g, "A");

// atributos estruturais: o valor fica, com digitos mascarados
const MANTER_FORMATO = new Set(["id", "name", "for"]);
// atributos de enumeracao curta: o valor fica se parecer palavra de enumeracao
const MANTER_ENUM = new Set(["rel", "type", "method", "role", "target", "lang", "colspan", "rowspan"]);
const URLS = new Set(["href", "src", "action"]);

function urlSanitizada(valor) {
  let u;
  try {
    u = new URL(valor, "http://base.invalid");
  } catch {
    return mascarar(valor);
  }
  const absoluta = /^[a-z][a-z0-9+.-]*:/i.test(valor);
  const partes = u.pathname.split("/").map((seg) =>
    /^[A-Za-z_.-]{1,40}$/.test(seg) ? seg : formato(seg).replace(/[A-Za-z]/g, (c) => (c === "A" ? "A" : "a")));
  const consulta = [...u.searchParams.entries()].map(([k, v]) => {
    const nome = /^[A-Za-z_][\w-]{0,40}$/.test(k) ? k : formato(k);
    const mantem = k === "acao" && /^[a-z_]{3,60}$/.test(v); // nome de acao e estrutura
    return `${nome}=${mantem ? v : formato(v)}`;
  });
  const origem = absoluta ? "https://host.invalid" : "";
  return `${origem}${partes.join("/")}${consulta.length ? "?" + consulta.join("&") : ""}`;
}

function atributo(nome, valor) {
  const n = nome.toLowerCase();
  if (valor === null) return nome;
  if (n === "class") return `${nome}="${valor.split(/\s+/).map((c) => (/^[A-Za-z][\w-]{0,40}$/.test(c) ? c : formato(c))).join(" ")}"`;
  if (MANTER_FORMATO.has(n)) return `${nome}="${formato(valor)}"`.replace(/A/g, (m) => m);
  if (MANTER_ENUM.has(n)) return `${nome}="${/^[A-Za-z0-9-]{0,20}$/.test(valor) ? valor : mascarar(valor)}"`;
  if (URLS.has(n)) return `${nome}="${urlSanitizada(valor)}"`;
  return `${nome}="${mascarar(valor)}"`;
}

function idFormato(valor) {
  // ids/names: letras ficam (estrutura), digitos viram 9
  return valor.replace(/[0-9]/g, "9");
}

export function sanitizar(html) {
  const entrada = String(html ?? "");
  const resumo = { tags: 0, caracteresMascarados: 0, atributosMantidos: new Set(), descricao: "" };
  let pularConteudo = false;
  const partes = entrada.split(/(<!--[\s\S]*?-->|<[^>]+>)/g);
  const saida = [];
  for (const parte of partes) {
    if (!parte) continue;
    if (parte.startsWith("<!--")) continue;
    if (parte.startsWith("<")) {
      const fechamento = /^<\//.test(parte);
      const m = parte.match(/^<\/?\s*([A-Za-z][\w:-]*)([\s\S]*?)(\/?)>$/);
      if (!m) { saida.push(mascarar(parte)); continue; }
      const tag = m[1];
      if (fechamento) { pularConteudo = false; saida.push(`</${tag}>`); continue; }
      resumo.tags++;
      const attrs = [];
      for (const a of m[2].matchAll(/([^\s=\/>"']+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+))?/g)) {
        const nome = a[1];
        const valor = a[2] === undefined ? null : a[2].replace(/^["']|["']$/g, "");
        let texto = atributo(nome, valor);
        if (MANTER_FORMATO.has(nome.toLowerCase()) && valor !== null) texto = `${nome}="${idFormato(valor)}"`;
        if (valor !== null && /^(class|id|name|for|rel|type|method|role|target|lang|href|src|action)$/i.test(nome)) resumo.atributosMantidos.add(nome.toLowerCase());
        if (valor !== null && !/^(class|id|name|for|rel|type|method|role|target|lang|colspan|rowspan|href|src|action)$/i.test(nome)) resumo.caracteresMascarados += valor.length;
        attrs.push(texto);
      }
      pularConteudo = /^(script|style)$/i.test(tag);
      saida.push(`<${tag}${attrs.length ? " " + attrs.join(" ") : ""}${m[3] ? " /" : ""}>`);
      continue;
    }
    if (pularConteudo) continue; // conteudo de script e estilo some
    const mascara = mascarar(parte);
    resumo.caracteresMascarados += parte.replace(/\s/g, "").length;
    saida.push(mascara);
  }
  const lista = [...resumo.atributosMantidos].sort();
  const cab = `<!-- NUSPEN estrutura sanitizada v${VERSAO_SANITIZADOR}: texto e valores mascarados; revise antes de entregar -->\n`;
  return {
    saida: cab + saida.join(""),
    resumo: {
      tags: resumo.tags,
      caracteresMascarados: resumo.caracteresMascarados,
      atributosMantidos: lista,
      descricao:
        "Será gravado um arquivo local só com a estrutura da página (marcas, classes, ids, nomes de ações e formato dos endereços). " +
        "Nenhum texto, nome, número, hash ou valor de atributo é gravado: tudo é trocado por marcadores do mesmo tamanho.",
    },
  };
}
