"""Atendimentos do NUSPEN: planilha do lote do SAP (extensão do navegador, "Salvar planilha") ligada aos assistidos da base.

A planilha (CSV com ";" e aspas, gravada em Downloads\\APTO\\SAP_processos_<data>.csv) traz, por cadastro do SAP: nome da lista,
nome no SAP, mãe, ID, data do último atendimento do NUSPEN e nº(s) do processo. Cada assistido da base é ligado pelo nº da
execução e, sem ele, pelo nome (só quando a planilha tem um único cadastro com esse nome).

Cores: vermelho = nunca atendido (não achado no SAP ou sem atendimento do NUSPEN); amarelo = último atendimento há mais de
90 dias; verde = até 90 dias; cinza = a planilha não informa (não está nela, homônimos ou não verificado)."""
import csv
import io
import re
import unicodedata
from datetime import date, datetime

PRAZO_DIAS = 90
RE_CNJ = re.compile(r"\b(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})\b")
NUNCA = re.compile(r"^(não encontrado no SAP|sem atendimento do NUSPEN no SAP|sem designações no SAP)$", re.I)


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"\([^)]*\)", " ", s).upper().split())


def _cab(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z0-9 ]", "", s).split())


def _cnjs(texto):
    return ["%s-%s.%s.%s.%s.%s" % m.groups() for m in RE_CNJ.finditer(str(texto or ""))]


def _data(s):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def ler_planilha(conteudo):
    """CSV (texto ou bytes) -> lista de cadastros: {lista, nome_sap, mae, sap_id, ultimo (date|None), nunca, processos, situacao}."""
    if isinstance(conteudo, bytes):
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                conteudo = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    texto = str(conteudo).lstrip("﻿")
    primeira = texto.split("\n", 1)[0]
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    linhas = list(csv.reader(io.StringIO(texto), delimiter=sep))
    if not linhas:
        return []
    cab = [_cab(c) for c in linhas[0]]

    def col(*nomes):
        for n in nomes:
            if n in cab:
                return cab.index(n)
        return None
    c_lista = col("NOME LISTA", "NOME")
    c_sap, c_mae, c_id = col("NOME NO SAP"), col("MAE"), col("ID SAP")
    c_ult = col("ULTIMO ATENDIMENTO NUSPEN")
    c_data = col("ATENDIMENTO COM O N", "DATA DO ATENDIMENTO")  # planilhas da extensão 1.5 (sem "Último atendimento")
    c_proc, c_sit = col("PROCESSOS", "PROCESSO"), col("SITUACAO")
    if c_lista is None or (c_ult is None and c_data is None):
        raise ValueError("não é a planilha do lote do SAP (faltam as colunas de nome e de atendimento)")
    v = lambda l, i: (l[i].strip() if i is not None and i < len(l) else "")
    out = []
    for l in linhas[1:]:
        if not any(x.strip() for x in l):
            continue
        sit = v(l, c_sit)
        ult_txt = v(l, c_ult) if c_ult is not None else v(l, c_data)
        ult = _data(ult_txt)
        out.append({"lista": v(l, c_lista), "nome_sap": v(l, c_sap), "mae": v(l, c_mae), "sap_id": v(l, c_id),
                    "ultimo": ult, "processos": _cnjs(v(l, c_proc)), "situacao": sit,
                    "nunca": not ult and (bool(NUNCA.match(sit)) or "sem atendimento registrado" in ult_txt.lower())})
    return out


def _melhor(infos):
    """vários cadastros para o mesmo nº: vale o atendimento mais recente."""
    com = [i for i in infos if i["ultimo"]]
    if com:
        return max(com, key=lambda i: i["ultimo"])
    return infos[0]


def classificar(registros, cadastros, hoje=None):
    """registros da base ({id, nome, proc}) -> lista em ordem de prioridade, com cor, último atendimento e dias."""
    hoje = hoje or date.today()
    por_proc, por_nome = {}, {}
    for c in cadastros:
        for p in c["processos"]:
            por_proc.setdefault(p, []).append(c)
        for n in {_norm(c["lista"]), _norm(c["nome_sap"])} - {""}:
            por_nome.setdefault(n, []).append(c)
    out = []
    for r in registros:
        procs = _cnjs(r.get("proc"))
        achado = [c for p in procs for c in por_proc.get(p, [])]
        fonte = "nº da execução" if achado else ""
        info = _melhor(achado) if achado else None
        if not info:
            mesmos = por_nome.get(_norm(r.get("nome")), [])
            pessoas = {(c["sap_id"] or c["mae"] or id(c)) for c in mesmos}
            if len(pessoas) == 1:
                info, fonte = _melhor(mesmos), "nome"
            elif len(pessoas) > 1:
                datas = sorted({c["ultimo"].strftime("%d/%m/%Y") for c in mesmos if c["ultimo"]})
                out.append(dict(r, cor="cinza", txt="Homônimos na planilha: confira", ultimo="", dias=None, fonte="nome",
                                obs=("datas: " + ", ".join(datas)) if datas else "", ordem=(3, 0)))
                continue
        if not info:
            out.append(dict(r, cor="cinza", txt="Não está na planilha", ultimo="", dias=None, fonte="", obs="", ordem=(3, 0)))
            continue
        if info["ultimo"]:
            dias = (hoje - info["ultimo"]).days
            cor, txt = ("amarelo", "Há mais de %d dias" % PRAZO_DIAS) if dias > PRAZO_DIAS else ("verde", "Dentro de %d dias" % PRAZO_DIAS)
            out.append(dict(r, cor=cor, txt=txt, ultimo=info["ultimo"].strftime("%d/%m/%Y"), dias=dias, fonte=fonte, obs="",
                            ordem=(1 if cor == "amarelo" else 2, -dias)))
        elif info["nunca"]:
            out.append(dict(r, cor="vermelho", txt="Nunca atendido", ultimo="", dias=None, fonte=fonte, obs=info["situacao"], ordem=(0, 0)))
        else:
            out.append(dict(r, cor="cinza", txt="Não verificado no SAP", ultimo="", dias=None, fonte=fonte, obs=info["situacao"], ordem=(3, 0)))
    # prioridade: nunca atendidos; depois mais de 90 dias e até 90 dias, do mais antigo ao mais recente; sem informação no fim
    out.sort(key=lambda x: (x["ordem"], _norm(x.get("nome"))))
    for x in out:
        x.pop("ordem", None)
    return out


def para_json(cadastros):
    return [dict(c, ultimo=c["ultimo"].isoformat() if c["ultimo"] else "") for c in cadastros]


def de_json(lst):
    out = []
    for c in lst or []:
        c = dict(c)
        try:
            c["ultimo"] = datetime.strptime(c["ultimo"], "%Y-%m-%d").date() if c.get("ultimo") else None
        except ValueError:
            c["ultimo"] = None
        out.append(c)
    return out
