# -*- coding: utf-8 -*-
"""
Auditoria do RSPE: confronta os dados que o SEEU imprimiu com a legislação e a
jurisprudência da base jurídica (base_juridica.json) e com a coerência interna
do próprio relatório. Não afirma erro: aponta o que tem efeito concreto e o que
deve ser verificado, sempre com o fundamento.

Níveis: 'alerta' (divergência com efeito concreto), 'verificar' (depende de dado
que o RSPE não traz), 'info' (registro sem efeito prático, oculto por padrão na
tela) e 'ok' (conferido sem ressalva). Cada item traz 'tipo' e 'ref' (chave da
baixa e filtro das outras abas: rspe_view.so_matematica tira da aba Auditoria
os pontos que outras abas já mostram).
"""

import re
from datetime import date, timedelta
from fractions import Fraction

import rspe_scraper as rs
import rspe_regras as rg
import rspe_prescricao as rp


def _descricao_tipo(c):
    """Descrição do tipo sem o rótulo do parágrafo e sem a pena cominada."""
    t = re.sub(r"^\s*(CAPUT|§\s*[\dº°A-Za-z-]+)\s*:\s*", "", c.get("tipo_penal") or "-")
    return re.split(r",\s*(Reclusão|Detenção|Prisão simples)\s*:", t)[0].strip()


def _nome(c):
    """'Proc. 0000554-90.2023.8.12.0042 · art. 33 Lei 11.343/06': a guia pode ter vários crimes iguais."""
    crime = rs.crimes_curto([dict(c, extinto="Não")]) or "crime"
    p = (c.get("processo_criminal") or "").strip()
    return "Proc. %s · %s" % (p, crime) if p else crime


def _trafico(c):
    """Tráfico da Lei 11.343/06 com livramento de 2/3 (art. 44, p. ú.: arts. 33, caput e § 1º, e 34 a 37).
    O art. 33, §§ 2º, 3º e 4º, fica fora."""
    if not (rs.num_lei(c.get("lei")) == "11343" and rs.num_art(c.get("artigo")) in ("33", "34", "35", "36", "37")):
        return False
    tp = c.get("tipo_penal") or ""
    return not (rs.num_art(c.get("artigo")) == "33" and (re.match(r"\s*§\s*[234](?!\d)", tp) or "§ 4" in tp))


def _trafico_pessoas(c):
    """CP, art. 149-A (tráfico de pessoas): livramento só após 2/3 (CP, art. 83, V, incluído pela Lei 13.344/2016,
    que também criou o tipo - por isso não há fato anterior à regra)."""
    lei = rs.num_lei(c.get("lei"))
    return (lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())) and rs.num_art(c.get("artigo")) == "149-A"


def _transito(c):
    return rs.to_date(c.get("transito_processo") or c.get("transito_mp") or "")


def _reincidencia_legal(c, crimes):
    """Reincidência pela lei (CP, arts. 63 e 64, I), a mesma para progressão e livramento: a marcação do RSPE ou condenação
    anterior deste RSPE transitada antes do fato, salvo a depurada (fato mais de 5 anos depois da extinção ou do cumprimento
    da pena anterior). Devolve (reincidente, marcação, anteriores válidas, anteriores depuradas)."""
    fato = rs.to_date(c.get("data_infracao") or "")
    marc = c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S"
    ants, dep = [], []
    for o in crimes:
        if o is c or not fato:
            continue
        t = _transito(o)
        if not (t and t < fato):
            continue
        ext = rs.to_date(o.get("data_extincao") or "") if (o.get("extinto") or "").upper().startswith("S") else None
        if ext:
            try:
                lim = ext.replace(year=ext.year + 5)
            except ValueError:
                lim = ext.replace(year=ext.year + 5, day=28)
            if fato > lim:
                dep.append(o)
                continue
        ants.append(o)
    return marc or bool(ants), marc, ants, dep


def _cap_criada(c, desc):
    """'A majorante cadastrada (art. 157, § 2º-A, I, do CP - emprego de arma de fogo, aumento de 2/3)'."""
    disp = "art. %s%s" % (rs.num_art(c.get("artigo")) or "?", (", " + _par_inc(c)) if _par_inc(c) else "")
    lei = rs.num_lei(c.get("lei"))
    disp += ", do CP" if lei in ("2848", "") else (", da Lei %s" % rs.lei_fmt(lei) if hasattr(rs, "lei_fmt") else ", da Lei %s" % lei)
    if not desc:
        return "O tipo, a qualificadora ou a majorante cadastrados (%s)" % disp
    nat, o_que, _ = desc
    return "%s cadastrad%s (%s - %s)" % ({"tipo": "O tipo", "qualificadora": "A qualificadora", "majorante": "A majorante"}[nat],
                                          "o" if nat == "tipo" else "a", disp, o_que)


def _par_inc(c):
    """'§ 2º-A, I' a partir do tipo penal do SEEU."""
    m = re.match(r"\s*(§\s*\d+[ºo°]?(?:\s*-\s*[A-Z])?)\s*,?\s*([IVXL]+\b)?", c.get("tipo_penal") or "")
    if not m:
        return ""
    par = re.sub(r"\s+", " ", m.group(1)).replace("§ ", "§ ").replace(" - ", "-")
    par = re.sub(r"§\s*", "§ ", par)
    return par + ((", " + m.group(2)) if m.group(2) else "")


def _reinc_especifica(c, crimes):
    """Base da reincidência específica do art. 83, V, do CP no próprio RSPE: condenação anterior por hediondo,
    equiparado (tortura, tráfico de drogas, terrorismo) ou tráfico de pessoas (art. 149-A), transitada antes do fato.
    Não presume: sem trânsito, a condenação fica 'não aferível'."""
    fato = rs.to_date(c.get("data_infracao") or "")
    confirma, sem_transito, nao_hed = [], [], []
    for o in crimes:
        if o is c or (o.get("processo_criminal") and rs.mesmo_processo(o.get("processo_criminal"), c.get("processo_criminal"))):
            continue
        hed_o = _e_hediondo_lei(o)[0]
        qualifica = hed_o is True or _trafico(o) or _trafico_pessoas(o) or (hed_o is None and _hediondo_seeu(o))
        t, f_o = _transito(o), rs.to_date(o.get("data_infracao") or "")
        if not qualifica:
            if t and fato and t < fato and rs.num_lei(o.get("lei")) == "11343":
                nao_hed.append(o)
            continue
        if t and fato and t < fato:
            confirma.append(o)
        elif not t and (not fato or not f_o or f_o < fato):
            sem_transito.append(o)
    return confirma, sem_transito, nao_hed


# Correções de cálculo do SEEU com data conhecida (portal de documentação do SEEU: notas de versão e boletins). Um RSPE emitido
# antes da correção pode trazer o valor antigo. (início, fim da janela, condição, título, detalhe, fonte)
CORRECOES_SEEU = [
    (None, date(2025, 5, 15), "sempre", "frações e cálculos de pena",
     "Em 15/05/2025 o SEEU corrigiu \"erro nos cálculos de penas e frações\" (versão 14.2.1). As frações e datas previstas deste RSPE "
     "podem ser anteriores à correção.", "Boletim Oficial do SEEU de 15/05/2025; notas da versão 14 (SEEU-30560)"),
    (date(2025, 9, 15), date(2025, 9, 19), "sempre", "término da pena (art. 75 do CP)",
     "Entre 15 e 19/09/2025 uma versão do SEEU com regra do art. 75 do CP gerou erros na calculadora, corrigidos em 19/09/2025. "
     "O término e as datas previstas deste RSPE podem ter saído errados.", "Comunicado extraordinário do SEEU de 19/09/2025"),
    (None, date(2025, 10, 31), "comutacao_impeditivo", "comutação com crime impeditivo",
     "Até 31/10/2025 (versão 18.11.1) o SEEU não calculava sozinho a comutação quando havia pena por crime impeditivo somada a "
     "crime comum; a fração deve incidir só sobre a parte comutável. Conferir o montante comutado.",
     "Comunicado do SEEU de 31/10/2025 (Cálculo automatizado da comutação)"),
    (None, date(2026, 7, 30), "comutacao", "campos de pena comutada no relatório",
     "Em 30/07/2026 (versão 20.3.0) o SEEU corrigiu os campos do relatório de situação executória sobre pena comutada para delito "
     "hediondo/impeditivo. Conferir os dados da comutação neste RSPE.", "Boletim Oficial do SEEU de 30/07/2026; notas da versão 20 (SEEU-43078)"),
]


def _correcoes_seeu(r, crimes, incidentes):
    """Alerta de RSPE emitido antes de uma correção de cálculo do SEEU que o alcança."""
    ger = rs.to_date(r.get("data_geracao_rspe") or "")
    if not ger:
        return []
    comut = any("COMUTA" in (i.get("tipo") or "").upper() and i.get("situacao", "CONCEDIDO") == "CONCEDIDO" for i in incidentes)
    impedit = any((c.get("hediondo_ou_equiparado") or "") == "S" for c in crimes)
    out = []
    for ini, fim, cond, titulo, detalhe, fonte in CORRECOES_SEEU:
        if ger > fim or (ini and ger < ini):
            continue
        if cond == "comutacao" and not comut or cond == "comutacao_impeditivo" and not (comut and impedit):
            continue
        out.append(_item("verificar", "RSPE emitido antes de correção do SEEU: %s" % titulo,
                         "RSPE emitido em %s. %s Importe um RSPE atualizado." % (rs.fmt(ger), detalhe), fonte,
                         tipo="rspe-anterior-a-correcao-do-seeu", ref=titulo))
    return out


def _item(nivel, titulo, detalhe, fundamento="", tipo="", ref=""):
    """tipo: identificador fixo do ponto (não muda com números, datas ou agrupamento do título); ref: o crime, o ano
    ou a falta a que o ponto se refere. A baixa usa tipo + ref (o processo já separa as baixas)."""
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "fundamento": fundamento, "tipo": tipo, "ref": ref or ""}


def _fr_seeu(txt):
    f = rs.parse_fracao(txt or "")
    return f


def _hediondo_seeu(c):
    return "HEDIONDO" in ((c.get("fracao_progressao") or "") + (c.get("fracao_livramento") or "")).upper()


def _ant_decidiu(itens, nome):
    """Já há item decidido (alerta) sobre a reincidência em crime violento deste crime."""
    return any(i.get("tipo") == "reincidente-vga-percentual-se-nao-especifica" and i.get("ref") == nome and i.get("nivel") == "alerta" for i in itens)


def _e_hediondo_lei(c):
    """Hediondez pela lei (base jurídica), independente do rótulo do SEEU, respeitada a lei da época do fato."""
    if rs.hediondo_na_epoca(c) is False:
        d, lei = rs.hediondo_desde(c)
        return False, "fato anterior à %s (vigência %s): não era hediondo à época" % (lei or "lei", rs.fmt(d))
    h = rg.hediondos()
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    if not art:
        return None, "artigo não informado no RSPE"
    cp = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
    if cp:
        if art in h.get("lei_8072_art1_cp_sempre", []):
            return True, ""
        if art in h.get("lei_8072_art1_cp_condicional", {}):
            hc = rs.hediondo_condicional(c)
            if hc is None:
                return None, h["lei_8072_art1_cp_condicional"][art]
            return hc, ""
        return False, ""
    eq = h.get("equiparados", {})
    if lei in eq and art in eq[lei]:
        _tp = c.get("tipo_penal") or ""
        if lei == "11343" and art == "33" and "§ 4" in _tp:
            return False, "tráfico privilegiado (art. 33, § 4º) não é hediondo (LEP, art. 112, § 5º)"
        if lei == "11343" and art == "33" and rs.re.match(r"\s*§\s*[23](?!\d)", _tp):
            return False, "art. 33, §§ 2º e 3º (induzimento e uso compartilhado) ficam fora do tráfico equiparado a hediondo"
        return True, ""
    return rs.hediondo_pu(c, h)


def _juntar_por_processo(nomes):
    """['Proc. A · art. 33', 'Proc. A · art. 180', 'Proc. B · art. 33'] -> 'Proc. A · art. 33, art. 180; Proc. B · art. 33'."""
    por, ordem = {}, []
    for n in nomes:
        p, _, cr = n.partition(" · ") if n.startswith("Proc. ") else ("", "", n)
        if p not in por:
            por[p] = []
            ordem.append(p)
        por[p].append(cr)
    return "; ".join(("%s · %s" % (p, ", ".join(por[p]).replace(", ", ", ")) if p else rs.resumir_nomes(por[p])) for p in ordem)


def _agrupar_por_crime(itens):
    """Mesmo ponto repetido em vários crimes ('art. 180 CP: X', 'art. 330 CP: X') vira uma linha só: 'X (art. 180 CP; art. 330 CP)'."""
    grupos, ordem = {}, []
    for it in itens:
        m = re.match(r"^((?:Proc\. [\d.\-]+ · )?(?:art\. [^:]+|[^:]{1,40}(?:CP|/\d{2}))): (.+)$", it["titulo"])
        chave = (it["nivel"], m.group(2), it.get("fundamento", "")) if m else None
        if chave is None:
            ordem.append(it)
            continue
        if chave not in grupos:
            grupos[chave] = {"base": dict(it), "crimes": [], "detalhes": []}
            ordem.append(grupos[chave]["base"])
        g = grupos[chave]
        g["crimes"].append(m.group(1))
        if it["detalhe"] not in g["detalhes"]:
            g["detalhes"].append(it["detalhe"])
    for (nivel, sufixo, _), g in grupos.items():
        b = g["base"]
        if len(g["crimes"]) > 1:
            # título enxuto (só os crimes); os processos vão no detalhe
            crimes_ = [n.partition(" · ")[2] if n.startswith("Proc. ") else n for n in g["crimes"]]
            b["titulo"] = "%s%s (%s)" % (sufixo[0].upper(), sufixo[1:], rs.resumir_nomes(crimes_))
            procs = _juntar_por_processo(g["crimes"])
            det = " | ".join(d.strip() for d in g["detalhes"] if d and d.strip())
            b["detalhe"] = ("Processos: %s.%s" % (procs.replace("Proc. ", "").replace(" · ", " - "), (" " + det) if det else "")) if "Proc. " in procs else det
    return ordem


FUND_127 = ("LEP, art. 127 (até 1/3; a contagem recomeça da data da infração); STJ, HC 398.850/SP, HC 293.475/SP e HC 377.088/SP; "
            "TJDFT, Acórdão 1230029.")


def perdas_por_falta(incidentes):
    """Para cada falta grave homologada no RSPE com perda de dias remidos: a perda, as parcelas e a remição
    sobre a qual cada parcela incidiu (parcela = 1/3 da remição, arredondado), a falta anterior e a janela de
    remição entre a falta anterior e a atual (LEP, art. 127: a contagem recomeça da data da infração)."""
    incidentes = [i for i in incidentes if not i.get("_ficha")]  # falta da ficha disciplinar: não é homologação no RSPE
    def dt(i):
        return rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
    def qtd(i):
        m = rs.re.search(rs.NUM_DIAS, i.get("complemento") or "")
        return rs.num_br(m.group(1)) if m else 0
    # a falta é datada pelo fato (data da infração lida no complemento da homologação), que é o que reinicia a contagem
    # (art. 127); sem ela, pela data de referência do incidente, com a ressalva
    sem_fato = set()
    def dt_falta(i):
        m = rs.RE_DATA.search(i.get("complemento") or "")
        d = rs.to_date(m.group(1)) if m else None
        if d:
            return d
        d = dt(i)
        if d:
            sem_fato.add(d)
        return d
    faltas = sorted(set(d for d in (dt_falta(i) for i in incidentes if "FALTA GRAVE" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO") if d))
    perdas = [(dt(i), qtd(i)) for i in incidentes if "PERDIDOS" in (i.get("tipo") or "").upper()]
    remicoes = []
    for i in incidentes:
        t = (i.get("tipo") or "").upper()
        if "REMI" in t and "PERDIDOS" not in t and i.get("situacao") == "CONCEDIDO":
            n = rs.dias_de(i.get("complemento", ""))
            if n is not None:
                remicoes.append({"d": dt(i), "data": i.get("data_decisao") or i.get("data_referencia") or "", "n": n})
    out = []
    resid = {id(x): x["n"] for x in remicoes}  # saldo de cada remição depois das perdas anteriores
    for k, f in enumerate(faltas):
        prox = faltas[k + 1] if k + 1 < len(faltas) else None
        prev = faltas[k - 1] if k else None
        pf = sorted([q for d, q in perdas if d and d >= f and (prox is None or d < prox)], reverse=True)
        if not pf:
            continue
        usadas, parcelas = set(), []
        def bate(q, n):
            return n > 0 and q in (n // 3, -(-n // 3), round(n / 3))
        for q in pf:
            cand = [x for x in remicoes if id(x) not in usadas and (bate(q, x["n"]) or bate(q, resid[id(x)]))]
            cand.sort(key=lambda x: (x["d"] is None or x["d"] > f, -(x["d"] or date.min).toordinal()))
            rem = cand[0] if cand else None
            if rem:
                usadas.add(id(rem))
            parcelas.append((q, rem))
        for q, rem in parcelas:
            if rem:
                resid[id(rem)] = max(0, resid[id(rem)] - q)
        janela = sum(x["n"] for x in remicoes if x["d"] and x["d"] <= f and (prev is None or x["d"] > prev))
        out.append({"falta": f, "prev": prev, "perda": sum(pf), "parcelas": parcelas, "janela": janela, "sem_fato": f in sem_fato,
                    "remido_ate": sum(x["n"] for x in remicoes if x["d"] and x["d"] <= f)})
    return out, faltas, perdas


def _perda_remidos(incidentes, perdidos, eventos=None):
    """LEP, art. 127: a falta grave permite revogar ATÉ 1/3 do tempo remido, e a contagem recomeça da data da
    infração - nova falta só alcança a remição adquirida depois da falta anterior (vedado o desconto em duplicidade)."""
    res, faltas, perdas = perdas_por_falta(incidentes)
    if not faltas or not perdas:
        _fg = [e for e in (eventos or []) if re.search(r"FUGA|EVAS|ABANDONO", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())]
        _dp_ = [rs.to_date(i.get("data_decisao") or i.get("data_referencia") or "") for i in incidentes if "PERDIDOS" in (i.get("tipo") or "").upper()]
        _dp_ = [d for d in _dp_ if d]
        extra = ""
        if _fg:
            extra = (" O RSPE registra %s; se a perda%s decorre disso, a falta precisa ter sido apurada em PAD e homologada, e o limite de 1/3 "
                     "incide só sobre a remição adquirida até a falta." % (
                         "; ".join("%s em %s" % ((e.get("motivo") or e.get("tipo") or "").strip().lower(), e.get("data")) for e in _fg),
                         (" (decisão de %s)" % rs.fmt(max(_dp_))) if _dp_ else ""))
        return [_item("verificar", "Perda de %s remidos sem falta grave datada no RSPE" % rs.pl(perdidos, "dia", "dias"),
                      "O saldo registra dias perdidos, mas não há incidente de homologação de falta grave com data: conferir a decisão e o PAD." + extra,
                      "LEP, arts. 118 e 127; Súmula 533/STJ.", tipo="perda-de-remidos-sem-falta-grave-datada-no-rspe")]
    itens = []
    for x in res:
        f, prev = x["falta"], x["prev"]
        ress = (" Data do fato não consta no complemento da homologação: usada a data de referência (%s); conferir a data da infração, "
                "que é a que reinicia a contagem (art. 127)." % rs.fmt(f)) if x.get("sem_fato") else ""
        dup = [(q, rem) for q, rem in x["parcelas"] if prev and rem and rem["d"] and rem["d"] <= prev]
        if dup:
            itens.append(_item("alerta", "Perda de dias remidos em duplicidade (falta de %s)" % rs.fmt(f),
                               "A perda de %s pela falta de %s incidiu sobre remição anterior à falta de %s: %s. A contagem recomeçou em %s; "
                               "a nova perda só pode alcançar a remição adquirida entre as duas faltas (%s; limite de 1/3: %d). Cabe impugnar o cálculo." % (
                                   rs.pl(x["perda"], "dia", "dias"), rs.fmt(f), rs.fmt(prev),
                                   "; ".join("%s sobre a remição de %s de %s" % (rs.pl(q, "dia", "dias"), rs.pl(rem["n"], "dia", "dias"), rem["data"]) for q, rem in dup),
                                   rs.fmt(prev), rs.pl(x["janela"], "dia", "dias"), x["janela"] // 3) + ress, FUND_127, tipo="perda-de-dias-remidos-em-duplicidade-falta-de", ref=rs.fmt(f)))
        base = x["janela"]
        limite = base // 3
        if base and x["perda"] > limite:
            itens.append(_item("alerta", "Perda de dias remidos acima de 1/3 (falta de %s)" % rs.fmt(f),
                               "Remição %s: %s; limite de 1/3: %s; perdidos: %s (excesso de %s).%s" % (
                                   ("adquirida entre a falta de %s e esta" % rs.fmt(prev)) if prev else "até a falta",
                                   rs.pl(base, "dia", "dias"), rs.pl(limite, "dia", "dias"), rs.num_txt(x["perda"]), rs.pl(x["perda"] - limite, "dia", "dias"),
                                   " Parcelas: %s - o arredondamento para cima de cada parcela ultrapassa o teto legal." % ", ".join(
                                       "%s (sobre %s)" % (rs.num_txt(q), rs.num_txt(rem["n"]) if rem else "?") for q, rem in x["parcelas"]) if (len(x["parcelas"]) > 1 and not dup) else "") + ress,
                               FUND_127, tipo="perda-de-dias-remidos-acima-de-1-3-falta-de", ref=rs.fmt(f)))
        elif not dup:
            itens.append(_item("info", "Perda de %s remidos pela falta grave de %s" % (rs.pl(x["perda"], "dia", "dias"), rs.fmt(f)),
                               "Dentro do limite de 1/3 (remição %s: %s)." % (("entre a falta de %s e esta" % rs.fmt(prev)) if prev else "até a falta", rs.pl(base, "dia", "dias")) + ress, "LEP, art. 127.", tipo="perda-de-remidos-pela-falta-grave-de", ref=rs.fmt(f)))
    return itens


def _dias_compl(i):
    m = re.search(r"(\d+)\s*Dia", i.get("complemento") or "", re.I)
    return int(m.group(1)) if m else 0


def _lancamentos_seeu(r, crimes, ativos, incidentes, eventos):
    """Lançamentos do SEEU que distorcem o cálculo sem aparecer como erro (Aula NUSPEN 2026 - SEEU/TJMS): remição de período
    antigo lançada depois da progressão (data fixa), indulto/comutação na data da decisão, unificação usada como soma, pena
    cumprida abaixo da custódia, comutação sem os impeditivos marcados e detração do recolhimento noturno lançada como remição."""
    out = []
    D = lambda s: rs.to_date(s or "")
    conc = [i for i in incidentes if i.get("situacao", "CONCEDIDO") == "CONCEDIDO"]
    procs_at = {c.get("processo_criminal") for c in ativos if c.get("processo_criminal")}
    # A - remição de período anterior à última progressão, lançada depois dela: a data da progressão é fixa no SEEU
    prog = [i for i in conc if "REGIME" in (i.get("tipo") or "").upper() and "PROGRESS" in (i.get("complemento") or "").upper()
            and D(i.get("data_referencia")) and D(i.get("data_decisao"))]
    if prog:
        up = max(prog, key=lambda i: D(i["data_referencia"]))
        rem = [i for i in conc if (i.get("tipo") or "").upper().startswith("REMI") and D(i.get("data_referencia"))
               and D(i.get("data_decisao")) and D(i["data_referencia"]) < D(up["data_referencia"]) and D(i["data_decisao"]) > D(up["data_decisao"])]
        if rem:
            out.append(_item("verificar", "Remição de período anterior à progressão lançada depois dela: pedir o recálculo",
                             "A progressão de %s (%s) foi decidida em %s e a data dela fica fixa no SEEU. Depois disso foram lançadas remições "
                             "com referência anterior: %s (%s no total). O SEEU não recalcula sozinho e o servidor não recalcula de ofício: "
                             "pedir que a remição entre na data de referência do atestado e o recálculo da progressão (e das comutações, se "
                             "houver), o que antecipa a data-base e os próximos benefícios." % (
                                 up["data_referencia"], (up.get("complemento") or "").strip(), up["data_decisao"],
                                 "; ".join("%s dias ref. %s, lançados em %s" % (_dias_compl(i) or "?", i["data_referencia"], i["data_decisao"]) for i in rem),
                                 rs.pl(sum(_dias_compl(i) for i in rem), "dia", "dias")),
                             "LEP, arts. 126, § 8º, e 128 (remição é pena cumprida, de natureza declaratória); STJ, Tema 1165.",
                             tipo="remicao-preterita-apos-progressao"))
    # B - indulto/comutação lançados na data da decisão, e não na do decreto, havendo outro processo em execução
    for i in conc:
        t = (i.get("tipo") or "").upper()
        txt = "%s %s" % (i.get("complemento") or "", i.get("motivo") or "")
        if not (t.startswith(("INDULTO", "COMUTA")) or (t.startswith("EXTIN") and re.search(r"INDULT|GRA[ÇC]A|ANISTIA", txt, re.I))):
            continue
        m = re.search(r"DE\s+(\d{4})\b", txt.upper())
        ref = D(i.get("data_referencia"))
        if not (m and ref):
            continue
        dec = date(int(m.group(1)), 12, 25)
        sel = set(rs.lista_processos(i.get("processos") or ""))
        outros = [p for p in procs_at if not any(rp._mesmo_processo(p, q) for q in sel)] if sel else []
        if (ref - dec).days > 31 and outros:
            out.append(_item("verificar", "%s na data da decisão (%s), não na do decreto (25/12/%s)" % (
                                 "Comutação lançada" if t.startswith("COMUTA") else "Indulto lançado", rs.fmt(ref), m.group(1)),
                             "%s: o benefício é declaratório e vale desde a data do decreto. Lançado na data da decisão, entra tarde na linha "
                             "do tempo do SEEU e altera a pena cumprida dos outros processos em execução (%s). Pedir a retificação da data e o "
                             "recálculo." % (rs._rotulo_incidente(i), ", ".join(sorted(outros))[:200]),
                             "CF, art. 84, XII; LEP, art. 192; STF, RE 1.236.835 (natureza declaratória da sentença de indulto).",
                             tipo="indulto-lancado-na-data-da-decisao", ref=m.group(1)))
    # C - incidente de unificação usado no lugar do somatório
    for i in conc:
        if (i.get("tipo") or "").upper().startswith("UNIFICA") and not re.search(r"CONCURSO|CONTINU|FORMAL", (i.get("complemento") or "") + " " + (i.get("motivo") or ""), re.I):
            out.append(_item("alerta", "Incidente de unificação usado para somar penas (%s)" % (i.get("data_referencia") or i.get("data_decisao") or "?"),
                             "No SEEU, a unificação serve só ao reconhecimento de concurso formal ou crime continuado; a soma de condenações "
                             "usa o incidente de somatório. Usada para somar, ela junta os processos num só: o SEEU perde a ordem de "
                             "cumprimento de cada um (indulto e comutação deixam de ser calculados por processo) e aplica efeito de "
                             "alteração de data-base. Pedir a substituição pelo somatório e o recálculo. Complemento: %s." % ((i.get("complemento") or "").strip() or "-"),
                             "LEP, arts. 66, III, a, e 111; CP, arts. 70, 71 e 75; STJ, Tema 1006.", tipo="unificacao-como-soma"))
            break
    # D - pena cumprida do SEEU bem menor que a custódia dos eventos somada à remição
    try:
        ger = D(r.get("data_geracao_rspe"))
        prop = [e for e in eventos if not e.get("_ficha")]
        cump = rs.pena_para_dias(r.get("pena_cumprida"))
        if ger and prop and cump and rs.pena_para_dias(r.get("pena_total")) and "SUSPENSA" not in (r.get("situacao_cumprimento") or "").upper():
            cust = sum(((fim or ger) - ini).days for ini, fim in rs.periodos_custodia(prop) if ini <= ger)
            rem = rs.saldo_remidos_num(r.get("saldo_remidos"))[0] or 0
            falta = cust + rem - cump
            if falta > 60 and not [c for c in crimes if c not in ativos]:
                out.append(_item("verificar", "Pena cumprida do SEEU %s menor que a custódia dos eventos" % rs.pl(falta, "dia", "dias"),
                                 "Os eventos de prisão somam %s de custódia e há %s remidos, mas o SEEU imprime %s de pena cumprida. Causas comuns: "
                                 "processo sem vínculo na linha do tempo (\"limbo\": o SEEU não debita o próximo processo depois que um termina), "
                                 "indulto parcial que levou a pena cumprida do processo, ou prisão que pertence a outro processo. Conferir a aba "
                                 "Eventos (cada processo marcado no seu início) e pedir a correção." % (
                                     rs.pl(cust, "dia", "dias"), rs.pl(rem, "dia", "dias"), r.get("pena_cumprida")),
                                 "CP, art. 42; LEP, arts. 111 e 126.", tipo="pena-cumprida-menor-que-custodia"))
    except Exception:
        pass
    # E - comutação com só parte dos processos marcados, havendo crime impeditivo ativo
    imp = {c.get("processo_criminal") for c in ativos if (c.get("hediondo_ou_equiparado") or "").upper().startswith("S") and c.get("processo_criminal")}
    for i in conc:
        if not (i.get("tipo") or "").upper().startswith("COMUTA"):
            continue
        sel = set(rs.lista_processos(i.get("processos") or ""))
        sem = [p for p in imp if sel and not any(rp._mesmo_processo(p, q) for q in sel)]
        if sem:
            out.append(_item("verificar", "Comutação lançada sem marcar os processos impeditivos (%s)" % rs._rotulo_incidente(i)[:60],
                             "O cálculo automático da comutação no SEEU só sai certo com todos os processos marcados, inclusive os impeditivos: "
                             "ele separa da pena cumprida os 2/3 do impeditivo, integraliza o terço restante e aplica a comutação sobre o que "
                             "sobra. Sem marcar %s, o SEEU calcula sem esse parâmetro. Conferir o cálculo (a fração aplicada aparece no incidente) "
                             "e pedir o recálculo." % ", ".join(sorted(sem)),
                             "Decretos de indulto e comutação (pedágio do crime impeditivo); LEP, art. 192.", tipo="comutacao-sem-impeditivos"))
    # F - detração do recolhimento noturno (Tema 1155) lançada como remição
    for i in conc:
        if (i.get("tipo") or "").upper().startswith("REMI") and re.search(r"NOTURN|1\.?155|DETRA|RECOLHIMENTO|MONITORA",
                                                                           "%s %s" % (i.get("complemento") or "", i.get("motivo") or ""), re.I):
            out.append(_item("alerta", "Detração lançada como remição (%s)" % (i.get("data_referencia") or "?"),
                             "%s: o período de recolhimento noturno ou monitoração (STJ, Tema 1155) é detração e deve entrar na aba Eventos, "
                             "ampliando a prisão. Lançado como remição, esses dias podem ser perdidos na próxima falta grave (até 1/3 dos "
                             "remidos). Pedir o relançamento como detração." % rs._rotulo_incidente(i),
                             "CP, art. 42; STJ, Tema 1155; LEP, art. 127.", tipo="detracao-como-remicao"))
    return out


def auditar(r, hoje=None):
    hoje = hoje or date.today()
    itens = []
    crimes = r.get("_crimes", [])
    # condenações das outras execuções da mesma pessoa (mesmo CPF) contam para a reincidência
    crimes_pessoa = crimes + [o for o in (r.get("_outras_condenacoes") or [])
                              if not any(rs.mesmo_processo(o.get("processo_criminal"), c.get("processo_criminal")) for c in crimes)]
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    incidentes = r.get("_incidentes", [])
    eventos = r.get("_eventos", [])
    nasc = rs.to_date(r.get("data_nascimento") or "")
    pena_total = rs.pena_para_dias(r.get("pena_total"))
    cumprida = rs.pena_para_dias(r.get("pena_cumprida"))
    reman = rs.pena_para_dias(r.get("pena_remanescente"))

    # "Faltam dados": cada dado essencial que o programa não leu vira um alerta com o botão Preencher; o valor informado entra
    # nos cálculos como se viesse do RSPE e o alerta passa a "Dado informado" (com a data)
    faltam = rs.campos_faltantes(r)
    if rs.sem_inicio_seeu(r):
        # guia sem evento nem incidente no SEEU: os campos de cálculo vêm vazios porque a pena não foi iniciada no sistema
        _soma = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in r.get("_crimes", []) if not c.get("extinto", "").upper().startswith("S"))
        itens.append(_item("verificar", "Pena não iniciada no SEEU: sem cálculo de pena",
                           "O RSPE não tem nenhum evento (prisão/início do cumprimento) nem incidente: a guia não teve o cumprimento iniciado no SEEU, "
                           "por isso não traz pena total, pena cumprida, regime atual nem término - não são dados faltando na leitura.%s Se a pessoa "
                           "já está presa por estes processos, pedir o início do cumprimento e o cálculo de pena (a prisão desde então conta como "
                           "detração ou cumprimento)." % ((" Soma das penas das condenações: %s." % rs.pena_extenso(rs.dias_para_pena(_soma))) if _soma else ""),
                           "LEP, arts. 105, 106 e 111; CP, art. 42.", tipo="pena-nao-iniciada-seeu"))
    if rs.interrompida_no_seeu(r) and not rs.sem_inicio_seeu(r) and (not r.get("regime_atual") or not r.get("termino_previsao_seeu")):
        # o SEEU deixa de imprimir regime e término enquanto o cumprimento está interrompido (fuga, evasão, soltura sem reinício)
        _ult = [(None, e) for e in sorted([e for e in r.get("_eventos", []) if not e.get("_ficha")], key=lambda e: rs.to_date(e.get("data") or "") or date.min)]
        _u = _ult[-1][1] if _ult else {}
        itens.append(_item("info", "Pena interrompida no SEEU: regime atual e término não impressos",
                           "O último evento do RSPE é %s%s (%s): enquanto não houver reinício lançado no SEEU, o sistema não imprime %s. Não é falha "
                           "de leitura. Se a pessoa já está presa (ficha ou autos), pedir o lançamento do reinício/recaptura no SEEU." % (
                               (_u.get("tipo") or "interrupção").lower(), (" - " + _u.get("motivo").lower()) if _u.get("motivo") else "", _u.get("data") or "?",
                               " nem ".join(x for x, v in (("o regime atual", r.get("regime_atual")), ("o término", r.get("termino_previsao_seeu"))) if not v)),
                           "LEP, arts. 111 e 112.", tipo="pena-interrompida-seeu"))
    _oe = r.get("_outras_execucoes") or []
    if _oe:
        _at = [o for o in _oe if not o["encerrada"] and o["tem_crime"]]
        _desc = "; ".join("%s (%s%s)" % (o["processo"], (o["status"] or "?").lower(),
                                         (", " + o["crimes"]) if o["crimes"] else (", sem condenação cadastrada" if not o["tem_crime"] else ""))
                          for o in _oe)
        if _at:
            itens.append(_item("verificar", "Mais de uma execução ativa no SEEU para a mesma pessoa",
                               "Outras execuções com condenação ativa: %s. A lista mostra só esta (a mais completa). As penas da mesma pessoa "
                               "devem ser somadas ou unificadas numa só execução: pedir a unificação, ou a baixa da execução redistribuída." % _desc,
                               "LEP, arts. 66, III, a, e 111; CP, art. 75.", tipo="outras-execucoes-ativas"))
        else:
            itens.append(_item("info", "Outras execuções da mesma pessoa fora da lista",
                               "Também há RSPE de: %s. Ficam fora da lista porque não têm pena ativa a acompanhar; esta é a execução em "
                               "andamento." % _desc, "", tipo="outras-execucoes"))
    itens += _lancamentos_seeu(r, crimes, ativos, [i for i in incidentes if not i.get("_ficha")], eventos)
    if rs.sem_condenacao_seeu(r):
        itens.append(_item("verificar", "Execução sem condenação cadastrada no SEEU",
                           "O RSPE só traz o cabeçalho, com a pena total zerada, sem nenhum processo criminal, evento ou incidente: a guia não foi "
                           "cadastrada no SEEU. Não é falha de leitura. Pedir a juntada e o cadastro da guia de recolhimento e o cálculo de pena.",
                           "LEP, arts. 105, 106 e 107.", tipo="execucao-sem-condenacao-seeu"))
    elif rs.sem_crime_seeu(r):
        itens.append(_item("verificar", "Condenação sem crime cadastrado no SEEU",
                           "O processo criminal está no RSPE (pena %s), mas sem nenhum crime lançado (artigo, data do fato e pena imposta). Não é "
                           "falha de leitura. Sem os crimes, frações, prescrição e decretos não são calculados: pedir a correção do cadastro da guia "
                           "no SEEU." % (r.get("pena_total") or "?"),
                           "LEP, arts. 105 e 106, § 1º.", tipo="condenacao-sem-crime-seeu"))
    rot_campo = {v[0]: k for k, v in rs.CAMPOS_MANUAIS.items()}
    for f_ in faltam:
        campo = rot_campo.get(f_)
        if campo:
            it = _item("alerta", "Faltam dados: %s não lido do RSPE - informar" % f_,
                       "O SEEU não imprimiu esse dado (guia sem cálculo, pena interrompida) ou o programa não conseguiu lê-lo. Sem ele, os "
                       "cálculos deste assistido ficam incompletos. Informe pelo botão Preencher (%s), conferindo no PDF ou no SEEU." % rs.CAMPOS_MANUAIS[campo][2],
                       "", tipo="faltam-dados-" + campo)
            it["preencher"] = {"campo": "rspe|" + campo, "rotulo": "%s (%s)" % (f_[:1].upper() + f_[1:], rs.CAMPOS_MANUAIS[campo][2]),
                               "tipo": rs.CAMPOS_MANUAIS[campo][1]}
        else:
            it = _item("alerta", "Faltam dados: %s - informar" % f_,
                       "O programa não leu esse dado do crime no RSPE. Preencha em Prescrição → editar dados (data do fato, pena, sentença e trânsito "
                       "de cada crime): o botão Preencher abre a aba.", "", tipo="faltam-dados-crime")
            it["preencher"] = {"campo": "", "rotulo": f_, "tipo": "ir_presc"}
        itens.append(it)
    for campo, v in (r.get("_manuais") or {}).items():
        rot = rs.CAMPOS_MANUAIS[campo][0]
        it = _item("alerta", "Faltam dados: %s não lido do RSPE - informar" % rot, "", "", tipo="faltam-dados-" + campo)
        it["preencher"] = {"campo": "rspe|" + campo, "rotulo": "%s (%s)" % (rot[:1].upper() + rot[1:], rs.CAMPOS_MANUAIS[campo][2]),
                           "tipo": rs.CAMPOS_MANUAIS[campo][1]}
        val = rs.pena_extenso(v["valor"]) if rs.CAMPOS_MANUAIS[campo][1] == "pena" else (v["valor"].lower() if campo == "regime_atual" else v["valor"])
        it["auto_baixa"] = {"obs": "Dado informado pelo operador (%s): %s. Usado nos cálculos." % (rot, val), "data": v.get("data", "")}
        itens.append(it)
    # dados objetivos que o RSPE não trouxe: o alerta pede o preenchimento (botão "Preencher" na Auditoria)
    if not nasc or r.get("_nasc_fonte"):
        it = _item("verificar", "Data de nascimento não consta no RSPE - informar",
                   "Sem ela o programa não aplica a metade do prazo de prescrição (menor de 21 anos no fato ou maior de 70 na sentença) nem as "
                   "hipóteses de idade do indulto e da comutação, e esses pontos ficam A VERIFICAR. Informe a data pelo botão Preencher "
                   "(ou importe a ficha disciplinar do SIAPEN, que traz a data).",
                   "CP, art. 115; Decretos de indulto (hipóteses por idade).", tipo="nascimento-nao-consta")
        it["preencher"] = {"campo": "data_nascimento", "rotulo": "Data de nascimento (dd/mm/aaaa)", "tipo": "data"}
        if nasc:
            # preenchido (pelo operador ou pela ficha): o alerta sai da contagem e fica como baixado, com a origem do dado
            _dt = r.get("_nasc_data") or ""
            it["auto_baixa"] = {"obs": "Data de nascimento %s: %s%s. Usada nos cálculos (art. 115 e idade no indulto)." % (
                r["_nasc_fonte"], rs.fmt(nasc), (" (RSPE: %s)" % r["_nasc_rspe"]) if r.get("_nasc_rspe") else ""), "data": _dt}
        itens.append(it)
    # indícios de falta: a decisão fica com o operador (botão Preencher); sem sanção reconhecida, tudo fica a apurar (Súmula 533/STJ)
    for fi in rs.faltas_editaveis(incidentes, eventos, hoje):
        dec = fi["decisao"]
        rot = {"sim": "falta grave", "nao": "não houve falta grave"}.get(dec, "")
        fuga = bool(re.search(r"FUGA|EVAS", fi.get("texto") or "", re.I)) and not fi.get("ficha_falta")
        if dec:
            it = _item("verificar", "%s em %s: %s" % ("Fuga" if fuga else "Falta a apurar", fi["data"] or "data não informada", "informar se houve falta grave"),
                       fi["texto"], "LEP, arts. 50 e 118; STJ, Tema 1195.", tipo="falta-a-apurar", ref=fi["chave"])
            it["auto_baixa"] = {"obs": "Decisão do operador: %s. Vale em todas as abas (falta nos 12 meses, indulto, comutação)." % rot, "data": ""}
        elif fi.get("ficha_falta"):
            it = _item("verificar", "%s em %s: a ficha registra a falta, sem sanção reconhecida no RSPE" % (fi["texto"][:40], fi["data"] or "data não informada"),
                       "%s. %s. A ficha explica o indício do RSPE, mas a falta só produz efeitos depois de reconhecida em juízo (Súmula 533/STJ): "
                       "fica \"a apurar\" (falta nos 12 meses, indulto, comutação). Confirmada a sanção, informe pelo botão Preencher." % (fi["texto"], fi["ficha"]),
                       "LEP, arts. 50, 52 e 118; Súmula 533/STJ; STJ, Tema 1195.", tipo="falta-a-apurar", ref=fi["chave"])
        elif fuga:
            it = _item("verificar", "Fuga em %s: em tese falta grave - informar se houve sanção reconhecida" % (fi["data"] or "data não informada"),
                       "%s. A fuga é, em tese, falta grave (LEP, art. 50, II), mas só impede o indulto e a comutação e só move a data-base depois de "
                       "reconhecida em juízo (Súmula 533/STJ), ainda que depois do decreto e salvo inércia ou mora estatal (STJ, Tema 1195). Até "
                       "lá fica \"a apurar\". Informe pelo botão Preencher se houve ou não falta grave." % fi["texto"],
                       "LEP, art. 50, II; Súmula 533/STJ; STJ, Tema 1195.", tipo="falta-a-apurar", ref=fi["chave"])
        else:
            it = _item("verificar", "Falta a apurar em %s: informar se houve falta grave" % (fi["data"] or "data não informada"),
                       "%s. O RSPE não registra sanção reconhecida.%s Informe se houve falta grave: a decisão vale em todas as abas "
                       "(falta nos 12 meses, indulto, comutação, linha do tempo)." % (fi["texto"], (" " + fi["ficha"]) if fi.get("ficha") else
                       " Ficha disciplinar não importada: importá-la ajuda a explicar o indício."), "LEP, arts. 50 e 118; STJ, Tema 1195.",
                       tipo="falta-a-apurar", ref=fi["chave"])
        if fi.get("presc_limite"):
            it["detalhe"] += (" Prescrição da falta disciplinar: 3 anos%s (menor prazo do art. 109 do CP - STJ, AgRg no HC 779.723), até %s; "
                              "depois disso não gera regressão, perda de remidos nem nova data-base." % (
                                  " da recaptura em %s - a fuga é falta permanente (STJ, HC 527.625)" % fi["presc_termo"] if fi.get("presc_fuga") else " do fato",
                                  fi["presc_limite"]))
        elif fi.get("presc_fuga") and fi["data"]:
            it["detalhe"] += " Sem recaptura registrada: a fuga é falta permanente, e a prescrição disciplinar só corre da recaptura (STJ, HC 527.625)."
        it["preencher"] = {"campo": "falta|" + fi["chave"], "rotulo": fi["texto"], "tipo": "falta", "data": fi["data"], "padrao": fi["padrao"], "decisao": dec}
        itens.append(it)
    # falta homologada depois de consumada a prescrição disciplinar (3 anos do fato; na fuga, da recaptura): cabe pedir que
    # a falta seja desconsiderada (regressão, perda de remidos, data-base)
    for i in incidentes:
        if i.get("_ficha") or not rs.RE_FALTA_PROPRIA.search(rs._rotulo_incidente(i)) or rs._negado(i) or rs._pendente(i):
            continue
        d_f, d_d = rs._data_fato_falta(i), rs.to_date(i.get("data_decisao") or "")
        if not d_f or not d_d or d_d <= d_f:
            continue
        fuga = any("INTERRUP" in (e.get("tipo") or "").upper() and rs.RE_FUGA_EV.search(e.get("motivo") or "")
                   and abs(((rs.to_date(e.get("data") or "") or date.min) - d_f).days) <= 3 for e in eventos)
        termo_f, lim_f = rs.prescricao_disciplinar(d_f, fuga, eventos)
        if lim_f and d_d > lim_f:
            itens.append(_item("alerta", "Falta grave de %s homologada depois da prescrição disciplinar" % rs.fmt(d_f),
                               "Homologação em %s; o prazo de %s contado %s terminou em %s. Falta prescrita não gera regressão, perda de dias "
                               "remidos nem nova data-base: cabe pedir que seja desconsiderada." % (
                                   rs.fmt(d_d), "2 anos" if d_f < date(2010, 5, 6) else "3 anos",
                                   ("da recaptura em %s (fuga é falta permanente)" % rs.fmt(termo_f)) if fuga else "do fato", rs.fmt(lim_f)),
                               "CP, art. 109, VI, por analogia; STJ, AgRg no HC 779.723 e HC 527.625.", tipo="falta-homologada-apos-prescricao", ref=rs.fmt(d_f)))
    # contravenção com pena aplicada acima do que a LCP permite: quase sempre erro de cadastro do tipo no SEEU
    # (ex.: art. 35 da LCP no lugar do art. 35 da Lei 11.343/06, associação para o tráfico)
    for c in ativos:
        if rs.num_lei(c.get("lei")) != "3688":
            continue
        _pa = rs.pena_para_dias(c.get("pena_imposta") or "")
        _pm = rs.pena_maxima_abstrata(dict(c))
        if _pa and _pm and _pa > 2 * _pm:
            nome = rs.crimes_curto([c])
            itens.append(_item("verificar", "%s: pena aplicada (%s) muito acima do máximo cominado (%s) - conferir a tipificação no SEEU" % (
                nome, rs.pena_extenso(c.get("pena_imposta")), rs.pena_extenso(rs.dias_para_pena(_pm))),
                "A contravenção tem prisão simples de no máximo %s (e nunca mais de 5 anos - LCP, art. 10). Pena de %s indica provável erro "
                "de cadastro do tipo no SEEU (por exemplo, art. %s da Lei 11.343/06 lançado como Lei 3.688/41). Conferir na sentença: se o crime "
                "for outro, a natureza (impeditivo ou não) e as frações mudam." % (rs.pena_extenso(rs.dias_para_pena(_pm)), rs.pena_extenso(c.get("pena_imposta")), rs.num_art(c.get("artigo"))),
                "LCP, arts. 10 e %s." % rs.num_art(c.get("artigo")), tipo="contravencao-pena-acima-do-maximo", ref=rs.chave_pena_max(c)))
    _pm_vistos = set()
    # medida de segurança informada em Prescrição → editar dados: a pena máxima regula o prazo, qualquer que seja a data do fato
    _ms, _cnt = set(), {}
    for _c0 in r.get("_crimes", []):
        _ch = rp.chave_ajuste(_c0, _cnt)
        if (((r.get("_presc_ajustes") or {}).get(_ch) or {}).get("valores") or {}).get("modalidade") == "MS":
            _ms.add(id(_c0))
    for c in ativos:
        _ff = rs.to_date(c.get("data_infracao") or "")
        if _ff and _ff > date(2022, 12, 25) and id(c) not in _ms:
            continue  # fora da medida de segurança, só o Decreto 11.302/2022 usa a pena máxima em abstrato
        _inf = c.get("_pena_max_inf")
        if _inf or rs.pena_maxima_abstrata(dict(c)) is None:
            ch = rs.chave_pena_max(c)
            if ch in _pm_vistos:
                continue
            _pm_vistos.add(ch)
            nome = rs.crimes_curto([c])
            it = _item("verificar", "%s: pena máxima em abstrato não lida do RSPE - informar" % nome,
                       "O SEEU cortou o texto do tipo penal e o tipo não está na tabela da base jurídica. Sem a pena máxima, %s fica A VERIFICAR. "
                       "Informe a pena máxima cominada pelo botão Preencher." % ("a prescrição da medida de segurança" if id(c) in _ms else
                                                                               "o indulto do Decreto 11.302/2022 (art. 5º: pena máxima de até 5 anos)"),
                       "Decreto 11.302/2022, art. 5º.", tipo="pena-maxima-nao-lida", ref=ch)
            it["preencher"] = {"campo": "pena_max|" + ch, "rotulo": "Pena máxima cominada de %s (ex.: 3 meses, 4 anos, 1 ano e 6 meses)" % nome, "tipo": "pena"}
            if _inf:
                it["auto_baixa"] = {"obs": "Pena máxima informada pelo operador: %s." % rs.dias_para_pena(int(_inf)), "data": c.get("_pena_max_data") or ""}
            itens.append(it)
    # ---------------- 0. extinções registradas em incidentes / cabeçalho ----------------
    if r.get("execucao_extinta"):
        itens.append(_item("alerta", "Execução extinta segundo incidente do RSPE (%s)" % r["execucao_extinta"],
                           "Há incidente de EXTINÇÃO sem processo selecionado: alcança a execução. Conferir se a guia deve ser baixada/arquivada.", "LEP, arts. 66, II, e 109; CP, art. 107.", tipo="execucao-extinta-segundo-incidente-do-rspe"))
    # indulto concedido no RSPE que o cálculo não refletiu: os processos seguem ativos e somados na pena total
    _ind = [c for c in r.get("_crimes", []) if c.get("indultado_rspe") and not (c.get("extinto_rspe") or "").upper().startswith("S")]
    _ind_total = False
    if _ind:
        _pind = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in _ind)
        _vivos = [c for c in r.get("_crimes", []) if not (c.get("extinto_rspe") or "").upper().startswith("S")]
        _soma_todos = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in _vivos)
        _am = [rs.pena_amd(c.get("pena_imposta")) for c in _vivos]
        if all(_am):
            _a, _m, _d = sum(x[0] for x in _am), sum(x[1] for x in _am), sum(x[2] for x in _am)
            _m += _d // 30; _d %= 30; _a += _m // 12; _m %= 12
            _soma_txt = "%da%dm%dd" % (_a, _m, _d)
        else:
            _soma_txt = rs.dias_para_pena(_soma_todos)
        _pt = rs.pena_para_dias(r.get("pena_total"))
        _ind_total = bool(_pt and _pt > _soma_todos - _pind)
        _com = [i for i in incidentes if "COMUTA" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO"
                and any(c.get("processo_criminal") in (i.get("processos") or "") for c in _ind)]
        itens.append(_item("alerta" if _ind_total else "info",
                           "Indulto concedido (%s) sem baixa no cálculo: %s" % (_ind[0].get("data_extincao") or "?", "; ".join(_nome(c) for c in _ind)),
                           "O RSPE registra indulto concedido para %s (penas de %s), mas a linha do crime diz \u201cExtinto: Não\u201d%s. "
                           "Soma de todas as condenações ativas no RSPE: %s; pena total impressa: %s.%s Conferir a decisão do indulto e pedir a retificação do cálculo "
                           "(baixa das penas indultadas), que reflete no término, na progressão e no livramento." % (
                               ", ".join("proc. %s" % c.get("processo_criminal") for c in _ind), " + ".join(rs.dias_para_pena(rs.pena_para_dias(c.get("pena_imposta")) or 0) for c in _ind),
                               " e a pena total continua a incluí-las" if _ind_total else "",
                               _soma_txt, r.get("pena_total") or "?",
                               (" A comutação de %s alcançou os mesmos processos, o que só se explica se o indulto não foi aplicado." % (_com[0].get("data_decisao") or _com[0].get("data_referencia") or "?")) if _com else ""),
                           "CP, art. 107, II; LEP, arts. 66, II, e 192.", tipo="indulto-concedido-sem-baixa-no-calculo"))
    _duv = [c for c in r.get("_crimes", []) if c.get("indulto_duvida")]
    if _duv:
        x = _duv[0]["indulto_duvida"]
        itens.append(_item("verificar", "Indulto de %s seguido de comutação dos mesmos processos: %s" % (x["data"] or "?", "; ".join(_nome(c) for c in _duv)),
                           "O RSPE registra indulto concedido em %s%s para %s, mas a comutação de %s alcançou os mesmos processos, que seguem ativos e somados na pena total. "
                           "O indulto pode ter sido revogado ou reformado em recurso sem registro no RSPE. O programa trata essas penas como em execução; "
                           "conferir a decisão do indulto e o eventual recurso: se o indulto foi mantido, pedir a baixa das penas indultadas." % (
                               x["data"] or "?", (" (Decreto %s)" % x["decreto"]) if x.get("decreto") else "",
                               ", ".join("proc. %s" % c.get("processo_criminal") for c in _duv), x.get("comutacao") or "?"),
                           "CP, art. 107, II; LEP, arts. 66, II, e 192.", tipo="indulto-de-seguido-de-comutacao-dos-mesmos-proce"))
    for c in r.get("_crimes", []):
        if c.get("indultado_rspe") and _ind:
            continue
        if c.get("extincao_fonte") and not (c.get("extinto_rspe") or "").upper().startswith("S"):
            itens.append(_item("info", "%s: extinção registrada (%s), mas a linha do crime diz \"Extinto: %s\"" % (
                _nome(c), c["extincao_fonte"], c.get("extinto_rspe") or "?"),
                "O programa tratou o crime como extinto (não entra na soma das penas, nas frações nem na prescrição). Conferir se o SEEU precisa ser atualizado.",
                "LEP, art. 66, II; CP, art. 107.", tipo="extincao-registrada-mas-a-linha-do-crime-diz-ext", ref=_nome(c)))
    if not pena_total and ativos and not rs.sem_inicio_seeu(r):  # pena não iniciada no SEEU: aviso próprio ("Pena não iniciada")
        soma_at = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos)
        itens.append(_item("alerta", "Guia sem pena calculada: pena total %s com %s" % (r.get("pena_total") or "em branco", rs.pl(len(ativos), "condenação ativa", "condenações ativas")),
                           "As condenações ativas somam %s%s. Sem cálculo de pena, o SEEU não imprime pena cumprida, regime atual, marcos nem término - não é falha "
                           "de leitura. Pedir a unificação/cálculo das penas no SEEU." % (
                               rs.dias_para_pena(soma_at), "" if r.get("regime_atual") else "; Regime Atual em branco"),
                           "LEP, arts. 66, III, a, e 111.", tipo="guia-sem-pena-calculada-pena-total-com"))

    # condenação ativa sem pena imposta: distorce soma, frações e prescrição
    for c in ativos:
        if not (rs.pena_para_dias(c.get("pena_imposta")) or 0):
            itens.append(_item("info", "%s: condenação sem pena imposta no RSPE" % _nome(c),
                               "O RSPE traz \u201cPena Imposta: 0 ano(s), 0 mês(es) e 0 dia(s)\u201d no processo %s. Esse crime não entra na soma das penas; "
                               "conferir a sentença e o lançamento no SEEU." % (c.get("processo_criminal") or "-"),
                               "LEP, art. 66, III, a.", tipo="condenacao-sem-pena-imposta-no-rspe", ref=_nome(c)))

    # ---------------- 1. coerência aritmética do RSPE ----------------
    soma = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos)
    _amds = [rs.pena_amd(c.get("pena_imposta")) for c in ativos]
    _tot = rs.pena_amd(r.get("pena_total"))
    if pena_total and soma and _tot and all(_amds):
        _comut = [i for i in incidentes if "COMUTA" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO"]
        _comutados = any("COMUTAD" in (c.get("processo_situacao") or "").upper() for c in ativos)
        if rs.amd_normal(sum(x[0] for x in _amds), sum(x[1] for x in _amds), sum(x[2] for x in _amds)) != rs.amd_normal(*_tot) and (_comut or _comutados) and soma > pena_total:
            itens.append(_item("info", "Soma das penas maior que a pena total: compatível com comutação",
                               "Soma das penas originais: %s; pena total impressa: %s. Há %s%s - a pena total já considera a redução." % (
                                   rs.dias_para_pena(soma), r.get("pena_total"), rs.pl(len(_comut), "comutação concedida", "comutações concedidas"), " e processos marcados \"(Comutada)\"" if _comutados else ""),
                               "Decretos de comutação; LEP, art. 192.", tipo="soma-das-penas-maior-que-a-pena-total-compativel"))
        elif _ind_total:
            pass  # divergência explicada pelo indulto sem baixa (item acima)
        elif rs.amd_normal(sum(x[0] for x in _amds), sum(x[1] for x in _amds), sum(x[2] for x in _amds)) != rs.amd_normal(*_tot):
            _extintos = [c for c in r.get("_crimes", []) if c.get("extinto", "").upper().startswith("S")]
            _rotulo = "Soma das penas dos crimes%s" % (" não extintos" if _extintos else " listados")
            # unificação/somatório com valor impresso: é o total que deveria valer
            _unif = []
            for i in incidentes:
                if i.get("situacao") == "CONCEDIDO" and re.search(r"UNIFICA|SOMAT", (i.get("tipo") or ""), re.I):
                    _v = rs.pena_para_dias(i.get("complemento") or "")
                    _d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
                    if _v:
                        _unif.append((_d or date.min, _v, (i.get("tipo") or "").lower()))
            _unif.sort()
            _extra = ""
            if _unif and abs(_unif[-1][1] - soma) <= 31 and _unif[-1][1] != pena_total:
                _extra = (" A %s de %s fixou a pena em %s, que confere com a soma dos crimes; a pena total impressa é %s maior. "
                          "Se a guia não foi recalculada depois da unificação, o término, a progressão e o livramento estão adiados." % (
                              _unif[-1][2], rs.fmt(_unif[-1][0]) if _unif[-1][0] != date.min else "data não informada",
                              rs.dias_para_pena(_unif[-1][1]), rs.dias_para_pena(abs(pena_total - _unif[-1][1]))))
            itens.append(_item("alerta", "Soma das penas difere da pena total",
                               "%s: %s; pena total impressa: %s (diferença %s).%s" % (
                                   _rotulo, rs.dias_para_pena(soma), rs.dias_para_pena(pena_total), rs.dias_para_pena(abs(soma - pena_total)), _extra),
                               "LEP, arts. 66, III, a, e 111 (soma/unificação); CP, art. 75, § 2º; possível pena extinta, comutada, detração ou unificação não refletida no cálculo.", tipo="soma-das-penas-difere-da-pena-total"))
        else:
            itens.append(_item("ok", "Soma das penas confere com a pena total", "Soma das penas = total %s." % r.get("pena_total"), tipo="soma-das-penas-confere-com-a-pena-total"))
    _t, _c, _r = rs.pena_amd(r.get("pena_total")), rs.pena_amd(r.get("pena_cumprida")), rs.pena_amd(r.get("pena_remanescente"))
    if _t and _c and _r:
        # conferência em anos/meses/dias, como o SEEU soma (não em dias corridos)
        if rs.amd_normal(_c[0] + _r[0], _c[1] + _r[1], _c[2] + _r[2]) != rs.amd_normal(*_t):
            itens.append(_item("alerta", "Cumprida + remanescente ≠ pena total",
                               "%s + %s = %s, mas a pena total é %s." % (rs.dias_para_pena(cumprida), rs.dias_para_pena(reman), rs.dias_para_pena(cumprida + reman), rs.dias_para_pena(pena_total)),
                               "Coerência interna do atestado; pedir recálculo/atestado atualizado.", tipo="cumprida-remanescente-pena-total"))
    # remições
    rem_inc = 0
    for i in incidentes:
        if rs.e_remicao_concedida(i):
            rem_inc += rs.dias_de(i.get("complemento", "")) or 0
    m = rs.re.search(r"\(" + rs.NUM_DIAS + r"\s*dias remidos\s*-\s*" + rs.NUM_DIAS + r"\s*dias perdidos\)", r.get("saldo_remidos", ""), rs.re.I)
    if m:
        remidos, perdidos = rs.num_br(m.group(1)), rs.num_br(m.group(2))
        if rem_inc and abs(rem_inc - remidos) > 0.01:
            itens.append(_item("alerta", "Dias remidos: incidentes não fecham com o saldo",
                               "Incidentes de remição somam %s; o resumo diz %s remidos (%s perdidos)." % (rs.pl(rem_inc, "dia", "dias"), rs.num_txt(remidos), rs.num_txt(perdidos)),
                               "LEP, arts. 126 e 127.", tipo="dias-remidos-incidentes-nao-fecham-com-o-saldo"))
        if perdidos:
            itens.extend(_perda_remidos(incidentes, perdidos, eventos))
    # RSPE anterior a correções de cálculo do SEEU
    itens.extend(_correcoes_seeu(r, crimes, incidentes))
    # pena integralmente cumprida
    if pena_total and cumprida is not None and cumprida >= pena_total and "ATIVO" in (r.get("status_execucao") or "").upper():
        itens.append(_item("alerta", "Pena integralmente cumprida com execução ativa",
                           "Cumprida %s ≥ total %s: cabe extinção da pena." % (rs.dias_para_pena(cumprida), rs.dias_para_pena(pena_total)), "LEP, art. 109; CP, art. 107.", tipo="pena-integralmente-cumprida-com-execucao-ativa"))

    reinc_sem_base = []
    # ---------------- 2. crime a crime: hediondez, VGA, frações ----------------
    for c in ativos:
        nome = _nome(c)
        art = rs.num_art(c.get("artigo"))
        lei = rs.num_lei(c.get("lei"))
        fato = rs.to_date(c.get("data_infracao") or "")
        # reincidência pela lei, a mesma na progressão e no livramento (CP, arts. 63 e 64, I): a marcação do RSPE ou condenação
        # anterior transitada antes do fato, fora a depurada
        reinc_ef, marc, _ant, _dep = _reincidencia_legal(c, crimes_pessoa)
        reinc = reinc_ef
        if not marc and _ant:
            itens.append(_item("verificar", "%s: reincidente pela lei, mas o RSPE não marca a reincidência" % nome,
                               "Condenação anterior transitada antes do fato (%s): %s. Pela lei (CP, art. 63), é reincidente; a Auditoria confere as "
                               "frações de progressão e livramento como reincidente. Conferir a sentença e a certidão de antecedentes." % (
                                   rs.fmt(fato), "; ".join("%s, trânsito em %s" % (_nome(o), rs.fmt(_transito(o))) for o in _ant)),
                               "CP, arts. 63 e 64, I; LEP, art. 112; CP, art. 83.", tipo="reincidente-pela-lei-sem-marcacao", ref=nome))
        if _dep and not _ant:
            itens.append(_item("verificar" if marc else "info", "%s: condenação anterior depurada (CP, art. 64, I)" % nome,
                               "%s: entre a extinção da pena anterior e o fato (%s) passaram mais de 5 anos - não gera reincidência.%s" % (
                                   "; ".join("%s, extinta em %s" % (_nome(o), o.get("data_extincao")) for o in _dep), rs.fmt(fato),
                                   " O RSPE marca reincidência: conferir se há outra condenação não listada; se não houver, as frações são de primário." if marc else ""),
                               "CP, art. 64, I.", tipo="condenacao-anterior-depurada", ref=nome))
        reinc_esp = c.get("reincidente_especifico") == "S"
        # violência ou grave ameaça: a marcação do RSPE ou a elementar do tipo (ameaça, roubo, extorsão, estupro, lesão e homicídio
        # dolosos) - o percentual do art. 112 segue as elementares do tipo da condenação (STJ, HC 1.032.430, 6ª T., 11/03/2026)
        vga_tipo = rs.vga_elementar(c) and c.get("vga") != "S"
        vga = c.get("vga") == "S" or rs.vga_elementar(c)
        morte = c.get("resultado_morte") == "S"
        hed_seeu = _hediondo_seeu(c)
        hed_lei, obs_h = _e_hediondo_lei(c)
        esp_ok = None  # reincidência específica em hediondo/tráfico: True confirmada no RSPE, False não aferível
        if reinc_esp and (hed_seeu or hed_lei or _trafico(c) or _trafico_pessoas(c)):
            _conf, _semt, _naoh = _reinc_especifica(c, crimes_pessoa)
            _pp = (rs.pct_rotulo(c.get("fracao_progressao")) or "?").split(" - ")[0]
            _fx = "%s e livramento %s" % (_pp, "vedado" if (_fr_seeu(c.get("fracao_livramento")) or 0) >= 1 else (c.get("fracao_livramento") or "?").split(" - ")[0])
            if _conf:
                esp_ok = True
                o = _conf[0]
                itens.append(_item("ok", "%s: reincidência específica confere com o RSPE" % nome,
                                   "Condenação anterior: %s, trânsito em %s, antes do fato (%s). O RSPE aplica %s." % (
                                       _nome(o), rs.fmt(_transito(o)), rs.fmt(fato), _fx),
                                   "CP, arts. 63 e 83, V; LEP, art. 112, VII; Lei 11.343/06, art. 44, p. ú.", tipo="reincidencia-especifica-confere-com-o-rspe", ref=nome))
            else:
                esp_ok = False
                partes = ["%s (fato %s): sem trânsito em julgado no RSPE, não é possível aferir se transitou antes de %s" % (
                    _nome(o), o.get("data_infracao") or "não informado", rs.fmt(fato) if fato else "o fato") for o in _semt]
                partes += ["%s (trânsito %s): %s: não gera reincidência específica em hediondo" % (
                    _nome(o), rs.fmt(_transito(o)), "tráfico privilegiado, não hediondo" if "§ 4" in (o.get("tipo_penal") or "") else "não é hediondo") for o in _naoh]
                if not _semt:
                    partes.append("nenhuma condenação anterior por hediondo, equiparado ou tráfico de pessoas (CP, art. 83, V) consta no RSPE; pode vir de processo não listado (certidão de antecedentes)")
                itens.append(_item("alerta", "%s: reincidência específica não demonstrada no RSPE (%s)" % (nome, _fx),
                                   "O RSPE marca “Reincidente específico: S”. %s. Sem condenação anterior por hediondo/equiparado transitada antes do fato, "
                                   "%s e o livramento é possível (2/3), salvo nas hipóteses de vedação do art. 112 da LEP (como o crime hediondo com resultado morte). O RSPE aplica %s. "
                                   "Conferir a certidão de trânsito em julgado." % ("; ".join(partes)[0].upper() + "; ".join(partes)[1:],
                                       ("a progressão é de 1/6, ainda que haja reincidência (LEP, art. 112, redação anterior à Lei 13.964/2019; fato anterior à Lei 11.464/2007: STJ Súmula 471; STF Súmula Vinculante 26)"
                                        if fato and fato < date(2007, 3, 29) else
                                        "a progressão é de 3/5 só se houver reincidência em qualquer crime, e de 2/5 sem ela (Lei 8.072/90, art. 2º, § 2º, na redação da Lei 11.464/2007, vigente no fato)"
                                        if fato and fato < date(2020, 1, 23) else
                                        "o percentual, por analogia, é o do primário (70%, ou 75% com morte), sem precedente específico sobre a Lei 15.358/2026 - conferir (ratio dos STJ Temas 1084 e 1196; STF Tema 1169)"
                                        if fato and fato >= date(2026, 3, 25) else
                                        "o percentual é o do reincidente genérico (40%, ou 50% com morte; STJ Temas 1084 e 1196, STF Tema 1169)"), _fx),
                                   "CP, arts. 63 e 83, V; LEP, art. 112, VII; Lei 11.343/06, art. 44, p. ú.; STJ Tema 1084; STF Tema 1169.", tipo="reincidencia-especifica-nao-demonstrada-no-rspe", ref=nome))
        # dados ausentes
        if art and c.get("artigo_inferido"):
            if c.get("lei_do_tempo"):
                itens.append(_item("verificar", "%s: tipo reconhecido pela descrição, conforme a lei da data do fato" % nome,
                                   "O SEEU não registrou o artigo; a descrição \u201c%s\u201d é a do tipo atual. %s." % (_descricao_tipo(c), c["lei_do_tempo"][0].upper() + c["lei_do_tempo"][1:]),
                                   "CF, art. 5º, XL; CP, arts. 1º e 2º.", tipo="tipo-reconhecido-pela-descricao-conforme-a-lei-d", ref=nome))
            else:
                itens.append(_item("info", "%s: artigo reconhecido pela descrição do tipo" % nome,
                                   "O SEEU não registrou o artigo; a descrição \u201c%s\u201d corresponde a este tipo penal%s. Hediondez, VGA e frações foram conferidas com ele." % (
                                       _descricao_tipo(c), (", vigente na data do fato (%s)" % c.get("data_infracao")) if c.get("data_infracao") else ""), "", tipo="artigo-reconhecido-pela-descricao-do-tipo", ref=nome))
        if art and c.get("artigo_letra"):
            itens.append(_item("info", "%s: artigo completado pela descrição" % nome,
                               "O RSPE traz o artigo sem a letra (a tabela de tipificação do SEEU grava assim); pela descrição \u201c%s\u201d, "
                               "o tipo é o art. %s. Hediondez, VGA e frações foram conferidas com ele." % (
                                   _descricao_tipo(c), art), "", tipo="artigo-completado-pela-descricao", ref=nome))
        if not art:
            itens.append(_item("info", "%s: artigo não informado" % nome, "O SEEU não registrou o artigo e a descrição do tipo não foi reconhecida: \u201c%s\u201d." % _descricao_tipo(c), "Sem o artigo, hediondez, VGA e frações ficam sem conferência.", tipo="artigo-nao-informado", ref=nome))
        # lei do tempo: capitulação criada depois do fato (anacronismo do cadastro) e hediondez posterior ao fato
        _dc, _lc = rs.tipo_criado_em(c)
        _desc = rs.tipo_criado_desc(c)
        _dh, _lh = rs.hediondo_desde(c)
        if fato and _dc and fato < _dc:
            itens.append(_item("alerta", "%s: %s criad%s depois do fato (%s)" % (
                nome, ("%s (%s)" % (_desc[0], _desc[1].split(",")[0])) if _desc else "capitulação", "o" if (_desc and _desc[0] == "tipo") else "a", rs.fmt(fato)),
                               "%s foi criad%s pela %s, em vigor desde %s; o fato é de %s.%s "
                               "A sentença usou a redação da época: o cadastro no SEEU está anacrônico. Conferir a capitulação da sentença - ela "
                               "decide a hediondez (%s), a fração de progressão e livramento e a vedação do indulto e da comutação." % (
                                   _cap_criada(c, _desc), "o" if (_desc and _desc[0] == "tipo") else "a", _lc.split(" (")[0], rs.fmt(_dc), rs.fmt(fato),
                                   (" Na data do fato, %s." % _desc[2]) if _desc else "",
                                   ("não era hediondo na data do fato: hediondez só desde %s" % rs.fmt(_dh)) if (_dh and fato < _dh) else "conferir"),
                               "CF, art. 5º, XL; CP, arts. 1º e 2º; Lei 8.072/90.", tipo="capitulacao-criada-depois-do-fato", ref=nome))
        elif fato and _dh and fato < _dh and not _hediondo_seeu(c) and rs.e_hediondo(c, date.today()):
            itens.append(_item("verificar", "%s: hediondez posterior ao fato (hediondo só desde %s)" % (nome, rs.fmt(_dh)),
                               "Fato em %s; o tipo passou a ser hediondo pela %s, em vigor desde %s. Progressão e livramento: vale a lei da época, "
                               "sem as frações de hediondo (CF, art. 5º, XL)%s. Indulto e comutação: o STJ afere a hediondez na data do decreto e "
                               "mantém a vedação; tese defensiva: irretroatividade (a vedação alcança só fatos posteriores à lei)." % (
                                   rs.fmt(fato), _lh or "lei", rs.fmt(_dh),
                                   ""),
                               "CF, art. 5º, XL; CP, art. 2º; Lei 8.072/90; STF, 2ª T., RHC 267.297 AgR.", tipo="hediondez-posterior-ao-fato", ref=nome))
        if not fato:
            itens.append(_item("info", "%s: data do fato ausente" % nome, "Sem a data do fato não se aplica a lei do tempo (frações de progressão, art. 115 CP).", "CF, art. 5º, XL; STJ Tema 1354.", tipo="data-do-fato-ausente", ref=nome))
        if not c.get("transito_processo") and not c.get("transito_mp"):
            itens.append(_item("info", "%s: trânsito em julgado não informado" % nome,
                               "Sem trânsito o RSPE pode estar em execução provisória; afeta a prescrição executória. O indulto não depende do trânsito "
                               "(Decretos 12.338/2024 e 12.790/2025, art. 2º; Decreto 11.302/2022, art. 9º).", "CP, art. 112, I; STF Tema 788.", tipo="transito-em-julgado-nao-informado", ref=nome))
        # hediondez
        if hed_lei is True and not hed_seeu:
            itens.append(_item("info", "%s: hediondo/equiparado pela lei, mas o SEEU aplicou fração comum (favorece o apenado)" % nome,
                               "No RSPE: progressão %s; livramento %s." % (rs.pct_rotulo(c.get("fracao_progressao")), c.get("fracao_livramento")), "Lei 8.072/90, art. 1º; LEP, art. 112; CP, art. 83, V.", tipo="hediondo-equiparado-pela-lei-mas-o-seeu-aplicou", ref=nome))
        elif hed_seeu and rs.hediondo_na_epoca(c) is False:
            _d, _lei = rs.hediondo_desde(c)
            itens.append(_item("alerta", "%s: SEEU tratou como hediondo, mas o fato (%s) é anterior à lei que o tornou hediondo (%s, vigência %s)" % (
                nome, rs.fmt(fato) if fato else "?", _lei or "?", rs.fmt(_d)),
                "A hediondez se rege pela lei da data do fato (irretroatividade da lei penal mais gravosa). Reflete no percentual de progressão (comum, não 40%%-60%% ou 70%%+), no livramento (1/3-1/2, não 2/3) e no indulto (art. 1º dos decretos). No RSPE: progressão %s; livramento %s." % (
                    rs.pct_rotulo(c.get("fracao_progressao")), c.get("fracao_livramento")),
                "CF, art. 5º, XL; CP, art. 2º; Lei 8.072/90 e alterações; STJ, Temas 1084 e 1196.", tipo="seeu-tratou-como-hediondo-mas-o-fato-e-anterior", ref=nome))
        elif hed_lei is False and hed_seeu and ("HEDIONDO" in (c.get("fracao_progressao") or "").upper() or not (lei == "11343" and art in ("33", "34", "35", "36", "37"))):
            itens.append(_item("alerta", "%s: SEEU tratou como hediondo, mas o tipo não consta do rol" % nome,
                               (obs_h or "Verificar a capitulação (qualificadora/§) que justifique a hediondez.") + " No RSPE: progressão %s; livramento %s." % (rs.pct_rotulo(c.get("fracao_progressao")), c.get("fracao_livramento")),
                               "Lei 8.072/90, art. 1º; LEP, art. 112, § 5º.", tipo="seeu-tratou-como-hediondo-mas-o-tipo-nao-consta", ref=nome))
        elif hed_lei is None and art:
            itens.append(_item("info", "%s: hediondez depende do parágrafo/inciso" % nome, "Hediondo apenas se: %s. SEEU aplicou %s." % (obs_h, "fração de hediondo" if hed_seeu else "fração comum"), "Lei 8.072/90, art. 1º.", tipo="hediondez-depende-do-paragrafo-inciso", ref=nome))
        # VGA
        esperado = rg.vga_esperado(art, "2848" if (lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())) else lei) if art else None
        # só a marcação que prejudica (VGA = S onde o tipo não a exige); VGA = N a mais é favorável e não se aponta
        if esperado and c.get("vga") == "S" and esperado != c.get("vga"):
            itens.append(_item("alerta" if c.get("vga") == "S" else "info", "%s: marcação de violência/grave ameaça diverge do tipo" % nome,
                               "RSPE: VGA = %s; pelo tipo penal esperava-se %s. Reflete nas frações de progressão e no indulto (arts. 9º, I a III dos decretos)." % (c.get("vga"), esperado),
                               ("LEP, art. 112, I e II (redação da Lei 15.402/2026)" if fato and fato >= date(2026, 5, 8) else "LEP, art. 112, III e IV") + "; Decretos 12.338/2024 e 12.790/2025.", tipo="marcacao-de-violencia-grave-ameaca-diverge-do-ti", ref=nome))
        # fração de progressão
        f_seeu = _fr_seeu(c.get("fracao_progressao"))
        hed = hed_lei if hed_lei is not None else hed_seeu
        _tp = c.get("tipo_penal") or ""
        _cp = lei in ("2848", "") or ("PENAL" in (c.get("lei") or "").upper() and "MILITAR" not in (c.get("lei") or "").upper())
        especial = None
        if c.get("comando_orcrim") == "S":
            especial = "comando_orcrim"
        elif _cp and art == "288-A":
            especial = "milicia"
        elif _cp and (art == "121-A" or (art == "121" and rs.re.match(r"\s*§\s*2[ºo°]?\s*,?\s*(inciso\s*)?VI\b", _tp))):
            especial = "feminicidio_primario"
        # desde 25/03/2026 o VI, b exige organização criminosa ULTRAVIOLENTA: o RSPE não diz; 75% só se o SEEU aplicou (conferir)
        orcrim_uv = especial == "comando_orcrim" and fato and fato >= date(2026, 3, 25)
        if orcrim_uv:
            especial = None
        f_esp, rot, obs = rg.fracao_mais_benefica(fato, hed, morte, vga, reinc, especial=especial)
        _conf_g, _semt_g, _ = _reinc_especifica(c, crimes_pessoa) if (reinc and not reinc_esp and hed) else ([], [], [])
        if reinc and not reinc_esp and hed and not _conf_g:
            # campo "reincidente específico" não marcado e nenhuma condenação anterior por hediondo transitada antes do fato no RSPE
            if not _semt_g:
                obs = obs + ["sem condenação anterior por hediondo transitada antes do fato no RSPE"]
            for _dref in ([fato, date(2020, 1, 23)] if fato and fato < date(2020, 1, 23) else [fato]):
                f_esp2, rot2, obs2 = rg.fracao_progressao_esperada(_dref, hed, morte, vga, reinc, reinc_especifico=False, especial=especial)
                if f_esp2 is not None and (f_esp is None or f_esp2 < f_esp):
                    f_esp, rot, obs = f_esp2, rot2, obs + obs2 + (["retroatividade da lei mais benéfica (Lei 13.964/2019; STJ Tema 1084)"] if _dref != fato else [])
        # reincidente em crime com VGA: o RSPE não diz se a condenação anterior teve violência; se não teve, a base prevê o
        # percentual do primário com VGA por analogia (vga_reincidente_generico). Só informa: o esperado segue o vga_reincidente
        _jan = rg.regime_progressao(fato) if fato else None
        _vg = (_jan or {}).get("vga_reincidente_generico")
        vga_gen = False
        if (vga and reinc and not reinc_esp and not hed and not especial and _vg and f_seeu is not None
                and float(f_seeu) > float(rg.fr(_vg)) + 0.001):
            vga_gen = True
            # condenações anteriores do RSPE (transitadas antes deste fato, de outro processo): decidem a natureza da reincidência
            _ant = [x for x in crimes_pessoa if x is not c and fato and not rs.mesmo_processo(x.get("processo_criminal"), c.get("processo_criminal"))
                    and (rs.to_date(x.get("transito_processo") or x.get("transito_mp") or "") or date.max) < fato]
            if _ant and any(rs.vga_indulto(x) for x in _ant):
                vga_gen = False  # reincidente em crime violento: o percentual do SEEU está certo
            elif _ant:
                itens.append(_item("alerta", "%s: reincidente em crime com violência ou grave ameaça, mas a condenação anterior não teve violência - %s" % (nome, _vg),
                                   "O SEEU aplica %s. As condenações anteriores do RSPE, transitadas antes do fato (%s), não têm violência ou grave ameaça: a "
                                   "reincidência não é em crime violento, e o STJ aplica, por analogia in bonam partem, o percentual do primário com violência: "
                                   "%s (AgRg no HC 675.062, 6ª T., 03/08/2021; Tema 1084). Se houver outra condenação, fora deste RSPE, por crime violento, "
                                   "o percentual do SEEU se mantém." % (rs.pct_rotulo(c.get("fracao_progressao")), rs.crimes_curto(_ant), _vg),
                                   "LEP, art. 112, III e IV; STJ, AgRg no HC 675.062; Tema 1084.", tipo="reincidente-vga-percentual-se-nao-especifica", ref=nome))
        if vga_gen and not _ant_decidiu(itens, nome):
            itens.append(_item("verificar", "%s: reincidente em crime com violência ou grave ameaça - %s se a reincidência não for em crime violento" % (nome, _vg),
                               "O SEEU aplica %s. Se a condenação anterior não foi por crime com violência ou grave ameaça, o STJ aplica, por analogia in "
                               "bonam partem, o percentual do primário com violência: %s (AgRg no HC 675.062, 6ª T., 03/08/2021; Tema 1084). O RSPE não "
                               "informa a natureza da condenação anterior: conferir a certidão de antecedentes." % (rs.pct_rotulo(c.get("fracao_progressao")), _vg),
                               "LEP, art. 112, III e IV; STJ, AgRg no HC 675.062; Tema 1084.", tipo="reincidente-vga-percentual-se-nao-especifica", ref=nome))
        if orcrim_uv:
            itens.append(_item("verificar", "%s: comando de organização criminosa (fato em %s) - 75%% só se a organização for ultraviolenta" % (nome, rs.fmt(fato)),
                               "Desde 25/03/2026 (Lei 15.358/2026), o art. 112, VI, b, da LEP prevê 75%%, vedado o livramento, ao condenado por exercer o comando de organização "
                               "criminosa ultraviolenta estruturada para a prática de crime hediondo ou equiparado. O RSPE não informa se a organização é ultraviolenta: "
                               "sem essa qualificação, vale o percentual do crime. No RSPE: progressão %s." % rs.pct_rotulo(c.get("fracao_progressao")),
                               "LEP, art. 112, VI, b (redação da Lei 15.358/2026).", tipo="comando-de-organizacao-criminosa-fato-em-75-so-s", ref=nome))
        if orcrim_uv and f_seeu is not None and abs(float(f_seeu) - 0.75) <= 0.01:
            pass  # 75% aplicado pelo SEEU: depende da qualificação "ultraviolenta" (item acima)
        elif f_seeu is not None and f_esp is not None:
            if abs(Fraction(f_seeu) - Fraction(f_esp)) > Fraction(1, 2000):
                itens.append(_item("alerta" if float(f_seeu) > float(f_esp) else "info",
                               ("%s: percentual de progressão do SEEU (%s) maior que o legal (%s)" if float(f_seeu) > float(f_esp) else "%s: percentual de progressão do SEEU (%s) menor que o esperado (%s) - favorece o apenado") % (nome, rs.pct_rotulo(c.get("fracao_progressao")), rs.pct_rotulo(rot)),
                               ("Fato em %s; %s; %s; %s. %s" % (rs.fmt(fato) if fato else "?", ("reincidente genérico (o cálculo não marca reincidência específica)"
                                                                if "reincidente genérico" in " ".join(obs) else "reincidente") if reinc else "primário", "com VGA" if vga else "sem VGA",
                                                               "hediondo" if hed else "comum", rs.pct_texto(" ".join(obs)))).strip() + (
                                   " Violência ou grave ameaça elementar do tipo (o RSPE não a marca): o percentual segue as elementares do tipo da condenação "
                                   "(STJ, HC 1.032.430, 6ª T., 11/03/2026)." if vga_tipo else "") + (
                                   " Ameaça (art. 147): a grave ameaça é elementar - 25% para o primário (TJMG, 6ª Câm., 0104039-06.2026; TJRS, 7ª Câm., "
                                   "8000046-39.2026; TJSP, 4ª Câm., 0007776-29.2025); em sentido contrário, TJSP, 7ª Câm., 0014444-50.2024 (tese defensiva)."
                                   if art == "147" and _cp else ""),
                               "LEP, art. 112 (redação vigente na data do fato; lei posterior só retroage se mais benéfica - CF, art. 5º, XL; STJ Temas 1084, 1196 e 1354; STF Tema 1169).", tipo="percentual-de-progressao-diverge", ref=nome))
            elif esp_ok is False or vga_gen:
                pass  # o alerta de reincidência específica / o item dos 25% já tratam do percentual
            else:
                nota = " ".join(obs) or "Conforme a lei da data do fato."
                itens.append(_item("ok", "%s: percentual de progressão confere (%s)" % (nome, rs.pct_rotulo(c.get("fracao_progressao"))), rs.pct_texto(nota), "LEP, art. 112.", tipo="percentual-de-progressao-confere", ref=nome))
        # fração de livramento
        if pena_total and pena_total < rg.carregar().get("livramento", {}).get("pena_minima_anos", 2) * rs.DIAS_ANO and c.get("fracao_livramento"):
            itens.append(_item("info", "%s: livramento condicional com pena total inferior a 2 anos" % nome,
                               "O RSPE calcula fração de livramento (%s), mas o benefício exige pena igual ou superior a 2 anos (pena total %s)." % (c.get("fracao_livramento"), rs.dias_para_pena(pena_total)),
                               "CP, art. 83, caput.", tipo="livramento-condicional-com-pena-total-inferior-a", ref=nome))
        fl_seeu = _fr_seeu(c.get("fracao_livramento"))
        trafico = _trafico(c)
        fl_esp, rotl = rg.fracao_livramento_esperada(hed, reinc_ef, trafico, _trafico_pessoas(c))
        jv = rg.regime_progressao(fato) if fato else None
        chave_m = "hediondo_morte_reincidente" if reinc_ef else "hediondo_morte_primario"
        lc_vedado = bool(jv and hed and morte and chave_m in (jv.get("vedado_lc") or []))
        lc_vedado_esp = bool(jv and especial and jv.get(especial) and especial in (jv.get("vedado_lc") or [])
                             and not (especial == "feminicidio_primario" and reinc_ef))
        if esp_ok is True or _conf_g:
            # reincidente específico em hediondo/tráfico, demonstrado no RSPE: livramento vedado (CP, art. 83, V; Lei 11.343/06, art. 44, p. ú.)
            fl_esp, rotl = Fraction(1, 1), "vedado (reincidente específico)"
        elif esp_ok is False:
            # marcação sem condenação anterior que a demonstre: o esperado segue a fração do crime (o item próprio explica)
            rotl += " - reincidência específica não demonstrada no RSPE"
        if lc_vedado:
            # LEP, art. 112, VI, a e VIII (Lei 13.964/2019): livramento vedado - o 1/1 do SEEU é o correto
            fl_esp, rotl = Fraction(1, 1), "vedado (LEP, art. 112, VI, a/VIII)"
        elif lc_vedado_esp:
            fl_esp, rotl = Fraction(1, 1), "vedado (%s)" % rg.ESPECIAIS.get(especial, especial)
        if orcrim_uv and fl_seeu is not None and float(fl_seeu) >= 1:
            # a vedação do livramento (VI, b) depende da mesma qualificação "ultraviolenta" que o RSPE não informa
            itens.append(_item("verificar", "%s: livramento vedado pelo SEEU (1/1) - só se a organização for ultraviolenta" % nome,
                               "Desde 25/03/2026, o art. 112, VI, b, da LEP veda o livramento ao comando de organização criminosa ultraviolenta. "
                               "O RSPE não informa essa qualificação: sem ela, vale a fração de livramento do crime (%s)." % rotl,
                               "LEP, art. 112, VI, b (redação da Lei 15.358/2026); CP, art. 83.", tipo="livramento-vedado-pelo-seeu-1-1-so-se-a-organiza", ref=nome))
        elif fl_seeu is not None and abs(float(fl_seeu) - float(fl_esp)) > 0.005:
            itens.append(_item("alerta" if float(fl_seeu) > float(fl_esp) else "info",
                               ("%s: fração de livramento do SEEU (%s) maior que a legal (%s)" if float(fl_seeu) > float(fl_esp) else "%s: fração de livramento do SEEU (%s) menor que a esperada (%s) - favorece o apenado") % (nome, c.get("fracao_livramento"), rotl),
                               "%s; %s." % (("reincidente genérico (o cálculo não marca reincidência específica%s)" % (
                                                 "; sem condenação anterior por hediondo transitada antes do fato no RSPE" if not _conf_g and not _semt_g else "")
                                             if hed and esp_ok is not True
                                             and (c.get("reincidente_especifico") or "").upper() != "S" else "reincidente") if reinc_ef else "primário",
                                            "hediondo/equiparado" if hed else ("art. 44, p. ú., Lei 11.343/06" if trafico else
                                                                                                  "tráfico de pessoas, art. 83, V, CP" if _trafico_pessoas(c) else "comum")) + (
                                   " A fração 1/1 só cabe a hediondo de reincidente específico; lançada em crime comum (muitas vezes para "
                                   "\"revogar\" o livramento na implantação do processo, em vez do incidente próprio), o SEEU trata o crime como "
                                   "hediondo e trava indulto e comutação: pedir a correção da fração." if (c.get("fracao_livramento") or "").startswith("1/1") and not hed else ""),
                               "CP, art. 83; Lei 11.343/06, art. 44, p. ú.", tipo="fracao-de-livramento-diverge", ref=nome))
        if lc_vedado:
            itens.append(_item("info", "%s: hediondo com resultado morte, fato em %s - livramento vedado" % (nome, rs.fmt(fato)),
                               ("O RSPE aplica 1/1 no livramento, como manda a lei da data do fato (LEP, art. 112, VI, a, e VIII, na redação da %s). "
                                "Para fatos anteriores a 23/01/2020, o STJ admite o 50%% sem a vedação ao livramento (Tema 1196; CP, art. 83, V); "
                                "a questão está pendente no STF (Tema 1319, repercussão geral reconhecida, sem julgamento de mérito).") % (
                                   "Lei 15.358/2026" if fato and fato >= date(2026, 3, 25) else "Lei 13.964/2019"),
                               "LEP, art. 112; STJ Tema 1196; STF Tema 1319 (pendente).", tipo="hediondo-com-resultado-morte-fato-em-livramento", ref=nome))
        elif lc_vedado_esp:
            itens.append(_item("info", "%s: %s, fato em %s - livramento vedado" % (nome, rg.ESPECIAIS.get(especial, especial), rs.fmt(fato)),
                               "A lei da data do fato veda o livramento condicional nesta hipótese; o 1/1 do SEEU é o correto.", "LEP, art. 112, VI-A e VI, b e d.", tipo="fato-em-livramento-vedado", ref=nome))
        # reincidência: precisa de condenação anterior transitada antes do fato (consolidado após o laço)
        if marc and fato:
            anteriores = [o for o in crimes_pessoa if o is not c and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "") and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < fato]
            if not anteriores:
                reinc_sem_base.append(fato)
        # idade
        if nasc:
            i_fato = fato.year - nasc.year - ((fato.month, fato.day) < (nasc.month, nasc.day)) if fato else None
            if i_fato is not None and i_fato < 21:
                itens.append(_item("info", "%s: menor de 21 anos no fato (%d) - prescrição pela metade" % (nome, i_fato),
                                   "Os prazos de prescrição caem pela metade (CP, art. 115); a aba Prescrição já os calcula assim.", "CP, art. 115.",
                                   tipo="menor-de-21-anos-no-fato-prescricao-pela-metade", ref=nome))

    if reinc_sem_base:
        itens.append(_item("info", "Marcado reincidente sem condenação anterior transitada no RSPE",
                           "Nenhum processo deste RSPE transitou em julgado antes dos fatos (%s). A reincidência pode vir de condenação não listada aqui: "
                           "conferir a certidão de antecedentes e o período depurador de 5 anos (art. 64, I). Afeta frações de progressão, livramento e indulto." % (
                               rs.fmt(min(reinc_sem_base)) if len(set(reinc_sem_base)) == 1 else "de %s a %s" % (rs.fmt(min(reinc_sem_base)), rs.fmt(max(reinc_sem_base)))),
                           "CP, arts. 63 e 64, I.", tipo="marcado-reincidente-sem-condenacao-anterior-tran"))
    # ---------------- 3. data-base e faltas ----------------
    regs = [i for i in incidentes if "REGIME" in (i.get("tipo") or "").upper() and i.get("situacao") == "CONCEDIDO"
            and rs.re.search(r"PROGRESS|REGRESS", i.get("complemento") or "", rs.re.I)]
    ult = None
    for i in regs:
        d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        # regressão cautelar não fixa data-base (só a definitiva, após a falta homologada)
        if d and (ult is None or d > ult[0]) and "CAUTELAR" not in (i.get("complemento") or "").upper():
            ult = (d, i)
    # erros de lançamento que a capacitação CNJ/SEEU (10 e 11/06/2025) aponta como os mais comuns e que atrasam benefícios
    _prog_dec = [i for i in regs if "PROGRESS" in (i.get("complemento") or "").upper() and i.get("data_decisao")
                 and i.get("data_decisao") == i.get("data_referencia")]
    # só pesa enquanto for a última data-base: depois de outra progressão, regressão, falta ou nova prisão, a data-base já mudou
    _marcos_db = [rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "") for j in regs]
    _marcos_db += [rs.to_date(e.get("data") or "") for e in eventos if "INTERRUP" not in (e.get("tipo") or "").upper()]
    _marcos_db += [rs._data_fato_falta(j) for j in incidentes if rs.RE_FALTA_PROPRIA.search(rs._rotulo_incidente(j)) and not rs._negado(j)]
    for i in _prog_dec:
        _di = rs.to_date(i.get("data_decisao"))
        _depois = sorted(x for x in _marcos_db if x and _di and x > _di)
        if _depois:
            itens.append(_item("info", "Progressão lançada na data da decisão (%s) - já superada" % i.get("data_decisao"),
                               "%s: a data de referência é a da decisão, mas a data-base mudou depois (%s), e o erro não pesa mais no cálculo "
                               "atual; só atrasou o benefício seguinte daquela época." % (rs._rotulo_incidente(i), rs.fmt(_depois[0])),
                               "STJ, Tema 1165.", tipo="progressao-na-decisao-superada", ref=i.get("data_decisao")))
            continue
        itens.append(_item("alerta", "Progressão lançada na data da decisão (%s)" % i.get("data_decisao"),
                           "%s: a data de referência lançada é a própria data da decisão (%s). A decisão de progressão é declaratória: a "
                           "data que vale - e que vira a data-base da progressão seguinte - é a do preenchimento dos requisitos, em regra a do "
                           "requisito objetivo que o próprio SEEU apontava na pendência; só o exame criminológico posterior desloca essa data "
                           "para o dia do exame favorável. Com a data da decisão, todo o tempo de espera pela decisão se perde para a próxima "
                           "progressão. Conferir nos autos a data em que o lapso foi atingido." % (rs._rotulo_incidente(i), i.get("data_decisao")),
                           "STJ, Tema 1165 (REsp 1.972.187); LEP, art. 112.", tipo="progressao-com-data-base-igual-a-data-da-decisao",
                           ref=i.get("data_decisao")))
    # regime inicial: um só por execução, na data da primeira prisão. Na data de uma prisão posterior, o SEEU desconta a detração
    # antes da fração (forma mais gravosa); um segundo "regime inicial" (em vez de somatório) muda a data-base sem fundamento
    _ri = sorted(((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), i) for i in incidentes
                  if i.get("situacao") == "CONCEDIDO" and "REGIME INICIAL" in rs._sem_acento((i.get("complemento") or "").upper())
                  and rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")), key=lambda x: x[0])
    _ri = [(d, i) for d, i in _ri]
    if len(_ri) > 1:
        itens.append(_item("alerta", "Mais de um regime inicial lançado (%s)" % ", ".join(rs.fmt(d) for d, _ in _ri),
                           "O RSPE registra %d incidentes de regime inicial: %s. Cada execução tem um só regime inicial; a chegada de nova guia "
                           "gera somatório de penas e, se for o caso, fixação/alteração de regime pelo motivo condenação - não outro regime "
                           "inicial. O regime inicial lançado de novo desloca a data-base para a data dele, sem falta grave nem progressão que o "
                           "justifique, e atrasa a progressão." % (len(_ri), "; ".join("%s (%s)" % (rs.fmt(d), i.get("complemento") or "") for d, i in _ri)),
                           "LEP, arts. 111 e 112; STJ, Tema 1006 (a unificação não altera a data-base).", tipo="mais-de-um-regime-inicial",
                           ref=rs.fmt(_ri[-1][0])))
    if _ri:
        _d_ri = _ri[0][0]
        _procs_exec = [c.get("processo_criminal") or "" for c in crimes]
        _prim = [a for a, _b, _m, procs in rs.periodos_custodia_detalhe(eventos)
                 if a and (not rs.lista_processos(procs) or any(rp._mesmo_processo(q, x) for q in rs.lista_processos(procs) for x in _procs_exec if x))]
        if _prim and min(_prim) < _d_ri - timedelta(days=1):
            itens.append(_item("alerta", "Regime inicial lançado em %s, depois da primeira prisão (%s)" % (rs.fmt(_d_ri), rs.fmt(min(_prim))),
                               "A primeira prisão por processo desta execução é de %s e o regime inicial foi lançado em %s. Lançado depois da "
                               "primeira prisão (na data de prisão posterior ou de decisão), o regime inicial faz o SEEU descontar a detração antes da fração (forma mais gravosa); "
                               "lançado na data da primeira prisão, a detração conta como pena cumprida para todos os fins e as datas de "
                               "progressão e livramento se antecipam. Se o juízo determinou a data da última prisão, o SEEU tem a opção "
                               "\"diminuir a detração após os cálculos\", que mantém essa data sem agravar o cálculo (aparece como \"Sim\" em vermelho no "
                               "cálculo); o incidente de alteração de data-base não serve para isso, porque aplica efeito de falta grave "
                               "(interrompe a contagem)." % (rs.fmt(min(_prim)), rs.fmt(_d_ri)),
                               "CP, art. 42 (a detração é pena cumprida); LEP, art. 112.", tipo="regime-inicial-depois-da-primeira-prisao",
                               ref=rs.fmt(_d_ri)))
    db_seeu = rs.to_date(r.get("data_base_seeu") or "")
    # regressão por falta grave: a data-base é a da falta (Súmula 534/STJ), anterior à data em que a regressão foi lançada
    _falta_db = db_seeu and ult and "REGRESS" in (ult[1].get("complemento") or "").upper() and any(
        d and abs((d - db_seeu).days) <= 1 for d in [rs._data_fato_falta(i) for i in incidentes if rs.RE_FALTA_PROPRIA.search(rs._rotulo_incidente(i))
                                                       and not rs._negado(i) and not rs._pendente(i)])
    if db_seeu and ult and db_seeu < ult[0] and not _falta_db:
        itens.append(_item("alerta", "Data-base de progressão anterior à última alteração de regime",
                           "Data-base impressa: %s; última alteração de regime: %s (%s)." % (rs.fmt(db_seeu), rs.fmt(ult[0]), ult[1].get("complemento")),
                           "LEP, art. 112, § 6º (falta grave reinicia pela remanescente); STJ Tema 1006 (a unificação de penas não altera a data-base); STJ Tema 1165 (data-base é a do preenchimento dos requisitos, não a da decisão).", tipo="data-base-de-progressao-anterior-a-ultima-altera"))
    # alteração de data-base determinada no RSPE depois da última progressão: só se justifica por falta grave homologada
    # (LEP, arts. 112, § 6º, e 118; Súmula 534/STJ), regressão ou nova prisão após interrupção; soma/unificação não altera
    # (STJ, Tema 1006). Sem nenhum desses fundamentos no RSPE, a alteração atrasa a progressão e pede conferência
    _lp = max((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.min for i in regs
               if "PROGRESS" in (i.get("complemento") or "").upper()), default=date.min)
    _firmes = [rs._data_fato_falta(i) for i in incidentes if rs.RE_FALTA_PROPRIA.search(rs._rotulo_incidente(i)) and not rs._negado(i)
               and not rs._pendente(i) and not i.get("_ficha")]
    _firmes = [d for d in _firmes if d]
    _firmes += [rs.to_date(e.get("data") or "") for e in eventos if e.get("_falta") == "sim"]
    _regr = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in regs if "REGRESS" in (i.get("complemento") or "").upper()]
    _pris = [rs.to_date(e.get("data") or "") for e in eventos if re.search(r"PRIS|REIN[ÍI]CIO|RECAPTURA", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())]
    _db_sem = []
    for i in incidentes:
        t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
        if not re.search(r"DATA[- ]BASE", i.get("tipo") or "", re.I) or i.get("situacao") != "CONCEDIDO":
            continue
        d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
        if not d:
            continue
        if (any(x and d - timedelta(days=365) <= x <= d for x in _firmes) or any(x and abs((x - d).days) <= 30 for x in _regr)
                or any(x and abs((x - d).days) <= 5 for x in _pris)):
            # há fundamento, mas o lançamento é o incidente de exceção: em data-base fixa, nada do que vier depois a move
            _dep = sorted(x for x in ([rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "") for j in regs] + _firmes + _pris) if x and x > d)
            _db = rs.to_date(r.get("data_base_seeu") or "")
            fixa = bool(_dep and _db and abs((_db - d).days) <= 1)
            # não fixa e com fundamento na data: o marco está certo, só o tipo de lançamento é atípico - informativo
            itens.append(_item("alerta" if fixa else "info",
                               ("Data-base presa na alteração de %s (data-base fixa?)" if fixa else "Alteração de data-base lançada em %s no lugar do incidente próprio") % rs.fmt(d),
                               "%s (decisão de %s). A falta grave, a regressão e a prisão têm incidentes próprios (homologação de falta grave, "
                               "fixação/alteração de regime, eventos), que o SEEU lê e atualiza sozinho; a alteração de data-base é exceção, para "
                               "entendimento do juízo que o sistema não aplica. Lançada como fixa, trava o cálculo automático: progressão, "
                               "regressão ou falta posteriores não movem mais a data-base. %s" % (
                                   rs._rotulo_incidente(i), i.get("data_decisao") or "?",
                                   ("Depois dela houve %s, mas a data-base impressa (%s) continua sendo a da alteração." % (
                                       ", ".join(rs.fmt(x) for x in _dep[:3]), rs.fmt(_db))) if fixa else
                                   "Conferir se a alteração é dinâmica e se a data corresponde ao marco correto."),
                               "LEP, arts. 112, § 6º, e 118; STJ, Temas 709 e 1165.", tipo="alteracao-de-data-base-no-lugar-do-incidente", ref=rs.fmt(d)))
            continue
        unif = bool(re.search(r"SOMA|UNIFICA|NOVA CONDENA|GUIA", t))
        antiga = d < _lp  # já houve progressão depois: a alteração atrasou a progressão daquela época
        # superada: depois dela veio um marco legítimo (falta homologada, regressão, prisão) antes de qualquer progressão, e a
        # data-base atual já é posterior - a alteração sem fundamento não produz mais efeito
        _leg = sorted(x for x in (_firmes + _regr + _pris) if x and x > d)
        superada = bool(_leg and db_seeu and db_seeu >= _leg[0] and not (d < _lp <= _leg[0]))
        if superada:
            itens.append(_item("info", "Alteração de data-base em %s sem falta grave homologada - superada" % rs.fmt(d),
                               "%s (decisão de %s). Sem fundamento no RSPE, mas em %s houve marco que reinicia a data-base, antes de qualquer "
                               "progressão, e a data-base atual (%s) já é posterior: a alteração não produz mais efeito." % (
                                   rs._rotulo_incidente(i), i.get("data_decisao") or "?", rs.fmt(_leg[0]), rs.fmt(db_seeu)),
                               "LEP, arts. 112, § 6º, e 118; STJ, Tema 1006.", tipo="alteracao-de-data-base-sem-falta-homologada", ref=rs.fmt(d)))
            _db_sem.append(d)
            continue
        itens.append(_item("alerta" if unif else "verificar",
                           "Alteração de data-base em %s sem falta grave homologada no RSPE" % rs.fmt(d),
                           "%s (decisão de %s). Não há falta grave homologada nos 12 meses anteriores, regressão nem nova prisão nessa data. "
                           "A data-base só se altera por falta grave reconhecida em juízo, por regressão ou pela recaptura/nova prisão depois de "
                           "interrupção; %s. Conferir o fundamento nos autos: sem ele, a data-base volta à anterior e a progressão se antecipa.%s" % (
                               rs._rotulo_incidente(i), i.get("data_decisao") or "?",
                               "a soma ou unificação de penas não altera a data-base (STJ, Tema 1006)" if unif else "falta pendente não pode mover a data-base",
                               (" Já houve progressão depois (%s): se a alteração a atrasou, retificada a data-base, a progressão retroage à data "
                                "em que os requisitos estavam preenchidos (STJ, Tema 1165), o que antecipa as datas atuais." % rs.fmt(_lp)) if antiga else ""),
                           "LEP, arts. 112, § 6º, e 118; Súmula 534/STJ; STJ, Temas 1006 e 1165.",
                           tipo="alteracao-de-data-base-sem-falta-homologada", ref=rs.fmt(d)))
        _db_sem.append(d)
    # data-base x eventos que a justificam: última prisão/início do cumprimento, progressão/regressão ou falta grave homologada
    # (a data-base que é a própria alteração sem fundamento já tem o item acima)
    if db_seeu and not any(abs((x - db_seeu).days) <= 1 for x in _db_sem):
        marcos, _preso, _fictas = [], False, []
        for e in sorted(r.get("_eventos", []), key=lambda e: rs.to_date(e.get("data") or "") or date.min):
            t = ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper()
            d = rs.to_date(e.get("data") or "")
            if d and "INTERRUP" in t:
                _preso = False
            elif d and re.search(r"PRIS|IN[ÍI]CIO|REIN[ÍI]CIO|RECAPTURA", t):
                # "prisão definitiva" de quem já estava preso (sem interrupção antes): é o mandado cumprido só para gerar a guia
                # nova - prisão fictícia, que não muda a data-base (senão a soma das penas a alteraria: Tema 1006)
                if _preso and "DEFINITIVA" in t:
                    _fictas.append(d)
                else:
                    marcos.append((d, "prisão/início do cumprimento (%s)" % (e.get("motivo") or e.get("tipo") or "").strip().lower()))
                _preso = True
        for i in incidentes:
            if i.get("situacao") != "CONCEDIDO":
                continue
            t = (i.get("tipo") or "").upper()
            for campo in ("data_referencia", "data_decisao"):
                d = rs.to_date(i.get(campo) or "")
                if not d:
                    continue
                if "DATA-BASE" in t or "DATA BASE" in t:
                    marcos.append((d, "alteração de data-base determinada no RSPE"))
                elif "REGIME" in t and re.search(r"SOMAT|UNIFICA", (i.get("complemento") or "").upper()):
                    continue  # regime fixado pela soma das penas: não altera a data-base (Tema 1006) - tratado como soma, abaixo
                elif "REGIME" in t:
                    marcos.append((d, "alteração de regime (%s)" % (i.get("complemento") or "").strip()))
                elif "FALTA GRAVE" in t:
                    marcos.append((d, "falta grave homologada"))
                elif "LIVRAMENTO" in t and "REVOG" in (t + " " + (i.get("complemento") or "")).upper():
                    marcos.append((d, "revogação do livramento"))
        bate = [m for m in marcos if abs((m[0] - db_seeu).days) <= 1]
        unif = [i for i in incidentes if (re.search(r"SOMAT|UNIFICA", (i.get("tipo") or "").upper())
                                          or ("REGIME" in (i.get("tipo") or "").upper() and re.search(r"SOMAT|UNIFICA", (i.get("complemento") or "").upper())))
                and any(rs.to_date(i.get(c) or "") and abs((rs.to_date(i.get(c)) - db_seeu).days) <= 1 for c in ("data_referencia", "data_decisao"))]
        # fuga: a data-base vai para a recaptura (infração permanente), mas a falta tem de ser apurada e homologada
        _fuga = [rs.to_date(e.get("data") or "") for e in r.get("_eventos", [])
                 if "FUGA" in ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper()]
        _fuga = sorted(d for d in _fuga if d)
        # só a falta desta fuga (fato a partir dela) conta; falta antiga, de outra data, não autoriza mover a data-base para a recaptura
        _homolog = bool(_fuga) and (any(
            re.search(r"FALTA|DISCIPLINAR|PAD\b", (i.get("tipo") or "") + " " + (i.get("complemento") or ""), re.I)
            and (rs._data_fato_falta(i) or date.min) >= _fuga[-1] - timedelta(days=5)
            for i in incidentes if i.get("situacao") == "CONCEDIDO") or any(
            e.get("_falta") == "sim" and rs.to_date(e.get("data") or "") == _fuga[-1] for e in r.get("_eventos", [])))
        _recapt = bool(bate) and "recaptura" in (bate[0][1] if bate else "").lower()
        if _fuga and _recapt and _fuga[-1] < db_seeu and not _homolog:
            itens.append(_item("alerta", "Data-base movida para a recaptura (%s) sem falta homologada no RSPE" % rs.fmt(db_seeu),
                               "Houve fuga em %s e recaptura em %s. Na fuga, a nova data-base é a da recaptura, porque a falta é permanente, "
                               "mas a interrupção depende de apuração em procedimento disciplinar com defesa técnica e de homologação judicial, "
                               "e o RSPE não registra esse incidente. Sem homologação, a data-base volta a ser %s e a progressão se antecipa; "
                               "a perda de até 1/3 dos %s remidos também depende dessa apuração. Se o juízo reconsiderou ou afastou a falta, "
                               "o lançamento correto é trocar a interrupção \"fuga\" por \"descumprimento das condições\": o SEEU desconta o "
                               "período fora, mas deixa de usar a recaptura como data-base." % (
                                   rs.fmt(_fuga[-1]), rs.fmt(db_seeu), ("%s (%s)" % (rs.fmt(ant2[0]), ant2[1]) if (ant2 := next((m for m in sorted(marcos, key=lambda x: x[0], reverse=True) if m[0] < _fuga[-1]), None)) else "a anterior"),
                                   rs.pl(rs.saldo_remidos_num(r.get("saldo_remidos"))[0], "dia", "dias")),
                               "LEP, arts. 50, II, 57, 59, 118 e 127; Súmulas 533, 534 e 535/STJ; STJ, Tema 709.", tipo="data-base-movida-para-a-recaptura-sem-falta-homo"))
        elif bate and "REGRESS" in bate[0][1].upper() and any(
                abs(((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.min) - db_seeu).days) <= 5
                for i in incidentes if re.search(r"SOMAT|UNIFICA", (i.get("tipo") or "").upper()) and i.get("situacao", "CONCEDIDO") == "CONCEDIDO") \
                and not any(m[1] == "falta grave homologada" and abs((m[0] - db_seeu).days) <= 365 for m in marcos):
            itens.append(_item("alerta", "Data-base (%s) movida pela regressão decorrente da soma de penas" % rs.fmt(db_seeu),
                               "A regressão de %s ocorreu junto com a soma ou unificação das penas, sem falta grave homologada: decorre da nova "
                               "condenação (LEP, arts. 111, p. ú., e 118, II), e a unificação não altera a data-base, que continua a da última "
                               "prisão, progressão ou falta grave." % rs.fmt(db_seeu),
                               "STJ, Tema 1006 (REsp 1.753.509); LEP, arts. 111 e 118.", tipo="data-base-coincide-com-a-soma-unificacao-das-pen"))
        elif bate:
            itens.append(_item("ok", "Data-base (%s) confere com o RSPE: %s" % (rs.fmt(db_seeu), bate[0][1]), "", "LEP, art. 112.", tipo="data-base-confere-com-o-rspe"))
        elif unif:
            itens.append(_item("alerta", "Data-base (%s) coincide com a soma/unificação das penas" % rs.fmt(db_seeu),
                               "Não há prisão, alteração de regime ou falta grave homologada nessa data; a data coincide com o incidente de %s. "
                               "A unificação não altera a data-base: ela continua sendo a da última prisão, progressão ou falta grave.%s" % (
                                   ("%s (%s)" % (unif[0].get("tipo") or "", unif[0].get("complemento") or "")).lower(),
                                   (" A \"prisão definitiva\" lançada em %s, com a pessoa já presa, é só o cumprimento do mandado para expedir "
                                    "a guia nova (prisão fictícia) e também não altera a data-base." % rs.fmt(next(x for x in _fictas if abs((x - db_seeu).days) <= 1)))
                                   if any(abs((x - db_seeu).days) <= 1 for x in _fictas) else ""),
                               "STJ, Tema 1006 (REsp 1.753.509); LEP, art. 112.", tipo="data-base-coincide-com-a-soma-unificacao-das-pen"))
        else:
            ant = sorted([m for m in marcos if m[0] <= db_seeu], key=lambda m: m[0])
            itens.append(_item("verificar", "Inconsistência da data-base (%s): sem prisão, alteração de regime ou falta grave homologada nessa data" % rs.fmt(db_seeu),
                               "A data-base é a da última prisão, da última progressão/regressão ou da falta grave homologada, e nenhum desses eventos consta no RSPE em %s. "
                               "Último evento anterior no RSPE: %s. Data-base posterior ao último evento atrasa a progressão: verificar no processo a origem "
                               "(ex.: falta ainda não homologada, que não pode mover a data-base)." % (
                                   rs.fmt(db_seeu), ("%s em %s" % (ant[-1][1], rs.fmt(ant[-1][0]))) if ant else "nenhum"),
                               "LEP, arts. 112 e 118; STJ, Temas 1006 e 1165.", tipo="inconsistencia-da-data-base-sem-prisao-alteracao"))
    # falta grave não interrompe o livramento condicional, o indulto nem a comutação
    _dbl = rs.to_date(r.get("livramento_data_base_seeu") or "")
    _faltas_d = sorted(d for d in [rs.to_date(e.get("data") or "") for e in r.get("_eventos", [])
                                   if re.search(r"FUGA|DESCUMPRIMENTO", (e.get("tipo") or "") + " " + (e.get("motivo") or ""), re.I)] if d)
    if _dbl and _faltas_d and any(abs((d - _dbl).days) <= 1 for d in _faltas_d + [rs.to_date(r.get("data_base_seeu") or "") or date.min]):
        itens.append(_item("alerta", "Data-base do livramento (%s) coincide com a de falta grave ou da progressão" % rs.fmt(_dbl),
                           "A falta grave interrompe o prazo da progressão, não o do livramento condicional, nem os do indulto e da comutação. "
                           "A data-base do livramento deve continuar a do início do cumprimento, descontado apenas o período de evasão.",
                           "Súmulas 441 e 535/STJ; STJ, Tema 709; LEP, art. 112, § 6º.", tipo="data-base-do-livramento-alterada-por-falta-grave"))
    # regressão depois do deferimento do livramento: conferir o desfecho da falta e do livramento
    _dls = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "") for i in incidentes
            if rs.e_concessao_livramento(i)]
    _dls = [d for d in _dls if d]
    _lc_reg = bool(ult and _dls and "REGRESS" in (ult[1].get("complemento") or "").upper() and ult[0] > max(_dls))
    if _lc_reg:
        _dlc = max(_dls)
        _int = [(rs.to_date(e.get("data") or ""), (e.get("motivo") or "").strip().lower()) for e in eventos
                if "INTERRUP" in (e.get("tipo") or "").upper() and (rs.to_date(e.get("data") or "") or date.min) > _dlc]
        _rev = any(rs.e_revogacao_livramento(j) for j in incidentes
                   if (rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.min) > _dlc)
        _cautelar = "CAUTELAR" in (ult[1].get("complemento") or "").upper()
        itens.append(_item("verificar", "%s em %s após o livramento condicional (deferido em %s): verificar o desfecho" % (
                               "Regressão cautelar" if _cautelar else "Regressão", rs.fmt(ult[0]), rs.fmt(_dlc)),
                           "O RSPE registra %s%s%s. Conferir nos autos: (a) se o livramento foi suspenso antes do fim do período de prova - sem suspensão "
                           "ou revogação nesse prazo, a pena está extinta (CP, art. 90; Súmula 617/STJ); (b) se houve revogação e por qual causa - revogado "
                           "por descumprimento de condição, o tempo em livramento não se desconta (CP, arts. 87 e 88); (c) se a falta foi apurada e homologada "
                           "(PAD/audiência): regressão cautelar é provisória e não fixa, por si, a data-base%s." % (
                               "; ".join("interrupção em %s (%s)" % (rs.fmt(d), m or "sem motivo") for d, m in _int) + " e " if _int else "",
                               "%s em %s" % ("regressão cautelar" if _cautelar else "regressão", rs.fmt(ult[0])),
                               "" if _rev else ", sem registro de suspensão ou revogação do livramento",
                               (" (o RSPE adota %s)" % r.get("data_base")) if r.get("data_base") else ""),
                           "CP, arts. 86 a 90; LEP, arts. 118, 145 e 146; Súmula 617/STJ; STJ, Tema 1006.", tipo="em-apos-o-livramento-condicional-deferido-em-ver", ref="Regressão cautelar" if _cautelar else "Regressão"))
    if ult and "REGRESS" in (ult[1].get("complemento") or "").upper() and not _lc_reg:
        itens.append(_item("info", "Regressão registrada em %s" % rs.fmt(ult[0]),
                           "Se decorreu de falta grave, a data-base da progressão é a data da falta e o requisito recomeça sobre a pena remanescente; a falta também impede LC (12 meses) e indulto (art. 6º dos decretos).",
                           "LEP, arts. 112, § 6º, 118 e 127; CP, art. 83, III, b.", tipo="regressao-registrada-em"))
    idade = None
    if nasc:
        idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        if idade >= 70:
            _ab = "ABERTO" in (r.get("regime_atual") or "").upper().replace("SEMIABERTO", "") and not re.search(r"INTERROMPIDA|SUSPENSA", r.get("situacao_cumprimento") or "")
            itens.append(_item("alerta" if _ab else "info",
                               ("Idade %s no regime aberto: cabe prisão domiciliar (LEP, art. 117, I)" if _ab else
                                "Idade %s: prisão domiciliar quando no regime aberto (LEP, art. 117, I)") % rs.pl(idade, "ano", "anos"),
                               "Art. 117, I, da LEP: recolhimento em residência particular do beneficiário do regime aberto maior de 70 anos%s. "
                               "Art. 115 do CP: prazos de prescrição pela metade se era maior de 70 anos na data da sentença - a aba Prescrição já o aplica." % (
                                   " - o regime atual é o aberto" if _ab else ""),
                               "CP, art. 115; LEP, art. 117, I.", tipo="idade-prisao-domiciliar-no-regime-aberto-lep-art"))
        # § 2º, I, dos decretos: maior de 60 anos em 25/12 do ano do decreto (medido na data de cada decreto)
        _i60 = []
        for _ano, _ref in sorted(rs.DECRETOS.items()):
            _id = _ref.year - nasc.year - ((_ref.month, _ref.day) < (nasc.month, nasc.day))
            if _id >= 60:
                _i60.append("%s em %s" % (rs.pl(_id, "ano", "anos"), rs.fmt(_ref)))
        if _i60:
            itens.append(_item("info", "Idade para o indulto: lapsos pela metade (%s)" % "; ".join(_i60),
                               "Decretos 12.338/2024 e 12.790/2025, art. 9º, § 2º, I (pessoas maiores de sessenta anos): os lapsos dos incisos I a XI caem pela "
                               "metade - a aba Indulto já calcula assim.", "", tipo="idade-para-o-indulto-lapsos-pela-metade"))

    # CP, art. 88: livramento revogado por crime cometido durante o período de prova - o tempo em liberdade não se desconta
    try:
        _lcs = rs.periodos_livramento(eventos, incidentes)
    except Exception:
        _lcs = []
    _revs = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in incidentes if rs.e_revogacao_livramento(i)]
    for _ini, _fim in _lcs:
        if not _fim or not any(x and abs((x - _fim).days) <= 5 for x in _revs):
            continue
        _novos = [o for o in crimes if (rs.to_date(o.get("data_infracao") or "") or date.min) >= _ini
                  and (rs.to_date(o.get("data_infracao") or "") or date.max) <= _fim]
        if _novos:
            itens.append(_item("alerta", "Livramento revogado com crime cometido durante o período de prova (art. 88)",
                               "Livramento de %s a %s, revogado; %s cometido nesse período. Revogado o livramento por crime praticado durante a sua "
                               "vigência, o tempo em liberdade não se desconta da pena (CP, art. 88; LEP, art. 142). O programa conta o período de "
                               "prova como pena cumprida: conferir o cálculo do SEEU e as datas de progressão, término e indulto." % (
                                   rs.fmt(_ini), rs.fmt(_fim), "; ".join("%s (fato em %s)" % (_nome(o), o.get("data_infracao")) for o in _novos)),
                               "CP, art. 88; LEP, arts. 141 e 142.", tipo="livramento-revogado-art-88", ref=rs.fmt(_ini)))
    # LEP, art. 112, §§ 3º e 4º: progressão com 1/8 para a mulher gestante, mãe ou responsável por criança ou pessoa com
    # deficiência - o RSPE não informa sexo nem filhos; só se aponta quando os demais requisitos objetivos batem
    _fr_seeu_max = max((_fr_seeu(c.get("fracao_progressao")) or 0 for c in ativos), default=0)
    if (ativos and not any(c.get("vga") == "S" for c in ativos)
            and not any(c.get("comando_orcrim") == "S" or rs.num_lei(c.get("lei")) == "12850" for c in ativos)
            and not any(_reincidencia_legal(c, crimes_pessoa)[0] for c in ativos) and r.get("_sexo") != "M"
            and _fr_seeu_max and float(_fr_seeu_max) > 0.125 + 0.001):
        # texto dos requisitos: o da base jurídica (progressao.art112_par3_mulheres), editável
        _txt18 = (rg.carregar() or {}).get("progressao", {}).get("art112_par3_mulheres") or (
            "Se for mulher gestante, mãe ou responsável por criança ou pessoa com deficiência, a progressão exige 1/8 da pena, desde que: "
            "sem violência ou grave ameaça, crime não cometido contra filho ou dependente, primária e com bom comportamento, e sem integrar "
            "organização criminosa (o benefício é revogado por novo crime doloso ou falta grave).")
        itens.append(_item("info", "Progressão especial da mulher (1/8): a verificar",
                           "%s O RSPE aplica %s." % (_txt18, rs.pct(_fr_seeu_max)),
                           "LEP, art. 112, §§ 3º e 4º.", tipo="progressao-especial-da-mulher-1-8-a-verificar"))
    # regime impresso no RSPE x livramento em curso
    _lc, _dl = rs.livramento_em_curso(r, incidentes)
    if _lc:
        _duv = rs.duvidas_livramento(r, eventos, incidentes, _dl)
        if _duv:
            itens.append(_item("alerta", "Livramento condicional%s com situação incerta no RSPE" % ((" deferido em %s" % rs.fmt(_dl)) if _dl else ""),
                "O SEEU imprime o livramento como vigente, mas o RSPE registra: %s. Conferir nos autos se o livramento foi suspenso ou revogado "
                "(CP, arts. 86 a 88; LEP, arts. 140 a 145) ou se o período de prova se esgotou sem revogação, caso em que a pena está extinta (CP, art. 90). "
                "Enquanto isso, progressão, livramento, indulto e extinção ficam como 'a verificar'." % "; ".join(_duv),
                "CP, arts. 86 a 90; LEP, arts. 140 a 145.", tipo="livramento-condicional-com-situacao-incerta-no-r"))
    # ---------------- 4. marcos vencidos e prescrição ----------------
    import rspe_view as _rv
    _est = _rv.estado_execucao(r)
    _est = _est[0] if _est else ""
    for chave, nome_marco in (("progressao_previsao_seeu", "Progressão"), ("livramento_previsao_seeu", "Livramento condicional")):
        d = rs.to_date(r.get(chave) or "")
        # pena cumprida / em livramento dispensam os dois marcos; regime aberto dispensa a progressão
        if _est in ("cumprida", "lc") or (_est == "aberto" and chave.startswith("prog")):
            continue
        if d and d <= hoje:
            palavra = "PROGRESS" if chave.startswith("prog") else "LIVRAMENTO"
            pedidos_pos = [i for i in incidentes if palavra in ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
                           and (rs.to_date(i.get("data_decisao") or "") or date.min) >= d]
            if not pedidos_pos:
                itens.append(_item("alerta", "%s vencida em %s sem decisão posterior no RSPE" % (nome_marco, rs.fmt(d)),
                                   "Lapso atingido há %s e nenhum incidente decidido depois dessa data." % rs.pl((hoje - d).days, "dia", "dias"), "LEP, art. 112; CP, art. 83.", tipo="vencida-em-sem-decisao-posterior-no-rspe", ref=nome_marco))
    presc = rp.analisar(r, hoje)
    for l in presc["presc_linhas"]:
        rot = l.get("rotulo") or l["crime"]
        if l.get("ppe_detracao_cobre") and l.get("ppe_detracao_exclusiva"):
            itens.append(_item("alerta", "%s: detração iguala ou supera a pena do processo - extinção pelo cumprimento" % rot,
                               "Custódia anterior ao trânsito de %s e pena do processo de %s. Nenhuma outra condenação do RSPE tem fato anterior a essa prisão, "
                               "então a detração só pode ser imputada a este processo: a pena está cumprida." % (
                                   rs.dias_para_pena(l.get("ppe_detracao_dias") or 0), l.get("ppe_pena_processo") or l.get("pena")),
                               "CP, art. 42; LEP, arts. 66, II, e 111.", tipo="pena-cumprida-por-detracao", ref=rot))
        elif l.get("ppe_detracao_cobre"):
            itens.append(_item("verificar", "%s: detração iguala ou supera a pena do processo - conferir extinção pelo cumprimento" % rot,
                               "Custódia anterior ao trânsito de %s e pena do processo de %s. A mesma prisão pode servir a várias condenações (a detração vale uma vez só na "
                               "pena unificada); se computada nesta condenação, cabe extinção pelo cumprimento." % (rs.dias_para_pena(l.get("ppe_detracao_dias") or 0), l.get("ppe_pena_processo") or l.get("pena")),
                               "CP, art. 42; LEP, arts. 66, II, e 111.", tipo="pena-cumprida-por-detracao", ref=rot))
        if l.get("ppe_cor") == "vermelho":
            itens.append(_item("alerta", "%s: prescrição da pretensão executória aparente (%s)" % (rot, l.get("ppe_previsao")), l.get("ppe_resumo") or l.get("ppe_status", ""), "CP, arts. 110, 112, 113, 117, V, e 119; STF Tema 788.", tipo="prescricao-da-pretensao-executoria-aparente", ref=rot))
        elif (l.get("ppe_status") or "").startswith("A VERIFICAR"):
            itens.append(_item("verificar", ("%s: prescrição executória a verificar - falta %s" % (rot, l["ppe_faltam"][0])) if l.get("ppe_faltam") else
                               "%s: prescrição executória a verificar - saldo na evasão depende da imputação do cumprimento" % rot,
                               (l.get("ppe_resumo") or "") + (" Falta: " + "; ".join(l.get("ppe_faltam") or []) + "." if l.get("ppe_faltam") else ""),
                               "CP, arts. 76, 113 e 119; LEP, art. 111.", tipo="prescricao-executoria-a-verificar-saldo-na-evasao", ref=rot))
        if l.get("retro_cor") == "vermelho":
            itens.append(_item("alerta", "%s: prescrição da pretensão punitiva aparente" % rot, l.get("retro_status", ""), "CP, arts. 109, 110, § 1º, e 117.", tipo="prescricao-da-pretensao-punitiva-aparente", ref=rot))
    # datas que o RSPE não traz: o programa não presume - apontar para verificar na ação penal
    falt = {}
    for l in presc["presc_linhas"]:
        m = re.search(r"não consta no RSPE: (.+?) - verificar", " ".join(l.get("avisos") or []))
        if m and not str(l.get("retro_status") or "").startswith("Extinta"):
            falt.setdefault(l.get("proc_crim") or "?", set()).update(x.strip() for x in m.group(1).split(","))
    if falt:
        itens.append(_item("verificar", "Prescrição não aferível por completo: datas ausentes no RSPE - verificar na ação penal",
                           "; ".join("processo %s: %s" % (p, ", ".join(sorted(v))) for p, v in sorted(falt.items())) +
                           ". O programa não presume datas: sem fato, recebimento da denúncia, sentença e trânsito em julgado, a prescrição daquele trecho não é calculada.",
                           "CP, arts. 109 a 117.", tipo="prescricao-nao-aferivel-por-completo-datas-ausen"))

    # ---------------- 5. indulto / comutação sem registro ----------------
    if True:  # 2022 tem exclusões próprias (art. 7º); 2024/2025 vêm "vedado" quando há impeditivo
        for ano in ("2022", "2024", "2025"):
            st = r.get("indulto_%s_status" % ano)
            if st == "possivel" and not rs.decisoes_decreto(incidentes, ano, "INDULTO"):
                itens.append(_item("alerta", "Indulto %s possível sem incidente no RSPE" % ano, r.get("indulto_%s" % ano, ""), "Decreto %s." % {"2022": "11.302/2022, arts. 4º e 5º", "2024": "12.338/2024, art. 9º", "2025": "12.790/2025, art. 9º"}[ano], tipo="indulto-possivel-sem-incidente-no-rspe", ref=ano))
            elif st == "verificar":
                itens.append(_item("info", "Indulto %s: hipóteses a verificar" % ano, r.get("indulto_%s" % ano, ""), "Depende de dado que o RSPE não traz (programa de egressos, estudo, saídas, valor do bem, saúde).", tipo="indulto-hipoteses-a-verificar", ref=ano))
        for ano, dec in (("2024", "12.338/2024"), ("2025", "12.790/2025")):
            if (r.get("comutacao_%s" % ano) or "").startswith("POSSÍVEL") and not rs.decisoes_decreto(incidentes, ano, "COMUTA"):
                itens.append(_item("alerta", "Comutação %s possível sem incidente no RSPE" % ano, r.get("comutacao_%s" % ano, ""), "Decreto %s, art. 13." % dec, tipo="comutacao-possivel-sem-incidente-no-rspe", ref=ano))
    # hediondez superveniente: impeditivo pelo STJ (data do decreto), mas há tese defensiva no STF
    sup = [c for c in ativos if any(rs.e_hediondo(c, _ref) for _ref in rs.DECRETOS.values()) and not rs.e_hediondo(c)]
    if sup:
        itens.append(_item("verificar", "Hediondez posterior ao fato (%s): indulto/comutação possíveis pela tese da irretroatividade; o STJ veda" % rs.crimes_curto(sup),
                           "Não era hediondo na data do fato; é na data do decreto. "
                           "STJ: afere na data do decreto e veda. "
                           "STF, a favor: 2ª Turma (RHC 267.297 AgR e HC 273.296 AgR) e monocráticas (RE 1.572.734, HC 258.516, RHC 269.076, HC 271.716, RE 1.607.670). "
                           "Em sentido contrário no STF: 1ª Turma, RHC 273.867 AgR (24/08/2026; antes, monocrática de 13/07/2026), aferição na data do decreto. "
                           "TJMS: a 2ª Câmara Criminal dá provimento parcial para reanálise (1602006-93.2026, 1602467-65.2026, 1603697-45.2026); a 1ª e a 3ª seguem o STJ. "
                           "Frações de progressão: pela data do fato.",
                           "Decretos de indulto, art. 1º, I; CF, art. 5º, XL; CP, art. 2º.", tipo="hediondez-posterior-ao-fato-indulto-comutacao-po"))
    # violência doméstica: art. 129 §§ 9º-11 sem sinal de que a vítima é mulher
    for c in ativos:
        vd = rs.violencia_domestica(c)
        if vd and vd[0] == "provavel":
            itens.append(_item("verificar", "%s: violência doméstica - confirmar se a vítima é mulher" % _nome(c),
                               "Se a vítima for mulher, o crime é impeditivo de indulto e comutação (art. 1º, XVII, dos Decretos 12.338/2024 e 12.790/2025; "
                               "art. 7º, II, do Decreto 11.302/2022). Enquanto não confirmado, o indulto fica \"a verificar\".",
                               "Decretos de indulto, art. 1º; Lei 11.340/06.", tipo="violencia-domestica-confirmar-se-a-vitima-e-mulh", ref=_nome(c)))
    # presunção de hipossuficiência (Defensoria): multa e reparação do dano nunca bloqueiam benefício no programa
    crimes_ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    if any(re.search(r"\b[Ee]\s+Multa", c.get("tipo_penal") or "") for c in crimes_ativos):
        itens.append(_item("info", "Pena de multa cominada: hipossuficiência na extinção da punibilidade",
                           "Multa pendente: o inadimplemento não obsta a extinção ante a alegada hipossuficiência, salvo decisão motivada que indique concretamente a possibilidade de pagamento (STJ, Tema 931, tese revista em 28/02/2024); há julgados exigindo prova da impossibilidade com base na ADI 7.032 (STJ, REsp 2.055.935) - por cautela, instruir com elementos da hipossuficiência. Elementos concretos úteis (declaração de hipossuficiência, ausência de bens, remuneração do trabalho prisional): a mera assistência pela Defensoria "
                           "foi tida por insuficiente pelo STJ (REsp 2.055.935). No indulto, a incapacidade econômica é presumida para o assistido da Defensoria (art. 12, § 2º, I, dos decretos).",
                           "STF ADI 7.032; STJ Tema 931 (rev. 28/02/2024); Decretos 12.338/2024 e 12.790/2025, art. 12, § 2º, I.", tipo="pena-de-multa-cominada-extincao-cabivel-se-compr"))
    if any(rs.crime_patrimonial(c) and c.get("vga") != "S" for c in crimes_ativos):
        itens.append(_item("info", "Crime patrimonial sem VGA: reparação do dano",
                           "Indulto, art. 9º, XV: reparação dispensada (art. 12, § 2º, I: presunção para o assistido da Defensoria). "
                           "Livramento (CP, art. 83, IV): a efetiva impossibilidade de reparar deve ser demonstrada - o STJ exige prova (AgRg no HC 799.167). Instruir o pedido.",
                           "CP, art. 83, IV ('salvo efetiva impossibilidade'); Decretos 12.338/2024 e 12.790/2025, art. 9º, XV c/c art. 12, § 2º, I; STJ, AgRg no HC 799.167.", tipo="crime-patrimonial-sem-vga-reparacao-do-dano"))
    # os indícios decidíveis já têm item próprio (Falta a apurar / Fuga): este só entra para a falta firme ou para o que não é decidível
    if r.get("falta_12m") == "SIM":
        itens.append(_item("info", "Falta grave nos últimos 12 meses", r.get("falta_12m_detalhe", ""), "Reflexo em LC (CP, art. 83, III, b), indulto e comutação (art. 6º dos decretos) e progressão (LEP, art. 112, §§ 6º e 7º).", tipo="indicio-de-falta-nos-ultimos-12-meses"))
    elif r.get("falta_12m") == "A APURAR" and not any(not fi["decisao"] for fi in rs.faltas_editaveis(incidentes, eventos, hoje)):
        itens.append(_item("verificar", "Indício de falta nos últimos 12 meses", r.get("falta_12m_detalhe", ""), "Reflexo em LC (CP, art. 83, III, b), indulto (art. 6º dos decretos) e progressão (LEP, art. 112, §§ 6º e 7º).", tipo="indicio-de-falta-nos-ultimos-12-meses"))

    # guia suspensa ainda somada na pena total: sem a data da suspensão, o SEEU mantém a pena dela no total (pena maior, benefícios
    # e término adiados). Caso típico: restritiva de direitos superveniente, suspensa durante a privativa (STJ, Tema 1106)
    _susp = [c for c in ativos if (c.get("suspenso") or "").upper().startswith("S")]
    if _susp and pena_total:
        _ps = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in _susp)
        _sem = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos if c not in _susp)
        if _ps and abs(pena_total - (_sem + _ps)) <= 3 and abs(pena_total - _sem) > 3:
            itens.append(_item("alerta", "Guia suspensa somada na pena total (%s)" % ", ".join(sorted(set(_nome(c) for c in _susp))),
                               "O RSPE marca como suspensa a condenação de %s (pena de %s), mas a pena total impressa (%s) é a soma com ela; sem "
                               "ela, o total seria %s. Guia suspensa não está em execução: no SEEU, a suspensão só tira a pena do total quando "
                               "lançada com a data. Enquanto somada, a pena maior adia progressão, livramento e término." % (
                                   ", ".join(sorted(set(_nome(c) for c in _susp))), rs.dias_para_pena(_ps), rs.dias_para_pena(pena_total),
                                   rs.dias_para_pena(_sem)),
                               "STJ, Tema 1106; LEP, art. 111.", tipo="guia-suspensa-somada-na-pena-total"))
    # ---------------- 6. eventos / detração ----------------
    periodos = rs.periodos_custodia(eventos)
    _livre = re.search(r"RESTRITIVA|\bPRD\b|SURSIS|LIVRAMENTO|ABERTO", ((r.get("regime_atual") or "") + " " + (r.get("livramento_obs_seeu") or "")).upper().replace("SEMIABERTO", "")) \
        or rs.livramento_em_curso(r, incidentes)[0]
    if not periodos and (cumprida or 0) > 0 and _livre:
        itens.append(_item("info", "Pena cumprida sem evento de prisão no RSPE (cumprimento em liberdade)",
                           "O relatório indica %s cumpridos sem evento de prisão: o cumprimento é em liberdade (%s), que não gera evento de prisão." % (
                               rs.dias_para_pena(cumprida), (r.get("regime_atual") or "livramento condicional").replace(" - ATIVO", "").lower()),
                           "CP, arts. 44 e 83; LEP, art. 147.", tipo="pena-cumprida-sem-evento-de-prisao-no-rspe"))
    elif not periodos and (cumprida or 0) > 0:
        itens.append(_item("verificar", "Pena cumprida sem evento de prisão no RSPE", "O relatório indica %s cumpridos, mas não lista eventos de início de cumprimento." % rs.dias_para_pena(cumprida), "Conferir a guia e a detração (CP, art. 42).", tipo="pena-cumprida-sem-evento-de-prisao-no-rspe"))
    import rspe_view as _rv2
    if _rv2.nao_iniciou(r):
        itens.append(_item("info", "Não iniciou o cumprimento da pena", "O RSPE não registra início de cumprimento definitivo (só prisão provisória encerrada, ou nenhuma). "
                           "A prescrição executória corre pela pena aplicada, sem desconto da detração, desde o trânsito (STJ, AgRg no HC 967.565; STF, RHC 85.026). "
                           "Mandado de prisão expedido e não cumprido não interrompe (STJ, AgRg no RHC 74.996).", "CP, arts. 110, 112, I, e 117, V.", tipo="nao-iniciou-o-cumprimento-da-pena"))
    elif "SUSPENSA" in (r.get("situacao_cumprimento") or ""):
        itens.append(_item("info", "Execução suspensa: %s" % (r.get("situacao_cumprimento") or "").split("(", 1)[-1].rstrip(")"),
                           "O RSPE registra a interrupção por prisão em outro processo: a pessoa segue presa, e esta execução fica suspensa até o "
                           "reinício. Não é fuga nem liberdade - a prescrição executória não corre enquanto estiver preso por outro motivo "
                           "(CP, art. 116, p. único). Conferir se a prisão no outro processo já foi convertida em cumprimento da pena unificada.",
                           "CP, art. 116, p. único; LEP, art. 111.", tipo="execucao-suspensa-preso-em-outro-processo"))
    elif "INTERROMPIDA" in (r.get("situacao_cumprimento") or ""):
        itens.append(_item("info", "Cumprimento interrompido (último evento é interrupção)", "Verificar se há prisão posterior não lançada ou se a pessoa está foragida ou em liberdade. A prescrição executória corre da interrupção: "
                           "pelo restante da pena só na fuga e na revogação do livramento (art. 113); nas demais interrupções, pela pena aplicada "
                           "(STF, HC 236.292; STJ, RHC 67.403).", "CP, arts. 112, II, e 113.", tipo="cumprimento-interrompido-ultimo-evento-e-interru"))

    itens = _agrupar_por_crime(itens)
    n_alerta = sum(1 for i in itens if i["nivel"] == "alerta")
    n_verif = sum(1 for i in itens if i["nivel"] == "verificar")
    status = "atencao" if n_alerta else ("verificar" if n_verif else "ok")
    ordem = {"alerta": 0, "verificar": 1, "info": 2, "ok": 3}
    itens.sort(key=lambda i: ordem[i["nivel"]])
    return {"aud_status": status, "aud_itens": itens, "aud_alertas": n_alerta, "aud_verificar": n_verif,
            "aud_resumo": " · ".join(x for x in (("%d alerta%s" % (n_alerta, "" if n_alerta == 1 else "s")) if n_alerta else "",
                                                 ("%d ponto%s a verificar" % (n_verif, "" if n_verif == 1 else "s")) if n_verif else "") if x) or "Sem inconsistências",
            "aud_base": "base jurídica %s" % rg.versao()}


# ---- fundamentação para impugnação do cálculo (campo "Fundamentação" da Auditoria) ----
# Até 3 parágrafos: (1) o erro apontado no RSPE; (2) o correto e o fundamento; (3) o pedido. Só para os pontos em que a
# correção favorece o assistido (os demais - p. ex., art. 88 - não geram texto de impugnação).
FUND_TIPOS = {
    "progressao-com-data-base-igual-a-data-da-decisao": (
        "A decisão que defere a progressão de regime é declaratória: o termo inicial da progressão - e a data-base da seguinte - é a data em que "
        "preenchidos os requisitos do art. 112 da LEP, não a data em que o benefício foi deferido (STJ, Tema 1165). O lançamento na data da decisão "
        "faz o assistido perder, para a progressão seguinte, todo o tempo em que aguardou a decisão.",
        "Requer-se a retificação do incidente de progressão, para que conste como data de referência a do preenchimento dos requisitos, com o "
        "recálculo das datas de progressão e livramento condicional."),
    "mais-de-um-regime-inicial": (
        "Cada execução tem um único regime inicial; a superveniência de nova condenação gera a soma das penas e, sendo o caso, a fixação do "
        "regime pela condenação (LEP, art. 111), sem alterar a data-base (STJ, Tema 1006). O lançamento de novo regime inicial desloca a "
        "data-base sem fundamento legal.",
        "Requer-se a exclusão do regime inicial lançado em duplicidade, substituindo-o pelo somatório de penas, com o restabelecimento da "
        "data-base e o recálculo das datas dos benefícios."),
    "regime-inicial-depois-da-primeira-prisao": (
        "A detração é pena cumprida para todos os fins (CP, art. 42) e deve ser computada a partir da primeira prisão. Lançado o regime inicial "
        "na data de prisão posterior, o cálculo desconta a detração antes da fração exigida para os benefícios, da forma mais gravosa ao "
        "assistido.",
        "Requer-se a retificação do regime inicial para a data da primeira prisão, com o cômputo da detração como pena cumprida e o recálculo "
        "das datas de progressão e livramento condicional."),
    "alteracao-de-data-base-no-lugar-do-incidente": (
        "A data-base se altera pelos marcos legais - falta grave homologada, regressão e reinício do cumprimento (LEP, arts. 112, § 6º, e 118; "
        "STJ, Tema 709) - e pela progressão, na data do preenchimento dos requisitos (STJ, Tema 1165). Fixada por incidente avulso, a data-base "
        "deixa de acompanhar os marcos posteriores.",
        "Requer-se seja a data-base vinculada ao último marco legal (falta grave, regressão ou prisão posterior), com o recálculo das datas dos "
        "benefícios."),
    "guia-suspensa-somada-na-pena-total": (
        "A pena restritiva de direitos superveniente à privativa de liberdade em execução não se unifica automaticamente com ela (STJ, Tema "
        "1106) e deve ser executada depois dela ou, se compatível, simultaneamente (CP, art. 76); enquanto isso, não integra a pena total que "
        "serve de base aos benefícios e ao término.",
        "Requer-se a anotação da suspensão com a respectiva data, excluindo-se a pena suspensa do total em execução, com o recálculo das datas "
        "de progressão, livramento condicional e término."),
    "alteracao-de-data-base-sem-falta-homologada": (
        "A data-base para nova progressão só se altera pelo cometimento de falta grave judicialmente reconhecida (na data da infração), pela regressão de regime ou pelo reinício do "
        "cumprimento após interrupção (LEP, arts. 112, § 6º, e 118; Súmula 534/STJ). A soma ou unificação de penas não a altera (STJ, Tema "
        "1006), e, na progressão, a nova data-base é a do preenchimento dos requisitos (STJ, Tema 1165). Sem fundamento idôneo, a alteração é indevida.",
        "Requer-se a exclusão da alteração da data-base, com o restabelecimento da data-base anterior e o recálculo das datas de progressão e "
        "livramento condicional."),
    "data-base-coincide-com-a-soma-unificacao-das-pen": (
        "A superveniência de nova condenação e a unificação ou soma das penas não alteram a data-base para a progressão, que permanece a da última "
        "prisão ou do último benefício (STJ, Tema 1006; LEP, art. 111). A data fixada coincide com a unificação e, portanto, não se sustenta.",
        "Requer-se a retificação da data-base, fixando-a na data da última prisão, da última alteração de regime ou da última falta grave "
        "anterior à unificação, com o recálculo das datas de progressão e livramento."),
    "data-base-do-livramento-alterada-por-falta-grave": (
        "A falta grave não interrompe o prazo para o livramento condicional (Súmula 441/STJ; STJ, Tema 709): interrompe apenas o da progressão "
        "(LEP, art. 112, § 6º) e, quanto ao livramento, repercute somente no requisito do art. 83, III, b, do CP (ausência de falta grave nos "
        "últimos 12 meses), sem deslocar a data-base.",
        "Requer-se a retificação da data-base do livramento condicional, afastando-se a interrupção pela falta grave, com o recálculo da data do "
        "benefício."),
    "data-base-movida-para-a-recaptura-sem-falta-homo": (
        "A fuga só produz efeitos sobre a data-base depois de reconhecida como falta grave em procedimento disciplinar ou em audiência judicial "
        "com defesa técnica (LEP, arts. 50, II, 59 e 118; Súmula 533/STJ; STF, Tema 941; Súmula 534/STJ). Sem falta homologada, a recaptura não reinicia a contagem para a progressão.",
        "Requer-se o restabelecimento da data-base anterior à fuga, descontado o período de evasão, com o recálculo das datas dos benefícios."),
    "inconsistencia-da-data-base-sem-prisao-alteracao": (
        "A data-base deve corresponder a um marco previsto em lei: início do cumprimento, última prisão, última alteração de regime ou data do "
        "cometimento de falta grave judicialmente reconhecida (LEP, arts. 112, § 6º, e 118; Súmula 534/STJ; STJ, Temas 1006 e 1165). A data fixada não coincide com nenhum desses marcos.",
        "Requer-se o esclarecimento do fundamento da data-base e, ausente marco legal, sua retificação para a data do último marco válido, com o "
        "recálculo das datas dos benefícios."),
    "capitulacao-criada-depois-do-fato": (
        "A lei penal mais gravosa não retroage (CF, art. 5º, XL; CP, arts. 1º e 2º). A capitulação cadastrada foi criada depois do fato, e a "
        "execução deve observar a lei vigente à época, inclusive quanto à hediondez, às frações de progressão e livramento e às vedações de "
        "indulto e comutação.",
        "Requer-se a retificação do cadastro da condenação, com a capitulação vigente na data do fato, e o recálculo das frações e datas dos "
        "benefícios."),
    "seeu-tratou-como-hediondo-mas-o-fato-e-anterior": (
        "A hediondez decorre de lei posterior ao fato e não pode retroagir (CF, art. 5º, XL; CP, art. 2º). As frações de progressão e livramento "
        "devem ser as de crime comum vigentes à época do fato.",
        "Requer-se a exclusão da marcação de hediondo e o recálculo das frações e datas de progressão e livramento condicional."),
    "seeu-tratou-como-hediondo-mas-o-tipo-nao-consta": (
        "O rol dos crimes hediondos e equiparados é taxativo (Lei 8.072/1990, art. 1º; CF, art. 5º, XLIII), e o tipo desta condenação não "
        "consta dele; no tráfico privilegiado, a natureza hedionda é afastada por lei (LEP, art. 112, § 5º). A aplicação das frações próprias dos "
        "hediondos carece de base legal.",
        "Requer-se a exclusão da marcação de hediondo e o recálculo das frações e datas de progressão e livramento condicional."),
    "hediondez-posterior-ao-fato-indulto-comutacao-po": (
        "Embora o Superior Tribunal de Justiça afira a hediondez na data do decreto, sustenta-se que a qualificação de hediondo, por ser "
        "posterior ao fato, não pode retroagir para impedir o indulto e a comutação (CF, art. 5º, XL; CP, art. 2º), entendimento acolhido pela "
        "2ª Turma do STF (RHC 267.297 AgR).",
        "Requer-se o afastamento da vedação e a análise do indulto e da comutação com o crime considerado comum."),
    "reincidencia-especifica-nao-demonstrada-no-rspe": (
        "A reincidência específica exige condenação anterior transitada em julgado por crime da mesma natureza antes do novo fato (CP, arts. 63 "
        "e 64). Não demonstrada, aplica-se o percentual do reincidente genérico ou do primário (LEP, art. 112; STJ, Temas 1084 e 1196; STF, "
        "Tema 1169).",
        "Requer-se o afastamento da reincidência específica, com a retificação da fração do livramento condicional e, se for o caso, do "
        "percentual de progressão, e o recálculo das datas dos benefícios."),
    "marcado-reincidente-sem-condenacao-anterior-tran": (
        "A reincidência pressupõe condenação anterior transitada em julgado antes do novo fato e não alcançada pelo período depurador de cinco "
        "anos (CP, arts. 63 e 64, I). Nenhuma condenação com essas características consta do RSPE.",
        "Requer-se a exclusão da marcação de reincidente, ou a indicação da condenação anterior que a fundamenta, com o recálculo das frações e "
        "datas dos benefícios."),
    "condenacao-anterior-depurada": (
        "Decorridos mais de cinco anos entre o cumprimento ou a extinção da pena anterior e o novo fato, a condenação não gera reincidência "
        "(CP, art. 64, I).",
        "Requer-se a exclusão da reincidência e o recálculo das frações e datas dos benefícios."),
    "reincidente-vga-percentual-se-nao-especifica": (
        "O percentual de 30% (LEP, art. 112, IV) pressupõe reincidência em crime cometido com violência à pessoa ou grave ameaça. Ao reincidente "
        "cuja condenação anterior não teve essa natureza, a lei não prevê percentual próprio, e o STJ aplica, por analogia in bonam partem, o do "
        "primário em crime com violência, 25% (LEP, art. 112, III; STJ, AgRg no HC 675.062, 6ª T., 03/08/2021, na linha do Tema 1084).",
        "Não constando dos autos que a condenação anterior tenha sido por crime com violência ou grave ameaça, requer-se a retificação do "
        "percentual de progressão para 25%, com o recálculo das datas."),
    "percentual-de-progressao-diverge": (
        "O percentual de progressão decorre da natureza do crime, da reincidência e da lei vigente à época do fato (LEP, art. 112; CF, art. 5º, "
        "XL). O percentual aplicado não corresponde a esses critérios.",
        "Requer-se a retificação do percentual de progressão e o recálculo da data do benefício."),
    "fracao-de-livramento-diverge": (
        "A fração do livramento condicional é fixada pela natureza do crime e pela reincidência (CP, art. 83). A fração aplicada não corresponde "
        "a esses critérios.",
        "Requer-se a retificação da fração do livramento condicional e o recálculo da data do benefício."),
    "comando-de-organizacao-criminosa-fato-em-75-so-s": (
        "O percentual de 75% e a vedação ao livramento (LEP, art. 112, VI, b, na redação da Lei 15.358/2026) exigem que a condenação reconheça "
        "o comando de organização criminosa ultraviolenta estruturada para a prática de crime hediondo ou equiparado. Sem esse reconhecimento "
        "expresso, aplica-se o percentual próprio do crime.",
        "Requer-se a retificação do percentual de progressão e o recálculo das datas dos benefícios."),
    "livramento-vedado-pelo-seeu-1-1-so-se-a-organiza": (
        "A vedação ao livramento condicional depende de hipótese legal expressa reconhecida na condenação, como o comando de organização "
        "criminosa ultraviolenta (LEP, art. 112, VI, b, na redação da Lei 15.358/2026) ou a manutenção do vínculo associativo (Lei 12.850/2013, "
        "art. 2º, § 9º); não havendo esse reconhecimento, aplica-se a fração do art. 83 do CP.",
        "Requer-se o afastamento da vedação e o cálculo da data do livramento condicional."),
    "marcacao-de-violencia-grave-ameaca-diverge-do-ti": (
        "A violência ou grave ameaça que agrava o percentual de progressão deve integrar o tipo penal ou constar da condenação (LEP, art. 112, "
        "III e IV). A marcação não corresponde ao tipo.",
        "Requer-se a retificação da marcação e o recálculo do percentual e das datas de progressão."),
    "cumprida-remanescente-pena-total": (
        "A pena cumprida somada à remanescente deve corresponder à pena total; a divergência indica erro no cálculo, que repercute em todas as "
        "datas de benefícios (LEP, arts. 66, III, a, e 111).",
        "Requer-se a retificação do cálculo e a emissão de atestado de pena atualizado."),
    "soma-das-penas-difere-da-pena-total": (
        "A pena total da execução deve corresponder à soma das penas das condenações em execução (LEP, art. 111). A divergência altera todas "
        "as frações e datas.",
        "Requer-se a retificação da pena total e o recálculo das datas dos benefícios."),
    "guia-sem-pena-calculada-pena-total-com": (
        "Todas as condenações em execução devem integrar o cálculo, com a respectiva pena (LEP, arts. 105 e 111).",
        "Requer-se a inclusão da pena no cálculo ou a exclusão da guia sem pena, com o recálculo das datas."),
    "dias-remidos-incidentes-nao-fecham-com-o-saldo": (
        "Os dias remidos declarados judicialmente integram a pena cumprida (LEP, arts. 126 e 128). O saldo do cálculo não corresponde à soma "
        "das remições concedidas.",
        "Requer-se a retificação do saldo de dias remidos e o recálculo das datas dos benefícios."),
    "perda-de-dias-remidos-acima-de-1-3-falta-de": (
        "A falta grave permite revogar até 1/3 do tempo remido (LEP, art. 127), limite que alcança apenas a remição adquirida até a infração, "
        "pois a contagem recomeça a partir da data da infração disciplinar (LEP, art. 127; STJ, HC 398.850/SP).",
        "Requer-se a limitação da perda a 1/3 dos dias remidos até a falta e a restituição do excedente, com o recálculo das datas."),
    "perda-de-dias-remidos-em-duplicidade-falta-de": (
        "Após cada falta, a contagem recomeça da data da infração, e a nova perda só alcança a remição adquirida depois da falta anterior (LEP, "
        "art. 127). O desconto repetido sobre a mesma remição é vedado.",
        "Requer-se a restituição dos dias remidos descontados em duplicidade e o recálculo das datas dos benefícios."),
    "perda-de-remidos-sem-falta-grave-datada-no-rspe": (
        "A perda de dias remidos exige falta grave reconhecida em decisão judicial (LEP, arts. 118 e 127; Súmula 533/STJ).",
        "Requer-se a indicação da falta grave que fundamentou a perda e, inexistente, a restituição dos dias remidos."),
    "falta-homologada-apos-prescricao": (
        "A falta disciplinar prescreve no menor prazo do art. 109 do CP (inciso VI: três anos, ou dois anos para fatos anteriores à Lei "
        "12.234/2010), aplicado por analogia e contado da infração ou, na fuga, da recaptura (STJ). Homologada depois de consumada a prescrição, "
        "a falta não produz efeitos.",
        "Requer-se o reconhecimento da prescrição da falta e o afastamento de seus efeitos (regressão, perda de remidos e nova data-base)."),
    "execucao-extinta-segundo-incidente-do-rspe": (
        "Declarada a extinção da pena, a execução correspondente deve ser encerrada (LEP, art. 66, II; CP, art. 107).",
        "Requer-se o reconhecimento da extinção, com a baixa da execução ou, se a extinção alcançou apenas uma das condenações, sua exclusão do "
        "cálculo e o recálculo das datas das demais."),
    "pena-integralmente-cumprida-com-execucao-ativa": (
        "Cumprida integralmente a pena, impõe-se a declaração de sua extinção (LEP, arts. 66, II, e 109).",
        "Requer-se a declaração da extinção da pena pelo integral cumprimento."),
    "pena-cumprida-por-detracao": (
        "O tempo de prisão provisória é computado na pena (CP, art. 42). Se igual ou superior à pena da condenação, a pena está cumprida.",
        "Requer-se o cômputo da detração e a declaração da extinção da pena pelo cumprimento (LEP, art. 66, II)."),
    "indulto-concedido-sem-baixa-no-calculo": (
        "Concedido o indulto, a pena correspondente está extinta (CP, art. 107, II) e deve ser excluída do cálculo.",
        "Requer-se a exclusão da pena indultada do cálculo e o recálculo das datas dos benefícios."),
    "indulto-possivel-sem-incidente-no-rspe": (
        "O indulto é direito do condenado que preenche os requisitos objetivos e subjetivos do decreto, e sua declaração independe de "
        "requerimento prévio (LEP, arts. 192 e 193).",
        "Requer-se a declaração do indulto, com a extinção da pena correspondente."),
    "comutacao-possivel-sem-incidente-no-rspe": (
        "Preenchidos os requisitos do decreto, a comutação é direito do condenado e deve ser declarada (LEP, arts. 192 e 193).",
        "Requer-se a declaração da comutação, com o abatimento da pena e o recálculo das datas dos benefícios."),
    "vencida-em-sem-decisao-posterior-no-rspe": (
        "Implementado o requisito temporal, o benefício deve ser apreciado sem demora (LEP, arts. 66, III, e 112).",
        "Requer-se a apreciação imediata do benefício."),
    "prescricao-da-pretensao-executoria-aparente": (
        "Esgotado o prazo do art. 109 do CP, calculado pela pena aplicada e aumentado de um terço se o condenado é reincidente (CP, art. 110), "
        "contado do termo inicial do art. 112 do CP - observado o Tema 788 do STF quando o trânsito em julgado para a acusação for posterior a "
        "12/11/2020 - e, na fuga ou na revogação do livramento, regulado pelo tempo que resta da pena (CP, art. 113), sem causa interruptiva "
        "(CP, art. 117), a pretensão executória está prescrita (CP, art. 107, IV).",
        "Requer-se o reconhecimento da prescrição da pretensão executória e a declaração da extinção da punibilidade quanto a essa condenação."),
    "prescricao-da-pretensao-punitiva-aparente": (
        "Transcorrido, entre os marcos interruptivos, prazo superior ao do art. 109 do CP calculado pela pena aplicada, a pretensão punitiva está "
        "prescrita (CP, arts. 107, IV, e 110, § 1º).",
        "Requer-se o reconhecimento da prescrição da pretensão punitiva e a declaração da extinção da punibilidade quanto a essa condenação."),
    "prescricao-executoria-a-verificar-saldo-na-evasao": (
        "Na fuga, a prescrição regula-se pelo tempo que resta da pena (CP, art. 113), apurado para cada condenação (CP, art. 119).",
        "Requer-se a juntada do cálculo da pena remanescente na data da fuga e, consumado o prazo, o reconhecimento da prescrição da pretensão "
        "executória."),
    "menor-de-21-anos-no-fato-prescricao-pela-metade": (
        "São reduzidos pela metade os prazos de prescrição quando o agente era menor de 21 anos na data do fato (CP, art. 115).",
        "Requer-se a aplicação da redução do art. 115 do CP na contagem dos prazos prescricionais."),
    "idade-para-o-indulto-lapsos-pela-metade": (
        "Os decretos de indulto reduzem os lapsos em razão da idade do condenado, requisito a ser aferido na data do decreto.",
        "Requer-se a análise do indulto e da comutação com os lapsos reduzidos pela idade."),
    "idade-prisao-domiciliar-no-regime-aberto-lep-art": (
        "O condenado maior de 70 anos em regime aberto tem direito ao recolhimento em residência particular (LEP, art. 117, I).",
        "Estando o assistido no regime aberto, requer-se o recolhimento em residência particular (LEP, art. 117, I)."),
    "rspe-anterior-a-correcao-do-seeu": (
        "O relatório foi emitido antes de correção do cálculo pelo próprio SEEU, e as datas dos benefícios devem refletir o cálculo corrigido "
        "(LEP, art. 66, III).",
        "Requer-se a atualização do cálculo e a emissão de novo atestado de pena."),
}
# frases de orientação ao operador que não cabem na peça
_RE_ORIENTACAO = re.compile(r"^(conferir|confira|importe|informe|verificar|verifique|o programa|clique|use |ver a aba|pedir|cabe impugnar|"
                            r"cabe pedir|marque|preencha|decida|se for o caso, informe|sem ele|sem esse)", re.I)
_RE_DIREITO = re.compile(r"\b(CP|LEP|CF|STJ|STF|S[úu]mula|Tema|Lei \d|art\.)", re.I)


def _frases(t):
    return [x.strip() for x in re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ(])", t or "") if x.strip()]


# prejuízo concreto de cada tipo de erro (terceiro parágrafo da impugnação): o que o erro causa ao assistido
_IMPACTO = [
    (r"reincidencia-especifica",
     "Com isso, o livramento condicional é vedado ou postergado e, conforme a lei da data do fato, o percentual de progressão pode ser "
     "elevado, sem que a reincidência específica esteja demonstrada."),
    (r"percentual-de-progressao|reincidente-vga|comando-de-organizacao",
     "Com isso, exige-se para a progressão mais pena cumprida do que a lei determina{pct}: a data do benefício é postergada e o assistido "
     "permanece em regime mais gravoso que o devido."),
    (r"fracao-de-livramento|livramento-vedado",
     "Com isso, o livramento condicional é postergado ou impedido{pct}, e o assistido permanece preso além do tempo exigido em lei."),
    (r"hediondez-posterior-ao-fato-indulto",
     "Com isso, o indulto e a comutação são afastados por uma vedação que não existia na data do fato."),
    (r"capitulacao",
     "Se mantido, o cadastro pode levar à aplicação das frações de crime hediondo na progressão e no livramento e à vedação do indulto e "
     "da comutação, inexistentes na lei vigente à época do fato."),
    (r"hediond",
     "Com isso, aplicam-se as frações de crime hediondo na progressão e no livramento e se afastam o indulto e a comutação sem base legal."),
    (r"reincidente-sem|depurada",
     "A reincidência indevida eleva as frações de progressão, livramento, indulto e comutação e retarda todos os benefícios."),
    (r"violencia-grave-ameaca",
     "A marcação indevida eleva o percentual de progressão e posterga a data do benefício."),
    (r"data-base-do-livramento",
     "Com isso, despreza-se, para o livramento condicional, tempo de pena já cumprido, e a data do benefício é postergada pelo mesmo período."),
    (r"data-base|regime-inicial|progressao-com-data-base",
     "Com isso, despreza-se tempo de pena já cumprido para a progressão seguinte, que é postergada pelo mesmo período."),
    (r"guia-suspensa|soma-das-penas|cumprida-remanescente|guia-sem-pena",
     "Com a pena total incorreta, todas as frações - progressão, livramento, indulto e comutação - e a data do término são calculadas "
     "sobre base errada."),
    (r"remidos",
     "Os dias remidos descontados indevidamente deixam de contar como pena cumprida e retardam todos os benefícios e o término da pena."),
    (r"falta-homologada-apos-prescricao",
     "A falta prescrita continua a produzir efeitos - regressão, perda de dias remidos e nova data-base - que não podem subsistir."),
    (r"extinta|integralmente|cumprida-por-detracao|indulto-concedido",
     "O assistido segue submetido à execução de pena já extinta ou cumprida, com reflexo indevido nas demais condenações e nos benefícios."),
    (r"indulto-possivel|comutacao-possivel",
     "Sem a declaração, a execução prossegue sobre pena que o decreto já alcançou."),
    (r"vencida",
     "Cada dia sem apreciação é cumprido em situação mais gravosa que a devida."),
    (r"prescricao-da|prescricao-executoria",
     "A execução prossegue sobre pena cuja pretensão o Estado já não detém."),
    (r"rspe-anterior",
     "As datas de benefícios informadas no relatório não refletem o cálculo corrigido."),
]
_ABREV = [(r"\bsem VGA\b", "sem violência ou grave ameaça"), (r"\bcom VGA\b", "com violência ou grave ameaça"), (r"\bVGA\b", "violência ou grave ameaça"),
          (r"\bdeste RSPE\b", "do RSPE")]


def _abrev(t):
    for a, b in _ABREV:
        t = re.sub(a, b, t)
    return t


def _fatos(it):
    """Fatos concretos do detalhe (datas, números, dados da condenação), sem as orientações ao operador nem a regra geral."""
    out = []
    for f in [y for x in _frases(it.get("detalhe")) for y in re.split(r"(?<=\.)\s+(?=[a-z])", x)]:
        if _RE_ORIENTACAO.search(f):
            continue
        f = re.sub(r"\s*[-:;,]\s*(conferir|verificar|confira|verifique)\b.*$", ".", f, flags=re.I).rstrip(";").strip()
        if not re.search(r"\d", f) and not re.search(r"\b(reincidente|prim[áa]ri[oa]|hediondo|anacr[ôo]nico|reda[çc][ãa]o da [ée]poca)\b", f, re.I):
            continue
        if re.search(r"\b(s[óo] se|n[ãa]o pode|pode vir|pode ter|afeta|deve|devem|exce[çc][ãa]o)\b", f, re.I):
            continue
        if _RE_DIREITO.search(f) and not re.search(r"\d{2}/\d{2}/\d{4}", f) and not f.startswith("Na data do fato"):
            continue  # regra geral sem data: vai no parágrafo do direito
        if re.match(r"^[^.]{0,70}\(decis[ãa]o de [^)]*\)\.?$", f) or len(f) < 20:
            continue
        if f.count("(") != f.count(")"):
            continue  # frase cortada dentro de um parêntese
        f = _abrev(f[0].upper() + f[1:])
        f = re.sub(r" \(o cálculo não marca reincidência específica[^)]*\)", "", f)
        if re.search(r"\bhediondo\b", f):
            f = f.replace("; sem violência ou grave ameaça", "").replace("; com violência ou grave ameaça", "")
        if f.count(";") >= 1 and all(len(x.strip()) < 32 for x in f.rstrip(".").split(";")):
            f = "O cálculo registra: " + f[0].lower() + f[1:]
        out.append(f if f.endswith(".") else f + ".")
    return out[:3]


def _limpa_par(t):
    """'(40% (Lei 13.964/2019 (Pacote Anticrime)))' -> '(40% - Lei 13.964/2019, Pacote Anticrime)'; '(2/3 (art. 83, V, CP))' -> '(2/3 - art. 83, V, CP)'."""
    t = re.sub(r"\((\d+%|\d+/\d+) \(([^()]*?) \(([^()]*)\)\)\)", r"(\1 - \2, \3)", t)
    return re.sub(r"\((\d+%|\d+/\d+) \(([^()]*)\)\)", r"(\1 - \2)", t)


# títulos de alerta que não cabem na peça como estão (rótulo interno): versão forense
_TIT_PECA = {
    "cumprida-remanescente-pena-total": "a soma da pena cumprida com a remanescente não corresponde à pena total",
    "soma-das-penas-difere-da-pena-total": "a soma das penas das condenações não corresponde à pena total",
    "alteracao-de-data-base-no-lugar-do-incidente": "a data-base foi fixada por alteração avulsa, que não acompanha os marcos legais posteriores",
}


def _razao(tipo, it, tit):
    """Por que o valor do cálculo está errado neste caso concreto (só onde o RSPE dá a razão)."""
    det = it.get("detalhe") or ""
    pc = re.findall(r"\((\d+%)", tit)
    rot_esp = " - embora o rótulo da fração lançada mencione \"Reincidente Específico\" -" if "Reincidente Específico" in tit else ""
    gen = ("No caso, a reincidência é genérica: o campo de reincidência específica da condenação não está marcado no cálculo%s%s. " % (
        rot_esp, " e nenhuma condenação anterior por crime hediondo ou equiparado, transitada antes do fato, consta do RSPE"
        if "sem condenação anterior por hediondo" in det else ""))
    if tipo == "percentual-de-progressao-diverge" and "reincidente genérico" in det and len(pc) >= 2:
        morte = "com morte" in det
        m = re.search(r"Fato em (\d{2}/\d{2}/\d{4})", det)
        fato = rs.to_date(m.group(1)) if m else None
        lei_esp = (" com resultado morte (LEP, art. 112, VIII)" if morte else " (LEP, art. 112, VII)")
        prim = pc[1] + (" (LEP, art. 112, VI, a)" if morte else " (LEP, art. 112, V)")
        prec = "STJ, Tema 1196" if morte else "STJ, Tema 1084; STF, Tema 1169"
        if fato and fato >= date(2026, 3, 25):
            fim = ("aplica-se, por analogia in bonam partem, o percentual do primário, %s, pela mesma razão adotada no %s." % (pc[1], prec))
        elif fato and fato >= date(2020, 1, 23):
            fim = ("a Lei 13.964/2019, vigente na data do fato, não prevê percentual próprio, e aplica-se o do primário, %s (%s)." % (prim, prec))
        else:
            fim = ("a Lei 13.964/2019 não prevê percentual próprio, e aplica-se o do primário, %s, que, por ser mais benéfico que a fração "
                   "vigente na data do fato, retroage (CF, art. 5º, XL; %s)." % (prim, prec))
        return gen + "O percentual de %s é o do reincidente específico em crime hediondo%s; para o reincidente genérico, %s" % (pc[0], lei_esp, fim)
    if tipo == "fracao-de-livramento-diverge" and "reincidente genérico" in det and re.search(r"\(1/1\b", tit):
        return gen + ("Fora das vedações próprias do art. 112 da LEP, que não incidem no caso, a vedação do livramento condicional alcança "
                      "apenas o reincidente específico em crime hediondo ou equiparado (CP, art. 83, V, parte final); ao reincidente genérico "
                      "aplica-se a fração de 2/3 do mesmo inciso.")
    return ""


def _citacoes(fund, ja):
    """Precedentes do campo fundamento que ainda não estão no texto (sem repetir a lei já citada)."""
    out = []
    for trib, corpo in re.findall(r"\b(STJ|STF),?\s+((?:Temas?|S[úu]mulas?|AgRg|HC|RHC|REsp|RE)\b[^;()]*?)(?=[;)]|$)", fund):
        corpo = corpo.strip().rstrip(".")
        nums = re.findall(r"\d[\d.]*", corpo)
        novos = [n for n in nums if n not in ja]
        if not nums or not novos:
            continue
        if re.match(r"Temas?\b", corpo) and len(novos) < len(nums):
            corpo = ("Tema %s" if len(novos) == 1 else "Temas %s") % (", ".join(novos[:-1]) + " e " + novos[-1] if len(novos) > 1 else novos[0])
        out.append("%s, %s" % (trib, corpo))
    return "; ".join(out)


def fundamentacao(it, r):
    """Impugnação do cálculo em 4 parágrafos curtos: (1) o que o cálculo mostra, com os dados concretos do RSPE; (2) por que está
    errado, com o fundamento; (3) o prejuízo ao assistido; (4) o pedido."""
    tipo = it.get("tipo") or ""
    if it.get("nivel") not in ("alerta", "verificar") or tipo not in FUND_TIPOS:
        return ""
    if tipo == "idade-prisao-domiciliar-no-regime-aberto-lep-art" and "ABERTO" not in (r.get("regime_atual") or "").upper():
        return ""  # LEP, art. 117, I: só no regime aberto
    if tipo == "alteracao-de-data-base-no-lugar-do-incidente" and it.get("nivel") != "alerta":
        return ""  # só a data-base fixa é erro a impugnar; no "verificar", o marco pode justificar a alteração
    correto, pedido = FUND_TIPOS[tipo]
    ger = r.get("data_geracao_rspe") or ""
    rel = "o cálculo de pena (Relatório da Situação Processual Executória%s)" % ((" emitido em %s" % ger) if ger else "")
    tit = _limpa_par(re.sub(r"\s+", " ", it.get("titulo") or "").strip().rstrip("."))
    tit = re.sub(r"\s*\([^()]*\?\)", "", tit)  # dúvida interna do alerta, ex.: "(data-base fixa?)"
    tit = _TIT_PECA.get(tipo, tit)
    m = re.match(r"^Proc\. ([\d.\-]+) · ([^:]+): (.+)$", tit)
    nao_erro = bool(re.search(r"vencida|possivel|prescricao|idade|menor-de-21|extinta|integralmente|detracao", tipo))
    verbo = "dele consta" if nao_erro else "apresenta a seguinte inconsistência"
    if m:
        erro = "Na condenação do processo %s (%s), %s %s: %s." % (m.group(1), m.group(2).strip(), rel, verbo, m.group(3))
    else:
        erro = "%s %s: %s." % (rel[0].upper() + rel[1:], verbo, tit[0].lower() + tit[1:] if tit[:2] != tit[:2].upper() else tit)
    fatos = [f for f in _fatos(it) if f.rstrip(".") not in tit]
    if tipo == "hediondez-posterior-ao-fato-indulto-comutacao-po":
        fatos = ["O crime não era hediondo na data do fato e passou a sê-lo por lei posterior."]
    if fatos:
        erro += " " + " ".join(fatos)
    erro = _abrev(erro)
    razao = _razao(tipo, it, tit)
    extra = (" " + razao) if razao else ""
    cit = "" if razao else _citacoes(it.get("fundamento") or "", correto + extra)
    if cit:
        extra += " Nesse sentido: %s." % cit
    elif not _RE_DIREITO.search(it.get("fundamento") or "") and (it.get("fundamento") or "").strip():
        extra += " Fonte: %s." % it["fundamento"].strip().rstrip(".")
    imp = next((t for rx, t in _IMPACTO if re.search(rx, tipo)), "")
    if imp:
        pc = re.findall(r"\((\d+%|\d+/\d+)", tit)
        pct = (" (%s no lugar de %s)" % (pc[0], pc[1])) if len(pc) >= 2 else ""
        imp = imp.format(pct=pct)
    return "\n\n".join(x for x in (erro, correto + extra, imp, pedido) if x)