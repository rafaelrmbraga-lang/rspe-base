"""Testes da leitura de rodape, numero de processo, assinatura e prazo (docs/14, secao 2).

Todos os textos de exemplo sao FICTICIOS.
"""

from nuspen_regras.rodape import (
    encontrar_numeros_processo,
    extrair_prazo,
    ler_assinatura,
    ler_rodape,
    normalizar_numero_processo,
)


def test_rodape_com_parenteses():
    rodape = ler_rodape("Despacho (9000001)  SEI 99/000123/2026 / pg. 3")
    assert rodape is not None
    assert rodape.rotulo == "Despacho"
    assert rodape.id_documento == "9000001"
    assert rodape.processo == "99/000123/2026"
    assert rodape.pagina == 3


def test_rodape_sem_parenteses_e_com_rotulo_composto():
    rodape = ler_rodape("Despacho - NUSPEN 9000002  SEI 99.000123.2026 / pg. 14")
    assert rodape is not None
    assert rodape.rotulo == "Despacho - NUSPEN"
    assert rodape.id_documento == "9000002"
    assert rodape.processo == "99.000123.2026"
    assert rodape.pagina == 14


def test_id_preserva_zeros_a_esquerda():
    rodape = ler_rodape("Oficio ao orgao (0000123)  SEI 99/000123/2026 / pg. 1")
    assert rodape is not None
    assert rodape.id_documento == "0000123"


def test_id_com_menos_de_seis_digitos_nao_e_rodape():
    assert ler_rodape("Despacho (12345)  SEI 99/000123/2026 / pg. 1") is None


def test_rodape_e_procurado_nas_ultimas_linhas_da_pagina():
    texto = (
        "DESPACHO\nTrata-se de caso ficticio.\n\nDespacho (9000001)  SEI 99/000123/2026 / pg. 2\n"
    )
    rodape = ler_rodape(texto)
    assert rodape is not None
    assert rodape.id_documento == "9000001"


def test_texto_sem_rodape_devolve_none():
    assert ler_rodape("Pagina de continuacao sem rodape nenhum.") is None
    assert ler_rodape("") is None


def test_normaliza_os_dois_formatos_atuais_para_a_mesma_chave():
    assert normalizar_numero_processo("99/000123/2026") == "99/000123/2026"
    assert normalizar_numero_processo("99.000123.2026") == "99/000123/2026"


def test_formato_antigo_e_mantido_e_invalido_devolve_none():
    assert normalizar_numero_processo("22.0.999999999-9") == "22.0.999999999-9"
    assert normalizar_numero_processo("abc") is None
    assert normalizar_numero_processo("99/00012/2026") is None


def test_encontra_numeros_em_dois_formatos_no_mesmo_texto_guardando_o_original():
    texto = "Processo 99/000123/2026, tambem citado como 99.000123.2026 e 22.0.999999999-9."
    achados = encontrar_numeros_processo(texto)
    assert [a.original for a in achados] == ["99/000123/2026", "99.000123.2026", "22.0.999999999-9"]
    assert [a.normalizado for a in achados] == [
        "99/000123/2026",
        "99/000123/2026",
        "22.0.999999999-9",
    ]


def test_assinatura_com_quebra_de_linha_no_nome_e_no_cargo():
    texto = (
        "Documento assinado eletronicamente por SERVIDOR FICTICIO\n"
        "DE EXEMPLO, COORDENADOR FICTICIO DO NUCLEO MODELO, em 03/02/2026, as 10:15, conforme x."
    ).replace("as 10:15", "às 10:15")
    assinatura = ler_assinatura(texto)
    assert assinatura is not None
    assert assinatura.nome == "SERVIDOR FICTICIO DE EXEMPLO"
    assert assinatura.cargo == "COORDENADOR FICTICIO DO NUCLEO MODELO"
    assert assinatura.data == "03/02/2026"
    assert assinatura.hora == "10:15"


def test_sem_carimbo_nao_ha_assinatura():
    assert ler_assinatura("OFICIO externo sem carimbo de assinatura do SEI.") is None


def test_prazo_expresso_sem_espaco_antes_do_extenso_nao_calcula_vencimento():
    prazo = extrair_prazo("Fica concedido prazo de 30(trinta) dias para resposta.")
    assert prazo is not None
    assert (prazo.numero, prazo.extenso, prazo.unidade) == (30, "trinta", "dias")
    # A regra de contagem nao esta no texto e nao pode ser presumida (ADR de prazos).
    assert not hasattr(prazo, "vencimento")
    assert not hasattr(prazo, "dias_uteis")


def test_texto_sem_prazo_devolve_none():
    assert extrair_prazo("Solicita-se resposta com brevidade.") is None


def test_assinatura_com_quebra_de_linha_logo_depois_da_virgula():
    texto = (
        "Documento assinado eletronicamente por SERVIDOR FICTICIO DE EXEMPLO,\n"
        "COORDENADOR FICTICIO DO NUCLEO MODELO, em 03/02/2026, às 10:15, conforme norma ficticia."
    )
    assinatura = ler_assinatura(texto)
    assert assinatura is not None
    assert assinatura.nome == "SERVIDOR FICTICIO DE EXEMPLO"
    assert assinatura.cargo == "COORDENADOR FICTICIO DO NUCLEO MODELO"
