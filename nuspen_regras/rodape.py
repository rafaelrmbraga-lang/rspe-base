"""Leitura de rodape, numero de processo, assinatura e prazo em texto de PDF exportado do SEI.

Os padroes sao os ilustrativos de docs/14 (secao 2), todos [A testar]. Nada aqui calcula
vencimento de prazo: a regra de contagem nao esta no texto e nao pode ser presumida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Padrao observado nas amostras: o rodape pode vir depois de texto do emissor na mesma linha ou
# repetido na linha (vale a ultima ocorrencia); o rotulo nunca contem parenteses.
_RODAPE = re.compile(
    r"(?P<rotulo>[^()\n]{1,120}?)\s*\(?(?<!\d)(?P<id>\d{6,8})\)?\s+SEI\s+(?P<proc>\S+)"
    r"\s*/\s*pg\.\s*(?P<pg>\d+)(?!\d)"
)
_RODAPE_SO_SEI = re.compile(r"^\s*SEI\s+(?P<proc>\S+)\s*/\s*pg\.\s*(?P<pg>\d+)\s*$")
_FIM_COM_ID = re.compile(r"^\s*(?P<rotulo>[^()\n]{1,120}?)\s*\((?P<id>\d{6,8})\)\s*$")
_PROCESSO_ATUAL = re.compile(r"(\d{2})[/.](\d{6})[/.](\d{4})")
_PROCESSO_ANTIGO = re.compile(r"22\.0\.\d{9}-\d")
_PROCESSO_NO_TEXTO = re.compile(r"(?<![\d/.])(?:\d{2}[/.]\d{6}[/.]\d{4}|22\.0\.\d{9}-\d)(?!\d)")
_ASSINATURA = re.compile(
    r"(?:Documento\s+)?assinado\s+eletronicamente\s+por\s+(?P<nome>.+?),\s+(?P<cargo>.+?),\s+"
    r"em\s+(?P<data>\d{2}/\d{2}/\d{4}),\s*às\s+(?P<hora>\d{2}:\d{2})",
    re.DOTALL,
)
_PRAZO = re.compile(
    r"prazo de\s+(?P<n>\d+)\s*\((?P<extenso>[^)]+)\)\s*(?P<unidade>dias?|horas?|meses?)"
)


@dataclass(frozen=True)
class Rodape:
    rotulo: str
    id_documento: str
    processo: str
    pagina: int


@dataclass(frozen=True)
class NumeroProcesso:
    original: str
    normalizado: str


@dataclass(frozen=True)
class Assinatura:
    nome: str
    cargo: str
    data: str
    hora: str


@dataclass(frozen=True)
class Prazo:
    """Prazo expresso no texto. Sem vencimento: a contagem nao e presumida."""

    numero: int
    extenso: str
    unidade: str
    trecho: str


def _limpar_rotulo(rotulo: str) -> str:
    """Tira o texto do emissor (depois de '|' ou de um e-mail) que antecede o rotulo."""
    rotulo = rotulo.split("|")[-1]
    partes = rotulo.split()
    com_arroba = [i for i, p in enumerate(partes) if "@" in p]
    if com_arroba:
        partes = partes[com_arroba[-1] + 1 :]
    return " ".join(partes).strip()


def ler_rodape(texto: str) -> Rodape | None:
    """Procura o rodape nas linhas da pagina, da ultima para a primeira.

    Aceita o rodape depois de texto na mesma linha, mais de um na linha (vale o ultimo) e o
    rodape quebrado em duas linhas (rotulo e id numa, 'SEI processo / pg. n' na seguinte).
    """
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    for indice in range(len(linhas) - 1, -1, -1):
        achados = list(_RODAPE.finditer(linhas[indice]))
        if achados:
            a = achados[-1]
            return Rodape(
                rotulo=_limpar_rotulo(a["rotulo"]),
                id_documento=a["id"],
                processo=a["proc"],
                pagina=int(a["pg"]),
            )
        so_sei = _RODAPE_SO_SEI.match(linhas[indice])
        if so_sei and indice > 0:
            anterior = _FIM_COM_ID.match(linhas[indice - 1])
            if anterior:
                return Rodape(
                    rotulo=anterior["rotulo"].strip(),
                    id_documento=anterior["id"],
                    processo=so_sei["proc"],
                    pagina=int(so_sei["pg"]),
                )
    return None


def normalizar_numero_processo(texto: str) -> str | None:
    """Chave unica: NN/NNNNNN/AAAA para os dois formatos atuais; formato antigo inalterado."""
    candidato = texto.strip()
    atual = _PROCESSO_ATUAL.fullmatch(candidato)
    if atual:
        return f"{atual[1]}/{atual[2]}/{atual[3]}"
    if _PROCESSO_ANTIGO.fullmatch(candidato):
        return candidato
    return None


def encontrar_numeros_processo(texto: str) -> list[NumeroProcesso]:
    """Numeros de processo no texto, com a forma original e a chave normalizada."""
    achados = []
    for achado in _PROCESSO_NO_TEXTO.finditer(texto):
        original = achado.group(0)
        normalizado = normalizar_numero_processo(original)
        if normalizado:
            achados.append(NumeroProcesso(original=original, normalizado=normalizado))
    return achados


def ler_assinatura(texto: str) -> Assinatura | None:
    """Carimbo de assinatura do SEI; nome e cargo podem quebrar linha."""
    achado = _ASSINATURA.search(texto)
    if not achado:
        return None
    return Assinatura(
        nome=" ".join(achado["nome"].split()),
        cargo=" ".join(achado["cargo"].split()),
        data=achado["data"],
        hora=achado["hora"],
    )


def extrair_prazo(texto: str) -> Prazo | None:
    """Primeiro prazo expresso 'prazo de N(extenso) dias'; nao calcula vencimento."""
    achado = _PRAZO.search(texto)
    if not achado:
        return None
    return Prazo(
        numero=int(achado["n"]),
        extenso=achado["extenso"].strip(),
        unidade=achado["unidade"],
        trecho=achado.group(0),
    )
