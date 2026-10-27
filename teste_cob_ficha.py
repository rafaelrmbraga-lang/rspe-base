"""Correção 7.14.8, frente "ficha" (leitura da ficha do SIAPEN): atestado com o ano corrigido e o trabalho sem baixa (sem
OverflowError); leitura por "CICLO Nº 03/2020"; falsas fugas da ficha (tentativa frustrada, "sob pena de evasão") fora das
fugas a apurar; regressão judicial pela evasão sem a palavra "falta" = falta homologada (LEP, art. 118, I) e sem o alerta de
falta de vaga; reinício omitido / RSPE sem prisão como alerta (LEP, art. 111; CP, art. 42); monitoramento contado com os dois
extremos. Casos da cobertura (casos_simulados/cobertura/ficha.json) e conferências diretas da leitura.
Casos hipotéticos, nomes fictícios. Rodar: python teste_cob_ficha.py"""
import os
import subprocess
import sys
import tempfile
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def ficha(eventos, **kw):
    f = {"tipo": "ficha_disciplinar", "versao_leitura": 0, "nome": "TESTE FICTICIO", "cpf": "900.000.000-00", "unidade": "INSTITUTO PENAL DE CAMPO GRANDE",
         "data_entrada": "20/03/2024", "data_prisao": "10/02/2024", "data_impressao": "02/10/2026", "autos": [],
         "eventos": [{"data": d, "texto": t} for d, t in eventos], "historico_oculto": []}
    f.update(kw)
    return f


# 1. ano trocado no atestado, trabalho sem baixa: a correção do ano não estoura a data máxima
f = rf.atualizar(ficha([("01.08.2024", "TRABALHO: Iniciou atividade laboral, no setor de trabalho FAXINA, conforme documento CI 10."),
                        ("10.11.2024", "Emitido ATESTADO DE TRABALHO Nº 088/2024, função FAXINA (01/08/2025 A 31/10/2024), totalizando 78 dias "
                                       "trabalhados e 26 dias remidos.")]))
a = (f.get("atestados") or [{}])[0]
ok(a.get("ano_corrigido") and a.get("periodo_inicio") == "01/08/2024" and a.get("periodo_fim") == "31/10/2024"
   and f.get("dias_trabalhados_atestados") == 78 and f.get("dias_remidos_atestados") == 26, "ano corrigido com trabalho sem baixa: %s" % f.get("atestados"))

# 2. "CICLO Nº 03/2020": ciclo de leitura reconhecido
f = rf.atualizar(ficha([("15.12.2020", "Atestado de Remição por Leitura nº 71/2020 - CICLO Nº 03/2020 - obra lida: O ALIENISTA, relatório aprovado.")]))
lt = (f.get("leituras") or [{}])[0]
ok(lt.get("ciclo") == "03/2020", "ciclo com 'Nº': %s" % f.get("leituras"))

# 3. regressão judicial pela evasão sem a palavra "falta": falta homologada na data da evasão
f = rf.atualizar(ficha([("05.02.2025", "Saída da Unidade Penal: CPAIG, Destino: , Motivo: EVASÃO"),
                        ("20.03.2025", "Entrada na Unidade Penal: PTRAN, Procedente: RECAPTURA - CAPITAL, Conforme OF/CI 1."),
                        ("10.05.2025", "REGRESSÃO DE REGIME: decisão judicial regride o interno ao regime fechado em razão da evasão de 05/02/2025.")]))
ok(any(x.get("data_fato") == "05.02.2025" and "homolog" in (x.get("situacao") or "") for x in f.get("faltas") or []),
   "regressão pela evasão sem 'falta': %s" % f.get("faltas"))

# 4. casos da cobertura (pela Api da tela), numa base nova só com eles
aqui = os.path.dirname(os.path.abspath(__file__))
ids = "S2007,S2016,S2019,S2032,S2038,S2049,S2050,S2051,S2052,S2053"
env = dict(os.environ, APTO_SIM_DESTINO=os.path.join(tempfile.mkdtemp(), "cob_ficha.sqlite"))
p = subprocess.run([sys.executable, os.path.join(aqui, "casos_simulados", "roda_casos.py"),
                    os.path.join(aqui, "casos_simulados", "cobertura", "ficha.json"), "--vazia", "--so", ids],
                   capture_output=True, text=True, env=env, cwd=os.path.join(aqui, "casos_simulados"))
fim = (p.stdout.strip().splitlines() or [""])[-1]
ok(p.returncode == 0 and fim.endswith(" 0 falhas") and "10 casos" in fim,
   "cobertura ficha: %s\n%s" % (fim, "\n".join(l for l in p.stdout.splitlines() if " - FALHA" in l or l.startswith("    x"))))
ok("Traceback" not in p.stdout + p.stderr, "erro interno na releitura: %s" % (p.stdout + p.stderr)[-1500:])

if falhas:
    print("FALHOU (cobertura ficha):")
    for x in falhas:
        print(" - " + x)
    sys.exit(1)
print("ok: cobertura ficha (ano corrigido sem baixa, ciclo 'Nº', regressão pela evasão, falsas fugas, custódia não contada, monitoramento)")
