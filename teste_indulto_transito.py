"""Teste de regressão: condenação na data da publicação do decreto de indulto (sentença e trânsito para a acusação) e
violência/grave ameaça elementar do tipo. Rodar: python teste_indulto_transito.py"""
import rspe_decretos as rd
import rspe_regras as rg
import rspe_scraper as rs

F = {f["id"]: f for f in rg.carregar()["decretos_fichas"]}


def crime(fato, sent, tm, tp=None, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="1 ano(s), 0 mês(es) e 0 dia(s)"):
    return {"data_infracao": fato, "data_sentenca": sent, "transito_mp": tm or "", "transito_processo": tp if tp is not None else (tm or ""),
            "extinto": "Não", "lei": "2848/40 - Código Penal", "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena,
            "pena_total_processo": "1a0m0d - PENA ORIGINÁRIA", "vga": "N", "reincidente_comum": "N", "reincidente_especifico": "N"}


# decretos 2000-2023 (fichas): regra de trânsito de cada decreto
assert rd.transito_pendente(F["2013"], {"_crimes": [crime("10/01/2012", "10/10/2013", "20/11/2013")]}) == ""
t = rd.transito_pendente(F["2013"], {"_crimes": [crime("10/01/2012", "10/06/2013", "15/03/2014")]})
assert t.startswith("A VERIFICAR") and "não vise majorar" in t and "991.402" in t, t
t = rd.transito_pendente(F["2021"], {"_crimes": [crime("10/01/2020", "10/06/2021", "15/03/2022")]})
assert "VEDA" in t, t
t = rd.transito_pendente(F["2004"], {"_crimes": [crime("10/01/2001", "10/06/2004", "", "")]})
assert "não consta no RSPE" in t, t
for ano in [str(a) for a in range(2002, 2012)]:  # conferido com o texto oficial (Planalto)
    assert F[ano]["transito"]["regra"] == "nao_majorar", ano
assert F["2017_maes"]["falta_grave"].get("contada_de") == "referencia"

# Decreto 11.302/2022 (art. 5º e art. 12)
def dec22(c):
    r = {"data_nascimento": "01/01/1980", "pena_total": "1a0m0d", "regime_atual": "Fechado - ATIVO"}
    return rs.analise_decreto_2022(r, [c], [], [])

o = dec22(crime("10/01/2020", "10/02/2023", "10/03/2023"))  # sentença posterior à publicação (23/12/2022)
assert o["indulto_2022_status"] == "nao" and "sentença posterior" in o["indulto_2022"], o["indulto_2022"]
o = dec22(crime("10/01/2020", "10/10/2022", "10/01/2023"))  # trânsito para a acusação posterior: art. 12
assert o["indulto_2022_status"] == "nao" and "art. 12" in o["indulto_2022"], o["indulto_2022"]
o = dec22(crime("10/01/2020", "10/10/2022", "10/11/2022", "10/02/2023"))  # só a defesa pendente: alcança
assert o["indulto_2022_status"] != "nao", o["indulto_2022"]

# violência ou grave ameaça elementar do tipo (ameaça, roubo) - mesmo com o RSPE marcando "N"
assert rs.vga_elementar(crime("10/01/2020", "", "", artigo="ART 147: Ameaça", tipo="CAPUT: Ameaçar alguém"))
assert not rs.vga_elementar(crime("10/01/2020", "", ""))
print("ok: indulto - condenação na data da publicação (2000-2025) e violência/grave ameaça elementar do tipo")
