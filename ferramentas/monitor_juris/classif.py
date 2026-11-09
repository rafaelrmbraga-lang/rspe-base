"""Classificação do acervo para o Monitor: escopo (execução penal), temas, quem recorreu, dispositivo e sentido para a defesa."""
import os
import re, unicodedata

def sa(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)

# ------------------------------------------------------------------ regiões do texto
MARC = re.compile(r"(ante o exposto|diante do exposto|pelo exposto|em face do exposto|do exposto|isso posto|posto isso|isto posto|ante o quadro|com essas consideracoes|por tais razoes|em vista do exposto|face ao exposto|por essas razoes|por esses motivos|por todo o exposto|nessas condicoes|dessa forma, (?=(nao )?(conheco|nego|dou|concedo|denego|indefiro|julgo))|assim, (?=(nao )?(conheco|nego|dou|concedo|denego|indefiro|julgo)))")


def caption(t):
    """Ementa em caixa alta (TJMS/STF/STJ acórdão; STJ monocrática no fim, depois de "EMENTA")."""
    for m in re.finditer(r"(ementa\s*:?\s*\|?\s*)", t):
        pass
    return ""


def cab_maiusc(raw):
    """Maior trecho inicial em caixa alta depois de 'Ementa:' / 'EMENTA' (a ementa-cabeçalho)."""
    out = []
    for m in re.finditer(r"EMENTA\s*:?\s*\|?|Ementa\s*:\s*\|?", raw):
        s = raw[m.end():m.end() + 2500]
        # corta onde começa texto em caixa baixa corrida (5 palavras minúsculas seguidas)
        mm = re.search(r"(?:\b[a-zà-ú][a-zà-ú,;]*\s+){6}", s)
        cap = s[:mm.start()] if mm else s[:900]
        if len(cap) > 40:
            out.append(cap)
    return " ".join(out)


def regioes(r):
    raw = r[14] or ""
    t = sa(raw)
    cap = sa(cab_maiusc(raw))
    if not cap and r[1] == "TJMS":
        cap = t[:700]
    ini = t[:1600]
    # dispositivo: janelas por prioridade
    jan = []
    m = re.search(r"acordam[^.]{0,200}?(por unanimidade|por maioria)[, ]+(.{0,330})", t[:2500])
    if m:
        jan.append(("acordam", m.group(2)))
    m = r[1] == "STF" and re.search(r"decisao: ?(a turma|o tribunal|a (primeira|segunda) turma|o plenario)[^.]{0,40}?(,|por unanimidade|por maioria)(.{0,300})", t)
    if m:
        jan.append(("stf_dec", m.group(4)))
    ms = list(MARC.finditer(t))
    if ms:
        k = ms[-1]
        # no STJ monocrático o fim pode trazer "EMENTA" depois do dispositivo: a janela vai até ela
        jan.append(("marcador", t[k.end():k.end() + 420]))
    m = re.search(r"(iv\.? ?-? ?dispositivo|dispositivo e tese|dispositivo:)(.{0,300})", t)
    if m:
        jan.append(("dispositivo", m.group(2)))
    if cap:
        jan.append(("cabecalho", cap[-260:]))
    jan.append(("fim", t[-450:]))
    return {"t": t, "cap": cap, "ini": ini, "jan": jan, "trib": r[1]}


# ------------------------------------------------------------------ dispositivo
_NEG_ANTES = re.compile(r"(nao|deixo de|deixa-se de|incabivel|descabe|nem|sem|inviavel|tampouco|nao ha como|nao e caso de|caso de)\s*(\w+\s*){0,3}$")
P = [
    ("oficio", r"(concedo|conceder|concedeu|concedida|concedido|concede-se|concedendo|concedo,)[^.;]{0,70}de oficio|de oficio,? (concedo|conceder|concedeu|concede-se|a ordem|habeas corpus)|ordem concedida,? de oficio|de oficio,? concedid[oa] (a ordem|o habeas)|habeas corpus concedido de oficio|concessao (da ordem )?de oficio (de|do|da|para)|concedo, de oficio|expeco,? de oficio"),
    ("parcial", r"(concedo|concedid[oa]|conceder),? (a ordem,? )?em menor extensao|concedo parcialmente|concedo em parte|concedo,? em parte|conceder parcialmente|conceder em parte|concedeu parcialmente|parcialmente concedid|concedid[oa] em parte|concedid[oa] parcialmente|dou parcial provimento|dar parcial provimento|deu parcial provimento|deram parcial provimento|dou provimento parcial|dou-lhe parcial provimento|parcialmente provid|provid[oa] em parte|provid[oa] parcialmente|julgo parcialmente procedente|parcialmente procedente|acolho parcialmente|acolher parcialmente|parcialmente acolhid|defiro parcialmente|deferid[oa] em parte|parcialmente deferid|provimento parcial"),
    ("concedida", r"conced(o|er|eu|eram|e-se)\s*,?\s*(liminarmente\s*,?\s*|de plano\s*,?\s*|in limine\s*,?\s*|monocraticamente\s*,?\s*)?(o presente o |o presente |a presente |a |o |a|o)?\s*(ordem|habeas|writ|impetracao|seguranca|presente (habeas|writ|ordem))|ordem\s*concedida|\bdefiro,?\s*(liminarmente,?\s*)?(o |a )?(presente )?(habeas|ordem|writ)|habeas corpus\s*concedido|writ concedido|seguranca concedida"),
    ("denegada", r"\bdenego\b|\bdenegar\b|\bdenegou\b|\bdenegaram\b|ordem denegada|habeas corpus denegado|writ denegado|seguranca denegada|indefiro a ordem|indeferiu a ordem|denegada a ordem"),
    ("indef", r"indefiro liminarmente|indefiro,? liminarmente|indeferir liminarmente|indefiro in limine|indefiro a peticao inicial|indefiro o habeas corpus|indefiro o presente habeas|indefiro a inicial|indefiro o writ|indefiro o pedido inicial|indefiro a impetracao|indeferimento liminar|liminarmente indeferid"),
    ("desprovido", r"(parcialmente|em parte) conhecid[oa] e,? (na parte conhecida,? |nessa extensao,? |no merito,? )?(im|des|nao )provid|conhecid[oa] em parte e,? (na parte conhecida,? |nessa extensao,? )?(im|des|nao )provid|recurso conhecido, no merito, (im|des)provid"),
    ("naoconh", r"nao conheco|nao conhecer|nao conheceu|nao conheceram|nao conhecid[oa]|nao se conhece|nao foi conhecid|nao comporta conhecimento|inadmito|nao admito|\bnao o conheco|nao conheco"),
    ("negseg", r"nego seguimento|negar seguimento|negou seguimento|negado seguimento|nego-lhe seguimento|negar-lhe seguimento|negaram seguimento|negativa de seguimento"),
    ("prej", r"julgo prejudicad|julgar prejudicad|julgou prejudicad|declaro prejudicad|prejudicad[oa] o (habeas|recurso|agravo|pedido|writ)|(recurso|agravo|habeas corpus|writ|ordem|pedido|impetracao) prejudicad|perda (superveniente )?do objeto|homologo (o pedido de )?(a )?desistencia|homologo a desistencia|extingo o (processo|feito)|julgo extint"),
    ("desprovido", r"nego\s*provimento|negar provimento|negou provimento|negaram provimento|nego-lhe provimento|negar-lhe provimento|nega-se provimento|desprovid|improvid|nao provid|rejeito os embargos|rejeitar os embargos|rejeitou os embargos|rejeitaram os embargos|embargos rejeitados|embargos de declaracao rejeitados|julgo improcedente|julgar improcedente|julgou improcedente|reclamacao improcedente|improcedente a reclamacao|indefiro o pedido|indefiro o requerimento|indefiro o pleito|indefiro os pedidos|julgo improcedentes"),
    ("provido", r"dou provimento|dar provimento|deu provimento|deram provimento|dou-lhe provimento|dar-lhe provimento|da-se provimento|(recurso|agravo|regimental|apelo|especial|extraordinario|conhecido e|conhecida e|embargos) provid|acolho os embargos|acolher os embargos|acolheu os embargos|embargos acolhidos|embargos de declaracao acolhidos|julgo procedente|julgar procedente|julgou procedente|reclamacao procedente|\bdefiro (o pedido|o requerimento|o pleito|os pedidos|a progressao|o livramento)|homologo a remicao|declaro remidos|julgo extinta a punibilidade|declaro extinta a punibilidade"),
    ("conflito", r"conheco do conflito|conhecer do conflito|conheceu do conflito|declarar competente|declarar a competencia|declaro competente|conflito conhecido"),
]
P = [(k, re.compile(v)) for k, v in P]


CITA = re.compile(r"^[\s.,;:\"')]{0,6}\(?\s*(hc|rhc|agrg|aresp|resp|edcl|agint|re|are|rcl|ag|ms|rms|ext)\b[^)]{0,40}?\d")
CITA2 = re.compile(r"^[^.;()]{0,45}[.;]?\s*[\"']?\s*\((hc|rhc|agrg|aresp|resp|edcl|agint|re|are|rcl|ag|ms|rms)\b[^)]{0,30}\d")
INTERLOC = re.compile(r"requisitem-se|solicitem-se|requisitem-se as informacoes|de-se vista|abra-se vista|ao ministerio publico federal para (parecer|manifestacao)|vista a procuradoria")
LIMINAR = re.compile(r"\b(defiro|indefiro|deferir|indeferir|concedo|nego)\s*,?\s*(o pedido de |a |o |o pedido |em parte o pedido de |parcialmente a |a medida )?(medida )?liminar\b|\b(defiro|indefiro) o pedido de reconsideracao")


def achados(s):
    out = []
    for k, rx in P:
        for m in rx.finditer(s):
            if CITA.search(s[m.end():m.end() + 60]) or CITA2.search(s[m.end():m.end() + 70]):
                continue
            antes = s[max(0, m.start() - 30):m.start()]
            if k in ("oficio", "concedida", "parcial", "provido") and _NEG_ANTES.search(antes):
                continue
            out.append((m.start(), k, m.group(0)))
    out.sort()
    return out


PRIMEIRA = re.compile(r"\b(concedo|denego|nego|dou|conheco|indefiro|julgo|homologo|defiro|acolho|rejeito|declaro|inadmito|admito|extingo|expeco|reconsidero)\b|conced(o|e-se)|nego-lhe|dou-lhe")


QUOTE_DEPOIS = re.compile(r"e-stj|ristj|regimento interno do (stj|superior)|grifei|grifo nosso|grifos? (no|do) original|\[\.\.\.\]|\(\.\.\.\)|\(fls?\. ?\d|e-doc\. ?\d+\)|\(doc\. ?\d")
QUOTE_ANTES = re.compile(r"ristj|regimento interno do (stj|superior)|e-stj|\(\.\.\.\)|\[\.\.\.\]|pelo meu voto|assim ementad|nos seguintes termos|in verbis|consignou|transcrevo|verbis|deu provimento|decidiu|registrou")
STF_MARCA = re.compile(r"ristf|regimento interno do supremo|publique-se|comunique-se|brasilia, ?\d|intime-se|intimem-se|arquive-se|ministro [a-z ]+ relator|e como voto|e o voto")


def stf_proprio(s, x):
    """No STF monocrático (o acervo traz trechos): o verbo é do próprio relator do STF, não de decisão transcrita."""
    i, g = x[0], x[2]
    depois = s[i + len(g):i + len(g) + 260]
    antes = s[max(0, i - 160):i]
    if QUOTE_DEPOIS.search(depois) or QUOTE_ANTES.search(antes):
        return False
    return bool(STF_MARCA.search(depois) or STF_MARCA.search(s[max(0, i - 300):i]) or len(depois) < 120)


def dispositivo(rg, classe, tipo=""):
    """(desfecho, janela, trecho): desfecho em oficio|parcial|concedida|denegada|indef|naoconh|negseg|prej|desprovido|provido|conflito.
    Monocrática: só vale o verbo na primeira pessoa (concedo, denego, nego provimento...); o particípio ("agravo desprovido",
    "ordem concedida") costuma ser de ementa transcrita."""
    for nome, s in rg["jan"]:
        a = achados(s)
        if tipo == "Monocrática" and a:
            m0 = LIMINAR.search(s)
            if m0 and m0.start() <= a[0][0] + 5:
                return "liminar", nome, s
            if INTERLOC.search(s[a[0][0]:a[0][0] + 220]) and a[0][1] in ("desprovido", "provido"):
                return "liminar", nome, s
        if tipo == "Monocrática" and rg.get("trib") == "STF":
            a = [x for x in a if stf_proprio(s, x)]
        if tipo == "Monocrática":
            a = [x for x in a if PRIMEIRA.search(s[max(0, x[0] - 70):x[0] + len(x[2])])]
        if not a:
            continue
        ks = [k for _, k, _ in a]
        if "oficio" in ks:
            return "oficio", nome, s
        prim = a[0][1]
        if re.match(r"(execucao penal|peticao)", sa(classe)) and {"provido", "desprovido"} <= set(ks):
            return "parcial", nome, s
        if prim in ("provido", "concedida") and any(k == "parcial" and x0 - a[0][0] < 30 for x0, k, _ in a):
            return "parcial", nome, s
        if prim == "naoconh" and any(k == "desprovido" and "conhecid" in g for _, k, g in a):
            return "desprovido", nome, s  # "parcialmente conhecido e improvido": houve mérito
        if prim in ("naoconh", "indef", "negseg", "prej"):
            # "não conheço do habeas corpus; contudo, concedo a ordem..." = ordem de ofício
            if "concedida" in ks:
                return "oficio", nome, s
            if "parcial" in ks and any(k == "parcial" and "conced" in g for _, k, g in a):
                return "oficio", nome, s
        return prim, nome, s
    return "", "", ""


# ------------------------------------------------------------------ quem recorreu
MP_NOME = r"(o |pelo |do |pela |a )?(ministerio publico|parquet|procuradoria[- ]geral (da republica|de justica)|mpf\b|mpe\b|mp\b|mpsp|mpmg|mprs|mpms|mppr|mpgo|mpsc|mprj|orgao ministerial|orgao acusador|representante ministerial|acusacao)"
RX_INTERP = re.compile(r"(interpost[oa]s?|manejad[oa]s?|opost[oa]s?|aviad[oa]s?|ajuizad[oa]|impetrad[oa])\s+(com fundamento[^,]{0,80},\s*)?(por|pel[oa]s?|em favor de)\s+(.{0,60})")
RX_MP = re.compile(r"recurso ministerial|(insurgencia|irresignacao|inconformismo|agravo regimental|agravo interno|recurso) do ministerio publico|regimental ministerial|impugnacao ministerial|agravo (regimental )?do parquet|recurso do parquet|irresignacao do parquet|insurgencia do parquet|concessao (da ordem )?de oficio mantida|ordem concedida mantida|manutencao da (ordem concedida|concessao)|mantida a (ordem concedida|concessao)|decisao concessiva mantida|insurgencia ministerial|pretensao ministerial|irresignacao ministerial|inconformismo ministerial|agravo ministerial|apelo ministerial|pleito ministerial|recurso do ministerio publico|recurso da acusacao|agravo (regimental |interno |em execucao (penal )?)?(interposto )?(do|pelo) ministerio publico|agravo regimental do mp|recurso especial do ministerio|recurso (especial|extraordinario) ministerial|o ministerio publico (do estado [a-z ]{3,30}|federal|estadual|do distrito federal[a-z ]{0,25})?,? ?(interpoe|interpos|agrava|recorre|recorreu|insurge|se insurge|agravou|maneja|pretende a reforma|pugna pela reforma|busca a reforma)|parquet (estadual |federal )?(interpoe|interpos|agrava|recorre|insurge|se insurge|pugna pela reforma)|recorrente: ministerio publico|agravante: ministerio publico|embargante: ministerio publico|ministerio publico (do estado [a-z ]{3,30}|federal)? ?(agravante|recorrente)\b")
RX_DEF = re.compile(r"recurso defensivo|insurgencia defensiva|pretensao defensiva|irresignacao defensiva|inconformismo defensivo|pleito defensivo|apelo defensivo|recurso da defesa|agravo (regimental |interno |em execucao (penal )?)?(interposto )?(da|pela) defesa|a defesa (interpoe|interpos|agrava|recorre|recorreu|insurge|se insurge|agravou|pretende|pugna|requer|sustenta|alega|busca)|a defensoria publica[a-z ]{0,40}(interpoe|interpos|agrava|recorre|insurge|se insurge|pretende|pugna|requer|sustenta|alega)|agravo interposto por [a-z]+ [a-z]+|defesa de [a-z]")
RX_DEC_AGRAV = re.compile(r"contra (a )?(r\. )?decisao (monocratica |agravada |singular |de primeiro grau |do juizo[^,;]{0,80}?|proferida[^,;]{0,80}?|da lavra[^,;]{0,60}?|por mim proferida,? |desta relatoria,? )?(que|a qual|na qual|em que)\s+((\S+\s+){0,11}\S+)")
FAV_VERB = re.compile(r"^(concedeu|deferiu|reconheceu (a remicao|o direito|a prescricao|a extincao)|homologou (a )?remi|declarou (remidos|extinta)|julgou extinta|absolveu|afastou (a falta|a regressao)|determinou a (progressao|retificacao)|indeferiu a regressao|rejeitou a|nao reconheceu a falta|deixou de (homologar|reconhecer|regredir)|deu provimento ao (habeas|agravo em execucao interposto pela defesa)|concedeu a ordem|concedeu o)")
DESF_VERB = re.compile(r"^(indeferiu|negou|denegou|nao conheceu|reconheceu a (pratica de )?falta|homologou (a )?falta|homologou o (pad|procedimento)|determinou a regressao|regrediu|revogou|cassou|julgou improcedente|manteve|deu provimento ao recurso (especial )?(do|interposto pelo) ministerio|nao concedeu|declarou a perda|interrompeu|indeferiu liminarmente|julgou prejudicado)")

RX_PED_DEF = re.compile(r"(pedido|pleito|pretensao|requerimento|postulacao|busca|almeja|pugna|requer|pretende)( defensiv[oa])? (de |da |do |pela |pelo |o |a )?(concessao|deferimento|reconhecimento|progressao|remicao|livramento|indulto|comutacao|saida|afastamento|absolvicao|desconsideracao|retificacao|prisao domiciliar|trabalho externo|extincao|unificacao|detracao|nulidade|exclusao da falta|revogacao da regressao|cassacao da decisao que (indeferiu|negou|reconheceu|homologou|determinou a regressao|regrediu))")
RX_PED_MP = re.compile(r"(pedido|pleito|pretensao|requerimento|busca|almeja|pugna|requer|pretende)( ministerial)? (de |da |do |pela |pelo |o |a )?(cassacao|reforma|revogacao|anulacao|afastamento) (da |do )?(decisao|beneficio|progressao|remicao|livramento|saida|indulto|comutacao|prisao domiciliar)[^.;]{0,40}?(que )?(concedeu|deferiu|concedid|deferid|homologou a remi|reconheceu a remi|declarou)?")


def polaridade_pedido(z):
    """Quem pediu, pelo que se pede: concessão/reconhecimento de benefício = defesa; cassação/reforma do benefício = MP."""
    a = RX_PED_MP.search(z)
    b = RX_PED_DEF.search(z)
    if a and (a.group(4) in ("cassacao", "revogacao", "anulacao") or a.group(7)) and not (b and b.start() < a.start()):
        return "mp"
    if b:
        return "defesa"
    return ""


POL_POS = re.compile(r"\bpossibilidade\b|requisitos? (objetivos? |subjetivos? |legais )?(preenchid|atendid|cumprid)|preenchimento dos requisitos|\bcabimento\b|bis in idem|irretroatividade|necessidade de fundamentacao|desnecessidade|ilegalidade|inaplicabilidade|irrelevancia|nao acolhimento|direito (a|ao) (remicao|progressao|beneficio|livramento|indulto|comutacao)|reconhecimento do direito|benesse devida|beneficio devido|remicao devida|cabivel a (remicao|progressao|concessao)|decisao concessiva|ausencia de fundamentacao|fundamentacao inidonea|nulidade (do pad|da decisao|do procedimento)|prescricao (da falta|reconhecida|configurada)|afastamento da falta|absolvicao|atipicidade|in bonam partem|analogia|mais benefica|retroatividade da lei mais|desproporcional")
POL_NEG = re.compile(r"impossibilidade|inviabilidade|inadmissibilidade|\bnao cabimento|incabivel|descabimento|vedacao|ausencia (do|de|dos) requisitos?|requisitos? (objetivos? |subjetivos? )?nao (preenchid|atendid|cumprid|satisfeit)|nao preenchimento|indeferimento mantido|falta grave (configurada|caracterizada|reconhecida|mantida|comprovada)|regressao (mantida|cabivel|devida|que se impoe)|que se impoe|necessidade (de|do) exame|exame criminologico (desfavoravel|necessario)|improcedencia|nao demonstrad|nao comprovad|legalidade da decisao|decisao fundamentada|fundamentacao idonea|perda dos dias|pretendid[oa]|almejad[oa]|nao acolhid|tese (rejeitada|afastada|nao acolhida)|nao configurad")


POS_F = re.compile(r"irretroativ|impossibilidade de aplicacao retroativa|novatio legis in pejus|in bon(am|a) partem|(?<!ausencia de )(?<!inexistencia de )(?<!inocorrencia de )(?<!alegacao de )(?<!tese de )bis in idem(?! nao)|nao vincula o magistrado|requisitos (objetivos? e subjetivos? |legais )?(preenchidos|atendidos|cumpridos)|requisito subjetivo (preenchido|atendido|demonstrado)|beneficio devido|direito (a|ao) (remicao|progressao|beneficio)")
NEG_F = re.compile(r"impossibilidade(?! de aplicacao retroativa)|inviabilidade|ausencia d[oe]s? requisito|(nao|nao foram|nao foi) (preenchid|atendid|implementad|demonstrad)|requisito subjetivo nao|indeferimento mantido|falta grave (configurada|caracterizada|reconhecida|mantida|demonstrada)|regressao (mantida|cabivel|que se impoe)|perda d[eo]s? .{0,12}dias remidos|(ausencia|inexistencia|inocorrencia) de bis in idem|descabid|nao configurad|reincidencia especifica|desnecessidade de identidade|necessidade de (exame|avaliacao|realizacao)|incabivel|vedacao|nao cabimento")


def pol_forte(cap):
    s = re.split(r"recurso (conhecido e )?(nao provido|desprovido|improvido|provido)|agravo (conhecido e )?(nao provido|desprovido|improvido|provido)|nao provimento|\bprovimento\b|i\. caso em exame", cap)[0]
    return 1 if (POS_F.search(s) and not NEG_F.search(s)) else 0


def polaridade_resultado(cap):
    """+1 se a ementa descreve resultado bom para o apenado, -1 se ruim, 0 se não dá para dizer."""
    s = re.split(r"recurso (conhecido e )?(nao provido|desprovido|improvido|provido)|agravo (conhecido e )?(nao provido|desprovido|improvido|provido)|nao provimento|\bprovimento\b", cap)[0]
    p = len(POL_POS.findall(s))
    n = len(POL_NEG.findall(s))
    if p > n:
        return 1
    if n > p:
        return -1
    return 0


DEF_SEMPRE = re.compile(r"^(habeas corpus|recurso em habeas corpus|recurso ordinario|embargos infringentes|revisao criminal|recurso ordinario em habeas corpus|rhc)", re.I)


def parte(rg, classe, tipo, desf=""):
    """'defesa' | 'mp' | 'ambos' | '' (não determinado) e a pista usada."""
    c = sa(classe)
    if DEF_SEMPRE.search(c):
        return "defesa", "classe"
    ini = rg["ini"]
    cap = rg["cap"]
    zona = cap[:900] + " || " + ini
    if rg.get("trib") == "TJMS":
        zona = cap[:900] + " || " + ini[:min(1600, len(cap) + 450)]  # no TJMS, o recorrente vem na ementa e no "caso em exame"
    if re.search(r"(agravo|recurso)[^.]{0,60}contra (a )?decisao (monocratica )?que julgou procedente (a )?reclamacao (ajuizada|proposta|formalizada) pelo ministerio publico", zona):
        return "defesa", "recl_mp"
    if re.search(r"(negou seguimento|julgou improcedente)[^.]{0,20}reclamacao (formalizada |ajuizada |proposta )?contra (decisao|acordao)[^.]{0,40}que (dispensou|afastou a (necessidade|exigencia)|concedeu|deferiu)", zona):
        return "mp", "recl_mp"
    # 1) primeira menção "interposto por/pelo X"
    m = None
    for mm in RX_INTERP.finditer(ini[:1400]):
        quem = mm.group(4)
        if re.match(r"(o |a )?(r\. )?(decisao|acordao|juizo|tribunal)", quem):
            continue
        m = mm
        break
    if m:
        quem = m.group(3) + " " + m.group(4)
        if re.match(r"(por|pel[oa]s?|em favor de)\s+" + MP_NOME, quem):
            return "mp", "interposto"
        if re.match(r"(pel[oa]s?)\s+(defesa|defensoria|defensor)", quem) or re.match(r"(por|em favor de)\s+[a-z]", quem):
            # "interposto por X e pelo Ministério Público" ou nome de pessoa
            if re.search(MP_NOME + r"\b", quem[:60]) and re.search(r"\be (pelo|o) ministerio", quem):
                return "ambos", "interposto"
            return "defesa", "interposto"
    if not re.match(r"(agravo de execucao|embargos de declaracao criminal|agravo interno criminal|cautelar)", c):
        # no STJ/STF, "agravo em execução do MP" e a ementa de origem transcrita são do processo anterior
        zona = re.sub(r"(agravo (em|de) execucao|apelacao|recurso em sentido estrito)( penal)?[^.;]{0,40}?(interposto |manejado |aviado )?(pelo|do|da) (ministerio publico|parquet|acusacao)", " ", zona)
        zona = re.sub(r"assim ementado.{0,700}", " ", zona)
    if re.match(r"(agravo de execucao|agravo interno criminal|cautelar)", c) and re.search(r"(atribuir|atribuicao de|concessao de|conceder) efeito suspensivo (ao|a) agravo", zona):
        return "mp", "efeito_suspensivo"
    mp = RX_MP.search(zona)
    df = RX_DEF.search(zona)
    if mp and df:
        return ("mp" if mp.start() < df.start() else "defesa"), "pista_ordem"
    if mp:
        return "mp", "pista"
    if df:
        return "defesa", "pista"
    # 3) polaridade da decisão agravada/recorrida
    m = RX_DEC_AGRAV.search(zona)
    if m and not re.search(r",? mas |, porem|, contudo", m.group(5)):
        v = m.group(5)
        if re.search(r"\be (concedeu|deferiu) (a|o|ao)", v):
            return "mp", "decisao_agravada"
        if FAV_VERB.search(v):
            return "mp", "decisao_agravada"
        if DESF_VERB.search(v):
            return "defesa", "decisao_agravada"
    if re.search(r"\bo agravado\b|\ba agravada\b|\bo recorrido\b|\ba recorrida\b|\bdo agravado\b|\bao agravado\b|\bdo recorrido\b|\bao recorrido\b", zona) and not re.search(r"\bo agravante\b|\bdo agravante\b|\bao agravante\b|\bo recorrente\b|\bdo recorrente\b|\bo paciente\b", zona[:600]):
        return "mp", "agravado"
    p = polaridade_pedido(zona)
    if p:
        return p, "pedido"
    if re.search(r"^(agravo interno|agravo regimental)", c):
        return "defesa", "padrao_agrg"
    # TJMS: o recurso do MP vem nomeado na ementa ("recurso ministerial"); sem essa marca, o agravo é da defesa
    if re.search(r"^(agravo de execucao penal|embargos de declaracao criminal|agravo interno criminal)", c):
        if re.search(r"(?<!parecer )(?<!manifestacao )(?<!opiniao )ministerial|execucao( penal)? (-|–)? ?ministerio publico|^(ementa: )?(e m e n t a )?(- )?agravo (em|de) execucao( penal)? (do )?ministerio publico", cap[:300]):
            return "mp", "cab_mp"
        pol = pol_forte(cap or ini[:700])  # só teses inequivocamente pró-apenado (a polaridade ampla errou 4 de 5 na 1a amostra)
        if pol > 0 and desf == "desprovido":
            # o resultado descrito na ementa é bom (pol>0) ou ruim para o apenado; com o desfecho, diz quem recorreu
            return ("defesa" if (pol > 0) == (desf == "provido") else "mp"), "polaridade"
        return "defesa", "padrao_tjms"
    if re.search(r"^(reclamacao|execucao penal|peticao)", c):
        return "defesa", "padrao_classe"
    return "", ""


# ------------------------------------------------------------------ sentido
ROT = {
    ("defesa", "oficio"): ("favoravel", "Ordem concedida de ofício"),
    ("mp", "oficio"): ("favoravel", "Ordem concedida de ofício"),
    ("ambos", "oficio"): ("favoravel", "Ordem concedida de ofício"),
}


PARA_FAV = re.compile(r"\bpara,?\s*(de oficio,? )?(conceder|restabelecer a (r\. )?decisao (de primeiro grau |do juizo[^,;]{0,60}?|singular )?que (concedeu|deferiu|reconheceu|homologou a remi|declarou|julgou extinta)|negar provimento ao (recurso especial|agravo|recurso)[^.;]{0,30}?(do|interposto pelo) (ministerio|parquet)|nao conhecer do (recurso especial|agravo|recurso)[^.;]{0,30}?(do|interposto pelo) (ministerio|parquet)|afastar a (falta|regressao|necessidade|exigencia|interrupcao)|reconhecer (o direito|a remicao|a prescricao|a extincao)|determinar (a retificacao|a progressao)|absolver|declarar (remidos|extinta)|deferir|julgar extinta)")
PARA_DESF = re.compile(r"\bpara,?\s*(denegar|cassar a (ordem|decisao (monocratica|agravada|que concedeu))|nao conhecer do habeas|nao conhecer da impetracao|restabelecer o (v\. )?acordao|restabelecer a decisao (que (indeferiu|negou|reconheceu a falta|homologou a falta|determinou a regressao))|dar provimento ao recurso (especial )?(do|interposto pelo) (ministerio|parquet)|reconhecer a (pratica|falta)|determinar a regressao|afastar a remicao|indeferir|julgar improcedente)")
CAP_DEF_GANHOU = re.compile(r"(?<!nao )preenche os requisitos|(?<!nao )preenchidos os requisitos|novatio legis in pejus|fundamentacao inidonea|irretroatividade|in bonam partem|(ordem|habeas corpus|writ) (de oficio )?(concedid[oa]|deferid)|concessao (da ordem|do habeas corpus|de oficio)|(?<!ausencia de )(?<!inexistencia de )(?<!nao ha )constrangimento ilegal (evidenciado|configurado|caracterizado|demonstrado|reconhecido)|(?<!ausencia de )(?<!inexistencia de )flagrante ilegalidade (evidenciada|configurada|caracterizada|reconhecida)|ilegalidade (evidenciada|configurada|caracterizada|reconhecida)")
CAP_DEF_PERDEU = re.compile(r"nao preenchimento|requisito subjetivo nao|ausencia d[oe]s? requisito|fundamentacao (adequada|idonea)|devidamente fundamentad|\bdescabimento\b|(ausencia|inexistencia) de (constrangimento|ilegalidade|flagrante)|constrangimento ilegal (nao|inexistente)|ilegalidade (nao|inexistente)|(ordem|habeas corpus|writ) (denegad|nao conhecid)|decisao (agravada )?mantida por seus proprios")


def sentido(classe, part, desf, rg, trecho="", pista=""):
    c = sa(classe)
    if c.startswith("embargos de declaracao"):
        return "", "Embargos de declaração (sentido não apurado)"
    agrg = bool(re.match(r"(agravo interno|agravo regimental)", c))
    if desf in ("provido", "parcial") and trecho:
        m = re.search(r"(provid\w*|provimento)[^.;]{0,90}?(\bpara\b.{0,200})", trecho)
        if m and not re.match(r"(habeas corpus|recurso em habeas|recurso ordinario|rhc)", c):
            if PARA_FAV.match(m.group(2)):
                return ("favoravel" if desf == "provido" else "parcial"), ("Recurso provido" if pista not in ("classe",) else "Recurso da defesa provido") + " (favorável à defesa)"
            if PARA_DESF.match(m.group(2)):
                return ("desfavoravel" if desf == "provido" else "parcial"), "Recurso provido (desfavorável à defesa)"
    if agrg and pista in ("padrao_agrg", "pedido", "decisao_agravada", "agravado") and desf in ("desprovido", "provido"):
        cap = rg["cap"] or rg["ini"][:700]
        cap = re.split(r"(agravo (regimental|interno)|recurso) (conhecido e )?(des|im|nao )?provido|\bi\. caso em exame", cap)[0]
        g, p = bool(CAP_DEF_GANHOU.search(cap)), bool(CAP_DEF_PERDEU.search(cap))
        if g and not p:
            return "favoravel", "Favorável à defesa (agravo %s)" % ("desprovido" if desf == "desprovido" else "provido")
        if p and not g:
            return "desfavoravel", "Desfavorável à defesa (agravo %s)" % ("desprovido" if desf == "desprovido" else "provido")
    hc = bool(re.match(r"(habeas corpus|recurso em habeas|recurso ordinario|rhc)", c))
    rec_hc = "recurso" in c and hc
    recl = c.startswith("reclamacao")
    emb = c.startswith("embargos de declaracao")
    if desf == "conflito" or c.startswith("conflito"):
        return "", "Conflito de competência"
    if desf == "liminar":
        return "", "Decisão liminar ou interlocutória"
    if desf == "oficio":
        return "favoravel", "Ordem concedida de ofício"
    if not desf:
        return "", "Dispositivo não identificado"
    if desf in ("naoconh", "indef", "negseg", "prej"):
        rot = {"naoconh": "não conhecido", "indef": "indeferido liminarmente", "negseg": "seguimento negado", "prej": "prejudicado"}[desf]
        if hc and not rec_hc:
            return "nao_conhecido", "Habeas corpus " + rot
        if part == "mp":
            return "nao_conhecido", "Recurso do MP " + rot
        if part == "defesa":
            return "nao_conhecido", ("Reclamação " if recl else "Recurso da defesa ") + rot
        return "nao_conhecido", "Não conhecido"
    if part not in ("defesa", "mp"):
        return "", "Recorrente não identificado"
    if hc and not rec_hc:
        m = {"concedida": ("favoravel", "Ordem concedida"), "provido": ("favoravel", "Ordem concedida"), "parcial": ("parcial", "Ordem parcialmente concedida"),
             "denegada": ("desfavoravel", "Ordem denegada"), "desprovido": ("desfavoravel", "Ordem denegada")}
        return m.get(desf, ("", "?"))
    if recl and desf in ("provido", "parcial") and re.search(r"cassar (o|a) (ato|decisao|acordao) reclamad[oa],? \(?(hc|rhc|agrg|resp)\b|restabelecer (o|a) (acordao|decisao|determinacao) (proferid[oa] )?(pel[oa] )?(tribunal de justica|tj[a-z]{2}\b|sexta camara|[a-z]+ camara)", trecho or ""):
        part = "mp"  # reclamação contra HC do STJ, para restabelecer o acórdão do TJ: quem reclama é o MP
    if recl:
        m = {"provido": ("favoravel", "Reclamação procedente"), "concedida": ("favoravel", "Reclamação procedente"), "parcial": ("parcial", "Reclamação parcialmente procedente"),
             "desprovido": ("desfavoravel", "Reclamação improcedente"), "denegada": ("desfavoravel", "Reclamação improcedente")}
        r = m.get(desf, ("", "?"))
        if part == "mp" and r[0]:
            r = ({"favoravel": "desfavoravel", "desfavoravel": "favoravel"}.get(r[0], r[0]), r[1].replace("Reclamação", "Reclamação do MP"))
        return r
    quem = "da defesa" if part == "defesa" else "do MP"
    nome = "Embargos " if emb else "Recurso "
    if desf in ("provido", "concedida"):
        if rec_hc:
            return "favoravel", "Recurso da defesa provido"
        return ("favoravel" if part == "defesa" else "desfavoravel"), nome + quem + (" acolhidos" if emb else " provido")
    if desf == "parcial":
        return "parcial", nome + quem + (" parcialmente acolhidos" if emb else " parcialmente provido")
    if desf in ("desprovido", "denegada"):
        return ("desfavoravel" if part == "defesa" else "favoravel"), nome + quem + (" rejeitados" if emb else " desprovido")
    return "", "?"


# ------------------------------------------------------------------ escopo
EX = [(3, r"agravo (em|de) execucao|juizo (da|das) execuc|vara (de|das) execuc|juizo executorio|juizo da vep|\bvep\b|\bvec\b|execucao penal|execucao da pena|\bseeu\b"),
      (3, r"progressao (de regime|prisional|para o regime|ao regime)|progressao|livramento condicional|remicao|remir|dias remidos|falta grave|falta disciplinar|infracao disciplinar|procedimento administrativo disciplinar|\bpad\b|indulto|comutacao|saida temporaria|saidas temporarias|regressao (de|cautelar|ao|para)|regressao|exame criminologico|trabalho externo|data-base|data base|pretensao executoria|prescricao executoria|unificacao (de|das) penas|unificacao|soma das penas|calculo (de|da) pena|calculo de liquidacao|atestado de pena|guia de (recolhimento|execucao)|sumula vinculante (n. )?56|medida de seguranca|estabelecimento penal|casa de albergado|monitora(cao|mento) eletronic|tornozeleira|harmonizacao|visita (intima|de familiares|ao preso)|direito de visita|transferencia (do preso|de presidio|para presidio|de estabelecimento|para estabelecimento|para unidade)|recambiamento|prisao domiciliar humanitaria|regime disciplinar diferenciado|\brdd\b|lei 7\.210|lei n\. 7\.210|lei de execucao|\blep\b"),
      (1, r"apenad[oa]|reeducand[oa]|sentenciad[oa]|executad[oa]\b|cumprimento (da|de) pena|regime (semiaberto|aberto)|prisao domiciliar|pena de multa|extincao da punibilidade|detracao")]
AP = [(1, r"maus antecedentes|confissao|qualificadora|continuidade delitiva|concurso (material|formal)|acao penal|investigacao|reincidencia (como )?agravante|condenacao (pela|por)"),
      (3, r"prisao preventiva|preventiva|custodia cautelar|segregacao cautelar|prisao cautelar|prisao em flagrante|flagrante|medidas cautelares (diversas|alternativas)|art\. 312|garantia da ordem publica|dosimetria|pena-base|pena base|primeira fase|terceira fase|causa de diminuicao|trafico privilegiado|minorante|regime inicial|regime prisional inicial|fixacao do regime|absolvicao|absolver|desclassificacao|pronuncia|tribunal do juri|trancamento|denuncia|inepcia|justa causa|busca (e apreensao|domiciliar|pessoal|veicular)|ilicitude d[ao]s? prova|provas? ilicit|reconhecimento (pessoal|fotografico)|cadeia de custodia|nao persecucao|\banpp\b|prescricao da pretensao punitiva|prescricao retroativa|instrucao criminal|audiencia de custodia|interceptacao|autoria e materialidade|in dubio pro reo|excesso de prazo|liberdade provisoria|fianca|revogacao da prisao|sentenca condenatoria recorrivel|direito de recorrer em liberdade|recorrer em liberdade|tipicidade|atipicidade|insignificancia|nulidade (da|do) (sentenca|processo|interrogatorio|acordao condenatorio|julgamento)|cerceamento de defesa|competencia (da justica|do juizo) (federal|estadual|militar|eleitoral)|inquerito policial|medidas protetivas|sursis processual|suspensao condicional do processo|transacao penal|substituicao da pena privativa|perdimento|sequestro de bens|lavagem")]
EXR = [(w, re.compile(x)) for w, x in EX]
APR = [(w, re.compile(x)) for w, x in AP]
FORA_CLASSE = re.compile(r"^(apelacao|revisao criminal|acao penal|inquerito|apelacao civel|agravo de instrumento|embargos de declaracao civel|agravo interno civel|conflito de competencia civel|mandado de seguranca civel|acao direta|adi|recurso inominado|procedimento|remessa|cumprimento de sentenca|acao civil|tutela|suspensao de liminar|incidente|queixa|extradicao|habeas data|mandado de injuncao|cautelar inominada civel)")


def pontos(s, R):
    tot = 0
    hits = set()
    for w, rx in R:
        for m in rx.finditer(s):
            if m.group(0) not in hits:
                hits.add(m.group(0))
                tot += w
    return tot, hits


def escopo(r, rg):
    """(no_escopo, motivo)."""
    trib, tipo, classe, orgao = r[1], r[2], sa(r[4]), sa(r[6])
    if "civel" in orgao or "civel" in classe:
        return False, "cível"
    if FORA_CLASSE.search(classe) and not re.search(r"execucao penal", classe):
        if classe.startswith("apelacao") and re.search(r"agravo (em|de) execucao|recebid[oa] como agravo", rg["t"][:900]):
            pass
        else:
            return False, "classe " + classe
    if classe.startswith("embargos infringentes") and re.search(r"em apelacao", rg["t"][:200]):
        return False, "embargos em apelação"
    if "agravo de execucao" in classe or "agravo em execucao" in classe or classe.startswith("execucao penal"):
        return True, "classe execução"
    foco = (rg["cap"] + " " + rg["ini"][:1300]) if rg["cap"] else rg["ini"][:1600]
    if trib == "STF" and tipo == "Monocrática":
        foco = rg["t"][:1500]
    e, eh = pontos(foco, EXR)
    a, ah = pontos(foco, APR)
    # detração na sentença (art. 387, § 2º, do CPP) é da ação penal
    if re.search(r"387,? (§|par|2)", foco):
        a += 3
    if e >= 3 and e >= a + 2:
        return True, "pontos %d x %d" % (e, a)
    if e >= 6 and e >= a:
        return True, "pontos %d x %d" % (e, a)
    return False, "pontos %d x %d" % (e, a)


# ------------------------------------------------------------------ temas (mesmo vocabulário da aba)
TEMAS = [
    ("Progressão de regime", r"progressao|progredir|regime (mais brando|intermediario)|requisito objetivo|lapso temporal|requisito subjetivo|progressao per saltum"),
    ("Falta grave e PAD", r"falta grave|falta disciplinar|faltas? (media|leve)|infracao disciplinar|procedimento administrativo disciplinar|\bpad\b|sindicancia|art\. 50|art\. 52 da|celular|aparelho telefonico|evasao|fuga|audiencia de justificacao"),
    ("Hediondos e frações", r"hediond|equiparad|fracao|fracoes|percentua|reincidencia especifica|reincidente especifico|art\. 112, (v|vi|vii|viii|i|ii|iii|iv)\b|lei (n\. )?13\.964|pacote anticrime|\b40%|\b60%|\b50%|\b70%|2/5|3/5|1/6|trafico privilegiado"),
    ("Exame criminológico", r"criminologic|psicossocial|exame psicologico|parecer psicologico"),
    ("Remição", r"remicao|remir|remido|remidos|remissao da pena"),
    ("Livramento condicional", r"livramento condicional|livramento"),
    ("Competência e processamento", r"competencia (do juizo|da vara|para|territorial|da justica)|conflito (negativo |positivo )?de competencia|juizo competente|deprecad|transferencia (do preso |do apenado |da execucao |do reeducando )?(de|para) (outr|presidio|estabelecimento|unidade|comarca|penitenciaria)|recambiamento|juizo natural|redistribuicao|execucao (penal )?(unica|em outro|de outro estado)|guia de (recolhimento|execucao)|reformatio in pejus|intimacao (pessoal )?d[ao] (defensor|defensoria|apenado)|oitiva previa|audiencia de justificacao|competente|supressao de instancia"),
    ("Regime aberto e condições", r"regime aberto|condicoes (especiais|do regime aberto)|condicao especial|sumula (n. )?493|casa de albergado|recolhimento noturno|prisao albergue"),
    ("Prisão domiciliar", r"prisao domiciliar|domiciliar"),
    ("Indulto e comutação", r"indulto|comutacao|decreto (presidencial|natalino)|decreto (n\. )?\d{1,2}\.\d{3}"),
    ("Saída temporária", r"saida temporaria|saidas temporarias|saidinha|visita periodica ao lar|saida (temporaria )?automatizada"),
    ("Saúde e condições prisionais", r"saude|tratamento medico|doenca|enfermidade|superlotacao|condicoes (carcerarias|degradantes|desumanas)|sumula vinculante (n. )?56|falta de vagas|ausencia de vagas|inexistencia de vagas|deficit de vagas|vaga em estabelecimento|direito de visita|visita|gestante|filhos menores|lactante|deficiencia|tratamento desumano|estabelecimento adequado"),
    ("Data-base", r"data-base|data base|marco (inicial|interruptivo)|termo inicial|interrupcao do prazo|ultima prisao|reinicio da contagem|nova data"),
    ("Unificação e soma de penas", r"unificacao|unificad|soma (das|de) penas|somatorio|art\. 111|art\. 75|limite (maximo )?de (30|40|trinta|quarenta)|nova condenacao|condenacao superveniente"),
    ("Regressão de regime", r"regressao|regredi"),
    ("Detração", r"detracao|art\. 42 do (cp|codigo penal)"),
    ("Pena de multa", r"pena de multa|multa"),
    ("Monitoração eletrônica", r"monitora(cao|mento) eletronic|tornozeleira|monitoramento"),
    ("Penas restritivas de direitos", r"restritivas? de direitos?|prestacao de servicos|prestacao pecuniaria|limitacao de fim de semana|conversao da pena restritiva|reconversao"),
    ("Extinção da pena", r"extincao da (pena|punibilidade)|extinta a punibilidade|extinguir a punibilidade|cumprimento integral|integral cumprimento|declarar extinta"),
    ("Prescrição", r"prescri"),
    ("Trabalho externo", r"trabalho externo|trabalho extramuros|servico externo"),
    ("Medida de segurança", r"medida de seguranca|internacao|tratamento ambulatorial|inimputa|semi-imputa|desinternacao|hospital de custodia"),
    ("Execução provisória", r"execucao provisoria|guia (de recolhimento )?provisoria|execucao antecipada|cumprimento antecipado"),
]
TEMR = [(t, re.compile(x)) for t, x in TEMAS]


def temas(rg):
    s = (rg["cap"] or "") + " " + rg["ini"][:1200]
    if not rg["cap"]:
        s = rg["ini"][:1600]
    s = s + " " + (rg["jan"][0][1] if rg["jan"] else "")
    out = [t for t, rx in TEMR if rx.search(s)]
    # "Hediondos e frações" sozinho a partir de percentuais genéricos: exige ao menos progressão/livramento/hediondez
    if "Hediondos e frações" in out and not re.search(r"hediond|equiparad|reincidencia especifica|pacote anticrime|13\.964|art\. 112|progress|livramento", s):
        out.remove("Hediondos e frações")
    if "Pena de multa" in out and not re.search(r"pena de multa|multa (e|como|nao|pendente|inadimplid|impaga)|inadimplemento da multa|pagamento da multa|dias-multa", s):
        out.remove("Pena de multa")
    return out[:4] or ["Outros"]


DISP_AP = re.compile(r"redutor|reduzir a(s)? pena|redimensionar a pena|readequar a pena|nova dosimetria|dosimetria|pena-base|regime inicial|fixar o regime (inicial )?(aberto|semiaberto)|estabelecer o regime (inicial )?(aberto|semiaberto)|substituir a pena privativa|substituicao da pena (privativa|corporal)|substituir a pena corporal|por duas restritivas|converter a pena privativa de liberdade (do paciente )?(por|em) (duas )?restritivas|desclassific|absolver|absolvicao|trancar|trancamento|revogar a prisao preventiva|prisao preventiva|liberdade provisoria|art\. 387|restabelecer a reprimenda|reconhecer a minorante|erro material da sentenca|torna-la definitiva|como inicio do cumprimento|regime semiaberto como inicio|regime aberto como inicio|exasperacao|restabelecer a sentenca|revogacao das medidas cautelares|art\. 282 do codigo de processo penal|trafico privilegiado|anular a sentenca|anular o processo|nulidade da sentenca|nova sentenca|novo julgamento")


def escopo_disp(trecho):
    """Dispositivo que mexe na pena da sentença, no regime inicial, na prisão cautelar ou na condenação: ação penal."""
    return bool(DISP_AP.search(trecho[:320]))
