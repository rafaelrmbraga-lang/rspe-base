"""Teste de regressão (revisão jurídica da aba Prescrição, 11/2026): só o trânsito final no RSPE e o termo real é o trânsito para a
acusação (CP, art. 112, I, na modulação do STF no Tema 788 - trânsito para a acusação até 12/11/2020), anterior e não informado.
Contar do trânsito final é o mais desfavorável ao assistido: se, com o termo em alguma data possível do trânsito para a acusação
(entre a sentença e o trânsito final ou 12/11/2020), a executória se completa, o resultado é A VERIFICAR, e não "não prescrita".
Dados fictícios. Rodar: python teste_rev_presc_termo_mp.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_prescricao as rp

HOJE = date(2026, 11, 10)
falhas = []


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(proc, sent, tr, tmp="", pena="0 ano(s), 8 mês(es) e 0 dia(s)", fato="01/06/2014"):
    return {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": "15/07/2014", "data_sentenca": sent, "transito_mp": tmp,
            "transito_processo": tr, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "RECLUSÃO",
            "pena_imposta": pena, "pena_total_processo": "0a8m0d - PENA ORIGINÁRIA", "reincidente_comum": "N",
            "reincidente_especifico": "N", "extinto": "Não"}


def reg(c, eventos):
    return {"_crimes": [c], "_eventos": list(eventos), "_incidentes": [], "data_nascimento": "01/01/1980", "nome": "SIMULADO CASO 901",
            "data_geracao_rspe": "10/11/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "9900901-00.2020.8.12.0001"}


def prisao(data, proc):
    return {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": data, "processos": proc}


def linha(r):
    return rp.analisar(r, HOJE)["presc_linhas"][0]


P = "9900901-11.2014.8.12.0001"

# 1. trânsito final 20/12/2019 (antes de 12/11/2020), sem o da acusação; solto até a prisão de 01/03/2020. Do trânsito final, não
# prescreve (3 anos). Com o trânsito para a acusação logo depois da sentença de 10/01/2015, os 3 anos venceram em 2018: A VERIFICAR
l = linha(reg(crime(P, "10/01/2015", "20/12/2019"), [prisao("01/03/2020", P)]))
confere(l["ppe_status"].startswith("A VERIFICAR") and "acusação" in l["ppe_status"], "1: esperado A VERIFICAR pelo trânsito para a acusação: %s" % l["ppe_status"])
confere(any("trânsito em julgado para a acusação" in x for x in l.get("ppe_faltam") or []), "1: falta a data do trânsito para a acusação: %s" % l.get("ppe_faltam"))

# 2. o mesmo caso com o trânsito para a acusação informado (igual ao final): o resultado é seguro - não prescrita
l = linha(reg(crime(P, "10/01/2015", "20/12/2019", tmp="20/12/2019"), [prisao("01/03/2020", P)]))
confere(not l["ppe_status"].startswith("A VERIFICAR") and "prescrita" not in l["ppe_status"].lower().replace("não prescrita", ""),
        "2: com o trânsito para a acusação informado, não prescrita: %s" % l["ppe_status"])

# 3. sentença de 01/06/2020 (antes de 12/11/2020) e trânsito final de 01/03/2021 (depois), sem o da acusação; prisão em 10/09/2023.
# Do trânsito final, os 3 anos vencem em 2024 (a prisão interrompe antes). Se a acusação não recorreu, o trânsito para ela pode ser
# anterior a 12/11/2020 e ser o termo: os 3 anos venceriam antes da prisão - A VERIFICAR
l = linha(reg(crime(P, "01/06/2020", "01/03/2021", fato="01/02/2020"), [prisao("10/09/2023", P)]))
confere(l["ppe_status"].startswith("A VERIFICAR"), "3: esperado A VERIFICAR (sentença antes da modulação): %s" % l["ppe_status"])

# 4. preso desde antes da sentença, sem interrupção: qualquer que seja o trânsito para a acusação, o prazo não corre - sem alteração
l = linha(reg(crime(P, "10/01/2015", "20/12/2019"), [prisao("01/12/2014", P)]))
confere(not l["ppe_status"].startswith("A VERIFICAR"), "4: preso desde antes da sentença, não muda: %s" % l["ppe_status"])

if falhas:
    print("FALHAS:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("teste_rev_presc_termo_mp: 4 casos ok")
