"""Teste da linha E (tela aprovada em 27/10/2026): "Parar depois deste arquivo" na importação (o que já foi lido fica, o resumo diz
quantos não foram lidos), falhas contadas no andamento e as peças da tela (Importar num botão, menu lateral que recolhe, filtros
combináveis, ordem por situação, "A verificar" separado, complemento "sem pedido no RSPE" fora da coluna, avisos, legenda, busca
vazia). Arquivos fictícios numa pasta temporária. Rodar: python teste_linha_e.py"""
import os
import sys
import tempfile
import types

_wv = types.ModuleType("webview")
_wv.SAVE_DIALOG, _wv.FOLDER_DIALOG, _wv.OPEN_DIALOG = 1, 2, 0
sys.modules["webview"] = _wv

import rspe_app as app  # noqa: E402

TMP = tempfile.mkdtemp(prefix="apto_linha_e_")
app.pasta_app = lambda: TMP
app.CONFIG = os.path.join(TMP, "rspe_config.json")
app._abrir = lambda c: None
DIR = os.path.dirname(os.path.abspath(__file__))
UI = open(os.path.join(DIR, "ui.html"), encoding="utf-8").read()
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


# importação parada a pedido: cada arquivo fictício falha na leitura; o pedido de parar chega durante o 2º
base = app.Base(os.path.join(TMP, "t.sqlite"))
api = app.Api.__new__(app.Api)
js = []
api._js = lambda c, *a, **k: js.append(c)
cont = [0]


def _extrai(a):
    cont[0] += 1
    if cont[0] == 2:
        api._parar_imp = True
    raise ValueError("não parece um RSPE do SEEU nem uma Ficha Disciplinar do SIAPEN")


app._extrair_com_hash = _extrai
arqs = [os.path.join(TMP, "SIMULADO_%03d.pdf" % i) for i in range(1, 9)]
res = api._lote_(arqs, base, False)
ok(res.get("parados", 0) >= 1 and res["erros"] + res["parados"] == len(arqs), "parar: lidos + não lidos = lote (%s)" % res)
ok(res["avisos"] and res["avisos"][0].startswith("Importação parada a pedido:") and "importe de novo" in res["avisos"][0], "parar: aviso no topo")
ok(any(c.startswith("ui.progresso(") and c.count(",") == 2 for c in js), "andamento leva as falhas até agora: %s" % js[:3])
ok(js and js[0] == "ui.progresso(0,%d,0)" % len(arqs), "andamento começa em 0, com 0 falhas")
ok("parciais" in res, "resumo traz as leituras parciais (para o total 'com ressalva')")
# sem pedido de parar, o lote vai até o fim (o pedido anterior não fica valendo)
cont[0] = 10
app._extrair_com_hash = lambda a: (_ for _ in ()).throw(ValueError("ilegível"))
res2 = api._lote_(arqs[:3], base, False)
ok(res2.get("parados") == 0 and res2["erros"] == 3, "lote seguinte começa sem o pedido de parar: %s" % res2)
r = app.Api.parar_importacao(api)
ok(api._parar_imp is True and "parar" in r.get("msg", ""), "parar_importacao marca o pedido e avisa")

# tela
for t, m in [("id=\"mImp\"", "Importar num botão com menu"), ("onclick=\"api('importar_pdfs')\"", "menu Importar: arquivos PDF"),
             ("onclick=\"api('importar_pasta')\"", "menu Importar: pasta inteira"), ("menuAlternar()", "menu lateral recolhe e expande"),
             ("localStorage.setItem('apto_menu'", "a escolha do menu fica gravada"), ("window.innerWidth/z<1400", "notebook (ou letra maior): menu começa recolhido"),
             ("NAV_GRUPOS:[[null,['geral']],['Prazos'", "abas agrupadas por tarefa"), ("passaUm(r,spec,f)", "filtros combináveis"),
             ("Object.values(G).every(L=>L.some(", "no mesmo grupo vale qualquer um; entre grupos, todos"),
             ("this.ordSit[spec.id]!==false", "ordem por situação é o padrão"), ("SEM_CMP:['sem pedido no RSPE - requerer']", "complemento fora da coluna"),
             ("out.verificar='A verificar'", "'A verificar' com contador próprio"), ("--v-dot:#B5651D", "'A verificar' na cor do RSPE antigo"),
             ("ui.impParar()", "botão Parar depois deste arquivo"), ("api('parar_importacao')", "tela chama parar_importacao"),
             ("<summary>Método completo</summary>", "método completo a um clique"), ("Limpar busca</button>", "busca vazia oferece Limpar busca"),
             ("{desfazer:volta}", "aviso de pedido com Desfazer"), ("ui.toastFechar()", "aviso de erro fica até fechar"),
             ("@media (max-width:1400px)", "modo compacto em notebook")]:
    ok(t in UI, "tela: " + m)
ok("Importar PDFs</button>" not in UI and "Importar pasta</button>" not in UI, "tela: os dois botões de importar viraram um")
ok("<div class=\"bar\">" not in UI, "tela: cabeçalho numa faixa só")

if falhas:
    print("FALHOU teste_linha_e:\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: linha E (parar a importação, falhas no andamento, menu lateral, filtros combináveis, situação, avisos, legenda, busca vazia)")
