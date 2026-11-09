"""Gera monitor_juris.bin (base do Monitor nos dois sentidos) a partir do acervo classificado (mj/class.pkl).

Formato: b"APTOMON1" + uint32 (tamanho do JSON comprimido) + zlib(JSON {"cab": {...}, "itens": [...]})."""
import os
import pickle, json, re, sys, struct, zlib, collections, unicodedata
S = os.environ.get("APTO_MJ_PASTA", ".")
sys.path.insert(0, S + "/mj")
import classif as C
OUT = sys.argv[1] if len(sys.argv) > 1 else S + "/mj/monitor_juris.bin"
rows = pickle.load(open(S + "/mj/rows.pkl", "rb")); res = pickle.load(open(S + "/mj/class.pkl", "rb"))

SIGLAS = ["LEP", "STJ", "STF", "TJMS", "TJSP", "CNJ", "PAD", "PADIC", "ENEM", "ENCCEJA", "CPP", "CP", "HC", "RHC", "MP", "MPF", "RE", "ARE", "REsp",
          "AREsp", "RDD", "SEEU", "CF", "EAD", "AGEPEN", "VEP", "RISTF", "RISTJ", "PGJ", "PGR", "SV", "ADI", "ADPF", "ADC", "COVID-19", "SISTEC"]
SIG = {s.lower(): s for s in SIGLAS}
ROMANO = re.compile(r"^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)$")


def frase(t):
    """Palavras em caixa alta da ementa -> caixa baixa (siglas e incisos romanos preservados); depois, maiúscula no início das frases."""
    letras = [c for c in t[:200] if c.isalpha()]
    if not letras or sum(c.isupper() for c in letras) < 0.3 * len(letras):
        return t
    out = []
    for w in re.split(r"([^\wÀ-ú-]+)", t):
        k = w.lower()
        if not w or not w[0].isalpha():
            out.append(w)
        elif k in SIG:
            out.append(SIG[k])
        elif w.isupper() and ROMANO.match(k) and len(k) > 1:
            out.append(w)
        elif w.isupper():
            out.append(k)
        else:
            out.append(w)
    t = "".join(out)
    t = re.sub(r"(^|[.!?]\s+|\s[–-]\s+)([a-zà-ú])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t


def curto(t, n=300):
    t = " ".join((t or "").replace("|", " ").split())
    t = re.sub(r"^(e m e n t a|ementa)\s*[:\-–]?\s*", "", t, flags=re.I)
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:-–") + "…"


MARC_RAW = re.compile(r"(Ante o exposto|Diante do exposto|Pelo exposto|Em face do exposto|Do exposto|Isso posto|Posto isso|Isto posto|Ex positis|Diante disso|Por tais raz[õo]es|Com essas considera[çc][õo]es)\s*,?\s*", re.I)


VERBO1 = re.compile(r"\b(n[ãa]o conhe[çc]o|conhe[çc]o|concedo|denego|nego|dou|indefiro|julgo|defiro|homologo|acolho|rejeito|reconsidero|declaro)\b", re.I)


def tese(r, tipo):
    raw = r[14] or ""
    cap = C.cab_maiusc(raw).strip()
    if tipo != "Monocrática" and len(cap) > 40:
        return curto(frase(cap))
    if tipo != "Monocrática" and not re.match(r"\s*(AC[ÓO]RD[ÃA]O|DECIS[ÃA]O|RELAT[ÓO]RIO|Vistos)", raw):
        return curto(frase(raw[:700]))
    ms = list(MARC_RAW.finditer(raw))
    if ms:
        s = raw[ms[-1].end():]
        s = re.split(r"\bPublique-se|\bIntime-se|\bIntimem-se|\bComunique-se|\bP\. ?I\.|\bEMENTA\b", s)[0]
        s = s.strip()
        v = VERBO1.search(s[:260])
        if v and v.start() > 0 and re.match(r"(com|nos termos|na forma|forte|por|em face|acolh|nao|não|constatad|ausente|presente|considerand|diante|assim)", s, re.I):
            s = s[v.start():]
        if len(s) > 25:
            s = s[0].upper() + s[1:]
            return curto(s)
    if len(cap) > 40:
        return curto(frase(cap))
    return curto(frase(raw[:700]))


ORG_STJ = {"quinta turma": "Quinta Turma", "sexta turma": "Sexta Turma", "terceira secao": "Terceira Seção", "corte especial": "Corte Especial",
           "primeira turma": "Primeira Turma", "segunda turma": "Segunda Turma", "terceira turma": "Terceira Turma", "quarta turma": "Quarta Turma",
           "primeira secao": "Primeira Seção", "segunda secao": "Segunda Seção", "6a turma": "Sexta Turma", "5a turma": "Quinta Turma"}
ORG_STF = {"primeira turma": "Primeira Turma", "segunda turma": "Segunda Turma", "tribunal pleno": "Tribunal Pleno", "plenario": "Tribunal Pleno"}


def orgao(r, rg):
    o = (r[6] or "").strip()
    k = C.sa(o)
    if r[1] == "TJMS":
        if re.match(r"^\d(a|ª)? (camara|secao) criminal$|^secao especial - criminal$|^orgao especial$|^vice-presidencia$", k):
            return o
        return ""
    tab = ORG_STJ if r[1] == "STJ" else ORG_STF
    if k in tab:
        return tab[k]
    if not k and r[1] == "STJ" and r[2] == "Acórdão":
        m = re.search(r"acordam os (srs\. )?ministros da (quinta turma|sexta turma|terceira secao|corte especial|primeira turma|segunda turma)", rg["t"][:3000])
        if m:
            return ORG_STJ[m.group(2)]
    if not k and r[1] == "STF" and r[2] == "Acórdão":
        m = re.search(r"orgao julgador: \| (primeira turma|segunda turma|tribunal pleno)", rg["t"][:400])
        if m:
            return ORG_STF[m.group(1)]
    return ""


ALIAS = {"rogerio schietti": "Rogerio Schietti Cruz", "marluce caldas": "Maria Marluce Caldas", "elizabete anache": "Elizabete Anache",
         "dileta terezinha souza thomaz": "Dileta Terezinha Souza Thomaz", "joao otavio de noronha": "João Otávio de Noronha",
         "luis roberto barroso": "Roberto Barroso"}


def relator(r):
    x = (r[7] or "").strip()
    x = re.sub(r"\s*\((desembargador|desembargadora|presidente|juiz|juíza)[^)]*\)\s*", " ", x, flags=re.I).strip()
    x = re.sub(r"^(Desª\.?|Des\.|Desa\.|Min\.|Ministro|Ministra|Desembargador[a]?)\s+", "", x).strip()
    if not x or len(x) > 60 or re.search(r"\d|[,;()\"]", x) or not x[0].isupper() or x.lower() in ("presidente", "vice-presidente", "ativa", "ativo", "ativas", "evante", "evantes"):
        return ""
    if x.isupper() or (x.istitle() and re.search(r" (De|Da|Do|Dos|Das|E) ", x)):
        x = " ".join(w.capitalize() if w.lower() not in ("de", "da", "do", "dos", "das", "e") else w.lower() for w in x.lower().split())
    if len(x.split()) < 2:
        return ""
    k = C.sa(x)
    return ALIAS.get(k, x)


def data(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    return "%s/%s/%s" % (m.group(3), m.group(2), m.group(1)) if m else ""


def link(r, pub):
    l = r[15] or ""
    if r[1] == "TJMS" and not l and r[3]:
        return ("https://esaj.tjms.jus.br/cjsg/resultadoCompleta.do?conversationId=&dados.buscaInteiroTeor=%%22%s%%22"
                "&dados.pesquisarComSinonimos=N&tipoDecisaoSelecionados=A" % r[3])
    m = re.search(r"processo\.stj\.jus\.br/processo/pesquisa/\?num_registro=(\d{12})", l)
    if m and r[2] == "Monocrática" and pub:
        return "https://processo.stj.jus.br/processo/monocraticas/decisoes/?num_registro=%s&dt_publicacao=%s" % (m.group(1), pub)
    return l


# relator só vale se o nome se repete no tribunal (o acervo traz pedaços de texto no campo em algumas monocráticas)
FREQ = collections.Counter()
for r in rows:
    d = res[r[0]]
    if d["esc"] and d.get("sentido"):
        FREQ[(r[1], relator(r))] += 1


def relator_ok(r):
    x = relator(r)
    return x if FREQ[(r[1], x)] >= (3 if r[1] == "STF" else 5) else ""


itens = []
cont = collections.Counter()
sem = collections.Counter()
for r in rows:
    d = res[r[0]]
    if not d["esc"]:
        cont[(r[1], "fora")] += 1
        continue
    cont[(r[1], "escopo")] += 1
    if not d.get("sentido"):
        sem[(r[1], d.get("rot") or "?")] += 1
        continue
    rg = C.regioes(r)
    pub = data(r[10])
    julg = data(r[9])
    ano = int(r[11]) if (r[11] or "").isdigit() else 0
    if ano < 2008:
        ano = int((julg or pub)[-4:]) if (julg or pub) else 0
        if ano < 2008:
            ano = 0
    x = {"id": r[0], "tribunal": r[1], "tipo": r[2], "orgao": orgao(r, rg), "relator": relator_ok(r), "julg": julg, "pub": pub, "ano": ano,
         "classe": r[4] or "", "proc": r[3] or "", "temas": d["temas"], "sentido": d["sentido"], "resultado": r[12] or "", "rot": d["rot"],
         "link": link(r, pub), "tese": tese(r, r[2])}
    if r[1] == "TJMS" and r[8]:
        x["comarca"] = r[8]
    itens.append(x)
    cont[(r[1], d["sentido"])] += 1
itens.sort(key=lambda x: (x["tribunal"], x["id"]))
porT = {t: {k: cont[(t, k)] for k in ("escopo", "fora", "favoravel", "parcial", "desfavoravel", "nao_conhecido")} for t in ("TJMS", "STJ", "STF")}
for t in porT:
    porT[t]["sem_sentido"] = sum(v for (tt, _), v in sem.items() if tt == t)
    porT[t]["sem_sentido_motivos"] = {k: v for (tt, k), v in sem.most_common() if tt == t}
cab = {"versao": "2026-11-09", "formato": 1,
       "fonte": "acervo_jurisprudencia.db (coleta de 22/07/2026 a 07/10/2026 por termo de busca, sobretudo \"execução penal\"): 188.037 decisões do TJMS, STJ e STF",
       "total": len(itens), "por_tribunal": porT,
       "regra": "escopo: execução penal (fora: dosimetria, regime inicial, prisão cautelar, nulidades e mérito da ação penal); sentido para a defesa "
                "pelo dispositivo x quem recorreu (defesa, MP); sem sentido determinável fica fora da base (e das taxas)",
       "precisao": "amostras lidas uma a uma (5 rodadas, 577 decisões): última rodada (regras finais, fora do ajuste) TJMS 90,6%, STJ 100%, STF 93,1%; "
                   "com as regras finais sobre todas as amostras: TJMS 95,7%, STJ 99,0%, STF 94,8%"}
js = json.dumps({"cab": cab, "itens": itens}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
z = zlib.compress(js, 9)
open(OUT, "wb").write(b"APTOMON1" + struct.pack("<I", len(z)) + z)
print("itens", len(itens), "json", len(js), "bin", len(z) + 12)
print(json.dumps(porT, ensure_ascii=False, indent=1)[:3000])
