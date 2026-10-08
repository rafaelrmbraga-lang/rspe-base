"""Teste de regressão: erros da auditoria do indulto e da comutação (casos mínimos montados dos registros reais da base).
Rodar: python teste_indulto_auditoria.py (sai com código 1 se algum caso falhar)."""
import sys
from datetime import date

import rspe_decretos as rd
import rspe_ficha as rf
import rspe_regras as rg

HOJE = date(2026, 10, 7)
F = {f["id"]: f for f in rg.carregar()["decretos_fichas"]}
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)", vara="1ª Vara Criminal", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001",
          extinto="Não", data_extincao=None):
    c = {"processo_criminal": proc, "vara_condenacao": vara, "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr, "transito_processo": tr,
         "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "pena_total_processo": "PENA ORIGINÁRIA", "regime_sentenca": "Fechado",
         "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "extinto": extinto}
    if data_extincao:
        c["data_extincao"] = data_extincao
    return c


def preso(desde, motivo="PRISÃO DEFINITIVA"):
    return {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": motivo, "data": desde, "processos": ""}


def incidente(tipo, compl, data, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_decisao": data, "data_referencia": data, "situacao": sit, "processos": ""}


def dec(r, ano):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if x["id"] == ano)


# (2) ficha disciplinar não transforma "A VERIFICAR (tese: hediondez superveniente)" em POSSÍVEL
# (Antonio José Ribeiro da Penha, 0000897-87.2006.8.12.0008: art. 157, § 2º-A, I, fato de 2006, Decreto 12.790/2025)
r = {"_eventos": [preso("01/01/2015")],
     "indulto_2025": "A VERIFICAR (tese: hediondez superveniente): art. 9º, XI", "indulto_2025_status": "verificar",
     "indulto_2025_detalhe": "Situação em 25/12/2025: regime semiaberto · primário\n? XI: exige 1/4 e 5 saídas temporárias - verificar na ficha"}
ficha = {"eventos": [{"data": "%02d/0%d/2025" % (d, m), "texto": "SAÍDA CONFIRMADA DO BENEFÍCIO DE: SAÍDA TEMPORÁRIA"}
                     for d, m in ((5, 1), (5, 3), (5, 5), (5, 7), (5, 9))], "trabalho": [], "estudos": [], "exames": []}
rf.complementar_decretos(r, ficha, HOJE)
confere(r["indulto_2025_status"] == "verificar" and r["indulto_2025"].startswith("A VERIFICAR (tese: hediondez superveniente)"),
        "(2) tese de hediondez superveniente virou %r" % r["indulto_2025"])

# (3) indulto indeferido no RSPE e comutação não decidida: a comutação continua (Ricardo Luiz da Cruz, 0005465-91.2011.8.12.0002, 2023)
base = {"pena_total": "10a0m0d", "_eventos": [preso("01/01/2015")],
        "_crimes": [crime("01/01/2014", "01/06/2014", "01/07/2014", pena="10 ano(s), 0 mês(es) e 0 dia(s)")]}
x = dec(dict(base, _incidentes=[]), "2023")
confere(x["s"] == "cabe" and x.get("beneficio") == "Indulto", "(3) sem decisão, o indulto de 2023 devia caber: %s" % x)
x = dec(dict(base, _incidentes=[incidente("INDULTO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "06/02/2025", "NÃO CONCEDIDO")]), "2023")
confere(x["s"] == "cabe" and x.get("beneficio") == "Comutação" and "indeferido" in (x.get("ressalva") or ""),
        "(3) indulto 2023 indeferido escondeu a comutação: %s" % x)
x = dec(dict(base, _incidentes=[incidente("INDULTO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "06/02/2025", "NÃO CONCEDIDO"),
                                incidente("COMUTAÇÃO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "06/02/2025", "NÃO CONCEDIDO")]), "2023")
confere(x["s"] == "indef", "(3) comutação também indeferida: devia ficar indeferido, %s" % x)
# decreto de análise detalhada (Reginaldo Luciano da Silva, 0016091-88.2014.8.13.0471, 2024)
r = dict(base, _incidentes=[incidente("INDULTO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "15/10/2025", "NÃO CONCEDIDO")],
         indulto_2024="INDEFERIDO no RSPE em 15/10/2025", indulto_2024_status="nao",
         comutacao_2024="POSSÍVEL: art. 13 (1/5 do cumprido)", comutacao_2024_status="possivel")
x = dec(r, "2024")
confere(x["s"] == "cabe" and x.get("beneficio") == "Comutação", "(3) 2024: indulto indeferido escondeu a comutação: %s" % x)

# (6) art. 129, § 9º: a vítima pode ser de qualquer sexo - violência contra a mulher só provável
c9 = crime("01/01/2019", "01/06/2019", "01/07/2019", artigo="ART 129: Lesão corporal", tipo="§ 9º: Violência Doméstica, Detenção: 3 meses a 3 anos Sem Multa",
           pena="0 ano(s), 6 mês(es) e 0 dia(s)", proc="0000002-00.2019.8.12.0001")
confere((rd._vd(c9) or ("",))[0] == "provavel", "(6) art. 129, § 9º tomado como violência contra a mulher certa: %s" % (rd._vd(c9),))

# (7) Decreto 2023: violência contra a mulher em crime do Código Penal (Gilmar da Silva Oliveira, 6004104-22.2020.8.12.0001;
# Justo de Almeida Guilhen, 0002043-88.2019.8.12.0015)
r = {"pena_total": "4a0m0d", "_eventos": [preso("01/01/2020")], "_incidentes": [],
     "_crimes": [crime("01/01/2019", "01/06/2019", "01/07/2019", pena="3 ano(s), 6 mês(es) e 0 dia(s)"), c9]}
x = dec(r, "2023")
confere(x["s"] == "ver" and "violência contra a mulher" in x.get("mot", ""), "(7) 2023, art. 129 § 9º: devia ficar a verificar, %s" % x)
c147 = crime("01/01/2019", "01/06/2019", "01/07/2019", artigo="ART 147: Ameaça", tipo="CAPUT: Ameaçar alguém, Detenção: 1 a 6 meses ou Multa",
             pena="0 ano(s), 3 mês(es) e 0 dia(s)", vara="2ª Vara da Violência Doméstica e Familiar c/Mulher - Campo Grande")
x = dec(dict(r, _crimes=[c147]), "2023")
confere(x["s"] == "imp", "(7) 2023, art. 147 em vara de violência doméstica: devia ser impeditivo, %s" % x)

# (9) crime extinto depois da data do decreto estava em execução nela (Rubens Rafael Lopes Echeverria, 0001113-59.2008.8.12.0014;
# Igor Roberto Arruda, 6000009-67.2021.8.12.0015)
r = {"pena_total": "0a0m0d", "_eventos": [preso("01/01/2020")], "_incidentes": [],
     "_crimes": [crime("01/01/2019", "01/06/2019", "01/07/2019", pena="6 ano(s), 0 mês(es) e 0 dia(s)", extinto="Sim", data_extincao="26/06/2026")]}
x = dec(r, "2023")
confere(x["s"] != "fora", "(9) 2023 com o crime extinto em 2026: não podia ficar fora, %s" % x)
confere(x.get("detalhe", {}).get("cumprido", 0) > 1400, "(9) pena zerada no RSPE: o cumprido devia vir dos eventos, %s" % x.get("detalhe"))
r["_crimes"][0]["data_extincao"] = "10/09/2023"
x = dec(r, "2023")
confere(x["s"] == "fora", "(9) crime extinto antes da data do decreto devia ficar fora: %s" % x)

# (10) livramento condicional sem confirmação do SEEU: livramento seguido de nova prisão e regime atual sem livramento
# (Reginaldo Luciano da Silva, 2023: "Total Interrupções 9a2m5d", livramento revogado)
r = {"regime_atual": "Semiaberto - ATIVO", "_crimes": [],
     "_eventos": [preso("22/12/2016"), {"tipo": "INTERRUPÇÃO", "motivo": "LIVRAMENTO CONDICIONAL", "data": "09/03/2017", "processos": ""},
                  preso("09/12/2024", "PRISÃO EM FLAGRANTE")],
     "_incidentes": [incidente("LIVRAMENTO CONDICIONAL", "09/03/2017", "09/03/2017")]}
confere("livramento condicional desde 09/03/2017" in rd._lc_duvida(r, rd._ctx(r), date(2023, 12, 25)),
        "(10) livramento duvidoso não apontado: %r" % rd._lc_duvida(r, rd._ctx(r), date(2023, 12, 25)))

# (11) execução posterior ao decreto: o art. 5º de 2022 e o inciso XV de 2024/2025 não exigem cumprimento na data
# (Jhonatan Ariel dos Santos Valdez, 6000105-46.2025.8.12.0014; Robert Ximenes de Souza, 6000118-03.2025.8.12.0028)
r = {"pena_total": "1a0m0d", "_eventos": [preso("01/03/2025")], "_incidentes": [], "_crimes": [crime("01/01/2021", "01/06/2022", "01/07/2022")],
     "indulto_2022": "POSSÍVEL: art. 5º (todos os crimes com pena máxima ≤ 5 anos)", "indulto_2022_status": "possivel",
     "indulto_2024": "A VERIFICAR: art. 9º, XV - sem pena em cumprimento até 25/12/2024", "indulto_2024_status": "verificar",
     "comutacao_2024": "não se aplica", "indulto_2025": "não se aplica: sem pena em cumprimento em 25/12/2025", "indulto_2025_status": "nao"}
confere(dec(r, "2022")["s"] == "cabe", "(11) 2022, art. 5º, com execução posterior: %s" % dec(r, "2022"))
confere(dec(r, "2024")["s"] == "ver", "(11) 2024, inciso XV a verificar, com execução posterior: %s" % dec(r, "2024"))
r["_eventos"] = [preso("01/03/2026")]
confere(dec(r, "2025")["s"] == "fora", "(11) 2025 sem hipótese que dispense o cumprimento: devia ficar fora, %s" % dec(r, "2025"))

# (12) sem condenação até a publicação: "fora" (não alcançado) em todos os decretos, não "não cabe"
r = {"pena_total": "1a0m0d", "_eventos": [preso("01/01/2020")], "_incidentes": [], "_crimes": [crime("01/01/2019", "10/02/2026", "10/03/2026")],
     "indulto_2022": "não atinge: sentença posterior à publicação (STJ, AgRg no HC 441.551)", "indulto_2022_status": "nao",
     "indulto_2024": "não se aplica: sem condenação até 23/12/2024", "indulto_2024_status": "nao",
     "indulto_2025": "não se aplica: sem condenação até 23/12/2025", "indulto_2025_status": "nao"}
for ano in ("2022", "2023", "2024", "2025"):
    confere(dec(r, ano)["s"] == "fora", "(12) %s sem condenação até a publicação: %s" % (ano, dec(r, ano)))

# (13) roubo com lesão grave (art. 157, § 3º, I) anterior a 23/01/2020 não é hediondo nem cai no latrocínio (Luciano Trazzi,
# 0009390-79.2003.8.12.0001); depois da Lei 13.964/2019, é
import rspe_scraper as rs
c3 = crime("16/10/2000", "01/06/2001", "01/07/2001", artigo="ART 157: Roubo", tipo="§ 3º, I: (Até 22.01.2020) Se resulta lesão corporal grave, Reclusão: 7 a 18 anos E Multa")
confere(not rs.e_hediondo(c3), "(13) art. 157, § 3º, I, de 2000, tomado como hediondo")
confere(rs.e_hediondo(dict(c3, data_infracao="01/03/2021")), "(13) art. 157, § 3º, I, de 2021, devia ser hediondo")
confere(rs.e_hediondo(dict(c3, tipo_penal="§ 3º, II: Se resulta morte, Reclusão: 20 a 30 anos E Multa")), "(13) latrocínio de 2000 devia ser hediondo")

# (14) crime extinto sem data no RSPE: a data vem do incidente de indulto que cita o processo (Wilson Marcondes,
# 0022824-18.2015.8.12.0001: "(Indultada)", incidente INDULTO de 15/04/2026 com "592006"); sem incidente, em execução nos
# decretos anteriores ao RSPE, a verificar
ce = crime("01/01/2009", "01/06/2009", "01/07/2009", pena="8 ano(s), 0 mês(es) e 0 dia(s)", proc="0000000-00.0000.0.59.2006", extinto="Sim")
r = {"pena_total": "1a0m0d", "data_geracao_rspe": "02/10/2026", "_eventos": [preso("01/01/2010")],
     "_incidentes": [dict(incidente("INDULTO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "15/04/2026"), processos="592006")],
     "_crimes": [ce, crime("01/01/2009", "01/06/2009", "01/07/2009", pena="0 ano(s), 2 mês(es) e 0 dia(s)")]}
confere(rd._data_extincao(r, ce) == date(2026, 4, 15), "(14) data da extinção não veio do incidente: %s" % rd._data_extincao(r, ce))
x = dec(r, "2013")
confere(x.get("detalhe", {}).get("pena", 0) > 8 * 365, "(14) 2013: o crime extinto em 2026 saiu da soma: %s" % x.get("detalhe"))
x = dec(dict(r, _incidentes=[]), "2013")
confere(x.get("detalhe", {}).get("pena", 0) > 8 * 365 and "extinta sem data" in (x.get("mot", "") + (x.get("ressalva") or "")),
        "(14) extinto sem data: devia ficar na soma, a verificar: %s" % x)

# (15) sentença posterior ao trânsito (dado incoerente): fica na soma, a verificar (Luziano dos Santos, 0049107-59.2007.8.12.0001)
r = {"pena_total": "1a0m0d", "_eventos": [preso("01/01/2009")], "_incidentes": [],
     "_crimes": [crime("01/01/2008", "18/12/2014", "16/07/2008", pena="1 ano(s), 0 mês(es) e 0 dia(s)")]}
x = dec(r, "2010")
confere(x["s"] == "ver" and "sentença posterior ao trânsito" in x.get("mot", ""), "(15) 2010, sentença incoerente: %s" % x)

# (16) âncora do SEEU que zera com 180 dias ou mais de custódia pelos eventos: a verificar, com o cumprido pelos eventos
r = {"pena_total": "4a0m0d", "pena_cumprida": "0a1m0d", "data_geracao_rspe": "02/10/2026", "_incidentes": [],
     "_eventos": [preso("01/01/2009"), {"tipo": "INTERRUPÇÃO", "motivo": "FUGA", "data": "01/01/2025", "processos": ""}],
     "_crimes": [crime("01/01/2008", "01/06/2008", "01/07/2008", pena="4 ano(s), 0 mês(es) e 0 dia(s)")]}
x = dec(r, "2010")
confere(x["s"] == "ver" and "âncora" in x.get("mot", "") and x.get("detalhe", {}).get("cumprido", 0) > 700, "(16) âncora zerada: %s" % x)

# (17) crime doloso na janela da falta, durante a execução (LEP, art. 52): a verificar (Antonio Marcos dos Anjos, 2012)
r = {"pena_total": "4a0m0d", "_eventos": [preso("01/01/2011")], "_incidentes": [],
     "_crimes": [crime("01/01/2010", "01/06/2010", "01/07/2010", pena="2 ano(s), 0 mês(es) e 0 dia(s)"),
                 crime("06/05/2012", "01/06/2013", "01/07/2013", pena="2 ano(s), 0 mês(es) e 0 dia(s)", proc="0000002-00.2012.8.12.0001")]}
x = dec(r, "2012")
confere(x["s"] == "ver" and "LEP, art. 52" in x.get("mot", ""), "(17) crime doloso na janela: %s" % x)

# (18) Decreto 9.246/2017, art. 4º, II a IV: livramento encerrado por nova prisão (Jaime Sebastião Ortega de Barros) - a verificar
r = {"pena_total": "8a0m0d", "_crimes": [crime("01/01/2011", "01/06/2011", "01/07/2011", pena="8 ano(s), 0 mês(es) e 0 dia(s)")],
     "_eventos": [preso("01/07/2011"), {"tipo": "INTERRUPÇÃO", "motivo": "LIVRAMENTO CONDICIONAL", "data": "20/07/2012", "processos": ""},
                  preso("18/06/2014", "PRISÃO EM FLAGRANTE")],
     "_incidentes": [incidente("LIVRAMENTO CONDICIONAL", "20/07/2012", "20/07/2012")]}
x = dec(r, "2017")
confere(x["s"] == "ver" and "art. 4º, II a IV" in x.get("mot", ""), "(18) 2017, livramento interrompido por nova prisão: %s" % x)
x = dec(dict(r, _eventos=r["_eventos"][:2]), "2017")
confere("art. 4º, II a IV" not in x.get("mot", ""), "(18) 2017 sem indício: não podia vedar, %s" % x)

# (19) interrupção do cumprimento entra no motivo também quando o resultado já é "a verificar" (Rogério Feliciano, 2002, art. 1º, X)
_orig = rd._avaliar_ficha
rd._avaliar_ficha = lambda *a: {"id": "2002", "ref": "25/12/2002", "s": "ver", "mot": "requisitos de pena, tempo e regime atendidos", "_interr": True}
try:
    x = rd.avaliar_ficha(F["2002"], {}, {}, None, HOJE)
finally:
    rd._avaliar_ficha = _orig
confere(x["s"] == "ver" and x["mot"].startswith("cumprimento interrompido em 25/12/2002"), "(19) a verificar sem a interrupção no motivo: %s" % x)

# (20) regressão cautelar explicada pela ficha, sem homologação: não é falta com sanção reconhecida (art. 6º) (Patrick Luan
# Castilho Ferreira, 2024)
inc = dict(incidente("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão Cautelar", "20/06/2024"),
           _ficha_falta={"data": "21/06/2024", "texto": "Saída da Unidade Penal: PRESÍDIO, Destino: , Motivo: Evasão", "homologada": ""})
ach = rs.indicios_falta([inc], date(2024, 12, 23))
confere(ach and not ach[0][1] and "Destino: ," not in ach[0][0], "(20) regressão cautelar tomada como falta reconhecida: %s" % ach)
ach = rs.indicios_falta([dict(inc, _ficha_falta=dict(inc["_ficha_falta"], homologada="10/08/2024"))], date(2024, 12, 23))
confere(ach and ach[0][1], "(20) regressão cautelar com a falta homologada na ficha devia impedir: %s" % ach)
ach = rs.indicios_falta([incidente("HOMOLOGAÇÃO DE FALTA GRAVE", "19/11/2024", "19/11/2024")], date(2024, 12, 23))
confere(ach and "19/11/2024 (19/11/2024)" not in ach[0][0], "(20) data repetida no texto da falta: %s" % ach)

# (21) linha do tempo: rótulos C1, C2 não vão para a petição; motivo do art. 7º, p. ú., e não "Vedado (art. 1º)"
import rspe_indulto_tl as rtl
out = {"numero": "12.338/2024", "referencia": "25/12/2024", "id": "2024", "cumprido_txt": {"total": "4a1m22d"},
       "indulto": {"status": "nao", "rotulo": "Vedado (art. 1º)", "checklist": []},
       "imputacao": {"fracao": "2/3", "dispositivo": "art. 7º, parágrafo único", "crimes_imp": ["C1"], "crimes_liv": ["C2"], "pena_imp_txt": "6a5m0d",
                     "exigido_txt": "4a3m10d", "data": "04/02/2025", "imputado_liv": 0, "sobra_txt": "0a0m0d"}}
t = rtl._fundamentacao(out, "indulto", nomes={"C1": "art. 33 Lei 11.343/06", "C2": "art. 12 Lei 10.826/03"})
confere("C1" not in t and "C2" not in t and "art. 12 Lei 10.826/03" in t, "(21) rótulo interno no texto: %s" % t)
confere("Vedado (art. 1º)" not in t and "não estavam cumpridos" in t, "(21) conclusão pelo art. 1º com motivo do art. 7º, p. ú.: %s" % t)

# (22) cartão do decreto: "a verificar" só da comutação não põe o indulto como "a verificar" (Antonio José Ribeiro da Penha, 2013)
xv = {"id": "2013", "ref": "25/12/2013", "s": "ver", "beneficio": "Comutação", "dispositivo": "art. 2º", "mot": "x", "detalhe": {}, "alc": [],
      "hips": [{"tipo": "indulto", "dispositivo": "art. 1º, I", "ok": False, "exigido": None, "mot": "pena acima", "texto": ""},
               {"tipo": "comutacao", "dispositivo": "art. 2º", "ok": True, "exigido": 10, "mot": "", "texto": ""}]}
cart = rtl._decreto_ficha(F["2013"], xv, [], lambda ref: {"total": 0}, [], [])
confere(cart["indulto"]["status"] == "nao" and cart["comutacao"]["status"] == "verificar", "(22) cartão: %s / %s" % (
    cart["indulto"]["status"], cart["comutacao"]["status"]))

# ---------------------------------------------------------------------------------------------------------------------------
# 2ª rodada da revisão do indulto (08/10/2026): A1 a A15 e coerência A2, A11 e A13
import rspe_view as rv


def preso_fuga(desde, fuga, volta=None):
    ev = [preso(desde), {"tipo": "INTERRUPÇÃO", "motivo": "FUGA", "data": fuga, "processos": ""}]
    return ev + ([preso(volta, "RECAPTURA")] if volta else [])


# (23) indulto indeferido no RSPE: a comutação do _se_indeferido volta com o status do texto (Claudemir Germano, José Cirso,
# Rafael Martins, 2024; Mauro Spanamberg, 2025)
r = {"pena_total": "10a0m0d", "_eventos": [preso("01/01/2015")], "_crimes": [crime("01/01/2014", "01/06/2014", "01/07/2014", pena="10 ano(s), 0 mês(es) e 0 dia(s)")],
     "indulto_2024": "POSSÍVEL: art. 9º, I", "indulto_2024_status": "possivel",
     "comutacao_2024": "prejudicada: indulto cabível (art. 13, § 5º)", "comutacao_2024_status": "nao",
     "comutacao_2024_se_indeferido": "POSSÍVEL: art. 13 (1/5 do cumprido)",
     "_incidentes": [incidente("INDULTO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "12/07/2025", "NÃO CONCEDIDO")]}
rs.aplicar_decisoes_decretos(r, r["_incidentes"])
confere(r["comutacao_2024_status"] == "possivel", "(23) status da comutação não acompanhou o texto: %s" % r["comutacao_2024_status"])
x = dec(r, "2024")
confere(x["s"] == "cabe" and x.get("beneficio") == "Comutação", "(23) aba escondeu a comutação: %s" % x)
r2 = dict(r, comutacao_2024="POSSÍVEL: art. 13 (1/5 do cumprido) | falta a verificar (art. 6º: só impede se ...): X", comutacao_2024_status="possivel")
confere(dec(r2, "2024")["s"] == "ver", "(23) comutação com falta a verificar devia ficar a verificar: %s" % dec(r2, "2024"))

# (24) decisão de um benefício não esconde o outro: comutação concedida e indulto indeferido = concedido (Luciano Nascimento,
# 2024); comutação indeferida e indulto a verificar = a verificar (Wellington Ribeiro de Souza, 2025)
base24 = {"pena_total": "10a0m0d", "_eventos": [preso("01/01/2015")], "_crimes": [crime("01/01/2014", "01/06/2014", "01/07/2014", pena="10 ano(s), 0 mês(es) e 0 dia(s)")]}
r = dict(base24, indulto_2024="INDEFERIDO no RSPE em 26/06/2026", indulto_2024_status="nao", comutacao_2024="CONCEDIDO no RSPE em 26/06/2026",
         comutacao_2024_status="nao", _incidentes=[incidente("INDULTO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "26/06/2026", "NÃO CONCEDIDO"),
                                                   incidente("COMUTAÇÃO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "26/06/2026")])
x = dec(r, "2024")
confere(x["s"] == "conc" and x.get("beneficio") == "Comutação" and "indulto indeferido" in (x.get("ressalva") or ""), "(24) comutação concedida sumiu: %s" % x)
r = dict(base24, indulto_2025="A VERIFICAR: art. 9º, § 2º, II a VI (metade do lapso)", indulto_2025_status="verificar",
         comutacao_2025="INDEFERIDO no RSPE em 04/08/2026", comutacao_2025_status="nao",
         _incidentes=[incidente("COMUTAÇÃO", "DECRETO Nº 12.790, DE 23 DE DEZEMBRO DE 2025", "04/08/2026", "NÃO CONCEDIDO")])
x = dec(r, "2025")
confere(x["s"] == "ver" and x.get("beneficio") == "Indulto" and "comutação indeferida" in (x.get("ressalva") or ""), "(24) indulto a verificar sumiu: %s" % x)
x = dec(dict(base, _incidentes=[incidente("COMUTAÇÃO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "06/02/2025", "NÃO CONCEDIDO")]), "2023")
confere(x["s"] == "cabe" and x.get("beneficio") == "Indulto", "(24) 2023: comutação indeferida escondeu o indulto cabível: %s" % x)

# (25) um só critério para a falta a verificar: aba, linha do tempo e colunas dizem "a verificar" (Chelton 2025, Gilio 2024...)
txt = "POSSÍVEL: art. 9º, XV | falta a verificar (art. 6º: só impede se a sanção for reconhecida em juízo; STJ, Tema 1195): FALTA X"
x = dec(dict(base24, _incidentes=[], indulto_2025=txt, indulto_2025_status="possivel", comutacao_2025="prejudicada: indulto cabível (art. 13, § 5º)"), "2025")
confere(x["s"] == "ver", "(25) aba: falta a verificar devia dar a verificar, %s" % x)
confere(rtl._st_aba(txt) == "verificar", "(25) linha do tempo: %s" % rtl._st_aba(txt))
confere(rv.sim_nao(rv.curto_indulto(txt), rv.cor_texto_indulto(txt))[0] == "Verificar", "(25) coluna: %s" % (rv.sim_nao(rv.curto_indulto(txt), rv.cor_texto_indulto(txt)),))
confere(rs.status_texto_decreto(txt) == "verificar", "(25) status pelo texto: %s" % rs.status_texto_decreto(txt))

# (26) pena extinta depois do decreto não converte "NÃO CABE (art. 6º)", "não se aplica" nem "sem crimes ativos" em A VERIFICAR
# (Martimiano 2024, Antonio Leonardo 2024, Ezequiel 2024); em 2022, a pena extinta de crime fora do art. 7º não muda o
# resultado dos demais (Jair Bernardes, Anderson Severino)
cx = crime("01/01/2020", "01/06/2020", "01/07/2020", extinto="Sim", data_extincao="01/03/2026")
for t in ("NÃO CABE (art. 6º): falta grave com sanção reconhecida nos 12 meses - X", "não se aplica: não iniciou o cumprimento até 25/12/2024",
          "sem crimes ativos no RSPE", "sem pena no RSPE"):
    o = {"indulto_2024": t, "indulto_2024_status": "nao"}
    rs._extinta_depois(o, [cx], "2024", date(2024, 12, 25))
    confere(o["indulto_2024"] == t, "(26) %r virou %r" % (t, o["indulto_2024"]))
o = {"indulto_2022": "POSSÍVEL: art. 5º para art. 155 CP", "indulto_2022_status": "possivel"}
rs._extinta_depois(o, [crime("01/01/2020", "01/06/2020", "01/07/2020", artigo="ART 14: Porte ilegal de arma de fogo de uso permitido",
                             lei="10826/03 - Estatuto do Desarmamento", tipo="CAPUT: Portar, Reclusão: 2 a 4 anos E Multa",
                             extinto="Sim", data_extincao="01/03/2024")], "2022", date(2022, 12, 25))
confere(o["indulto_2022"].startswith("POSSÍVEL"), "(26) 2022: pena extinta fora do art. 7º mudou o resultado: %s" % o["indulto_2022"])
o = {"indulto_2024": "não atinge (cumprido 1a0m0d de 6a0m0d até 25/12/2024)", "indulto_2024_status": "nao"}
rs._extinta_depois(o, [cx], "2024", date(2024, 12, 25))
confere(o["indulto_2024"].startswith("A VERIFICAR"), "(26) 2024: 'não atinge' com pena extinta depois devia ficar a verificar: %s" % o["indulto_2024"])

# (27) execução arquivada ou com todas as penas extintas: nenhum "cabe" (Rubens Aquino 2023, João Vitor Vitoy, Wilson Marcondes)
r = {"pena_total": "0a0m0d", "status_execucao": "ARQUIVADO", "_eventos": [preso("01/01/2020")], "_incidentes": [],
     "_crimes": [crime("01/01/2019", "01/06/2019", "01/07/2019", pena="0 ano(s), 2 mês(es) e 0 dia(s)", artigo="ART 329: Resistência",
                       tipo="CAPUT: Opor-se, Detenção: 2 meses a 2 anos")]}
for ano in ("2020", "2021", "2023"):
    confere(dec(r, ano)["s"] not in ("cabe", "ver"), "(27) execução arquivada com resultado favorável em %s: %s" % (ano, dec(r, ano)))
o = {"indulto_2024": "POSSÍVEL: art. 9º, I", "indulto_2024_status": "possivel", "comutacao_2024": "prejudicada: indulto cabível (art. 13, § 5º)"}
rs._sem_objeto(o, {"status_execucao": "ARQUIVADO"}, [], "2024")
confere(o["indulto_2024_status"] == "nao" and o["indulto_2024"].startswith("não se aplica: execução arquivada") and o["comutacao_2024"].startswith("não se aplica"),
        "(27) 2024 em execução arquivada: %s" % o)

# (28) inciso XIII só com conclusão certificada: ENEM peticionado fica a verificar; ENCCEJA com certificado, como antes (Kelven 2025)
def _r13():
    return {"_eventos": [preso("01/01/2020")], "indulto_2025": "A VERIFICAR: art. 9º, XIII", "indulto_2025_status": "verificar",
            "indulto_2025_detalhe": "Situação em 25/12/2025: regime Fechado · primário\n? XIII: pena ≤ 12 anos, 1/5 cumprido - verificar conclusão de curso certificado nos 3 anos anteriores"}
for txt13, ex13, novo, esperado in (("Peticionado Certificado do Enem 2024 no Sistema SEEU nos autos nº 1", "ENEM 2024", False, "?"),
                                    ("Peticionado Certificado do ENCCEJA 2024 no Sistema SEEU nos autos nº 1", "ENCCEJA 2024", True, "✔"),
                                    ("Peticionado a declaração parcial de proficiência para ens. fund. - ENCCEJA/2024", "ENCCEJA", False, "?")):
    for com_marca in (True, False):  # ficha lida nesta versão (com a marca) e ficha gravada antes (sem ela)
        ex = {"exame": ex13, "data": "11.04.2025"}
        if com_marca:
            ex["certificado"] = novo
        r = _r13()
        rf.complementar_decretos(r, {"eventos": [{"data": "11.04.2025", "texto": txt13.upper()}], "exames": [ex], "trabalho": [], "estudos": []}, HOJE)
        lin = [l for l in r["indulto_2025_detalhe"].split("\n") if " XIII:" in l]
        confere(lin and lin[0].startswith(esperado), "(28) %s (marca %s): %s" % (txt13[:40], com_marca, lin))

# (29) SEEU sem cálculo (cumprida zero e remanescente igual à pena) ou pena total zerada: o cumprido vem dos eventos e o
# favorável fica a verificar (Davi Antonio Vigil e Murilo Alves de Souza 2025; Cláudio de Anunciação 2022/2024/2025)
r = {"nome": "T", "pena_total": "0a1m0d", "pena_cumprida": "0a0m0d", "pena_remanescente": "0a1m0d", "data_geracao_rspe": "01/12/2025",
     "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_eventos": [preso("30/11/2025")],
     "_incidentes": [incidente("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime inicial", "30/11/2025")],
     "_crimes": [crime("01/01/2024", "01/06/2025", "01/07/2025", pena="0 ano(s), 1 mês(es) e 0 dia(s)")]}
r = rs.reprocessar(r)
confere(r["indulto_2025_status"] == "verificar" and "não traz o cálculo" in r["indulto_2025"], "(29) SEEU sem cálculo: %s" % r["indulto_2025"])
r = dict(r, pena_total="0a0m0d", pena_remanescente="0a0m0d")
r = rs.reprocessar(r)
confere(r["indulto_2025_status"] == "verificar" and not r["indulto_2025"].startswith("sem pena"), "(29) pena total zerada: %s" % r["indulto_2025"])

# (30) concurso com impeditivo e cumprimento interrompido: o art. 7º, p. ú., veda antes da dúvida da interrupção (Alex Rodrigues
# de Souza, Brehndo, Márcio de Souza Alves, 2024/2025)
traf = crime("01/01/2023", "01/06/2023", "01/07/2023", artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas",
             tipo="CAPUT: Importar, exportar, Reclusão: 5 a 15 anos E Multa", pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000002-00.2023.8.12.0001")
r = {"nome": "T", "pena_total": "7a0m0d", "pena_cumprida": "1a0m0d", "pena_remanescente": "6a0m0d", "data_geracao_rspe": "01/10/2026",
     "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_crimes": [traf, crime("01/01/2023", "01/06/2023", "01/07/2023")],
     "_eventos": preso_fuga("01/07/2023", "01/10/2024", "01/01/2026"), "_incidentes": [incidente("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime inicial", "01/07/2023")]}
r = rs.reprocessar(r)
confere(r["indulto_2024_status"] == "vedado" and "art. 7º, p. ú." in r["indulto_2024"], "(30) interrupção escondeu a vedação: %s" % r["indulto_2024"])

# (31) concurso: a memória descreve a violência dos crimes não impeditivos, não a de todos (Chelton 2024)
est = crime("01/01/2010", "01/06/2010", "01/07/2010", artigo="ART 213: Estupro", tipo="CAPUT: Constranger alguém, mediante violência ou grave ameaça, Reclusão: 6 a 10 anos",
            pena="6 ano(s), 0 mês(es) e 0 dia(s)", proc="0000003-00.2010.8.12.0001")
est["vga"] = "S"
r = {"nome": "T", "pena_total": "7a0m0d", "pena_cumprida": "6a0m0d", "pena_remanescente": "1a0m0d", "data_geracao_rspe": "25/12/2024",
     "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_crimes": [est, crime("01/01/2010", "01/06/2010", "01/07/2010")],
     "_eventos": [preso("01/01/2019")], "_incidentes": [incidente("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime inicial", "01/01/2019")]}
r = rs.reprocessar(r)
sit = next((l for l in (r.get("indulto_2024_detalhe") or "").split("\n") if l.startswith("Situação em")), "")
confere("Art. 7º, p. ú.: 2/3" in (r.get("indulto_2024_detalhe") or "") and "VGA" not in sit and not r["indulto_2024_num"]["vga"],
        "(31) memória do concurso com a violência do impeditivo: %r / %s" % (sit, r.get("indulto_2024")))

# (32) 2022: crime com pena máxima acima de 5 anos não vai para a conferência do trânsito (Aldo Pereira de Souza)
o = rs.analise_decreto_2022({"pena_total": "3a0m0d"}, [crime("01/01/2020", "01/06/2020", "01/07/2020"),
                                                       crime("01/01/2020", None, None, tipo="§ 4º: Furto qualificado, Reclusão: 2 a 8 anos E Multa",
                                                             proc="0000004-00.2020.8.12.0001")], [], [])
confere(o["indulto_2022_status"] == "possivel" and "conferir" not in o["indulto_2022"], "(32) 2022: %s" % o["indulto_2022"])

# (33) textos da petição: dias acima de 30 viram mês, "da pena cumprida", ficha sem reticências no meio do texto
confere(rtl._pena_ext("4a11m33d") == "5 anos e 3 dias" and rtl._pena_ext("1a2m31d") == "1 ano, 3 meses e 1 dia", "(33) %s / %s" % (
    rtl._pena_ext("4a11m33d"), rtl._pena_ext("1a2m31d")))
t = rs._texto_ficha("Saída da Unidade Penal: ESTABELECIMENTO PENAL DE REGIME SEMIABERTO E ABERTO DE AQUIDAUANA, Destino: , Motivo: Evasão do "
                    "estabelecimento sem autorização judicial durante o período noturno de recolhimento", 90)
confere("..." not in t and "Destino: ," not in t, "(33) texto da ficha: %s" % t)
out = {"numero": "12.338/2024", "referencia": "25/12/2024", "id": "2024", "indulto": {},
       "comutacao": {"status": "cabe", "checklist": [], "reducao": {"fracao": "1/5", "base": "cumprido", "reducao_txt": "0a6m0d", "antes_txt": "3a0m0d",
                                                                   "depois_txt": "2a6m0d"}}}
t = rtl._fundamentacao(out, "comutacao")
confere("da pena cumprida" in t and "da pena cumprido" not in t, "(33) concordância: %s" % t)

# (34) cartão de 2000 a 2023 em concurso: o cabeçalho traz os números da conta das hipóteses (Claudemir 2023)
xc = dict(xv, s="cabe", beneficio="Indulto", detalhe={"pena": 5800, "cumprido": 3833, "pena_conc": 1450, "cumprido_conc": 956, "exigido_imp": 2877})
cart = rtl._decreto_ficha(F["2023"], xc, [], lambda ref: {"total": 0}, [], [])
confere(cart["indulto"]["pena_considerada_txt"] == rtl._pena(1450) and cart["indulto"]["cumprido_txt"] == rtl._pena(956),
        "(34) cabeçalho com os números de antes do concurso: %s / %s" % (cart["indulto"]["pena_considerada_txt"], cart["indulto"]["cumprido_txt"]))

if falhas:
    print("FALHOU: indulto - auditoria\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: indulto - auditoria (tese, indeferimento x comutação, violência contra a mulher, extinção posterior e sem data, livramento, execução posterior, "
      "lesão grave do roubo, sentença incoerente, âncora zerada, crime doloso na janela, art. 4º de 2017, regressão cautelar, textos da petição; "
      "rev. 08/10: comutação com indulto indeferido, decisões cruzadas, falta a verificar, extinta depois, execução encerrada, inciso XIII, SEEU sem cálculo, "
      "vedação antes da interrupção, VGA do concurso, trânsito x teto em 2022)")
