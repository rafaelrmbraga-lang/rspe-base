"""Opcao conservadora para as sugestoes O.2 (decisao delegada): SINALIZAR sem extrair obrigacao.

- 'encaminhe-se' em oficio expedido: nao vira obrigacao; vira sinalizacao.
- Obrigacao implicita ('devera ...'): nao vira obrigacao; vira sinalizacao.
- Prazo sem numero ('imediato', 'com urgencia'): vira prazo NAO IDENTIFICADO com lacuna.
Frases INVENTADAS.
"""

from pathlib import Path

import pytest

from nuspen_regras.obrigacoes import extrair_obrigacoes, extrair_sinalizacoes

PDFS = Path(__file__).resolve().parents[2] / "dados_ficticios" / "pdfs"


def test_encaminhe_se_em_oficio_expedido_nao_e_obrigacao_mas_e_sinalizado():
    texto = "OFÍCIO Nº 1/2026 - UNIDADE\nEncaminhe-se o anexo ao destinatário."
    assert extrair_obrigacoes(texto, "A6") == []
    [s] = extrair_sinalizacoes(texto, "A6")
    assert s.tipo == "encaminhe-se-em-oficio"
    assert "Encaminhe-se" in s.frase


def test_encaminhe_se_em_despacho_continua_obrigacao_e_nao_e_sinalizacao():
    texto = "Encaminhe-se ao Órgão Ficticio."
    assert len(extrair_obrigacoes(texto, "A1")) == 1
    assert extrair_sinalizacoes(texto, "A1") == []


@pytest.mark.parametrize("tipo", ["A1", "A2", "A6", "C2", "B1"])
def test_obrigacao_implicita_e_sinalizada_e_nao_extraida(tipo):
    texto = "Deverá a direção providenciar a reforma das celas."
    assert extrair_obrigacoes(texto, tipo) == []
    [s] = extrair_sinalizacoes(texto, tipo)
    assert s.tipo == "obrigacao-implicita"


def test_tipos_sem_regra_nao_sinalizam():
    assert extrair_sinalizacoes("Deverá a direção providenciar.", "B2") == []
    assert extrair_sinalizacoes("Deverá a direção providenciar.", "") == []


def test_frase_sem_nenhum_dos_padroes_nao_sinaliza():
    assert extrair_sinalizacoes("Constatação: celas superlotadas.", "A1") == []


@pytest.mark.parametrize(
    "frase",
    [
        "Determino a vistoria das celas com urgência.",
        "Determino a vistoria das celas de imediato.",
        "Determino a vistoria das celas o quanto antes.",
    ],
)
def test_prazo_sem_numero_e_marcado_na_candidata(frase):
    [c] = extrair_obrigacoes(frase, "A1")
    assert c.prazo_quantidade is None
    assert c.prazo_sem_numero is True


def test_prazo_com_numero_nao_e_marcado_como_sem_numero():
    [c] = extrair_obrigacoes("Determino a vistoria em 10 dias, com urgência.", "A1")
    assert c.prazo_quantidade == 10
    assert c.prazo_sem_numero is False


def test_sem_urgencia_e_sem_numero_nao_marca_nada():
    [c] = extrair_obrigacoes("Determino a vistoria das celas.", "A1")
    assert c.prazo_sem_numero is False
