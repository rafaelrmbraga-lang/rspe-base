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

# tipo do estabelecimento pelo nome: unidades penais (AGEPEN e federal), delegacias e cadeias, unidades militares e as demais
RE_MILITAR = re.compile(r"REGIMENTO|BATALH|COMPANHIA|BASE AEREA|BASE DE ADMIN|ALA \d|COMANDO|GRUPO DE ARTILHARIA|EXERCITO|FUZILEIROS|PRESIDIO MILITAR")
RE_PENAL = re.compile(r"PENITENCI|PRESIDIO|ESTABELECIMENTO PENAL|CENTRO PENAL|COLONIA PENAL|CENTRO DE DETENCAO|TRIAGEM|UNIDADE PENAL|INSTITUTO PENAL")
RE_DELEGACIA = re.compile(r"DELEGACIA|\bDEAM\b|\bDEFURV\b|\bDP\b|DEPAC|CEPOL|GARRAS|DERF|CADEIA")
CATEGORIAS = {"penal": "Unidades penais", "delegacia": "Delegacias e cadeias", "militar": "Unidades militares", "outra": "Polícia Federal e outras"}


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

# indicadores dos demais temas (rodízio mensal: 2 habitabilidade, 3 assistências, 4 segurança, 5 saúde).
# (chave, tema, questão, rótulo, resposta que indica problema: regex sobre o texto sem acento, ou None quando só informa)
INDICADORES = [
    ("agua_racion", 2, "200006", "Racionamento de água", r"^SIM"),
    ("agua_acesso", 2, "200055", "Água para consumo a qualquer momento", r"^NAO"),
    ("refeicoes", 2, "200028", "Cinco refeições diárias", r"^NAO"),
    ("alim_castigo", 2, "200041", "Alimentação suspensa ou limitada como castigo", r"^SIM"),
    ("agua_castigo", 2, "200057", "Água suspensa ou limitada como castigo", r"^SIM"),
    ("sanitarios", 2, "200004", "Condições dos sanitários", r"RUIM|PESSIM|INADEQUAD"),
    ("vestuario", 2, "200014", "Reposição do vestuário", r"^NAO"),
    ("ubs", 5, "500002", "UBS do SUS na unidade", r"^NAO"),
    ("equipe_saude", 5, "500008", "Equipe de saúde com a composição mínima", r"^NAO"),
    ("medicos", 5, "500008.3", "Médicos em número adequado à população", r"^NAO"),
    ("saude_24h", 5, "500010", "Atendimento de saúde 24 horas", r"^NAO"),
    ("vacinacao", 5, "500015", "Vacinação regular", r"^NAO"),
    ("forcas_especiais", 4, "400005.3", "Intervenção de forças especiais de segurança", r"^SIM"),
    ("procedimento", 4, "400010", "Prática do \"procedimento\" na rotina", r"^SIM"),
    ("familia_transf", 4, "400034.1", "Família informada das transferências", r"^NAO|NUNCA|AS VEZES"),
    ("rem_leitura", 3, "300064", "Remição pela leitura reconhecida a todos", r"^NAO"),
    ("rem_estudo", 3, "300073", "Remição pelo estudo", r"^NAO"),
    ("trab_vagas", 3, "300084", "Vagas de trabalho oferecidas", r"^NAO"),
    ("trab_juizo", 3, "300085", "Registro mensal do trabalho enviado ao juízo", r"^NAO"),
    ("visitas", 3, "300001", "Visitas sociais presenciais", None),
    ("banho_sol", 3, "300054", "Banho de sol", r"NAO E OFERTADO|MENOS DE"),
    ("defensoria", 3, "300044", "Defensoria Pública na unidade", r"NAO HA ATENDIMENTO|NAO COMPARECE|NUNCA"),
]
# como a constatação aparece na tela e no relatório, quando a resposta indica o problema
PROBLEMA = {
    "agua_racion": "Há racionamento de água", "agua_acesso": "Sem acesso à água para consumo a qualquer momento",
    "refeicoes": "Não são oferecidas cinco refeições diárias", "alim_castigo": "Alimentação suspensa ou limitada como castigo",
    "agua_castigo": "Água suspensa ou limitada como castigo", "sanitarios": "Sanitários em condição ruim",
    "vestuario": "Sem regularidade na reposição do vestuário", "ubs": "Sem UBS do SUS na unidade",
    "equipe_saude": "Equipe de saúde abaixo da composição mínima", "medicos": "Médicos abaixo do número adequado à população",
    "saude_24h": "Sem atendimento de saúde 24 horas", "vacinacao": "Sem vacinação regular",
    "forcas_especiais": "Intervenção de forças especiais de segurança", "procedimento": "Prática do \"procedimento\" na rotina",
    "familia_transf": "Família nem sempre informada das transferências", "rem_leitura": "Remição pela leitura não reconhecida a todos",
    "rem_estudo": "Sem remição pelo estudo", "trab_vagas": "Sem vagas de trabalho",
    "trab_juizo": "Registro do trabalho não enviado mensalmente ao juízo", "banho_sol": "Banho de sol abaixo de 2 horas ou não ofertado",
    "defensoria": "Sem atendimento periódico presencial da Defensoria",
}
MESES = ["JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]


def ordem_ciclo(ciclo):
    """'Julho/2026' ou 'Janeiro/26' -> (2026, 7), para ordenar os ciclos de inspeção."""
    m = re.match(r"\s*([^/]+)/(\d{2,4})", _sem_acento(ciclo or ""))
    if not m or m.group(1).strip() not in MESES:
        return (0, 0)
    a = int(m.group(2))
    return (a + 2000 if a < 100 else a, MESES.index(m.group(1).strip()) + 1)


NUM_TEMA = {"defensores": ("300043", None), "trab_remicao": ("300087", "Com cômputo para remição"), "escola": ("300072", "*")}
TEMAS = {1: "Aspectos gerais", 2: "Habitabilidade e necessidades básicas", 3: "Serviços, assistências e contato com o mundo exterior",
         4: "Segurança e prevenção da violência", 5: "Acesso à saúde integral"}


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper()


def categoria(nome):
    n = _sem_acento(nome)
    return "militar" if RE_MILITAR.search(n) else "penal" if RE_PENAL.search(n) else "delegacia" if RE_DELEGACIA.search(n) else "outra"


def _get(caminho, params=None, timeout=90, tentativas=6):
    """GET na API; repete com espera crescente quando o servidor limita os pedidos (429) ou falha (5xx, conexão)."""
    import random
    import time
    import urllib.error
    url = API + caminho + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "APTO"})
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            if ex.code != 429 and ex.code < 500 or n == tentativas - 1:
                raise
            espera = ex.headers.get("Retry-After") if ex.headers else None
            time.sleep(float(espera) if espera and espera.isdigit() else min(30, 2 ** n) + random.random())
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if n == tentativas - 1:
                raise
            time.sleep(min(30, 2 ** n) + random.random())


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


def _populacao(rel, tema):
    """População por regime informada em qualquer inspeção (todos os temas repetem o quadro de pessoas)."""
    v = {}
    for r in rel.get("respostas") or []:
        q = str(r.get("numero_questao") or "")
        if len(q) == 6 and q[0] == str(tema) and q[1:] in ("00902", "00903", "00904", "00905", "00906", "00907"):
            v.setdefault(q[1:], _num(r.get("resposta")))
    if not v:
        return None
    k = {"00902": "provisorios", "00903": "fechado", "00904": "semiaberto", "00905": "aberto"}
    out = {k[q]: (v.get(q) or 0) for q in k}
    out["pop"] = sum((x or 0) for x in v.values())
    return out


def _indicadores(rel, tema):
    """Respostas dos indicadores do tema: {chave: {"v": texto, "ruim": bool}} e os números (defensores, trabalho, escola)."""
    resp = {}
    for r in rel.get("respostas") or []:
        q = str(r.get("numero_questao") or "")
        resp.setdefault(q, []).append(r)
    out = {}
    for ch, t, q, rot, ruim in INDICADORES:
        if t != tema:
            continue
        v = next((x.get("resposta") for x in resp.get(q, []) if isinstance(x.get("resposta"), str) and x["resposta"].strip()), None)
        if v is None or v.upper() in ("NA", "NONE"):
            continue
        vv = v.replace("*", "").strip()
        # "Não informado" / "Não se aplica" não são constatação de problema
        sem = re.match(r"NAO (INFORMAD|SE APLICA|VERIFICAD)", _sem_acento(vv))
        out[ch] = {"v": vv, "ruim": bool(ruim and not sem and re.search(ruim, _sem_acento(vv)))}
    for ch, (q, perg) in NUM_TEMA.items():
        if q[0] != str(tema) or q not in resp:
            continue
        if perg == "*":
            n = sum(_num(x.get("resposta")) or 0 for x in resp[q])
        else:
            n = next((_num(x.get("resposta")) for x in resp[q] if not perg or str(x.get("pergunta") or "").startswith(perg)), None)
        if n is not None:
            out[ch] = {"n": n}
    return out


def atualizar(destino, todas=False, aviso=None):
    """Baixa o cadastro e as inspeções e, para cada estabelecimento de MS (unidades penais, delegacias, cadeias e unidades
    militares), o relatório da última inspeção de cada tema. Grava o resultado em `destino` e o devolve. `todas` fica por
    compatibilidade: o download traz sempre todos e a tela filtra pelo tipo."""
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
    ult = {}  # (unidade, tema) -> última inspeção
    for i in insp:
        ch = (i["seq_estabelecimento"], i.get("tema_id"))
        if ch not in ult or i["data_inicio"] > ult[ch]["data_inicio"]:
            ult[ch] = i
    sel = estabs  # todos os estabelecimentos de MS; a tela filtra pelo tipo (unidades penais, delegacias, militares, outras)
    pedidos = [i for (sq, t), i in ult.items() if any(e["seq_estabelecimento"] == sq for e in sel)]
    rels, feitos = {}, [0]
    antigo = {}  # inspeção -> dados já baixados antes (usados se o relatório desta vez falhar)
    for u0 in (carregar(destino) or {}).get("unidades", []):
        for t0, T0 in (u0.get("temas") or {}).items():
            antigo[T0.get("id")] = ("tema", u0, t0)
        if u0.get("inspecao"):
            antigo[u0["inspecao"].get("id")] = ("geral", u0, "1")

    def baixa(i):
        try:
            rels[i["id"]] = _get("/geopresidios/relatorio-inspecao", {"ID_INSPECAO": i["id"]})
        except Exception as ex:  # uma inspeção com falha não derruba as demais
            rels[i["id"]] = {"erro": str(ex)[:120]}
        feitos[0] += 1
        aviso("relatórios: %d de %d" % (feitos[0], len(pedidos)))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:  # mais que isso, o servidor do CNJ passa a recusar (429)
        list(ex.map(baixa, pedidos))
    unidades, falhas = [], [0]
    for e in sorted(sel, key=lambda x: x["dsc_identificacao"]):
        sq = e["seq_estabelecimento"]
        u = {"id": sq, "nome": re.sub(r"\s+", " ", e["dsc_identificacao"]).strip(), "endereco": e.get("dsc_endereco") or "",
             "cat": categoria(e["dsc_identificacao"]), "inspecao": None, "temas": {}, "serie": []}
        u["penal"] = u["cat"] == "penal"
        g = geo.get(sq) or {}
        try:
            u.update(cidade=(g.get("dsc_cidade") or "").title(), ibge=str(g.get("codigo_ibge") or ""), lat=float(g["lat"]), lon=float(g["lon"]))
        except (KeyError, TypeError, ValueError):
            u.update(cidade=(g.get("dsc_cidade") or "").title(), ibge=str(g.get("codigo_ibge") or ""))
        for t in sorted(TEMAS):
            i = ult.get((sq, t))
            rel = rels.get(i["id"]) if i else None
            if not rel or rel.get("erro"):
                if rel and rel.get("erro"):
                    velho = antigo.get(i["id"])
                    if velho and velho[0] == "tema":
                        u["temas"][str(t)] = velho[1]["temas"][velho[2]]
                    elif velho:
                        u.update({k: velho[1].get(k) for k in list(QUESTOES.values()) + list(TEXTO.values()) + ["servidores", "servidores_seguranca", "inspecao"]})
                    else:
                        falhas[0] += 1
                        u["erro"] = rel["erro"]
                continue
            info = {"id": i["id"], "data": i["data_inicio"][:10], "ciclo": i.get("ciclo") or ""}
            if t == TEMA_GERAL:
                u.update(_extrair(rel))
                u["inspecao"] = info
            else:
                u["temas"][str(t)] = dict(info, ind=_indicadores(rel, t))
            p = _populacao(rel, t)
            if p:
                u["serie"].append(dict(p, data=info["data"], ciclo=info["ciclo"]))
        u["serie"].sort(key=lambda x: (ordem_ciclo(x["ciclo"]), x["data"]))
        if u["serie"]:
            # a população mais recente vem da inspeção do mês (qualquer tema); a capacidade e o perfil, do tema 1
            a = u["serie"][-1]
            u.update(provisorios=a["provisorios"], fechado=a["fechado"], semiaberto=a["semiaberto"], aberto=a["aberto"],
                     pop=a["pop"], pop_ciclo=a["ciclo"], pop_data=a["data"])
        unidades.append(u)
    dados = {"atualizado": datetime.now().strftime("%d/%m/%Y %H:%M"), "fonte": SITE, "uf": UF, "todas": True, "unidades": unidades,
             "falhas": falhas[0]}
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
