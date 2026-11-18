// Adaptador do SEI da Defensoria (sei.defensoria.ms.def.br): páginas SINTÉTICAS com a estrutura observada (sei_dpms/). Mesmo
// contrato do fictício: só leitura, estrutura diferente PARA, nada é inventado (endereços só os que a página traz, já assinados).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { adaptadorSeiDpms as A } from "../lib/adaptador_sei_dpms.js";
import { EstruturaInesperada, SessaoAusente } from "../lib/erros.js";
const P = (f) => fs.readFileSync(new URL("./sei_dpms/" + f, import.meta.url), "utf-8");
const B = "https://sei.defensoria.ms.def.br";

test("dpms: tem todos os membros do contrato", () => {
  for (const m of ["nome", "versao", "temVersao", "ativo", "permitido", "urlLista", "ehLogin", "listarProcessos", "lerProcesso", "listarDocumentos", "lerDocumento"]) assert.ok(m in A, m);
  assert.equal(A.temVersao, false);
});
test("dpms: permitido só as quatro leituras, só no SEI da Defensoria", () => {
  for (const a of ["procedimento_controlar", "procedimento_trabalhar", "procedimento_visualizar", "documento_visualizar"]) assert.equal(A.permitido(`${B}/sei/controlador.php?acao=${a}&infra_hash=x`), true, a);
  for (const a of ["documento_excluir", "documento_assinar", "procedimento_enviar", "procedimento_concluir", "documento_gerar", "anotacao_registrar", "arvore_visualizar", "documento_download_anexo"])
    assert.equal(A.permitido(`${B}/sei/controlador.php?acao=${a}`), false, a);
  assert.equal(A.permitido("https://outro.invalid/sei/controlador.php?acao=documento_visualizar"), false);
});
test("dpms: começa do Controle de Processos aberto na aba (endereço assinado); sem ele, pede para abrir", () => {
  A.entrada = "";
  assert.throws(() => A.urlLista(B, 0), SessaoAusente);
  A.entrada = `${B}/sei/controlador.php?acao=procedimento_controlar&infra_hash=z`;
  assert.equal(A.urlLista(B, 0), A.entrada);
  assert.throws(() => A.urlLista(B, 1), EstruturaInesperada);
});
test("dpms: lista de processos (visualizado e não visualizado, dica com especificação e tipo)", () => {
  A.avisos = [];
  const r = A.listarProcessos(P("lista.html"));
  assert.deepEqual(r.itens.map((x) => [x.id, x.numero]), [["111", "99/000111/2026"], ["222", "99/000222/2026"], ["333", "99/000333/2026"]]);
  assert.match(r.itens[0].href, /^controlador\.php\?acao=procedimento_trabalhar&acao_origem=.*&infra_hash=h111$/);
  assert.equal(r.proxima, null); assert.equal(r.total, 3); assert.deepEqual(A.avisos, []);
  const p = A.lerProcesso(P("processo.html"));
  assert.equal(p.especificacao, "Inspeção - Unidade Prisional — Inspeção fictícia no EPMF");
  assert.equal(p.unidade, "NUSPEN-FICT");
  assert.match(p.arvore, /acao=procedimento_visualizar&.*id_procedimento=111&.*infra_hash=v111$/);
});
test("dpms: lista com mais processos do que linhas avisa (paginação ainda não calibrada)", () => {
  A.avisos = [];
  A.listarProcessos(P("lista.html").replace("(3 registros)", "(250 registros)"));
  assert.match(A.avisos[0], /3 de 250/);
});
test("dpms: árvore: documentos com o endereço do conteúdo; anexo PDF fica de fora (ainda não lido)", () => {
  const d = A.listarDocumentos(P("arvore.html"));
  assert.deepEqual(d.map((x) => [x.id, x.titulo]), [["5001", "Despacho 1000001"], ["5002", "Ofício 1000002"]]);
  assert.match(d[0].href, /acao=documento_visualizar&.*infra_hash=d1$/);
});
test("dpms: documento: texto por parágrafo, entidades decodificadas, sem estilo", () => {
  const t = A.lerDocumento(P("documento.html"));
  assert.match(t, /^DESPACHO\nTrata-se de inspeção fictícia\. Determino a expedição de ofício à direção do EPMF, com prazo de 30 \(trinta\) dias/);
  assert.match(t, /Documento assinado eletronicamente por Defensor Fictício/);
  assert.ok(!/font-size|&[a-z]+;/.test(t));
  assert.equal(A.lerDocumento("sem corpo"), null);
});
test("dpms: estrutura diferente PARA; página de login é reconhecida", () => {
  assert.throws(() => A.listarProcessos("<p>mudou</p>"), EstruturaInesperada);
  assert.throws(() => A.lerProcesso("<p>mudou</p>"), EstruturaInesperada);
  assert.throws(() => A.listarDocumentos("<p>mudou</p>"), EstruturaInesperada);
  assert.equal(A.ehLogin('<form id="frmLogin"><input name="txtUsuario"></form>'), true);
  assert.equal(A.ehLogin(P("lista.html")), false);
});
