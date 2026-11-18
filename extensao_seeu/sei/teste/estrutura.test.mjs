// Coleta de estrutura sanitizada: NENHUM texto ou valor com dado pode vazar. Pagina SINTETICA.
import test from "node:test";
import assert from "node:assert/strict";
import { sanitizar, VERSAO_SANITIZADOR } from "../lib/estrutura.js";

const SEGREDOS = [
  "FULANO DE TAL", "Fulano", "12345678901", "22.0.000012345-6", "x@exemplo.invalid", "987654",
  "abcDEF123", "SEGREDO", "Nome Fictício Confidencial", "senha123", "Processo 99/000123/2026",
  "orgao-secreto.invalid", "Estabelecimento Reservado",
];
const PAGINA = `<!doctype html><html lang="pt-BR"><head><title>Processo 99/000123/2026 - SEI</title>
<meta name="description" content="Nome Fictício Confidencial"><style>.a{color:red} /* FULANO DE TAL */</style>
<script>var cpf="12345678901"; abrir("SEGREDO");</script></head><body class="infra">
<!-- comentario com FULANO DE TAL -->
<table id="tblProcessos" class="infraTable"><tr class="infraTrClara">
<td><a class="processoVisualizado" id="lnk987654" title="Nome Fictício Confidencial" data-valor="SEGREDO"
 href="https://orgao-secreto.invalid/sei/controlador.php?acao=procedimento_trabalhar&id_procedimento=987654&infra_hash=abcDEF123"
 onclick="abrir('SEGREDO')">22.0.000012345-6</a></td>
<td>FULANO DE TAL</td><td>Estabelecimento Reservado</td></tr></table>
<form method="post" action="/sei/controlador.php?acao=pesquisa_rapida"><input type="text" name="txtPesquisa" value="senha123" placeholder="x@exemplo.invalid"></form>
<a rel="next" href="controlador.php?acao=procedimento_controlar&pagina=2">Próxima</a></body></html>`;

test("nenhum segredo da pagina sintetica aparece na saida", () => {
  const { saida } = sanitizar(PAGINA);
  for (const s of SEGREDOS) assert.ok(!saida.includes(s), `vazou: ${s}`);
  assert.ok(!/@/.test(saida.replace(/<!--[\s\S]*?-->/g, "")), "nem e-mail");
});

test("a estrutura util permanece: tags, classes, ids, nomes de acao, formato dos enderecos", () => {
  const { saida } = sanitizar(PAGINA);
  assert.match(saida, /<table[^>]*id="tblProcessos"[^>]*class="infraTable"|<table[^>]*class="infraTable"[^>]*id="tblProcessos"/);
  assert.match(saida, /class="processoVisualizado"/);
  assert.match(saida, /acao=procedimento_trabalhar/);
  assert.match(saida, /acao=pesquisa_rapida/);
  assert.match(saida, /rel="next"/);
  assert.match(saida, /name="txtPesquisa"/);
  assert.match(saida, /id_procedimento=999999/); // valor mascarado com o mesmo formato (digitos -> 9)
  assert.match(saida, /infra_hash=aaaAAA999/); // formato do hash, sem o valor
  assert.match(saida, /id="lnk999999"/);
});

test("texto vira marcadores do mesmo tamanho; scripts, estilos e comentarios somem", () => {
  const { saida } = sanitizar("<p>FULANO DE TAL  e outros</p><script>segredo()</script><style>.x{}</style><!-- c -->");
  assert.ok(saida.includes("<p>xxxxxx xx xxx  x xxxxxx</p>".replace("xxxxxx xx xxx  x xxxxxx", "xxxxxx xx xxx  x xxxxxx")) || /<p>x{6} x{2} x{3} {2}x x{6}<\/p>/.test(saida));
  assert.ok(!saida.includes("segredo"));
  assert.ok(!saida.includes(".x{}"));
  assert.ok(!saida.includes("<!-- c -->"));
});

test("atributos com possivel dado sao mascarados por inteiro", () => {
  const { saida } = sanitizar('<a title="Nome Fictício" data-x="abc" onclick="f(1)" alt="z" value="v" href="/p">t</a>');
  assert.ok(!saida.includes("Nome Fictício") && !saida.includes("f(1)"));
  assert.match(saida, /title="x{4} x{8}"/); // mesmo tamanho, espaco preservado
  assert.match(saida, /onclick="x{4}"/);
});

test("resumo para a tela e cabecalho de aviso", () => {
  const r = sanitizar(PAGINA);
  assert.ok(r.saida.startsWith(`<!-- NUSPEN estrutura sanitizada v${VERSAO_SANITIZADOR}`));
  assert.ok(r.resumo.tags > 5 && r.resumo.caracteresMascarados > 20);
  assert.ok(r.resumo.atributosMantidos.includes("class"));
  assert.ok(r.resumo.descricao.includes("Nenhum texto"));
});

test("entrada vazia ou nao-HTML nao quebra", () => {
  assert.equal(sanitizar("").resumo.tags, 0);
  assert.ok(!sanitizar("só texto FULANO").saida.includes("FULANO"));
});
