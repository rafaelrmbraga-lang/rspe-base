// Ponta a ponta do SEI no APTO (laboratório, tudo fictício): o leitor da extensão (extensao_seeu/sei/lib, vindo do NUSPEN) lê o
// SEI FICTÍCIO (ferramentas/sei_ficticio) e entrega ao servidor local do APTO. Imprime JSON para o teste_sei_apto.py conferir.
// Env: SEI_BASE, APP_BASE, TOKEN. O cookie imita a sessão do navegador; o Origin imita a página da extensão.
import { sincronizar, criarLeitor, SessaoAusente, EscritaProibida } from "../extensao_seeu/sei/lib/nucleo.js";
import { adaptadorFicticio as adaptador } from "../extensao_seeu/sei/lib/adaptador_ficticio.js";

const { SEI_BASE, APP_BASE, TOKEN } = process.env;
const fetch0 = globalThis.fetch;
globalThis.fetch = (u, o = {}) => (String(u).startsWith(APP_BASE)
  ? fetch0(u, { ...o, headers: { ...(o.headers || {}), Origin: "chrome-extension://teste" } }) : fetch0(u, o));
const app = { base: APP_BASE, baseSei: SEI_BASE, token: TOKEN };
const leitor = (cookie) => criarLeitor({ baseSei: SEI_BASE, adaptador, limitePorMinuto: 1000000, cabecalhos: cookie ? { Cookie: "SEIFICT=ok" } : {} });
const saida = {};
try {
  await sincronizar({ adaptador, leitor: leitor(false), app });
  saida.semSessao = "NAO reconheceu";
} catch (e) { saida.semSessao = e instanceof SessaoAusente ? "ok" : `erro: ${e.message}`; }
try { await leitor(true).get(`${SEI_BASE}/sei/controlador.php?acao=documento_excluir&id=1`); saida.escrita = "NAO recusou"; }
catch (e) { saida.escrita = e instanceof EscritaProibida ? "recusada" : `erro: ${e.message}`; }
saida.tokenErrado = await sincronizar({ adaptador, leitor: leitor(true), app: { ...app, token: "errado" } }).then(() => "NAO barrou", (e) => e.codigo || e.message);
saida.primeira = await sincronizar({ adaptador, leitor: leitor(true), app, opcoes: { tetoProcessos: 30 } });
saida.repetida = await sincronizar({ adaptador, leitor: leitor(true), app, opcoes: { tetoProcessos: 30 } });
await fetch(`${SEI_BASE}/_ficticio/avancar`);
saida.segunda = await sincronizar({ adaptador, leitor: leitor(true), app, opcoes: { tetoProcessos: 30 } });
saida.estatisticas = await (await fetch(`${SEI_BASE}/_ficticio/estatisticas`)).json();
console.log(JSON.stringify(saida));
