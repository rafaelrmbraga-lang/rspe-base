"""Testes da segmentacao por rodape (docs/14, secoes 3 e 6). Paginas e textos FICTICIOS."""

from nuspen_regras.leitura import PaginaLida, classificar_leitura
from nuspen_regras.segmentacao import segmentar


def _pagina(numero: int, texto: str) -> PaginaLida:
    return PaginaLida(numero=numero, texto=texto, leitura=classificar_leitura(texto))


def _rodape(rotulo: str, id_doc: str, proc: str, pg: int) -> str:
    return f"{rotulo} ({id_doc})  SEI {proc} / pg. {pg}"


def test_paginas_consecutivas_com_o_mesmo_id_formam_um_documento():
    paginas = [
        _pagina(
            1,
            "DESPACHO ficticio, primeira pagina.\n"
            + _rodape("Despacho", "9000001", "99/000123/2026", 1),
        ),
        _pagina(
            2,
            "Continuacao do despacho ficticio.\n"
            + _rodape("Despacho", "9000001", "99/000123/2026", 2),
        ),
        _pagina(3, "OFICIO ficticio.\n" + _rodape("Oficio", "9000002", "99/000123/2026", 3)),
    ]
    segmentos = segmentar(paginas)
    assert [s.id_documento for s in segmentos] == ["9000001", "9000002"]
    assert [s.paginas for s in segmentos] == [[1, 2], [3]]
    assert not any(s.orfao or s.id_repetido for s in segmentos)


def test_pagina_sem_rodape_e_sinalizada_como_orfa_e_nao_descartada():
    paginas = [
        _pagina(1, "CERTIDAO ficticia.\n" + _rodape("Certidao", "9000003", "99/000123/2026", 1)),
        _pagina(2, "Anexo ficticio sem rodape algum, apenas texto corrido de teste."),
    ]
    segmentos = segmentar(paginas)
    assert len(segmentos) == 2
    assert segmentos[1].orfao is True
    assert segmentos[1].id_documento is None
    assert segmentos[1].paginas == [2]


def test_id_que_reaparece_depois_de_outro_documento_e_sinalizado():
    paginas = [
        _pagina(1, "PROTOCOLO ficticio.\n" + _rodape("Protocolo", "9000005", "99/000123/2026", 1)),
        _pagina(2, "OFICIO ficticio.\n" + _rodape("Oficio", "9000006", "99/000123/2026", 2)),
        _pagina(
            3,
            "PROTOCOLO ficticio de novo.\n" + _rodape("Protocolo", "9000005", "99/000123/2026", 3),
        ),
    ]
    segmentos = segmentar(paginas)
    assert [s.id_documento for s in segmentos] == ["9000005", "9000006", "9000005"]
    assert [s.id_repetido for s in segmentos] == [False, False, True]


def test_numero_de_processo_em_dois_formatos_vira_a_mesma_chave_e_guarda_o_original():
    paginas = [
        _pagina(1, "A\n" + _rodape("Despacho", "9000001", "99/000123/2026", 1)),
        _pagina(2, "B\n" + _rodape("Oficio", "9000002", "99.000123.2026", 2)),
    ]
    segmentos = segmentar(paginas)
    assert {s.processo for s in segmentos} == {"99/000123/2026"}
    assert [s.processo_original for s in segmentos] == ["99/000123/2026", "99.000123.2026"]


def test_pagina_sem_texto_e_texto_ruidoso_marcam_leitura_prejudicada():
    ruido = "@#$% ~~ ^^ |||| ;;;; ¬¬ ©© ·· ¨¨ ¢¢ ££ ¥¥ §§ ¿¿ ¤¤ ¦¦"
    paginas = [
        _pagina(1, ""),
        _pagina(2, ruido + "\n" + _rodape("Carta Assistido", "9000007", "99/000123/2026", 2)),
        _pagina(
            3,
            "Texto normal e legivel de uma pagina ficticia.\n"
            + _rodape("Despacho", "9000008", "99/000123/2026", 3),
        ),
    ]
    segmentos = segmentar(paginas)
    assert segmentos[0].orfao and segmentos[0].leitura_prejudicada
    assert segmentos[1].leitura_prejudicada
    assert not segmentos[2].leitura_prejudicada


def test_classificar_leitura():
    assert classificar_leitura("") == "sem_texto"
    assert classificar_leitura("   \n  ") == "sem_texto"
    assert classificar_leitura("Texto legivel de teste, com varias palavras.") == "ok"
    assert (
        classificar_leitura("@#$% ~~ ^^ |||| ;;;; ¬¬ ©© ·· ¨¨ ¢¢ ££ ¥¥ §§ ¿¿ ¤¤ ¦¦")
        == "prejudicada"
    )
