"""Resumo para o assistido (linguagem simples, CNJ): frases a partir do modelo e das providências; data
duvidosa sai como "conferindo"; pedido feito tira o direito da lista; as providências que a Defensoria vai adotar saem no futuro
("Vamos pedir...");  PDF de uma página com o canhoto do assistido (pedido do próximo atendimento). Nomes fictícios."""
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
M = {"crimes_det": [{"nome_crime": "Furto qualificado", "pena": "6 anos", "proc": "8800001-00.2021.8.12.0001", "extinto": "Não"},
                    {"nome_crime": "Ameaça", "pena": "1 mês", "proc": "8800002-00.2020.8.12.0001", "extinto": "Sim"}],
     "id": "0000001-00.2026.8.12.0001", "proc": "0000001-00.2026.8.12.0001", "nome": "FULANO DE TESTE", "regime": "Fechado",
     "pena_total": "6 anos", "pena_cumprida": "2 anos", "pena_rem": "4 anos", "remidos": "30 dias (30 dias remidos - 0 dias perdidos)",
     "termino": "10/10/2030", "ext_sit": "Em cumprimento", "prog": "12/02/2027", "prog_sit": "Em cumprimento",
     "liv": "01/01/2025", "liv_sit": "Vencido há 651 dias · sem pedido no RSPE - requerer", "i25": "Sim", "c25": "Prejudicada",
     "falta": "Sim · HOMOLOGAÇÃO DE FALTA GRAVE 01/06/2026", "geracao": "10/10/2026", "frac_prog": "16%", "frac_liv": "1/3", "dbase": "01/01/2024"}


def itens(d, sid):
    return next((s["itens"] for s in d["secoes"] if s["id"] == sid), [])


try:
    d = rres.montar(M, {}, HOJE)
    pena, dirs, aten = itens(d, "pena"), itens(d, "direitos"), itens(d, "atencao")
    Q = dict(d["quadro"])
    ok(Q == {"Regime atual": "Fechado", "Pena total": "6 anos", "Dias tirados pelo trabalho e estudo": "30 dias"} and not pena, "quadro: %s %s" % (Q, pena))
    ok(d["barra"] == {"pct": 33, "cumprida": "2 anos", "falta": "4 anos", "fim": "10/10/2030"}, "pizza da pena: %s" % d["barra"])
    ok("condenacoes" not in d, "sem o que cumpre hoje (o atestado vai junto)")
    ok(dirs[0] == "Semiaberto: Dia do benefício: 12/02/2027. Precisa ter bom comportamento. Fração do SEEU: 16%. Data-base: 01/01/2024.",
       "progressão futura: %s" % dirs[0])
    # livramento vencido, mas a falta grave de 01/06/2026 tem menos de 12 meses (CP, art. 83, III, "b")
    ok(dirs[1] == "Livramento condicional: Já tem o tempo desde 01/01/2025. Precisa ter bom comportamento. Também precisa de 12 meses "
       "sem falta grave. Fração do SEEU: 1/3. Data-base: 01/01/2024.", "livramento vencido com falta recente: %s" % dirs[1])
    dv = rres.montar(dict(M, falta="Sim · HOMOLOGAÇÃO DE FALTA GRAVE 01/06/2025"), {}, HOJE)
    ok(itens(dv, "direitos")[1] == "Livramento condicional: Já tem o tempo desde 01/01/2025. A Defensoria vai analisar. "
       "Fração do SEEU: 1/3. Data-base: 01/01/2024.", "livramento vencido, falta com mais de 12 meses: %s" % itens(dv, "direitos")[1])
    ok(dirs[2].startswith("Indulto 2025: Você pode ter direito.") and len(dirs) == 3, "indulto: só o decreto mais recente: %s" % dirs)
    ok(d["pizzas"].get("Livramento condicional") == 100, "pizza do livramento vencido: %s" % d["pizzas"])
    ok(not any("(" in x for x in dirs + aten), "sem parênteses")
    ok(aten[0] == "Você tem falta grave, confirmada em 01/06/2026. Ela pode atrasar seus direitos.", "falta grave: %s" % aten)
    # falta grave: vale a data do RSPE. RSPE gerado depois da homologação traz a data refeita; RSPE anterior a ela ainda não (sem data).
    # O livramento segue com a data do RSPE (Súmulas 534 e 441 do STJ)
    dfg = rres.montar(dict(M, geracao="10/10/2026", dbase="20/05/2026", prog="17/12/2026"), {}, HOJE)
    ok(itens(dfg, "direitos")[0] == "Semiaberto: Dia do benefício: 17/12/2026. Precisa ter bom comportamento. Fração do SEEU: 16%. Data-base: 20/05/2026.",
       "RSPE depois da falta: data do RSPE: %s" % itens(dfg, "direitos")[0])
    ok(dfg["pizzas"]["Semiaberto"] == 70, "pizza da progressão (20/05 a 17/12, hoje 14/10): %s" % dfg["pizzas"])
    dant = rres.montar(dict(M, geracao="15/05/2026"), {}, HOJE)
    ok(itens(dant, "direitos")[0] == "Semiaberto: A data vai ser refeita por causa da falta grave. Fração do SEEU: 16%."
       and "Semiaberto" not in dant["pizzas"] and itens(dant, "direitos")[1].startswith("Livramento condicional"),
       "RSPE anterior à falta: sem data: %s" % itens(dant, "direitos"))
    dl = rres.montar(dict(M, liv="01/03/2027", liv_sit="Em cumprimento"), {}, HOJE)
    ok(itens(dl, "direitos")[1] == "Livramento condicional: Completa o tempo em 01/03/2027. Precisa ter bom comportamento. "
       "Também precisa de 12 meses sem falta grave. Fração do SEEU: 1/3. Data-base: 01/01/2024.", "livramento a menos de 12 meses da falta grave: %s" % itens(dl, "direitos")[1])
    # data duvidosa: não sai como data
    d2 = rres.montar(dict(M, prog_sit="Em cumprimento · percentual do SEEU acima do legal - ver Auditoria"), {}, HOJE)
    ok(itens(d2, "direitos")[0] == "Semiaberto: A Defensoria está conferindo a data. Fração do SEEU: 16%. Data-base: 01/01/2024.", "data a conferir: %s" % itens(d2, "direitos")[0])
    ok("12/02/2027" not in " ".join(itens(d2, "direitos")), "data a conferir não aparece")
    # pedido já feito: sai dos direitos; as providências a adotar não vêm marcadas
    d3 = rres.montar(M, {"liv": {"data": "14/10/2026", "tipo": "pedido"}, "fd": {"data": "14/10/2026", "tipo": "oficio"},
                         "prog": {"data": "01/09/2026", "tipo": "pedido"}}, HOJE)
    ok(not any(x.startswith("Livramento") for x in itens(d3, "direitos")), "pedido feito sai dos direitos")
    ok(not any(p["marcado"] for p in d3["providencias"]) and d3["outro"] == "" and d3["data_atend"] == "14/10/2026",
       "providências a adotar: nada vem marcado")
    ok(all(p["frase"].startswith("Vamos ") and "(" not in p["frase"] for p in d3["providencias"]), "providências no futuro, sem parênteses")
    ok(any(s_["id"] == "prov" and s_["titulo"] == "O que a Defensoria vai fazer" for s_ in d3["secoes"])
       and not any(s_["id"] in ("fez", "atend") for s_ in d3["secoes"]), "seção do que a Defensoria vai fazer")
    # sem RSPE na base
    d4 = rres.montar(None, {}, HOJE, "BELTRANO SEM RSPE")
    ok(d4["nome"] == "BELTRANO SEM RSPE" and "Ainda não temos o cálculo" in itens(d4, "pena")[0] and not itens(d4, "direitos"), "sem RSPE")
    # extinção cabível
    d5 = rres.montar(dict(M, ext_sit="Extinção cabível", pena_rem="2 dias"), {}, HOJE)
    ok(d5["barra"]["falta"] == "" and any("pode já ter terminado" in x for x in itens(d5, "pena")), "extinção cabível")
    # pedido registrado no RSPE: pendente (aguarda decisão) e negado
    dp = rres.montar(dict(M, ped_prog="pendente (15/09/2026)"), {}, HOJE)
    ok(itens(dp, "direitos")[0] == "Semiaberto: Já tem pedido no processo, desde 15/09/2026. Aguarde a decisão do juiz. Fração do SEEU: 16%. Data-base: 01/01/2024.",
       "pedido pendente no RSPE: %s" % itens(dp, "direitos")[0])
    dn = rres.montar(dict(M, ped_liv="negado (20/08/2026)"), {}, HOJE)
    ok("O juiz negou o pedido em 20/08/2026." in itens(dn, "direitos")[1], "pedido negado no RSPE: %s" % itens(dn, "direitos"))
    # PDF de uma página, com o canhoto
    tmp = tempfile.mkdtemp()
    try:
        pdf = os.path.join(tmp, "Resumo.pdf")
        fr = {p["id"]: p["frase"] for p in d3["providencias"]}
        sec = [dict(s_, itens=[fr["ped_ind"], fr["falta"]]) if s_["id"] == "prov" else s_ for s_ in d3["secoes"]]
        rrel.relatorio_resumo_assistido(dict(d3, secoes=sec, retorno="60", unidade="UNIDADE PENAL DE TESTE"), pdf)
        import pdfplumber
        with pdfplumber.open(pdf) as p:
            n = len(p.pages)
            txt = p.pages[0].extract_text() or ""
        ok(n == 1, "uma página: %d" % n)
        ok("Resumo da sua pena" in txt and "FULANO DE TESTE" in txt and "O que a Defensoria vai fazer" in txt
           and "O que você cumpre hoje" not in txt and "Sua pena hoje" in txt and "Indulto 2025" in txt and "Já cumpriu" in txt
           and "Vamos pedir o indulto ao juiz." in txt and "psicossocial da unidade" in txt and "Motivo:" in txt and "Trabalho/educação" in txt and "Saldo de salário" not in txt and "PADIC" in txt
           and "Retorno em" not in txt
           and "recorte aqui" in txt and "Data do retorno" not in txt
           and "Unidade: UNIDADE PENAL DE TESTE" in txt and "Processo nº 0000001-00.2026.8.12.0001" in txt.split("recorte aqui")[-1]
           and "Atendido por" not in txt, "conteúdo do PDF")
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
print("ok: resumo para o assistido (linguagem simples, datas do RSPE, falta grave, providências a adotar, PDF com canhoto)")
