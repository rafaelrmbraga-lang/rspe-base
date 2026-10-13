"""Funções de trabalho do defensor (auditoria funcional, 2ª rodada) e "Trazer de" da calculadora: ajuste da prescrição
(pena negativa ou ilegível, data futura, datas invertidas, opções e chaves inexistentes), saldos de fuga inexistente, pedido
com data futura, situação do decreto no pedido do indulto, Histórico com o retorno num RSPE posterior, "Mesma pessoa" com três
homônimos e o desfazer, dados informados impossíveis, regime informado, chaves inexistentes, um só defensor padrão, avisos
do "Trazer de" (art. 75, período fora das interrupções, o que não veio) e "1 dia". Base sintética numa pasta temporária.
Rodar: python teste_trabalho_rev1012.py"""
import copy
import os
import shutil
import sys
import tempfile
import types

_wv = types.ModuleType("webview")
_wv.SAVE_DIALOG, _wv.FOLDER_DIALOG, _wv.OPEN_DIALOG = 1, 2, 0
sys.modules["webview"] = _wv

import rspe_app as app  # noqa: E402
import rspe_scraper as rs  # noqa: E402

TMP = tempfile.mkdtemp(prefix="apto_teste_trabalho_")
app.pasta_app = lambda: TMP
app.PASTA_BASES = os.path.join(TMP, "bases")
app.CONFIG = os.path.join(TMP, "rspe_config.json")
app.VIGIA_ESTADO = os.path.join(TMP, "pasta_vigiada_estado.json")
app.DEFENSORES = os.path.join(TMP, "defensores.json")
app._abrir = lambda c: None

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


class Janela:
    fila = []

    def evaluate_js(self, c):
        pass

    def create_file_dialog(self, tipo, **kw):
        return None


def sint(proc, nome, **kw):
    r = {"processo_execucao": proc, "nome": nome, "data_geracao_rspe": "01/10/2026", "cpf": "", "nome_mae": "",
         "regime_atual": "Fechado - ATIVO", "pena_total": "8a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "5a0m0d",
         "data_base_seeu": "01/03/2023", "versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE, "_hash": "h" + proc[:7],
         "_crimes": [{"processo_criminal": proc, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
                      "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "8 ano(s), 0 mês(es) e 0 dia(s)",
                      "data_infracao": "10/01/2020", "data_denuncia": "10/02/2020", "data_sentenca": "10/06/2020",
                      "transito_mp": "10/07/2020", "transito_processo": "10/07/2020", "extinto": "Não", "suspenso": "Não", "vga": "N",
                      "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
                      "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum"}],
         "_incidentes": [], "_eventos": [{"tipo": "PRISÃO", "motivo": "PRISÃO EM FLAGRANTE", "data": "01/10/2023", "processos": proc}]}
    r.update(kw)
    return r


P1, P2, P3 = "0000001-11.2020.8.12.0001", "0000002-22.2020.8.12.0001", "0000003-33.2020.8.12.0001"
api = app.Api()
api._janela = Janela()
api.nova_base("Trabalho")
for p in (P1, P2, P3):
    api.base.gravar(sint(p, "HOMONIMO DA SILVA"))
api.listar()


def reg(p):
    return api.registro(p)["parcial"][0]


# ---- E1/E2: ajuste da prescrição
L = reg(P1)["presc_linhas"][0]
ch = L["chave_ajuste"]
for vals, palavra in (({"pena": "-2a0m0d"}, "Pena inválida"), ({"pena": "abc"}, "Pena inválida"), ({"transito": "01/01/2099"}, "futura"),
                      ({"fato": "01/01/2025", "sentenca": "01/01/2015"}, "incoerentes"), ({"reinc": "talvez"}, "inválido"),
                      ({"qualquer": "x"}, "desconhecido")):
    r = api.presc_ajuste(P1, ch, {"valores": vals})
    ok(palavra in (r.get("erro") or ""), "ajuste da prescrição %s recusado: %s" % (vals, r.get("erro") or r.get("msg")))
ok(not api.base.presc_ajustes().get(P1), "nada gravado com ajuste inválido")
r = api.presc_ajuste(P1, ch, {"valores": {"pena": "2a6m0d", "reinc": "S"}})
ok(not r.get("erro"), "ajuste válido aceito: %s" % r.get("erro"))
ok(api.presc_ajuste(P1, "nao-existe", {"valores": {"pena": "1a0m0d"}}).get("erro"), "ajuste em crime inexistente recusado")
r = api.presc_saldos_calc(P1, "01/01/2000", {ch: 10})
ok(r.get("erro"), "saldo em fuga inexistente recusado: %s" % (r.get("erro") or r.get("msg")))
r = api.presc_saldos_calc(P1, "01/01/2000", {"chave-inexistente": 10})
ok(r.get("erro") and "chave-inexistente" not in (api.base.presc_ajustes().get(P1) or {}), "saldo em crime inexistente recusado")

# ---- E11/E12: pedidos
ok(api.pedido(P1, "prog", "01/01/2031", "", "x").get("erro"), "pedido com data futura recusado")
api.pedido(P1, "ind_2025", "05/10/2026", "", "", "pedido")
pd = reg(P1)["pedidos"].get("ind_2025") or {}
ok(pd.get("ref") and pd.get("ref") == pd.get("ref_atual"), "pedido do indulto guarda a situação do decreto: %s" % pd)

# ---- E3: Histórico liga o pedido ao retorno em RSPE posterior
api.pedido(P2, "prog", "01/09/2026", "", reg(P2)["prog"], "pedido")
b = copy.deepcopy(api.base.um(P2))
b.pop("importado_em", None)
b.pop("_pessoa_man", None)
b.update(data_geracao_rspe="11/10/2026", _hash="novo")
b["_incidentes"] = [{"tipo": "PROGRESSÃO DE REGIME", "motivo": "", "complemento": "Semiaberto", "data": "", "data_decisao": "05/10/2026",
                     "data_referencia": "05/10/2026", "processos": "", "situacao": "NÃO CONCEDIDO"}]
api.base.gravar(b)
api.listar()
h = api.historico(P2)
peds = [(c["geracao"], p["ret"]) for c in h["colunas"] for p in c["pedidos"]]
ok(("11/10/2026", "indeferida (incidente de 05/10/2026)") in peds and any("retorno no RSPE de 11/10/2026" in x for _, x in peds),
   "Histórico: retorno do pedido no RSPE posterior: %s" % peds)

# ---- E4: mesma pessoa com três homônimos e desfazer
api.mesma_pessoa(P1, P2)
r = api.mesma_pessoa(P2, P3)
man = api.base.pessoa_man()
ok(len({man.get(p) for p in (P1, P2, P3)}) == 1 and None not in {man.get(p) for p in (P1, P2, P3)}, "mesma pessoa junta os três: %s" % man)
ok(len(r["registros"]) == 1, "uma linha para os três: %d" % len(r["registros"]))
ok(len(r["registros"]) == 1 and reg(r["registros"][0]["id"]).get("mesma_pessoa_marcada"), "flag mesma_pessoa_marcada")
r = api.mesma_pessoa_desfazer(P3)
ok(not api.base.pessoa_man() and len(r["registros"]) == 3, "desfazer mesma pessoa: %s" % api.base.pessoa_man())
ok(api.mesma_pessoa_desfazer(P3).get("erro"), "desfazer sem marcação: erro")

# ---- E13/E14: dados informados e chaves inexistentes
for campo, valor in (("data_nascimento", "01/01/2030"), ("data_base", "01/01/2030|x"), ("data_base", "05/10/2026|x"),
                     ("rspe|regime_atual", "não sei se fechado"), ("qualquer_coisa", "x")):
    ok(api.dado_manual(P1, campo, valor).get("erro"), "dado informado impossível recusado: %s=%s" % (campo, valor))
api.base.gravar(dict(sint("0000004-44.2020.8.12.0001", "OUTRO NOME"), regime_atual=""))
api.listar()
api.dado_manual("0000004-44.2020.8.12.0001", "rspe|regime_atual", "semiaberto")
x = reg("0000004-44.2020.8.12.0001")
ok(x["regime"].startswith("Semiaberto") and not x["regime_rspe"], "regime informado: %r / regime_rspe %r" % (x["regime"], x["regime_rspe"]))
ok(api.remover("NAO-EXISTE").get("erro"), "remover inexistente: erro")
ok(api.reabrir_alerta(P1, "t:naoexiste").get("erro") and not api.base.hist_alertas(P1), "reabrir alerta não baixado: erro, sem histórico")

# ---- E15: um só defensor padrão
lst = api.defensores_salvar([{"nome": "A", "padrao": True}, {"nome": "B", "padrao": True}])["lista"]
ok([d["padrao"] for d in lst] == [False, True], "um só defensor padrão: %s" % lst)

# ---- A3/A10/A8: Trazer de e "1 dia"
c = api.calc_assistido(P1)
ok("avisos" in c and c.get("termino_criterio_seeu") and c.get("termino_nota"), "calc_assistido: termino_criterio_seeu, termino_nota, avisos")
api.base.gravar(sint("0000005-55.2020.8.12.0001", "LONGA PENA", pena_total="45a0m0d", pena_cumprida="3a0m0d", pena_remanescente="42a0m0d",
                     _eventos=[{"tipo": "PRISÃO", "motivo": "PRISÃO EM FLAGRANTE", "data": "01/10/2013", "processos": ""}]))
api.base.gravar(sint("0000006-66.2020.8.12.0001", "SEM PENA", pena_total="", pena_cumprida="", pena_remanescente=""))
api.listar()
c = api.calc_assistido("0000005-55.2020.8.12.0001")
ok(any("art. 75" in a for a in c["avisos"]) and any("liberdade" in a for a in c["avisos"]), "avisos: art. 75 e liberdade: %s" % c["avisos"])
c = api.calc_assistido("0000006-66.2020.8.12.0001")
ok("Não veio: pena total" in c["msg"] and any("Sem pena total" in a for a in c["avisos"]), "sem pena total avisado: %s" % c["msg"])
r = api.calc_gravar({"p1": "01/01/2026", "p2": "01/01/2026"})
lst = [x for x in r.get("itens", []) if "período" in (x.get("resumo") or "")]
ok(lst and "(1 dia)" in lst[0]["resumo"], "'1 dia' no resumo: %s" % (lst[0]["resumo"] if lst else r))

shutil.rmtree(TMP, ignore_errors=True)
if falhas:
    print("FALHOU (trabalho rev 12/10):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: trabalho rev 12/10 (ajuste da prescrição, saldos, pedidos, indulto, Histórico, mesma pessoa, dados informados, chaves, "
      "defensor padrão, Trazer de, 1 dia)")
