"""Correção 7.14.8, frente "situação" (base simulada independente): situação da execução, coluna Falta, progressão refeita,
prescrição e extinção.
- quem nunca iniciou o cumprimento (só flagrante, solto antes do trânsito) não aparece como "pena interrompida" (LEP, art. 105);
- livramento condicional "desde" a audiência/soltura, não desde a decisão (LEP, art. 137);
- fuga anterior à janela, com recaptura nela e falta homologada com a data da evasão: falta nos 12 meses (falta permanente -
  STJ, HC 527.625; CP, art. 83, III, b);
- progressão refeita: o 1/6 de fato anterior a 2020 vira 16% (Lei 13.964/2019, mais benéfica e retroativa - CF, art. 5º, XL);
- óbito lançado como interrupção, sem extinção: extinção a verificar (CP, art. 107, I; CPP, art. 62);
- multa como única pena: prescrição em 2 anos (CP, art. 114, I);
- detração visível nos eventos e não abatida pelo SEEU que zera o saldo na fuga: extinção pelo cumprimento a verificar (CP, art. 42).
Casos hipotéticos, nomes fictícios. Rodar: python teste_cob_situacao.py"""
import os
import subprocess
import sys
import tempfile
import types
from datetime import date
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs
import rspe_view as rv

falhas = []
AQUI = os.path.dirname(os.path.abspath(__file__))


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P = "0000001-11.2022.8.12.0001"
CR = {"processo_criminal": P, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "§ 4º: furto qualificado",
      "pena_imposta": "6 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/03/2022", "transito_processo": "25/11/2022",
      "transito_mp": "25/11/2022", "extinto": "Não", "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum Primário"}

# 1) livramento: "desde" a soltura (interrupção lançada para o período de prova), não a decisão que o deferiu
campos = {"livramento_obs_seeu": "Em livramento condicional deferido em 25/02/2026", "regime_atual": "Fechado - ATIVO", "_crimes": [CR]}
evs = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "06/06/2023", "processos": P},
       {"tipo": "INTERRUPÇÃO", "motivo": "LIVRAMENTO CONDICIONAL", "data": "02/03/2026", "processos": ""}]
incs = [{"tipo": "LIVRAMENTO CONDICIONAL", "complemento": "02/03/2026", "data_decisao": "25/02/2026", "data_referencia": "02/03/2026", "situacao": "CONCEDIDO"}]
sit = rs.situacao_execucao(campos, evs, incs, [CR], date(2026, 10, 5))["situacao_cumprimento"]
ok("desde 02/03/2026" in sit, "livramento desde a soltura: %s" % sit)
ok(rs.inicio_periodo_prova(evs, date(2026, 2, 25)) == date(2026, 3, 2), "início do período de prova")
ok(rs.inicio_periodo_prova([], date(2026, 2, 25)) == date(2026, 2, 25), "sem soltura lançada, a data do deferimento")

# 2) fuga antes da janela, recaptura dentro, falta homologada com a data da evasão: falta nos 12 meses (permanente)
evs = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO DEFINITIVA", "data": "02/02/2024", "processos": P},
       {"tipo": "INTERRUPÇÃO", "motivo": "FUGA", "data": "10/08/2025", "processos": ""},
       {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "RECAPTURA", "data": "20/04/2026", "processos": P}]
incs = [{"tipo": "HOMOLOGAÇÃO DE FALTA GRAVE", "complemento": "10/08/2025", "data_decisao": "15/05/2026", "data_referencia": "10/08/2025",
         "situacao": "CONCEDIDO"}]
f = rs.faltas({"saldo_remidos": "0 dias"}, evs, incs, date(2026, 10, 5), [CR])
ok(f["falta_12m"] == "SIM" and "20/04/2026" in f["falta_12m_detalhe"], "fuga homologada com recaptura na janela: %s" % f)
# a mesma fuga com recaptura também antes da janela: não conta
evs2 = evs[:2] + [dict(evs[2], data="20/08/2025")]
f = rs.faltas({"saldo_remidos": "0 dias"}, evs2, incs, date(2026, 10, 5), [CR])
ok(f["falta_12m"] != "SIM", "fuga encerrada antes da janela: %s" % f)

# 3) progressão refeita: 1/6 de fato anterior a 2020 -> 16% (retroativo); depois da Lei 15.402/2026, a fração literal
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Comum", "data_infracao": "10/10/2018"}) == Fraction(16, 100), "16% retroativo (2018)")
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Art.112, caput, da LEP", "data_infracao": "10/05/2026"}) == Fraction(1, 6), "1/6 da Lei 15.402")
ok(rv._fr_prog_refeita({"fracao_progressao": "1/6 - Comum", "data_infracao": "10/10/2018", "reincidente_comum": "S"}) == Fraction(1, 6),
   "reincidente: 1/6 do SEEU é o favorável")

# 4) os casos da cobertura pela Api da tela (a mesma conta da tela)
for area, ids in (("leitura", "S1001,S1008,S1036"), ("progressao", "S3040"), ("prescricao_extincao", "S8027,S8031,S8053")):
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, APTO_SIM_DESTINO=os.path.join(tmp, "b.sqlite"), TMPDIR=tmp)
    p = subprocess.run([sys.executable, os.path.join(AQUI, "casos_simulados", "roda_casos.py"),
                        os.path.join(AQUI, "casos_simulados", "cobertura", area + ".json"), "--vazia", "--so", ids],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        falhas.append("cobertura %s: %s" % (area, "\n".join(l for l in p.stdout.splitlines() if "FALHA" in l or l.startswith("    x"))
                                            or p.stderr[-1500:]))

if falhas:
    print("FALHOU:")
    for x in falhas:
        print("  -", x)
    sys.exit(1)
print("ok: correção 7.14.8, situação (não iniciou, livramento desde a soltura, fuga permanente na falta, 16% retroativo, óbito, multa isolada, "
      "detração não abatida na fuga)")
