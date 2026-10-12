"""Vigilância de legislação: ao abrir, confere na API de Dados Abertos do Senado Federal (legislação federal) se saiu
(1) norma que altera as leis em que os cálculos do programa se apoiam depois da data da base jurídica, ou (2) decreto de
indulto/comutação que a base jurídica ainda não tem. Só informa: nenhuma regra de cálculo muda sem a revisão da base
jurídica. Sem internet, nada é mostrado. A consulta é guardada por um dia (cache) para não atrasar as aberturas seguintes.
Fonte: https://legis.senado.leg.br/dadosabertos/ (gratuita, sem cadastro)."""
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

API = "https://legis.senado.leg.br/dadosabertos/legislacao"
TIMEOUT = 25

# normas em que os cálculos se apoiam: (tipo na API, número, ano, nome curto)
NORMAS = [
    ("LEI", "7210", "1984", "a Lei de Execução Penal (Lei 7.210/1984)"),
    ("DEL", "2848", "1940", "o Código Penal (Decreto-Lei 2.848/1940)"),
    ("LEI", "8072", "1990", "a Lei dos Crimes Hediondos (Lei 8.072/1990)"),
    ("LEI", "11343", "2006", "a Lei de Drogas (Lei 11.343/2006)"),
    ("LEI", "10826", "2003", "o Estatuto do Desarmamento (Lei 10.826/2003)"),
    ("LEI", "12850", "2013", "a Lei das Organizações Criminosas (Lei 12.850/2013)"),
]
RE_INDULTO = re.compile(r"indulto|comuta", re.I)
RE_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": "APTO"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _data(txt):
    m = RE_DATA.search(txt or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _so_digitos(t):
    return re.sub(r"\D", "", t or "")


def data_base_juridica(versao):
    """'2026-10-08i' -> date(2026, 10, 8): data até a qual a base jurídica considera a legislação."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", versao or "")
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def alteracoes(tipo, numero, ano, depois_de, get=_get):
    """Normas posteriores que alteram/acrescentam/revogam dispositivos da norma, assinadas depois de 'depois_de':
    [{norma, data, dispositivos, efeito, cod}] (uma por norma posterior)."""
    lst = ET.fromstring(get("%s/lista?tipo=%s&numero=%s&ano=%s" % (API, tipo, numero, ano)))
    doc = lst.find(".//documento")
    if doc is None:
        return []
    det = ET.fromstring(get("%s/%s" % (API, doc.get("id"))))
    out = {}
    for disp in det.iter("disp"):
        nome = (disp.findtext("nomeDispositivo") or "").split(" [")[0].strip()
        for ref in disp.iter("ref"):
            norma = (ref.findtext("dispositivo") or "").strip()
            com = (ref.findtext("comentario") or "").strip()
            d = _data(norma)
            if not d or not depois_de or d <= depois_de or re.match(r"Regulament", com, re.I):
                continue
            x = out.setdefault(norma, {"norma": norma, "data": d.strftime("%d/%m/%Y"), "dispositivos": [], "efeito": set(),
                                       "cod": ref.findtext("codNormaPosterior") or ""})
            if nome and nome not in x["dispositivos"]:
                x["dispositivos"].append(nome)
            x["efeito"].add(com.split(" (")[0].lower())
    return [dict(x, efeito=", ".join(sorted(x["efeito"]))) for x in sorted(out.values(), key=lambda x: _data(x["data"]))]


def decretos_indulto(ano, get=_get):
    """Decretos do ano cuja ementa fala em indulto ou comutação: [{numero, norma, data, ementa, cod}]."""
    root = ET.fromstring(get("%s/lista?tipo=DEC&ano=%s" % (API, ano)))
    out = []
    for doc in root.iter("documento"):
        em = doc.findtext("ementa") or ""
        if RE_INDULTO.search(em):
            out.append({"numero": doc.findtext("numero") or "", "norma": doc.findtext("normaNome") or "",
                        "data": doc.findtext("dataassinatura") or "", "ementa": em.strip(), "cod": doc.get("id") or ""})
    return out


def verificar(versao_base, decretos_conhecidos, hoje=None, get=_get):
    """Avisos de legislação nova: {"itens": [...], "erro": "..."}. Cada item: {chave, tipo (lei|decreto), titulo, texto, link}.
    decretos_conhecidos: números (só dígitos) dos decretos que a base jurídica já tem."""
    hoje = hoje or date.today()
    d0 = data_base_juridica(versao_base)
    itens, erros = [], []
    for tipo, num, ano, nome in NORMAS:
        try:
            for a in alteracoes(tipo, num, ano, d0, get):
                disp = a["dispositivos"]
                itens.append({"chave": "lei|%s|%s" % (_so_digitos(a["norma"]), num), "tipo": "lei",
                              "titulo": "%s altera %s" % (a["norma"], nome),
                              "texto": "%s: %s%s." % (a["efeito"].capitalize() or "Alteração", "; ".join(disp[:6]), " e outros" if len(disp) > 6 else ""),
                              "link": "https://legis.senado.leg.br/norma/%s" % a["cod"] if a["cod"] else ""})
        except Exception as e:  # sem rede ou resposta inválida: segue para as demais
            erros.append("%s: %s" % (nome[2:], e))
    conhecidos = {_so_digitos(str(n).split("/")[0]) for n in decretos_conhecidos}  # "12.790/2025" -> "12790"
    for ano in sorted({hoje.year - 1, hoje.year}):
        try:
            for dc in decretos_indulto(ano, get):
                if _so_digitos(dc["numero"]) in conhecidos:
                    continue
                itens.append({"chave": "decreto|%s" % _so_digitos(dc["numero"]), "tipo": "decreto",
                              "titulo": "Novo decreto de indulto: %s" % dc["norma"],
                              "texto": "%s A aba Indulto e a linha do tempo ainda não o analisam." % dc["ementa"],
                              "link": "https://legis.senado.leg.br/norma/%s" % dc["cod"] if dc["cod"] else ""})
        except Exception as e:
            erros.append("decretos de %s: %s" % (ano, e))
    return {"itens": itens, "erro": "; ".join(erros), "consultado": datetime.now().strftime("%d/%m/%Y %H:%M")}


def com_cache(arquivo, versao_base, decretos_conhecidos, hoje=None, get=_get):
    """verificar() guardado por um dia em 'arquivo' (JSON); refaz se a base jurídica mudou. Sem rede e sem cache: sem itens."""
    hoje = hoje or date.today()
    try:
        c = json.load(open(arquivo, encoding="utf-8"))
        if c.get("dia") == hoje.isoformat() and c.get("versao") == versao_base and not c.get("erro"):
            return c
    except (OSError, ValueError):
        c = None
    r = verificar(versao_base, decretos_conhecidos, hoje, get)
    if r["erro"] and not r["itens"] and c and c.get("versao") == versao_base:
        return c  # sem internet hoje: vale a última consulta completa
    r.update(dia=hoje.isoformat(), versao=versao_base)
    try:
        os.makedirs(os.path.dirname(arquivo) or ".", exist_ok=True)
        json.dump(r, open(arquivo, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass
    return r
