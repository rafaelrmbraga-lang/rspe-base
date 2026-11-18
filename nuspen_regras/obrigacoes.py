"""Extracao de obrigacoes por REGRAS EXPLICITAS (ADR-011, ADR-013): so sugere, sempre com fonte.

Regras nomeadas e versionadas (VERSAO). Entram: determinacao ("determino", "reitere-se" e
"reitero", "encaminha-se"/"encaminhe-se", "providencie-se", "oficie-se"), solicitacao
("solicita-se", "solicito", com itens numerados) e recomendacao ("Recomendacao:", "recomendo",
"recomenda-se"). Ficam de fora, de proposito: possibilidade ("podera"), sugestao ("sugere-se"),
negacao, discurso reportado ("determinou"), fato ja cumprido ("providenciou-se"), pedido de
prazo de outro orgao e afirmacao de cumprimento ("foi prestado atendimento"): resposta recebida
NAO e cumprimento. Obrigacao implicita ("devera a direcao providenciar") ainda NAO e extraida.
Destinatario e prazo so saem do texto; nada e inferido por semelhanca de nome; o prazo nunca
tem vencimento calculado (a contagem fica nao definida, ADR-012).
Os padroes sao [A testar] fora dos documentos ficticios; v2 incorpora formas observadas nas
amostras anonimizadas (docs/17), sempre reproduzidas em testes por frases inventadas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

VERSAO = "regras-obrigacoes-v1"  # conjunto de regras 1.1 (docs/09, secao O); prefixo mantido

# tipo documental (docs/14) -> origem da obrigacao (docs/03)
_ORIGEM = {
    "A1": "despacho",
    "A2": "despacho",
    "A3": "despacho",
    "A6": "decisao",
    "B1": "solicitacao_externa",
    "C2": "relatorio",
}
_REGRAS_POR_TIPO = {
    "A1": {
        "determino",
        "reitere-se",
        "solicita-se",
        "solicito",
        "providencie-se",
        "oficie-se",
        "encaminhe-se",
        "recomendo",
    },
    "A2": {"encaminha-se", "encaminhe-se", "solicita-se", "solicito", "providencie-se"},
    "A3": {"recomendo"},
    "A6": {"solicita-se", "solicito", "reitere-se"},
    "B1": {"solicita-se", "solicito"},
    "C2": {"recomendacao", "recomendo"},
}

_SENTENCA = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú(])")
_URGENCIA = re.compile(r"\b(?:imediat\w+|com\s+urg[êe]ncia|urgente|o\s+quanto\s+antes)\b", re.I)
_PRAZO_SEGUINTE = re.compile(r"^Fica\s+(?:estipulado|fixado)\s+(?:o\s+)?prazo", re.I)
_NEGACAO = re.compile(r"\bn[ãa]o\s+(?:determino|solicito|recomendo|requisito)\b", re.I)
_DESTINATARIO_OFICIO = re.compile(r"of[ií]cio\s+(?:à|ao|aos|às)\s+([^,.;]+)", re.I)
_LINHA_DESTINATARIO = re.compile(r"^(?:À|Ao|Aos|Às)\s+(.+?)\.?$")
_ITENS = re.compile(r"\(\d+\)\s*(.+?)(?=;\s*\(\d+\)|$)")

# ---------------------------------------------------------------- prazo expresso
_UNIDADES = r"(?:dias?\s+[uú]teis|dias?\s+corridos|dias?|horas?|mes(?:es)?)"
_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
    "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15, "dezesseis": 16,
    "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30,
    "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
    "noventa": 90, "cem": 100,
}  # fmt: skip
_PALAVRA_NUM = "|".join(sorted(_EXTENSO, key=len, reverse=True))
_NUMERO = rf"(?P<n>\d+|(?:{_PALAVRA_NUM})(?:\s+e\s+(?:{_PALAVRA_NUM}))?)"
_ENTRE_PARENTESES = r"(?:\s*\([^)]+\))?"
_PRAZOS = [
    re.compile(
        rf"prazo\s+de\s+(?:at[ée]\s+)?{_NUMERO}{_ENTRE_PARENTESES}\s*(?P<u>{_UNIDADES})\b", re.I
    ),
    re.compile(
        rf"\b(?:em|dentro\s+de|no\s+prazo\s+de)\s+(?:at[ée]\s+)?{_NUMERO}{_ENTRE_PARENTESES}"
        rf"\s*(?P<u>{_UNIDADES})\b",
        re.I,
    ),
]


@dataclass(frozen=True)
class PrazoExpresso:
    """Prazo lido do texto. Sem vencimento: a contagem nao e presumida (ADR-012)."""

    quantidade: int
    unidade: str
    trecho: str


def _valor(numero: str) -> int:
    numero = numero.lower().strip()
    if numero.isdigit():
        return int(numero)
    return sum(_EXTENSO[p] for p in re.split(r"\s+e\s+", numero))


def _unidade(texto: str) -> str:
    texto = " ".join(texto.lower().replace("úteis", "úteis").replace("uteis", "úteis").split())
    if texto.startswith("dia"):
        return (
            "dias úteis" if "úteis" in texto else "dias corridos" if "corridos" in texto else "dias"
        )
    if texto.startswith("hora"):
        return "horas"
    return "meses"


def extrair_prazo_do_texto(texto: str) -> PrazoExpresso | None:
    """Primeiro prazo expresso ('prazo de N dias', 'em 10 dias', 'quarenta e oito horas'...)."""
    texto = " ".join(texto.split())
    for padrao in _PRAZOS:
        achado = padrao.search(texto)
        if achado:
            return PrazoExpresso(_valor(achado["n"]), _unidade(achado["u"]), achado.group(0))
    return None


@dataclass(frozen=True)
class CandidataObrigacao:
    frase: str  # frase de origem: vira o trecho da Fonte
    objeto: str
    tipo: str  # TipoObrigacao
    origem: str  # OrigemObrigacao
    destinatario: str
    regra: str
    prazo_quantidade: int | None = None
    prazo_unidade: str = ""
    prazo_frase: str = ""  # frase onde o prazo foi lido (Fonte do prazo)
    finalidade: str = "outra"
    prazo_sem_numero: bool = False  # "com urgencia", "imediato": nao e prazo expresso


def _sentencas(texto: str) -> list[str]:
    return [s.strip() for s in _SENTENCA.split(" ".join(texto.split())) if s.strip()]


def _prazo(frase: str, seguinte: str | None) -> tuple[int | None, str, str, str]:
    """Prazo expresso na propria frase ou na seguinte ('Fica estipulado prazo de ...')."""
    achado = extrair_prazo_do_texto(frase)
    origem = frase
    if achado is None and seguinte and _PRAZO_SEGUINTE.match(seguinte):
        achado = extrair_prazo_do_texto(seguinte)
        origem = seguinte
    if achado is None:
        return None, "", "", "outra"
    finalidade = "resposta" if re.search(r"\bresposta\b", origem, re.I) else "outra"
    return achado.quantidade, achado.unidade, origem, finalidade


_CORTE_PRAZO = re.compile(
    r",\s*(?:com|no)\s+(?:novo\s+)?prazo"
    rf"|,\s*(?:em|dentro\s+de)\s+(?:at[ée]\s+)?(?:\d+|{_PALAVRA_NUM})\b"
    r"|\.$",
    re.I,
)


def _objeto(resto: str) -> str:
    return _CORTE_PRAZO.split(resto)[0].strip().rstrip(".").strip()


def _tipo_da_determinacao(resto: str) -> str:
    texto = resto.lower()
    if "ofício" in texto or "oficio" in texto:
        return "expedir_oficio"
    if "relatório" in texto or "relatorio" in texto:
        return "elaborar_relatorio"
    return "outro"


_DEST_COM_OBJETO = re.compile(
    r"^(?:à|ao|aos|às)\s+(?P<d>.+?)\s+(?=(?:a|o|as|os|que|para)\s)(?P<o>.+)$", re.I
)
_DEST_ATE_FIM = re.compile(
    r"^(?:à|ao|aos|às)\s+(?P<d>[^,.;]+?)(?=\s+(?:para|solicitando|requisitando)\b|[,.;]|$)", re.I
)

# (nome da regra, regex da forma, tipo da obrigacao)
_IMPERATIVOS = [
    ("providencie-se", re.compile(r"\bProvidencie-se\b\s*(?P<resto>.*)"), "providencia_material"),
    ("oficie-se", re.compile(r"\bOficie-se\b\s*(?P<resto>.*)"), "expedir_oficio"),
    ("encaminhe-se", re.compile(r"\bEncaminhe-se\b\s*(?P<resto>.*)"), "providencia_material"),
]


def _recomendacao(frase: str) -> str | None:
    achado = re.search(r"\bRecomenda[çc][ãa]o:\s*(?P<o>.+?)\.?$", frase)
    if achado:
        return achado["o"].strip()
    achado = re.search(r"\b(?:Recomendo|Recomenda-se)\b\s+(?P<o>.+?)\.?$", frase, re.I)
    return achado["o"].strip() if achado else None


def extrair_obrigacoes(texto: str, tipo_documental: str) -> list[CandidataObrigacao]:
    """Candidatas a obrigacao de um texto. Tipo documental sem regra: nada e extraido."""
    permitidas = _REGRAS_POR_TIPO.get(tipo_documental)
    if not permitidas:
        return []
    origem = _ORIGEM[tipo_documental]
    frases = _sentencas(texto)
    destinatario_do_oficio = ""
    if tipo_documental == "A6":
        for frase in frases:
            achado = _LINHA_DESTINATARIO.match(frase)
            if achado:
                destinatario_do_oficio = achado.group(1).strip()
                break
    candidatas: list[CandidataObrigacao] = []
    for indice, frase in enumerate(frases):
        if _NEGACAO.search(frase):
            continue
        seguinte = frases[indice + 1] if indice + 1 < len(frases) else None
        qtd, unidade, frase_prazo, finalidade = _prazo(frase, seguinte)
        sem_numero = qtd is None and bool(_URGENCIA.search(frase))
        base = {
            "frase": frase,
            "origem": origem,
            "prazo_quantidade": qtd,
            "prazo_unidade": unidade,
            "prazo_frase": frase_prazo,
            "finalidade": finalidade,
            "prazo_sem_numero": sem_numero,
        }
        sem_prazo = {
            **base,
            "prazo_sem_numero": False,
            "prazo_quantidade": None,
            "prazo_unidade": "",
            "prazo_frase": "",
        }

        if permitidas & {"recomendacao", "recomendo"}:
            objeto = _recomendacao(frase)
            if objeto:
                candidatas.append(
                    CandidataObrigacao(
                        objeto=objeto,
                        tipo="outro",
                        destinatario="",
                        regra="recomendacao",
                        **{**sem_prazo, "origem": "recomendacao"},
                    )
                )
                continue
            if "recomendacao" in permitidas:
                continue

        achado = re.search(r"\bdetermino\b\s*(?P<resto>.*)", frase, re.I)
        if achado and "determino" in permitidas:
            resto = _objeto(achado["resto"])
            dest = _DESTINATARIO_OFICIO.search(frase)
            candidatas.append(
                CandidataObrigacao(
                    objeto=resto,
                    tipo=_tipo_da_determinacao(resto),
                    destinatario=dest.group(1).strip() if dest else "",
                    regra="determino",
                    **base,
                )
            )
            continue

        achado = re.search(r"\b(?:Reitere-se|Reitero)\b\s*(?P<resto>.*)", frase)
        if achado and "reitere-se" in permitidas:
            candidatas.append(
                CandidataObrigacao(
                    objeto=f"reiterar {_objeto(achado['resto'])}",
                    tipo="expedir_oficio",
                    destinatario="",
                    regra="reitere-se",
                    **base,
                )
            )
            continue

        achado = re.search(r"\bencaminha-se\b\s*(?P<resto>.*)", frase)
        if achado and "encaminha-se" in permitidas:
            candidatas.append(
                CandidataObrigacao(
                    objeto=f"encaminhar {_objeto(achado['resto'])}",
                    tipo="providencia_material",
                    destinatario="",
                    regra="encaminha-se",
                    **base,
                )
            )
            continue

        casou = False
        for nome, rx, tipo in _IMPERATIVOS:
            achado = rx.search(frase)
            if achado and nome in permitidas:
                resto = _objeto(achado["resto"])
                dest = _DEST_ATE_FIM.match(resto)
                candidatas.append(
                    CandidataObrigacao(
                        objeto=resto,
                        tipo=tipo,
                        destinatario=dest["d"].strip() if dest else "",
                        regra=nome,
                        **base,
                    )
                )
                casou = True
                break
        if casou:
            continue

        achado = re.search(r"\bSolicita-se\b[:\s]*(?P<resto>.*)", frase)
        regra = "solicita-se"
        if not achado:
            achado = re.search(r"\b(?:Solicito|Requisito)\b[:\s]*(?P<resto>.*)", frase)
            regra = "solicito"
        if achado and regra in permitidas:
            resto = achado["resto"].strip().rstrip(".").strip()
            if re.match(r"o\s+prazo|prorroga", resto, re.I):
                continue  # pedido de prazo de outro orgao: nao e obrigacao
            itens = _ITENS.findall(resto)
            if itens:
                candidatas.extend(
                    CandidataObrigacao(
                        objeto=item.strip().rstrip(".").strip(),
                        tipo="responder",
                        destinatario=destinatario_do_oficio,
                        regra=regra,
                        **base,
                    )
                    for item in itens
                )
                continue
            if "devolução" in resto.lower() or "devolucao" in resto.lower():
                tipo = "retornar_solicitante"
            elif tipo_documental == "A6":
                tipo = "responder"
            elif tipo_documental == "B1":
                tipo = "providencia_material"
            else:
                tipo = "outro"
            destinatario = destinatario_do_oficio
            objeto = _objeto(resto)
            com_dest = _DEST_COM_OBJETO.match(objeto) if regra == "solicito" else None
            if com_dest:
                destinatario, objeto = com_dest["d"].strip(), com_dest["o"].strip()
            candidatas.append(
                CandidataObrigacao(
                    objeto=objeto,
                    tipo=tipo,
                    destinatario=destinatario,
                    regra=regra,
                    **base,
                )
            )
    return candidatas


# ------------------------------------------------- indicios de resposta (nao e cumprimento)

_RESPOSTA_A_OFICIO = re.compile(r"resposta\s+ao\s+of[ií]cio(?:\s+n[ºo°])?\s*(?P<id>\d{6,8})", re.I)
_ATENDIMENTO_AFIRMADO = re.compile(
    r"foi\s+prestado\s+atendimento|conforme\s+relat[óo]rio\s+anexo", re.I
)


@dataclass(frozen=True)
class IndicioResposta:
    """Indicio de que houve RESPOSTA. Nao e cumprimento material (RF50 x RF51)."""

    frase: str
    oficio: str  # ID do oficio citado, ou "" se o texto nao cita
    descricao: str


def extrair_indicios_resposta(texto: str, tipo_documental: str) -> list[IndicioResposta]:
    """Certidao/termo que citam resposta a oficio; manifestacao que afirma atendimento."""
    indicios: list[IndicioResposta] = []
    for frase in _sentencas(texto):
        if tipo_documental in {"A4", "A5"}:
            achado = _RESPOSTA_A_OFICIO.search(frase)
            if achado:
                nome = "certidão" if tipo_documental == "A4" else "termo de juntada"
                indicios.append(
                    IndicioResposta(
                        frase=frase,
                        oficio=achado["id"],
                        descricao=f"Indício de resposta ao ofício {achado['id']} ({nome})",
                    )
                )
        elif tipo_documental == "A3" and _ATENDIMENTO_AFIRMADO.search(frase):
            indicios.append(
                IndicioResposta(
                    frase=frase,
                    oficio="",
                    descricao=(
                        "Indício de resposta: a manifestação afirma atendimento "
                        "(comprovação em outro documento, não verificada)"
                    ),
                )
            )
    return indicios


# ------------------------------------------------- sinalizacoes (nao viram obrigacao)


@dataclass(frozen=True)
class Sinalizacao:
    """Frase que a pessoa deve olhar, mas que NAO foi extraida como obrigacao (conservador)."""

    frase: str
    tipo: str  # "encaminhe-se-em-oficio" | "obrigacao-implicita"
    descricao: str


_IMPLICITA = re.compile(r"\bdever(?:á|a|ão|ao)\b", re.I)
_TIPOS_COM_REGRA = {"A1", "A2", "A6", "B1", "C2"}


def extrair_sinalizacoes(texto: str, tipo_documental: str) -> list[Sinalizacao]:
    if tipo_documental not in _TIPOS_COM_REGRA:
        return []
    saida = []
    for frase in _sentencas(texto):
        if tipo_documental == "A6" and re.search(r"\bEncaminh(?:e-se|a-se)\b", frase):
            saida.append(
                Sinalizacao(
                    frase,
                    "encaminhe-se-em-oficio",
                    "'encaminhe-se' em ofício expedido (não extraído como obrigação)",
                )
            )
        elif _IMPLICITA.search(frase):
            saida.append(
                Sinalizacao(
                    frase,
                    "obrigacao-implicita",
                    "possível obrigação implícita (não extraída como obrigação)",
                )
            )
    return saida
