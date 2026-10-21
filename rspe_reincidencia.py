# -*- coding: utf-8 -*-
"""
Reincidência pelas datas do próprio RSPE (e da ficha do SIAPEN), para a Auditoria, a progressão, o livramento e o indulto.

O SEEU só traz a marcação "Reincidente: S/N"; a lei (CP, arts. 63 e 64, I) depende de datas: há reincidência quando o novo
crime é cometido depois do trânsito em julgado de condenação anterior, salvo se entre a extinção (ou o cumprimento) da pena
anterior e o novo fato passaram mais de 5 anos. Quando o próprio documento resolve, o programa afirma; quando não resolve,
fica "a verificar":

- reincidente: condenação anterior do RSPE (outro processo, que gera reincidência) transitada antes do fato e não depurada;
  ou, como indício, pena de outro processo extinta antes do fato, há menos de 5 anos, registrada na ficha do SIAPEN (só existe
  pena extinta se houve condenação, e a extinção é posterior ao trânsito);
- não reincidente: fato cometido antes dos 18 anos ou poucos dias depois (não há tempo para condenação de adulto transitar
  antes dele - ato infracional não gera reincidência); tráfico privilegiado (Lei 11.343/06, art. 33, § 4º: a sentença
  reconheceu a primariedade), salvo condenação anterior transitada no próprio RSPE;
- indeterminado: nenhuma das hipóteses acima (a condenação anterior pode estar fora do RSPE). Ficam registrados os indícios:
  condenação anterior sem trânsito informado com sentença antes do fato e trânsito em data impossível (antes da sentença
  ou do fato daquele processo).
"""

import re
from datetime import date, timedelta

import rspe_scraper as rs

# dias depois dos 18 anos em que não cabe condenação de adulto transitada (prisão, denúncia, instrução, sentença e prazo de
# recurso levam mais que isso): fato até 18 anos + MARGEM_MAIORIDADE -> não reincidente
MARGEM_MAIORIDADE = 60


def porte_uso(c):
    """Porte de droga para consumo próprio: art. 28 da Lei 11.343/06 ou o antigo art. 16 da Lei 6.368/76."""
    lei, art = rs.num_lei(c.get("lei")), rs.num_art(c.get("artigo"))
    return (lei == "11343" and art == "28") or (lei == "6368" and art == "16")


def gera_reincidencia(o):
    """Condenação anterior que gera reincidência: não a contravenção seguida de crime (CP, art. 63; LCP, art. 7º) nem o porte
    para consumo próprio (art. 28 da Lei 11.343/06; STJ: não gera reincidência)."""
    return rs.num_lei(o.get("lei")) != "3688" and "CONTRAVEN" not in (o.get("lei") or "").upper() and not porte_uso(o)


def transito(c):
    return rs.to_date(c.get("transito_processo") or c.get("transito_mp") or "")


def _mais_anos(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def depurada(extincao, fato):
    """CP, art. 64, I: mais de 5 anos entre a extinção (ou o cumprimento) da pena anterior e o novo fato."""
    return bool(extincao and fato and fato > _mais_anos(extincao, 5))


def trafico_privilegiado(c):
    return rs.num_lei(c.get("lei")) == "11343" and rs.num_art(c.get("artigo")) == "33" and bool(
        re.match(r"\s*§\s*4", c.get("tipo_penal") or ""))


def crime_lei_drogas(o):
    """Condenação por crime da Lei de Drogas que gera a reincidência específica do art. 44, p. ú., da Lei 11.343/06 (STJ):
    arts. 33 a 37 da Lei 11.343/06 ou arts. 12 a 14 da Lei 6.368/76 (o porte para consumo próprio fica fora)."""
    lei, art = rs.num_lei(o.get("lei")), rs.num_art(o.get("artigo"))
    return (lei == "11343" and art in ("33", "34", "35", "36", "37")) or (lei == "6368" and art in ("12", "13", "14"))


def extincoes_ficha(f):
    """Penas de outros processos extintas, registradas na ficha do SIAPEN: [{processo, data (date), texto}].
    Reconhece "Destino: EXTINÇÃO DE PENA ... AUT. <processo>" (data do evento) e "PENA EXTINTA EM dd/mm/aaaa ... <processo>"."""
    out = []
    for e in (f or {}).get("eventos") or []:
        t = " ".join(str(e.get("texto") or "").split())
        u = rs._sem_acento(t).upper()
        if not re.search(r"EXTINCAO DE PENA|PENA EXTINTA|EXTINTA A PENA", u):
            continue
        if re.search(r"CONSELHO DISCIPLINAR|PADIC|PROCESSO DISCIPLINAR", u):
            continue
        procs = re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", t)
        if not procs:
            continue
        m = re.search(r"PENA EXTINTA(?: [A-Z ]{0,40}?,)? EM (\d{1,2}/\d{1,2}/\d{4})", u)
        d = rs.to_date(m.group(1)) if m else None
        if not d:
            dd = str(e.get("data") or "").replace(".", "/")
            d = rs.to_date(dd)
        if d:
            out.append({"processo": procs[0], "data": d, "texto": t[:200]})
    # pena em cumprimento antes da extinção: o primeiro registro da ficha que cita o mesmo processo como execução de pena
    # (progressão ou regressão de regime, "para cumprimento de pena", regime fechado/semiaberto/aberto) - a condenação já
    # transitara nessa data, mesmo que a extinção seja posterior ao fato de outro crime
    for x in out:
        raiz = x["processo"][:15]
        ds = []
        for e in (f or {}).get("eventos") or []:
            t = " ".join(str(e.get("texto") or "").split())
            if raiz not in t:
                continue
            u = rs._sem_acento(t).upper()
            if re.search(r"EXTINCAO DE PENA|PENA EXTINTA|EXTINTA A PENA|PROVISORI|PREVENTIV|FLAGRANTE", u):
                continue
            if re.search(r"CUMPRIMENTO DE PENA|CUMPRIR (?:A )?PENA|PROGRESSAO DE REGIME|REGRESSAO DE REGIME|REGIME (?:FECHADO|SEMIABERTO|ABERTO)", u):
                d = rs.to_date(str(e.get("data") or "").replace(".", "/"))
                if d and d < x["data"]:
                    ds.append(d)
        if ds:
            x["cumprimento_desde"] = min(ds)
    return out


def idade_em(nasc, d):
    return d.year - nasc.year - ((d.month, d.day) < (nasc.month, nasc.day))


def reincidencia_pelas_datas(c, crimes, nasc=None, extincoes=None, processos_excluir=()):
    """Teste da reincidência (CP, arts. 63 e 64, I) do crime c pelas datas do RSPE e da ficha.

    c: crime do RSPE (dict do rspe_scraper: data_infracao, reincidente_comum/especifico, processo_criminal...).
    crimes: as condenações da pessoa (as deste RSPE e, se houver, as de outras execuções, com "_execucao").
    nasc: data de nascimento (date) ou None. extincoes: extincoes_ficha(ficha) ou None.
    processos_excluir: processos que não contam como condenação anterior (o da própria execução, por exemplo).

    Devolve dict:
      estado: "reincidente" | "nao_reincidente" | "indeterminado"
      fonte: "rspe" | "ficha" | "idade" | "privilegio" | "outra_execucao" | ""   (o que decidiu o estado)
      marcado: bool (o RSPE marca "Reincidente: S", comum ou específico)
      anteriores: condenações do RSPE transitadas antes do fato, não depuradas (geram a reincidência)
      outra_execucao: as mesmas, mas só de outra execução da pessoa ("_execucao")
      depuradas: condenações anteriores depuradas (art. 64, I)
      ficha: extinções da ficha antes do fato, há 5 anos ou menos [{processo, data, texto}]
      sem_transito: condenações anteriores sem trânsito informado, com sentença antes do fato (indício)
      transito_duvidoso: condenações com trânsito antes do fato, mas em data impossível (antes da sentença ou do fato delas)
      motivo: frase curta que explica o estado (para a tela)
    """
    fato = rs.to_date(c.get("data_infracao") or "")
    marc = c.get("reincidente_comum") == "S" or c.get("reincidente_especifico") == "S"
    R = {"estado": "indeterminado", "fonte": "", "marcado": marc, "anteriores": [], "outra_execucao": [], "depuradas": [],
         "ficha": [], "sem_transito": [], "transito_duvidoso": [], "motivo": ""}
    if not fato:
        R["motivo"] = "sem a data do fato não é possível aferir a reincidência"
        return R
    proc_c = c.get("processo_criminal") or ""
    for o in crimes:
        if o is c or not gera_reincidencia(o):
            continue
        po = o.get("processo_criminal") or ""
        if po and proc_c and rs.mesmo_processo(po, proc_c):
            continue
        t = transito(o)
        s_o, f_o = rs.to_date(o.get("data_sentenca") or ""), rs.to_date(o.get("data_infracao") or "")
        if t and t < fato:
            if (s_o and t < s_o) or (f_o and t < f_o):
                R["transito_duvidoso"].append(o)
                continue
            ext = rs.to_date(o.get("data_extincao") or "") if (o.get("extinto") or "").upper().startswith("S") else None
            if depurada(ext, fato):
                R["depuradas"].append(o)
            elif o.get("_execucao"):
                R["outra_execucao"].append(o)
            else:
                R["anteriores"].append(o)
        elif not t and s_o and s_o < fato and (not f_o or f_o < fato):
            R["sem_transito"].append(o)
    # a extinção da ficha pode citar o número da execução (não o da ação penal): o de outra execução já lida também decide pelas
    # datas e pelos crimes dela (ex.: execução só do art. 28 da Lei 11.343/06, que não gera reincidência)
    procs_rspe = ([x.get("processo_criminal") or "" for x in crimes] + [x.get("_execucao") or "" for x in crimes]
                  + [p for p in processos_excluir if p])
    for e in extincoes or []:
        if any(p and rs.mesmo_processo(p, e["processo"]) for p in procs_rspe):
            continue  # processo deste RSPE (ou de outra execução já lida): as datas do RSPE decidem
        if any(rs.mesmo_processo(x["processo"], e["processo"]) and x["data"] == e["data"] for x in R["ficha"]):
            continue  # (7.14.4) a mesma extinção lançada duas vezes na ficha: uma só no aviso
        if e["data"] < fato and not depurada(e["data"], fato):
            R["ficha"].append(e)
        elif e["data"] >= fato and ((rs.to_date(e["cumprimento_desde"]) if isinstance(e.get("cumprimento_desde"), str)
                                     else e.get("cumprimento_desde")) or date.max) < fato:
            # extinta depois do fato, mas a ficha a registra em cumprimento antes dele: a condenação já tinha transitado
            R["ficha"].append(e)
    menor = bool(nasc and fato < _mais_anos(nasc, 18) + timedelta(days=MARGEM_MAIORIDADE))
    if R["anteriores"]:
        R["estado"], R["fonte"] = "reincidente", "rspe"
        R["motivo"] = "condenação anterior transitada antes do fato (%s): %s" % (rs.fmt(fato), "; ".join(
            "proc. %s, trânsito em %s" % (o.get("processo_criminal") or "?", rs.fmt(transito(o))) for o in R["anteriores"][:4]))
    elif menor and not R["ficha"] and not R["outra_execucao"]:
        R["estado"], R["fonte"] = "nao_reincidente", "idade"
        _i = idade_em(nasc, fato)
        R["motivo"] = ("tinha %d anos no fato (%s; nascimento em %s): %s" % (
            _i, rs.fmt(fato), rs.fmt(nasc),
            "menor de 18 anos não tem condenação criminal anterior (ato infracional não gera reincidência)" if _i < 18 else
            "não houve tempo para uma condenação de adulto transitar em julgado antes do fato"))
    elif trafico_privilegiado(c) and not R["ficha"] and not R["outra_execucao"]:
        R["estado"], R["fonte"] = "nao_reincidente", "privilegio"
        R["motivo"] = ("tráfico privilegiado (Lei 11.343/06, art. 33, § 4º): a sentença reconheceu a primariedade, e nenhuma "
                       "condenação deste RSPE transitou antes do fato")
    elif R["ficha"]:
        R["estado"], R["fonte"] = "reincidente", "ficha"
        _cd = lambda e: rs.to_date(e["cumprimento_desde"]) if isinstance(e.get("cumprimento_desde"), str) else e.get("cumprimento_desde")
        if all(e["data"] < fato for e in R["ficha"]):
            R["motivo"] = "a ficha do SIAPEN registra pena de outro processo extinta antes do fato (%s), há menos de 5 anos: %s" % (
                rs.fmt(fato), "; ".join(dict.fromkeys("proc. %s, extinta em %s" % (e["processo"], rs.fmt(e["data"])) for e in R["ficha"][:3])))
        else:
            R["motivo"] = "a ficha do SIAPEN registra pena de outro processo em cumprimento antes do fato (%s): %s" % (
                rs.fmt(fato), "; ".join(dict.fromkeys(("proc. %s, extinta em %s" % (e["processo"], rs.fmt(e["data"]))) if e["data"] < fato else
                                        ("proc. %s, em cumprimento desde %s e extinta em %s, depois do fato" % (e["processo"], rs.fmt(_cd(e)), rs.fmt(e["data"])))
                                        for e in R["ficha"][:3])))
    elif R["outra_execucao"]:
        R["estado"], R["fonte"] = "reincidente", "outra_execucao"
        R["motivo"] = "condenação de outra execução da mesma pessoa transitada antes do fato (%s): %s" % (rs.fmt(fato), "; ".join(
            "proc. %s, trânsito em %s" % (o.get("processo_criminal") or "?", rs.fmt(transito(o))) for o in R["outra_execucao"][:4]))
    else:
        partes = []
        if R["sem_transito"]:
            partes.append("condenação anterior com sentença antes do fato e sem trânsito informado (%s)" % "; ".join(
                "proc. %s, sentença em %s" % (o.get("processo_criminal") or "?", o.get("data_sentenca")) for o in R["sem_transito"][:4]))
        if R["transito_duvidoso"]:
            partes.append("trânsito em data impossível (%s)" % "; ".join(
                "proc. %s, trânsito em %s" % (o.get("processo_criminal") or "?", rs.fmt(transito(o))) for o in R["transito_duvidoso"][:4]))
        R["motivo"] = ("; ".join(partes) + ": conferir a certidão de trânsito") if partes else \
            "nenhuma condenação deste RSPE transitou antes do fato; pode haver condenação fora dele (certidão de antecedentes)"
    return R


def reincidente_para_calculo(R):
    """Reincidência que a Auditoria usa nas frações: a demonstrada (RSPE ou ficha) ou a marcação do SEEU não desmentida pelas
    datas. A só de outra execução, sem marcação, não entra sozinha (a conferir)."""
    if R["estado"] == "nao_reincidente":
        return False
    if R["marcado"]:
        return True
    return R["estado"] == "reincidente" and R["fonte"] == "rspe"


def reincidencia_em_duvida(R):
    """Marcado reincidente sem base no documento (nem RSPE, nem ficha): as frações de reincidente ficam a verificar."""
    return R["marcado"] and R["estado"] == "indeterminado"
