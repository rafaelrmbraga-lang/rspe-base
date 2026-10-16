"""Quesitos de 16/10 - pontos da junção dos grupos: item 35 na análise detalhada de 2024/2025 (homicídio simples com o selo de
hediondo do SEEU: conta refeita sem o selo; se melhora, A VERIFICAR com as duas hipóteses)."""
import sys
from datetime import date
import rspe_scraper as rs

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, sent, tr, artigo, tipo, pena, fr="40% - Hediondo Primário", proc="0000001-00.2015.8.12.0001"):
    return {"processo_criminal": proc, "vara_condenacao": "1ª Vara", "data_infracao": fato, "data_sentenca": sent, "transito_mp": tr,
            "transito_processo": tr, "lei": "2848/40 - Código Penal", "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena,
            "pena_total_processo": "PENA ORIGINÁRIA", "regime_sentenca": "Fechado", "vga": "S", "resultado_morte": "S",
            "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "extinto": "Não",
            "fracao_progressao": fr, "fracao_livramento": "2/3 - Hediondo"}


ev = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "01/01/2016", "processos": ""}]
hs = crime("01/01/2015", "01/06/2016", "01/07/2016", "ART 121: Homicídio simples", "CAPUT: Matar alguém, Reclusão: 6 a 20 anos",
           "6 ano(s), 0 mês(es) e 0 dia(s)")
ok(rs.homicidio_simples_selo(hs), "selo não reconhecido")
ok(rs.e_hediondo(hs) and not rs.e_hediondo(dict(hs, _sem_selo=True)), "_sem_selo não tira a hediondez")
r = {"nome": "T", "processo_execucao": "X", "pena_total": "6a0m0d", "pena_cumprida": "", "pena_remanescente": "",
     "data_geracao_rspe": "05/10/2026", "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M",
     "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_crimes": [hs], "_eventos": ev, "_incidentes": []}
o = rs.analise_decretos(r, [hs], ev, [], date(2026, 10, 16))
o2 = rs.analise_decretos(r, [dict(hs, _sem_selo=True)], ev, [], date(2026, 10, 16))
for k in ("indulto_2024", "comutacao_2024", "indulto_2025", "comutacao_2025"):
    s, s2 = rs.status_texto_decreto(o.get(k)), rs.status_texto_decreto(o2.get(k))
    if s2 in ("possivel", "verificar"):
        ok(s in ("possivel", "verificar"), "35: %s com o selo nega o que sem o selo cabe: %s" % (k, (o.get(k) or "")[:200]))
    if (o.get(k) or "").startswith("A VERIFICAR (homicídio simples"):
        ok("sem o selo" in o[k] and "com o selo" in o[k], "35: %s sem as duas hipóteses" % k)
# nunca rebaixa: crime sem o selo não muda
fu = dict(hs, artigo="ART 155: Furto", tipo="CAPUT: Subtrair", fracao_progressao="16%", fracao_livramento="1/3", vga="N", resultado_morte="N")
ok(rs.analise_decretos(dict(r, _crimes=[fu]), [fu], ev, [], date(2026, 10, 16)) == rs.analise_decretos(dict(r, _crimes=[fu]), [fu], ev, [], date(2026, 10, 16)),
   "conta instável")
print("\n".join(falhas) if falhas else "ok: quesitos 16/10 - junção (item 35 na análise detalhada)")
print({k: (o.get(k) or "")[:90] for k in ("indulto_2024", "comutacao_2024")}) if "-v" in sys.argv else None
sys.exit(1 if falhas else 0)
