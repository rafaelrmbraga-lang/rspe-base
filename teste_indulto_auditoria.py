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

if falhas:
    print("FALHOU: indulto - auditoria\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: indulto - auditoria (tese, indeferimento x comutação, violência contra a mulher, extinção posterior, livramento, execução posterior)")
