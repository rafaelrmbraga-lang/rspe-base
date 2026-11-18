"""Extracao de obrigacoes por regras explicitas (ADR-011, ADR-013). Tudo FICTICIO.

O extrator so SUGERE: cada candidata traz a frase de origem (fonte), a regra e o verbo.
Prazo vem so do texto; destinatario so do texto; nada e inferido por semelhanca de nome.
"""

import pytest

from nuspen_regras.obrigacoes import extrair_obrigacoes

DESPACHO = (
    "DESPACHO\nProcesso nº 99/000123/2026\nTrata-se de inspeção fictícia no EPMF. CONSIDERANDO a "
    "necessidade de acompanhar as condições\ndo estabelecimento, determino a expedição de ofício "
    "à direção, com prazo de 30(trinta) dias\npara resposta. Cumpra-se.\n"
)
OFICIO = (
    "OFÍCIO Nº 9000002/99/000123/2026 - NUSPEN (FICTÍCIO)\n"
    "Campo Grande, 05 de fevereiro de 2026 (fictício).\n"
    "À Direção do EPMF. Assunto: informações sobre as condições do estabelecimento.\n"
    "Solicita-se: (1) quantidade de pessoas custodiadas; (2) condições de alimentação; (3)\n"
    "atendimentos de saúde realizados no mês.\n"
    "Fica estipulado prazo de 15(quinze) dias para a resposta.\n"
)


def _por(texto, tipo):
    return extrair_obrigacoes(texto, tipo)


def test_determino_gera_obrigacao_com_destinatario_e_prazo_expresso():
    [c] = _por(DESPACHO, "A1")
    assert c.tipo == "expedir_oficio"
    assert c.origem == "despacho"
    assert c.destinatario == "direção"
    assert (c.prazo_quantidade, c.prazo_unidade) == (30, "dias")
    assert "determino a expedição de ofício" in c.frase
    assert c.regra == "determino"


def test_cumpra_se_sozinho_nao_gera_obrigacao():
    assert _por("Cumpra-se. Ciente.", "A1") == []


def test_solicitacoes_itemizadas_viram_uma_obrigacao_por_item_com_o_prazo_da_frase_seguinte():
    candidatas = _por(OFICIO, "A6")
    assert [c.objeto for c in candidatas] == [
        "quantidade de pessoas custodiadas",
        "condições de alimentação",
        "atendimentos de saúde realizados no mês",
    ]
    assert {c.tipo for c in candidatas} == {"responder"}
    assert {c.destinatario for c in candidatas} == {"Direção do EPMF"}
    assert {(c.prazo_quantidade, c.prazo_unidade) for c in candidatas} == {(15, "dias")}
    assert {c.origem for c in candidatas} == {"decisao"}


def test_pedido_de_prazo_de_outro_orgao_nao_e_obrigacao():
    texto = "MINISTÉRIO PÚBLICO FICTÍCIO\nSolicita-se o prazo de 10(dez) dias para complementação."
    assert _por(texto, "B1") == []


def test_oficio_externo_pedindo_assistencia_vira_solicitacao_externa():
    texto = (
        "Solicita-se assistência jurídica a FULANO DE TAL EXEMPLO (pessoa inventada), custodiado."
    )
    [c] = _por(texto, "B1")
    assert c.origem == "solicitacao_externa"
    assert c.tipo == "providencia_material"
    assert "FULANO DE TAL EXEMPLO" in c.frase  # a pessoa fica so na frase, sem entidade nem fusao


def test_reitere_se_com_novo_prazo():
    texto = "Reitere-se o ofício 9000002, com novo prazo de 5(cinco) dias. Ciente."
    [c] = _por(texto, "A1")
    assert c.tipo == "expedir_oficio"
    assert (c.prazo_quantidade, c.prazo_unidade) == (5, "dias")
    assert c.regra == "reitere-se"


def test_encaminhamento_com_prazo_e_devolucao():
    texto = (
        "Em cumprimento à determinação do Coordenador, encaminha-se o caso, no prazo de 10(dez) "
        "dias,\nou em prazo menor. Solicita-se a devolução do expediente."
    )
    candidatas = _por(texto, "A2")
    assert [c.tipo for c in candidatas] == ["providencia_material", "retornar_solicitante"]
    assert (candidatas[0].prazo_quantidade, candidatas[0].prazo_unidade) == (10, "dias")
    assert candidatas[1].prazo_quantidade is None  # o prazo nao e estendido a outra frase


def test_recomendacao_vira_obrigacao_de_origem_recomendacao_sem_destinatario_inventado():
    texto = "Constatação fictícia: superlotação declarada. Recomendação: reduzir a ocupação."
    [c] = _por(texto, "C2")
    assert c.origem == "recomendacao"
    assert c.destinatario == ""
    assert c.objeto == "reduzir a ocupação"


@pytest.mark.parametrize(
    "frase",
    [
        "A direção poderá providenciar a reforma.",  # possibilidade nao e obrigacao
        "Sugere-se avaliar a situação.",  # sugestao fica fora: nao vira obrigacao
        "O juiz determinou a soltura em outro processo.",  # discurso reportado
        "Não determino nenhuma providência.",  # negacao
        "Foi prestado atendimento, conforme relatório anexo.",  # afirmacao de cumprimento
    ],
)
def test_frases_que_nao_sao_comando_nao_geram_obrigacao(frase):
    assert _por(frase, "A1") == []


def test_tipo_documental_sem_regra_nao_extrai_nada():
    assert _por(DESPACHO, "B2") == []  # e-mail
    assert _por(DESPACHO, "") == []  # tipo nao identificado
    assert _por(DESPACHO, "A3") == []  # manifestacao: informa, nao determina


def test_prazo_nao_e_inventado_quando_o_texto_nao_traz():
    [c] = _por("Determino a expedição de ofício à direção.", "A1")
    assert c.prazo_quantidade is None
    assert c.prazo_unidade == ""


# ------------------------------------------------- indicios de resposta (nao e cumprimento)


def test_certidao_e_termo_de_juntada_citam_resposta_a_um_oficio():
    from nuspen_regras.obrigacoes import extrair_indicios_resposta

    [a] = extrair_indicios_resposta(
        "Certifico que, na data de teste, a resposta ao ofício 9000002 foi recebida.", "A4"
    )
    [b] = extrair_indicios_resposta(
        "Junto aos autos a resposta ao ofício nº 9000002, enviada pelo EPMF.", "A5"
    )
    assert a.oficio == b.oficio == "9000002"


def test_manifestacao_que_afirma_atendimento_e_so_afirmacao_com_prova_em_outro_documento():
    from nuspen_regras.obrigacoes import extrair_indicios_resposta

    [i] = extrair_indicios_resposta(
        "Prezado Coordenador, informo que foi prestado atendimento, conforme relatório anexo.",
        "A3",
    )
    assert i.oficio == ""
    assert "afirma" in i.descricao.lower()
    assert "não verificada" in i.descricao.lower()


def test_tipo_sem_regra_de_indicio_nao_extrai():
    from nuspen_regras.obrigacoes import extrair_indicios_resposta

    assert extrair_indicios_resposta("resposta ao ofício 9000002", "A1") == []


def test_objeto_da_determinacao_nao_inclui_a_oracao_do_prazo():
    """Achado ao medir os erros: 'no prazo de ...' entrava no objeto."""
    [c] = _por(
        "Determino que a direção informe o número de custodiados, no prazo de 10(dez) dias.", "A1"
    )
    assert c.objeto == "que a direção informe o número de custodiados"
    assert c.prazo_quantidade == 10
