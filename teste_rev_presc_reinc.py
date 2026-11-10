"""Teste de regressão (revisão jurídica da aba Prescrição, decisão de 11/2026): reincidência marcada no RSPE sem condenação anterior
transitada no próprio RSPE. O prazo principal leva o +1/3 (CP, art. 110), como está no RSPE, também com várias condenações; a hipótese
sem ele vai para o aviso e, se mudar o resultado, fica A VERIFICAR. Tráfico privilegiado (art. 33, § 4º, que pressupõe primariedade)
continua sem o +1/3. Dados fictícios. Rodar: python teste_rev_presc_reinc.py (sai com código 1 se algum caso falhar)."""
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


def crime(proc, fato, tr, pena, reinc="S", artigo="ART 155: Furto", lei="2848/40 - Código Penal", tipo="RECLUSÃO"):
    return {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": "", "data_sentenca": "", "transito_mp": tr,
            "transito_processo": tr, "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena,
            "pena_total_processo": "%s - PENA ORIGINÁRIA" % pena, "reincidente_comum": reinc, "reincidente_especifico": "N", "extinto": "Não"}


def reg(crimes, eventos=()):
    return {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": [], "data_nascimento": "01/01/1980", "nome": "SIMULADO CASO 902",
            "data_geracao_rspe": "10/11/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "9900902-00.2021.8.12.0001"}


def linha(r, proc):
    return next(l for l in rp.analisar(r, HOJE)["presc_linhas"] if l["proc_crim"] == proc)


A, B = "9900902-11.2019.8.12.0001", "9900902-22.2021.8.12.0001"
UM = "1 ano(s), 0 mês(es) e 0 dia(s)"

# 1. duas condenações, A marcada reincidente; a outra (B) transitou depois do fato de A: o principal leva o +1/3, a hipótese sem ele no aviso
r = reg([crime(A, "01/01/2019", "01/06/2020", UM), crime(B, "01/01/2021", "01/06/2022", UM, reinc="N")],
        [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "01/07/2022", "processos": "%s, %s" % (A, B)}])
l = linha(r, A)
confere(l["reinc"] and "+1/3" in l["prazo_ppe"], "1: +1/3 no prazo principal: %s" % l["prazo_ppe"])
confere("Sem o +1/3" in (l.get("ppe_reinc_aviso") or ""), "1: hipótese sem o +1/3 no aviso: %s" % l.get("ppe_reinc_aviso"))

# 2. o mesmo, solto desde o trânsito de A (01/06/2020) até a prisão de 01/08/2025: com o +1/3 (5 anos e 4 meses) não prescreve;
# sem ele (4 anos), venceu em 2024 - A VERIFICAR, com a nota
r = reg([crime(A, "01/01/2019", "01/06/2020", UM), crime(B, "01/01/2015", "01/06/2022", UM, reinc="N")],
        [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "01/08/2025", "processos": "%s, %s" % (A, B)}])
l = linha(r, A)
confere(l["ppe_status"].startswith("A VERIFICAR") and "+1/3" in l["prazo_ppe"], "2: A VERIFICAR com o +1/3 no principal: %s / %s" % (l["ppe_status"], l["prazo_ppe"]))
confere("Sem o +1/3" in (l.get("ppe_reinc_aviso") or "") and "o resultado seria" in (l.get("ppe_reinc_aviso") or ""),
        "2: nota diz que sem o +1/3 o resultado muda: %s" % l.get("ppe_reinc_aviso"))

# 3. tráfico privilegiado marcado reincidente sem condenação anterior: continua sem o +1/3 (o § 4º pressupõe primariedade)
r = reg([crime(A, "01/01/2019", "01/06/2020", "1 ano(s), 8 mês(es) e 0 dia(s)", artigo="ART 33: Tráfico de drogas", lei="11343/06 - Lei de Drogas",
               tipo="§ 4º: Nos delitos definidos no caput, as penas poderão ser reduzidas"), crime(B, "01/01/2021", "01/06/2022", UM, reinc="N")])
l = linha(r, A)
confere(not l["reinc"] and "+1/3" not in l["prazo_ppe"], "3: privilegiado sem o +1/3: %s" % l["prazo_ppe"])

if falhas:
    print("FALHAS:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("teste_rev_presc_reinc: 3 casos ok")
