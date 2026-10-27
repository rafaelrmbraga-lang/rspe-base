"""7.14.6: forma favorável da detração antes da fração em anos, meses e dias, como o SEEU (6a − 26 dias = 5a11m4d)."""
from fractions import Fraction
import rspe_auditoria as ra
import rspe_scraper as rs

t = ra._texto_blocos([[Fraction(2, 5), rs.pena_para_dias("15a0m0d"), rs.pena_para_dias("5a11m19d"), 26, [5, 11, 19], [15, 0, 0]]])
if not ("descontada depois (pena × fração − detração): 5 anos, 11 meses e 4 dias" in t and "Diferença: 15 dias" in t):
    raise SystemExit("FALHOU: 6a - 26d deve dar 5a11m4d e diferença de 15 dias: " + t)
print("ok: detração antes da fração em anos, meses e dias (7.14.6)")
