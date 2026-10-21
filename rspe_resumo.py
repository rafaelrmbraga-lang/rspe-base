"""Resumo para o assistido: a situação da pena, os próximos direitos e o que a Defensoria vai fazer, em linguagem simples
(Pacto Nacional do Judiciário pela Linguagem Simples, CNJ): frases curtas, ordem direta, voz ativa, "você", sem termos
técnicos sem explicação e o mais importante primeiro.

Só entra o que o APTO já calculou. Data duvidosa (aviso "ver Auditoria", "verificar") sai como "a Defensoria está
conferindo", nunca como data. O texto é uma proposta: a janela do APTO deixa editar e tirar cada frase antes do PDF."""
import re
from datetime import date


MESES = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()

PROXIMO_REGIME = {"fechado": "semiaberto", "semiaberto": "aberto"}

# providências que a Defensoria vai adotar: (id, rótulo na janela, frase no resumo)
PROVIDENCIAS = [
    ("ped_prog", "Pedir a progressão de regime", "Vamos pedir a progressão ao juiz."),
    ("acomp_prog", "Acompanhar a data da progressão", "Vamos acompanhar a data da progressão."),
    ("ped_liv", "Pedir o livramento condicional", "Vamos pedir o livramento condicional ao juiz."),
    ("ped_ind", "Pedir o indulto", "Vamos pedir o indulto ao juiz. Indulto é o perdão da pena."),
    ("ped_com", "Pedir a comutação", "Vamos pedir a comutação ao juiz. Comutação diminui a pena."),
    ("ped_rem", "Pedir a remição", "Vamos pedir ao juiz o desconto dos dias de trabalho e estudo."),
    ("ped_ext", "Pedir a extinção da pena", "Vamos pedir ao juiz o fim da pena."),
    ("ped_presc", "Pedir a prescrição", "Vamos pedir a prescrição ao juiz. É quando acaba o prazo para cumprir a pena."),
    ("ped_st", "Pedir a saída temporária", "Vamos pedir a saída temporária ao juiz."),
    ("ofi_atest", "Ofício: atestados de trabalho e estudo", "Vamos pedir à unidade os atestados de trabalho e estudo."),
    ("rspe", "Pedir o cálculo atualizado da pena", "Vamos pedir o cálculo atualizado da sua pena."),
    ("falta", "Defesa na falta disciplinar", "Vamos fazer a sua defesa na falta disciplinar."),
    ("analise", "Analisar o processo", "Vamos analisar o seu processo."),
    ("aguarda", "Acompanhar pedido já feito", "Vamos acompanhar o seu pedido até o juiz decidir."),
]


def _data(txt):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(txt or ""))
    if not m:
        m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(txt or ""))
        if not m2:
            return None
        try:
            return date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError:
            return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def extenso(d):
    """date -> "12 de fevereiro de 2027" ("1º" no primeiro dia do mês)."""
    return "%s de %s de %d" % ("1º" if d.day == 1 else d.day, MESES[d.month - 1], d.year)


def _dias(pena):
    """"3 anos, 6 meses e 16 dias" -> dias (aproximado: ano 365, mês 30); None se não reconhecer."""
    t = str(pena or "").lower()
    if not t or t in ("—", "-"):
        return None
    tot, achou = 0, False
    for n, u in re.findall(r"(\d+)\s*(ano|mes|mês|dia)", t):
        achou = True
        tot += int(n) * {"ano": 365, "mes": 30, "mês": 30, "dia": 1}[u]
    return tot if achou else None


def _sem_pref(s):
    return (s or "").strip().lower()


def _beneficio_data(m, chave, sit_chave):
    """(situação, data, aproximada): situação = futuro | vencido | conferir | None (não entra)."""
    sit = str(m.get(sit_chave) or "")
    v = str(m.get(chave) or "")
    d = _data(v)
    aprox = v.strip().endswith("*")
    s = sit.lower()
    if s.startswith("vencido"):
        return ("vencido", d, aprox) if d else ("conferir", None, False)
    if "ver auditoria" in s or "verificar" in s:
        return "conferir", None, False
    if s.startswith("em cumprimento") or re.match(r"em \d+ dias?", s):
        return ("futuro", d, aprox) if d else (None, None, False)
    return None, None, False


def br(d):
    return d.strftime("%d/%m/%Y")


def _quando(d, aprox):
    return ("por volta de " if aprox else "") + br(d)


def _pct(base, alvo, hoje):
    """quanto do tempo entre a data-base e a data do direito já passou (0 a 100); None sem as duas datas."""
    if not base or not alvo or alvo <= base:
        return None
    return max(0, min(100, round(100.0 * (hoje - base).days / (alvo - base).days)))


def montar(m, pedidos, hoje=None, nome="", data_atend=None):
    """m: modelo do assistido (None se ainda não há RSPE na base); pedidos: {aba: {data, tipo, obs}} do processo;
    data_atend: o atendimento do resumo (hoje, se vazio). Frases curtas, datas em dd/mm/aaaa, sem parênteses.
    -> dados do resumo (editáveis na janela do APTO)."""
    hoje = hoje or date.today()
    nome = (m or {}).get("nome") or nome
    sec_pena, sec_dir, sec_aten = [], [], []
    barra, quadro, pizzas = None, [], {}

    # 1) a pena hoje: quadro (regime, pena total, remição) e a pizza do que já cumpriu e do que falta, com o fim previsto
    if not m:
        sec_pena.append("Ainda não temos o cálculo atualizado da sua pena.")
    else:
        reg = str(m.get("regime") or "").strip()
        r0 = reg.split(" (")[0].strip().lower()
        if "livramento" in r0:
            sec_pena.append("Você está em livramento condicional.")
        elif r0 in ("fechado", "semiaberto", "aberto") and "não iniciado" in reg.lower():
            sec_pena.append("O cumprimento da pena ainda não começou.")
        tot, cum, rem = m.get("pena_total"), m.get("pena_cumprida"), m.get("pena_rem")
        ext = str(m.get("ext_sit") or "")
        mr = re.match(r"\s*(\d+)\s*dias?", str(m.get("remidos") or ""))
        rem_d = int(mr.group(1)) if mr else 0
        dt = _data(m.get("termino"))
        fim = ""
        if ext.startswith("Extinção cabível"):
            fim = "pode já ter terminado"
        elif dt and not ext.startswith(("Pena interrompida", "Pena suspensa", "Pena extinta")):
            fim = _quando(dt, str(m.get("termino")).strip().endswith("*"))
        quadro = [["Regime atual", reg.split(" (")[0] or "—"], ["Pena total", tot if _dias(tot) else "—"],
                  ["Dias tirados pelo trabalho e estudo", "%d dias" % rem_d if rem_d else "zero"]]
        if _dias(cum) and _dias(rem) is not None:
            t_ = (_dias(cum) or 0) + (_dias(rem) or 0)
            if t_:
                falta = rem if _dias(rem) and not ext.startswith("Extinção cabível") else ""
                barra = {"pct": round(100.0 * (_dias(cum) or 0) / t_), "cumprida": cum, "falta": falta, "fim": fim}
        if ext.startswith("Extinção cabível") and not (pedidos or {}).get("ext"):
            sec_pena.append("Sua pena pode já ter terminado. A Defensoria vai analisar.")

    # 2) próximos direitos: "Título: frase. frase." (a janela edita; o PDF põe cada frase numa linha, com a pizza do tempo já cumprido)
    if m:
        ped = pedidos or {}
        r0 = str(m.get("regime") or "").split(" (")[0].strip().lower()
        prox = PROXIMO_REGIME.get(r0)
        bruto = m.get("_bruto") or {}
        # falta grave: a contagem da progressão recomeça (STJ, Súmula 534) e o SEEU refaz a data-base e a data. Vale a data do RSPE:
        # RSPE gerado depois da homologação já traz a data refeita; RSPE anterior a ela ainda não (sem data). O livramento não é
        # interrompido pela falta grave (Súmula 441), mas exige 12 meses sem falta grave (CP, art. 83, III, "b").
        fa = str(m.get("falta") or "")
        dfa, ger = _data(fa) if fa.startswith("Sim") else None, _data(m.get("geracao"))

        def pedido_rspe(chave):
            """situação do último pedido registrado no RSPE: ("pendente"|"negado"|"", data)"""
            v = str(m.get(chave) or "").lower()
            return ("pendente" if v.startswith("pendente") else "negado" if v.startswith("negado") else ""), _data(v)

        def direito(titulo, fracao, chave, sit_chave, ped_chave, base, comportamento, aviso_falta):
            sit, d, ap = _beneficio_data(m, chave, sit_chave)
            if not sit:
                return
            pr, dp = pedido_rspe(ped_chave)
            # primeiro o dia do benefício (a palavra que o assistido entende; "data-base" ele confunde com o dia do benefício, por isso
            # a fração e a data-base vão no PDF em "Outras informações", menores); depois o que mais precisa
            fr = ("Fração do SEEU: %s." % fracao) if fracao else ""
            db = _data(base)
            if db and aviso_falta != "refazer":  # a data-base do RSPE anterior à falta grave já não vale
                fr += " Data-base: %s." % br(db)
            extra = ""
            doze = " Também precisa de 12 meses sem falta grave." if aviso_falta == "12meses" else ""
            if pr == "pendente":
                txt = "Já tem pedido no processo%s. Aguarde a decisão do juiz." % (", desde " + br(dp) if dp else "")
            elif pr == "negado" and sit == "vencido":
                txt = "O juiz negou o pedido%s. A Defensoria vai analisar." % (" em " + br(dp) if dp else "")
            elif aviso_falta == "refazer":
                txt = "A data vai ser refeita por causa da falta grave."
            elif sit == "futuro":
                txt = ("Completa o tempo em %s." if doze else "Dia do benefício: %s.") % _quando(d, ap)
                extra = comportamento + doze
            elif sit == "vencido":
                txt = "Já tem o tempo desde %s." % _quando(d, ap)
                extra = (comportamento + doze) if doze else "A Defensoria vai analisar."
            else:
                txt = "A Defensoria está conferindo a data."
            sec_dir.append("%s: %s" % (titulo, " ".join(x.strip() for x in (txt, extra, fr) if x.strip())))
            if d and sit in ("futuro", "vencido") and aviso_falta != "refazer":
                p_ = 100 if sit == "vencido" else _pct(_data(base), d, hoje)
                if p_ is not None:
                    pizzas[titulo] = p_

        if prox and not ped.get("prog"):
            direito(prox.capitalize(), m.get("frac_prog"), "prog", "prog_sit", "ped_prog", m.get("dbase"),
                    "Precisa ter bom comportamento.", "refazer" if dfa and ger and ger < dfa else "")
        if "livramento" not in r0 and not ped.get("liv"):
            dl = _data(m.get("liv"))
            direito("Livramento condicional", m.get("frac_liv"), "liv", "liv_sit", "ped_liv",
                    bruto.get("livramento_data_base_seeu") or m.get("dbase"), "Precisa ter bom comportamento.",
                    "12meses" if dfa and dl and (max(dl, hoje) - dfa).days < 365 else "")
        ind_ped = bool(ped.get("ind"))  # pedido antigo, sem decreto; o de um decreto (ind_<ano>) só tira aquele decreto
        if not ind_ped:
            for ano, ki, kc in (("2025", "i25", "c25"), ("2024", "i24", "c24"), ("2022", "i22", None)):
                if ped.get("ind_" + ano):
                    continue
                vi, vc = str(m.get(ki) or ""), str(m.get(kc) or "") if kc else ""
                if vi == "Sim":
                    sec_dir.append("Indulto %s: Você pode ter direito. Indulto é o perdão da pena. A Defensoria vai analisar." % ano)
                elif vc == "Sim":
                    sec_dir.append("Comutação %s: Você pode ter direito. Comutação diminui a pena. A Defensoria vai analisar." % ano)
                elif vi == "Verificar" or vc == "Verificar":
                    sec_dir.append("Indulto ou comutação %s: A Defensoria vai verificar se você tem direito." % ano)
                else:
                    continue
                break  # só o decreto mais recente que alcança
        if not sec_dir:
            sec_dir.append("Neste momento, não há data próxima de novo direito.")

    # 3) o que a Defensoria vai fazer: quem atendeu marca na janela as providências que serão adotadas e escreve outras; as frases
    # saem no PDF (nada vem marcado: é a decisão de quem atendeu)
    da = data_atend or hoje
    provs = [{"id": i_, "rot": r_, "frase": f_, "marcado": False} for i_, r_, f_ in PROVIDENCIAS]

    # 4) atenção
    if m:
        fa = str(m.get("falta") or "")
        if fa.startswith("Sim"):
            dfa = _data(fa)
            sec_aten.append("Você tem falta grave%s. Ela pode atrasar seus direitos." % (", confirmada em " + br(dfa) if dfa else ""))
        elif fa.startswith("A apurar"):
            sec_aten.append("Há uma falta em apuração. Se for confirmada, pode atrasar seus direitos.")
    sec_aten += ["Trabalhar e estudar diminui a pena.", "Bom comportamento ajuda nos seus direitos."]

    secoes = [{"id": "pena", "titulo": "Sua pena hoje", "itens": sec_pena}]
    if m:
        secoes.append({"id": "direitos", "titulo": "Seus próximos benefícios", "itens": sec_dir})
    secoes += [{"id": "prov", "titulo": "O que a Defensoria vai fazer", "itens": []},
               {"id": "atencao", "titulo": "Fique atento", "itens": sec_aten}]
    ger = (m or {}).get("geracao") or ""
    rodape = ("Datas do SEEU de %s. Elas podem mudar com decisões do juiz, faltas, trabalho e estudo." % ger if m else "")
    V = verso(m)
    return {"nome": nome, "proc": (m or {}).get("proc") or "", "hoje": hoje.strftime("%d/%m/%Y"), "barra": barra,
            "quadro": quadro, "pizzas": pizzas, "vara": (m or {}).get("vara") or "",
            "secoes": secoes, "rodape": rodape, "data_atend": da.strftime("%d/%m/%Y"), "providencias": provs, "outro": "",
            "verso": V, "verso_modo": "remicao" if V["itens"] else "",
            "verso_fontes": ("Informações da ficha da unidade%s e do SEEU de %s." % (
                (" de " + V["ficha"]) if V["ficha"] else "", ger)) if V["itens"] else ""}


# --------------------------------------------------------------------------- #
# verso do resumo (2ª folha): trabalho em cima, estudo embaixo; com os dias descontados da pena ou só o histórico
_SEM_UN = ("Unidade não identificada na ficha", "—", "-")


def _dt_ini(per):
    d = _data(per)
    return d or date.max


def _per_simples(per):
    """'08/07/2026 a hoje (em curso)' -> 'desde 08/07/2026'"""
    per = str(per or "").strip()
    mm = re.match(r"(\d{2}/\d{2}/\d{4}) a (?:hoje|\d{2}/\d{2}/\d{4} \(em curso)", per)
    return ("desde " + mm.group(1)) if mm else per


def verso(m):
    """Itens do verso, pelo modelo da aba Ficha (fd_novo: trabalho da ficha x atestados e documentos de remição). Cada item: grupo,
    tipo (ok = já descontado - só o documento marcado "✓ Homologado" na conferência; pend = ainda não descontado - documento posterior
    à última decisão de remição, ou trabalho depois do último atestado, sem atestado; curso = trabalhando agora; conf = a Defensoria vai
    conferir), onde, unidade, período, quantidade, situação, detalhe, dias já descontados e dias que ainda podem ser descontados. O RSPE
    não diz de qual atestado veio cada remição: o resto fica "a Defensoria vai conferir"."""
    out = {"itens": [], "ficha": ""}
    if not m or not m.get("ficha_tem"):
        return out
    out["ficha"] = str((m.get("ficha") or {}).get("data_impressao") or "").split(" ")[0].replace(".", "/")
    N = m.get("fd_novo") or {}
    trab, est = [], []

    def item(lst, grupo, tipo, onde, un, per, qtd, sit, det, ok=0.0, pend=0.0):
        lst.append({"grupo": grupo, "tipo": tipo, "onde": onde or "", "un": "" if (un or "—") in _SEM_UN else un, "per": _per_simples(per),
                    "qtd": qtd or "", "sit": sit, "det": det, "dias_ok": ok, "dias_pend": pend})

    fmt = lambda d: d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d or "")
    docs = {d["chave"]: d for d in N.get("docs") or []}
    for L in (N.get("trab") or {}).get("linhas") or []:
        d = docs.get(L.get("at_chave")) if L["st"] in ("auto", "manual") else None
        qtd = "%d dias" % (d["trab"] if d and d.get("trab") else L["dias"])
        if L["st"] == "sem" and L.get("em_curso"):
            item(trab, "trabalho", "curso", L["local"], L.get("un"), L["periodo"], qtd, "Trabalhando agora", "o atestado sai ao fim do período")
        elif L["st"] == "sem" and L.get("pedir_dias"):
            item(trab, "trabalho", "pend", L["local"], L.get("un"), L["periodo"], qtd, "Ainda não descontado",
                 "falta o atestado da unidade · cerca de %d dias" % int(L["pedir_dias"]), pend=L["pedir_dias"])
        elif d and d.get("hom"):
            item(trab, "trabalho", "ok", L["local"], L.get("un"), L["periodo"], qtd, "Já descontado",
                 "atestado nº %s, decisão conferida pela Defensoria" % d["num"])
        elif d and d.get("cor") in ("vermelho", "amarelo") and (d.get("sit") or "").startswith(("Posterior", "Sem remição", "Sem peticionamento e posterior")):
            item(trab, "trabalho", "pend", L["local"], L.get("un"), L["periodo"], qtd, "Ainda não descontado",
                 "o atestado nº %s foi feito; falta o juiz decidir" % d["num"], pend=d.get("dias") or 0)
        else:
            item(trab, "trabalho", "conf", L["local"], L.get("un"), L["periodo"], qtd, "A Defensoria vai conferir",
                 ("se o atestado nº %s já foi descontado" % L["at"]) if L.get("at") else "com a unidade, se há atestado do período")
    for d in N.get("docs") or []:
        if d.get("fora") or d["tipo"] in ("Atestado de trabalho", "Trabalho (informado por você)"):
            continue
        if d["tipo"] == "Leitura":
            onde, qtd = "Leitura de livro", rs_pl(int((d.get("dias") or 0) // 4), "livro", "livros") if d.get("dias") else ""
        elif d["tipo"] == "Exame":
            onde, qtd = "Prova do " + (d.get("num") or "exame"), ""
        else:
            onde, qtd = d["tipo"], d.get("num") or ""
        per = "entregue em %s" % fmt(d.get("emissao"))
        if d.get("hom"):
            item(est, "estudo", "ok", onde, d.get("un"), per, qtd, "Já descontado", "decisão conferida pela Defensoria", ok=d.get("dias") or 0)
        elif (d.get("sit") or "").startswith(("Posterior", "Sem remição")) and d["tipo"] != "Exame":
            item(est, "estudo", "pend", onde, d.get("un"), per, qtd, "Ainda não descontado", "falta o juiz decidir%s" % (
                (" · até %s dias" % int(d["dias"])) if d.get("dias") else ""), pend=d.get("dias") or 0)
        else:
            item(est, "estudo", "conf", onde, d.get("un"), per, qtd, "A Defensoria vai conferir", "se o desconto já foi feito")
    trab.sort(key=lambda x: _dt_ini(x["per"]))
    est.sort(key=lambda x: _dt_ini(x["per"]))
    out["itens"] = trab + est
    for i, x in enumerate(out["itens"]):
        x["id"] = "v%d" % i
    return out


def rs_pl(n, s, p):
    return "%d %s" % (n, s if n == 1 else p)
