// Ponta a ponta do leitor do SEI da Defensoria (adaptador_sei_dpms) com o núcleo do NUSPEN e o servidor do APTO. O "SEI" são
// as páginas SINTÉTICAS de extensao_seeu/sei/teste/sei_dpms (mesma estrutura do SEI 4 da Defensoria), servidas pelo fetch do
// teste conforme a ação. Env: APP_BASE, TOKEN. Imprime JSON para o teste_sei_apto.py.
import fs from "node:fs";
import { sincronizar, criarLeitor } from "../extensao_seeu/sei/lib/nucleo.js";
import { adaptadorSeiDpms as A } from "../extensao_seeu/sei/lib/adaptador_sei_dpms.js";
const { APP_BASE, TOKEN } = process.env;
const P = (f) => fs.readFileSync(new URL("../extensao_seeu/sei/teste/sei_dpms/" + f, import.meta.url), "utf-8");
const BASE = "https://sei.defensoria.ms.def.br";
const pedidos = [];
const resp = (corpo) => ({ status: 200, ok: true, headers: { get: () => "text/html; charset=iso-8859-1" }, text: async () => corpo });
const fetch0 = globalThis.fetch;
globalThis.fetch = async (u, o = {}) => {
  const s = String(u);
  if (s.startsWith(APP_BASE)) return fetch0(u, { ...o, headers: { ...(o.headers || {}), Origin: "chrome-extension://teste" } });
  const url = new URL(s);
  pedidos.push([o.method || "GET", url.searchParams.get("acao")]);
  const acao = url.searchParams.get("acao");
  if (acao === "procedimento_controlar") return resp(P("lista.html"));
  if (acao === "procedimento_trabalhar") return resp(P("processo.html").replace(/id_procedimento=111/g, "id_procedimento=" + url.searchParams.get("id_procedimento")));
  if (acao === "procedimento_visualizar") return resp(P("arvore.html").replace(/id_documento=(500\d)/g, (m, d) => `id_documento=${url.searchParams.get("id_procedimento")}${d}`).replace(/"(500\d)"/g, (m, d) => `"${url.searchParams.get("id_procedimento")}${d}"`));
  if (acao === "documento_visualizar") return resp(P("documento.html"));
  return { status: 404, ok: false, headers: { get: () => "text/html" }, text: async () => "" };
};
const app = { base: APP_BASE, baseSei: BASE, token: TOKEN };
const leitor = () => criarLeitor({ baseSei: BASE, adaptador: A, limitePorMinuto: 1000000 });
const saida = {};
A.entrada = "";
saida.semEntrada = await sincronizar({ adaptador: A, leitor: leitor(), app }).then(() => "NAO parou", (e) => e.codigo);
A.entrada = `${BASE}/sei/controlador.php?acao=procedimento_controlar&acao_origem=procedimento_controlar&infra_hash=z`;
saida.primeira = await sincronizar({ adaptador: A, leitor: leitor(), app });
saida.repetida = await sincronizar({ adaptador: A, leitor: leitor(), app });
saida.metodos = [...new Set(pedidos.map((p) => p[0]))];
saida.acoes = [...new Set(pedidos.map((p) => p[1]))].sort();
console.log(JSON.stringify(saida));
