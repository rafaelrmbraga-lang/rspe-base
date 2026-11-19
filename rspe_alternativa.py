"""Relatório de pena alternativa do SEEU (aba "Medidas Diversas da Prisão" > Gerar Relatório; actionType=emitirRelatorioPenaAlternativa):
leitura do texto das páginas (o mesmo extract_text do pdfplumber que o APTO usa; no navegador, rspe_pdf_paginas) e avaliação do
cumprimento das condições na data de referência.

Estrutura do relatório: cabeçalho (PODER JUDICIÁRIO, comarca, vara - repetido em cada página), "Número Único:", QUALIFICAÇÃO, o título
da medida (ex.: SUBSTITUIÇÃO DE PENA PRIVATIVA POR RESTRITIVA DE DIREITO) com "Pena Substituída:", "Data de Início:", "Data de
Término:" e "Status:"; depois CONDIÇÕES, cada uma com o nome (ex.: Prestação pecuniária, Prestação de serviços à comunidade), "Status:",
"Data Provável de Término:", os totais ("Total Previsto:", "Total Pago:", "Total A Pagar:") e a tabela "Cumprimentos:" (data prevista,
data do cumprimento efetivo, valor ou horas previstas, valor pago ou horas trabalhadas).

Avaliação (só o que a tabela mostra; nada é presumido):
- valor (prestação pecuniária e similares): parcelas vencidas sem pagamento e parcelas pagas a menor;
- horas (prestação de serviços à comunidade): horas devidas até a data (soma das previstas vencidas) x horas trabalhadas, e os meses
  vencidos sem registro;
- demais condições com cumprimentos (comparecimento etc.): vencidos sem registro;
- status do SEEU "VERIFICAR" ou "NÃO CUMPRIDA": a conferir.
"""
import re
from datetime import date

RE_DATA = r"\d{2}/\d{2}/\d{4}"
RE_LINHA = re.compile(r"^(%s)(?:\s+(%s))?\s+(R\$\s*)?([\d.,]+)(?:\s+([\d.,]+))?(?:\s+(Sim|Não|N[aã]o))?\s*$" % (RE_DATA, RE_DATA))
RE_SEM_VALOR = re.compile(r"^(%s)(?:\s+(%s))?(?:\s+(Sim|Não|N[aã]o))?\s*$" % (RE_DATA, RE_DATA))
CABECALHO = re.compile(r"^(PODER JUDICI[ÁA]RIO|TJ[A-Z]{2}\s*-\s*COMARCA|.*VARA DE EXECU|P[áa]gina \d+)", re.I)
TITULOS_MEDIDA = re.compile(r"^(SUBSTITUI[ÇC][ÃA]O DE PENA|SUSPENS[ÃA]O CONDICIONAL|CONDI[ÇC][ÕO]ES DE CUMPRIMENTO|LIBERA[ÇC][ÃA]O CONDICIONAL|"
                            r"PRIS[ÃA]O DOMICILIAR|LIVRAMENTO CONDICIONAL|TRANSA[ÇC][ÃA]O PENAL|ACORDO DE N[ÃA]O PERSECU)", re.I)
ROTULOS = ("Status", "Data Provável de Término", "Data de Término Efetiva", "Observação", "Valor", "Nº de Parcelas Previsto", "Destinatário",
           "Controle de Pagamentos", "Controle de Horas", "Total Previsto", "Total Pago", "Total A Pagar", "Cumprimentos", "Data Prevista",
           "Qtde de Horas", "Entidade Beneficiada", "Vaga Alocada", "Dias para Trabalho", "Horários para Trabalho", "Pena Substituída",
           "Incidente", "Data de Início", "Data de Término")
CURTO = {"prestação de serviços à comunidade": "PSC", "prestação pecuniária": "Prestação pecuniária",
         "limitação de fim de semana": "Limitação de fim de semana", "interdição temporária de direitos": "Interdição de direitos",
         "perda de bens e valores": "Perda de bens e valores"}


def _d(s):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _n(s):
    """Número do relatório: "3.306,00" / "330,60" (formato brasileiro) ou "303.60" / "28.00" (ponto decimal)."""
    s = (s or "").replace("R$", "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _campo(linha, rotulo):
    m = re.search(re.escape(rotulo) + r":\s*(.*?)(?=\s+[A-ZÁÉÍÓÚ][\wçãõáéíóúâêô ]{2,40}:|$)", linha)
    return m.group(1).strip() if m else None


def ler(paginas):
    """Texto das páginas do relatório -> {"processo", "medidas": [{"titulo", "pena", "inicio", "termino", "status", "condicoes": [...]}]}.
    Cada condição: {"nome", "status", "termino_previsto", "termino_efetivo", "unidade" ("R$" | "h" | ""), "total_previsto",
    "total_pago", "total_a_pagar", "cumprimentos": [{"prevista", "efetiva", "previsto", "realizado"}]}."""
    linhas = []
    for t in paginas or []:
        for ln in str(t or "").split("\n"):
            ln = ln.strip()
            if ln and not CABECALHO.match(ln):
                linhas.append(ln)
    out = {"processo": "", "medidas": []}
    med = cond = None
    na_tabela = False
    for i, ln in enumerate(linhas):
        m = re.match(r"N[úu]mero [ÚU]nico:\s*(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", ln)
        if m:
            out["processo"] = m.group(1)
            continue
        if TITULOS_MEDIDA.match(ln) and ln == ln.upper():
            med = {"titulo": ln.title().replace(" De ", " de ").replace(" Por ", " por ").replace(" Da ", " da "), "pena": "", "inicio": "",
                   "termino": "", "status": "", "condicoes": []}
            out["medidas"].append(med)
            cond, na_tabela = None, False
            continue
        if med is None:
            continue
        if ln.upper() == "CONDIÇÕES" or ln.upper() == "CONDICOES":
            cond, na_tabela = None, False
            continue
        nxt = linhas[i + 1] if i + 1 < len(linhas) else ""
        # nome de uma condição: linha sem rótulo seguida de "Status:"
        if ":" not in ln and nxt.startswith("Status:") and not RE_LINHA.match(ln):
            cond = {"nome": ln, "status": "", "termino_previsto": "", "termino_efetivo": "", "unidade": "", "total_previsto": None,
                    "total_pago": None, "total_a_pagar": None, "cumprimentos": []}
            med["condicoes"].append(cond)
            na_tabela = False
            continue
        if cond is None:
            for rot, k in (("Pena Substituída", "pena"), ("Data de Início", "inicio"), ("Data de Término", "termino"), ("Status", "status")):
                v = _campo(ln, rot)
                if v is not None and not med[k]:
                    med[k] = v
            continue
        if ln.startswith("Data Prevista de Cumprimento"):
            na_tabela = True
            if re.search(r"Horas", ln):
                cond["unidade"] = "h"
            elif re.search(r"Valor", ln):
                cond["unidade"] = "R$"
            continue
        if na_tabela:
            m = RE_LINHA.match(ln)
            if m:
                prev, efet, rs_, v1, v2 = m.group(1), m.group(2) or "", m.group(3), m.group(4), m.group(5)
                if rs_ and not cond["unidade"]:
                    cond["unidade"] = "R$"
                cond["cumprimentos"].append({"prevista": prev, "efetiva": efet, "previsto": _n(v1), "realizado": _n(v2) if v2 else None})
                continue
            m = RE_SEM_VALOR.match(ln)
            if m:
                cond["cumprimentos"].append({"prevista": m.group(1), "efetiva": m.group(2) or "", "previsto": None, "realizado": None})
                continue
            na_tabela = False
        st = _campo(ln, "Status")
        if st is not None and not cond["status"]:
            cond["status"] = st
        tp = re.search(r"Data Provável de Término:\s*(%s)?" % RE_DATA, ln)
        if tp:
            cond["termino_previsto"] = tp.group(1) or ""
            te = re.search(r"Data de Término Efetiva:\s*(%s)" % RE_DATA, ln)
            cond["termino_efetivo"] = te.group(1) if te else ""
        for rot, k in (("Total Previsto", "total_previsto"), ("Total Pago", "total_pago"), ("Total A Pagar", "total_a_pagar")):
            v = _campo(ln, rot)
            if v is not None:
                cond[k] = _n(v)
                if "R$" in v:
                    cond["unidade"] = "R$"
        if re.match(r"Qtde de Horas", ln) and not cond["unidade"]:
            cond["unidade"] = "h"
    return out


def _br(v, unidade):
    if v is None:
        return "—"
    if unidade == "R$":
        return "R$ " + ("{:,.2f}".format(v)).replace(",", "X").replace(".", ",").replace("X", ".")
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return s.replace(".", ",") + " h"


def avaliar(rel, hoje):
    """Cumprimento de cada condição na data -> lista de {"id", "medida", "nome", "curto", "status_seeu", "em_dia" (bool),
    "titulo", "valor", "conta" [linhas], "pct" (realizado/previsto total, 0-100 ou None)}."""
    res = []
    for mi, med in enumerate(rel.get("medidas") or []):
        for ci, c in enumerate(med.get("condicoes") or []):
            un = c.get("unidade") or ""
            nome = c.get("nome") or "Condição"
            curto = CURTO.get(nome.lower(), nome)
            cs = c.get("cumprimentos") or []
            venc = [x for x in cs if _d(x["prevista"]) and _d(x["prevista"]) <= hoje]
            st = (c.get("status") or "").upper()
            conta, pend = [], []
            tp, tr = c.get("total_previsto"), c.get("total_pago")
            pct = round(100 * tr / tp) if tp and tr is not None else None
            if un == "R$":
                sem = [x for x in venc if not x["efetiva"] and not x["realizado"]]
                menor = [x for x in venc if x["realizado"] is not None and x["previsto"] and x["realizado"] < x["previsto"] - 0.005]
                dif = sum(x["previsto"] - x["realizado"] for x in menor)
                deve = sum(x["previsto"] or 0 for x in sem) + dif
                if sem:
                    pend.append("%d %s vencida%s sem pagamento (%s)" % (len(sem), "parcela" if len(sem) == 1 else "parcelas", "" if len(sem) == 1 else "s",
                                                                       ", ".join(x["prevista"] for x in sem[:6]) + ("…" if len(sem) > 6 else "")))
                if menor:
                    pend.append("%d %s paga%s a menor (diferença de %s)" % (len(menor), "parcela" if len(menor) == 1 else "parcelas",
                                                                            "" if len(menor) == 1 else "s", _br(dif, un)))
                conta.append("Total previsto %s; pago %s; a pagar %s" % (_br(tp, un), _br(tr, un), _br(c.get("total_a_pagar"), un)))
                if deve > 0.005:
                    conta.append("Em atraso até %s: %s" % (date.strftime(hoje, "%d/%m/%Y"), _br(deve, un)))
                valor = ("%s em atraso" % _br(deve, un)) if deve > 0.005 else "em dia"
            elif un == "h":
                devidas = sum(x["previsto"] or 0 for x in venc)
                feitas = sum(x["realizado"] or 0 for x in cs)
                sem = [x for x in venc if not x["efetiva"] and not x["realizado"]]
                deficit = max(0.0, devidas - feitas)
                if deficit > 0.005:
                    pend.append("%s a menos que o devido até a data (%s devidas, %s cumpridas)" % (_br(deficit, un), _br(devidas, un), _br(feitas, un)))
                if sem:
                    pend.append("%s vencido%s sem registro de horas (%s)" % ("1 mês" if len(sem) == 1 else "%d meses" % len(sem), "" if len(sem) == 1 else "s",
                                                                           ", ".join(x["prevista"] for x in sem[:6]) + ("…" if len(sem) > 6 else "")))
                conta.append("Total previsto %s; cumprido %s; a cumprir %s" % (_br(tp, un), _br(tr, un), _br(c.get("total_a_pagar"), un)))
                valor = ("%s em atraso" % _br(deficit, un)) if deficit > 0.005 else ("%s cumpridas" % _br(feitas, un))
            else:
                sem = [x for x in venc if not x["efetiva"]]
                if sem:
                    pend.append("%d %s vencido%s sem registro (%s)" % (len(sem), "cumprimento" if len(sem) == 1 else "cumprimentos", "" if len(sem) == 1 else "s",
                                                                       ", ".join(x["prevista"] for x in sem[:6]) + ("…" if len(sem) > 6 else "")))
                valor = "%d de %d registrados" % (len(cs) - len([x for x in cs if not x["efetiva"]]), len(cs)) if cs else ""
            if c.get("termino_previsto"):
                conta.append("Término previsto: %s%s" % (c["termino_previsto"], (" (efetivo: %s)" % c["termino_efetivo"]) if c.get("termino_efetivo") else ""))
            if st in ("VERIFICAR", "NÃO CUMPRIDA", "NAO CUMPRIDA"):
                pend.append("status no SEEU: %s" % st.lower())
            em_dia = not pend and st not in ("SUSPENSA",)
            res.append({"id": "prd%d_%d" % (mi, ci), "medida": med.get("titulo") or "", "nome": nome, "curto": curto, "status_seeu": st,
                        "em_dia": em_dia, "titulo": "%s: %s" % (curto, valor) if valor else curto, "valor": valor,
                        "pendencias": pend, "conta": pend + conta, "pct": pct, "unidade": un})
    return res
