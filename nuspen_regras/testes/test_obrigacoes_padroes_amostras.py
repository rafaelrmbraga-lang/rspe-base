"""Formas de comando e de prazo observadas nas amostras anonimizadas, reproduzidas com frases
INVENTADAS (ordem de 08/11/2026, bloco B). O prazo continua sem vencimento calculado."""

import pytest

from nuspen_regras.obrigacoes import extrair_obrigacoes, extrair_prazo_do_texto


def _uma(texto, tipo="A1"):
    candidatas = extrair_obrigacoes(texto, tipo)
    assert len(candidatas) == 1, candidatas
    return candidatas[0]


# ------------------------------------------------------------------ prazos


@pytest.mark.parametrize(
    "frase,quantidade,unidade",
    [
        ("com prazo de 10(dez) dias para resposta", 10, "dias"),
        ("no prazo de 10 dias", 10, "dias"),
        ("no prazo de dez dias", 10, "dias"),
        ("em 15 dias", 15, "dias"),
        ("em até 5 dias", 5, "dias"),
        ("dentro de vinte dias", 20, "dias"),
        ("no prazo de 48 horas", 48, "horas"),
        ("no prazo de quarenta e oito horas", 48, "horas"),
        ("em vinte e quatro horas", 24, "horas"),
        ("prazo de 30 (trinta) dias úteis", 30, "dias úteis"),
        ("prazo de 5 dias corridos", 5, "dias corridos"),
        ("prazo de três meses", 3, "meses"),
        ("prazo de 2 meses", 2, "meses"),
        ("prazo de sessenta dias", 60, "dias"),
    ],
)
def test_formas_de_prazo_expresso(frase, quantidade, unidade):
    prazo = extrair_prazo_do_texto(f"Determino a vistoria {frase}.")
    assert prazo is not None, frase
    assert (prazo.quantidade, prazo.unidade) == (quantidade, unidade)


@pytest.mark.parametrize(
    "frase",
    [
        "com urgência",
        "de imediato",
        "o quanto antes",
        "há 10 dias foi feito o contato",  # passado: nao e prazo
        "ocorrido em 10 de março",  # data, nao prazo
    ],
)
def test_expressoes_sem_numero_ou_nao_prazo_nao_viram_prazo(frase):
    assert extrair_prazo_do_texto(f"Determino a vistoria {frase}.") is None


def test_prazo_da_determinacao_continua_sem_vencimento_na_candidata():
    c = _uma("Determino a expedição de ofício à direção, em 10 dias.")
    assert (c.prazo_quantidade, c.prazo_unidade) == (10, "dias")
    assert "em 10 dias" not in c.objeto  # o prazo nao entra no objeto
    assert not hasattr(c, "data_vencimento")


# ------------------------------------------------------------------ formas de comando


def test_solicito_na_primeira_pessoa():
    c = _uma("Solicito à direção a remessa de cópia do prontuário, no prazo de dez dias.")
    assert c.regra == "solicito"
    assert c.destinatario == "direção"
    assert c.objeto.startswith("a remessa")
    assert (c.prazo_quantidade, c.prazo_unidade) == (10, "dias")


def test_providencie_se():
    c = _uma("Providencie-se a vistoria das celas.")
    assert (c.regra, c.tipo) == ("providencie-se", "providencia_material")
    assert c.objeto == "a vistoria das celas"


def test_oficie_se_com_destinatario():
    c = _uma("Oficie-se à Secretaria Ficticia para que informe a situação.")
    assert (c.regra, c.tipo) == ("oficie-se", "expedir_oficio")
    assert c.destinatario == "Secretaria Ficticia"


def test_encaminhe_se_imperativo_com_destinatario():
    c = _uma("Encaminhe-se ao Órgão Ficticio, em 5 dias.")
    assert (c.regra, c.tipo) == ("encaminhe-se", "providencia_material")
    assert c.destinatario == "Órgão Ficticio"
    assert c.prazo_quantidade == 5


def test_reitero_na_primeira_pessoa():
    c = _uma("Reitero o pedido anterior, no prazo de 5 dias.")
    assert (c.regra, c.tipo) == ("reitere-se", "expedir_oficio")


def test_recomendo_e_recomenda_se_viram_recomendacao():
    for texto, tipo in (
        ("Recomendo a reforma das celas.", "A1"),
        ("Recomenda-se a reforma das celas.", "A3"),
        ("Recomendo a reforma das celas.", "C2"),
    ):
        c = _uma(texto, tipo)
        assert c.origem == "recomendacao"
        assert c.objeto == "a reforma das celas"
        assert c.prazo_quantidade is None


def test_solicito_em_oficio_externo_e_solicitacao_externa():
    c = _uma("Solicito assistência jurídica ao assistido fictício.", "B1")
    assert c.origem == "solicitacao_externa"


@pytest.mark.parametrize(
    "frase",
    [
        "Não solicito nada.",
        "Cumpra-se.",
        "Junte-se aos autos.",
        "O diretor solicitou informações no mês passado.",  # passado/terceira pessoa
        "Poderá a direção providenciar a reforma.",  # possibilidade
        "Providenciou-se a vistoria.",  # ja feito
        "Solicito o prazo de 10 dias para complementação.",  # pedido de prazo
    ],
)
def test_formas_que_nao_sao_comando_continuam_de_fora(frase):
    assert extrair_obrigacoes(frase, "A1") == []


def test_tipos_sem_regra_continuam_sem_extrair():
    assert extrair_obrigacoes("Providencie-se a vistoria.", "B2") == []
    assert extrair_obrigacoes("Providencie-se a vistoria.", "") == []


def test_lacunas_conhecidas_continuam_documentadas():
    """'Deverá' (obrigacao implicita) segue sem extracao: ver docs/09, secao O."""
    assert extrair_obrigacoes("Deverá a direção providenciar a reforma.", "A1") == []
