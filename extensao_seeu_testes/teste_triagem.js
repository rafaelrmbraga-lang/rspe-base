// Testes da Triagem da Mesa (extensão APTO): leitura da Mesa, da página do processo, da lista de arquivos e do texto
// das decisões, escolha do motivo e da última decisão, alertas, filtros de final, endereços permitidos e planilha.
// As páginas desta pasta são FICTÍCIAS, com a mesma marcação do SEEU. Rodar: node teste_triagem.js
"use strict";
const fs = require("fs");
const path = require("path");
const T = require("../extensao_seeu/triagem_core.js");
const A = require("../extensao_seeu/comum.js");

let falhas = 0;
const ok = (c, m) => { if (!c) { falhas++; console.log("FALHA: " + m); } };
const ler = (f) => new TextDecoder("windows-1252").decode(fs.readFileSync(path.join(__dirname, f)));

// ---- Mesa
const mesa = T.lerMesa(ler("mesa_manifestacao.html"));
ok(mesa.total === 23 && mesa.de === 1 && mesa.ate === 20 && mesa.pageSize === 20, "navegação da Mesa: " + JSON.stringify([mesa.total, mesa.de, mesa.ate, mesa.pageSize]));
ok(mesa.campos["org.apache.struts.taglib.html.TOKEN"] === "0123456789abcdef0123456789abcdef" && mesa.campos.finalidadeRemessa === "5", "campos ocultos do formulário");
ok(mesa.linhas.length === 3, "3 linhas na Mesa: " + mesa.linhas.length);
const l0 = mesa.linhas[0];
ok(l0.processo === "7000117-54.2016.8.12.0001" && l0.final === 7, "processo e final (7): " + l0.processo + " " + l0.final);
ok(l0.url === "https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?_tj=aa11bb22cc33dd44", "link do nº (não o Analisar): " + l0.url);
ok(l0.executado === "Fulano de Tal Exemplo" && l0.defensor === "Defensora Alfa Exemplo", "assistido e defensor");
ok(l0.dataEnvio === "13/10/2026" && l0.ultimoDia === "23/10/2026" && l0.prazo === "10 dias corridos", "datas e prazo");
ok(l0.classe === "Execução da Pena" && l0.assunto === "Pena Privativa de Liberdade", "classe e assunto: " + l0.classe + " / " + l0.assunto);
ok(mesa.linhas[1].final === 0 && mesa.linhas[1].classe === "Execução de Medidas Alternativas no Juízo Comum", "segunda linha");
ok(mesa.linhas[2].defensor === "" && mesa.linhas[2].executado === "Ciclano & Filho", "sem defensor vinculado e entidade (&amp;)");
ok(mesa.linhas.every((l) => !/preAnalise/.test(l.url)), "nenhum link de Analisar");

// ---- acentos em entidades HTML, como o SEEU às vezes manda ("at&eacute;"): a navegação da Mesa precisa ser lida
const navEnt = T.lerMesa(ler("mesa_manifestacao.html").replace("exibindo de 1 até 20", "exibindo de 21 at&eacute; 39").replace("23 registro(s)", "39 registro(s)"));
ok(navEnt.total === 39 && navEnt.de === 21 && navEnt.ate === 39, "navegação com &eacute;: " + JSON.stringify([navEnt.total, navEnt.de, navEnt.ate]));
ok(T.texto("Juntar MANIFESTA&Ccedil;&Atilde;O referente ao movimento - JUNTADA DE CERTID&Atilde;O") === "Juntar MANIFESTAÇÃO referente ao movimento - JUNTADA DE CERTIDÃO", "entidades maiúsculas (&Ccedil; &Atilde;)");
ok(T.texto("Execu&ccedil;&atilde;o &amp; &uacute;ltimo &ordm; &laquo;x&raquo; &yuml;") === "Execução & último º «x» ÿ", "entidades do Latin-1");
const pendEnt = T.lerPendencias('<fieldset id="quadroPendencias"><legend>Pend&ecirc;ncias</legend>Juntar MANIFESTA&Ccedil;&Atilde;O referente ao movimento - JUNTADA DE CERTID&Atilde;O ( 13 de outubro de 2026 &agrave;s 17:31 )</fieldset>');
ok(pendEnt.length === 1 && pendEnt[0].movimento === "JUNTADA DE CERTIDÃO" && pendEnt[0].hora === "17:31", "pendência com entidades: " + JSON.stringify(pendEnt));

// ---- final do nº
ok(T.finalDoNumero("0011147-54.2016.8.12.0001") === 7, "final: o último algarismo antes do traço");
ok([...T.faixasFinal("0-2")].join() === "0,1,2", "0-2 = finais 0, 1 e 2");
ok([...T.faixasFinal("0-2, 5, 7 a 9")].join() === "0,1,2,5,7,8,9", "faixas com vírgula e 'a'");
ok([...T.faixasFinal("3 até 4")].join() === "3,4" && [...T.faixasFinal("9-7")].join() === "7,8,9", "'até' e faixa invertida");
ok(T.faixasFinal("") === null && T.faixasFinal("xyz") === null, "sem faixa = sem filtro");
ok(T.faixaTexto(new Set([0, 1, 2, 5])) === "0-2, 5" && T.faixaTexto(new Set([3, 4])) === "3, 4", "botões 0-9 -> texto da faixa");

// ---- processo intimado por certidão: lembra a última decisão
const p1 = T.lerProcesso(ler("processo_certidao.html"));
ok(p1.processo === "7000117-54.2016.8.12.0001" && !p1.login, "nº do processo na página");
ok(p1.pendencias.length === 1 && p1.pendencias[0].juntar === "MANIFESTAÇÃO" && p1.pendencias[0].movimento === "JUNTADA DE CERTIDÃO" &&
   p1.pendencias[0].data === "13/10/2026" && p1.pendencias[0].hora === "17:31", "pendência: " + JSON.stringify(p1.pendencias[0]));
ok(p1.movimentos.length === 10, "10 movimentos: " + p1.movimentos.length);
const m29 = p1.movimentos.find((m) => m.seq === 29);
ok(m29 && m29.nome === "JUNTADA DE CERTIDÃO" && m29.data === "13/10/2026" && m29.hora === "17:31:27" && m29.papel === "SERVIDOR" &&
   m29.ajax === "https://seeu.pje.jus.br/seeu/processo/movimentacaoArquivoDocumento.do?_tj=f0f0f0a2" && m29.autor === "Servidor Exemplo", "movimento da certidão: " + JSON.stringify(m29));
const m28 = p1.movimentos.find((m) => m.seq === 28);
ok(m28.semArquivo && !m28.ajax && m28.complemento === "Incidente 1 - FIXAÇÃO/ALTERAÇÃO DE REGIME cadastrado", "ato ordinatório sem arquivo e complemento");
const e1 = T.escolher(p1, "Manifestação");
ok(e1.motivo && e1.motivo.seq === 29, "motivo = certidão seq. 29");
ok(p1.movimentos.find((m) => m.seq === 9).papel === "JUIZ" && p1.movimentos.find((m) => m.seq === 12).papel === "JUIZ" && p1.movimentos.find((m) => m.seq === 33).papel === "PROMOTOR", "papel de quem praticou o ato (JUIZ, PROMOTOR)");
ok(e1.decisao && e1.decisao.seq === 9 && e1.decisao.nome === "PROFERIDO DESPACHO DE MERO EXPEDIENTE", "última decisão = despacho seq. 9 (não a remessa automática do juiz, seq. 12)");
ok(e1.merito === null, "sem decisão de mérito anterior");
ok(e1.desde.map((m) => m.seq).join() === "19,28,29,33", "desde a decisão, sem remessas e confirmações: " + e1.desde.map((m) => m.seq).join());
ok(T.tipoDoMotivo(e1.pendencia.movimento) === "Certidão", "tipo do motivo");

// ---- processo intimado pelo próprio despacho: mostra também a última decisão de mérito
const p2 = T.lerProcesso(ler("processo_despacho.html"));
const e2 = T.escolher(p2, "Manifestação");
ok(e2.motivo && e2.motivo.seq === 160 && e2.decisao && e2.decisao.seq === 160, "motivo e última decisão = despacho seq. 160");
ok(e2.merito && e2.merito.seq === 151 && e2.merito.nome === "DECISÃO INTERLOCUTÓRIA DE MÉRITO", "mérito anterior = seq. 151");
ok(!T.ehAtoDoJuiz(p2.movimentos.find((m) => m.seq === 131)), "expedição de intimação do juiz não é decisão");
ok(T.pendenciaDaAba([{ juntar: "CIÊNCIA" }, { juntar: "MANIFESTAÇÃO" }], "Manifestação").juntar === "MANIFESTAÇÃO", "pendência da aba");
ok(T.pendenciaDaAba([{ juntar: "CIÊNCIA" }, { juntar: "MANIFESTAÇÃO" }], "Ciência").juntar === "CIÊNCIA", "pendência da aba Ciência");

// ---- lista de arquivos do movimento
const arqs = T.lerArquivos(ler("arquivos_movimento.html"));
ok(arqs.length === 2, "2 arquivos (o menu 'Versão assinada/original' não conta): " + arqs.length);
ok(arqs[0].ordem === "160.1" && arqs[0].descricao === "Despacho" && arqs[0].tipo === "Outros Documentos" && arqs[0].nome === "online.pdf" &&
   arqs[0].assinatura === "Juiz Exemplo (certificado por SEEU)", "arquivo principal: " + JSON.stringify(arqs[0]));
ok(arqs[0].url === "https://seeu.pje.jus.br/seeu/arquivo.do?_tj=c0ffee03", "link de download do PDF carimbado");
ok(T.arquivoPrincipal(arqs).ordem === "160.1" && T.arquivoPrincipal([]) === null, "arquivo principal = .1");

// ---- texto do PDF: trechos em negrito fora de ordem voltam para o lugar
const it = (str, x, y, w) => ({ str, transform: [12, 0, 0, 12, x, y], width: w, height: 12 });
const itens = [
  it("Vistos,", 200, 700, 40),
  it("Considerando as violações, ", 100, 680, 160), it("para que, ", 100, 665, 55), it("em até 5 dias", 160, 665, 75),
  it(", apresente justificativa, sob pena de internação cautelar.", 236, 665, 300), it("intime-se a defesa", 265, 680, 110),
  { str: "Documento assinado digitalmente", transform: [0, 12, -12, 0, 580, 300], width: 200, height: 12 },
];
const txt = T.itensParaTexto(itens);
ok(txt.split("\n")[1] === "Considerando as violações, intime-se a defesa", "negrito na ordem: " + JSON.stringify(txt.split("\n")[1]));
ok(txt.split("\n")[2] === "para que, em até 5 dias, apresente justificativa, sob pena de internação cautelar.", "linha com negrito no meio: " + JSON.stringify(txt.split("\n")[2]));

// ---- leitura do documento e alertas (texto fictício no formato do PDF carimbado do SEEU)
const despacho = [
  "SEEU - Processo: 7000333-10.2014.8.12.0008 - Assinado digitalmente por Juiz Exemplo (certificado por SEEU)",
  "[160.1] PROFERIDO DESPACHO DE MERO EXPEDIENTE - Despacho em 02/10/2026",
  "PODER JUDICIÁRIO", "TJMS - COMARCA DE CAMPO GRANDE", "2ª VARA DE EXECUÇÃO PENAL DE CAMPO GRANDE", "Autos nº. 7000333-10.2014.8.12.0008",
  "Processo nº: 7000333-10.2014.8.12.0008", "Classe Processual: Execução da Pena", "Assunto Principal: Medidas de Segurança",
  "Autoridade(s): AUTORIDADE EXEMPLO", "Executado(s): Ciclano Exemplo", "Vistos,",
  "Considerando as violações noticiadas no evento 152.1, intime-se a defesa",
  "para que, em até 5 dias, apresente justificativa para o descumprimento do monitoramento eletrônico, sob",
  "pena de suspensão da medida de segurança e decretação da internação cautelar do sentenciado.",
  "Decorrido o prazo, com ou sem manifestação, ao MP e conclusos.", "Cumpra-se com urgência.", "Intimem-se.",
  "Campo Grande, 01 de outubro de 2026.", "Juiz Exemplo", "Juiz de Direito", "(assinado por certificação digital)",
  "Documento assinado digitalmente, conforme MP nº 2.200-2/2001, Lei nº 11.419/2006.Validação em https://seeu.pje.jus.br/seeu/ - Identificador: XX",
].join("\n");
const d = T.lerDocumento(despacho);
ok(d.carimbo && d.carimbo.ordem === "160.1" && d.carimbo.descricao === "Despacho" && d.carimbo.data === "02/10/2026", "carimbo do SEEU");
ok(d.corpo.startsWith("Considerando as violações") && d.corpo.endsWith("Intimem-se.") && !/Juiz de Direito|Classe Processual|Validação/.test(d.corpo), "corpo sem cabeçalho e assinatura: " + d.corpo.slice(0, 80));
ok(/intime-se a defesa para que, em até 5 dias/.test(d.corpo), "linhas quebradas juntadas");
const al = d.alertas.map((x) => x.txt);
ok(al.includes("Risco: internação, suspensão") && al.includes("Justificativa da defesa") && al.includes("Prazo no texto: 5 dias") && al.includes("Urgente"), "alertas: " + al.join(" | "));
ok(d.temas.includes("monitoramento") && d.temas.includes("medida de segurança"), "temas: " + d.temas.join(", "));
const neg = T.lerDocumento("Vistos,\nTrata-se de pedido de progressão de regime.\nAnte o exposto, INDEFIRO o pedido de progressão ao regime semiaberto.\nIntimem-se.\nCampo Grande, 3 de outubro de 2026.\nJuiz de Direito");
ok(neg.alertas.some((x) => /Indeferimento/.test(x.txt)) && neg.temas.includes("progressão") && /^Ante o exposto, INDEFIRO/.test(neg.resumo), "indeferimento e dispositivo: " + neg.resumo);
const aud = T.analisarTexto("Designo audiência de justificação para o dia 12/11/2026, às 14h30, intimando-se o sentenciado.");
ok(aud.alertas.some((x) => x.txt === "Audiência 12/11/2026 às 14:30"), "audiência com data e hora: " + JSON.stringify(aud.alertas));
const cert = T.lerDocumento("PODER JUDICIÁRIO\nCERTIDÃO\nCERTIFICO que o sentenciado não compareceu para assinar em juízo nos meses de agosto e setembro.\nCampo Grande, 13 de outubro de 2026.");
ok(/^CERTIFICO que o sentenciado não compareceu/.test(cert.resumo), "certidão: resumo a partir de CERTIFICO: " + cert.resumo);
ok(T.lerDocumento("   ").semTexto, "PDF escaneado (sem texto)");
ok(T.analisarTexto("Ante o exposto, DEFIRO a progressão.").alertas.some((x) => x.nivel === "info"), "deferimento");

// ---- providência sugerida (no lugar dos alertas)
const mov = (nome, data, cargo) => ({ seq: 1, nome, data, cargo: cargo || "" });
const PV = (a, aba) => T.providencia(a, aba);
let pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "PROFERIDO DESPACHO DE MERO EXPEDIENTE" }, mesma: true,
  motivo: mov("PROFERIDO DESPACHO DE MERO EXPEDIENTE", "02/10/2026"), decisao: Object.assign(mov("PROFERIDO DESPACHO DE MERO EXPEDIENTE", "02/10/2026"), { doc: d }) }, "Manifestação");
ok(pv.texto === "Requerer a intimação pessoal do sentenciado para justificar – sob pena de internação, suspensão (prazo no texto: 5 dias)" && pv.tipo === "Intimação pessoal" && pv.urgente, "justificativa -> intimação pessoal: " + JSON.stringify(pv));
const certGr = T.lerDocumento("CERTIDÃO\nCERTIFICO, para os devidos fins, que em consulta ao SAJ, autos nº 0900000-00.2026.8.12.0001, constatei sentença condenatória [2 anos em regime aberto], mas sem GR expedida até o momento.\nCampo Grande, 20 de outubro de 2026.");
pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "JUNTADA DE CERTIDÃO" }, motivo: Object.assign(mov("JUNTADA DE CERTIDÃO", "20/10/2026"), { doc: certGr }),
  decisao: Object.assign(mov("PROFERIDO DESPACHO DE MERO EXPEDIENTE", "14/10/2026"), { doc: T.lerDocumento("Vistos,\nCiente da informação. Ao MP e à defesa.\nCampo Grande, 14 de outubro de 2026.\nJuiz de Direito") }) }, "Manifestação");
ok(pv.tipo === "Certidão" && /nova condenação\/guia/.test(pv.texto) && !pv.urgente, "certidão de nova condenação sem GR: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "JUNTADA DE CERTIDÃO" }, motivo: Object.assign(mov("JUNTADA DE CERTIDÃO", "13/10/2026"), { doc: cert }) }, "Manifestação");
ok(pv.texto.startsWith("Requerer a intimação pessoal do sentenciado sobre o descumprimento") && pv.tipo === "Intimação pessoal" && pv.urgente, "certidão de não comparecimento: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "DECISÃO INTERLOCUTÓRIA DE MÉRITO" }, mesma: true, motivo: mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"),
  decisao: Object.assign(mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"), { doc: neg }) }, "Manifestação");
ok(pv.texto === "Avaliar agravo em execução contra a decisão de 03/10/2026" && pv.tipo === "Agravo" && pv.urgente, "indeferimento: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "CIÊNCIA", movimento: "DECISÃO INTERLOCUTÓRIA DE MÉRITO" }, mesma: true, motivo: mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"),
  decisao: Object.assign(mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"), { doc: T.lerDocumento("Vistos,\nAnte o exposto, DEFIRO a progressão ao regime aberto.\nCampo Grande, 3 de outubro de 2026.") }) }, "Ciência");
ok(pv.texto === "Dar ciência" && !pv.urgente, "ciência de decisão favorável: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "CIÊNCIA", movimento: "DECISÃO INTERLOCUTÓRIA DE MÉRITO" }, mesma: true, motivo: mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"),
  decisao: Object.assign(mov("DECISÃO INTERLOCUTÓRIA DE MÉRITO", "03/10/2026"), { doc: neg }) }, "Ciência");
ok(pv.tipo === "Agravo" && /depois dar ciência/.test(pv.texto), "ciência de indeferimento: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "JUNTADA DE MANIFESTAÇÃO" }, motivo: Object.assign(mov("JUNTADA DE MANIFESTAÇÃO", "16/10/2026", "Membro(a) do Ministério Público"),
  { doc: T.lerDocumento("O Ministério Público opina pelo indeferimento do pedido de livramento condicional, por ausência de requisito subjetivo.") }) }, "Manifestação");
ok(pv.tipo === "Parecer do MP" && pv.texto.startsWith("Manifestar sobre o parecer do MP"), "parecer do MP: " + JSON.stringify(pv));
pv = PV({ pendencia: { juntar: "MANIFESTAÇÃO", movimento: "JUNTADA DE CERTIDÃO" }, motivo: Object.assign(mov("JUNTADA DE CERTIDÃO", "13/10/2026"), { doc: { erro: "falhou", alertas: [] } }) }, "Manifestação");
ok(pv.texto === "Manifestar sobre a certidão" && pv.tipo === "Certidão", "certidão não lida: " + JSON.stringify(pv));
ok(T.urgencia({ ultimoDia: "30/10/2026" }, { providencia: { urgente: true } }, "21/10/2026") < T.urgencia({ ultimoDia: "22/10/2026" }, { providencia: { urgente: false }, alertas: [{ nivel: "alto" }] }, "21/10/2026"), "prioridade pela providência urgente");

// ---- endereços que a triagem pode pedir ao SEEU (só leitura)
const P = A.pedidoTriagemPermitido;
ok(P("/seeu/usuario/mesaDefensor1Grau.do?actionType=listar&finalidadeRemessa=2&situacao=1&pageNumber=2", "GET") === "", "Mesa: lista");
ok(P("/seeu/usuario/mesaDefensor1Grau.do?actionType=listar", "POST", "org.apache.struts.taglib.html.TOKEN=x&pageNumber=2&finalidadeRemessa=5&situacao=1") === "", "Mesa: página pelo formulário");
ok(P("/seeu/usuario/mesaDefensor1Grau.do?actionType=listar", "POST", "pageNumber=2&vistas=123") !== "", "Mesa: 'vistas' (leitura de prazo) recusado");
ok(P("/seeu/usuario/mesaDefensor1Grau.do?actionType=realizarLeitura", "GET") !== "", "Mesa: outra ação recusada");
ok(P("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?_tj=aa11bb22", "GET") === "", "processo pelo link do nº");
ok(P("/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabMovimentacoesProcesso", "GET") === "", "aba Movimentações");
ok(P("/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=70001175420168120001", "GET") === "", "processo pelo nº (como o lote)");
ok(P("/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=123", "GET") !== "" && P("/seeu/visualizacaoProcesso.do?actionType=visualizar&numeroUnico=70001175420168120001&x=1", "GET") !== "", "nº inválido ou parâmetro a mais recusado");
ok(P("/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=tabPeticao", "GET") !== "", "outra aba recusada");
ok(P("/seeu/processo/movimentacaoArquivoDocumento.do?_tj=f0f0", "POST", "tipoLayout=1") === "", "lista de arquivos");
ok(P("/seeu/processo/movimentacaoArquivoDocumento.do?_tj=f0f0", "POST", "tipoLayout=1&x=2") !== "", "lista de arquivos: outro corpo recusado");
ok(P("/seeu/arquivo.do?_tj=c0ffee03", "GET") === "", "PDF do movimento");
ok(P("/seeu/processo/preAnalise.do?_tj=aa11", "GET") !== "", "Analisar (preAnalise) recusado");
ok(P("/seeu/processo/preAnalise.do?_tj=aa11", "POST", "") !== "", "Analisar por POST recusado");
ok(P("/seeu/usuario/mesaDefensor1Grau.do?actionType=listar&dispensarJuntada=1", "GET") !== "", "Dispensar Juntada recusado");
ok(P("https://seeu.pje.jus.br.evil.com/seeu/arquivo.do?_tj=aa", "GET") !== "" && P("http://seeu.pje.jus.br/seeu/arquivo.do?_tj=aa", "GET") !== "", "outro domínio ou http recusado");
ok(P("/seeu/arquivo.do?_tj=c0ffee03", "POST", "a=1") !== "", "PDF por POST recusado");

// ---- planilha
const bytes = T.xlsx([["Final", "Processo", "Texto"], [7, "7000117-54.2016.8.12.0001", "linha <com> & \"aspas\" e acentuação"]], [6, 26, 40], "Triagem");
ok(bytes[0] === 0x50 && bytes[1] === 0x4b && bytes.length > 1500, "xlsx é um zip");
ok(T.crc32(new TextEncoder().encode("123456789")) === 0xcbf43926, "crc32");
ok(T.colunaLetra(0) === "A" && T.colunaLetra(25) === "Z" && T.colunaLetra(26) === "AA", "letras das colunas");
if (process.argv[2]) fs.writeFileSync(process.argv[2], bytes);

// ---- prioridade
const alto = { alertas: [{ nivel: "alto", txt: "x" }] };
ok(T.urgencia({ ultimoDia: "30/10/2026" }, alto, "21/10/2026") < T.urgencia({ ultimoDia: "22/10/2026" }, { alertas: [] }, "21/10/2026"), "alerta vermelho antes do prazo");
ok(T.urgencia({ ultimoDia: "22/10/2026" }, null, "21/10/2026") < T.urgencia({ ultimoDia: "25/10/2026" }, null, "21/10/2026"), "prazo mais próximo antes");

// ---- proteção do prazo
const movs = [
  { seq: 60, nome: "JUNTADA DE CERTIDÃO", complemento: "" },
  { seq: 61, nome: "CONFIRMADA A INTIMAÇÃO ELETRÔNICA", complemento: "Referente ao evento (seq. 58)" },
];
ok(T.novaConfirmacao(movs, 61).length === 0, "nada novo depois da leitura: sem alarme");
ok(T.novaConfirmacao(movs, 60).length === 1, "confirmação de intimação nova: alarme");
ok(T.novaConfirmacao([{ seq: 62, nome: "CONFIRMADA A INTIMAÇÃO ELETRÔNICA", complemento: "MINISTÉRIO PÚBLICO" }], 61).length === 0, "confirmação do MP não conta");
ok(T.novaConfirmacao([{ seq: 62, nome: "JUNTADA DE PETIÇÃO", complemento: "" }], 61).length === 0, "movimento novo comum não conta");
const lidos = [{ aba: "2", processo: "A" }, { aba: "2", processo: "B" }, { aba: "5", processo: "A" }];
const sairam = T.sairamDaMesa(lidos, [{ aba: "2", processo: "A" }, { aba: "5", processo: "B" }]);
ok(sairam.length === 2 && sairam[0].processo === "B" && sairam[1].aba === "5", "processos que saíram da Mesa (por aba e nº)");
ok(T.sairamDaMesa(lidos, lidos).length === 0, "todos continuam: nenhum saiu");

if (falhas) { console.log(falhas + " falha(s)"); process.exit(1); }
console.log("ok: triagem da Mesa (Mesa, processo, arquivos, PDF, decisão, alertas, filtros, endereços permitidos, planilha)");
