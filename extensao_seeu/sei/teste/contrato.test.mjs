// Contrato que TODO adaptador cumpre (fictício hoje; real quando calibrado). Fixtures SINTETICAS.
import test from "node:test";
import assert from "node:assert/strict";
import { adaptadorFicticio } from "../lib/adaptador_ficticio.js";
import { adaptadorSeiReal } from "../lib/adaptador_sei_real.js";
import { EstruturaInesperada, AdaptadorDesligado } from "../lib/erros.js";

const MEMBROS = ["nome", "versao", "temVersao", "ativo", "permitido", "urlLista", "ehLogin", "listarProcessos", "lerProcesso", "listarDocumentos", "lerDocumento"];

for (const [rotulo, a] of [["ficticio", adaptadorFicticio], ["real (desligado)", adaptadorSeiReal]]) {
  test(`${rotulo}: tem todos os membros do contrato`, () => {
    for (const m of MEMBROS) assert.ok(m in a, `falta ${m}`);
    assert.equal(typeof a.nome, "string"); assert.equal(typeof a.versao, "string");
    assert.equal(typeof a.temVersao, "boolean"); assert.equal(typeof a.ativo, "boolean");
  });
}

test("ficticio: leitura de paginas sinteticas", () => {
  const lista = '<table id="lista"><a class="processo" data-id="1" data-numero="N-1" data-mov="m" href="a.php?x=1">x</a></table><a rel="next" href="b.php">p</a>';
  const r = adaptadorFicticio.listarProcessos(lista);
  assert.equal(r.itens.length, 1); assert.equal(r.proxima, "b.php");
  assert.equal(adaptadorFicticio.lerDocumento('<div id="conteudo">t</div>'), "t");
  assert.equal(adaptadorFicticio.lerDocumento("<p>x</p>"), null);
});

test("ficticio: estrutura diferente PARA (nao devolve lista vazia como se estivesse certo)", () => {
  assert.throws(() => adaptadorFicticio.listarProcessos("<p>mudou</p>"), EstruturaInesperada);
  assert.throws(() => adaptadorFicticio.lerProcesso("<p>mudou</p>"), EstruturaInesperada);
  assert.throws(() => adaptadorFicticio.listarDocumentos("<p>mudou</p>"), EstruturaInesperada);
});

test("permitido(): so leitura conhecida, nunca escrita", () => {
  const b = "http://sei.exemplo.invalid";
  assert.equal(adaptadorFicticio.permitido(`${b}/sei/controlador.php?acao=documento_visualizar&id_documento=1`), true);
  for (const ruim of ["documento_excluir", "documento_assinar", "procedimento_alterar", "documento_receber", "procedimento_gerar"]) {
    assert.equal(adaptadorFicticio.permitido(`${b}/sei/controlador.php?acao=${ruim}`), false, ruim);
  }
});

test("real: desligado por padrao, nada e lido, tudo marcado para calibrar", () => {
  assert.equal(adaptadorSeiReal.ativo, false);
  assert.equal(adaptadorSeiReal.permitido("https://qualquer.invalid/x"), false);
  for (const f of ["urlLista", "listarProcessos", "lerProcesso", "listarDocumentos", "lerDocumento"]) {
    assert.throws(() => adaptadorSeiReal[f]("x", 0), AdaptadorDesligado, f);
  }
  assert.match(adaptadorSeiReal.versao, /nao-calibrado/);
});
