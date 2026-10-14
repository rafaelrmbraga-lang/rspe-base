"""Atendimentos por unidade: "Listagem Internos Ativos" do SIAPEN (quem está hoje na unidade) + "Relatório de Atendimento" do
SAP da Defensoria (atendimentos do período). Cada interno da listagem recebe a data do último atendimento; quem está no
relatório e não está na listagem não entra (já saiu da unidade). A listagem também mostra quem ainda não tem RSPE na base.

Cores: vermelho = sem atendimento no período do relatório; amarelo = último atendimento há mais de 90 dias; verde = até 90
dias. Nome só parecido (grafia diferente entre SIAPEN e SAP) leva a cor da data achada, com o aviso para conferir."""
import difflib
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

PRAZO_DIAS = 90
PREP = {"DE", "DA", "DO", "DOS", "DAS", "E", "D"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\([^)]*\)", " ", s).replace("'", " ").replace("`", " ")  # SANT'ANA = SANT ANA (como o SIAPEN imprime)
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())


def assinatura(s):
    """nome sem preposições: "COSTA E SILVA" = "COSTA SILVA"."""
    return " ".join(t for t in norm(s).split() if t not in PREP)


def _d(s):
    m = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", str(s or ""))
    if not m:
        return None
    a = int(m.group(3))
    try:
        return date(a + 2000 if a < 100 else a, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def tipo_pdf(texto_1a_pagina):
    t = norm(texto_1a_pagina)
    if "LISTAGEM INTERNOS ATIVOS" in t:
        return "listagem"
    if "RELATORIO DE ATENDIMENTO" in t and "ASSISTIDO" in t:
        return "relatorio"
    return ""


def tipo_pelo_nome(arquivo):
    n = norm(arquivo)
    if re.search(r"LISTAGEM ?DE ?INTERNOS ?ATIVOS", n):
        return "listagem"
    if re.search(r"RELATORIO ?ATENDIMENTO", n):
        return "relatorio"
    return ""


# ---- leitura: texto por posição (a 2ª linha de um nome comprido sai impressa por cima da 1ª, com a altura um pouco diferente) ----
def _celula(page, x0, x1, top, tol=3.0):
    """linhas de texto da célula [x0, x1) na altura da linha `top`: a linha principal primeiro, depois as de cima/baixo."""
    g = defaultdict(list)
    for c in page.chars:
        if x0 <= c["x0"] < x1 and abs(c["top"] - top) < tol:
            g[round(c["top"], 2)].append(c)
    partes = []
    for k in sorted(g, key=lambda k: (abs(k - top) > 0.06, k)):
        s, ult = "", None
        for c in sorted(g[k], key=lambda c: c["x0"]):
            if ult is not None and c["x0"] - ult > 1.5:
                s += " "
            s += c["text"]
            ult = c["x1"]
        if s.strip():
            partes.append(s.strip())
    return partes


def ler_listagem(pdf):
    """pdfplumber.PDF da "Listagem Internos Ativos" -> {unidade, emitida, internos: [{n, nome, local, entrada, procedencia}]}."""
    internos = []
    linhas1 = (pdf.pages[0].extract_text() or "").splitlines()
    unidade = ""
    for i, l in enumerate(linhas1):
        if "AGEPEN" in norm(l) or "ADMINISTRACAO DO SISTEMA PENITENCIARIO" in norm(l):
            unidade = linhas1[i + 1].strip() if i + 1 < len(linhas1) else ""
            break
    emitida = ""
    m = re.search(r"Impresso em (\d{2}/\d{2}/\d{4})", "\n".join((p.extract_text() or "") for p in pdf.pages[-1:]))
    if m:
        emitida = m.group(1)
    for p in pdf.pages:
        ws = p.extract_words()
        hdr = {w["text"]: w["x0"] for w in ws if w["text"] in ("NOME", "LOCALIZAÇÃO", "ENTRADA", "PROCEDÊNCIA")}
        xn, xl = hdr.get("NOME", 89) - 4, hdr.get("LOCALIZAÇÃO", 301) - 3
        for w in ws:
            if w["x0"] < xn and re.fullmatch(r"\d{1,5}", w["text"]):
                t = w["top"]
                nome = " ".join(" ".join(_celula(p, xn, xl, t)).split())
                if not nome:
                    continue
                # localização, entrada e procedência não têm coluna fixa: a linha principal é "D - UNICO - 102 02/10/2026 EPJFC"
                resto = (_celula(p, xl, p.width, t) or [""])[0]
                m = re.search(r"\d{2}/\d{2}/\d{4}", resto)
                internos.append({"n": int(w["text"]), "nome": nome, "local": (resto[:m.start()] if m else resto).strip(),
                                 "entrada": m.group(0) if m else "", "procedencia": resto[m.end():].strip() if m else ""})
    internos.sort(key=lambda x: x["n"])
    return {"unidade": unidade, "emitida": emitida, "internos": internos}


def _relatorio_paginas(args):
    """registros de atendimento das páginas [i0, i1) do relatório (cada atendimento tem o seu cabeçalho: não passa de página)."""
    import pdfplumber
    caminho, i0, i1 = args
    regs = []
    with pdfplumber.open(caminho) as pdf:
        for p in pdf.pages[i0:i1]:
            ws = p.extract_words()
            # cabeçalho de cada atendimento: "UNIDADE" na mesma linha de "ASSISTIDO" (um estabelecimento chamado "UNIDADE ..." não conta)
            t_ass = [w["top"] for w in ws if w["text"] == "ASSISTIDO"]
            heads = sorted(w["top"] for w in ws if w["text"] == "UNIDADE" and any(abs(w["top"] - t) < 1.5 for t in t_ass))
            if not heads:
                continue
            hx = {w["text"]: w["x0"] for w in ws if w["text"] in ("ESTABELECIMENTO", "DEFENSOR(A)", "ASSISTIDO", "STATUS", "DATA")}
            xe, xd = hx.get("ESTABELECIMENTO", 198) - 20, hx.get("DEFENSOR(A)", 376) - 58
            xa, xs, xt = hx.get("ASSISTIDO", 548) - 60, hx.get("STATUS", 664) - 8, hx.get("DATA", 779) - 24
            rod = min([w["top"] for w in ws if w["text"] in ("Página", "TOTAL")] + [p.height])
            for i, h in enumerate(heads):
                fim = min(heads[i + 1] - 6 if i + 1 < len(heads) else p.height, rod - 1)
                faixa = [w for w in ws if h + 3 < w["top"] < fim]
                dt = [w for w in faixa if w["x0"] >= xt and re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", w["text"])]
                if not dt:
                    continue

                def col(a, b):
                    return " ".join(w["text"] for w in sorted((w for w in faixa if a <= w["x0"] < b), key=lambda w: (round(w["top"]), w["x0"])))
                nome, d = col(xa, xs), _d(dt[0]["text"])
                if nome and d:
                    hora = next((w["text"] for w in faixa if w["x0"] >= xt and re.fullmatch(r"\d{2}:\d{2}", w["text"])), "")
                    regs.append((nome, d.isoformat(), hora, col(xs, xt), col(xd, xa), col(xe, xd)))
    return regs


def ler_relatorio(caminho, processos=1):
    """caminho do "Relatório de Atendimento" do SAP -> {periodo, gerado, n, pessoas: {nome: resumo do último atendimento}}.
    Relatório grande (centenas de páginas) é lido em paralelo, por blocos de páginas."""
    import pdfplumber
    with pdfplumber.open(caminho) as pdf:
        t1 = pdf.pages[0].extract_text() or ""
        total = len(pdf.pages)
    per = re.search(r"PER[IÍ]ODO:\s*(\d{2}/\d{2}/\d{4})\s*\S+\s*(\d{2}/\d{2}/\d{4})", t1)
    ger = re.search(r"Gerado em\s*:\s*(\d{2}/\d{2}/\d{4})", t1)
    passo = 30
    blocos = [(caminho, i, min(i + passo, total)) for i in range(0, total, passo)]
    regs = []
    if processos > 1 and len(blocos) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=processos) as ex:
            for r in ex.map(_relatorio_paginas, blocos):
                regs += r
    else:
        for b in blocos:
            regs += _relatorio_paginas(b)
    pessoas = {}
    for nome, d, hora, tipo, defensor, estab in regs:
        k = norm(nome)
        r = pessoas.get(k)
        if not r:
            r = pessoas[k] = {"nome": nome, "n": 0, "ultimo": "", "hora": "", "tipo": "", "defensor": "", "estab": ""}
        r["n"] += 1
        if not r["ultimo"] or (d, hora) >= (r["ultimo"], r["hora"]):
            r.update(ultimo=d, hora=hora, tipo=tipo, defensor=defensor, estab=estab)
    return {"periodo": [per.group(1), per.group(2)] if per else [], "gerado": ger.group(1) if ger else "", "n": len(regs), "pessoas": pessoas}


def ler_listagem_arquivo(caminho):
    import pdfplumber
    with pdfplumber.open(caminho) as pdf:
        return ler_listagem(pdf)


def tipo_do_arquivo(caminho):
    import pdfplumber
    try:
        with pdfplumber.open(caminho) as pdf:
            return tipo_pdf(pdf.pages[0].extract_text() or "") if pdf.pages else ""
    except Exception:
        return ""


# ---- cruzamento ----
class _Indice:
    """procura um nome: igual; igual sem preposições/apóstrofo; nome cortado (a listagem do SIAPEN corta nomes compridos);
    parecido (grafia diferente, >= 92%), este marcado para conferir."""

    def __init__(self, nomes):
        self.exato, self.sig = {}, defaultdict(list)
        for k in nomes:
            self.exato[norm(k)] = k
            self.sig[assinatura(k)].append(k)
        self.lista = list(self.sig)

    def achar(self, nome, parecido=True):
        n, s = norm(nome), assinatura(nome)
        if n in self.exato:
            return self.exato[n], ""
        if len(self.sig.get(s, [])) == 1:
            return self.sig[s][0], ""
        if len(s.split()) >= 3:
            pref = [k for k in self.lista if k.startswith(s + " ") or s.startswith(k + " ")]
            if len(pref) == 1 and len(self.sig[pref[0]]) == 1:
                return self.sig[pref[0]][0], "nome cortado"
        if not parecido:
            return None, ""
        par = difflib.get_close_matches(s, self.lista, n=2, cutoff=0.92)
        if len(par) == 1 and len(self.sig[par[0]]) == 1:
            return self.sig[par[0]][0], "parecido"
        return None, ""


def cruzar(listagem, relatorio, registros, fichas_nomes, hoje=None):
    """Uma linha por interno da listagem, em ordem de prioridade, com o último atendimento, a cor e os documentos na base
    (RSPE pelo nome; ficha pelo nome ou pelo RSPE)."""
    hoje = hoje or date.today()
    pessoas = (relatorio or {}).get("pessoas") or {}
    ind_rel = _Indice(pessoas.keys())
    ind_base = _Indice([r["nome"] for r in registros if r.get("nome")])
    por_nome = defaultdict(list)
    for r in registros:
        por_nome[norm(r.get("nome"))].append(r)
    fichas = {norm(f) for f in fichas_nomes or []}
    ind_ficha = _Indice(fichas)
    repetidos = defaultdict(int)
    for it in (listagem or {}).get("internos") or []:
        repetidos[norm(it["nome"])] += 1
    out = []
    for it in (listagem or {}).get("internos") or []:
        x = {"n": it["n"], "nome": it["nome"], "local": it.get("local", ""), "entrada": it.get("entrada", ""),
             "homonimo": repetidos[norm(it["nome"])] > 1, "ultimo": "", "dias": None, "tipo": "", "defensor": "", "n_atend": 0,
             "conf": "", "nome_sap": "", "obs": "", "proc": "", "id": "", "rspe": False, "ficha": False}
        k, como = ind_rel.achar(it["nome"])
        if k:
            r = pessoas[k]
            d = datetime.strptime(r["ultimo"], "%Y-%m-%d").date()
            if como == "parecido":
                # grafia só parecida não prova que é a mesma pessoa ("ALEXANDRO" x "LEANDRO"): fica sem atendimento, com o aviso
                x.update(conf="parecido", nome_sap=r["nome"], obs="nome parecido no SAP: %s, atendido em %s - confira" % (r["nome"], d.strftime("%d/%m/%Y")))
            else:
                x.update(ultimo=d.strftime("%d/%m/%Y"), dias=(hoje - d).days, tipo=r.get("tipo", ""), defensor=r.get("defensor", ""),
                         n_atend=r.get("n", 0), conf=como, nome_sap=r["nome"] if como else "")
        if not relatorio:
            x.update(cor="cinza", txt="Sem relatório do SAP")
        elif x["dias"] is None:
            x.update(cor="vermelho", txt="Sem atendimento no período")
        elif x["dias"] > PRAZO_DIAS:
            x.update(cor="amarelo", txt="Há mais de %d dias" % PRAZO_DIAS)
        else:
            x.update(cor="verde", txt="Dentro de %d dias" % PRAZO_DIAS)
        kb, _ = ind_base.achar(it["nome"], parecido=False)
        if kb and len(por_nome[norm(kb)]) >= 1:
            r0 = por_nome[norm(kb)][0]
            x.update(rspe=True, proc=r0.get("proc", ""), id=r0.get("id", ""), ficha=bool(r0.get("ficha_tem")))
        if not x["ficha"]:
            x["ficha"] = bool(ind_ficha.achar(it["nome"], parecido=False)[0])
        out.append(x)
    ordem = {"vermelho": 0, "amarelo": 1, "verde": 2, "cinza": 3}
    out.sort(key=lambda x: (ordem[x["cor"]], -(x["dias"] or 0), norm(x["nome"])))
    return out


def pendentes(listagem, registros):
    """internos da listagem sem RSPE na base (para a aba Geral e o aviso das demais abas)."""
    ind = _Indice([r["nome"] for r in registros if r.get("nome")])
    return [{"n": it["n"], "nome": it["nome"], "local": it.get("local", "")}
            for it in (listagem or {}).get("internos") or [] if not ind.achar(it["nome"], parecido=False)[0]]
