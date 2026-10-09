"""Dados prisionais de MS pelo Geopresídios (CNJ): a API pública do CNIEP (Cadastro Nacional de Inspeções nos Estabelecimentos
Penais) traz, para cada unidade, a última inspeção mensal do juízo. Do tema "Aspectos Gerais" saem a capacidade, a população
por regime e por perfil e o quadro de servidores. Os dados ficam guardados num arquivo ao lado do programa e só são baixados
de novo pelo botão "Atualizar"."""
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime

API = "https://cniep.cnj.jus.br/api"
SITE = "https://geopresidios.cnj.jus.br/"
UF = "MS"
TEMA_GERAL = 1  # Aspectos Gerais: estrutura, ocupação, população prisional e servidores penais

# unidades do sistema penitenciário (AGEPEN e federal); as demais são delegacias, cadeias e unidades militares
RE_PENAL = re.compile(r"PENITENCI|PRESIDIO|ESTABELECIMENTO PENAL|CENTRO PENAL|COLONIA PENAL|CENTRO DE DETENCAO|TRIAGEM|UNIDADE PENAL")

# questão do formulário -> campo
QUESTOES = {
    "100034": "capacidade",
    "100902": "provisorios", "100903": "fechado", "100904": "semiaberto", "100905": "aberto",
    "100906": "medida_seguranca", "100907": "prisao_civil", "100908": "rdd", "100909": "isolamento", "100910": "seguro",
    "100911": "homens", "100912": "mulheres", "100913": "migrantes", "100914": "indigenas",
    "100916": "lgbt", "100917": "idosos", "100918": "deficiencia_fisica", "100919": "transtorno_mental",
    "100922": "gestantes", "100923": "lactantes",
}
TEXTO = {"100001": "classificacao", "100002": "destinacao", "100035": "faixa_lotacao"}


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper()


def _get(caminho, params=None, timeout=90):
    url = API + caminho + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "APTO"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _extrair(rel):
    """Campos da unidade a partir do relatório de uma inspeção do tema 1."""
    out, serv = {}, {}
    for r in rel.get("respostas") or []:
        q = str(r.get("numero_questao") or "")
        if q in QUESTOES and out.get(QUESTOES[q]) is None:
            out[QUESTOES[q]] = _num(r.get("resposta"))
        elif q in TEXTO and not out.get(TEXTO[q]) and isinstance(r.get("resposta"), str):
            out[TEXTO[q]] = r["resposta"]
        elif q in ("100093", "100094") and isinstance(r.get("pergunta"), str):
            serv[r["pergunta"]] = _num(r.get("resposta"))
    out["servidores"] = sum(v or 0 for k, v in serv.items() if k.startswith("Total de homens") or k.startswith("Total de mulheres")) or None
    out["servidores_seguranca"] = serv.get("Total de RH na área de segurança")
    return out


def atualizar(destino, todas=False, aviso=None):
    """Baixa o cadastro e as inspeções e, para cada unidade de MS, o relatório da última inspeção do tema 1.
    Grava o resultado em `destino` e o devolve. `todas`: inclui delegacias, cadeias e unidades militares."""
    aviso = aviso or (lambda *_: None)
    aviso("cadastro de estabelecimentos")
    estabs = [e for e in _get("/geopresidios/estabelecimentos") if e.get("dsc_uf") == UF and e.get("flg_ativo") == "S"]
    try:  # cidade e coordenadas de cada unidade (o cadastro não traz)
        geo = {m["seq_estabelecimento"]: m.get("geo") or {} for m in _get("/geopresidios/mapa") if m.get("dsc_uf") == UF}
    except Exception:
        geo = {}
    aviso("inspeções")
    insp = [i for i in _get("/geopresidios/inspecoes", timeout=180)
            if (i.get("estabelecimento") or {}).get("dsc_uf") == UF and not i.get("excluida") and i.get("status_submissao")]
    ult = {}
    for i in insp:
        if i.get("tema_id") == TEMA_GERAL and (i["seq_estabelecimento"] not in ult or i["data_inicio"] > ult[i["seq_estabelecimento"]]["data_inicio"]):
            ult[i["seq_estabelecimento"]] = i
    unidades = []
    sel = [e for e in estabs if todas or RE_PENAL.search(_sem_acento(e["dsc_identificacao"]))]
    for n, e in enumerate(sorted(sel, key=lambda x: x["dsc_identificacao"]), 1):
        u = {"id": e["seq_estabelecimento"], "nome": re.sub(r"\s+", " ", e["dsc_identificacao"]).strip(), "endereco": e.get("dsc_endereco") or "",
             "penal": bool(RE_PENAL.search(_sem_acento(e["dsc_identificacao"]))), "inspecao": None}
        g = geo.get(e["seq_estabelecimento"]) or {}
        try:
            u.update(cidade=(g.get("dsc_cidade") or "").title(), ibge=str(g.get("codigo_ibge") or ""), lat=float(g["lat"]), lon=float(g["lon"]))
        except (KeyError, TypeError, ValueError):
            u.update(cidade=(g.get("dsc_cidade") or "").title(), ibge=str(g.get("codigo_ibge") or ""))
        i = ult.get(e["seq_estabelecimento"])
        if i:
            aviso("relatório %d de %d" % (n, len(sel)))
            try:
                u.update(_extrair(_get("/geopresidios/relatorio-inspecao", {"ID_INSPECAO": i["id"]})))
                u["inspecao"] = {"id": i["id"], "data": i["data_inicio"][:10], "ciclo": i.get("ciclo") or ""}
            except Exception as ex:  # uma unidade com falha não derruba as demais
                u["erro"] = str(ex)[:120]
        unidades.append(u)
    dados = {"atualizado": datetime.now().strftime("%d/%m/%Y %H:%M"), "fonte": SITE, "uf": UF, "todas": todas, "unidades": unidades}
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    os.replace(tmp, destino)
    return dados


def carregar(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def chave_unidade(nome):
    """Nome normalizado para casar a unidade da ficha (SIAPEN) com a do Geopresídios."""
    s = _sem_acento(nome)
    s = re.sub(r"\b(DE|DA|DO|DAS|DOS|E|EM|REGIME|MASCULINO|MASCULINA|ESTADUAL)\b", " ", s)
    return re.sub(r"[^A-Z0-9]+", " ", s).split()
