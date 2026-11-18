"""Leitura de PDF: texto por pagina (pdfplumber). No APTO sem a renderizacao (pypdfium2) e sem OCR: pagina so de imagem fica sem_texto."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Caracteres de pontuacao comuns em texto juridico; qualquer outro simbolo e "estranho".
_COMUNS = set(".,;:!?()[]{}-–—/\\\"'º°ª%&*+=_§")


def classificar_leitura(texto: str) -> str:
    """'sem_texto', 'prejudicada' (muito simbolo estranho) ou 'ok'. Heuristica [A testar]."""
    conteudo = "".join(texto.split())
    if not conteudo:
        return "sem_texto"
    estranhos = sum(1 for c in conteudo if not c.isalnum() and c not in _COMUNS)
    if estranhos / len(conteudo) > 0.2:
        return "prejudicada"
    return "ok"


@dataclass(frozen=True)
class PaginaLida:
    numero: int  # posicao da pagina no arquivo, comecando em 1
    texto: str
    leitura: str  # ok | sem_texto | prejudicada


def extrair_paginas(caminho: Path | str) -> list[PaginaLida]:
    """Texto nativo de cada pagina. Pagina so de imagem volta com texto vazio e 'sem_texto'."""
    import pdfplumber  # so quando le PDF (os testes de segmentacao nao precisam)

    paginas = []
    with pdfplumber.open(caminho) as pdf:
        for numero, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""
            pagina.close()  # libera o cache da pagina (sem isso, ~750 MB em 370 paginas)
            paginas.append(
                PaginaLida(numero=numero, texto=texto, leitura=classificar_leitura(texto))
            )
    return paginas
