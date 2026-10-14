"""Resumo para o assistido: a situação da pena, os próximos direitos e o resumo do atendimento, em linguagem simples
(Pacto Nacional do Judiciário pela Linguagem Simples, CNJ): frases curtas, ordem direta, voz ativa, "você", sem termos
técnicos sem explicação e o mais importante primeiro.

Só entra o que o APTO já calculou. Data duvidosa (aviso "ver Auditoria", "verificar") sai como "a Defensoria está
conferindo", nunca como data. O texto é uma proposta: a janela do APTO deixa editar e tirar cada frase antes do PDF."""
import re
from datetime import date

import rspe_atendimentos as ratd

MESES = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()

PROXIMO_REGIME = {"fechado": "semiaberto", "semiaberto": "aberto"}

# providências do atendimento: (id, rótulo na janela, frase no resumo)
PROVIDENCIAS = [
    ("explicou", "Explicação da pena e das datas", "Explicamos como está a sua pena e as datas dos seus direitos."),
    ("ped_prog", "Pedido de progressão de regime", "Pedimos ao juiz a mudança de regime."),
    ("ped_liv", "Pedido de livramento condicional", "Pedimos ao juiz o livramento condicional."),
    ("ped_ind", "Pedido de indulto", "Pedimos ao juiz o indulto (perdão da pena)."),
    ("ped_com", "Pedido de comutação", "Pedimos ao juiz a comutação (redução da pena)."),
    ("ped_rem", "Pedido de remição", "Pedimos ao juiz o desconto dos dias de trabalho e estudo na pena (remição)."),
    ("ped_ext", "Pedido de extinção da pena", "Pedimos ao juiz o fim da pena (extinção)."),
    ("ped_presc", "Pedido de prescrição", "Pedimos ao juiz o reconhecimento da prescrição (o fim do prazo para cumprir a pena)."),
    ("ped_st", "Pedido de saída temporária", "Pedimos ao juiz a saída temporária."),
    ("ofi_atest", "Ofício: atestados de trabalho e estudo", "Pedimos à unidade prisional os atestados de trabalho e estudo."),
    ("falta", "Orientação sobre falta disciplinar", "Orientamos você sobre a falta disciplinar."),
    ("analise", "Processo em análise", "Vamos analisar o seu processo e, se for o caso, fazer o pedido ao juiz."),
    ("aguarda", "Pedido aguardando decisão", "Já existe pedido no seu processo. Agora é preciso esperar a decisão do juiz."),
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


def montar(m, pedidos, atendimentos, hoje=None, nome="", data_atend=None):
    """m: modelo do assistido (None se ainda não há RSPE na base); pedidos: {aba: {data, tipo, obs}} do processo;
    atendimentos: [{data ISO, tipo, texto, fonte}] da pessoa; data_atend: o atendimento do resumo (hoje, se vazio).
    -> dados do resumo (editáveis na janela do APTO)."""
    hoje = hoje or date.today()
    nome = (m or {}).get("nome") or nome
    sec_pena, sec_dir, sec_aten = [], [], []
    barra = None

    # 1) como está a pena
    if not m:
        sec_pena.append("A Defensoria ainda não tem o relatório atualizado da sua pena. Por isso, este resumo não traz as datas dos seus direitos.")
    else:
        reg = str(m.get("regime") or "").strip()
        r0 = reg.split(" (")[0].strip().lower()
        if "livramento" in r0:
            sec_pena.append("Você está em livramento condicional: cumpre o resto da pena em liberdade, seguindo as regras do juiz.")
        elif r0 in ("fechado", "semiaberto", "aberto"):
            if "não iniciado" in reg.lower():
                sec_pena.append("Seu regime é o %s. O cumprimento ainda não começou." % r0)
            else:
                sec_pena.append("Você está no regime %s." % r0)
        tot, cum, rem = m.get("pena_total"), m.get("pena_cumprida"), m.get("pena_rem")
        if _dias(tot):
            sec_pena.append("Sua pena total é de %s." % tot)
        ext = str(m.get("ext_sit") or "")
        if _dias(cum) and _dias(rem) is not None:
            if _dias(rem) and not ext.startswith("Extinção cabível"):
                sec_pena.append("Você já cumpriu %s. %s %s." % (cum, "Falta" if re.match(r"^1 \w+$", str(rem).strip()) else "Faltam", rem))
            else:
                sec_pena.append("Você já cumpriu %s." % cum)
            t_ = (_dias(cum) or 0) + (_dias(rem) or 0)
            if t_:
                barra = {"pct": round(100.0 * (_dias(cum) or 0) / t_), "cumprida": cum, "falta": rem}
        mr = re.match(r"\s*(\d+)\s*dias?", str(m.get("remidos") or ""))
        if mr and int(mr.group(1)) > 0:
            sec_pena.append("O trabalho e o estudo já tiraram %s dias da sua pena. Isso se chama remição." % mr.group(1))
        if ext.startswith("Extinção cabível"):
            if not (pedidos or {}).get("ext"):
                sec_pena.append("Pelas contas, a sua pena pode já ter terminado. A Defensoria vai analisar e, se for o caso, pedir ao juiz o fim da pena.")
        else:
            dt = _data(m.get("termino"))
            if dt and dt > hoje and not ext.startswith(("Pena interrompida", "Pena suspensa", "Pena extinta")):
                sec_pena.append("Pela conta de hoje, a sua pena termina em %s." % _quando(dt, str(m.get("termino")).strip().endswith("*")))

    # 2) próximos direitos
    if m:
        ped = pedidos or {}
        r0 = str(m.get("regime") or "").split(" (")[0].strip().lower()
        prox = PROXIMO_REGIME.get(r0)
        # falta grave homologada depois da data-base do RSPE: a contagem para a progressão recomeça (STJ, Súmula 534); o RSPE ainda
        # não traz a data nova, então não sai data (o livramento não é interrompido: Súmula 441)
        fa = str(m.get("falta") or "")
        dfa, dbase = _data(fa) if fa.startswith("Sim") else None, _data(m.get("dbase"))
        if prox and not ped.get("prog"):
            sit, d, ap = _beneficio_data(m, "prog", "prog_sit")
            if dfa and dbase and dfa > dbase and sit in ("futuro", "vencido", "conferir"):
                sec_dir.append("Ir para o regime %s: por causa da falta grave, a contagem do tempo recomeçou. A Defensoria vai acompanhar a nova data." % prox)
            elif sit == "futuro":
                sec_dir.append("Ir para o regime %s: a partir de %s. Para isso, é preciso ter bom comportamento." % (prox, _quando(d, ap)))
            elif sit == "vencido":
                sec_dir.append("Ir para o regime %s: você já cumpriu o tempo necessário em %s. A Defensoria vai analisar e, se for o caso, fazer o pedido ao juiz." % (prox, _quando(d, ap)))
            elif sit == "conferir":
                sec_dir.append("Ir para o regime %s: a Defensoria está conferindo a data." % prox)
        if "livramento" not in r0 and not ped.get("liv"):
            sit, d, ap = _beneficio_data(m, "liv", "liv_sit")
            lc = "Livramento condicional (terminar a pena em liberdade, cumprindo regras)"
            if sit == "futuro":
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

    # 3) resumo do atendimento: quem atendeu marca na janela as providências feitas (as do APTO com a data do atendimento já vêm
    # marcadas) e escreve o que mais houve; as frases saem no PDF
    da = data_atend or hoje
    marcadas = {"explicou"}
    for k, p in (pedidos or {}).items():
        if _data(p.get("data")) != da:
            continue
        tp = p.get("tipo") or "pedido"
        if k == "fd" and tp == "oficio":
            marcadas.add("ofi_atest")
        elif tp == "pedido":
            marcadas.add({"prog": "ped_prog", "liv": "ped_liv", "fd": "ped_rem", "ext": "ped_ext", "presc": "ped_presc", "st": "ped_st"}.get(k)
                         or ("ped_ind" if k == "ind" or k.startswith("ind_") else ""))
    provs = [{"id": i_, "rot": r_, "frase": f_, "marcado": i_ in marcadas} for i_, r_, f_ in PROVIDENCIAS]
    outro = next((a.get("texto") or "" for a in atendimentos or [] if a.get("fonte") == "apto" and _data(a.get("data")) == da), "")

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

    secoes = [{"id": "pena", "titulo": "Como está a sua pena", "itens": sec_pena}]
    if m:
        secoes.append({"id": "direitos", "titulo": "Seus próximos direitos", "itens": sec_dir})
    secoes += [{"id": "atend", "titulo": "Resumo do atendimento", "itens": []},
               {"id": "atencao", "titulo": "Fique atento", "itens": sec_aten}]
    ger = (m or {}).get("geracao") or ""
    rodape = ("As datas deste resumo vêm do SEEU (relatório de %s). Elas podem mudar com decisões do juiz, faltas ou dias de trabalho e estudo." % ger
              if m else "")
    return {"nome": nome, "proc": (m or {}).get("proc") or "", "hoje": hoje.strftime("%d/%m/%Y"), "barra": barra,
            "secoes": secoes, "rodape": rodape, "data_atend": da.strftime("%d/%m/%Y"), "providencias": provs, "outro": outro}


def atendimentos_da_pessoa(nome, registros, manuais):
    """atendimentos do SAP e registrados no APTO da pessoa (pelo nome, sem ligar nome só parecido), do mais recente ao mais antigo."""
    nomes = {r["nome"] for r in registros if r.get("nome")} | {x["nome"] for x in manuais if x.get("nome")}
    k, _c = ratd._Indice(nomes).achar(nome, parecido=False)
    if not k:
        return []
    alvo = ratd.norm(k)
    out = [{"data": r["data"], "tipo": r.get("tipo") or "", "texto": "", "fonte": "sap"} for r in registros if ratd.norm(r.get("nome")) == alvo]
    out += [{"data": x["data"], "tipo": "", "texto": x.get("obs") or "", "fonte": "apto", "registrado_em": x.get("registrado_em")}
            for x in manuais if ratd.norm(x.get("nome")) == alvo]
    # o mesmo dia no SAP e no APTO: fica o do APTO (traz o que foi feito)
    dias_apto = {x["data"] for x in out if x["fonte"] == "apto"}
    out = [x for x in out if x["fonte"] == "apto" or x["data"] not in dias_apto]
    out.sort(key=lambda x: (x["data"], x.get("registrado_em") or ""), reverse=True)
    return out
