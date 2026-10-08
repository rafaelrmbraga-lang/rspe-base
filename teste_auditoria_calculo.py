"""Teste de regressão dos alertas de cálculo da Auditoria (fundamentações NUSPEN): detração (as duas contas), 1/1 do livramento
lançado no crime, referência do semiaberto não refeita e comutações fora de ordem. Rodar: python teste_auditoria_calculo.py"""
from datetime import date

import rspe_auditoria as ra


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs=""):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


def crime(fl="2/3 - Comum Reincidente", fp="2/5 - Art.112, V, da LEP", art="ART 155: Furto"):
    return {"processo_criminal": "0000001-11.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": art,
            "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "10 ano(s), 0 mês(es) e 0 dia(s)",
            "pena_total_processo": "10a0m0d - PENA ORIGINÁRIA", "data_infracao": "10/01/2020", "data_sentenca": "10/06/2020",
            "transito_mp": "10/07/2020", "transito_processo": "10/07/2020", "extinto": "Não", "vga": "N", "resultado_morte": "N",
            "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "fracao_progressao": fp, "fracao_livramento": fl}


def reg(incs, eventos=None, crimes=None, regime="Semiaberto - ATIVO", db="01/03/2024"):
    return {"nome": "Teste", "regime_atual": regime, "pena_total": "10a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "7a0m0d",
            "fracao_progressao_aplicada": "2/5", "data_geracao_rspe": "01/10/2026", "data_base_seeu": db,
            "_crimes": crimes or [crime()], "_incidentes": incs, "_eventos": eventos or []}


def tipos(r):
    return {i["tipo"]: i for i in ra.auditar(r, date(2026, 10, 1))["aud_itens"]}


# detração: regime inicial depois da primeira prisão, com as duas contas e a diferença d x (1 - f)
ev = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO EM FLAGRANTE", "data": "01/01/2020", "processos": "0000001-11.2020.8.12.0001"},
      {"tipo": "INTERRUPÇÃO", "motivo": "SOLTURA", "data": "01/04/2020", "processos": ""},
      {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "MANDADO", "data": "01/01/2021", "processos": "0000001-11.2020.8.12.0001"}]
t = tipos(reg([inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "01/01/2021")], ev, regime="Fechado - ATIVO", db="01/01/2021"))
it = t["regime-inicial-depois-da-primeira-prisao"]
assert "91 dias de prisão provisória" in it["detalhe"] and "(1 − fração) = 1 mês e 25 dias" in it["detalhe"], it["detalhe"]
assert "AgRg no AREsp 2.956.206" in ra.fundamentacao(it, reg([]))

# 1/1 no crime comum com livramento já concedido: revogação lançada no lugar errado
t = tipos(reg([inc("LIVRAMENTO CONDICIONAL", "01/02/2023", "01/02/2023", "01/02/2023")], crimes=[crime(fl="1/1 - Hediondo Reincidente/Reincidente Específico")]))
assert "livramento-1-1-pela-revogacao" in t and "fracao-de-livramento-diverge" not in t, list(t)

# semiaberto: comutação de decreto anterior à referência, decidida depois da progressão
base = [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial", "", "01/01/2020"),
        inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Semiaberto - Progressão de Regime", "10/03/2024", "01/03/2024")]
t = tipos(reg(base + [inc("COMUTAÇÃO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", "10/05/2025", "10/05/2025")]))
assert "semiaberto-referencia-desatualizada" in t, list(t)
t = tipos(reg(base + [inc("COMUTAÇÃO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "10/05/2025", "10/05/2025")]))
assert "semiaberto-referencia-desatualizada" not in t  # decreto posterior à referência: não altera a primeira progressão

# comutações: inversão (alerta) e a anterior lançada depois do 25/12 do decreto seguinte (verificar)
c23 = lambda ref: inc("COMUTAÇÃO", "DECRETO Nº 11.846, DE 22 DE DEZEMBRO DE 2023", ref, ref)
c24 = inc("COMUTAÇÃO", "DECRETO Nº 12.338, DE 23 DE DEZEMBRO DE 2024", "20/05/2025", "20/05/2025")
assert tipos(reg([c23("10/06/2025"), c24]))["comutacoes-fora-de-ordem"]["nivel"] == "alerta"
assert tipos(reg([c23("10/01/2025"), c24]))["comutacoes-fora-de-ordem"]["nivel"] == "verificar"
assert "comutacoes-fora-de-ordem" not in tipos(reg([c23("10/03/2024"), c24]))
print("ok: alertas de cálculo (detração, 1/1 do livramento, semiaberto, comutações)")
