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
from datetime import date
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


def _item(nivel, titulo, detalhe, fundamento="", tipo="", ref=""):
    """tipo: identificador fixo do ponto (não muda com números, datas ou agrupamento do título); ref: o crime, o ano
    ou a falta a que o ponto se refere. A baixa usa tipo + ref (o processo já separa as baixas)."""
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "fundamento": fundamento, "tipo": tipo, "ref": ref or ""}


def _fr_seeu(txt):
    f = rs.parse_fracao(txt or "")
    return f


def _hediondo_seeu(c):
    return "HEDIONDO" in ((c.get("fracao_progressao") or "") + (c.get("fracao_livramento") or "")).upper()


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
    pu = h.get("paragrafo_unico", {})
    if lei in pu:
        regra = pu[lei]
        if isinstance(regra, dict):
            if art in regra:
                return (True, "") if regra[art] == "sempre" else (None, "art. 1º, p. ú., Lei 8.072/90: " + regra[art])
        elif isinstance(regra, list) and art in [str(x).split()[0] for x in regra]:
            return True, ""
    return False, ""


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
            det = " | ".join(d for d in g["detalhes"] if d)
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
                               FUND_127 + " STF, Tema 477 (RE 1.116.485).", tipo="perda-de-dias-remidos-acima-de-1-3-falta-de", ref=rs.fmt(f)))
        elif not dup:
            itens.append(_item("info", "Perda de %s remidos pela falta grave de %s" % (rs.pl(x["perda"], "dia", "dias"), rs.fmt(f)),
                               "Dentro do limite de 1/3 (remição %s: %s)." % (("entre a falta de %s e esta" % rs.fmt(prev)) if prev else "até a falta", rs.pl(base, "dia", "dias")) + ress, "LEP, art. 127.", tipo="perda-de-remidos-pela-falta-grave-de", ref=rs.fmt(f)))
    return itens


def auditar(r, hoje=None):
    hoje = hoje or date.today()
    itens = []
    crimes = r.get("_crimes", [])
    ativos = [c for c in crimes if not c.get("extinto", "").upper().startswith("S")]
    incidentes = r.get("_incidentes", [])
    eventos = r.get("_eventos", [])
    nasc = rs.to_date(r.get("data_nascimento") or "")
    pena_total = rs.pena_para_dias(r.get("pena_total"))
    cumprida = rs.pena_para_dias(r.get("pena_cumprida"))
    reman = rs.pena_para_dias(r.get("pena_remanescente"))

    faltam = rs.campos_faltantes(r)
    if faltam:
        itens.append(_item("verificar", "Dados ausentes no RSPE: %s" % ", ".join(faltam),
                           "O SEEU não imprimiu esses dados (guia sem cálculo, pena interrompida) ou o programa não conseguiu lê-los. Os cálculos deste assistido podem ficar incompletos; conferir o PDF."
                           + (" Data do fato, pena, sentença e trânsito de cada crime: preencher em Prescrição → editar dados." if any("crime" in f for f in faltam) else ""),
                           "", tipo="dados-ausentes-no-rspe"))
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
    # indícios de falta: a decisão fica com o operador (botão Preencher); fuga é falta grave por padrão (LEP, art. 50, II)
    for fi in rs.faltas_editaveis(incidentes, eventos):
        dec = fi["decisao"]
        rot = {"sim": "falta grave", "nao": "não houve falta grave"}.get(dec, "")
        fuga = fi["padrao"] == "falta"
        if dec:
            it = _item("verificar", "%s em %s: %s" % ("Fuga" if fuga else "Falta a apurar", fi["data"] or "data não informada", "informar se houve falta grave"),
                       fi["texto"], "LEP, arts. 50 e 118; STJ, Tema 1195.", tipo="falta-a-apurar", ref=fi["chave"])
            it["auto_baixa"] = {"obs": "Decisão do operador: %s. Vale em todas as abas (falta nos 12 meses, indulto, comutação)." % rot, "data": ""}
        elif fuga:
            it = _item("info", "Fuga em %s tratada como falta grave" % (fi["data"] or "data não informada"),
                       "%s. Fuga é falta grave (LEP, art. 50, II) e impede o indulto e a comutação quando está na janela do decreto, "
                       "ainda que homologada depois (STJ, Tema 1195). Se não houve falta (retorno justificado, absolvição no PAD), "
                       "informe pelo botão Preencher." % fi["texto"], "LEP, art. 50, II; STJ, Tema 1195.", tipo="fuga-falta-grave", ref=fi["chave"])
        else:
            it = _item("verificar", "Falta a apurar em %s: informar se houve falta grave" % (fi["data"] or "data não informada"),
                       "%s. O RSPE não registra sanção reconhecida. Informe se houve falta grave: a decisão vale em todas as abas "
                       "(falta nos 12 meses, indulto, comutação, linha do tempo)." % fi["texto"], "LEP, arts. 50 e 118; STJ, Tema 1195.",
                       tipo="falta-a-apurar", ref=fi["chave"])
        it["preencher"] = {"campo": "falta|" + fi["chave"], "rotulo": fi["texto"], "tipo": "falta", "data": fi["data"], "padrao": fi["padrao"], "decisao": dec}
        itens.append(it)
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
    for c in ativos:
        _ff = rs.to_date(c.get("data_infracao") or "")
        if _ff and _ff > date(2022, 12, 25):
            continue  # só o Decreto 11.302/2022 usa a pena máxima em abstrato
        _inf = c.get("_pena_max_inf")
        if _inf or rs.pena_maxima_abstrata(dict(c)) is None:
            ch = rs.chave_pena_max(c)
            if ch in _pm_vistos:
                continue
            _pm_vistos.add(ch)
            nome = rs.crimes_curto([c])
            it = _item("verificar", "%s: pena máxima em abstrato não lida do RSPE - informar" % nome,
                       "O SEEU cortou o texto do tipo penal e o tipo não está na tabela da base jurídica. Sem a pena máxima, o indulto do "
                       "Decreto 11.302/2022 (art. 5º: pena máxima de até 5 anos) fica A VERIFICAR. Informe a pena máxima cominada pelo botão Preencher.",
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
    if not pena_total and ativos:
        soma_at = sum(rs.pena_para_dias(c.get("pena_imposta")) or 0 for c in ativos)
        itens.append(_item("alerta", "Guia sem pena calculada: pena total %s com %s" % (r.get("pena_total") or "em branco", rs.pl(len(ativos), "condenação ativa", "condenações ativas")),
                           "As condenações ativas somam %s%s. Sem cálculo de pena, regime atual, marcos e término não constam; conferir se as guias foram unificadas/calculadas no SEEU." % (
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
        reinc = c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S"
        # reincidência efetiva: a linha pode dizer "N" havendo condenação anterior transitada antes do fato (CP, art. 63)
        _ant = [o for o in crimes if o is not c and fato and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "")
                and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < fato]
        reinc_ef = reinc or bool(_ant)
        reinc_esp = c.get("reincidente_especifico") == "S"
        vga = c.get("vga") == "S"
        morte = c.get("resultado_morte") == "S"
        hed_seeu = _hediondo_seeu(c)
        hed_lei, obs_h = _e_hediondo_lei(c)
        esp_ok = None  # reincidência específica em hediondo/tráfico: True confirmada no RSPE, False não aferível
        if reinc_esp and (hed_seeu or hed_lei or _trafico(c) or _trafico_pessoas(c)):
            _conf, _semt, _naoh = _reinc_especifica(c, crimes)
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
                                   "%s e o livramento é possível (2/3). O RSPE aplica %s. "
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
        if not art:
            itens.append(_item("info", "%s: artigo não informado" % nome, "O SEEU não registrou o artigo e a descrição do tipo não foi reconhecida: \u201c%s\u201d." % _descricao_tipo(c), "Sem o artigo, hediondez, VGA e frações ficam sem conferência.", tipo="artigo-nao-informado", ref=nome))
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
        esperado = rg.vga_esperado(art) if art else None
        # só a marcação que prejudica (VGA = S onde o tipo não a exige); VGA = N a mais é favorável e não se aponta
        if esperado and c.get("vga") == "S" and esperado != c.get("vga"):
            itens.append(_item("alerta" if c.get("vga") == "S" else "info", "%s: marcação de violência/grave ameaça diverge do tipo" % nome,
                               "RSPE: VGA = %s; pelo tipo penal esperava-se %s. Reflete nas frações de progressão e no indulto (arts. 9º, I a III dos decretos)." % (c.get("vga"), esperado),
                               "LEP, art. 112, I e II; Decretos 12.338/2024 e 12.790/2025.", tipo="marcacao-de-violencia-grave-ameaca-diverge-do-ti", ref=nome))
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
        if reinc and not reinc_esp and hed:
            for _dref in ([fato, date(2020, 1, 23)] if fato and fato < date(2020, 1, 23) else [fato]):
                f_esp2, rot2, obs2 = rg.fracao_progressao_esperada(_dref, hed, morte, vga, reinc, reinc_especifico=False, especial=especial)
                if f_esp2 is not None and (f_esp is None or f_esp2 < f_esp):
                    f_esp, rot, obs = f_esp2, rot2, obs + obs2 + (["retroatividade da lei mais benéfica (Lei 13.964/2019; STJ Tema 1084)"] if _dref != fato else [])
        # reincidente em crime com VGA: o RSPE não diz se a condenação anterior teve violência; se não teve, a base prevê o
        # percentual do primário com VGA por analogia (vga_reincidente_generico). Só informa: o esperado segue o vga_reincidente
        _jan = rg.regime_progressao(fato) if fato else None
        _vg = (_jan or {}).get("vga_reincidente_generico")
        if (vga and reinc and not reinc_esp and not hed and not especial and _vg and f_seeu is not None
                and float(f_seeu) > float(rg.fr(_vg)) + 0.001):
            itens.append(_item("info", "%s: reincidente em crime com violência ou grave ameaça - percentual se a reincidência não for específica" % nome,
                               "O SEEU aplica %s. Se a condenação anterior não foi por crime com violência ou grave ameaça, o percentual por analogia "
                               "in bonam partem é %s (STJ, Tema 1084, aplicado por analogia). O RSPE não informa a natureza da condenação anterior: "
                               "conferir a certidão de antecedentes. O cálculo da Auditoria não muda." % (rs.pct_rotulo(c.get("fracao_progressao")), _vg),
                               "LEP, art. 112, III e IV; STJ, Tema 1084.", tipo="reincidente-vga-percentual-se-nao-especifica", ref=nome))
        if orcrim_uv:
            itens.append(_item("verificar", "%s: comando de organização criminosa (fato em %s) - 75%% só se a organização for ultraviolenta" % (nome, rs.fmt(fato)),
                               "Desde 25/03/2026 (Lei 15.358/2026), o art. 112, VI, b, da LEP prevê 75%%, vedado o livramento, ao condenado por exercer o comando de organização "
                               "criminosa ultraviolenta estruturada para a prática de crime hediondo ou equiparado. O RSPE não informa se a organização é ultraviolenta: "
                               "sem essa qualificação, vale o percentual do crime. No RSPE: progressão %s." % rs.pct_rotulo(c.get("fracao_progressao")),
                               "LEP, art. 112, VI, b (redação da Lei 15.358/2026).", tipo="comando-de-organizacao-criminosa-fato-em-75-so-s", ref=nome))
        if orcrim_uv and f_seeu is not None and abs(float(f_seeu) - 0.75) <= 0.01:
            pass  # 75% aplicado pelo SEEU: depende da qualificação "ultraviolenta" (item acima)
        elif f_seeu is not None and f_esp is not None:
            if abs(float(f_seeu) - float(f_esp)) > 0.01:
                itens.append(_item("alerta" if float(f_seeu) > float(f_esp) else "info",
                               ("%s: percentual de progressão do SEEU (%s) maior que o legal (%s)" if float(f_seeu) > float(f_esp) else "%s: percentual de progressão do SEEU (%s) menor que o esperado (%s) - favorece o apenado") % (nome, rs.pct_rotulo(c.get("fracao_progressao")), rs.pct_rotulo(rot)),
                               "Fato em %s; %s; %s; %s. %s" % (rs.fmt(fato) if fato else "?", "reincidente" if reinc else "primário", "com VGA" if vga else "sem VGA",
                                                               "hediondo" if hed else "comum", rs.pct_texto(" ".join(obs))),
                               "LEP, art. 112 (redação vigente na data do fato; lei posterior só retroage se mais benéfica - CF, art. 5º, XL; STJ Temas 1084, 1196 e 1354; STF Tema 1169).", tipo="percentual-de-progressao-diverge", ref=nome))
            elif esp_ok is False:
                pass  # o alerta de reincidência específica já trata do 60%
            else:
                nota = " ".join(obs) or "Conforme a lei da data do fato."
                if abs(float(f_seeu) - float(f_esp)) > 0.001:
                    nota += " (diferença marginal 16,67% x 16%: STJ Tema 1354 admite o percentual mais benéfico)"
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
        if esp_ok is not None:
            # reincidente específico em hediondo/tráfico: livramento vedado (CP, art. 83, V; Lei 11.343/06, art. 44, p. ú.);
            # o 1/1 do SEEU é coerente com a marcação - a base da reincidência é conferida no item próprio
            fl_esp, rotl = Fraction(1, 1), "vedado (reincidente específico)"
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
                               "%s; %s." % ("reincidente" if reinc_ef else "primário", "hediondo/equiparado" if hed else ("art. 44, p. ú., Lei 11.343/06" if trafico else
                                                                                                  "tráfico de pessoas, art. 83, V, CP" if _trafico_pessoas(c) else "comum")), "CP, art. 83; Lei 11.343/06, art. 44, p. ú.", tipo="fracao-de-livramento-diverge", ref=nome))
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
        if reinc and fato:
            anteriores = [o for o in crimes if o is not c and rs.to_date(o.get("transito_processo") or o.get("transito_mp") or "") and rs.to_date(o.get("transito_processo") or o.get("transito_mp")) < fato]
            if not anteriores:
                reinc_sem_base.append(fato)
        # idade
        if nasc:
            i_fato = fato.year - nasc.year - ((fato.month, fato.day) < (nasc.month, nasc.day)) if fato else None
            if i_fato is not None and i_fato < 21:
                itens.append(_item("verificar", "%s: menor de 21 anos no fato (%d) - prescrição pela metade" % (nome, i_fato), "Conferir se o SEEU/juízo considerou o art. 115 nos cálculos de prescrição.", "CP, art. 115.", tipo="menor-de-21-anos-no-fato-prescricao-pela-metade", ref=nome))

    if reinc_sem_base:
        itens.append(_item("verificar", "Marcado reincidente sem condenação anterior transitada no RSPE",
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
        if d and (ult is None or d > ult[0]):
            ult = (d, i)
    for i in regs:
        if "PROGRESS" in (i.get("complemento") or "").upper() and i.get("data_decisao") and i.get("data_decisao") == i.get("data_referencia"):
            itens.append(_item("info", "Progressão com data-base igual à data da decisão (%s)" % i.get("data_decisao"),
                               "A data-base da progressão seguinte deve ser a data em que os requisitos foram preenchidos, não a da decisão que a deferiu; se o lapso já estava vencido antes, a data-base pode ser anterior.",
                               "STJ, Tema 1165 (REsp 1.973.589).", tipo="progressao-com-data-base-igual-a-data-da-decisao"))
            break
    db_seeu = rs.to_date(r.get("data_base_seeu") or "")
    if db_seeu and ult and db_seeu < ult[0]:
        itens.append(_item("alerta", "Data-base de progressão anterior à última alteração de regime",
                           "Data-base impressa: %s; última alteração de regime: %s (%s)." % (rs.fmt(db_seeu), rs.fmt(ult[0]), ult[1].get("complemento")),
                           "LEP, art. 112, § 6º (falta grave reinicia pela remanescente); STJ Tema 1006 (a unificação de penas não altera a data-base); STJ Tema 1165 (data-base é a do preenchimento dos requisitos, não a da decisão).", tipo="data-base-de-progressao-anterior-a-ultima-altera"))
    # data-base x eventos que a justificam: última prisão/início do cumprimento, progressão/regressão ou falta grave homologada
    if db_seeu:
        marcos = []
        for e in r.get("_eventos", []):
            t = ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper()
            d = rs.to_date(e.get("data") or "")
            if d and re.search(r"PRIS|IN[ÍI]CIO|REIN[ÍI]CIO|RECAPTURA", t):
                marcos.append((d, "prisão/início do cumprimento (%s)" % (e.get("motivo") or e.get("tipo") or "").strip().lower()))
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
                elif "REGIME" in t:
                    marcos.append((d, "alteração de regime (%s)" % (i.get("complemento") or "").strip()))
                elif "FALTA GRAVE" in t:
                    marcos.append((d, "falta grave homologada"))
                elif "LIVRAMENTO" in t and "REVOG" in (t + " " + (i.get("complemento") or "")).upper():
                    marcos.append((d, "revogação do livramento"))
        bate = [m for m in marcos if abs((m[0] - db_seeu).days) <= 1]
        unif = [i for i in incidentes if re.search(r"SOMAT|UNIFICA", (i.get("tipo") or "").upper())
                and any(rs.to_date(i.get(c) or "") and abs((rs.to_date(i.get(c)) - db_seeu).days) <= 1 for c in ("data_referencia", "data_decisao"))]
        # fuga: a data-base vai para a recaptura (infração permanente), mas a falta tem de ser apurada e homologada
        _fuga = [rs.to_date(e.get("data") or "") for e in r.get("_eventos", [])
                 if "FUGA" in ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper()]
        _fuga = sorted(d for d in _fuga if d)
        _homolog = any(re.search(r"FALTA|DISCIPLINAR|PAD\b", (i.get("tipo") or "") + " " + (i.get("complemento") or ""), re.I)
                       for i in incidentes if i.get("situacao") == "CONCEDIDO")
        _recapt = bool(bate) and "recaptura" in (bate[0][1] if bate else "").lower()
        if _fuga and _recapt and _fuga[-1] < db_seeu and not _homolog:
            itens.append(_item("verificar", "Data-base movida para a recaptura (%s) sem falta homologada no RSPE" % rs.fmt(db_seeu),
                               "Houve fuga em %s e recaptura em %s. Na fuga, a nova data-base é a da recaptura, porque a falta é permanente, "
                               "mas a interrupção depende de apuração em procedimento disciplinar com defesa técnica e de homologação judicial, "
                               "e o RSPE não registra esse incidente. Sem homologação, a data-base volta a ser %s e a progressão se antecipa; "
                               "a perda de até 1/3 dos %s remidos também depende dessa apuração." % (
                                   rs.fmt(_fuga[-1]), rs.fmt(db_seeu), ("%s (%s)" % (rs.fmt(ant2[0]), ant2[1]) if (ant2 := next((m for m in sorted(marcos, key=lambda x: x[0], reverse=True) if m[0] < _fuga[-1]), None)) else "a anterior"),
                                   rs.pl(rs.saldo_remidos_num(r.get("saldo_remidos"))[0], "dia", "dias")),
                               "LEP, arts. 50, II, 57, 59, 118 e 127; Súmulas 533, 534 e 535/STJ; STJ, Tema 709.", tipo="data-base-movida-para-a-recaptura-sem-falta-homo"))
        elif bate:
            itens.append(_item("ok", "Data-base (%s) confere com o RSPE: %s" % (rs.fmt(db_seeu), bate[0][1]), "", "LEP, art. 112.", tipo="data-base-confere-com-o-rspe"))
        elif unif:
            itens.append(_item("alerta", "Data-base (%s) coincide com a soma/unificação das penas" % rs.fmt(db_seeu),
                               "Não há prisão, alteração de regime ou falta grave homologada nessa data; a data coincide com o incidente de %s. "
                               "A unificação não altera a data-base: ela continua sendo a da última prisão, progressão ou falta grave." % (unif[0].get("tipo") or "").lower(),
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
        itens.append(_item("alerta", "Data-base do livramento (%s) alterada por falta grave" % rs.fmt(_dbl),
                           "A falta grave interrompe o prazo da progressão, não o do livramento condicional, nem os do indulto e da comutação. "
                           "A data-base do livramento deve continuar a do início do cumprimento.",
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
            itens.append(_item("verificar", "Idade %s: prisão domiciliar no regime aberto (LEP, art. 117, I); conferir a idade na data da sentença para o art. 115 do CP" % rs.pl(idade, "ano", "anos"),
                               "Art. 117, I, da LEP: recolhimento em residência particular do beneficiário do regime aberto maior de 70 anos. "
                               "Art. 115 do CP: prazos de prescrição pela metade só se era maior de 70 anos na data da sentença (a aba Prescrição calcula).",
                               "CP, art. 115; LEP, art. 117, I.", tipo="idade-prisao-domiciliar-no-regime-aberto-lep-art"))
        # § 2º, I, dos decretos: maior de 60 anos em 25/12 do ano do decreto (medido na data de cada decreto)
        _i60 = []
        for _ano, _ref in sorted(rs.DECRETOS.items()):
            _id = _ref.year - nasc.year - ((_ref.month, _ref.day) < (nasc.month, nasc.day))
            if _id >= 60:
                _i60.append("%s em %s" % (rs.pl(_id, "ano", "anos"), rs.fmt(_ref)))
        if _i60:
            itens.append(_item("verificar", "Idade para o indulto: lapsos pela metade (%s)" % "; ".join(_i60),
                               "Decretos 12.338/2024 e 12.790/2025, art. 9º, § 2º, I (pessoas maiores de sessenta anos): os lapsos dos incisos I a XI caem pela metade.", "", tipo="idade-para-o-indulto-lapsos-pela-metade"))

    # LEP, art. 112, §§ 3º e 4º: progressão com 1/8 para a mulher gestante, mãe ou responsável por criança ou pessoa com
    # deficiência - o RSPE não informa sexo nem filhos; só se aponta quando os demais requisitos objetivos batem
    _fr_seeu_max = max((_fr_seeu(c.get("fracao_progressao")) or 0 for c in ativos), default=0)
    if (ativos and not any(c.get("vga") == "S" for c in ativos)
            and not any(c.get("comando_orcrim") == "S" or rs.num_lei(c.get("lei")) == "12850" for c in ativos)
            and not any(c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S" for c in ativos)
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
        if l.get("ppe_detracao_cobre"):
            itens.append(_item("verificar", "%s: detração iguala ou supera a pena do processo - conferir extinção pelo cumprimento" % rot,
                               "Custódia anterior ao trânsito de %s e pena do processo de %s. A mesma prisão pode servir a várias condenações (a detração vale uma vez só na "
                               "pena unificada); se computada nesta condenação, cabe extinção pelo cumprimento." % (rs.dias_para_pena(l.get("ppe_detracao_dias") or 0), l.get("ppe_pena_processo") or l.get("pena")),
                               "CP, art. 42; LEP, arts. 66, II, e 111.", tipo="pena-cumprida-por-detracao", ref=rot))
        if l.get("ppe_cor") == "vermelho":
            itens.append(_item("alerta", "%s: prescrição da pretensão executória aparente (%s)" % (rot, l.get("ppe_previsao")), l.get("ppe_resumo") or l.get("ppe_status", ""), "CP, arts. 110, 112, 113, 117, V, e 119; STF Tema 788.", tipo="prescricao-da-pretensao-executoria-aparente", ref=rot))
        elif (l.get("ppe_status") or "").startswith("A VERIFICAR"):
            itens.append(_item("verificar", "%s: prescrição executória a verificar - saldo na evasão depende da imputação do cumprimento" % rot,
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
        itens.append(_item("info", "Pena de multa cominada: extinção cabível se comprovada a impossibilidade de pagamento",
                           "Multa pendente: a extinção da punibilidade exige prova da impossibilidade de pagamento, ainda que parcelado (STF ADI 7.032, vinculante; STJ Tema 931). "
                           "Instruir com elementos concretos (declaração de hipossuficiência, ausência de bens, remuneração do trabalho prisional): a mera assistência pela Defensoria "
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
    elif r.get("falta_12m") == "A APURAR" and not any(not fi["decisao"] for fi in rs.faltas_editaveis(incidentes, eventos)):
        itens.append(_item("verificar", "Indício de falta nos últimos 12 meses", r.get("falta_12m_detalhe", ""), "Reflexo em LC (CP, art. 83, III, b), indulto (art. 6º dos decretos) e progressão (LEP, art. 112, §§ 6º e 7º).", tipo="indicio-de-falta-nos-ultimos-12-meses"))

    # ---------------- 6. eventos / detração ----------------
    periodos = rs.periodos_custodia(eventos)
    if not periodos and (cumprida or 0) > 0:
        itens.append(_item("verificar", "Pena cumprida sem evento de prisão no RSPE", "O relatório indica %s cumpridos, mas não lista eventos de início de cumprimento." % rs.dias_para_pena(cumprida), "Conferir a guia e a detração (CP, art. 42).", tipo="pena-cumprida-sem-evento-de-prisao-no-rspe"))
    import rspe_view as _rv2
    if _rv2.nao_iniciou(r):
        itens.append(_item("info", "Não iniciou o cumprimento da pena", "O RSPE não registra início de cumprimento definitivo (só prisão provisória encerrada, ou nenhuma). "
                           "A prescrição executória corre pela pena integral (menos a detração) desde o trânsito.", "CP, arts. 112, I, e 113.", tipo="nao-iniciou-o-cumprimento-da-pena"))
    elif "INTERROMPIDA" in (r.get("situacao_cumprimento") or ""):
        itens.append(_item("info", "Cumprimento interrompido (último evento é interrupção)", "Verificar se há prisão posterior não lançada ou se o apenado está foragido/em liberdade; a prescrição executória corre pela pena restante.", "CP, arts. 112, II, e 113.", tipo="cumprimento-interrompido-ultimo-evento-e-interru"))

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
