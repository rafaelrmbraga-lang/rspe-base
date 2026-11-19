"""Relatório de pena alternativa do SEEU (aba Medidas Diversas da Prisão > Gerar Relatório): leitura (rspe_alternativa.ler) e
avaliação do cumprimento (rspe_alternativa.avaliar) sobre o relatório fictício no leiaute real, com as contas feitas à mão.
Uso: python teste_pena_alternativa.py"""
import os
import sys
import tempfile
from datetime import date

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "seeu_ficticio"))
import pdfplumber  # noqa: E402
import alternativa_pdf as ap  # noqa: E402
import rspe_alternativa as ra  # noqa: E402

p = ap.gerar(os.path.join(tempfile.mkdtemp(), "alt.pdf"))
with pdfplumber.open(p) as d:
    rel = ra.ler([x.extract_text() or "" for x in d.pages])
assert rel["processo"] == "9900001-00.2026.8.12.0001", rel["processo"]
m = rel["medidas"][0]
assert m["titulo"].startswith("Substituição de Pena Privativa") and m["status"] == "ATIVA" and m["inicio"] == "30/10/2025", m
pc, ps = m["condicoes"]
assert pc["nome"] == "Prestação pecuniária" and pc["unidade"] == "R$" and pc["status"] == "VERIFICAR" and len(pc["cumprimentos"]) == 4, pc
assert ps["nome"] == "Prestação de serviços à comunidade" and ps["unidade"] == "h" and len(ps["cumprimentos"]) == 4, ps
a, b = ra.avaliar(rel, date(2026, 3, 15))
# pecuniária: 30/01 e 28/02 vencidas sem pagamento (2 x 330,60) + a de 30/12 paga a menor (330,60 - 300,60 = 30,00) = 691,20
# o título traz o saldo do relatório ("Total A Pagar": 3.306,00 - 631,20 pagos = 2.674,80) e, dele, o que já venceu
assert a["titulo"] == "Prestação pecuniária: faltam R$ 2.674,80 · R$ 691,20 em atraso" and not a["em_dia"], a
assert any("2 parcelas vencidas sem pagamento" in x for x in a["pendencias"]) and any("diferença de R$ 30,00" in x for x in a["pendencias"])
assert any("status no SEEU: verificar" in x for x in a["pendencias"])
# PSC: 3 meses vencidos (nov, dez, jan) x 10 h = 30 h devidas; 16 h cumpridas -> 14 h; janeiro sem registro
assert b["titulo"] == "PSC: faltam 104 h · 14 h em atraso" and any("1 mês vencido sem registro" in x for x in b["pendencias"]), b
# antes do 1º vencimento: em dia (o status "verificar" do SEEU continua sendo ponto a conferir)
a0, b0 = ra.avaliar(rel, date(2025, 11, 1))
assert b0["em_dia"] and b0["valor"] == "faltam 104 h · em dia" and not a0["em_dia"] and a0["pendencias"] == ["status no SEEU: verificar"], (a0, b0)
print("ok: pena alternativa (leitura do relatório do SEEU; parcelas vencidas e pagas a menor; horas de PSC devidas x cumpridas)")
