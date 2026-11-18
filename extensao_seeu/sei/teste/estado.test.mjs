import test from "node:test";
import assert from "node:assert/strict";
import { estadoConexao, estimativa, formatarTempo, fasePainel, percentual, tempoRestante, mensagemErro, textoResultado, MODOS_PAINEL } from "../lib/estado.js";

test("conexao: cada caso diz o que fazer em seguida", () => {
  let e = estadoConexao({ appOk: false, pareado: false, sessaoSei: false });
  assert.equal(e.app.codigo, "indisponivel"); assert.match(e.acaoSeguinte, /Abra o aplicativo/); assert.equal(e.pronto, false);
  e = estadoConexao({ appOk: true, pareado: false, sessaoSei: true });
  assert.equal(e.app.codigo, "nao_pareado"); assert.match(e.acaoSeguinte, /código de pareamento/);
  e = estadoConexao({ appOk: true, pareado: true, sessaoSei: false });
  assert.equal(e.sessao.codigo, "nao_detectada"); assert.match(e.acaoSeguinte, /Entre no SEI/);
  e = estadoConexao({ appOk: true, pareado: true, sessaoSei: true });
  assert.equal(e.pronto, true); assert.equal(e.acaoSeguinte, "");
  assert.equal(estadoConexao({ appOk: true, pareado: true, sessaoSei: null }).sessao.codigo, "verificando");
  assert.equal(estadoConexao({ appOk: true, pareado: true, sessaoSei: true, destinoFicticio: true }).destinoFicticio, true);
});

test("cada estado tem texto e cor (nao so cor)", () => {
  for (const [a, p, s] of [[false, false, false], [true, false, true], [true, true, false], [true, true, true]]) {
    const e = estadoConexao({ appOk: a, pareado: p, sessaoSei: s });
    for (const x of [e.app, e.sessao]) { assert.ok(x.rotulo.length > 5); assert.ok(["ok", "aviso", "erro", "neutro"].includes(x.tom)); }
  }
});

test("estimativa: honesta quando nao ha base e limitada pelo teto", () => {
  const primeira = estimativa({ modo: "todos", processosConhecidos: 0, tetoProcessos: 5 });
  assert.equal(primeira.processosMax, 5); assert.ok(primeira.incerta); assert.ok(primeira.requisicoes > 0);
  const semTeto = estimativa({ modo: "todos", processosConhecidos: 0 });
  assert.equal(semTeto.requisicoes, null); assert.match(semTeto.texto, /primeira leitura/);
  const conhecida = estimativa({ modo: "documentos_novos", processosConhecidos: 40, pausaMs: 300, limitePorMinuto: 1000 });
  assert.equal(conhecida.processosMax, 40); assert.equal(conhecida.requisicoes, 2 + 80);
  assert.ok(Math.abs(conhecida.segundos - 82 * 0.3) < 1e-9);
  const um = estimativa({ modo: "um", processosConhecidos: 100 });
  assert.equal(um.processosMax, 1);
  const lim = estimativa({ modo: "documentos_novos", processosConhecidos: 10, pausaMs: 0, limitePorMinuto: 30 });
  assert.ok(Math.abs(lim.segundos - lim.requisicoes * 2) < 1e-9); // 30/min = 2 s por requisicao
});

test("formatarTempo", () => {
  assert.equal(formatarTempo(45), "45 s"); assert.equal(formatarTempo(150), "2 min 30 s");
  assert.equal(formatarTempo(3600), "1 h 0 min"); assert.equal(formatarTempo(null), "—");
});

test("fase do painel e progresso", () => {
  assert.equal(fasePainel(null), "ocioso");
  assert.equal(fasePainel({ fase: "lendo" }), "lendo");
  assert.equal(fasePainel({ fase: "lendo", pausado: true }), "pausado");
  assert.equal(fasePainel({ fase: "concluida", falhas: 0 }), "concluida");
  assert.equal(fasePainel({ fase: "concluida", falhas: 2 }), "concluida_com_falhas");
  assert.equal(fasePainel({ fase: "parada", parada: "sessao_expirada" }), "parada");
  assert.equal(fasePainel({ fase: "lendo", erro: "x" }), "erro");
  assert.equal(percentual({ processos: 5, processosPulados: 5 }, 20), 50);
  assert.equal(percentual({ processos: 5 }, 0), null);
  assert.equal(tempoRestante({ processos: 5, decorridoMs: 10000 }, 15), 20);
  assert.equal(tempoRestante({ processos: 1, decorridoMs: 10000 }, 15), null);
});

test("mensagens humanas com o que fazer; codigo desconhecido nao quebra", () => {
  for (const c of ["sessao_ausente", "sessao_expirada", "app_indisponivel", "nao_pareado", "estrutura_inesperada", "resposta_inesperada", "teto", "cancelado"]) {
    const m = mensagemErro(c); assert.ok(m.titulo && m.oQueFazer);
  }
  assert.match(mensagemErro("zzz").titulo, /inesperado/);
  assert.match(mensagemErro("estrutura_inesperada").oQueFazer, /dados incompletos/);
});

test("resultado resume sem inventar e diz se e retomavel", () => {
  const r = textoResultado({ processos: 3, documentosLidos: 9, novos: 7, modificados: 1, documentosPulados: 2, falhas: 1, indisponiveis: 1, parada: "sessao_expirada" });
  assert.match(r.resumo, /3 processo/); assert.match(r.problemas, /1 com falha/); assert.match(r.problemas, /1 inacessível/);
  assert.equal(r.retomavel, true);
  assert.equal(textoResultado({ parada: "teto" }).retomavel, false);
});

test("modos do painel", () => {
  assert.deepEqual(MODOS_PAINEL.map((m) => m.id), ["todos", "novos", "documentos_novos", "selecionados", "um"]);
  assert.ok(MODOS_PAINEL.every((m) => m.ajuda.length > 20));
});
