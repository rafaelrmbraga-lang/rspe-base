"""Ficha disciplinar no painel do SEEU (extensão 1.15): (1) a leitura da ficha a partir dos caracteres (rspe_pdf_paginas,
como o pdf.js entrega no navegador) é a mesma do pdfplumber (rspe_ficha.extrair); (2) nos casos simulados com ficha, o painel
com a ficha carregada é o MESMO que o APTO monta com a ficha vinculada ao processo na base; (3) ficha de outra pessoa não é
usada (e o painel diz isso); (4) ficha impressa há mais de 90 dias: conferir a atual; (5) com a ficha, o indulto possível sem
falta deixa de pedir a conferência da falta grave. Rodar: python teste_ficha_painel.py"""
import copy
import json
import os
import sys
import tempfile
import types
from datetime import date, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "ferramentas", "seeu_ficticio"))
sys.path.insert(0, os.path.join(AQUI, "casos_simulados"))
wv = types.ModuleType("webview")
wv.SAVE_DIALOG, wv.FOLDER_DIALOG, wv.OPEN_DIALOG = 1, 2, 0
sys.modules.setdefault("webview", wv)
os.environ.setdefault("APTO_SIM_DESTINO", os.path.join(tempfile.mkdtemp(), "base_ficha_painel.sqlite"))
import pdfplumber  # noqa: E402
import seeu  # noqa: E402
import rspe_ficha as rf  # noqa: E402
import rspe_painel as rp  # noqa: E402
import rspe_pdf_paginas as pp  # noqa: E402
import rspe_seeu_abas as ra  # noqa: E402

HOJE = date(2026, 10, 12)
falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


# (1) caracteres -> páginas no formato do pdfplumber -> mesma ficha
try:
    import ficha_pdf as fp
    d = tempfile.mkdtemp()
    for nome, kw in (("a", {"eventos": fp.EXEMPLO}), ("b", {"eventos": fp.EXEMPLO * 5, "por_pagina": 8}), ("c", {"eventos": [], "oculto": False})):
        cam = fp.gerar(os.path.join(d, nome + ".pdf"), **kw)
        with pdfplumber.open(cam) as pdf:
            dados = [pp.de_pdfplumber(p) for p in pdf.pages]
        a = rf.extrair(cam)
        b = rf.extrair_paginas_pdf(pp.paginas(json.loads(json.dumps(dados))), cam)
        ok(json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str), "ficha %s: leitura pelos caracteres diferente" % nome)
    pagina = pp.paginas(dados)[0]
    ok(isinstance(pagina.extract_text(), str) and pagina.filter(lambda c: False).extract_text() == "", "Página: texto e filtro")
except ImportError:
    pass  # sem o reportlab: os casos (2) a (5) ainda rodam

# (2) mesmo painel que o APTO com a ficha vinculada na base
import roda_casos as rc  # noqa: E402


class _DT(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(HOJE.year, HOJE.month, HOJE.day, 12, 0, 0)


app = rc.app
app.datetime = _DT
casos = json.load(open(os.path.join(AQUI, "casos_simulados", "casos.json"), encoding="utf-8"))
com_ficha = [c for c in casos if c.get("ficha")]
caminho = rc.preparar(com_ficha, True)
tmp = tempfile.mkdtemp()
app.pasta_app = lambda: tmp
app.CONFIG = os.path.join(tmp, "c.json")
app._abrir = lambda c: None
api = app.Api()
api._js = lambda *a: None
api.abrir_base(caminho)
brutos = api.base.todos()
ctx = api._contexto(brutos)
fichas_base = api.base.fichas()
iguais = 0
chaves = ("pena", "marcos", "alertas", "confere", "nao_cabe", "ficha", "ficha_info")
for c in com_ficha:
    r_abas, _ = ra.ler(seeu.abas_dict(c["rspe"]), rp.rs.fmt(HOJE))  # a mesma leitura da extensão (as abas lidas hoje)
    bruto = next(x for x in brutos if x.get("processo_execucao") == c["processo"])
    sub_apto = json.loads(json.dumps(app._ctx_de(ctx, bruto), default=app._enc_chave))
    p_apto = rp.analisar(r_abas, sub_apto, HOJE)
    f = fichas_base.get(c["processo"])  # a ficha como o APTO a guarda (relida pela versão atual)
    p_ext = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": rp.rs.fmt(HOJE), "fichas": [f]}, ensure_ascii=False, default=str)))
    if all(json.dumps(p_apto[k], sort_keys=True) == json.dumps(p_ext[k], sort_keys=True) for k in chaves):
        iguais += 1
    else:
        falhas.append("%s: painel com a ficha diferente do APTO (%s)" % (c["id"], [k for k in chaves if p_apto[k] != p_ext[k]]))
    ok(p_ext["ficha"] is True, "%s: ficha da própria pessoa não usada" % c["id"])
ok(iguais == len(com_ficha), "mesmo painel do APTO com a ficha em %d de %d" % (iguais, len(com_ficha)))

# (3) ficha de outra pessoa: não usada, e o painel avisa
c = com_ficha[0]
outra = dict(fichas_base[c["processo"]], nome="OUTRA PESSOA QUALQUER", cpf="", data_nascimento="", nome_mae="MÃE DIFERENTE", autos=[])
p = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": "12/10/2026", "fichas": [outra]}, ensure_ascii=False, default=str)))
ok(p["ficha"] is False and any(a["id"] == "ficha_outra" for a in p["alertas"]), "ficha de outra pessoa: não usada e avisada")
# mesmo nome, mãe diferente e nenhum dado objetivo: homônimo, não usada
homon = dict(fichas_base[c["processo"]], cpf="", data_nascimento="", nome_mae="OUTRA MÃE", autos=[])
p = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": "12/10/2026", "fichas": [homon]}, ensure_ascii=False, default=str)))
ok(p["ficha"] is False, "homônimo (mesmo nome, outra mãe): ficha não usada")

# (4) ficha velha
velha = dict(fichas_base[c["processo"]], data_impressao="01/01/2026")
p = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": "12/10/2026", "fichas": [velha]}, ensure_ascii=False, default=str)))
ok(p["ficha_info"] and p["ficha_info"]["velha"] and any(a["id"] == "ficha_velha" for a in p["alertas"]), "ficha de 9 meses: conferir a atual")

# (5) com a ficha, o que dependia dela muda: nenhum alerta pede "falta grave (ficha disciplinar)" quando a ficha foi usada
for c in com_ficha:
    p = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(c["rspe"]), "hoje": "12/10/2026", "fichas": [fichas_base[c["processo"]]]}, ensure_ascii=False, default=str)))
    ok(not any("(ficha disciplinar)" in (a.get("conferir") or "") for a in p["alertas"]), "%s: com a ficha, ainda pede a ficha" % c["id"])

if falhas:
    print("FALHOU:\n  " + "\n  ".join(falhas[:20]))
    sys.exit(1)
print("ok: ficha no painel (leitura pelos caracteres = pdfplumber; %d casos com o mesmo painel do APTO; outra pessoa; ficha velha)" % len(com_ficha))
