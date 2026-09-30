# -*- coding: utf-8 -*-
"""
Prescrição, crime a crime, a partir dos dados do RSPE (arts. 109 a 119 do CP).

Pretensão punitiva (retroativa e intercorrente) - art. 110, § 1º:
  prazo pela pena aplicada (art. 109), reduzido de metade se < 21 anos no fato ou > 70 na
  sentença (art. 115); intervalos: fato-denúncia (só para fatos até 05/05/2010 - Lei 12.234/2010, DOU e vigência em
  06/05/2010), denúncia-sentença e sentença-trânsito. O acórdão confirmatório também
  interrompe (art. 117, IV; STF HC 176.473), mas o RSPE não traz sua data - anotado.
Pretensão executória - art. 110, caput:
  prazo pela pena aplicada, +1/3 se reincidente, metade pelo art. 115; termo inicial no
  trânsito em julgado para ambas as partes (STF, Tema 788), ou para a acusação (art. 112, I)
  quando esse trânsito é anterior a 12/11/2020 (modulação). Cada período dos eventos do RSPE é
  classificado em relação ao crime: custódia anterior ao termo = prisão provisória (detração, CP, art. 42),
  só informativa - não reduz a pena nem o prazo (STJ, AgRg no HC 967.565; RHC 67.403; HC 400.704);
  custódia a partir do termo = cumprimento da pena unificada (LEP, art. 111), interrompe (art. 117, V),
  inclusive flagrante/preventiva cujo campo "Processos" inclui este processo (também no formato curto do
  SEEU) ou não indica processo; prisão provisória registrada só para OUTRO processo, iniciada depois do
  termo = prisão por outro motivo: suspende (art. 116, p. único), não conta como cumprimento (nota: se
  convertida em cumprimento, interrompe - conferir). Livramento concedido conta como cumprimento.
  Intervalo sem custódia após o termo: evasão (fuga, abandono, revogação do livramento; motivo ausente =
  evasão com aviso) -> prazo pelo saldo da pena (art. 113); soltura sem culpa ou sem início do cumprimento
  -> prazo pela pena aplicada (STJ, RHC 67.403).
  Saldo na evasão: uma condenação só -> pena menos o cumprido desde o termo (ou a pena remanescente do RSPE
  no trecho em aberto); várias condenações unificadas -> o RSPE não informa a imputação do tempo cumprido:
  saldo mínimo (este crime imputado primeiro) e saldo máximo (imputado por último, depois das outras
  condenações com trânsito anterior à evasão), com as hipóteses do art. 76 (mais grave primeiro; STJ, RHC
  9.158) e da ordem cronológica do trânsito (STJ, HC 627.646) como referência. O prazo (art. 109 sobre o
  saldo, +1/3, metade) é testado em cada faixa do art. 109 atravessada por [saldo_min, saldo_max]; a
  data-limite soma os dias de suspensão. Todas as faixas prescritas -> aparente (data mais tardia); nenhuma
  -> não prescrita; divergentes -> "A VERIFICAR" com a lista do que falta. Cada crime pelo seu saldo (art.
  119; STJ, AgRg no REsp 2.256.555, RHC 35.425, HC 261.866). Não existe resultado "pena cumprida por
  detração": a detração que cobre a pena do processo é aviso na memória e hipótese a verificar na Extinção.
Penas mais leves prescrevem com as mais graves (art. 118); cada crime isoladamente (art. 119).
"""

from datetime import date, timedelta
import copy
import re
from fractions import Fraction

import rspe_scraper as rs
import rspe_regras as rg


def prazo_base_anos(pena_dias, data_fato=None):
    """Art. 109 pela pena (aplicada), em anos (tabela da base jurídica), pela redação vigente na data do fato
    (inciso VI: 2 anos para fatos anteriores à Lei 12.234/2010)."""
    return rg.prazo_art109_anos(pena_dias, data_fato)


IMINENTE_DIAS = 180  # prescrição executória correndo: destacar quando faltar até isto


def periodos_cumprimento(r, hoje, extras_out=None):
    """Períodos em que a pena esteve em cumprimento (custódia, regime aberto, livramento condicional):
    a prescrição executória não corre nesses períodos (arts. 116, p. ú., e 117, V, CP).
    Devolve (periodos, avisos). extras_out (lista) recebe só os períodos de livramento e os inferidos, sem a custódia."""
    avisos = []
    eventos = r.get("_eventos", [])
    incidentes = r.get("_incidentes", [])
    per = list(rs.periodos_custodia(eventos))
    # livramento condicional concedido conta como cumprimento (período de prova) até a revogação ou suspensão decidida
    extras = rs.periodos_livramento(eventos, incidentes)
    per += extras
    # RSPE diz "em cumprimento" (último evento não é interrupção) mas não há período aberto: abre a partir da última alteração de regime
    em_cumpr = "INTERROMPIDA" not in (r.get("situacao_cumprimento") or "")
    if em_cumpr and not any(f is None for _, f in per):
        datas = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in incidentes if "REGIME" in (i.get("tipo") or "").upper()]
        datas = [x for x in datas if x]
        ini = max(datas) if datas else None
        if ini:
            per.append((ini, None))
            extras.append((ini, None))
            avisos.append("cumprimento em curso inferido a partir de %s (última alteração de regime); RSPE sem evento de início correspondente" % rs.fmt(ini))
    # normaliza e funde sobreposições
    per = sorted([(a, b) for a, b in per if a], key=lambda x: x[0])
    fund = []
    for a, b in per:
        if fund and (fund[-1][1] is None or a <= fund[-1][1]):
            pa, pb = fund[-1]
            fund[-1] = (pa, None if (pb is None or b is None) else max(pb, b))
        else:
            fund.append((a, b))
    if extras_out is not None:
        extras_out.extend(extras)
    return fund, avisos


def _desde(g0, termo, cumprido):
    """Início da contagem, em linguagem simples."""
    if not cumprido and g0 == termo:
        return "Conta do trânsito em julgado (%s), sem início do cumprimento" % rs.fmt(g0)
    return "Cumprimento parado desde %s" % rs.fmt(g0)


def _mods(L):
    """'(+1/3 reincidência)', '(½ art. 115)' do prazo, se houver."""
    m = re.findall(r"\(([^)]*)\)", L.get("prazo_ppe") or "")
    return (" (%s)" % "; ".join(m)) if m else ""


def soma_meses(d, meses):
    meses = int(meses)
    y, m = divmod(d.month - 1 + meses, 12)
    y += d.year
    m += 1
    dia = min(d.day, [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, dia)


def ultimo_dia(d, meses):
    """Último dia do prazo prescricional iniciado em d: o dia do começo se inclui no cômputo, pelo calendário comum (CP,
    art. 10). Ex.: 4 anos a partir de 10/03/2017 terminam em 09/03/2021; a prescrição está consumada no dia seguinte."""
    return soma_meses(d, meses) - timedelta(days=1)


def fmt_prazo(meses):
    if int(meses) <= 0:
        return "0 meses"
    a, m = divmod(int(meses), 12)
    return ("%d ano%s" % (a, "s" if a != 1 else "") if a else "") + (" e " if a and m else "") + ("%d %s" % (m, "mês" if m == 1 else "meses") if m else "")


def _idade(nasc, ref):
    if not nasc or not ref:
        return None
    return ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))


def _pena_processo(r, c):
    """Soma das penas dos crimes ativos da mesma condenação (processo criminal) do crime c."""
    proc = c.get("processo_criminal") or ""
    mesmos = [x for x in r.get("_crimes", []) if rs.mesmo_processo(x.get("processo_criminal"), proc) and not (x.get("extinto") or "").upper().startswith("S")] if proc else [c]
    return sum(rs.pena_para_dias(x.get("pena_imposta")) or 0 for x in mesmos)


def _so_digitos(t):
    """Chave de comparação: dígitos sem zeros à esquerda (o SEEU imprime o processo antigo de dois jeitos)."""
    return rs.chave_processo(t)


def _lista_processos(procs):
    """'Processos Selecionados' do evento (texto do RSPE) -> lista de chaves de processo."""
    return [d for d in (rs.chave_processo(x) for x in rs.lista_processos(procs)) if d]


RE_EVASAO = rs.re.compile(r"FUGA|EVAS|ABANDON|FORAGID|N[ÃA]O RETORN|REVOGA[ÇC][ÃA]O D[OE] LIVRAMENTO|LIVRAMENTO[^\n]*REVOGA", rs.re.I)
RE_REVOGA_LC = rs.re.compile(r"REVOGA[ÇC][ÃA]O D[OE] LIVRAMENTO|LIVRAMENTO[^\n]*REVOGA", rs.re.I)
RE_SEM_CULPA = rs.re.compile(r"LIBERDADE PROVIS|RELAXAMENTO|HABEAS|ALVAR|FINAL DA PRIS|REVOGA[ÇC][ÃA]O DA PRIS|REVOGA[ÇC][ÃA]O DA PREVENTIVA|PREVENTIVA REVOGADA|SOLTURA", rs.re.I)


# motivos de interrupção da tabela oficial do SEEU (Tabelas de Parâmetros - Motivos de Interrupção/Extinção)
RE_MOTIVO_VAZIO = rs.re.compile(r"^\s*(N[ÃA]O CONSTA|INTERRUP[ÇC][ÃA]O DO CUMPRIMENTO( DA PENA)?)\s*$", rs.re.I)
RE_MOTIVO_GENERICO = rs.re.compile(r"BENEF[ÍI]CIO REVOGADO|BENEF[ÍI]CIO SUSPENSO|SUSPENS[ÃA]O DE BENEF[ÍI]CIO|DESCUMPRIMENTO DAS CONDI", rs.re.I)
# a execução seguiu em outra modalidade ou lugar: não é liberdade (a prescrição não corre)
RE_INTERRUP_CONTINUA = rs.RE_INTERRUP_CONTINUA
# a execução terminou: depois disso não há prescrição a correr
RE_INTERRUP_EXTINCAO = rs.re.compile(r"[ÓO]BITO|^\s*CUMPRIMENTO DA PENA\s*$|^\s*PRESCRI[ÇC][ÃA]O\s*$|^\s*INDULTO\s*$|PERD[ÃA]O JUDICIAL|"
                                     r"PAGAMENTO DE MULTA|CUMPRIMENTO DA MEDIDA DE SEGURAN|ARQUIVAMENTO DOS AUTOS|ABSOLVI", rs.re.I)


def _motivo_interrupcao(eventos, incidentes, g0):
    """Motivo da interrupção do cumprimento em g0 (evento INTERRUPÇÃO na data, ou revogação do livramento). "Não consta" e a
    interrupção sem causa valem como motivo ausente; "benefício revogado/suspenso" e "descumprimento das condições" buscam
    nos incidentes da data se o benefício era o livramento (art. 113)."""
    mot_ev = None
    for e in eventos:
        if "INTERRUP" in (e.get("tipo") or "").upper() and rs.to_date(e.get("data") or "") == g0:
            mot_ev = (e.get("motivo") or "").strip()
            if RE_MOTIVO_VAZIO.search(mot_ev):
                mot_ev = ""
            break
    if mot_ev and not RE_MOTIVO_GENERICO.search(mot_ev):
        return mot_ev
    for i in incidentes:
        t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
        if rs.e_revogacao_livramento(i):
            d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and abs((d - g0).days) <= 1:
                return "REVOGAÇÃO DO LIVRAMENTO"
    for i in incidentes:
        if rs.e_suspensao_livramento(i):
            d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if d and abs((d - g0).days) <= 1:
                return "SUSPENSÃO DO LIVRAMENTO"
    return mot_ev or ""


RE_CONTINUIDADE = re.compile(r"\bART\.?\s*71\b|CRIME CONTINUADO|CONTINUIDADE DELITIVA", re.I)


def _continuidade(c):
    """'art. 71' se o RSPE indica crime continuado no artigo, no tipo penal ou na pena do processo; senão ''."""
    txt = " ".join(str(c.get(k) or "") for k in ("artigo", "tipo_penal", "pena_total_processo", "complemento"))
    if rs.num_lei(c.get("lei")) not in ("2848", "") and "PENAL" not in (c.get("lei") or "").upper() and rs.num_art(c.get("artigo")) == "71":
        txt = txt.replace(c.get("artigo") or "", "")  # art. 71 de outra lei não é continuidade
    m = RE_CONTINUIDADE.search(txt)
    return "art. 71 do CP" if m else ""


RE_CONCURSO_FORMAL = re.compile(r"\bART\.?\s*70\b|CONCURSO FORMAL", re.I)


def _concurso_formal(c):
    """True se o RSPE indica concurso formal (art. 70 do CP) no tipo penal ou na pena do processo."""
    txt = " ".join(str(c.get(k) or "") for k in ("tipo_penal", "pena_total_processo", "artigo"))
    if rs.num_lei(c.get("lei")) not in ("2848", "") and "PENAL" not in (c.get("lei") or "").upper() and rs.num_art(c.get("artigo")) == "70":
        txt = txt.replace(c.get("artigo") or "", "")  # art. 70 de outra lei não é concurso formal
    return bool(RE_CONCURSO_FORMAL.search(txt))


def imprescritivel(c):
    """('sim', texto) para racismo (Lei 7.716/1989, inclusive a injúria racial do art. 2º-A - CF, art. 5º, XLII); ('verificar',
    texto) para a injúria qualificada do art. 140, § 3º, do CP (imprescritível se racial - STF, HC 154.248 e RE 1.467.380) e
    para os crimes contra o Estado Democrático dos arts. 359-L e 359-M (ação de grupos armados - CF, art. 5º, XLIV); senão None.
    Hediondos e tráfico prescrevem normalmente (CF, art. 5º, XLIII, não os torna imprescritíveis)."""
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    if lei == "7716":
        return ("sim", "racismo (Lei 7.716/1989): imprescritível (CF, art. 5º, XLII)")
    cp = lei in ("2848", "") and "MILITAR" not in (c.get("lei") or "").upper()
    if cp and art == "140" and re.search(r"§\s*3", (c.get("tipo_penal") or "") + " " + (c.get("artigo") or "")):
        return ("verificar", "injúria qualificada (CP, art. 140, § 3º): se racial ou étnica, é espécie de racismo e imprescritível (STF, HC 154.248, "
                             "Plenário; RE 1.467.380) - conferir o elemento da sentença")
    if cp and art in ("359-L", "359-M"):
        return ("verificar", "crime contra o Estado Democrático (CP, art. %s): a ação de grupos armados contra a ordem constitucional é "
                             "imprescritível (CF, art. 5º, XLIV) - conferir" % art)
    return None


def _juri(c):
    """Crime do júri: CP, arts. 121 (salvo o culposo, § 3º), 121-A, 121-B, 122, 123 e 124 a 127, ou condenação na vara do
    júri (o júri pode ter desclassificado o crime; a pronúncia interrompe mesmo assim - STJ, Súmula 191)."""
    if re.search(r"\bJ[ÚU]RI\b", c.get("vara_condenacao") or "", re.I):
        return True
    if not (rs.num_lei(c.get("lei")) in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())):
        return False
    art = rs.num_art(c.get("artigo"))
    if art == "121":
        return (rs.paragrafo_inciso(c) or ("", ""))[0] != "3"
    return art in ("121-A", "121-B", "122", "123", "124", "125", "126", "127")


def _uniao(periodos, hoje=None):
    """Une períodos sobrepostos ou contíguos (mesma regra de rspe_scraper.uniao_periodos)."""
    return rs.uniao_periodos(periodos)


def _gaps_sem_custodia(inicio, fim, periodos):
    """Trechos entre inicio e fim em que não há custódia. Devolve [(g0, g1)]."""
    ps = sorted([(a, b or fim) for a, b in periodos if (b or fim) > inicio])
    gaps, cursor = [], inicio
    for a, b in ps:
        if a > cursor:
            gaps.append((cursor, min(a, fim)))
        cursor = max(cursor, b)
        if cursor >= fim:
            break
    if cursor < fim:
        gaps.append((cursor, fim))
    return [(a, b) for a, b in gaps if b > a]


RE_PROVISORIA = rs.re.compile(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", rs.re.I)


def _mesmo_processo(a, b):
    """Mesmo processo pelos dígitos (sem zeros à esquerda): iguais, ou um termina com o outro e o menor tem 5 dígitos ou mais
    ("32698" é o 0000000-00.0000.0.03.2698; "001030824550" é o 0000000-00.0103.0.82.4550)."""
    ka, kb = rs.chave_processo(a), rs.chave_processo(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    return min(len(ka), len(kb)) >= 5 and (ka.endswith(kb) or kb.endswith(ka))


def _dias_uniao(periodos, de, ate):
    """Dias de calendário dos períodos (unidos) dentro de [de, ate]."""
    total = 0
    for a, b in rs.uniao_periodos([(x, y) for x, y in periodos if x]):
        a2, b2 = max(a, de), min(b or ate, ate)
        if b2 > a2:
            total += (b2 - a2).days
    return total


def _termo_crime(c, TEMA_788):
    """Termo inicial da executória de um crime (trânsito para a acusação até a modulação do Tema 788; depois, o trânsito final), ou None."""
    tmp, tpr = rs.to_date(c.get("transito_mp") or ""), rs.to_date(c.get("transito_processo") or "")
    if tmp and tmp <= TEMA_788:
        return tmp
    return tpr or tmp


def _rotulo_faixa(dias):
    """Rótulo da faixa do art. 109 em que o saldo cai: 'inferior a 1 ano', 'de 1 a 2 anos', ... 'acima de 12 anos'."""
    a = dias / float(rs.DIAS_ANO)
    if a < 1:
        return "inferior a 1 ano"
    for lo, hi in ((1, 2), (2, 4), (4, 8), (8, 12)):
        if a <= hi:
            return "de %d a %s" % (lo, rs.pl(hi, "ano", "anos"))
    return "acima de 12 anos"


def _faixas_saldo(smin, smax):
    """Valores de saldo (dias) a testar entre os limites: os dois limites e as bordas das faixas do art. 109 atravessadas."""
    vals = {smin, smax}
    for anos in (1, 2, 4, 8, 12):
        for v in (anos * rs.DIAS_ANO - 1, anos * rs.DIAS_ANO, anos * rs.DIAS_ANO + 1):
            if smin <= v <= smax:
                vals.add(v)
    return sorted(vals)


def _dur(d0, d1):
    """Tempo entre duas datas por extenso: '6 anos, 11 meses e 4 dias'."""
    if not d0 or not d1 or d1 <= d0:
        return "0 dia"
    a, m = d1.year - d0.year, d1.month - d0.month
    dd = d1.day - d0.day
    if dd < 0:
        m -= 1
        dd += ((d1.replace(day=1) - timedelta(days=1)).day)
    if m < 0:
        a -= 1
        m += 12
    p = [rs.pl(a, "ano", "anos") if a else "", rs.pl(m, "mês", "meses") if m else "", rs.pl(dd, "dia", "dias") if dd else ""]
    p = [x for x in p if x]
    return " e ".join([", ".join(p[:-1]), p[-1]]) if len(p) > 1 else (p[0] if p else "0 dia")


FAIXAS_TETO = ((0, 1, "inferior a 1 ano"), (1, 2, "de até 2 anos"), (2, 4, "de até 4 anos"), (4, 8, "de até 8 anos"), (8, 12, "de até 12 anos"), (12, None, "acima de 12 anos"))


def _d(n):
    """'1.234 dias'."""
    return "{:,}".format(int(n)).replace(",", ".") + (" dia" if n == 1 else " dias")


def _pena_ou_zero(n):
    """Saldo em texto: 'zero', '120 dias' (abaixo de um ano) ou '2a0m0d'."""
    if not n:
        return "zero"
    return _d(n) if n < rs.DIAS_ANO else rs.dias_para_pena(n)


def _textos_saldo(S, aberto):
    """(saldo, prazo, vencimento) em texto: um valor só quando os limites coincidem; 'nada a prescrever' no saldo zero."""
    v = "vence" if aberto else "venceria"
    if S["saldo_min"] == S["saldo_max"]:
        saldo = "saldo %s%s" % (_pena_ou_zero(S["saldo_max"]), (" " + S["fonte_saldo"]) if S["fonte_saldo"] else "")
        prazo = ("prazo de %s" % S["prazo_max"]) if S["prazo_max"] else "nada a prescrever"
        venc = ("%s em %s" % (v, S["limite_max"])) if S["limite_max"] else ""
        return saldo, prazo, venc
    saldo = "saldo entre %s e %s" % (_pena_ou_zero(S["saldo_min"]), _pena_ou_zero(S["saldo_max"]))
    if not S["saldo_min"]:
        return saldo, "nada a prescrever pelo saldo mínimo; pelo saldo máximo, prazo de %s" % S["prazo_max"], "%s em %s" % (v, S["limite_max"])
    if S["prazo_min"] == S["prazo_max"]:
        return saldo, "prazo de %s nos dois limites" % S["prazo_max"], "%s em %s" % (v, S["limite_max"])
    return saldo, "prazo entre %s e %s" % (S["prazo_min"], S["prazo_max"]), "%s entre %s e %s" % (v, S["limite_min"], S["limite_max"])


def _executoria(L, c, r, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia):
    """Prescrição da pretensão executória de um crime com termo inicial (arts. 112, 113, 116, p. único, 117, V, e 119 do CP):
    classifica cada período dos eventos em relação a este crime (prisão provisória = detração informativa; cumprimento da
    execução unificada = interrompe; prisão só de outro processo = suspende), acha as evasões, calcula o saldo da pena
    entre dois limites (este crime imputado primeiro ou por último no tempo cumprido) e o prazo de cada faixa do art. 109
    atravessada, e conclui: aparente, não prescrita ou A VERIFICAR. Preenche os campos ppe_* de L e devolve a memória."""
    hoje, eventos, incidentes = ctx["hoje"], ctx["eventos"], ctx["incidentes"]
    periodos_det, extras, extras_lc = ctx["periodos_det"], ctx["extras"], ctx["extras_lc"]
    remicoes, ativos, crimes, TEMA_788 = ctx["remicoes"], ctx["ativos"], ctx["crimes"], ctx["TEMA_788"]
    em_custodia = ctx["em_custodia"]
    # regime aberto com a data da fuga desconhecida: o operador informa o último comparecimento; o cumprimento termina nele
    ult_ppl = rs.to_date(c.get("_ult_comp") or "")
    if ult_ppl and ult_ppl > termo:
        periodos_det = [(a, (ult_ppl if (a <= ult_ppl < (b or hoje)) else b), m, p) for a, b, m, p in periodos_det]
        extras = [(a, (ult_ppl if (a <= ult_ppl < (b or hoje)) else b)) for a, b in extras]
        em_custodia = em_custodia and not any(a <= ult_ppl for a, b in periodos_det if b == ult_ppl)
    else:
        ult_ppl = None
    proc_x = c.get("processo_criminal") or ""
    cab = ["Pena aplicada: %s (título executivo)." % L["pena"],
           "Termo inicial: %s." % termo_txt,
           "Prazo pela pena aplicada: %s." % L["prazo_ppe"]]
    LT, cumpr, susp, faltam, corpo = [], [], [], [], []
    detr = 0
    todos = []  # custódia e livramento de toda a execução (tempo cumprido total), sem a prisão por outro motivo

    def lt(inicio, fim, tipo, fonte, efeito, atribuicao="comprovada"):
        """atribuicao: 'comprovada' (o evento liga ao processo do crime ou não indica processo) ou 'nao_comprovada' (cumprimento
        registrado só para outro processo: conta como cumprimento da execução unificada, mas a imputação a este crime não consta)."""
        LT.append({"inicio": rs.fmt(inicio), "fim": rs.fmt(fim) if fim else "", "tipo": tipo, "fonte": fonte, "efeito": efeito, "atribuicao": atribuicao})

    RE_INICIO = rs.re.compile(r"DEFINITIV|IN[ÍI]CIO DO CUMPRIMENTO|REIN[ÍI]CIO|RECAPTURA|CUMPRIMENTO", rs.re.I)
    inicios_cumpr = sorted(set(d for d in (rs.to_date(e.get("data") or "") for e in eventos
                                           if "INTERRUP" not in (e.get("tipo") or "").upper() and RE_INICIO.search(e.get("motivo") or "")) if d))
    for (a, b, motivo, procs) in periodos_det:
        lst = rs.lista_processos(procs)
        liga = (not lst) or any(_mesmo_processo(proc_x, p) for p in lst)
        provisoria = RE_PROVISORIA.search(motivo or "") is not None
        fim = b or hoje
        mot = (motivo or "prisão").lower()
        fonte = "%s de %s%s" % (mot, rs.fmt(a), (" (processo %s)" % procs) if procs else " (sem processo indicado)")
        if a < termo:
            f = min(fim, termo)
            if liga:
                detr += (f - a).days + (1 if (b and b < termo) else 0)  # conta o dia da prisão e o da soltura, como o SEEU (dias_cumpridos_ate)
                lt(a, f, "provisoria", fonte, "prisão provisória anterior ao termo inicial: detração (CP, art. 42), informativa; não reduz a pena nem o prazo")
            else:
                lt(a, f, "provisoria", fonte, "anterior ao termo inicial e registrada só para outro processo: sem efeito nesta prescrição")
        if fim > termo:
            a2 = max(a, termo)
            fim_txt = rs.fmt(b) if b else "hoje"
            if not liga and provisoria and a > termo:
                # evento de início do cumprimento (prisão definitiva, início de regime, recaptura) dentro da custódia: a partir
                # dele a prisão é cumprimento da pena unificada
                conv = min([d for d in inicios_cumpr if a < d < fim], default=None)
                s_fim = conv or b
                s_fim_txt = rs.fmt(s_fim) if s_fim else "hoje"
                susp.append((a2, s_fim))
                lt(a2, s_fim, "outro_motivo", fonte, "preso por outro motivo: suspende o prazo (art. 116, p. único), sem interromper; se essa prisão foi "
                                                      "convertida em cumprimento da pena unificada, o efeito é de interrupção - conferir")
                corpo.append((a2, "Prisão por outro motivo de %s a %s (%s, processo %s) - suspende (art. 116, p. único); se convertida em cumprimento "
                                  "da pena unificada, interrompe - conferir." % (rs.fmt(a2), s_fim_txt, mot, procs)))
                faltam.append("se a prisão de %s a %s pelo processo %s foi convertida em cumprimento da pena unificada" % (rs.fmt(a2), s_fim_txt, procs))
                if conv:
                    cumpr.append((conv, b))
                    todos.append((conv, b))
                    ev_conv = next(e for e in eventos if rs.to_date(e.get("data") or "") == conv and "INTERRUP" not in (e.get("tipo") or "").upper())
                    lt(conv, b, "cumprimento", "%s de %s%s" % ((ev_conv.get("motivo") or "início do cumprimento").lower(), rs.fmt(conv),
                                                                 (" (processo %s)" % ev_conv.get("processos")) if ev_conv.get("processos") else ""),
                       "início do cumprimento da pena unificada registrado durante a custódia: interrompe (art. 117, V) e conta como tempo cumprido")
                    corpo.append((conv, "Cumprimento de %s a %s (%s, registrado durante a custódia): interrompe (art. 117, V)." % (rs.fmt(conv), fim_txt, (ev_conv.get("motivo") or "início do cumprimento").lower())))
                continue
            cumpr.append((a2, b))
            ef = "cumprimento da pena unificada (LEP, art. 111): interrompe (art. 117, V) e conta como tempo cumprido"
            if not liga:
                ef += "; registrada só para outro processo" + (", já em curso no termo inicial" if a <= termo else "") + " - conferir"
            lt(a2, b, "cumprimento", fonte, ef, "comprovada" if liga else "nao_comprovada")
            corpo.append((a2, "Cumprimento de %s a %s (%s%s)%s." % (rs.fmt(a2), fim_txt, mot, (", processo %s" % procs) if procs else ", sem processo indicado",
                                                                  (" - registrada só para outro processo%s: conferir se alcança esta condenação" % (", já em curso no termo inicial" if a <= termo else "")) if not liga else "")))
        todos.append((a, b))
    for (a, b) in extras:
        todos.append((a, b))
        if (b or hoje) <= termo:
            continue
        a2 = max(a, termo)
        fim_txt = rs.fmt(b) if b else "hoje"
        if (a, b) in extras_lc and a < termo:
            # livramento que começou antes desta condenação existir: é de outra pena (esta só começa depois do período de
            # prova - STJ, Tema 1.367); em livramento por outro crime, a prescrição não corre (art. 116, p. único; STJ, HC 429.545)
            susp.append((a2, b))
            lt(a2, b, "outro_motivo", "livramento condicional de %s (outra condenação)" % rs.fmt(a),
               "em livramento por outra condenação: a prescrição desta não corre (art. 116, p. único; STJ, HC 429.545)")
            corpo.append((a2, "Livramento condicional de outra condenação de %s a %s: a prescrição desta não corre (art. 116, p. único; STJ, HC 429.545)." % (rs.fmt(a2), fim_txt)))
            continue
        cumpr.append((a2, b))
        if (a, b) in extras_lc:
            lt(a2, b, "livramento", "livramento condicional de %s" % rs.fmt(a), "período de prova: a pena se cumpre e o prazo não corre (art. 117, V)")
            corpo.append((a2, "Livramento condicional de %s a %s: período de prova, conta como cumprimento." % (rs.fmt(a2), fim_txt)))
        else:
            lt(a2, b, "cumprimento", "cumprimento em curso inferido da última alteração de regime", "conta como cumprimento; RSPE sem evento de início correspondente - conferir")
            corpo.append((a2, "Cumprimento de %s a %s (inferido da última alteração de regime; sem evento de início no RSPE - conferir)." % (rs.fmt(a2), fim_txt)))
    L["ppe_detracao_dias"] = detr
    if detr:
        cab.append("Prisão provisória anterior ao termo inicial: %s (detração, CP, art. 42) - informativa; não reduz a pena nem o prazo "
                   "(STJ, AgRg no HC 967.565; RHC 67.403)." % _d(detr))
        pp = _pena_processo(r, c)
        if pp and detr >= pp:
            cab.append("⚠ A verificar: a detração (%s) iguala ou supera a pena do processo (%s). Se computada nesta condenação, cabe extinção pelo "
                       "cumprimento (LEP, art. 66, II) - hipótese na aba Extinção; como a mesma prisão pode servir a várias condenações, a "
                       "detração vale uma vez só na pena unificada (LEP, art. 111)." % (_d(detr), rs.dias_para_pena(pp)))
            L["avisos"].append("detração de %s anterior ao trânsito cobre a pena do processo - conferir se cabe extinção pelo cumprimento (aba Extinção)" % rs.dias_para_pena(detr))
            L["ppe_detracao_cobre"], L["ppe_pena_processo"] = True, rs.dias_para_pena(pp)

    def rem_ate(ate):
        return sum(n for d, n in remicoes if d and d <= ate)

    # condenações em execução além desta: ativas com trânsito, ou extintas pelo cumprimento
    outros_crimes = []
    for x in crimes:
        if x is c:
            continue
        tx = _termo_crime(x, TEMA_788)
        px = rs.pena_para_dias(x.get("pena_imposta") or x.get("pena_total_processo")) or 0
        ext = (x.get("extinto") or "").upper().startswith("S")
        if tx and px and (not ext or "CUMPRIM" in (x.get("extincao_motivo") or "").upper()):
            outros_crimes.append((tx, px, x))
    # novo crime praticado depois do termo inicial (art. 117, VI): interrompe na data do fato (STF, HC 230.334; STJ, AgRg no
    # HC 861.588), se a prescrição ainda não se consumara (STJ, RHC 168.441); o marco se confirma com o trânsito da nova
    # condenação (STJ, REsp 2.117.844). Fontes: as outras condenações deste RSPE e a data informada pelo operador
    novos = []
    for x in crimes:
        if x is c:
            continue
        dx = rs.to_date(x.get("data_infracao") or "")
        if dx and dx > termo:
            novos.append((dx, "%s, ação penal %s" % (rs.crimes_curto([x]) or "crime", x.get("processo_criminal") or "não informada"),
                          bool(x.get("transito_processo") or x.get("transito_mp"))))
    if rs.to_date(c.get("_novo_crime") or ""):
        novos.append((rs.to_date(c["_novo_crime"]), "informado pelo operador", True))
    novos.sort(key=lambda t: t[0])
    # regime aberto com a data da fuga desconhecida: o operador informa o último comparecimento (ou a ausência à audiência de
    # justificação), e a execução se tem por interrompida nessa data, não na do lançamento do SEEU (STF, HC 166.850; TJMS,
    # 1603205-53.2026)
    if ult_ppl:
        corpo.append((ult_ppl, "Último comparecimento em %s (informado pelo operador): a execução se tem por interrompida nessa data, e não na "
                               "do lançamento no SEEU (STF, HC 166.850; TJMS, 1603205-53.2026)." % rs.fmt(ult_ppl)))
    gaps = _gaps_sem_custodia(termo, hoje, cumpr)
    prescrita = correndo = verificar = None
    datas_ver = []  # evasões com resultado divergente
    L["ppe_resumo"] = ""
    if not gaps:
        corpo.append((hoje, "Em cumprimento (custódia, regime aberto ou livramento) desde o termo inicial: a prescrição não corre (arts. 116, p. único, e 117, V)."))
    for g0, g1 in gaps:
        aberto = g1 >= hoje and not em_custodia
        ref = hoje if aberto else g1
        fim_txt = "hoje" if g1 >= hoje else rs.fmt(g1)
        # interrupção por prisão em outro processo: a pessoa segue presa - o prazo não corre (art. 116, p. único)
        _mot0 = _motivo_interrupcao(eventos, incidentes, g0) if (g0 > termo and not (ult_ppl and g0 == ult_ppl)) else ""
        if _mot0 and rs.RE_OUTRO_PROC.search(_mot0):
            lt(g0, g1 if g1 < hoje else None, "outro_motivo", "interrupção de %s (%s)" % (rs.fmt(g0), _mot0.lower()),
               "preso em outro processo: suspende o prazo (art. 116, p. único)")
            corpo.append((g0, "De %s a %s preso em outro processo (%s): a prescrição não corre (art. 116, p. único)." % (rs.fmt(g0), fim_txt, _mot0.lower())))
            if g1 >= hoje:
                L["ppe_nao_corre"] = "preso em outro processo desde %s (%s)" % (rs.fmt(g0), _mot0.lower())
            continue
        if _mot0 and RE_INTERRUP_CONTINUA.search(_mot0):
            lt(g0, g1 if g1 < hoje else None, "cumprimento", "interrupção de %s (%s)" % (rs.fmt(g0), _mot0.lower()),
               "a execução seguiu em outra modalidade ou lugar: conta como cumprimento e o prazo não corre (art. 117, V) - conferir")
            corpo.append((g0, "De %s a %s: %s - a execução seguiu (outra modalidade ou lugar), não houve liberdade; a prescrição não corre "
                              "(art. 117, V). Conferir se houve abandono depois." % (rs.fmt(g0), fim_txt, _mot0.lower())))
            L["avisos"].append("interrupção em %s por \"%s\": tratada como continuidade do cumprimento - conferir" % (rs.fmt(g0), _mot0.lower()))
            if g1 >= hoje:
                L["ppe_nao_corre"] = "execução seguiu desde %s (%s)" % (rs.fmt(g0), _mot0.lower())
            continue
        if _mot0 and RE_INTERRUP_EXTINCAO.search(_mot0):
            lt(g0, g1 if g1 < hoje else None, "outro_motivo", "interrupção de %s (%s)" % (rs.fmt(g0), _mot0.lower()),
               "execução encerrada: depois disso não há prescrição a correr")
            corpo.append((g0, "Execução encerrada em %s (%s): depois disso não há prescrição executória a correr - conferir a extinção nos autos." % (
                rs.fmt(g0), _mot0.lower())))
            L["ppe_encerrada"] = "%s (%s)" % (rs.fmt(g0), _mot0.lower())
            break

        novos_g = [t for t in novos if g0 < t[0] < g1]
        interr_nc = []  # novos crimes que interromperam o prazo neste intervalo (o último vale)

        def _limite0(meses, ini):
            """Último dia do prazo: ini + prazo + dias presos por outro motivo dentro do intervalo (art. 116, p. único). A suspensão
            que atravessa a data-limite empurra-a para a frente até que a soltura (ou o fim do intervalo) fique antes dela."""
            lim = soma_meses(ini, meses)
            sd = 0
            for s0, s1 in sorted((a, b or hoje) for a, b in susp):
                contados = 0
                while True:
                    if s0 >= lim or s1 <= ini:
                        break
                    dias_s = (min(s1, g1, lim) - max(s0, ini + timedelta(days=1))).days + 1
                    if dias_s <= contados:
                        break
                    lim = lim + timedelta(days=dias_s - contados)
                    sd += dias_s - contados
                    contados = dias_s
            return lim - timedelta(days=1), sd  # último dia do prazo (CP, art. 10)

        def _limite(meses):
            """Com os novos crimes do intervalo: cada um reinicia todo o prazo na data do fato (art. 117, VI, e § 2º), salvo se o
            prazo já se consumara antes dele."""
            lim, sd = _limite0(meses, g0)
            usados = []
            for d_nc, rot_nc, _t in novos_g:
                if lim < d_nc:
                    break
                usados.append((d_nc, rot_nc, _t))
                lim, sd = _limite0(meses, d_nc)
            interr_nc[:] = usados
            return lim, sd

        def _nota_nc(meses):
            """Memória e linha do tempo dos novos crimes do intervalo (art. 117, VI)."""
            if not novos_g or meses is None:
                return ""
            lim, _ = _limite(meses)
            for d_nc, rot_nc, tr_nc in novos_g:
                if (d_nc, rot_nc, tr_nc) in interr_nc:
                    corpo.append((d_nc, "Novo crime em %s (%s): interrompe a prescrição na data do fato e todo o prazo recomeça (CP, art. 117, VI, e § 2º; "
                                        "STF, HC 230.334)%s." % (rs.fmt(d_nc), rot_nc, "" if tr_nc else " - a nova condenação ainda não consta como "
                                        "transitada: o marco só se confirma com o trânsito (STJ, REsp 2.117.844) - conferir")))
                    if not tr_nc:
                        faltam.append("trânsito em julgado da condenação pelo novo crime de %s" % rs.fmt(d_nc))
                else:
                    corpo.append((d_nc, "Novo crime em %s (%s): posterior à consumação da prescrição, não a interrompe (STJ, RHC 168.441)." % (rs.fmt(d_nc), rot_nc)))
            return rs.fmt(interr_nc[-1][0]) if interr_nc else ""

        susp_total = sum(max(0, (min(b or hoje, g1) - max(a, g0)).days) for a, b in susp)
        if susp_total and susp_total >= (g1 - g0).days - 1:
            corpo.append((g0, "De %s a %s preso ou em livramento por outro motivo: o prazo não corre (art. 116, p. único)." % (rs.fmt(g0), fim_txt)))
            continue
        motivo = _motivo_interrupcao(eventos, incidentes, g0) if g0 > termo else ""
        if ult_ppl and g0 == ult_ppl:
            motivo = "ABANDONO DO REGIME (último comparecimento em %s)" % rs.fmt(ult_ppl)
        cumprido_g0 = _dias_uniao(cumpr, termo, g0)
        rem_g0 = rem_ate(g0)
        if g0 == termo or not any(a <= g0 for a, _ in cumpr):
            # nunca iniciou o cumprimento depois do trânsito: prazo pela pena aplicada, do termo inicial (art. 112, I)
            lim, sd = _limite(ppe_meses)
            lt(g0, g1 if g1 < hoje else None, "liberdade", "trânsito em julgado sem início do cumprimento",
               "prazo pela pena aplicada, do termo inicial (art. 112, I)" + ("; %s de suspensão" % _d(sd) if sd else ""))
            txt = "Liberdade de %s a %s (sem início do cumprimento após o trânsito): prazo de %s pela pena aplicada%s" % (
                rs.fmt(g0), fim_txt, fmt_prazo(ppe_meses), ("; %s de suspensão (art. 116, p. único)" % _d(sd)) if sd else "")
            base = dict(g0=g0, g1=g1, meses=ppe_meses, base_dias=pena, cumprido=0, motivo="", restante=False, limite=lim, evasao=False)
        elif motivo and not RE_EVASAO.search(motivo):
            # o art. 113 (prazo pelo saldo) só alcança a evasão e a revogação do livramento; qualquer outra interrupção
            # (soltura, habeas corpus, descumprimento de condição do semiaberto harmonizado, conversão de restritiva) segue a
            # pena aplicada (STF, HC 236.292; STJ, RHC 67.403 e AgRg no HC 751.110)
            lim, sd = _limite(ppe_meses)
            lt(g0, g1 if g1 < hoje else None, "liberdade", "interrupção de %s (%s)" % (rs.fmt(g0), motivo.lower()),
               "interrupção sem evasão nem revogação do livramento: prazo pela pena aplicada, sem o art. 113 (STF, HC 236.292; STJ, RHC 67.403)"
               + ("; %s de suspensão" % _d(sd) if sd else ""))
            if RE_MOTIVO_GENERICO.search(motivo):
                L["avisos"].append("interrupção em %s por \"%s\" sem incidente de revogação do livramento na data: se o benefício era o livramento, "
                                   "o prazo é pelo saldo (art. 113) - conferir qual benefício" % (rs.fmt(g0), motivo.lower()))
                faltam.append("qual benefício foi revogado/suspenso em %s" % rs.fmt(g0))
                L["ppe_alerta_extra"] = ("Confira qual benefício foi revogado/suspenso em %s: se foi o livramento, o prazo é pelo saldo da pena "
                                         "(art. 113), e pode ser menor." % rs.fmt(g0))
            txt = "Interrupção sem evasão de %s a %s (%s): prazo de %s pela pena aplicada - o art. 113 vale só na evasão e na revogação do livramento (STF, HC 236.292; STJ, RHC 67.403)%s" % (
                rs.fmt(g0), fim_txt, motivo.lower(), fmt_prazo(ppe_meses), ("; %s de suspensão (art. 116, p. único)" % _d(sd)) if sd else "")
            base = dict(g0=g0, g1=g1, meses=ppe_meses, base_dias=pena, cumprido=cumprido_g0, motivo=motivo, restante=False, limite=lim, evasao=False)
        else:
            # evasão (fuga, abandono, revogação do livramento; motivo ausente = evasão com aviso): prazo pelo saldo (art. 113)
            revog = bool(motivo and RE_REVOGA_LC.search(motivo))
            e_evasao = revog or not motivo or RE_EVASAO.search(motivo) is not None
            if motivo and not e_evasao:
                L["avisos"].append("interrupção do cumprimento em %s (%s): não é evasão nem revogação do livramento, e o art. 113 pode não se aplicar - conferir" % (rs.fmt(g0), motivo.lower()))
            if not motivo:
                L["avisos"].append("interrupção do cumprimento em %s sem motivo no RSPE: tratada como evasão (art. 113) - conferir" % rs.fmt(g0))
                faltam.append("motivo da interrupção do cumprimento em %s" % rs.fmt(g0))
            outras = [(tx, px, x) for tx, px, x in outros_crimes if tx < g0]
            soma_outras = sum(px for _, px, _ in outras)
            inicio_exec = min([termo] + [tx for tx, _, _ in outras])
            cumprido_total = _dias_uniao(todos, inicio_exec, g0) + rem_g0
            cumprido_min_base = cumprido_g0 + rem_g0
            fonte_saldo = ""
            if not outras:
                saldo_min = saldo_max = max(0, pena - cumprido_min_base)
                rem_seeu = rs.pena_para_dias(r.get("pena_remanescente"))
                if aberto and rem_seeu and len(ativos) == 1 and not ult_ppl:  # com o último comparecimento, o remanescente do SEEU conta tempo que não houve
                    saldo_min = saldo_max = rem_seeu
                    fonte_saldo = " (pena remanescente do RSPE)"
            else:
                saldo_min = max(0, pena - cumprido_min_base)
                saldo_max = min(pena, max(0, pena - max(0, cumprido_total - soma_outras)))
            # item 6.5: a origem do saldo fica sempre à vista; estimativa não passa por dado confirmado
            inf = (ctx.get("saldos_inf") or {}).get(rs.fmt(g0))
            if inf is not None:
                saldo_min = saldo_max = max(0, min(pena, int(inf)))
                fonte_saldo = " (informado pelo operador)"
                origem = "informado"
                saldo_rotulo = "Saldo informado pelo operador%s: %s (na data da fuga de %s)." % (
                    (" em " + ctx["ajuste_data"]) if ctx.get("ajuste_data") else "", rs.dias_para_pena(saldo_max), rs.fmt(g0))
            elif fonte_saldo:
                origem = "confirmado"
                saldo_rotulo = "Saldo confirmado: %s (pena remanescente do SEEU)." % rs.dias_para_pena(saldo_max)
            elif saldo_min == saldo_max:
                origem = "calculado"
                ini_c = min([a for a, _ in cumpr if a >= termo] or [termo])
                saldo_rotulo = "Saldo calculado a partir dos eventos de %s e %s: %s." % (rs.fmt(ini_c), rs.fmt(g0), rs.dias_para_pena(saldo_max))
            else:
                origem = "nao_determinado"
                saldo_rotulo = "Saldo não determinado pelos dados disponíveis (entre %s e %s)." % (rs.dias_para_pena(saldo_min), rs.dias_para_pena(saldo_max))

            def _hip(ordem):
                """Saldo deste crime se o tempo cumprido for imputado na ordem dada (hipótese de referência)."""
                antes = pos = 0
                for i, (tx, px, x) in enumerate(ordem):
                    if x is c:
                        pos = i + 1
                        break
                    antes += px
                s = min(pena, max(0, pena - max(0, cumprido_total - antes)))
                if s > 0:
                    m = Fraction(prazo_base_anos(s, fato) * 12) * fator
                    lim_h, _ = _limite(m)
                    res = "prescrita" if lim_h < ref else "não prescrita"
                else:
                    m, lim_h, res = None, None, "nada a prescrever"
                return {"posicao": pos, "de": len(ordem), "saldo": s, "prazo_meses": (int(m) if m is not None else None),
                        "prazo": fmt_prazo(m) if m is not None else "", "limite": rs.fmt(lim_h) if lim_h else "", "resultado": res}

            em_exec = outras + [(termo, pena, c)]
            hip76 = _hip(sorted(em_exec, key=lambda t: (-t[1], t[0])))
            hipcron = _hip(sorted(em_exec, key=lambda t: (t[0], -t[1])))
            # faixas do art. 109 atravessadas por [saldo_min, saldo_max]
            # saldo zero (crime já cumprido nessa imputação) não vota: com toda faixa positiva prescrita, a pena deste crime
            # está extinta em qualquer imputação (cumprimento ou prescrição) e o resultado é "aparente"
            faixas, resultados = [], []
            for s in _faixas_saldo(saldo_min, saldo_max):
                if s <= 0:
                    faixas.append({"saldo": 0, "saldo_ate": 0, "meses": None, "limite": "", "prescrita": False, "susp": 0, "rotulo": "saldo zero"})
                    continue
                m = Fraction(prazo_base_anos(s, fato) * 12) * fator
                lim_s, sd = _limite(m)
                pres = lim_s < ref
                if faixas and faixas[-1]["meses"] == int(m):
                    faixas[-1]["saldo_ate"] = s
                    continue
                faixas.append({"saldo": s, "saldo_ate": s, "meses": int(m), "limite": rs.fmt(lim_s), "prescrita": pres, "susp": sd, "rotulo": _rotulo_faixa(s)})
                resultados.append(pres)
            algum_p, algum_n = any(resultados), (not all(resultados)) or not resultados
            mmin = Fraction(prazo_base_anos(saldo_min, fato) * 12) * fator if saldo_min > 0 else None
            mmax = Fraction(prazo_base_anos(saldo_max, fato) * 12) * fator if saldo_max > 0 else None
            lim_min, sd_min = _limite(mmin) if mmin is not None else (None, 0)
            lim_max, sd_max = _limite(mmax) if mmax is not None else (None, 0)
            sd = sd_max or sd_min
            resultado = "não prescrita" if not algum_p else ("prescrita" if not algum_n else "a verificar")
            # a fuga alcançou o menor prazo possível do art. 109 e o saldo não foi informado nem confirmado pelo SEEU: o saldo
            # real (remição, detração, soma de penas que o RSPE não mostra) pode mudar a faixa - pede a pena remanescente na fuga
            informar = None
            if origem in ("calculado", "nao_determinado"):
                m1 = Fraction(prazo_base_anos(1, fato) * 12) * fator
                if _limite(m1)[0] < ref:
                    crit = None
                    for lo, hi, rot_f in FAIXAS_TETO:
                        piso = lo * rs.DIAS_ANO + (1 if lo else 0) if lo != 1 else rs.DIAS_ANO
                        teto = pena if hi is None else min(pena, hi * rs.DIAS_ANO - (1 if hi == 1 else 0))
                        if piso > pena:
                            break
                        mf = Fraction(prazo_base_anos(teto, fato) * 12) * fator
                        lf, _ = _limite(mf)
                        if lf < ref:
                            crit = {"saldo": rot_f, "teto_dias": teto, "prazo": fmt_prazo(mf), "limite": rs.fmt(lf)}
                        else:
                            break
                    if crit and crit["teto_dias"] < pena:
                        informar = dict(crit, fuga=rs.fmt(g0), fim=fim_txt, duracao=_dur(g0, ref), aberto=aberto)
            S = {"evasao": rs.fmt(g0), "fim": fim_txt, "motivo": motivo.lower() if motivo else "não consta", "revogacao": revog, "e_evasao": e_evasao,
                 "cumprido_min": pena - saldo_max, "cumprido_max": pena - saldo_min, "cumprido_desde_termo": cumprido_g0, "remicao": rem_g0,
                 "cumprido_total": cumprido_total, "outras": len(outras), "soma_outras": soma_outras,
                 "saldo_min": saldo_min, "saldo_max": saldo_max, "fonte_saldo": fonte_saldo.strip(),
                 "prazo_min": fmt_prazo(mmin) if mmin is not None else "", "prazo_max": fmt_prazo(mmax) if mmax is not None else "",
                 "prazo_min_meses": int(mmin) if mmin is not None else None, "prazo_max_meses": int(mmax) if mmax is not None else None,
                 "limite_min": rs.fmt(lim_min) if lim_min else "", "limite_max": rs.fmt(lim_max) if lim_max else "",
                 "suspensao_dias": sd, "art76": hip76, "cronologica": hipcron, "faixas": faixas, "resultado": resultado,
                 "saldo_origem": origem, "saldo_rotulo": saldo_rotulo, "informar": informar,
                 "triagem": ("Prescrição confirmada pela análise do limite máximo de saldo." if resultado == "prescrita" and saldo_min != saldo_max else
                             "Não prescrito mesmo com o menor saldo possível." if resultado == "não prescrita" and saldo_min != saldo_max else
                             "O resultado depende do saldo efetivamente atribuído à condenação." if resultado == "a verificar" else "")}
            L["ppe_saldos"].append(S)
            rotulo = "Revogação do livramento" if revog else ("Evasão" if e_evasao else "Interrupção")
            saldo_txt, prazo_txt, venc_txt = _textos_saldo(S, aberto)
            cabeca = "%s em %s%s: cumprido desde o termo %s%s%s; %s; %s%s%s" % (
                rotulo, rs.fmt(g0), (" (%s)" % motivo.lower()) if motivo else " (motivo não consta)",
                _d(cumprido_g0), (" mais %s de remição (LEP, art. 128)" % _d(rem_g0)) if rem_g0 else "",
                ("; outras condenações em execução: %s (soma %s)" % (rs.pl(len(outras), "condenação", "condenações"), rs.dias_para_pena(soma_outras))) if outras else "; única condenação em execução",
                saldo_txt, prazo_txt, ("; " + venc_txt) if venc_txt else "", ("; %s de suspensão (art. 116, p. único)" % _d(sd)) if sd else "")
            if aberto:
                fecho = {"prescrita": " → venceu: prescrição aparente", "não prescrita": " → em curso" if mmax is not None else "", "a verificar": " → a verificar"}[resultado]
            elif g1 >= hoje:
                fecho = {"prescrita": " → venceu: prescrição aparente", "não prescrita": " → prazo suspenso (preso por outro motivo)", "a verificar": " → a verificar"}[resultado]
            else:
                fecho = "; %s em %s → %s" % ("reinício" if revog else "recaptura", rs.fmt(g1),
                                             {"prescrita": "depois de vencido o prazo: prescrição aparente", "não prescrita": "interrompe (art. 117, V)",
                                              "a verificar": "a verificar"}[resultado])
            txt = cabeca + fecho + ". " + saldo_rotulo + ((" " + S["triagem"]) if S["triagem"] else "")
            if resultado == "prescrita" and saldo_min == 0:
                txt += " Pelo saldo mínimo (zero) a pena deste crime já estaria cumprida: extinta em qualquer imputação."
            if informar:
                txt += ("\n⚠ A fuga durou %s (de %s a %s): prescreveria se o saldo na data da fuga fosse %s (prazo de %s, vencido em %s). "
                        "O saldo usado foi %s e pode não refletir remição, detração ou soma de penas que o RSPE não mostra: informe a pena "
                        "remanescente na data da fuga (cálculo de pena do SEEU daquela data, atestado de pena ou decisão de regressão/recaptura)." % (
                            informar["duracao"], informar["fuga"], informar["fim"], informar["saldo"], informar["prazo"], informar["limite"],
                            "estimado entre dois limites" if origem == "nao_determinado" else "calculado pelos eventos do RSPE"))
            if motivo and not e_evasao:
                txt += "\nMotivo da interrupção \"%s\": não é evasão nem revogação do livramento; fora delas o prazo se regula pela pena aplicada (STJ, RHC 67.403) - conferir." % motivo.lower()
            if outras:
                txt += ("\nHipóteses de imputação: pela ordem do art. 76 do CP (mais grave primeiro), este crime seria o %dº de %d - saldo %s (%s%s); "
                        "pela ordem cronológica do trânsito (STJ, HC 627.646), o %dº de %d - saldo %s (%s%s). O RSPE não informa a imputação adotada." % (
                            hip76["posicao"], hip76["de"], _pena_ou_zero(hip76["saldo"]), hip76["resultado"],
                            (", prazo %s até %s" % (hip76["prazo"], hip76["limite"])) if hip76["limite"] else "",
                            hipcron["posicao"], hipcron["de"], _pena_ou_zero(hipcron["saldo"]), hipcron["resultado"],
                            (", prazo %s até %s" % (hipcron["prazo"], hipcron["limite"])) if hipcron["limite"] else ""))
            if outras:
                txt += ("\nVárias execuções: adotada a corrente simultânea - depois da fuga, cada condenação corre pelo seu saldo, nunca pela pena "
                        "unificada (STJ, AgRg no REsp 2.256.555 e HC 261.866). Há corrente sucessiva, desfavorável: só corre a execução em curso e as "
                        "demais ficam suspensas (STJ, AgRg no RHC 150.075). O foragido não está \"preso por outro motivo\" (art. 116, p. único).")
            if rem_g0 and inf is None and not fonte_saldo:
                txt += ("\nOs %s remidos entram como pena cumprida no saldo (LEP, art. 128): tese favorável, sem precedente específico localizado "
                        "sobre a remição no restante que regula a prescrição." % _d(rem_g0))
            if len(faixas) > 1:
                txt += "\nFaixas do art. 109 entre os limites: " + "; ".join(
                    "saldo zero - nada a prescrever" if f["meses"] is None else
                    ("saldo %s%s → %s, %s em %s" % (_pena_ou_zero(f["saldo"]), (" a %s" % _pena_ou_zero(f["saldo_ate"])) if f["saldo_ate"] != f["saldo"] else "",
                                                     fmt_prazo(f["meses"]), "venceu" if f["prescrita"] else ("vence" if aberto else "não venceria"), f["limite"]))
                    for f in faixas) + "."
            lt(g0, g1 if g1 < hoje else None, "evasao" if e_evasao else "interrupcao", "%s de %s (%s)" % ("revogação do livramento" if revog else "interrupção", rs.fmt(g0), motivo.lower() if motivo else "motivo não consta"),
               "prazo pelo saldo da pena (art. 113): %s; %s" % (saldo_txt, resultado))
            base = dict(g0=g0, g1=g1, meses=(mmax if mmax is not None else ppe_meses), base_dias=max(saldo_max, 1), cumprido=pena - saldo_max, motivo=motivo,
                        restante=True, limite=lim_max, evasao=e_evasao, revog=revog, S=S)
            base["nc"] = _nota_nc(mmax)
            if resultado == "a verificar" or (informar and resultado == "não prescrita"):
                corpo.append((g0, "? " + txt))
                datas_ver.append(rs.fmt(g0))
                if verificar is None:
                    verificar = base
                continue
            if resultado == "prescrita":
                corpo.append((g0, "✘ " + txt))
                prescrita = base
                break
            corpo.append((g0, ("… " if (aberto and mmax is not None) else "✔ ") + txt))
            if aberto and mmax is not None:
                correndo = base
            continue
        # liberdade sem evasão ou sem início do cumprimento: prazo pela pena aplicada
        base["nc"] = _nota_nc(base["meses"])
        if base["limite"] < ref:
            corpo.append((g0, "✘ %s: venceu em %s." % (txt, rs.fmt(base["limite"]))))
            prescrita = base
            break
        if aberto:
            corpo.append((g0, "… %s: vence em %s." % (txt, rs.fmt(base["limite"]))))
            correndo = base
        else:
            corpo.append((g0, "✔ %s: não se completou (venceria em %s); retomada do cumprimento interrompeu (art. 117, V)." % (txt, rs.fmt(base["limite"]))))
    corpo.sort(key=lambda t: t[0])
    det = cab + [t for _, t in corpo]
    LT.sort(key=lambda x: (rs.to_date(x["inicio"]) or date.min, x["tipo"]))
    L["ppe_linha_tempo"] = LT
    _dec = prescrita or verificar or correndo
    if _dec and _dec.get("S"):
        L["ppe_saldo_rotulo"] = _dec["S"]["saldo_rotulo"]
    elif L["ppe_saldos"]:
        L["ppe_saldo_rotulo"] = L["ppe_saldos"][-1]["saldo_rotulo"]
        L["ppe_triagem"] = L["ppe_saldos"][-1].get("triagem") or ""
    _inf_v = verificar and (verificar.get("S") or {}).get("informar") and verificar["S"]["resultado"] == "não prescrita"
    if verificar and not _inf_v:
        faltam.insert(0, "cálculo de pena do SEEU com o saldo por condenação em %s" % " e em ".join(datas_ver))
        faltam.insert(1, "ordem de imputação do cumprimento entre as condenações adotada pelo juízo (CP, art. 76; LEP, art. 111)")
    _infs = [S_["informar"] for S_ in L["ppe_saldos"] if S_.get("informar")]
    for _i in _infs:
        faltam.insert(0, "pena remanescente na data da fuga de %s (cálculo de pena do SEEU daquela data, atestado de pena ou decisão de "
                         "regressão/recaptura): com saldo %s, a fuga de %s completou o prazo" % (_i["fuga"], _i["saldo"], _i["duracao"]))
    L["ppe_informar"] = _infs
    L["ppe_faltam"] = faltam if (verificar or _infs) else []
    _x = prescrita or verificar or correndo
    if _x:
        # para a petição: pena que regula o prazo (saldo máximo, quando há limites), cumprido correspondente e início da contagem
        L["ppe_meses"] = _x["meses"]
        L["ppe_meses_integral"] = _x["meses"] * 2 if meia else _x["meses"]
        L["inciso109"] = rg.inciso_art109(_x["base_dias"])
        L["ppe_meses_art109"] = Fraction(prazo_base_anos(_x["base_dias"], fato) * 12)
        L["ppe_base_dias"], L["ppe_inicio"] = _x["base_dias"], rs.fmt(_x["g0"])
        L["ppe_cumprido_dias"] = _x["cumprido"]
        L["ppe_restante"] = _x["restante"]
        L["ppe_evasao"] = rs.fmt(_x["g0"]) if (_x["evasao"] and not _x.get("revog")) else ""
        L["ppe_revogacao"] = rs.fmt(_x["g0"]) if _x.get("revog") else ""
        L["ppe_novo_crime"] = _x.get("nc") or ""
        L["ppe_motivo"] = (_x.get("motivo") or "").lower()

    def _res_evasao(S, aberto):
        rot = "Revogação do livramento" if S["revogacao"] else ("Evasão" if S.get("e_evasao", True) else "Interrupção")
        a, b, c_ = _textos_saldo(S, aberto)
        return "%s em %s com %s: %s%s%s." % (rot, S["evasao"], a, b, _mods(L) if S["saldo_min"] == S["saldo_max"] else "", ("; " + c_) if c_ else "")

    if prescrita:
        L["ppe_status"] = "Prescrição executória aparente em %s" % rs.fmt(prescrita["limite"])
        L["ppe_cor"] = "vermelho"
        L["ppe_previsao"] = rs.fmt(prescrita["limite"])
        L["ppe_dias"] = (prescrita["limite"] - hoje).days
        S = prescrita.get("S")
        L["ppe_resumo"] = (_res_evasao(S, False) + (" Adotada a data mais tardia." if S["limite_min"] and S["limite_min"] != S["limite_max"] else "")) if S else \
            "%s. Com a pena de %s, o prazo é de %s%s: venceu em %s." % (_desde(prescrita["g0"], termo, prescrita["cumprido"]), L["pena"], fmt_prazo(prescrita["meses"]), _mods(L), rs.fmt(prescrita["limite"]))
        det.append("Conclusão: prescrição da pretensão executória aparente em %s.%s" % (
            rs.fmt(prescrita["limite"]), (" " + S["triagem"]) if S and S.get("triagem") else ""))
        det.append("Antes de requerer: conferir recaptura ou nova condenação não registradas no RSPE (interrompem - art. 117, V e VI).")
        if S and S.get("informar"):
            det.append("Antes de requerer: confirmar a pena remanescente na data da fuga de %s (saldo %s): a prescrição se mantém com saldo %s." % (
                S["evasao"], "calculado pelos eventos do RSPE" if S.get("saldo_origem") == "calculado" else "não determinado", S["informar"]["saldo"]))
        L["ppe_triagem"] = (S or {}).get("triagem") or ""
    elif _inf_v:
        S = verificar["S"]
        I = S["informar"]
        L["ppe_status"] = "A VERIFICAR: informe a pena remanescente na fuga de %s" % I["fuga"]
        L["ppe_cor"] = "amarelo"
        L["ppe_resumo"] = ("Fuga de %s a %s (%s fora). Com o saldo %s, não prescreveu; prescreveria se o saldo na fuga fosse %s (prazo de %s, "
                           "vencido em %s)." % (I["fuga"], I["fim"], I["duracao"], _pena_ou_zero(S["saldo_max"]) if S["saldo_min"] == S["saldo_max"] else
                                                "entre %s e %s" % (_pena_ou_zero(S["saldo_min"]), _pena_ou_zero(S["saldo_max"])),
                                                I["saldo"], I["prazo"], I["limite"]))
        L["ppe_triagem"] = "O saldo na data da fuga decide: informe a pena remanescente em \"informar saldo\"."
        det.append("Conclusão: A VERIFICAR - a fuga durou o bastante para prescrever com saldo %s; o saldo usado não foi informado nem confirmado "
                   "pelo SEEU. Falta: %s." % (I["saldo"], "; ".join(faltam)))
    elif verificar:
        S = verificar["S"]
        L["ppe_status"] = "A VERIFICAR: saldo na evasão depende da imputação do cumprimento entre as condenações unificadas"
        L["ppe_cor"] = "amarelo"
        L["ppe_resumo"] = (_res_evasao(S, False) + " Uma faixa do art. 109 dá prescrição e outra não: depende do saldo por condenação no cálculo do SEEU.")
        L["ppe_triagem"] = S.get("triagem") or ""
        det.append("Conclusão: A VERIFICAR - o saldo da pena na evasão depende da imputação do cumprimento entre as condenações unificadas. Falta: " + "; ".join(faltam) + ".")
    elif correndo:
        L["ppe_status"] = "Não prescrita"
        L["ppe_cor"] = ""
        L["ppe_correndo_ate"] = rs.fmt(correndo["limite"])
        S = correndo.get("S")
        L["ppe_triagem"] = (S or {}).get("triagem") or ""
        L["ppe_resumo"] = _res_evasao(S, True) if S else \
            "%s. Com a pena de %s, o prazo é de %s%s: vence em %s." % (_desde(correndo["g0"], termo, correndo["cumprido"]), L["pena"], fmt_prazo(correndo["meses"]), _mods(L), rs.fmt(correndo["limite"]))
        _falta = (correndo["limite"] - hoje).days
        if _falta <= IMINENTE_DIAS:
            L["ppe_status"] = "Prescrição executória em %s (%s %s)" % (rs.fmt(correndo["limite"]), "falta" if _falta == 1 else "faltam", rs.pl(_falta, "dia", "dias"))
            L["ppe_cor"] = "amarelo"
            L["ppe_previsao"] = rs.fmt(correndo["limite"])
            L["ppe_dias"] = _falta
            det.append("Conferir nos autos, antes de requerer: recaptura ou prisão não registrada no RSPE e nova condenação transitada "
                       "(interrompem - art. 117, V e VI); regressão cautelar e mandado de prisão não interrompem o prazo.")
        det.append("Conclusão: prazo em curso, vence em %s%s." % (rs.fmt(correndo["limite"]),
                                                                  (" (pelo saldo máximo; pelo saldo mínimo, %s)" % S["limite_min"]) if S and S["limite_min"] and S["limite_min"] != S["limite_max"] else ""))
    else:
        L["ppe_cor"] = ""
        if L.get("ppe_nao_corre") and not L.get("ppe_encerrada"):
            L["ppe_status"] = "Não corre (%s)" % L["ppe_nao_corre"]
            det.append("Conclusão: não corre - %s; nenhum intervalo de liberdade anterior completou o prazo." % L["ppe_nao_corre"])
        elif L.get("ppe_encerrada"):
            L["ppe_status"] = "Não corre (execução encerrada em %s)" % L["ppe_encerrada"]
            det.append("Conclusão: execução encerrada em %s; não há prescrição executória a correr." % L["ppe_encerrada"])
        elif gaps:
            L["ppe_status"] = "Não prescrita"
            det.append("Conclusão: nenhum intervalo de liberdade completou o prazo; não prescrita.")
        else:
            L["ppe_status"] = "Não corre (em cumprimento)"
            det.append("Conclusão: não corre (em cumprimento).")
    if L["reinc"]:
        det.append("Reincidência do RSPE aplicada (+1/3, art. 110, caput). O aumento pressupõe a reincidência reconhecida na condenação: se a sentença "
                   "declarou o réu primário, a reincidência apurada só na execução não aumenta o prazo (STJ, RHC 6.611); o Tema 1.208/STJ trata de "
                   "benefícios, não de prescrição. O decurso posterior do período depurador (art. 64, I) não afasta o aumento (TJMS, 1607078-95.2025).")
    if not novos:
        det.append("Novo crime depois do termo inicial interrompe o prazo na data do fato (art. 117, VI): nenhum neste RSPE - conferir a certidão de "
                   "antecedentes; a data pode ser informada em \"editar dados\".")
    return det


AJUSTAVEIS = {"fato": "data_infracao", "denuncia": "data_denuncia", "sentenca": "data_sentenca", "acordao": "data_acordao",
              "transito_mp": "transito_mp", "transito": "transito_processo", "ultimo_comparecimento": "_ult_comp",
              "inicio_prd": "_ini_prd", "revogacao_sursis": "_rev_sursis", "novo_crime": "_novo_crime"}


def chave_ajuste(c, cont):
    """Chave estável da linha para os ajustes manuais: ação penal | crime | ordem (cont: contador por ação penal e crime)."""
    base = "%s|%s" % (c.get("processo_criminal") or "", rs.crimes_curto([c]) or rs.num_art(c.get("artigo")) or "?")
    cont[base] = cont.get(base, 0) + 1
    return "%s|%d" % (base, cont[base])


def _aplicar_ajuste(c, v):
    """Cópia do crime com os dados preenchidos ou corrigidos pelo operador (datas dd/mm/aaaa, pena 'XaYmZd', reincidência S/N).
    Valor ilegível é ignorado (fica o do RSPE)."""
    c2 = dict(c)
    for k, campo in AJUSTAVEIS.items():
        if v.get(k) and rs.to_date(v[k]):
            c2[campo] = rs.fmt(rs.to_date(v[k]))
    if v.get("pena") and rs.pena_para_dias(v["pena"]):
        c2["pena_imposta"] = rs.dias_para_pena(rs.pena_para_dias(v["pena"]))
    if v.get("modalidade") in ("PPL", "PRD", "SURSIS", "MS", "MS98"):
        c2["_modalidade"] = v["modalidade"]
    if v.get("reinc") in ("S", "N"):
        c2["reincidente_comum"] = v["reinc"]
        if v["reinc"] == "N":
            c2["reincidente_especifico"] = "N"
    return c2


ORIGEM_TXT = {"informado": "saldo informado pelo operador", "confirmado": "saldo confirmado (remanescente do SEEU)",
              "calculado": "saldo calculado pelos eventos", "nao_determinado": "saldo não determinado"}


def _base_do_prazo(L):
    """Deixa explícito sobre qual pena o prazo da executória foi calculado: a pena aplicada (sem fuga ou interrupção depois do
    trânsito) ou o saldo na data da fuga (art. 113), com a origem do saldo (item 6.5)."""
    S = None
    if L.get("ppe_saldos"):
        S = next((x for x in L["ppe_saldos"] if x.get("evasao") == L.get("ppe_inicio")), L["ppe_saldos"][-1])
    if S:
        faixa = rs.dias_para_pena(S["saldo_max"]) if S["saldo_min"] == S["saldo_max"] else "%s a %s" % (rs.dias_para_pena(S["saldo_min"]), rs.dias_para_pena(S["saldo_max"]))
        L["ppe_base_txt"] = "%s %s %s de %s" % (ORIGEM_TXT.get(S.get("saldo_origem"), "saldo"), faixa,
                                                ("no " + S["rotulo_evento"]) if S.get("rotulo_evento") else ("na revogação do livramento" if S.get("revogacao") else "na fuga"), S["evasao"])
        L["ppe_prazo_efetivo"] = S["prazo_max"] if (not S["prazo_min"] or S["prazo_min"] == S["prazo_max"]) else "%s a %s" % (S["prazo_min"], S["prazo_max"])
        L["ppe_prazo_efetivo"] = L["ppe_prazo_efetivo"] or "nada a prescrever"
    elif L.get("ppe_termo"):
        L["ppe_base_txt"] = "pena aplicada %s%s" % (L.get("pena", ""), "" if L.get("ppe_saldos") else " (sem fuga ou interrupção após o trânsito)")
        L["ppe_prazo_efetivo"] = L.get("prazo_ppe", "")
    else:
        L["ppe_base_txt"], L["ppe_prazo_efetivo"] = "", L.get("prazo_ppe", "")


def _explicar(L, hoje):
    """Resumo da executória em linguagem simples (topo da memória): resultado, pena que regula o prazo, por que prescreveu ou não,
    o que acontece hoje e o que conferir; e uma linha por fuga/interrupção (ppe_fugas). Só lê o que o cálculo já apurou."""
    st = L.get("ppe_status") or ""
    fugas = []
    for S in L.get("ppe_saldos") or []:
        g0 = rs.to_date(S.get("evasao") or "")
        fim = rs.to_date(S.get("fim") or "")
        aberto = not fim
        saldo = _pena_ou_zero(S["saldo_max"]) if S["saldo_min"] == S["saldo_max"] else "%s a %s" % (_pena_ou_zero(S["saldo_min"]), _pena_ou_zero(S["saldo_max"]))
        prazo = S["prazo_max"] if (not S["prazo_min"] or S["prazo_min"] == S["prazo_max"]) else "%s a %s" % (S["prazo_min"], S["prazo_max"])
        venc = S["limite_max"] if (not S["limite_min"] or S["limite_min"] == S["limite_max"]) else "%s a %s" % (S["limite_min"], S["limite_max"])
        res = S.get("resultado")
        if res == "prescrita":
            txt, cor = ("prescreveu antes da recaptura" if not aberto else "prescreveu"), "vermelho"
        elif res == "a verificar":
            txt, cor = "a verificar (saldo por condenação)", "amarelo"
        elif S.get("informar"):
            txt, cor = "a verificar: informe o saldo na fuga", "amarelo"
        elif aberto:
            txt, cor = ("prazo em curso" if S["limite_max"] else "nada a prescrever"), ""
        else:
            txt, cor = "recaptura antes do vencimento: interrompeu (art. 117, V)", "verde"
        fugas.append({"tipo": "Revogação do livramento" if S.get("revogacao") else ("Evasão" if S.get("e_evasao", True) else "Interrupção"),
                      "motivo": S.get("motivo") or "", "fuga": S.get("evasao") or "", "retorno": S.get("fim") if fim else "não houve",
                      "tempo": _dur(g0, fim or hoje), "saldo": saldo or "—", "origem": ORIGEM_TXT.get(S.get("saldo_origem"), "").replace("saldo ", ""),
                      "prazo": prazo or "nada a prescrever", "vencia": venc or "—", "resultado": txt, "cor": cor})
    L["ppe_fugas"] = fugas
    ex = []
    if not L.get("ppe_termo"):
        L["ppe_explica"] = []
        return
    ex.append("Resultado: %s." % (st[0].lower() + st[1:] if st.startswith(("Não", "Prescrição")) else st))
    Sd = next((S for S in (L.get("ppe_saldos") or []) if S.get("evasao") == L.get("ppe_inicio")), None)
    if Sd:
        sal = _pena_ou_zero(Sd["saldo_max"]) if Sd["saldo_min"] == Sd["saldo_max"] else "entre %s e %s" % (_pena_ou_zero(Sd["saldo_min"]), _pena_ou_zero(Sd["saldo_max"]))
        ex.append("Prazo: %s (art. 109, pelo saldo da pena na fuga - art. 113). Saldo na %s de %s: %s (%s)." % (
            L.get("ppe_prazo_efetivo") or "—", "revogação do livramento" if Sd.get("revogacao") else "fuga", Sd["evasao"], sal,
            ORIGEM_TXT.get(Sd.get("saldo_origem"), "").replace("saldo ", "")))
    elif L.get("ppe_base_txt"):
        ex.append("Prazo: %s (art. 109), calculado sobre a %s." % (L.get("ppe_prazo_efetivo") or "—", L["ppe_base_txt"]))
    n = len(fugas)
    if L.get("ppe_cor") == "vermelho" and Sd and rs.to_date(Sd.get("fim") or ""):
        ex.append("%s em %s (%s): com saldo %s, o prazo de %s venceu em %s, durante a fuga, antes da recaptura em %s. A recaptura posterior "
                  "não reabre o prazo já consumado (arts. 113 e 117, V)." % (
                      "Revogação do livramento" if Sd.get("revogacao") else "Fuga", Sd["evasao"], _dur(rs.to_date(Sd["evasao"]), rs.to_date(Sd["fim"])) + " fora",
                      _pena_ou_zero(Sd["saldo_max"]), Sd["prazo_max"], Sd["limite_max"], Sd["fim"]))
    elif L.get("ppe_resumo") and (L.get("ppe_cor") in ("vermelho", "amarelo") or L.get("ppe_correndo_ate")):
        ex.append(L["ppe_resumo"])
    elif n:
        ex.append("%s depois do trânsito. Em %s, a recaptura (ou a retomada do cumprimento) veio antes de o prazo vencer e interrompeu a "
                  "prescrição (art. 117, V); a cada nova fuga o prazo recomeça pelo saldo que restava (art. 113)." % (
                      "Houve 1 fuga ou interrupção" if n == 1 else "Houve %d fugas ou interrupções" % n,
                      "todas" if n > 1 else "cada uma"))
    elif st.startswith("Não corre"):
        ex.append("Desde o termo inicial (%s) a pena está em cumprimento, sem fuga: a prescrição executória não corre (arts. 116, p. único, e 117, V)." % L["ppe_termo"])
    lt = L.get("ppe_linha_tempo") or []
    ult = lt[-1] if lt else None
    if ult and not ult.get("fim") and L.get("ppe_cor") != "vermelho":
        if ult["tipo"] in ("cumprimento", "livramento"):
            ex.append("Hoje: pena em cumprimento desde %s - o prazo não corre." % ult["inicio"])
        elif ult["tipo"] == "outro_motivo":
            ex.append("Hoje: preso por outro motivo desde %s - o prazo está suspenso (art. 116, p. único)." % ult["inicio"])
        elif L.get("ppe_correndo_ate"):
            ex.append("Hoje: fora do cumprimento desde %s - o prazo corre e vence em %s." % (ult["inicio"], L["ppe_correndo_ate"]))
    if L.get("ppe_faltam") and L.get("ppe_cor") == "amarelo":
        ex.append("Para concluir: " + "; ".join(L["ppe_faltam"]) + ".")
    elif (Sd or (L.get("ppe_saldos") or [{}])[-1]).get("saldo_origem") == "calculado":
        ex.append("Conferir: o saldo na fuga foi calculado pelos eventos do RSPE; se o cálculo do SEEU daquela data trouxer outro valor, informe-o.")
    L["ppe_explica"] = ex


def _quadro(L, hoje):
    """Quadro simples da executória (o que o usuário vê primeiro): resultado, período que decide, pena que regula o prazo e
    saldo remanescente, mais um alerta de uma linha quando falta dado. O cálculo completo e a linha do tempo ficam recolhidos."""
    st, cor = L.get("ppe_status") or "", L.get("ppe_cor") or ""
    if not L.get("ppe_termo"):
        L["ppe_quadro"] = None
        return
    Q = {"resultado": st, "cor": cor, "periodo": "", "prazo": "", "saldo": "", "alerta": ""}
    inc = (" (art. 109, %s)" % L["inciso109"]) if L.get("inciso109") else " (art. 109)"
    Sd = next((S for S in (L.get("ppe_saldos") or []) if S.get("evasao") == L.get("ppe_inicio")), None)
    if Sd is None and L.get("ppe_saldos") and not L.get("ppe_inicio"):
        Sd = L["ppe_saldos"][-1]
    venc = L.get("ppe_previsao") or L.get("ppe_correndo_ate") or ""
    if cor == "vermelho":
        vtxt = "venceu em %s" % venc
    elif L.get("ppe_correndo_ate") or (Sd and not Sd.get("fim")):
        vtxt = "vence em %s" % (venc or (Sd or {}).get("limite_max") or "—")
    else:
        vtxt = ""
    if Sd:
        g0, g1 = rs.to_date(Sd["evasao"]), rs.to_date(Sd.get("fim") or "")
        rot = "Revogação do livramento" if Sd.get("revogacao") else ("Fuga" if Sd.get("e_evasao", True) else "Interrupção")
        Q["periodo"] = ("%s de %s a %s (%s fora)" % (rot, Sd["evasao"], Sd["fim"], _dur(g0, g1)) if g1 else
                        "%s em %s, sem recaptura (%s até hoje)" % (rot, Sd["evasao"], _dur(g0, hoje)))
        sal = _pena_ou_zero(Sd["saldo_max"]) if Sd["saldo_min"] == Sd["saldo_max"] else "entre %s e %s" % (_pena_ou_zero(Sd["saldo_min"]), _pena_ou_zero(Sd["saldo_max"]))
        org = ORIGEM_TXT.get(Sd.get("saldo_origem"), "").replace("saldo ", "")
        prazo = Sd["prazo_max"] if (not Sd["prazo_min"] or Sd["prazo_min"] == Sd["prazo_max"]) else "%s a %s" % (Sd["prazo_min"], Sd["prazo_max"])
        if not vtxt and g1:
            vtxt = "venceria em %s; a recaptura veio antes e interrompeu (art. 117, V)" % Sd["limite_max"] if Sd["limite_max"] else ""
        Q["prazo"] = "%s%s, contado da %s pelo saldo (art. 113)%s" % (prazo or "nada a prescrever", inc if Sd["saldo_min"] == Sd["saldo_max"] else "",
                                                                       "revogação" if Sd.get("revogacao") else "fuga", (" → " + vtxt) if vtxt else "")
        Q["saldo"] = "%s na %s de %s (%s)" % (sal, "revogação" if Sd.get("revogacao") else "fuga", Sd["evasao"], org)
    elif st.startswith("Não corre") and (L.get("ppe_nao_corre") or L.get("ppe_encerrada")):
        Q["periodo"] = L.get("ppe_nao_corre") or ("execução encerrada em " + L["ppe_encerrada"])
        Q["prazo"] = "%s pela pena aplicada de %s; hoje o prazo não corre" % (L.get("prazo_ppe") or "—", L.get("pena", ""))
    elif not (L.get("ppe_linha_tempo") and any(p["tipo"] in ("liberdade", "interrupcao", "evasao") for p in L["ppe_linha_tempo"])) and st.startswith("Não corre"):
        ini = next((p["inicio"] for p in (L.get("ppe_linha_tempo") or []) if p["tipo"] in ("cumprimento", "livramento", "prd")), L["ppe_termo"])
        Q["periodo"] = "em cumprimento desde %s, sem fuga" % ini
        Q["prazo"] = "%s pela pena aplicada de %s; enquanto cumpre, o prazo não corre" % (L.get("prazo_ppe") or "—", L.get("pena", ""))
    else:
        ini = L.get("ppe_inicio") or L["ppe_termo"]
        cump = L.get("ppe_cumprido_dias") or 0
        if ini == L["ppe_termo"] or not cump:
            Q["periodo"] = "sem início do cumprimento desde o trânsito (%s)" % L["ppe_termo"]
        else:
            Q["periodo"] = "cumprimento interrompido em %s (%s), sem fuga" % (ini, L.get("ppe_motivo") or "motivo não consta")
        Q["prazo"] = "%s pela pena aplicada de %s%s" % (L.get("ppe_prazo_efetivo") or L.get("prazo_ppe") or "—", L.get("pena", ""), (" → " + vtxt) if vtxt else "")
        pena_d = rs.pena_para_dias(L.get("pena_dias_txt") or "") or L.get("ppe_base_dias") or 0
        rest = max(0, pena_d - cump - (L.get("ppe_detracao_dias") or 0))
        if cump or L.get("ppe_detracao_dias"):
            Q["saldo"] = "%s (pena menos %s%s) - informativo: sem fuga, o prazo segue a pena aplicada" % (
                _pena_ou_zero(rest), ("%s cumpridos" % _d(cump)) if cump else "", (("%s de detração" % _d(L["ppe_detracao_dias"])) if L.get("ppe_detracao_dias") else "")
                if not cump else (" e %s de detração" % _d(L["ppe_detracao_dias"]) if L.get("ppe_detracao_dias") else ""))
        else:
            Q["saldo"] = "a pena inteira (%s)" % L.get("pena", "")
    infs = L.get("ppe_informar") or []
    if infs:
        I = infs[0]
        Q["alerta"] = "Informe o saldo na fuga de %s: com saldo %s, a fuga de %s já teria prescrito (prazo de %s)." % (I["fuga"], I["saldo"], I["duracao"], I["prazo"])
        Q["informar"] = True
    elif cor == "amarelo" and L.get("ppe_faltam"):
        Q["alerta"] = "Falta para concluir: " + L["ppe_faltam"][0] + "."
        Q["informar"] = bool(L.get("ppe_saldos"))
    elif Sd and Sd.get("saldo_origem") == "calculado" and cor == "vermelho":
        Q["alerta"] = "Confirme o saldo na fuga (calculado pelos eventos do RSPE) antes de requerer."
        Q["informar"] = True
    if not Q["alerta"] and L.get("ppe_alerta_extra"):
        Q["alerta"] = L["ppe_alerta_extra"]
    L["ppe_quadro"] = Q


def _exec(L, c, r, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia):
    """Executória pela modalidade informada: privativa de liberdade (padrão, eventos do RSPE), restritiva de direitos, sursis ou
    medida de segurança (inimputável: pena máxima em abstrato; semi-imputável, art. 98: pena substituída)."""
    mod = c.get("_modalidade")
    if mod == "PRD":
        return _executoria_prd(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses)
    if mod == "SURSIS":
        return _executoria_sursis(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses)
    if mod == "MS":
        return _executoria_ms(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia)
    det = _executoria(L, c, r, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia)
    if mod == "MS98":
        det.insert(0, "Modalidade: medida de segurança substitutiva do semi-imputável (CP, art. 98): prazo pela pena concreta substituída, como na "
                      "pena (STJ, HC 53.170).")
    return det


def _prd_campos(L, pena, fato, ppe_meses, inicio, base_dias=None):
    """Campos comuns das modalidades sem saldo (restritiva, sursis, medida de segurança): o prazo é o da pena inteira."""
    bd = base_dias or pena
    L["ppe_detracao_dias"], L["ppe_saldos"], L["ppe_faltam"] = 0, [], []
    L["ppe_meses"], L["ppe_base_dias"], L["ppe_inicio"], L["ppe_cumprido_dias"], L["ppe_restante"] = ppe_meses, bd, rs.fmt(inicio) if inicio else "", 0, False
    L["inciso109"] = rg.inciso_art109(bd)
    L["ppe_meses_art109"] = Fraction(prazo_base_anos(bd, fato) * 12)
    L["ppe_meses_integral"] = ppe_meses
    L["ppe_evasao"], L["ppe_revogacao"], L["ppe_triagem"] = "", "", ""


def _primeiro_cumprimento(ctx, depois):
    """Primeiro início de custódia ou de cumprimento registrado no RSPE depois da data (interrompe - art. 117, V)."""
    return min([a for a, _ in ctx.get("periodos") or [] if a and a > depois], default=None)


def _executoria_prd(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses):
    """Pena restritiva de direitos (modalidade informada pelo operador). O prazo é sempre o da pena aplicada, sem abater a parte
    cumprida: o art. 113 não alcança a restritiva descumprida nem a convertida em prisão (STF, HC 236.292; STJ, AgRg no HC
    640.938). Só o efetivo início (1º dia de serviço ou atividade computada) interrompe; a audiência admonitória e o termo de
    compromisso não (STJ, AgRg no HC 956.128 e AgRg no RHC 74.996). Do trânsito ao início corre o prazo; do último
    comparecimento (dia em que a execução foi interrompida - art. 112, II) corre de novo, inteiro."""
    hoje = ctx["hoje"]
    ini = rs.to_date(c.get("_ini_prd") or "")
    ult = rs.to_date(c.get("_ult_comp") or "")
    if ini and ult and ini > ult:
        ini = None
    det = ["Modalidade: pena restritiva de direitos (informado pelo operador). Pena aplicada: %s." % L["pena"],
           "Termo inicial: %s." % termo_txt,
           "Prazo pela pena aplicada, sem abater a parte cumprida: o art. 113 não alcança a restritiva descumprida ou convertida em prisão "
           "(STF, HC 236.292; STJ, AgRg no HC 640.938): %s." % fmt_prazo(ppe_meses),
           "Só o efetivo início da restritiva (1º comparecimento ao local do serviço ou atividade computada) interrompe (art. 117, V); a audiência "
           "admonitória e o termo de compromisso não interrompem (STJ, AgRg no HC 956.128)."]
    LT = []
    _prd_campos(L, pena, fato, ppe_meses, termo)
    L["ppe_linha_tempo"] = LT
    lim1 = ultimo_dia(termo, ppe_meses)
    marco = ini or ult
    # 1) do trânsito ao início efetivo
    if not marco or marco <= termo:
        LT.append({"inicio": rs.fmt(termo), "fim": "", "tipo": "liberdade", "fonte": "restritiva de direitos sem início efetivo informado",
                   "efeito": "prazo pela pena aplicada, do termo inicial (art. 112, I)", "atribuicao": "comprovada"})
        det.append("Sem início efetivo nem último comparecimento informados: prazo de %s do termo inicial; %s em %s." % (
            fmt_prazo(ppe_meses), "venceu" if lim1 < hoje else "vence", rs.fmt(lim1)))
        L["ppe_saldo_rotulo"] = "Prazo pela pena aplicada, do trânsito (sem início da restritiva informado)."
        _fecha_prd(L, det, lim1 < hoje, lim1, (lim1 - hoje).days, "Com a pena de %s, o prazo é de %s: %s em %s." % (
            L["pena"], fmt_prazo(ppe_meses), "venceu" if lim1 < hoje else "vence", rs.fmt(lim1)))
        return det
    LT.append({"inicio": rs.fmt(termo), "fim": rs.fmt(marco), "tipo": "liberdade", "fonte": "do trânsito ao %s" % ("início efetivo da restritiva" if ini else "cumprimento (início não informado)"),
               "efeito": "prazo pela pena aplicada (art. 112, I); o início efetivo interrompe (art. 117, V)", "atribuicao": "comprovada"})
    antes = lim1 < marco
    if antes and ini:
        det.append("Do trânsito (%s) ao início efetivo (%s) decorreu o prazo, que se esgotou em %s: o início posterior não restabelece a pena." % (
            rs.fmt(termo), rs.fmt(ini), rs.fmt(lim1)))
        L["ppe_saldo_rotulo"] = "Prazo consumado antes do início da restritiva."
        _fecha_prd(L, det, True, lim1, (lim1 - hoje).days, "Com a pena de %s, o prazo de %s contado do trânsito em %s se esgotou em %s, antes do início "
                                                         "efetivo da restritiva em %s." % (L["pena"], fmt_prazo(ppe_meses), rs.fmt(termo), rs.fmt(lim1), rs.fmt(ini)))
        return det
    if ini:
        det.append("Início efetivo em %s, antes do fim do prazo (%s): interrompe (art. 117, V)." % (rs.fmt(ini), rs.fmt(lim1)))
    # 2) cumprimento e 3) do último comparecimento
    if not ult:
        LT.append({"inicio": rs.fmt(ini), "fim": "", "tipo": "prd", "fonte": "restritiva em cumprimento desde %s" % rs.fmt(ini),
                   "efeito": "cumprimento da pena: o prazo não corre", "atribuicao": "comprovada"})
        det.append("Restritiva em cumprimento desde %s, sem último comparecimento informado: o prazo não corre." % rs.fmt(ini))
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "Não corre (em cumprimento)", "", "", None
        L["ppe_resumo"], L["ppe_saldo_rotulo"] = "Restritiva em cumprimento desde %s: a prescrição não corre." % rs.fmt(ini), ""
        det.append("Conclusão: não corre (em cumprimento).")
        return det
    LT.append({"inicio": rs.fmt(ini or termo), "fim": rs.fmt(ult), "tipo": "prd", "fonte": "cumprimento da restritiva até o último comparecimento",
               "efeito": "cumprimento da pena: o prazo não corre", "atribuicao": "comprovada"})
    retomada = _primeiro_cumprimento(ctx, ult)
    lim2 = ultimo_dia(ult, ppe_meses)
    LT.append({"inicio": rs.fmt(ult), "fim": rs.fmt(retomada) if retomada else "", "tipo": "liberdade", "rotulo": "Último comparecimento",
               "fonte": "último comparecimento em %s (informado pelo operador)" % rs.fmt(ult),
               "efeito": "descumprimento: o prazo corre de novo pela pena aplicada (art. 112, II), sem o art. 113", "atribuicao": "comprovada"})
    L["ppe_inicio"] = rs.fmt(ult)
    L["ppe_ult_comp"] = rs.fmt(ult)
    L["ppe_saldo_rotulo"] = "Prazo pela pena aplicada, do último comparecimento."
    ref = retomada or hoje
    det.append("Último comparecimento em %s: a execução ficou interrompida (art. 112, II); prazo de %s pela pena aplicada, %s em %s%s." % (
        rs.fmt(ult), fmt_prazo(ppe_meses), "venceu" if lim2 < ref else "vence", rs.fmt(lim2),
        ("; prisão ou retomada em %s %s" % (rs.fmt(retomada), "depois de consumada" if lim2 < retomada else "interrompeu (art. 117, V)")) if retomada else ""))
    if marco == ult and not ini:
        det.append("Início efetivo não informado: presume-se que ocorreu antes de %s; se o único ato foi a audiência admonitória, conta-se do trânsito." % rs.fmt(lim1))
        if antes:
            L["ppe_faltam"] = ["data do efetivo início da restritiva (1º dia de serviço): se posterior a %s, a prescrição se consumou antes dele" % rs.fmt(lim1)]
    det.append("Conferir se a restritiva foi convertida em privativa de liberdade (CP, art. 44, § 4º): a prisão para cumprir a pena convertida interrompe; o prazo segue pela pena inteira.")
    if retomada and lim2 >= retomada:
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "Não corre (cumprimento retomado)", "", "", None
        L["ppe_resumo"] = "Último comparecimento em %s; retomada em %s, antes do fim do prazo (%s)." % (rs.fmt(ult), rs.fmt(retomada), rs.fmt(lim2))
        det.append("Conclusão: cumprimento retomado antes do fim do prazo.")
        return det
    if L["ppe_faltam"] and not lim2 < ref:
        L["ppe_status"] = "A VERIFICAR: data do efetivo início da restritiva não informada"
        L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "amarelo", "", None
        L["ppe_resumo"] = "Do trânsito em %s o prazo se esgotaria em %s, antes do último comparecimento (%s): depende da data do início efetivo." % (
            rs.fmt(termo), rs.fmt(lim1), rs.fmt(ult))
        det.append("Conclusão: A VERIFICAR - informe o início efetivo da restritiva.")
        return det
    _fecha_prd(L, det, lim2 < ref, lim2, (lim2 - hoje).days, "Último comparecimento em %s; com a pena de %s, o prazo é de %s: %s em %s." % (
        rs.fmt(ult), L["pena"], fmt_prazo(ppe_meses), "venceu" if lim2 < ref else "vence", rs.fmt(lim2)))
    return det


def _executoria_sursis(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses):
    """Suspensão condicional da pena (modalidade informada pelo operador): no período de prova a prescrição não corre (STF, HC
    91.562); revogado o sursis, corre da decisão que o revoga, pela pena inteira (CP, art. 112, I, parte final; STJ, AgRg no HC
    514.499). Expirado o período sem revogação, a pena se extingue (CP, art. 82)."""
    hoje = ctx["hoje"]
    rev = rs.to_date(c.get("_rev_sursis") or "")
    det = ["Modalidade: suspensão condicional da pena - sursis (informado pelo operador). Pena suspensa: %s." % L["pena"],
           "Termo inicial da condenação: %s." % termo_txt,
           "No período de prova a prescrição não corre (STF, HC 91.562). A regra de que a audiência admonitória não inicia o cumprimento vale "
           "para as restritivas, não para o sursis (STJ, AgRg no HC 514.499)."]
    LT = []
    _prd_campos(L, pena, fato, ppe_meses, rev or termo)
    L["ppe_linha_tempo"] = LT
    if not rev:
        LT.append({"inicio": rs.fmt(termo), "fim": "", "tipo": "prd", "fonte": "período de prova do sursis", "efeito": "a prescrição não corre",
                   "atribuicao": "comprovada"})
        det.append("Sem revogação informada: a prescrição não corre; expirado o período de prova sem revogação, a pena se extingue (CP, art. 82).")
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "Não corre (período de prova do sursis)", "", "", None
        L["ppe_resumo"], L["ppe_saldo_rotulo"] = "Sursis sem revogação informada: a prescrição não corre no período de prova.", ""
        det.append("Conclusão: não corre (período de prova).")
        return det
    L["ppe_rev_sursis"] = rs.fmt(rev)
    retomada = _primeiro_cumprimento(ctx, rev)
    lim = ultimo_dia(rev, ppe_meses)
    ref = retomada or hoje
    LT.append({"inicio": rs.fmt(termo), "fim": rs.fmt(rev), "tipo": "prd", "fonte": "período de prova do sursis", "efeito": "a prescrição não corre", "atribuicao": "comprovada"})
    LT.append({"inicio": rs.fmt(rev), "fim": rs.fmt(retomada) if retomada else "", "tipo": "liberdade", "rotulo": "Revogação do sursis",
               "fonte": "revogação do sursis em %s (informada pelo operador)" % rs.fmt(rev),
               "efeito": "prazo pela pena inteira, da revogação (art. 112, I)", "atribuicao": "comprovada"})
    L["ppe_saldo_rotulo"] = "Prazo pela pena inteira, da revogação do sursis."
    det.append("Sursis revogado em %s: prazo de %s pela pena inteira, %s em %s%s." % (
        rs.fmt(rev), fmt_prazo(ppe_meses), "venceu" if lim < ref else "vence", rs.fmt(lim),
        ("; prisão em %s %s" % (rs.fmt(retomada), "depois de consumada" if lim < retomada else "interrompeu (art. 117, V)")) if retomada else ""))
    if retomada and lim >= retomada:
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "Não corre (cumprimento iniciado)", "", "", None
        L["ppe_resumo"] = "Sursis revogado em %s; prisão em %s, antes do fim do prazo (%s)." % (rs.fmt(rev), rs.fmt(retomada), rs.fmt(lim))
        det.append("Conclusão: cumprimento iniciado antes do fim do prazo.")
        return det
    _fecha_prd(L, det, lim < ref, lim, (lim - hoje).days, "Sursis revogado em %s; com a pena de %s, o prazo é de %s: %s em %s." % (
        rs.fmt(rev), L["pena"], fmt_prazo(ppe_meses), "venceu" if lim < ref else "vence", rs.fmt(lim)))
    return det


def _executoria_ms(L, c, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia):
    """Medida de segurança do inimputável (absolvição imprópria): prazo pela pena máxima em abstrato do crime (STJ, AgRg no
    REsp 1.667.508; STF, HC 97.621), interrompido pelo início do cumprimento; a duração não passa do máximo cominado (STJ,
    Súmula 527). Sem reincidência: não há condenação."""
    hoje = ctx["hoje"]
    L["reinc"] = False
    pmax = rs.pena_maxima_abstrata(c) or 0
    det = ["Modalidade: medida de segurança - inimputável, absolvição imprópria (informado pelo operador)."]
    if not pmax:
        det.append("Pena máxima em abstrato não identificada no tipo penal: informe-a na Auditoria para calcular o prazo.")
        _prd_campos(L, pena, fato, ppe_meses, termo)
        L["ppe_linha_tempo"] = []
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "A VERIFICAR: pena máxima em abstrato não identificada", "amarelo", "", None
        L["ppe_faltam"] = ["pena máxima em abstrato do crime (prazo da medida de segurança)"]
        L["ppe_resumo"] = "Medida de segurança: o prazo se regula pela pena máxima em abstrato, não identificada."
        return det
    meses = Fraction(prazo_base_anos(pmax, fato) * 12) * (Fraction(1, 2) if meia else 1)
    _prd_campos(L, pena, fato, meses, termo, pmax)
    L["prazo_ppe"] = fmt_prazo(meses) + (" (½ art. 115)" if meia else "")
    retomada = _primeiro_cumprimento(ctx, termo - timedelta(days=1))
    lim = ultimo_dia(termo, meses)
    ref = retomada or hoje
    L["ppe_linha_tempo"] = [{"inicio": rs.fmt(termo), "fim": rs.fmt(retomada) if retomada else "", "tipo": "liberdade", "fonte": "trânsito da absolvição imprópria",
                             "efeito": "prazo pela pena máxima em abstrato (art. 109)", "atribuicao": "comprovada"}]
    det += ["Termo inicial: %s." % termo_txt,
            "Prazo pela pena máxima em abstrato (%s): %s%s (STJ, AgRg no REsp 1.667.508; STF, HC 97.621). A duração da medida não passa do "
            "máximo cominado (STJ, Súmula 527)." % (rs.dias_para_pena(pmax), fmt_prazo(meses), " (½ art. 115)" if meia else ""),
            "%s em %s%s." % ("Venceu" if lim < ref else "Vence", rs.fmt(lim), ("; início do cumprimento em %s %s" % (
                rs.fmt(retomada), "depois de consumada" if lim < retomada else "interrompeu (art. 117, V)")) if retomada else "")]
    L["ppe_saldo_rotulo"] = "Prazo pela pena máxima em abstrato."
    if retomada and lim >= retomada:
        L["ppe_status"], L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "Não corre (medida em cumprimento)", "", "", None
        L["ppe_resumo"] = "Medida de segurança iniciada em %s, antes do fim do prazo (%s)." % (rs.fmt(retomada), rs.fmt(lim))
        det.append("Conclusão: medida em cumprimento.")
        return det
    _fecha_prd(L, det, lim < ref, lim, (lim - hoje).days, "Medida de segurança: prazo de %s pela pena máxima em abstrato (%s): %s em %s." % (
        fmt_prazo(meses), rs.dias_para_pena(pmax), "venceu" if lim < ref else "vence", rs.fmt(lim)))
    return det


def _fecha_prd(L, det, pres, lim, falta, resumo):
    L["ppe_resumo"] = resumo
    if pres:
        L["ppe_status"], L["ppe_cor"] = "Prescrição executória aparente em %s" % rs.fmt(lim), "vermelho"
        L["ppe_previsao"], L["ppe_dias"] = rs.fmt(lim), falta
        det.append("Conclusão: prescrição da pretensão executória aparente em %s." % rs.fmt(lim))
        det.append("Antes de requerer: conferir conversão em privativa, recaptura ou nova condenação não registradas no RSPE (interrompem - art. 117, V e VI).")
    elif falta <= IMINENTE_DIAS:
        L["ppe_status"] = "Prescrição executória em %s (%s %s)" % (rs.fmt(lim), "falta" if falta == 1 else "faltam", rs.pl(falta, "dia", "dias"))
        L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"], L["ppe_correndo_ate"] = "amarelo", rs.fmt(lim), falta, rs.fmt(lim)
        det.append("Conclusão: prazo em curso, vence em %s." % rs.fmt(lim))
    else:
        L["ppe_status"], L["ppe_cor"], L["ppe_correndo_ate"] = "Não prescrita", "", rs.fmt(lim)
        det.append("Conclusão: prazo em curso, vence em %s." % rs.fmt(lim))


def _classe(L):
    """p = prescrita, v = a verificar, n = não prescrita (para comparar hipóteses de reincidência e idade)."""
    if L.get("ppe_cor") == "vermelho":
        return "p"
    return "v" if (L.get("ppe_status") or "").startswith("A VERIFICAR") else "n"


# ---------------- fundamentação para a petição (padrão do programa: título, fatos e fundamentos, pedido) ----------------
def _ext(dias):
    """dias -> '2 anos, 5 meses e 27 dias' ('0 dia' para zero)."""
    if not dias:
        return "0 dia"
    m = rs.re.match(r"^(\d+)a(\d+)m(\d+)d$", rs.dias_para_pena(int(dias)) or "")
    if not m:
        return rs.pl(int(dias), "dia", "dias")
    a, me, d = (int(x) for x in m.groups())
    p = [("%d ano%s" % (a, "s" if a != 1 else "")) if a else "", ("%d %s" % (me, "meses" if me != 1 else "mês")) if me else "",
         ("%d dia%s" % (d, "s" if d != 1 else "")) if d else ""]
    p = [x for x in p if x]
    return p[0] if len(p) == 1 else ", ".join(p[:-1]) + " e " + p[-1]


def _inc_de(dias):
    y = dias / 365.0
    return "VI" if y < 1 else "V" if y <= 2 else "IV" if y <= 4 else "III" if y <= 8 else "II" if y <= 12 else "I"


def fundamentacao(L, parte):
    """Texto pronto para a petição sobre a prescrição do crime L: 'pp' (punitiva - retroativa/intercorrente) ou 'pe'
    (executória - pela pena aplicada ou pelo saldo na evasão/revogação do livramento, arts. 113 e 119)."""
    cab = "DA PRESCRIÇÃO DA %s - %s%s" % ("PRETENSÃO PUNITIVA" if parte == "pp" else "PRETENSÃO EXECUTÓRIA", L.get("rotulo") or L.get("crime") or "",
                                          (" (autos %s)" % L["proc_crim"]) if L.get("proc_crim") else "")
    fato = rs.to_date(L.get("fato") or "")
    antiga = bool(fato and fato < date(2010, 5, 6))
    pena_d = rs.pena_para_dias(L.get("orig", {}).get("pena") if isinstance(L.get("orig"), dict) else None) or rs.pena_livre(L.get("pena") or "") or 0

    def mods(pe):
        m = []
        if L.get("art115"):
            m.append("reduzido à metade em razão da idade (CP, art. 115)")
        if L.get("reinc") and pe:
            m.append("acrescido de 1/3 pela reincidência (CP, art. 110, caput)")
        return (", " + " e ".join(m)) if m else ""

    def red(inc):
        return " (redação anterior à Lei 12.234/2010, vigente à data do fato - 2 anos)" if (antiga and inc == "VI") else ""
    if parte == "pp":
        m = rs.re.search(r"✘\s*(.+?):\s*(\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4}) = (.+?) \(prazo (.+?), vence (\d{2}/\d{2}/\d{4})\)", L.get("retro_detalhe") or "")
        if not m:
            return ""
        nome, a, b, dur, prazo, vence = m.groups()
        mk = {"fato → denúncia": ("a data do fato", "", "o recebimento da denúncia", "CP, art. 117, I", "retroativa - CP, art. 110, § 1º, na redação anterior à Lei 12.234/2010"),
              "denúncia → sentença": ("o recebimento da denúncia", "CP, art. 117, I", "a sentença condenatória", "CP, art. 117, IV", "retroativa - CP, art. 110, § 1º"),
              "sentença → acórdão": ("a sentença condenatória", "CP, art. 117, IV", "o acórdão condenatório", "CP, art. 117, IV", "intercorrente - CP, art. 110, § 1º"),
              "acórdão → trânsito": ("o acórdão condenatório", "CP, art. 117, IV", "o trânsito em julgado", "", "intercorrente - CP, art. 110, § 1º"),
              "sentença → trânsito": ("a sentença condenatória", "CP, art. 117, IV", "o trânsito em julgado", "", "intercorrente - CP, art. 110, § 1º")}.get(nome)
        if not mk:
            return ""
        inc = _inc_de(pena_d) if pena_d else ""
        return "%s\nCom trânsito em julgado para a acusação, a prescrição regula-se pela pena aplicada (%s): prazo do art. 109, %s, do Código Penal%s%s: %s. " \
               "Entre %s (%s%s) e %s (%s%s) decorreram %s, superando o prazo, que se esgotou em %s (prescrição %s).\n" \
               "Operou-se a prescrição da pretensão punitiva, requerendo-se a declaração da extinção da punibilidade (CP, art. 107, IV), com o afastamento " \
               "dos efeitos da condenação." % (cab, L.get("pena", ""), inc, red(inc), mods(False), prazo, mk[0], a, ("; " + mk[1]) if mk[1] else "",
                                               mk[2], b, ("; " + mk[3]) if mk[3] else "", dur, vence, mk[4])
    # executória
    sal = L.get("ppe_saldos") or []
    S = next((x for x in sal if x.get("resultado") == "prescrita"), None) or next((x for x in sal if x.get("resultado") == "a verificar" and x.get("limite_min")), None)
    st = L.get("ppe_status") or ""
    if S:
        ev = "revogação do livramento condicional" if S.get("revogacao") else "fuga"
        fim = S.get("fim") if S.get("fim") and S.get("fim") != "hoje" else ""
        cab2 = ("%s\nA condenação a %s (fato em %s; trânsito em julgado em %s) teve o cumprimento interrompido pela %s em %s. Nos termos do art. 113 do "
                "Código Penal, no caso de evadir-se o condenado ou de revogar-se o livramento condicional, a prescrição é regulada pelo tempo que resta "
                "da pena, calculado para cada condenação isoladamente (CP, art. 119; STJ, AgRg no REsp 2.256.555). Até essa data, a execução unificada "
                "registrava %s dias de cumprimento%s" % (cab, L.get("pena", ""), L.get("fato") or "—", L.get("ppe_termo") or "—", ev, S.get("evasao", ""),
                                                         S.get("cumprido_desde_termo", 0), (" e %s dias remidos" % S["remicao"]) if S.get("remicao") else ""))

        def base(sd, pz, lim):
            inc = _inc_de(sd)
            return "Para esse saldo, o prazo prescricional é o do art. 109, %s, do Código Penal%s%s: %s, que se esgotou em %s" % (inc, red(inc), mods(True), pz, lim)
        if S.get("resultado") == "prescrita":
            txt = (", de modo que o saldo imputável a esta condenação era de, no máximo, %s. %s%s%s\nOperou-se, portanto, a prescrição da pretensão "
                   "executória, impondo-se a declaração da extinção da punibilidade quanto a esta condenação (CP, art. 107, IV, c/c art. 119), com as "
                   "comunicações e anotações devidas." % (
                       _ext(S.get("saldo_max")), base(S.get("saldo_max") or 0, S.get("prazo_max"), S.get("limite_max")),
                       (", antes da recaptura/reinício do cumprimento em %s, causa interruptiva posterior (CP, art. 117, V)." % fim) if fim else ", sem nova causa interruptiva (CP, art. 117).",
                       " Ainda que se considere integralmente cumprida esta pena na imputação do tempo, a solução é a mesma: extinção da punibilidade." if not S.get("saldo_min") else ""))
        else:
            hip = [h for h, k in (("que coincide com a ordem do art. 76 do CP (execução primeiro da pena mais grave)", "art76"),
                                  ("que coincide com a ordem cronológica do trânsito em julgado (STJ, HC 627.646)", "cronologica"))
                   if (S.get(k) or {}).get("resultado") == "prescrita"]
            txt = (". O RSPE não informa a imputação desse tempo entre as condenações unificadas. Na hipótese mais favorável - o tempo cumprido imputado "
                   "primeiro a esta condenação%s -, o saldo era de %s. %s%s\nAssim, requer-se a imputação do tempo cumprido na forma mais favorável e o "
                   "reconhecimento da prescrição da pretensão executória, com a extinção da punibilidade quanto a esta condenação (CP, art. 107, IV, c/c art. 119)." % (
                       (", " + " e ".join(hip)) if hip else "", _ext(S.get("saldo_min")), base(S.get("saldo_min") or 0, S.get("prazo_min") or S.get("prazo_max"), S.get("limite_min")),
                       (", antes da recaptura/reinício do cumprimento em %s (CP, art. 117, V)." % fim) if fim else "."))
        return cab2 + txt
    inc = (L.get("inciso109") or "").replace("art. 109, ", "")
    prazo = fmt_prazo(L["ppe_meses"]) if L.get("ppe_meses") is not None else (L.get("prazo_ppe") or "").split(" (")[0]
    if not rs.re.search(r"aparente", st, rs.re.I):
        return ""
    d = (rs.re.search(r"\d{2}/\d{2}/\d{4}", st) or [None])[0] if rs.re.search(r"\d{2}/\d{2}/\d{4}", st) else ""
    reg = "o do art. 109, %s, do Código Penal%s%s: %s" % (inc or "—", red(inc), mods(True), prazo or "—")
    mod = L.get("modalidade") or "PPL"
    ini, termo = L.get("ppe_inicio") or "", L.get("ppe_termo") or "—"
    if mod == "MS":
        fatos = ("A absolvição imprópria (fato em %s) transitou em julgado em %s. Na medida de segurança do inimputável, a prescrição regula-se pela "
                 "pena máxima em abstrato do crime (STJ, AgRg no REsp 1.667.508; STF, HC 97.621), e o prazo é %s" % (L.get("fato") or "—", termo, reg))
    elif mod == "SURSIS" and L.get("ppe_rev_sursis"):
        fatos = ("A condenação a %s (fato em %s) teve a pena suspensa, e o sursis foi revogado em %s. Revogado o sursis, a prescrição corre da decisão "
                 "que o revoga, pela pena inteira (CP, art. 112, I, parte final; STJ, AgRg no HC 514.499), e o prazo é %s" % (
                     L.get("pena", ""), L.get("fato") or "—", L["ppe_rev_sursis"], reg))
    elif mod == "PRD" and L.get("ppe_ult_comp"):
        fatos = ("A condenação a %s (fato em %s), substituída por restritiva de direitos, teve o último comparecimento em %s, quando a execução foi "
                 "interrompida (CP, art. 112, II). Como o art. 113 não alcança a restritiva descumprida (STF, HC 236.292; STJ, AgRg no HC 640.938), "
                 "o prazo se regula pela pena aplicada, sem abater a parte cumprida, e é %s" % (L.get("pena", ""), L.get("fato") or "—", L["ppe_ult_comp"], reg))
    elif L.get("ppe_novo_crime"):
        fatos = ("A condenação a %s (fato em %s) transitou em julgado em %s. O novo crime praticado em %s interrompeu a prescrição, e todo o prazo "
                 "recomeçou nessa data (CP, art. 117, VI, e § 2º; STF, HC 230.334). Regulada pela pena aplicada (CP, art. 110, caput), o prazo é %s" % (
                     L.get("pena", ""), L.get("fato") or "—", termo, L["ppe_novo_crime"], reg))
    elif ini and ini != termo and L.get("ppe_motivo"):
        fatos = ("A condenação a %s (fato em %s) transitou em julgado em %s, e o cumprimento foi interrompido em %s (%s), sem fuga nem revogação do "
                 "livramento. Fora dessas duas hipóteses, a prescrição regula-se pela pena aplicada, sem o art. 113 (STF, HC 236.292; STJ, RHC 67.403), "
                 "e corre de novo desde a interrupção (CP, art. 112, II): o prazo é %s" % (L.get("pena", ""), L.get("fato") or "—", termo, ini, L["ppe_motivo"], reg))
    else:
        fatos = ("A condenação a %s (fato em %s) transitou em julgado em %s, termo inicial da prescrição da pretensão executória (CP, art. 112, I). "
                 "Regulada pela pena aplicada, sem desconto da detração (CP, art. 110, caput; STJ, AgRg no HC 967.565), o prazo é %s" % (
                     L.get("pena", ""), L.get("fato") or "—", termo, reg))
    return ("%s\n%s, que se esgotou em %s, sem causa interruptiva no período (CP, art. 117, V e VI).\nOperou-se a prescrição da pretensão executória, "
            "requerendo-se a declaração da extinção da punibilidade (CP, art. 107, IV)." % (cab, fatos, d))


def analisar(r, hoje=None):
    """r = registro extraído (rspe_scraper.extrair). Devolve dict com linhas por crime e resumo.
    r["_presc_ajustes"] (opcional, só em memória): {chave_ajuste: {"valores": {...}, "saldos": {dd/mm/aaaa da fuga: dias}, "_data": ...}}
    com os dados preenchidos ou corrigidos pelo operador; a análise é refeita com eles."""
    hoje = hoje or date.today()
    aj_all = r.get("_presc_ajustes") or {}
    _cont = {}
    crimes = []
    for c0 in r.get("_crimes", []):
        ch = chave_ajuste(c0, _cont)
        aj = aj_all.get(ch) or {}
        c2 = _aplicar_ajuste(c0, aj.get("valores") or {})
        c2["_chave_ajuste"], c2["_ajuste"], c2["_orig"] = ch, aj, c0
        crimes.append(c2)
    nasc = rs.to_date(r.get("data_nascimento") or "")
    pena_total = rs.pena_para_dias(r.get("pena_total")) or 0
    eventos = r.get("_eventos", [])
    incidentes = r.get("_incidentes", [])
    extras = []
    periodos, avisos_gerais = periodos_cumprimento(r, hoje, extras)
    periodos_det = rs.periodos_custodia_detalhe(eventos)
    remicoes = []
    for i in incidentes:
        if rs.e_remicao_concedida(i):
            n = rs.dias_de(i.get("complemento", ""))
            if n is not None:
                remicoes.append((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), n))
    em_custodia = any(a <= hoje and (b is None or b > hoje) for a, b in periodos)
    inicio_def = [rs.to_date(e.get("data", "")) for e in eventos
                  if rs.re.search(r"DEFINITIV|CUMPRIMENTO", (e.get("motivo") or "") + " " + (e.get("tipo") or ""), rs.re.I)
                  and "INTERRUP" not in (e.get("tipo") or "").upper()]
    inicio_def = sorted(x for x in inicio_def if x)
    menor21, maior70, arts_sexuais = rg.art115()
    LEI_12234 = rg.data_lei_12234()
    TEMA_788 = rg.data_tema_788()
    ACRESC = rg.acrescimo_reincidencia()

    linhas = []
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    ctx = {"hoje": hoje, "eventos": eventos, "incidentes": incidentes, "periodos_det": periodos_det, "extras": extras,
           "extras_lc": set(rs.periodos_livramento(eventos, incidentes)), "remicoes": remicoes, "ativos": ativos,
           "crimes": crimes, "TEMA_788": TEMA_788, "em_custodia": em_custodia, "periodos": periodos}
    for c in crimes:
        if c.get("extinto", "").upper().startswith("S"):
            continue  # só crimes ativos
        L = {
            "crime": rs.crimes_curto([c]),
            "descricao": c.get("tipo_penal", ""),
            "proc_crim": c.get("processo_criminal", ""),
            "fato": c.get("data_infracao", ""),
            "denuncia": c.get("data_denuncia", ""),
            "sentenca": c.get("data_sentenca", ""),
            "transito_mp": c.get("transito_mp", ""),
            "transito": c.get("transito_processo", ""),
            "acordao": c.get("data_acordao", ""),
            "modalidade": c.get("_modalidade") or "PPL",
            "ultimo_comparecimento": c.get("_ult_comp", ""),
            "inicio_prd": c.get("_ini_prd", ""), "revogacao_sursis": c.get("_rev_sursis", ""), "novo_crime": c.get("_novo_crime", ""),
            "pena": rs.pena_extenso(rs.pena_curta(c.get("pena_imposta") or c.get("pena_total_processo"))),
            "reinc": c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S",
            "avisos": list(avisos_gerais),
        }
        # dados importados (para o formulário de edição) e ajustes gravados
        _o, _aj = c["_orig"], c["_ajuste"]
        L["chave_ajuste"], L["ajuste"], L["ajustado"] = c["_chave_ajuste"], _aj, bool(_aj.get("valores") or _aj.get("saldos"))
        L["orig"] = {"fato": _o.get("data_infracao", ""), "denuncia": _o.get("data_denuncia", ""), "sentenca": _o.get("data_sentenca", ""),
                     "transito_mp": _o.get("transito_mp", ""), "transito": _o.get("transito_processo", ""),
                     "pena": rs.pena_curta(_o.get("pena_imposta") or _o.get("pena_total_processo")),
                     "reinc": "S" if (_o.get("reincidente_comum") == "S" or _o.get("reincidente_especifico") == "S") else ("N" if _o.get("reincidente_comum") == "N" else ""),
                     "nascimento": r.get("data_nascimento") or "", "acordao": "", "modalidade": "PPL", "ultimo_comparecimento": "",
                     "inicio_prd": "", "revogacao_sursis": "", "novo_crime": "",
                     "convertida": "CONVERTIDA" in (_o.get("pena_total_processo") or "").upper()}
        if L["ajustado"]:
            L["avisos"].append("dados ajustados manualmente em %s: %s" % ((_aj.get("_data") or "?").split(" ")[0], ", ".join(
                ["%s %s" % (k, v) for k, v in (_aj.get("valores") or {}).items()] + ["saldo na fuga de %s: %s" % (d_, rs.dias_para_pena(n_)) for d_, n_ in (_aj.get("saldos") or {}).items()])))
        ctx["saldos_inf"] = {k_: int(v_) for k_, v_ in (_aj.get("saldos") or {}).items() if str(v_).lstrip("-").isdigit()}
        ctx["ajuste_data"] = (_aj.get("_data") or "").split(" ")[0]
        reinc_desc = (c.get("reincidente_comum") not in ("S", "N")) and c.get("reincidente_especifico") != "S"
        # reincidência marcada sem base no próprio RSPE (mesmo critério da Auditoria: nenhuma condenação deste RSPE transitou
        # antes do fato); não confirmada pelo operador em "editar dados" -> o +1/3 é conferido também sem ele
        _fx = rs.to_date(L["fato"] or "")
        reinc_sem_base = bool(L["reinc"] and _fx and (_aj.get("valores") or {}).get("reinc") not in ("S", "N") and not any(
            o is not c and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "")
            and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < _fx for o in crimes))
        L["reinc_sem_base"] = reinc_sem_base
        pena = rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo"))
        if "CONVERTIDA" in (c.get("pena_total_processo") or "").upper():
            L["avisos"].append("pena originalmente substituída por restritiva de direitos (CONVERTIDA): o período de cumprimento da PRD não consta no RSPE e também suspende/interrompe a executória - conferir")
        fato, den, sent = (rs.to_date(x or "") for x in (L["fato"], L["denuncia"], L["sentenca"]))
        tmp, tpr = rs.to_date(L["transito_mp"] or ""), rs.to_date(L["transito"] or "")
        extinto = c.get("extinto", "").upper().startswith("S")

        # art. 115
        meia = False
        art_cp = rs.num_art(c.get("artigo"))
        sexual = (rs.num_lei(c.get("lei")) in ("2848", "") and art_cp in arts_sexuais)
        if nasc:
            i_fato, i_sent = _idade(nasc, fato), _idade(nasc, sent)
            if i_fato is not None and i_fato < menor21:
                meia = True
                L["avisos"].append("art. 115: menor de %s na data do fato (%s) - prazos pela metade" % (rs.pl(menor21, "ano", "anos"), rs.pl(i_fato, "ano", "anos")))
            if i_sent is not None and i_sent >= maior70:
                meia = True
                L["avisos"].append("art. 115: maior de %s na sentença (%s) - prazos pela metade" % (rs.pl(maior70, "ano", "anos"), rs.pl(i_sent, "ano", "anos")))
            if meia and sexual:
                LEI_15160 = rg.data_lei_15160()
                if fato and LEI_15160 and fato < LEI_15160:
                    L["avisos"].append("art. 115 mantido: a exceção de violência sexual contra a mulher (Lei 15.160/2025) só alcança fatos a partir de %s (irretroatividade da lei mais gravosa)" % rs.fmt(LEI_15160))
                else:
                    meia = False
                    L["avisos"].append("art. 115 NÃO aplicado: exceção de violência sexual contra a mulher (Lei 15.160/2025, art. %s) - conferir a vítima" % art_cp)
        else:
            L["avisos"].append("sem data de nascimento: art. 115 não aferido")
        _v115 = (c["_ajuste"].get("valores") or {}).get("art115")
        if _v115 in ("sim", "nao"):
            meia = _v115 == "sim"
            L["avisos"].append("art. 115 %s por informação do operador" % ("aplicado" if meia else "afastado"))
        meia_desc = nasc is None and _v115 not in ("sim", "nao")
        L["art115"] = meia

        if not pena:
            L.update(retro_status="sem pena no RSPE", retro_cor="cinza", ppe_status="sem pena no RSPE", ppe_cor="cinza",
                     prazo_ppp="", prazo_ppe="", ppe_termo="", ppe_previsao="", retro_detalhe="", ppe_detalhe="")
            linhas.append(L)
            continue
        if extinto:
            _mot = (c.get("extincao_motivo") or "").strip()
            _dt = c.get("data_extincao") or ""
            _txt = "Extinta" + ((" · " + _mot.lower()) if _mot else "") + ((" em " + _dt) if _dt else "")
            L.update(retro_status=_txt, retro_cor="cinza", ppe_status=_txt, ppe_cor="cinza",
                     prazo_ppp="", prazo_ppe="", ppe_termo="", ppe_previsao="",
                     retro_detalhe="Punibilidade já extinta segundo o RSPE" + ((" (" + c["extincao_fonte"] + ")") if c.get("extincao_fonte") else "") + ".", ppe_detalhe="")
            linhas.append(L)
            continue

        impr = imprescritivel(c)
        if impr and impr[0] == "sim":
            _t = "Imprescritível (CF, art. 5º, XLII)"
            L.update(retro_status=_t, retro_cor="cinza", ppe_status=_t, ppe_cor="cinza", prazo_ppp="", prazo_ppe="", ppe_termo="", ppe_previsao="",
                     ppe_dias=None, retro_detalhe=impr[1][0].upper() + impr[1][1:] + ".", ppe_detalhe=impr[1][0].upper() + impr[1][1:] + ".",
                     ppe_linha_tempo=[], ppe_saldos=[], ppe_faltam=[])
            L["avisos"].append(impr[1])
            linhas.append(L)
            continue
        base_meses = prazo_base_anos(pena, fato) * 12
        L["inciso109"] = rg.inciso_art109(pena)
        if fato and fato < LEI_12234 and prazo_base_anos(pena, fato) != prazo_base_anos(pena):
            L["avisos"].append("art. 109, VI, na redação anterior à Lei 12.234/2010 (fato de %s): prazo de %s" % (rs.fmt(fato), rs.pl(prazo_base_anos(pena, fato), "ano", "anos")))
        # Súmula 497/STF: o acréscimo da continuidade não entra no prazo; o RSPE só traz a pena com o aumento
        cont = _continuidade(c)
        aviso497 = ("crime continuado (%s): o prazo se calcula sem o acréscimo da continuidade (STF, Súmula 497); "
                    "o RSPE não traz a pena sem o aumento - a verificar na sentença" % cont) if cont else ""
        if _concurso_formal(c):
            aviso497 = ((aviso497 + "; ") if aviso497 else "") + ("concurso formal (art. 70 do CP): o prazo se calcula pela pena de cada crime, sem a "
                                                                   "exasperação (CP, art. 119; STJ, RHC 14.277) - a verificar na sentença")
        if aviso497:
            L["avisos"].append(aviso497)
        # ---------------- pretensão punitiva (retroativa / intercorrente) ----------------
        ppp_meses = Fraction(base_meses) * (Fraction(1, 2) if meia else 1)
        L["prazo_ppp"] = fmt_prazo(ppp_meses)
        intervalos = []
        if fato and den and fato < LEI_12234:
            intervalos.append(("fato → denúncia", fato, den))
        if den and sent:
            intervalos.append(("denúncia → sentença", den, sent))
        transito_inferido = None  # o programa não presume datas: sem trânsito no RSPE, verificar na ação penal
        acord = rs.to_date(L["acordao"] or "")
        if sent and (tpr or tmp):
            # intercorrente (art. 110, § 1º): da sentença ao trânsito em julgado definitivo, e não ao da acusação;
            # o acórdão condenatório, quando informado, interrompe (art. 117, IV; STF, HC 176.473)
            if acord and sent < acord < (tpr or tmp):
                intervalos.append(("sentença → acórdão", sent, acord))
                intervalos.append(("acórdão → trânsito", acord, tpr or tmp))
            else:
                intervalos.append(("sentença → trânsito", sent, tpr or tmp))
        if sent and tmp and not tpr:
            L["avisos"].append("não consta no RSPE o trânsito em julgado final (só o da acusação, %s): se a defesa ainda recorria depois dessa data, "
                               "a intercorrente seguiu correndo - verificar na ação penal" % rs.fmt(tmp))
        det = []
        pior = None
        for nome, a, b in intervalos:
            limite = ultimo_dia(a, ppp_meses)
            ok = b > limite  # o marco seguinte veio depois do último dia do prazo (CP, art. 10)
            det.append("%s%s: %s a %s = %s (prazo %s, vence %s)" % ("✘ " if ok else "✔ ", nome, rs.fmt(a), rs.fmt(b), fmt_prazo(_meses(a, b)), L["prazo_ppp"], rs.fmt(limite)))
            if ok and pior is None:
                pior = nome  # o primeiro intervalo em que o prazo se completou
        faltando = [n for n, v in (("data do fato", fato), ("recebimento da denúncia", den), ("sentença", sent), ("trânsito em julgado", tpr or tmp)) if not v]
        if faltando:
            L["avisos"].append("não consta no RSPE: %s - verificar na ação penal (o programa não presume datas; a data do acórdão, se houve, também não consta)" % ", ".join(faltando))
            det.append("Não consta no RSPE: %s. Verificar na ação penal; nenhuma data foi presumida." % ", ".join(faltando))
        juri = _juri(c)
        if pior:
            L["retro_status"] = "Prescrição da pretensão punitiva aparente (%s)" % pior
            L["retro_cor"] = "vermelho"
            if juri and pior == "denúncia → sentença":
                L["retro_status"] += " - conferir pronúncia"
                det.append("⚠ A verificar: crime do júri - a pronúncia e a decisão que a confirma interrompem o prazo (CP, art. 117, II e III), ainda que o "
                           "júri desclassifique o crime (STJ, Súmula 191); as datas não constam do RSPE.")
        elif not intervalos or faltando:
            L["retro_status"] = "Verificar na ação penal: falta " + ", ".join(faltando) if faltando else "Verificar na ação penal"
            L["retro_cor"] = "cinza"
        else:
            L["retro_status"] = "não configurada"
            L["retro_cor"] = ""
        if sent and (tpr or tmp) and (tpr or tmp) > sent and not acord:
            det.append("Obs.: eventual acórdão condenatório entre a sentença e o trânsito interrompe o prazo (art. 117, IV; STF HC 176.473) - data não consta no RSPE.")
        if tmp and tpr and tmp != tpr:
            det.append("Trânsito para a acusação em %s; trânsito final em %s. A retroativa pressupõe o trânsito para a acusação (art. 110, § 1º); "
                       "a intercorrente corre da sentença até o trânsito final." % (rs.fmt(tmp), rs.fmt(tpr)))
        if sent and tmp and not tpr:
            det.append("A verificar: o RSPE só traz o trânsito para a acusação (%s); se a defesa recorreu, a intercorrente corre até o trânsito final." % rs.fmt(tmp))
        if sent and fato and fato >= rg.d("2020-01-23"):
            det.append("A verificar: embargos de declaração, recursos inadmitidos nos tribunais superiores e acordo de não persecução suspendem o prazo "
                       "(CP, art. 116, III e IV, fatos a partir de 23/01/2020) - o RSPE não traz esses dados.")
        if aviso497:
            det.append("⚠ " + aviso497[0].upper() + aviso497[1:] + ".")
        L["retro_detalhe"] = "\n".join(det)

        # ---------------- pretensão executória ----------------
        fator = (1 + ACRESC) if L["reinc"] else Fraction(1)
        if meia:
            fator *= Fraction(1, 2)
        ppe_meses = Fraction(base_meses) * fator
        L["prazo_ppe"] = fmt_prazo(ppe_meses) + (" (+1/3 reincidência)" if L["reinc"] else "") + (" (½ art. 115)" if meia else "")
        L["ppe_meses"] = ppe_meses
        L["ppe_meses_integral"] = ppe_meses * 2 if meia else ppe_meses
        L["ppe_meses_art109"] = Fraction(base_meses)  # só o art. 109, sem o +1/3 da reincidência nem a metade do art. 115
        if tmp and tmp <= TEMA_788:
            termo, termo_txt = tmp, "trânsito para a acusação %s (art. 112, I; modulação do Tema 788)" % rs.fmt(tmp)
        elif tpr:
            termo, termo_txt = tpr, "trânsito para ambas as partes %s (STF, Tema 788)" % rs.fmt(tpr)
        elif tmp:
            termo, termo_txt = tmp, "trânsito para a acusação %s (trânsito do processo não informado)" % rs.fmt(tmp)
        elif transito_inferido:
            termo, termo_txt = transito_inferido, "início do cumprimento %s (trânsito não informado; data usada como limite)" % rs.fmt(transito_inferido)
        else:
            termo, termo_txt = None, ""
        L["ppe_termo"] = rs.fmt(termo) if termo else ""
        L["ppe_previsao"] = ""
        L["ppe_dias"] = None
        L["ppe_linha_tempo"], L["ppe_saldos"], L["ppe_faltam"] = [], [], []
        if not termo:
            L["ppe_status"] = "Verificar na ação penal: trânsito em julgado não consta no RSPE"
            L["ppe_cor"] = "cinza"
            det = ["Sem data de trânsito no RSPE: verificar na ação penal. Se a execução for provisória, a prescrição executória ainda não corre."]
        else:
            L0 = copy.deepcopy(L)
            det = _exec(L, c, r, ctx, termo, termo_txt, pena, fato, fator, ppe_meses, meia)
            # item 6 (contribuição 2): reincidência ou idade ausentes no RSPE que mudam o resultado -> A VERIFICAR
            variantes = []
            if reinc_desc:
                variantes.append(("reincidência", not L["reinc"], meia))
            if reinc_sem_base:
                variantes.append(("reincidência sem condenação anterior no RSPE", False, meia))
            if meia_desc:
                variantes.append(("idade no fato/sentença (art. 115)", L["reinc"], not meia))
            if reinc_desc and meia_desc:
                variantes.append(("reincidência e idade", not L["reinc"], not meia))
            difs = []
            for nome_v, rv_, mv_ in variantes:
                Lx = copy.deepcopy(L0)
                Lx["reinc"] = rv_
                fx = ((1 + ACRESC) if rv_ else Fraction(1)) * (Fraction(1, 2) if mv_ else 1)
                Lx["prazo_ppe"] = fmt_prazo(Fraction(base_meses) * fx) + (" (+1/3 reincidência)" if rv_ else "") + (" (½ art. 115)" if mv_ else "")
                _exec(Lx, c, r, ctx, termo, termo_txt, pena, fato, fx, Fraction(base_meses) * fx, mv_)
                if _classe(Lx) != _classe(L):
                    difs.append((nome_v, Lx))
                elif nome_v.startswith("reincidência sem"):
                    _base_do_prazo(Lx)
                    L["ppe_reinc_aviso"] = ("Reincidência marcada no RSPE sem condenação anterior transitada neste RSPE (ver Auditoria: conferir a "
                                            "certidão de antecedentes e o período depurador - CP, art. 64, I). Sem o +1/3, o prazo seria %s: "
                                            "o resultado não muda." % (Lx.get("ppe_prazo_efetivo") or Lx.get("prazo_ppe") or "—"))
            if difs:
                antes = L["ppe_status"]
                L["ppe_status"] = "A VERIFICAR: o resultado depende de dado ausente no RSPE (%s)" % difs[0][0]
                L["ppe_cor"], L["ppe_previsao"], L["ppe_dias"] = "amarelo", "", None
                _nm = " ".join(n for n, _ in difs)
                L["ppe_faltam"] = ([x for x in ("reincidência (marcada no RSPE sem condenação anterior transitada listada: conferir a certidão de antecedentes; "
                                                "+1/3 no prazo - CP, arts. 64, I, e 110)" if "sem condenação" in _nm else
                                                ("reincidência (o RSPE não informa; +1/3 no prazo - CP, art. 110)" if "reincid" in _nm else ""),
                                                "data de nascimento (idade no fato e na sentença - CP, art. 115)" if "idade" in _nm else "") if x]
                                   + list(L.get("ppe_faltam") or []))
                L["ppe_triagem"] = "O resultado muda conforme %s: informe o dado em \"editar dados\"." % " / ".join(n for n, _ in difs)
                det.append("Conclusão ajustada: A VERIFICAR - com os dados do RSPE: %s; considerando %s de outro modo: %s." % (
                    antes, difs[0][0], difs[0][1]["ppe_status"]))
        if aviso497:
            det.append("⚠ " + aviso497[0].upper() + aviso497[1:] + ".")
        if "MULTA" in (c.get("tipo_penal") or "").upper():
            det.append("Multa cumulada: prescreve no prazo da pena privativa (CP, arts. 114, II, e 118), mas com as causas de suspensão e "
                       "interrupção da dívida ativa (Lei 6.830/1980; CTN, art. 174), sem as dos arts. 116 e 117 do CP (STJ, Tema 1.405): a prisão "
                       "não suspende a prescrição da multa (STJ, REsp 2.268.643). Conferir nos autos da execução da multa o despacho que ordenou a citação.")
        if impr:
            L["avisos"].append(impr[1])
            det.append("⚠ " + impr[1][0].upper() + impr[1][1:] + ".")
            for k in ("ppe", "retro"):
                if L.get(k + "_cor") == "vermelho":
                    L[k + "_status"] = "A VERIFICAR: %s aparente, salvo imprescritibilidade" % ("prescrição executória" if k == "ppe" else "prescrição punitiva")
                    L[k + "_cor"] = "amarelo"
                    if k == "ppe":
                        L["ppe_previsao"], L["ppe_dias"] = "", None
                        L["ppe_faltam"] = ["natureza do crime na sentença (%s)" % impr[1].split(":")[0]] + list(L.get("ppe_faltam") or [])
        L["ppe_detalhe"] = "\n".join(det)
        _base_do_prazo(L)
        _explicar(L, hoje)
        _quadro(L, hoje)
        linhas.append(L)
    # avisos próprios de cada crime identificam o crime e a ação penal (uma execução pode ter vários processos)
    geral = set(avisos_gerais)
    for L in linhas:
        L["avisos"] = [a if a in geral else "%s (ação penal %s): %s" % (L["crime"], L["proc_crim"] or "não informada", a) for a in L["avisos"]]
    # rótulo do crime no resumo: com o número da ação penal quando o mesmo artigo se repete na execução
    _rep = {}
    for L in linhas:
        _rep[L["crime"]] = _rep.get(L["crime"], 0) + 1
    for L in linhas:
        L["rotulo"] = L["crime"] + ((" (ação penal %s)" % (L["proc_crim"] or "?")) if _rep[L["crime"]] > 1 else "")

    # resumo por sentenciado
    cores = [l.get("retro_cor", "") for l in linhas] + [l.get("ppe_cor", "") for l in linhas]
    if "vermelho" in cores:
        cor = "vermelho"
    elif "amarelo" in cores:
        cor = "amarelo"
    elif linhas and all(c in ("cinza",) for c in cores):
        cor = "cinza"
    else:
        cor = ""
    previsoes = [l["ppe_previsao"] for l in linhas if l.get("ppe_previsao")]
    prox = min(previsoes, key=lambda s: rs.to_date(s) or date.max) if previsoes else ""
    retro = [l for l in linhas if l.get("retro_cor") == "vermelho"]
    ppe_red = [l for l in linhas if l.get("ppe_cor") == "vermelho"]
    ppe_ver = [l for l in linhas if (l.get("ppe_status") or "").startswith("A VERIFICAR")]
    ppe_amb = [l for l in linhas if l.get("ppe_cor") == "amarelo" and l not in ppe_ver]
    if retro:
        resumo_retro = "Aparente: " + "; ".join(l["rotulo"] for l in retro)
    elif linhas and all(l.get("retro_cor") == "cinza" or (l.get("retro_status") or "").startswith("Verificar") for l in linhas):
        resumo_retro = "sem dados: verificar na ação penal"
    else:
        resumo_retro = "não configurada" if linhas else ""
    partes = []
    if ppe_red:
        partes.append("Aparente: " + "; ".join(("%s em %s" % (l["rotulo"], l["ppe_previsao"])) if l.get("ppe_previsao") else l["rotulo"] for l in ppe_red))
    if ppe_amb:
        partes.append("Iminente: " + "; ".join("%s em %s" % (l["rotulo"], l["ppe_previsao"]) for l in ppe_amb))
    if ppe_ver:
        partes.append("A verificar (saldo na evasão): " + "; ".join(l["rotulo"] for l in ppe_ver))
    if partes:
        resumo_ppe = " · ".join(partes)
    elif linhas:
        resumo_ppe = "Não prescrita" if any(l.get("ppe_cor") != "cinza" for l in linhas) else "; ".join(sorted(set(l["ppe_status"] for l in linhas)))
    else:
        resumo_ppe = ""
    dias = [l["ppe_dias"] for l in linhas if l.get("ppe_dias") is not None]
    for l in linhas:
        try:
            l["ppe_fund"], l["pp_fund"] = fundamentacao(l, "pe"), fundamentacao(l, "pp")
        except Exception:
            l["ppe_fund"] = l["pp_fund"] = ""
    return {
        "presc_linhas": linhas,
        "presc_cor": cor,
        "presc_retro": resumo_retro,
        "presc_ppe": resumo_ppe,
        "presc_prox": prox,
        "presc_dias": min(dias) if dias else None,
        "presc_obs": "; ".join(sorted(set(a for l in linhas for a in l["avisos"]))),
    }


def _meses(a, b):
    m = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        m -= 1
    return m
