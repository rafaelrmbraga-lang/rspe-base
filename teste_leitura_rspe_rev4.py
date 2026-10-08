"""Teste de regressão da leitura do RSPE (revisão 4 da leitura, VERSAO_LEITURA_RSPE = 4), com trechos reais dos RSPEs da
conferência: marcadores "(Extinta)(Comutada)" e "(Indultada)(Comutada)", vara em duas linhas, medida de segurança sem rótulo,
nota depois da data prevista, bloco de sentença repetido, tribunal pelo número CNJ e "Não informado" na mãe e no RG.
Rodar: python teste_leitura_rspe_rev4.py"""
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs
import rspe_view as rv

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


CRIME = """Lei: 2848/40 - Código Penal
Artigo da Lei: ART 155: Furto
Pena:CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., Reclusão: 1 a 4 anos E Multa
Pena Imposta: 1 ano(s), 4 mês(es) e 0 dia(s)
Data da infração: 28/08/2012 Violência ou grave ameaça: N Resultado morte: N
Reincidente comum: Reincidente específico: N
Condenado por exercer comando de organização criminosa:N
Fração adotada no cálculo para progressão de regime: 1/6 - Comum
Fração adotada no cálculo para livramento condicional: 1/2 - Comum Reincidente
Extinto:Não Data da extinção: Suspenso: Não Data de suspensão:
"""


def acao(numero, vara="Juízo/Vara de condenação: Aquidauana, Vara Criminal - Infância e Juventude", sentenca=None, crimes=CRIME):
    sentenca = sentenca if sentenca is not None else "SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)\nPena total: 1a4m0d - PENA ORIGINÁRIA\nRegime imposto na sentença/acórdão:Fechado\nDESMEMBRAMENTO(S)\n"
    return ("Número: %s\nTipo: ACAO PENAL\n%s\nData do recebimento da denúncia: 29/08/2013\nData da Sentença: 25/05/2015\n"
            "Data do trânsito em julgado do Ministério Público: 01/06/2015\nData do trânsito em julgado do processo: 08/06/2015\n"
            "Observação: Não informado\n%s%s") % (numero, vara, sentenca, crimes)


# A1: todos os marcadores ao lado do número (Cleovan Barbosa de Lima_outras ações, Juliano, Rubens)
cs = rs.parse_crimes(acao("0000015-03.0000.6.40.0000 (Indultada)(Comutada)") + acao("0001234-56.2015.8.12.0005 (Extinta)(Indultada)(Comutada)")
                     + acao("0003610-97.2013.8.12.0005 (Indultada)") + acao("0003643-14.2018.8.12.0005"))
ok([c["processo_situacao"] for c in cs] == ["Indultada, Comutada", "Extinta, Indultada, Comutada", "Indultada", ""], "A1 marcadores: %r" % [c["processo_situacao"] for c in cs])
ok([c["processo_criminal"] for c in cs] == ["0000015-03.0000.6.40.0000", "0001234-56.2015.8.12.0005", "0003610-97.2013.8.12.0005", "0003643-14.2018.8.12.0005"],
   "A1 número sem os marcadores: %r" % [c["processo_criminal"] for c in cs])
# o processo "(Indultada)(Comutada)" é extinto, mesmo com comutação concedida depois do indulto (sem cair em indulto_duvida)
r = {"status_execucao": "ATIVO", "pena_remanescente": "1a0m0d", "versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE}
inc = [{"tipo": "INDULTO", "situacao": "CONCEDIDO", "data_decisao": "10/05/2019", "complemento": "Decreto 9.246/2017",
        "processos": "0000015-03.0000.6.40.0000"},
       {"tipo": "COMUTAÇÃO", "situacao": "CONCEDIDO", "data_decisao": "10/05/2021", "complemento": "", "processos": "0000015-03.0000.6.40.0000"}]
rs.aplicar_extincoes(r, cs, inc)
ok(cs[0]["extinto"] == "Sim" and cs[0].get("extincao_motivo") == "indulto" and not cs[0].get("indulto_duvida"),
   "A1 (Indultada)(Comutada) extinto: %r %r" % (cs[0]["extinto"], cs[0].get("indulto_duvida")))
ok(cs[1]["extinto"] == "Sim" and cs[2]["extinto"] == "Sim" and cs[3]["extinto"] == "Não", "A1 (Extinta)… extinto")
ok('"(Indultada)(Comutada)"' in cs[0]["extincao_fonte"], "A1 fonte: %r" % cs[0]["extincao_fonte"])

# A2: vara em duas linhas (Diego Rodrigues Neto; JORGE ALEXANDER RIBERA PEREZ)
cs = rs.parse_crimes(acao("0011675-62.2012.8.16.0019", vara="6477 - 2º Juizado de Violência Doméstica e Familiar Contra a Mulher e Vara de\n"
                          "Juízo/Vara de condenação: Crimes Contra Crianças, Adolescentes e Idosos de Ponta Grossa")
                     + acao("5001564-09.2024.4.03.6000", vara="3ª Vara Federal de Campo Grande com Juizado Especial Federal Criminal Adjunto -\n"
                            "Juízo/Vara de condenação: TRF3")
                     + acao("0001640-17.2022.8.12.0015", vara="Juízo/Vara de condenação: Miranda, 1ª Vara")
                     + acao("0000253-93.2024.8.12.0015", vara="Juízo/Vara de condenação:"))
ok(cs[0]["vara_condenacao"] == "6477 - 2º Juizado de Violência Doméstica e Familiar Contra a Mulher e Vara de Crimes Contra Crianças, Adolescentes e Idosos de Ponta Grossa",
   "A2 Diego: %r" % cs[0]["vara_condenacao"])
ok(cs[1]["vara_condenacao"] == "3ª Vara Federal de Campo Grande com Juizado Especial Federal Criminal Adjunto - TRF3", "A2 Jorge: %r" % cs[1]["vara_condenacao"])
ok(cs[2]["vara_condenacao"] == "Miranda, 1ª Vara" and cs[3]["vara_condenacao"] == "", "A2 vara de uma linha / vazia: %r %r" % (cs[2]["vara_condenacao"], cs[3]["vara_condenacao"]))

# A3: medida de segurança sem os rótulos "Pena total:" e "Regime imposto…" (KEMOEL, PATRICK, Fernando A. D. Miranda)
cs = rs.parse_crimes(acao("0001953-80.2019.8.12.0015", sentenca="SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)\n1a0m0d - MEDIDA DE SEGURANÇA\nIndefinido\nDESMEMBRAMENTO(S)\n")
                     + acao("0000529-95.2018.8.12.0028", sentenca="SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)\n1a0m0d - MEDIDA DE SEGURANÇA\nAberto\nDESMEMBRAMENTO(S)\n")
                     + acao("0802025-42.2022.8.12.0043", sentenca="SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)\n1a0m0d - MEDIDA DE SEGURANÇA\nDESMEMBRAMENTO(S)\n"))
ok((cs[0]["pena_total_processo"], cs[0]["regime_sentenca"]) == ("1a0m0d - MEDIDA DE SEGURANÇA", "Indefinido"), "A3 KEMOEL: %r" % ((cs[0]["pena_total_processo"], cs[0]["regime_sentenca"]),))
ok(cs[1]["regime_sentenca"] == "Aberto", "A3 PATRICK regime")
ok((cs[2]["pena_total_processo"], cs[2]["regime_sentenca"]) == ("1a0m0d - MEDIDA DE SEGURANÇA", ""), "A3 sem regime: %r" % cs[2]["regime_sentenca"])
cs = rs.parse_crimes(acao("0003643-14.2018.8.12.0005"))
ok((cs[0]["pena_total_processo"], cs[0]["regime_sentenca"]) == ("1a4m0d - PENA ORIGINÁRIA", "Fechado"), "A3 rótulo comum intacto")

# A7: bloco de sentença repetido pelo SEEU (RAUL DA SILVA FAINELO, 0000794-74.2015.8.12.0005)
sent = "SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)\nPena total: 4a9m5d - PENA ORIGINÁRIA\nRegime imposto na sentença/acórdão:Fechado\nDESMEMBRAMENTO(S)\n"
furto = CRIME.replace("CAPUT: Subtrair", "§ 4º: A pena é de reclusão de dois a oito anos").replace("1 ano(s), 4 mês(es) e 0 dia(s)", "4 ano(s), 9 mês(es) e 5 dia(s)")
rep = sent + furto + "Pena total: 4a9m5d - PENA ORIGINÁRIA\nRegime imposto na sentença/acórdão:Fechado\nDESMEMBRAMENTO(S)\n"
cs = rs.parse_crimes(acao("0000794-74.2015.8.12.0005", sentenca=rep, crimes=furto) + acao("0002079-73.2013.8.12.0005 (Indultada)"))
ok(len(cs) == 2 and cs[0]["pena_imposta"].startswith("4 ano") and cs[1]["processo_criminal"] == "0002079-73.2013.8.12.0005", "A7 RAUL: %d crimes" % len(cs))
# concurso legítimo (dois crimes iguais no mesmo bloco) continua com os dois
cs = rs.parse_crimes(acao("0000001-00.2015.8.12.0005", crimes=CRIME + CRIME))
ok(len(cs) == 2, "A7 concurso legítimo")
# segundo bloco de sentença diferente (outra pena) fica
cs = rs.parse_crimes(acao("0000002-00.2015.8.12.0005", sentenca=sent, crimes=furto + "Pena total: 1a4m0d - APELAÇÃO CRIMINAL\nRegime imposto na sentença/acórdão:Fechado\nDESMEMBRAMENTO(S)\n" + CRIME))
ok(len(cs) == 2, "A7 bloco diferente fica")

# A4: nota depois da data prevista (MARIANO ROCHA SIQUEIRA; Deivide Andrade Santos; "Em trâmite"; "Em livramento condicional")
calc = """Regime Atual: Fechado - ATIVO
CÁLCULOS PARA PROGRESSÃO DE REGIME:
Data-base adotada no cálculo para progresso regime: 06/10/2022
Data prevista para progressão de regime: 02/06/2029 (Indeferido em 10/01/2026)
CÁLCULOS PARA LIVRAMENTO CONDICIONAL:
Data-base adotada no cálculo para livramento condicional: 13/09/2016
Data prevista livramento condicional: 03/02/2038 (Existe falta grave nos últimos 12 meses em 05/12/2025)
"""
ok(rs._previsao_seeu(calc, ("Data prevista para progressão de regime",)) == ("02/06/2029", "", "Indeferido em 10/01/2026"), "A4 progressão")
ok(rs._previsao_seeu(calc, ("Data prevista livramento condicional", "Data prevista para livramento condicional"))
   == ("03/02/2038", "", "Existe falta grave nos últimos 12 meses em 05/12/2025"), "A4 livramento")
ok(rs._previsao_seeu("Data prevista para progressão de regime: (Regime aberto desde 10/10/2024)\n", ("Data prevista para progressão de regime",))
   == ("", "Regime aberto desde 10/10/2024", ""), "A4 observação só entre parênteses (sem mudança)")
ok(rs._previsao_seeu("Data prevista para progressão de regime: 02/06/2029\n", ("Data prevista para progressão de regime",)) == ("02/06/2029", "", ""), "A4 sem nota")
ok(rs._previsao_seeu("Data prevista para livramento condicional: 01/01/2030 (Indeferido em 20/04/2026)\n",
                     ("Data prevista livramento condicional", "Data prevista para livramento condicional")) == ("01/01/2030", "", "Indeferido em 20/04/2026"),
   "A4 rótulo alternativo do livramento")
ok(rv._com_nota("", "Indeferido em 10/01/2026") == "RSPE: Indeferido em 10/01/2026", "A4 nota sem situação")
ok(rv._com_nota("Em 30 dias", "Em trâmite desde 01/09/2026") == "Em 30 dias · RSPE: Em trâmite desde 01/09/2026", "A4 nota com situação")
# "Em trâmite desde …" conta como pedido: o vencido não vira "sem pedido no RSPE - requerer"
venc = rv.HOJE - timedelta(days=40)
sc = ("Vencido há 40 dias · %s" % rv.VERIFICAR_VENCIDO, "vencido")
ok("sem pedido" in rv._vencido_pedido({"_incidentes": []}, sc, venc, "PROGRESS")[0], "A4 sem nota: sem pedido")
ok("sem pedido" not in rv._vencido_pedido({"_incidentes": [], "progressao_nota": "Em trâmite desde 01/09/2026"}, sc, venc, "PROGRESS")[0], "A4 em trâmite (progressão)")
ok("sem pedido" not in rv._vencido_pedido({"_incidentes": [], "livramento_nota": "Em trâmite desde 01/09/2026"}, sc, venc, "LIVRAMENTO")[0], "A4 em trâmite (livramento)")
ok("sem pedido" in rv._vencido_pedido({"_incidentes": [], "progressao_nota": "Indeferido em 10/01/2026"}, sc, venc, "PROGRESS")[0], "A4 indeferido não muda a regra")

# A9: tribunal pelo número quando o cabeçalho é "COMARCA DE X" (Cleberson, Deivide, Erismar, Francisco Neris, VINICIUS ALVES)
for num, trib in (("0012960-96.2014.8.22.0005", "TJRO"), ("5000372-26.2020.8.25.0086", "TJSE"), ("5001406-41.2025.8.10.0001", "TJMA"),
                  ("2000088-05.2025.8.11.0015", "TJMT"), ("0000001-00.2020.8.06.0001", "TJCE"), ("0000001-00.2020.8.12.0001", "TJMS"),
                  ("0000001-00.2020.8.07.0001", "TJDFT"), ("5001564-09.2024.4.03.6000", "TRF3"), ("0000001-00.2020.9.12.0001", ""), ("123", "")):
    ok(rs.tribunal_do_numero(num) == trib, "A9 %s -> %r" % (num, rs.tribunal_do_numero(num)))
ok(rs._comarca_fora_do_padrao("COMARCA DE JI-PARANÁ", "2ª VARA CRIMINAL DA COMARCA DE JI-PARANÁ") == ("", "JI-PARANÁ"), "A9 comarca (sem mudança)")

# A10: "Não informado" não é nome da mãe nem RG (MAYKON e outros)
cab = "Nome: Maykon José\nCPF: 12345678901\nRG: Não informado\nNome da Mãe: Não informado\nData de Nascimento: 01/01/1990\n"
ok(rs._sem_nao_informado(rs._campo_rg(cab)) == "" and rs._sem_nao_informado(rs.campo(cab, "Nome da Mãe")) == "", "A10 Não informado")
ok(rs._sem_nao_informado("Maria da Silva") == "Maria da Silva" and rs._sem_nao_informado("1989782") == "1989782", "A10 valor comum")

# versão: registro antigo recebe o aviso de reimportar; o atual não
ok(rs.VERSAO_LEITURA_RSPE >= 4, "versão da leitura")
for v in (1, 2, 3):
    ant = {"versao_leitura_rspe": v, "_crimes": [{"processo_criminal": "0000015-03.0000.6.40.0000", "processo_situacao": "Comutada", "pena_total_processo": ""}],
           "_incidentes": []}
    mot = rs.reimportar_motivos(ant)
    ok(any("nota do SEEU" in m for m in mot) and any("(Comutada)" in m for m in mot) and any("medida de segurança" in m for m in mot),
       "aviso de reimportar v%d: %r" % (v, mot))
ok(rs.reimportar_motivos({"versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE, "_crimes": []}) == [], "registro atual sem aviso")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("teste_leitura_rspe_rev4: ok")
