"""7.14.5: a aba Extinção mostra a ressalva do limite de cumprimento (CP, art. 75) apontado pela Auditoria, mantendo o término do SEEU."""
import rspe_view as rv

def ok(c, msg):
    if not c:
        raise SystemExit("FALHOU: " + msg)

TR = rv.TRACO
base = {"prog": "", "liv": "", "termino": "", "ext_termino": "23/08/2045", "ext_cor": "", "ext_hipoteses": TR}
m = rv.simplificar(dict(base, aud_itens=[{"tipo": "limite-de-cumprimento-art-75-unificacao", "nivel": "verificar", "baixado": False,
     "titulo": "Término (23/08/2045) além do limite de 30 anos de cumprimento (CP, art. 75), mesmo contado da condenação nova"}]))
ok(m["ext_termino"] == "23/08/2045", "mantém o término do SEEU: %s" % m["ext_termino"])
ok(m["ext_sit"] == "Em cumprimento · art. 75 a verificar" and m["ext_cor"] == "amarelo", "situação com a ressalva: %s %s" % (m["ext_sit"], m["ext_cor"]))
ok("30 anos" in m["ext_sit_full"] and "ver Auditoria" in m["ext_sit_full"], m["ext_sit_full"])
m = rv.simplificar(dict(base, aud_itens=[{"tipo": "limite-de-cumprimento-art-75", "nivel": "verificar", "baixado": True, "titulo": "x"}]))
ok(m["ext_sit"] == "Em cumprimento", "item baixado não gera ressalva: %s" % m["ext_sit"])
m = rv.simplificar(dict(base, aud_itens=[]))
ok(m["ext_sit"] == "Em cumprimento", "sem item, sem ressalva")
print("ok: extinção mostra a ressalva do art. 75 da Auditoria (7.14.5)")
