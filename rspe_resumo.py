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
    ("ped_prog", "Pedir a progressão de regime", "Vamos pedir ao juiz a mudança de regime."),
    ("acomp_prog", "Acompanhar a data da progressão", "Vamos acompanhar a data da mudança de regime e fazer o pedido ao juiz quando ela chegar."),
    ("ped_liv", "Pedir o livramento condicional", "Vamos pedir ao juiz o livramento condicional."),
    ("ped_ind", "Pedir o indulto", "Vamos pedir ao juiz o indulto (perdão da pena)."),
    ("ped_com", "Pedir a comutação", "Vamos pedir ao juiz a comutação (redução da pena)."),
    ("ped_rem", "Pedir a remição", "Vamos pedir ao juiz o desconto dos dias de trabalho e estudo na pena (remição)."),
    ("ped_ext", "Pedir a extinção da pena", "Vamos pedir ao juiz o fim da pena (extinção)."),
    ("ped_presc", "Pedir a prescrição", "Vamos pedir ao juiz o reconhecimento da prescrição (o fim do prazo para cumprir a pena)."),
    ("ped_st", "Pedir a saída temporária", "Vamos pedir ao juiz a saída temporária."),
    ("ofi_atest", "Ofício: atestados de trabalho e estudo", "Vamos pedir à unidade prisional os atestados de trabalho e estudo."),
    ("rspe", "Pedir o cálculo atualizado da pena", "Vamos pedir o cálculo atualizado da sua pena (relatório do SEEU)."),
    ("falta", "Defesa na falta disciplinar", "Vamos acompanhar o procedimento da falta disciplinar e fazer a sua defesa."),
    ("analise", "Analisar o processo", "Vamos analisar o seu processo e, se for o caso, fazer o pedido ao juiz."),
    ("aguarda", "Acompanhar pedido já feito", "Vamos acompanhar o pedido que já está no processo até a decisão do juiz."),
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


def _quando(d, aprox):
    return extenso(d) + (" (data aproximada)" if aprox else "")


def montar(m, pedidos, hoje=None, nome="", data_atend=None):
    """m: modelo do assistido (None se ainda não há RSPE na base); pedidos: {aba: {data, tipo, obs}} do processo;
    data_atend: o atendimento do resumo (hoje, se vazio).
    -> dados do resumo (editáveis na janela do APTO)."""
    hoje = hoje or date.today()
    nome = (m or {}).get("nome") or nome
    sec_pena, sec_dir, sec_aten = [], [], []
    barra = None

    # 1) como está a pena: o quadro com os números (como no atestado de pena do SEEU, sem as frações) e as notas que pedem explicação
    quadro, condenacoes = [], []
    if not m:
        sec_pena.append("A Defensoria ainda não tem o relatório atualizado da sua pena. Por isso, este resumo não traz as datas dos seus direitos.")
    else:
        reg = str(m.get("regime") or "").strip()
        r0 = reg.split(" (")[0].strip().lower()
        if "livramento" in r0:
            sec_pena.append("Você está em livramento condicional: cumpre o resto da pena em liberdade, seguindo as regras do juiz.")
        elif r0 in ("fechado", "semiaberto", "aberto") and "não iniciado" in reg.lower():
            sec_pena.append("O cumprimento da pena no regime %s ainda não começou." % r0)
        tot, cum, rem = m.get("pena_total"), m.get("pena_cumprida"), m.get("pena_rem")
        ext = str(m.get("ext_sit") or "")
        mr = re.match(r"\s*(\d+)\s*dias?", str(m.get("remidos") or ""))
        rem_d = int(mr.group(1)) if mr else 0
        dt = _data(m.get("termino"))
        fim = "—"
        if ext.startswith("Extinção cabível"):
            fim = "pode já ter terminado"
        elif dt and not ext.startswith(("Pena interrompida", "Pena suspensa", "Pena extinta")):
            fim = dt.strftime("%d/%m/%Y") + (" (aproximada)" if str(m.get("termino")).strip().endswith("*") else "")
        quadro = [["Regime atual", reg.split(" (")[0] or "—"], ["Pena total", tot if _dias(tot) else "—"],
                  ["Dias tirados pelo trabalho e estudo", "%d dias" % rem_d if rem_d else "nenhum"],
                  ["Já cumpriu", cum if _dias(cum) else "—"],
                  ["Falta cumprir", rem if _dias(rem) and not ext.startswith("Extinção cabível") else "—"],
                  ["Fim previsto da pena", fim]]
        if _dias(cum) and _dias(rem) is not None:
            t_ = (_dias(cum) or 0) + (_dias(rem) or 0)
            if t_:
                barra = {"pct": round(100.0 * (_dias(cum) or 0) / t_), "cumprida": cum, "falta": rem}
        if ext.startswith("Extinção cabível") and not (pedidos or {}).get("ext"):
            sec_pena.append("Pelas contas, a sua pena pode já ter terminado. A Defensoria vai analisar e, se for o caso, pedir ao juiz o fim da pena.")
        for c in m.get("crimes_det") or []:
            if str(c.get("extinto") or "").upper().startswith("S"):
                continue
            condenacoes.append({"crime": c.get("nome_crime") or c.get("dispositivo") or "Crime", "pena": c.get("pena") or "",
                                "proc": c.get("proc") or ""})

    # 2) próximos direitos
    if m:
        ped = pedidos or {}
        r0 = str(m.get("regime") or "").split(" (")[0].strip().lower()
        prox = PROXIMO_REGIME.get(r0)
        # falta grave: a contagem para a progressão recomeça (STJ, Súmula 534) e o SEEU refaz a data-base e a data. Vale a data do RSPE:
        # RSPE gerado depois da homologação já traz a data refeita; RSPE anterior a ela ainda não (sem data: falta o RSPE atualizado).
        # O livramento não é interrompido pela falta grave (Súmula 441): segue a data do RSPE.
        fa = str(m.get("falta") or "")
        dfa, ger = _data(fa) if fa.startswith("Sim") else None, _data(m.get("geracao"))
        def pedido_rspe(chave):
            """situação do último pedido registrado no RSPE: ("pendente"|"negado"|"", data)"""
            v = str(m.get(chave) or "").lower()
            return ("pendente" if v.startswith("pendente") else "negado" if v.startswith("negado") else ""), _data(v)
        if prox and not ped.get("prog"):
            sit, d, ap = _beneficio_data(m, "prog", "prog_sit")
            pr, dp = pedido_rspe("ped_prog")
            if pr == "pendente" and sit:
                sec_dir.append("Ir para o regime %s: já há pedido no processo%s, aguardando a decisão do juiz."
                               % (prox, " desde " + extenso(dp) if dp else ""))
            elif pr == "negado" and sit == "vencido":
                sec_dir.append("Ir para o regime %s: você cumpriu o tempo necessário em %s, mas o juiz negou o pedido%s. A Defensoria vai "
                               "analisar o caso." % (prox, _quando(d, ap), " em " + extenso(dp) if dp else ""))
            elif dfa and ger and ger < dfa and sit:
                sec_dir.append("Ir para o regime %s: por causa da falta grave, a data vai ser refeita no SEEU. A Defensoria vai pedir o relatório "
                               "atualizado e informar a nova data." % prox)
            elif sit == "futuro":
                sec_dir.append("Ir para o regime %s: a partir de %s%s. Para isso, é preciso ter bom comportamento."
                               % (prox, _quando(d, ap), " (data já refeita depois da falta grave)" if dfa else ""))
            elif sit == "vencido":
                sec_dir.append("Ir para o regime %s: você já cumpriu o tempo necessário em %s. A Defensoria vai analisar e, se for o caso, fazer o pedido ao juiz." % (prox, _quando(d, ap)))
            elif sit == "conferir":
                sec_dir.append("Ir para o regime %s: a Defensoria está conferindo a data." % prox)
        if "livramento" not in r0 and not ped.get("liv"):
            sit, d, ap = _beneficio_data(m, "liv", "liv_sit")
            lc = "Livramento condicional (terminar a pena em liberdade, cumprindo regras)"
            pr, dp = pedido_rspe("ped_liv")
            if pr == "pendente" and sit:
                sec_dir.append("%s: já há pedido no processo%s, aguardando a decisão do juiz." % (lc, " desde " + extenso(dp) if dp else ""))
            elif pr == "negado" and sit == "vencido":
                sec_dir.append("%s: você cumpriu o tempo necessário em %s, mas o juiz negou o pedido%s. A Defensoria vai analisar o caso."
                               % (lc, _quando(d, ap), " em " + extenso(dp) if dp else ""))
            elif sit == "futuro" and dfa and (d - dfa).days < 365:
                # o livramento exige também 12 meses sem falta grave (CP, art. 83, III, "b"); a data da falta em si não está no RSPE
                sec_dir.append("%s: o tempo necessário se completa em %s. A lei também exige 12 meses sem falta grave. A Defensoria vai "
                               "conferir essa data." % (lc, _quando(d, ap)))
            elif sit == "futuro":
                sec_dir.append("%s: a partir de %s." % (lc, _quando(d, ap)))
            elif sit == "vencido":
                sec_dir.append("%s: você já cumpriu o tempo necessário em %s. A Defensoria vai analisar e, se for o caso, fazer o pedido ao juiz." % (lc, _quando(d, ap)))
            elif sit == "conferir":
                sec_dir.append("%s: a Defensoria está conferindo a data." % lc)
        ind_ped = any(k == "ind" or k.startswith("ind_") for k in ped)
        if not ind_ped:
            for ano, ki, kc in (("2025", "i25", "c25"), ("2024", "i24", "c24"), ("2022", "i22", None)):
                vi, vc = str(m.get(ki) or ""), str(m.get(kc) or "") if kc else ""
                if vi == "Sim":
                    sec_dir.append("Indulto de %s (perdão da pena dado pelo Presidente da República): você pode ter direito. A Defensoria vai analisar." % ano)
                elif vc == "Sim":
                    sec_dir.append("Comutação de %s (redução da pena dada pelo Presidente da República): você pode ter direito. A Defensoria vai analisar." % ano)
                elif vi == "Verificar" or vc == "Verificar":
                    sec_dir.append("Indulto ou comutação de %s: a Defensoria vai verificar se você tem direito." % ano)
                else:
                    continue
                break  # só o decreto mais recente que alcança
        if not sec_dir:
            sec_dir.append("Neste momento, não há data próxima de novo direito no seu processo.")

    # 3) o que a Defensoria vai fazer: quem atendeu marca na janela as providências que serão adotadas e escreve outras; as frases
    # saem no PDF (nada vem marcado: é a decisão de quem atendeu)
    da = data_atend or hoje
    provs = [{"id": i_, "rot": r_, "frase": f_, "marcado": False} for i_, r_, f_ in PROVIDENCIAS]
    outro = ""

    # 4) atenção
    if m:
        fa = str(m.get("falta") or "")
        if fa.startswith("Sim"):
            dfa = _data(fa)
            sec_aten.append("Consta falta grave confirmada pelo juiz%s. A falta grave pode atrasar a mudança de regime e outros direitos."
                            % (" em " + extenso(dfa) if dfa else ""))
        elif fa.startswith("A apurar"):
            sec_aten.append("Há uma falta disciplinar em apuração. Se for confirmada, pode atrasar os seus direitos.")
    sec_aten.append("Trabalhar e estudar diminui a pena. Manter o bom comportamento ajuda a conseguir os seus direitos.")

    secoes = [{"id": "pena", "titulo": "Sua pena hoje", "itens": sec_pena}]
    if m:
        secoes.append({"id": "direitos", "titulo": "Seus próximos direitos", "itens": sec_dir})
    secoes += [{"id": "prov", "titulo": "O que a Defensoria vai fazer", "itens": []},
               {"id": "atencao", "titulo": "Fique atento", "itens": sec_aten}]
    ger = (m or {}).get("geracao") or ""
    rodape = ("As datas deste resumo vêm do SEEU (relatório de %s). Elas podem mudar com decisões do juiz, faltas ou dias de trabalho e estudo." % ger
              if m else "")
    return {"nome": nome, "proc": (m or {}).get("proc") or "", "hoje": hoje.strftime("%d/%m/%Y"), "barra": barra,
            "quadro": quadro, "condenacoes": condenacoes[:8], "vara": (m or {}).get("vara") or "",
            "secoes": secoes, "rodape": rodape, "data_atend": da.strftime("%d/%m/%Y"), "providencias": provs, "outro": outro}

