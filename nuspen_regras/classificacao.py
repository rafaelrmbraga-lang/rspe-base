"""Classificacao SUGERIDA do tipo documental (docs/14, secoes 3, 4 e 6).

Os codigos do catalogo sao provisorios (docs/14, secao 4). A classificacao nunca e fato:
traz grau de confianca, conflito entre rotulo e titulo impresso e os sinais que a justificam,
e passa por validacao humana (ADR-014). Sem sinal reconhecido, nao inventa tipo.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from typing import TYPE_CHECKING

from nuspen_regras.rodape import ler_rodape

if TYPE_CHECKING:  # só tipos: a leitura de PDF do NUSPEN não vem para o APTO
    from nuspen.documentos.leitura import PaginaLida
    from nuspen.documentos.segmentacao import Segmento

LINHAS_DO_TITULO = 8  # o titulo costuma estar nas primeiras linhas da primeira pagina

NOMES = {
    "A1": "Despacho",
    "A2": "Encaminhamento",
    "A3": "Manifestação",
    "A4": "Certidão",
    "A5": "Termo (juntada, encerramento)",
    "A6": "Ofício expedido",
    "B1": "Ofício externo",
    "B2": "E-mail",
    "B3": "Protocolo / recibo",
    "B4": "Denúncia / ouvidoria",
    "B6": "Publicação oficial",
    "B8": "Termo de inspeção de outro órgão",
    "C1": "Formulário de inspeção respondido",
    "C2": "Relatório de inspeção",
    "C3": "Relatório de atendimento individual",
    "A7": "Decisão / requerimento / comunicação interna",
    "B5": "Carta do assistido",
    "B7": "Pauta / convite de reunião",
    "C6": "Anexo de dados",
    "C8": "Notícia / publicação em site",
    # PROPOSTOS a partir das amostras (docs/09, secao O): pendentes de aprovacao
    "B9": "Resposta (proposto)",
    "C9": "Relatório, subtipo a definir (proposto)",
}

# (padrao no texto sem acento e em maiusculas, codigo). A ORDEM importa: o mais especifico antes.
_POR_TITULO: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"TERMO DE INSPECAO"), "B8"),
    (re.compile(r"OFICIO EXTERNO"), "B1"),
    (re.compile(r"^OFICIO N", re.M), "A6"),
    (re.compile(r"PROTOCOLO DE ATENDIMENTO"), "B4"),
    (re.compile(r"PROTOCOLO (DE RECEBIMENTO|RECEBIMENTO|E-MAIL)"), "B3"),
    (re.compile(r"^DESPACHO\b", re.M), "A1"),
    (re.compile(r"^ENCAMINHAMENTO\b", re.M), "A2"),
    (re.compile(r"^MANIFESTACAO\b", re.M), "A3"),
    (re.compile(r"^CERTIDAO\b", re.M), "A4"),
    (re.compile(r"^TERMO\b", re.M), "A5"),
    (re.compile(r"FORMULARIO DE INSPECAO|EXIBIR RESULTADOS"), "C1"),
    (re.compile(r"RELATORIO DE ATENDIMENTO"), "C3"),
    (re.compile(r"^RESPOSTA\b", re.M), "B9"),
    (re.compile(r"^DECISAO\b", re.M), "A7"),
    (re.compile(r"RELATORIO DE INSPECAO"), "C2"),
    (re.compile(r"DIARIO OFICIAL ELETRONICO|^EDITAL\b|^PORTARIA\b", re.M), "B6"),
]
_EMAIL = re.compile(r"^DE:.*\n(?:.*\n)?PARA:", re.M)

# Rotulo livre do rodape (so pista): padrao no rotulo sem acento e em maiusculas.
_POR_ROTULO: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^DESPACHO"), "A1"),
    (re.compile(r"^ENCAMINHAMENTO"), "A2"),
    (re.compile(r"^MANIFESTACAO"), "A3"),
    (re.compile(r"^CERTIDAO"), "A4"),
    (re.compile(r"^TERMO"), "A5"),
    (re.compile(r"^OFICIO\b.*NUSPEN"), "A6"),
    (re.compile(r"^OFICIO\b"), "B1"),
    (re.compile(r"^E-?MAIL"), "B2"),
    (re.compile(r"^PROTOCOLO|^RECIBO"), "B3"),
    (re.compile(r"^FORMULARIO"), "C1"),
    (re.compile(r"^RELATORIO DE INSPECAO"), "C2"),
    (re.compile(r"^RELATORIO DE ATENDIMENTO"), "C3"),
    (re.compile(r"^DECISAO|^REQUERIMENTO|^COMUNICACAO"), "A7"),
    (re.compile(r"^DENUNCIA"), "B4"),
    (re.compile(r"^CARTA"), "B5"),
    (re.compile(r"^PORTARIA|^EDITAL|^DIARIO"), "B6"),
    (re.compile(r"^PAUTA|^CONVITE|^REUNIAO"), "B7"),
    (re.compile(r"^NOTICIA"), "C8"),
    (re.compile(r"^ANEXO"), "C6"),
    (re.compile(r"^RESPOSTA"), "B9"),
    (re.compile(r"^RELATORIO\b"), "C9"),
]


@dataclass(frozen=True)
class Classificacao:
    codigo: str | None
    nome: str | None
    confianca: str  # alta | media | baixa | nenhuma
    conflito: bool = False
    sinais: list[str] = field(default_factory=list)
    sugestao: bool = True  # sempre: so vira validada pela regra de validacao do tipo (ADR-014)


def _sem_acento_maiusculo(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).upper()


def _codigo_pelo_titulo(texto: str) -> tuple[str | None, str | None]:
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()][:LINHAS_DO_TITULO]
    cabeca = _sem_acento_maiusculo("\n".join(linhas))
    for padrao, codigo in _POR_TITULO:
        achado = padrao.search(cabeca)
        if achado:
            return codigo, achado.group(0).strip()
    if _EMAIL.search(cabeca):
        return "B2", "cabeçalho De/Para"
    return None, None


def _codigo_pelo_rotulo(rotulo: str | None) -> str | None:
    if not rotulo:
        return None
    normalizado = _sem_acento_maiusculo(rotulo.strip())
    for padrao, codigo in _POR_ROTULO:
        if padrao.search(normalizado):
            return codigo
    return None


def _sem_rodape(texto: str) -> str:
    """Tira a linha do rodape do SEI, para que o rotulo livre nao seja lido como titulo."""
    linhas = texto.splitlines()
    for indice in range(len(linhas) - 1, -1, -1):
        if linhas[indice].strip() and ler_rodape(linhas[indice]) is not None:
            del linhas[indice]
            break
    return chr(10).join(linhas)


def _codigos_compativeis(rotulo: str | None, por_rotulo: str | None) -> set[str]:
    """Codigos que o rotulo admite. 'Oficio <destinatario>' pode ser expedido (A6) ou externo (B1):
    nas amostras o rotulo de oficio expedido costuma nomear o destinatario."""
    if not rotulo or por_rotulo is None:
        return set()
    if por_rotulo in {"A6", "B1"}:
        return {"A6", "B1"}
    return {por_rotulo}


def classificar_texto(texto: str, rotulo: str | None) -> Classificacao:
    """Sugere o tipo a partir do titulo impresso (prevalece) e do rotulo do rodape (pista)."""
    por_titulo, trecho = _codigo_pelo_titulo(texto)
    por_rotulo = _codigo_pelo_rotulo(rotulo)
    sinais: list[str] = []
    if por_titulo:
        sinais.append(f"título impresso: «{trecho}»")
    if por_rotulo:
        sinais.append(f"rótulo do rodapé: «{rotulo}»")
    if por_titulo is None and por_rotulo is None:
        if rotulo:
            sinais.append(f"rótulo do rodapé sem correspondência no catálogo: «{rotulo}»")
        return Classificacao(None, None, "nenhuma", False, sinais)
    if por_titulo and por_rotulo and por_titulo not in _codigos_compativeis(rotulo, por_rotulo):
        sinais.append(f"conflito: rótulo sugere {por_rotulo} e título sugere {por_titulo}")
        return Classificacao(por_titulo, NOMES.get(por_titulo), "baixa", True, sinais)
    codigo = por_titulo or por_rotulo
    confianca = "alta" if por_titulo and por_rotulo else "media"
    return Classificacao(codigo, NOMES.get(codigo or ""), confianca, False, sinais)


def classificar_documentos(
    paginas: Sequence[PaginaLida], segmentos: Sequence[Segmento]
) -> list[tuple[Segmento, Classificacao]]:
    """Classifica cada segmento pela primeira pagina; orfa ou sem texto nao e classificada."""
    texto_da_pagina = {p.numero: p for p in paginas}
    resultado: list[tuple[Segmento, Classificacao]] = []
    for segmento in segmentos:
        primeira = texto_da_pagina[segmento.paginas[0]]
        if primeira.leitura == "sem_texto":
            sinais = ["sem_texto: página só de imagem; exige OCR e leitura humana"]
            if segmento.orfao:
                sinais.append("página órfã (sem rodapé do SEI)")
            resultado.append((segmento, Classificacao(None, None, "nenhuma", False, sinais)))
        elif primeira.leitura == "prejudicada":
            sinais = ["leitura prejudicada: camada de texto não confiável; exige leitura humana"]
            resultado.append((segmento, Classificacao(None, None, "nenhuma", False, sinais)))
        elif segmento.orfao:
            sinais = ["página órfã (sem rodapé do SEI): não classificada, mantida para revisão"]
            resultado.append((segmento, Classificacao(None, None, "nenhuma", False, sinais)))
        else:
            texto = _sem_rodape(primeira.texto)
            resultado.append((segmento, classificar_texto(texto, segmento.rotulo)))
    return resultado
