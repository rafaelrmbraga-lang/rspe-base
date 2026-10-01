"""Leitura da "Linha do Tempo Detalhada" do SEEU (PDF gerado a partir da aba "Informações adicionais").

O PDF traz, para cada ocorrência (condenação, prisão, remição, interrupção/fuga, decreto, unificação...), a coluna
"Condenação Detalhada": por ação penal e por crime, a pena, a pena cumprida e o restante naquela data. É a imputação
que o próprio SEEU fazia do tempo cumprido entre as condenações - o dado que o RSPE não mostra e que decide o saldo
de cada condenação na fuga (CP, art. 113).

Devolve {"tipo": "linha_seeu", "processo_execucao", "gerado_em", "ocorrencias": [{"rotulo", "data", "motivo",
"acoes": {"0069596-20.2007.8.12.0001": [{"pena": dias, "cumprida": dias, "restante": dias}, ...]}}]}."""
import re

import rspe_scraper as rs

RE_CNJ = r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}"
RE_VAL = r"((?:\d+a\d+m\d+d[ \t]*)+)"
# início de ocorrência: rótulo (primeira linha dele), data e "Total Pena Imposta:"
RE_OCOR = re.compile(r"^(?P<rot>[A-ZÀ-Ú][^\n]{0,40}?) (?P<data>\d{2}/\d{2}/\d{4}) Total Pena Imposta:", re.M)
RE_TOK = re.compile(r"Ação Penal:\s*(?P<ap>%s)|(?<!Pena )(?<!Total )Pena Total:\s*%s|(?<!Pena )Cumprida:\s*%s|(?<!Pena )Restante:\s*%s"
                    % (RE_CNJ, RE_VAL.replace("(", "(?P<pena>", 1), RE_VAL.replace("(", "(?P<cump>", 1), RE_VAL.replace("(", "(?P<rest>", 1)))
ROTULOS = {"Início da": "Interrupção", "Prisão em": "Prisão", "Data de Delito": "Data do delito", "Data Base de": "Data-base",
           "Decreto em 25 de": "Decreto", "Comutação de": "Comutação", "Progressão de": "Progressão", "Término de Pena": "Término da pena"}


def e_linha(txt):
    return "LINHA DO TEMPO DETALHADA" in (txt or "")[:600].upper()


def _vals(t):
    return [rs.pena_para_dias(x) or 0 for x in re.findall(r"\d+a\d+m\d+d", t or "")]


def ler_texto(txt):
    proc = (re.search(RE_CNJ, txt[:300]) or [""])[0]
    ger = re.search(r"GERADO EM (\d{2}/\d{2}/\d{4})", txt[:600])
    marcas = list(RE_OCOR.finditer(txt))
    ocs = []
    for i, m in enumerate(marcas):
        seg = txt[m.start(): marcas[i + 1].start() if i + 1 < len(marcas) else len(txt)]
        rot = m.group("rot").strip()
        rot = next((v for k, v in ROTULOS.items() if rot.startswith(k)), rot)
        mot = re.search(r"Motivo da Interrupção:\s*([A-ZÀ-Ú][A-ZÀ-Ú ]+?)(?:\s+Ação Penal:|\n)", seg)
        acoes, cur, ult = {}, None, None
        for t in RE_TOK.finditer(seg):
            if t.group("ap"):
                cur = t.group("ap")
                acoes.setdefault(cur, [])
                ult = None
            elif cur is None:
                continue
            elif t.group("pena") is not None:
                ult = [{"pena": v, "cumprida": None, "restante": None} for v in _vals(t.group("pena"))]
                acoes[cur] = ult
            elif ult is not None and t.group("cump") is not None:
                for e, v in zip(ult, _vals(t.group("cump"))):
                    e["cumprida"] = v
            elif ult is not None and t.group("rest") is not None:
                for e, v in zip(ult, _vals(t.group("rest"))):
                    e["restante"] = v
        acoes = {k: v for k, v in acoes.items() if v and all(e["cumprida"] is not None and e["restante"] is not None for e in v)}
        ocs.append({"rotulo": rot, "data": m.group("data"), "motivo": mot.group(1).strip() if mot else "", "acoes": acoes})
    return {"tipo": "linha_seeu", "processo_execucao": proc, "gerado_em": ger.group(1) if ger else "", "ocorrencias": ocs}


def extrair(caminho):
    import pdfplumber
    with pdfplumber.open(caminho) as pdf:
        txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if not e_linha(txt):
        raise ValueError("não é a Linha do Tempo Detalhada do SEEU")
    out = ler_texto(txt)
    if not out["processo_execucao"]:
        raise ValueError("Linha do Tempo Detalhada sem o número da execução")
    return out


def saldo_na(linha, data, proc, pena, idx=0):
    """Situação do crime (ação penal + pena) na ocorrência da data (a interrupção do dia, se houver; senão a última antes dela):
    {"pena", "cumprida", "restante", "ocorrencia", "data"} ou None. Com dois crimes de mesma pena na mesma ação penal, o primeiro."""
    if not linha:
        return None
    d = rs.to_date(data) if isinstance(data, str) else data
    chave = rs.chave_processo(proc)
    cands = []
    for o in linha.get("ocorrencias") or []:
        do = rs.to_date(o["data"])
        if not do or do > d:
            continue
        ac = next((v for k, v in o["acoes"].items() if rs.chave_processo(k) == chave), None)
        if ac:
            cands.append((do, o["rotulo"] == "Interrupção" and do == d, o, ac))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    do, _i, o, ac = cands[-1]
    e = next((x for x in ac if x["pena"] == pena), None)
    if e is None and 0 <= idx < len(ac):
        e = ac[idx]  # pena alterada depois (unificação, comutação): a posição do crime na ação penal
    if e is None:
        return None
    return dict(e, ocorrencia=o["rotulo"] + ((" (%s)" % o["motivo"].lower()) if o.get("motivo") else ""), data=o["data"])
