"""Segmentacao de um PDF exportado do SEI em documentos, pelo rodape (docs/14, secoes 3 e 6).

Regras: paginas consecutivas com o mesmo ID formam um documento; pagina sem rodape e
sinalizada como orfa (nunca descartada); ID que reaparece apos outro documento e sinalizado.
O resultado e uma SUGESTAO: a delimitacao passa por validacao humana (ADR de validacao).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from nuspen_regras.leitura import PaginaLida
from nuspen_regras.rodape import ler_rodape, normalizar_numero_processo


@dataclass
class Segmento:
    id_documento: str | None
    rotulo: str | None
    processo: str | None  # chave normalizada
    processo_original: str | None
    paginas: list[int] = field(default_factory=list)
    orfao: bool = False
    id_repetido: bool = False
    leitura_prejudicada: bool = False
    paginas_sem_rodape: list[int] = field(default_factory=list)
    pg_inicial: int | None = None  # numeracao 'pg.' do rodape (primeira e ultima pagina)
    pg_final: int | None = None


def segmentar(paginas: Sequence[PaginaLida]) -> list[Segmento]:
    segmentos: list[Segmento] = []
    ids_vistos: set[str] = set()
    for pagina in paginas:
        rodape = ler_rodape(pagina.texto) if pagina.texto else None
        atual = segmentos[-1] if segmentos else None
        if rodape is None:
            if atual is None or not atual.orfao:
                atual = Segmento(None, None, None, None, orfao=True)
                segmentos.append(atual)
        elif atual is None or atual.orfao or atual.id_documento != rodape.id_documento:
            atual = Segmento(
                id_documento=rodape.id_documento,
                rotulo=rodape.rotulo,
                processo=normalizar_numero_processo(rodape.processo),
                processo_original=rodape.processo,
                id_repetido=rodape.id_documento in ids_vistos,
            )
            ids_vistos.add(rodape.id_documento)
            segmentos.append(atual)
        atual.paginas.append(pagina.numero)
        if rodape is not None:
            if atual.pg_inicial is None:
                atual.pg_inicial = rodape.pagina
            atual.pg_final = rodape.pagina
        if pagina.leitura != "ok":
            atual.leitura_prejudicada = True
    return _incorporar_paginas_sem_rodape(segmentos)


def _incorporar_paginas_sem_rodape(segmentos: list[Segmento]) -> list[Segmento]:
    """Pagina(s) sem rodape entre dois trechos do MESMO documento pertencem a ele.

    Padrao medido nas amostras: o documento aparece partido em dois pelo mesmo ID com paginas
    sem rodape no meio. So funde se a numeracao 'pg.' do rodape confere (ultima + paginas sem
    rodape + 1 = primeira do trecho seguinte); sem conferencia, mantem como esta (sugestao).
    """
    saida: list[Segmento] = []
    i = 0
    while i < len(segmentos):
        atual = segmentos[i]
        if (
            saida
            and atual.orfao
            and i + 1 < len(segmentos)
            and not saida[-1].orfao
            and segmentos[i + 1].id_documento == saida[-1].id_documento
            and saida[-1].pg_final is not None
            and segmentos[i + 1].pg_inicial is not None
            and segmentos[i + 1].pg_inicial == saida[-1].pg_final + len(atual.paginas) + 1
        ):
            anterior = saida[-1]
            proximo = segmentos[i + 1]
            anterior.paginas_sem_rodape.extend(atual.paginas)
            anterior.paginas.extend(atual.paginas)
            anterior.paginas.extend(proximo.paginas)
            anterior.pg_final = proximo.pg_final
            anterior.leitura_prejudicada = (
                anterior.leitura_prejudicada or proximo.leitura_prejudicada
            )
            i += 2
            continue
        saida.append(atual)
        i += 1
    return saida
