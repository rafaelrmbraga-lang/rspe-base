"""Resumo para o assistido (linguagem simples, CNJ): frases a partir do modelo, das providências e dos atendimentos; data
duvidosa sai como "conferindo"; pedido feito tira o direito da lista; as providências do dia do atendimento já vêm marcadas no
resumo do atendimento; atendimento do SAP e do APTO no mesmo dia fica uma vez só (o do APTO, com o que foi feito); PDF de uma página com o canhoto do assistido (pedido do próximo atendimento). Nomes fictícios."""
import os
import shutil
import sys
import tempfile
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rspe_resumo as rres  # noqa: E402
import rspe_relatorio as rrel  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


HOJE = date(2026, 10, 14)
M = {"id": "0000001-00.2026.8.12.0001", "proc": "0000001-00.2026.8.12.0001", "nome": "FULANO DE TESTE", "regime": "Fechado",
     "pena_total": "6 anos", "pena_cumprida": "2 anos", "pena_rem": "4 anos", "remidos": "30 dias (30 dias remidos - 0 dias perdidos)",
     "termino": "10/10/2030", "ext_sit": "Em cumprimento", "prog": "12/02/2027", "prog_sit": "Em cumprimento",
     "liv": "01/01/2025", "liv_sit": "Vencido há 651 dias · sem pedido no RSPE - requerer", "i25": "Sim", "c25": "Prejudicada",
     "falta": "Sim · HOMOLOGAÇÃO DE FALTA GRAVE 01/06/2026", "geracao": "10/10/2026"}


def itens(d, sid):
    return next((s["itens"] for s in d["secoes"] if s["id"] == sid), [])


try:
    d = rres.montar(M, {}, [], HOJE)
    pena, dirs, aten = itens(d, "pena"), itens(d, "direitos"), itens(d, "atencao")
    ok(pena[0] == "Você está no regime fechado." and "Faltam 4 anos" in pena[2] and "30 dias" in pena[3], "pena: %s" % pena)
    ok(any("10 de outubro de 2030" in x for x in pena), "término por extenso")
    ok(d["barra"]["pct"] == 33, "barra: %s" % d["barra"])
    ok(dirs[0].startswith("Ir para o regime semiaberto: a partir de 12 de fevereiro de 2027"), "progressão futura: %s" % dirs[0])
    ok("já cumpriu o tempo necessário em 1º de janeiro de 2025" in dirs[1] and "se for o caso" in dirs[1], "livramento vencido: %s" % dirs[1])
    ok(dirs[2].startswith("Indulto de 2025") and len(dirs) == 3, "indulto: só o decreto mais recente: %s" % dirs)
    ok(aten[0].startswith("Consta falta grave confirmada pelo juiz em 1º de junho de 2026"), "falta grave: %s" % aten)
    # data duvidosa: não sai como data
    d2 = rres.montar(dict(M, prog_sit="Em cumprimento · percentual do SEEU acima do legal - ver Auditoria"), {}, [], HOJE)
    ok(itens(d2, "direitos")[0] == "Ir para o regime semiaberto: a Defensoria está conferindo a data.", "data a conferir: %s" % itens(d2, "direitos")[0])
    ok("12 de fevereiro" not in " ".join(itens(d2, "direitos")), "data a conferir não aparece")
    # pedido feito: sai dos direitos e entra no que a Defensoria fez; atendimento do mesmo dia (SAP e APTO) uma vez só
    regs = [{"nome": "FULANO DE TESTE", "data": "2026-10-14", "tipo": "VIDEO CONFERENCIA"}, {"nome": "FULANO DE TESTE", "data": "2026-08-12", "tipo": "PRESENCIAL"},
            {"nome": "OUTRA PESSOA", "data": "2026-09-01", "tipo": "PRESENCIAL"}]
    man = [{"nome": "Fulano de Teste", "data": "2026-10-14", "obs": "explicamos o cálculo da pena", "registrado_em": "2026-10-14 10:00:00"}]
    at = rres.atendimentos_da_pessoa("FULANO DE TESTE", regs, man)
    ok(len(at) == 2 and at[0]["fonte"] == "apto" and at[1]["data"] == "2026-08-12", "atendimentos da pessoa: %s" % at)
    d3 = rres.montar(M, {"liv": {"data": "14/10/2026", "tipo": "pedido"}, "fd": {"data": "14/10/2026", "tipo": "oficio"},
                         "prog": {"data": "01/09/2026", "tipo": "pedido"}}, at, HOJE)
    ok(not any(x.startswith("Livramento") for x in itens(d3, "direitos")), "pedido feito sai dos direitos")
    marc = {p["id"] for p in d3["providencias"] if p["marcado"]}
    ok(marc == {"explicou", "ped_liv", "ofi_atest"}, "providências do dia do atendimento já marcadas: %s" % marc)
    ok(d3["outro"] == "explicamos o cálculo da pena" and d3["data_atend"] == "14/10/2026", "o que foi feito registrado no APTO: %s" % d3["outro"])
    ok(any(s_["id"] == "atend" for s_ in d3["secoes"]) and not any(s_["id"] == "fez" for s_ in d3["secoes"]), "seção do resumo do atendimento")
    # sem RSPE na base
    d4 = rres.montar(None, {}, [], HOJE, "BELTRANO SEM RSPE")
    ok(d4["nome"] == "BELTRANO SEM RSPE" and "ainda não tem o relatório" in itens(d4, "pena")[0] and not itens(d4, "direitos"), "sem RSPE")
    # extinção cabível: sem "faltam"
    d5 = rres.montar(dict(M, ext_sit="Extinção cabível", pena_rem="2 dias"), {}, [], HOJE)
    ok(not any("Faltam" in x for x in itens(d5, "pena")) and any("pode já ter terminado" in x for x in itens(d5, "pena")), "extinção cabível")
    ok(rres.montar(dict(M, pena_rem="1 ano"), {}, [], HOJE)["secoes"][0]["itens"][2].endswith("Falta 1 ano."), "singular: falta 1 ano")
    # PDF de uma página, com o canhoto
    tmp = tempfile.mkdtemp()
    try:
        pdf = os.path.join(tmp, "Resumo.pdf")
        sec = [dict(s_, itens=[p["frase"] for p in d3["providencias"] if p["marcado"]]) if s_["id"] == "atend" else s_ for s_ in d3["secoes"]]
        rrel.relatorio_resumo_assistido(dict(d3, secoes=sec, retorno="60"), pdf)
        import pdfplumber
        with pdfplumber.open(pdf) as p:
            n = len(p.pages)
            txt = p.pages[0].extract_text() or ""
        ok(n == 1, "uma página: %d" % n)
        ok("Resumo da sua pena" in txt and "FULANO DE TESTE" in txt and "Resumo do atendimento de 14 de outubro de 2026" in txt
           and "Pedimos ao juiz o livramento condicional." in txt and "setor psicossocial da unidade" in txt and "Retorno em" in txt
           and "recorte aqui" in txt and "Data do retorno: 13/12/2026" in txt, "conteúdo do PDF")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %s" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: resumo para o assistido (linguagem simples, datas a conferir, pedidos e atendimentos, PDF com canhoto)")
