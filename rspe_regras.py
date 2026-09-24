# -*- coding: utf-8 -*-
"""
Base jurídica (base_juridica.json) e regras derivadas dela.
A cópia ao lado do executável tem prioridade sobre a embutida, para permitir atualização.
"""

import json
import os
import sys
from datetime import date
from fractions import Fraction

_BASE = None
_ORIGEM = ""


def _pasta_app():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _recurso(nome):
    return os.path.join(getattr(sys, "_MEIPASS", _pasta_app()), nome)


def carregar(forcar=False):
    global _BASE, _ORIGEM
    if _BASE is not None and not forcar:
        return _BASE
    candidatos = [os.path.join(_pasta_app(), "base_juridica.json"), _recurso("base_juridica.json")]
    for c in candidatos:
        try:
            with open(c, encoding="utf-8") as f:
                _BASE = json.load(f)
            _ORIGEM = c
            return _BASE
        except Exception:
            continue
    _BASE = {}
    _ORIGEM = "(não encontrada)"
    return _BASE


def origem():
    carregar()
    return _ORIGEM


def versao():
    return carregar().get("versao", "?")


def fr(txt):
    """'1/5' -> Fraction(1,5); '16%' -> Fraction(16,100); None -> None."""
    if txt is None:
        return None
    if isinstance(txt, (int, float)):
        return Fraction(txt).limit_denominator(1000)
    t = str(txt).strip()
    if t.endswith("%"):
        return Fraction(t[:-1].replace(",", ".")).limit_denominator(1000) / 100
    if "/" in t:
        a, b = t.split("/")
        return Fraction(int(a), int(b))
    return Fraction(t).limit_denominator(1000)


def d(txt):
    try:
        return date.fromisoformat(txt)
    except Exception:
        return None


# ---------------------------------------------------------------- prescrição
def _faixa_art109(pena_dias):
    tab = carregar().get("prescricao", {}).get("art109_tabela")
    a = pena_dias / 365.0
    if not tab:
        tab = [{"pena_maior_que_anos": 12, "prazo_anos": 20, "inciso": "I"}, {"pena_maior_que_anos": 8, "prazo_anos": 16, "inciso": "II"},
               {"pena_maior_que_anos": 4, "prazo_anos": 12, "inciso": "III"}, {"pena_maior_que_anos": 2, "prazo_anos": 8, "inciso": "IV"},
               {"pena_maior_ou_igual_anos": 1, "prazo_anos": 4, "inciso": "V"},
               {"pena_menor_que_anos": 1, "prazo_anos": 3, "inciso": "VI", "prazo_anos_fato_ate_2010_05_05": 2}]
    for faixa in tab:
        if "pena_maior_que_anos" in faixa and a > faixa["pena_maior_que_anos"]:
            return faixa
        if "pena_maior_ou_igual_anos" in faixa and a >= faixa["pena_maior_ou_igual_anos"]:
            return faixa
        if "pena_menor_que_anos" in faixa and a < faixa["pena_menor_que_anos"]:
            return faixa
    return {"prazo_anos": 3, "inciso": "VI", "prazo_anos_fato_ate_2010_05_05": 2}


def prazo_art109_anos(pena_dias, data_fato=None):
    """Prazo do art. 109 do CP pela pena. data_fato anterior à Lei 12.234/2010 (vigência em 06/05/2010): inciso VI
    na redação da Lei 7.209/1984 (2 anos), porque a lei mais gravosa não retroage (CF, art. 5º, XL)."""
    f = _faixa_art109(pena_dias)
    antigo = f.get("prazo_anos_fato_ate_2010_05_05")
    if antigo is not None and data_fato and data_fato < (data_lei_12234() or date(2010, 5, 6)):
        return antigo
    return f["prazo_anos"]


def inciso_art109(pena_dias):
    """Inciso do art. 109 do CP que corresponde à pena ('V')."""
    return _faixa_art109(pena_dias).get("inciso", "")


def art115():
    p = carregar().get("prescricao", {}).get("art115_metade", {})
    return (p.get("menor_de_anos_no_fato", 21), p.get("maior_de_anos_na_sentenca", 70), set(p.get("artigos_violencia_sexual", [])))


def data_lei_15160():
    return d(carregar().get("prescricao", {}).get("art115_metade", {}).get("lei_15160_2025_vigencia", "2025-07-04"))


def data_lei_12234():
    return d(carregar().get("prescricao", {}).get("lei_12234_2010_vigencia", "2010-05-06"))


def data_tema_788():
    return d(carregar().get("prescricao", {}).get("tema_788_modulacao_data", "2020-11-12"))


def acrescimo_reincidencia():
    return fr(carregar().get("prescricao", {}).get("art110_reincidencia_acrescimo", "1/3"))


# ---------------------------------------------------------------- progressão
def regime_progressao(data_fato):
    """Janela de vigência do art. 112 aplicável à data do fato (tempus regit actum)."""
    jan = carregar().get("progressao", {}).get("regimes_vigencia", [])
    if not data_fato:
        return None
    for j in jan:
        de, ate = d(j.get("de", "0001-01-01")), d(j.get("ate", "9999-12-31"))
        if (de or date.min) <= data_fato <= (ate or date.max):
            return j
    return None


ESPECIAIS = {  # hipóteses próprias do art. 112 (chave na janela de vigência -> descrição)
    "feminicidio_primario": "feminicídio, primário (LEP, art. 112, VI-A de 10/10/2024 a 24/03/2026; VI, d, desde 25/03/2026)",
    "milicia": "constituição de milícia privada (LEP, art. 112, VI, c)",
    "comando_orcrim": "comando de organização criminosa (LEP, art. 112, VI, b)",
}


def fracao_progressao_esperada(data_fato, hediondo, morte, vga, reincidente, reinc_especifico=None, especial=None):
    """Devolve (fração, rótulo, observações) esperadas pela lei da data do fato, com as teses do STJ/STF.
    reinc_especifico: None = desconhecido. especial: chave de ESPECIAIS (usada só se a janela a prevê)."""
    j = regime_progressao(data_fato)
    if not j:
        return None, "", ["sem data do fato: fração não aferida"]
    obs = []
    if especial and j.get(especial) and not (especial == "feminicidio_primario" and reincidente):
        valor = j.get(especial)
        if especial in ("comando_orcrim", "milicia"):
            # hipótese que se soma às demais: vale o percentual mais alto entre ela e o do crime (ex.: reincidente em hediondo)
            f_base, rot_base, obs_base = fracao_progressao_esperada(data_fato, hediondo, morte, vga, reincidente, reinc_especifico)
            if f_base is not None and f_base > fr(valor):
                return f_base, rot_base, obs_base + ["%s: %s, menor que o do crime" % (ESPECIAIS[especial], valor)]
        obs.append(ESPECIAIS.get(especial, especial))
        return fr(valor), "%s (%s)" % (valor, j.get("lei", "")), obs
    if hediondo:
        if morte:
            chave = "hediondo_morte_reincidente" if reincidente else "hediondo_morte_primario"
            if reincidente and reinc_especifico is False and j.get("hediondo_morte_reincidente_generico"):
                chave = "hediondo_morte_reincidente_generico"
                obs.append("reincidente genérico em hediondo com morte: STJ Tema 1196")
            elif reincidente and reinc_especifico is None and j.get("hediondo_morte_reincidente_generico"):
                obs.append("se a reincidência for genérica (não em hediondo), aplica-se %s (STJ Tema 1196)" % j["hediondo_morte_reincidente_generico"])
        else:
            chave = "hediondo_reincidente" if reincidente else "hediondo_primario"
            if reincidente and reinc_especifico is False and j.get("hediondo_reincidente_generico"):
                chave = "hediondo_reincidente_generico"
                obs.append("reincidente genérico em hediondo: STJ Tema 1084 / STF Tema 1169" + (
                    " (analogia na redação da Lei 15.358/2026, sem precedente específico - conferir)" if (d(j.get("de", "")) or date.min) >= date(2026, 3, 25) else ""))
            elif reincidente and reinc_especifico is None and j.get("hediondo_reincidente_generico"):
                obs.append("se a reincidência for genérica (não em hediondo), aplica-se %s (STJ Tema 1084; STF Tema 1169%s)" % (
                    j["hediondo_reincidente_generico"], "; por analogia na redação da Lei 15.358/2026" if (d(j.get("de", "")) or date.min) >= date(2026, 3, 25) else ""))
    elif vga:
        chave = "vga_reincidente" if reincidente else "vga_primario"
        # a Auditoria só pede reinc_especifico=False para hediondos: o RSPE não diz se a condenação anterior teve violência
        if reincidente and reinc_especifico is False and j.get("vga_reincidente_generico"):
            chave = "vga_reincidente_generico"
            obs.append("reincidente genérico em crime com VGA: analogia in bonam partem (STJ Tema 1084)")
    else:
        chave = "comum_reincidente" if reincidente else "comum"
    valor = j.get(chave)
    return fr(valor), "%s (%s)" % (valor, j.get("lei", "")), obs


def fracao_mais_benefica(data_fato, hediondo, morte, vga, reincidente, especial=None):
    """Considera retroatividade da lei mais benéfica (Tema 1354): menor fração entre a da data do fato e as posteriores."""
    jan = carregar().get("progressao", {}).get("regimes_vigencia", [])
    if not data_fato:
        return None, "", []
    cands = []
    for j in jan:
        ate = d(j.get("ate", "9999-12-31")) or date.max
        if ate < data_fato:
            continue
        f, rot, _ = _fracao_em(j, hediondo, morte, vga, reincidente, especial)
        if f is not None:
            cands.append((f, rot, j.get("lei", "")))
    if not cands:
        return None, "", []
    f_fato, rot_fato, obs = fracao_progressao_esperada(data_fato, hediondo, morte, vga, reincidente, especial=especial)
    melhor = min(cands, key=lambda x: x[0])
    if f_fato is not None and melhor[0] < f_fato:
        obs.append("lei posterior mais benéfica retroage: %s" % melhor[1])
        return melhor[0], melhor[1], obs
    return f_fato, rot_fato, obs


def _fracao_em(j, hediondo, morte, vga, reincidente, especial=None):
    if especial and j.get(especial) and not (especial == "feminicidio_primario" and reincidente):
        v = j.get(especial)
        if especial in ("comando_orcrim", "milicia"):
            fb, rb, _ = _fracao_em(j, hediondo, morte, vga, reincidente)
            if fb is not None and fb > fr(v):
                return fb, rb, []
        return fr(v), "%s (%s)" % (v, j.get("lei", "")), []
    if hediondo:
        chave = ("hediondo_morte_" if morte else "hediondo_") + ("reincidente" if reincidente else "primario")
    elif vga:
        chave = "vga_reincidente" if reincidente else "vga_primario"
    else:
        chave = "comum_reincidente" if reincidente else "comum"
    v = j.get(chave)
    return fr(v), "%s (%s)" % (v, j.get("lei", "")), []


# ---------------------------------------------------------------- livramento
def fracao_livramento_esperada(hediondo, reincidente, trafico=False, trafico_pessoas=False):
    """CP, art. 83, V: mais de 2/3 nos crimes hediondos, tortura, tráfico de drogas, tráfico de pessoas e terrorismo
    (tráfico de pessoas incluído pela Lei 13.344/2016, a mesma que criou o art. 149-A do CP)."""
    l = carregar().get("livramento", {})
    if hediondo or trafico or trafico_pessoas:
        return fr(l.get("hediondo", "2/3")), "2/3 (art. 83, V, CP%s)" % (
            "; art. 44, p. ú., Lei 11.343/06" if trafico else " - tráfico de pessoas" if (trafico_pessoas and not hediondo) else "")
    if reincidente:
        return fr(l.get("comum_reincidente", "1/2")), "1/2 (art. 83, II, CP)"
    return fr(l.get("comum_primario", "1/3")), "1/3 (art. 83, I, CP)"


# ---------------------------------------------------------------- hediondos / VGA
def hediondos():
    return carregar().get("hediondos", {})


def vga_esperado(artigo):
    v = carregar().get("vga_esperado", {})
    if artigo in v.get("S", []):
        return "S"
    if artigo in v.get("N", []):
        return "N"
    return None


def patrimonio():
    p = carregar().get("patrimonio_cp", {"de": 155, "ate": 180})
    return set(str(a) for a in range(p["de"], p["ate"] + 1))


def patrimonio_faixa():
    """(de, ate, incluir_sufixos): Título II da Parte Especial do CP; com sufixos, 168-A, 171-A, 180-A etc. entram."""
    p = carregar().get("patrimonio_cp", {"de": 155, "ate": 180})
    return int(p.get("de", 155)), int(p.get("ate", 180)), bool(p.get("incluir_sufixos", True))


def decretos():
    return carregar().get("decretos_indulto", {})


def jurisprudencia():
    return carregar().get("jurisprudencia", [])
