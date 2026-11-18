"""SEI FICTICIO para a prova de conceito da extensao (ADR-015). Nada aqui e do SEI real.

Imita SO a ESTRUTURA geral de um sistema com lista paginada de processos, arvore de documentos
e visualizacao de documento, tudo inventado e servido apenas em 127.0.0.1. A estrutura do SEI
real NAO e conhecida aqui: o adaptador da extensao so poderia ser calibrado com autorizacao.

Rotas de leitura (GET): entrar_ficticio, controlador.php?acao=
  procedimento_controlar&pagina=N | procedimento_trabalhar&id_procedimento=ID |
  arvore_visualizar&id_procedimento=ID | documento_visualizar&id_documento=ID
Controles do laboratorio (so para os testes): /_ficticio/avancar, /_ficticio/falhar?n=K,
  /_ficticio/estatisticas. Qualquer metodo diferente de GET e recusado (405) e CONTADO: a prova
  de que a extensao nao escreve.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

POR_PAGINA = 20
TOTAL_PROCESSOS = 230
FRASES = [
    "Solicito a vistoria das celas em 10 dias.",
    "Oficie-se ao órgão fictício para informar o número de pessoas custodiadas.",
    "Determino a juntada do relatório fictício em 5 dias úteis.",
    "Ciência. Arquive-se.",
    "Encaminhe-se ao Núcleo fictício para manifestação.",
]
TIPOS = ["Despacho", "Ofício", "Manifestação"]


class Estado:
    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.rodada = 1
        self.requisicoes = 0
        self.metodos: dict[str, int] = {}
        self.falhar_proximos = 0
        self.mortos_por_falha = 0

    def numero(self, i: int) -> str:
        return f"22.0.{i:09d}-{i % 10}"

    def processos(self) -> list[int]:
        extra = 1 if self.rodada >= 2 else 0
        return list(range(1, TOTAL_PROCESSOS + extra + 1))

    def restrito(self, i: int) -> bool:
        return i % 97 == 0  # alguns processos sem permissao

    def documentos(self, i: int) -> list[dict]:
        qtd = 2 + (i % 3)  # 2 a 4 documentos
        docs = []
        for k in range(qtd):
            docs.append(self._doc(i, k, "v1"))
        if self.rodada >= 2 and i % 25 == 0:
            docs.append(self._doc(i, qtd, "v1"))  # documento novo na rodada 2
        if self.rodada >= 2 and i == 3:
            docs[0] = self._doc(i, 0, "v2")  # documento modificado na rodada 2
        return docs

    def _doc(self, i: int, k: int, versao: str) -> dict:
        did = 5_000_000 + i * 10 + k
        tipo = TIPOS[(i + k) % len(TIPOS)]
        texto = f"{tipo.upper()} Nº {k + 1}/2026\nProcesso {self.numero(i)}.\n{FRASES[(i + k) % len(FRASES)]}"
        if versao == "v2":
            texto += "\nRetificação fictícia: prazo alterado para 15 dias."
        return {"id": did, "titulo": f"{tipo} {k + 1}/2026", "versao": versao, "texto": texto}

    def mov(self, i: int) -> str:
        dia = 1 + i % 27
        return f"2026-0{1 + i % 9}-{dia:02d}" if self.rodada == 1 else f"2026-1{i % 2}-{dia:02d}"


ESTADO = Estado()


def _pagina(corpo: str, titulo: str = "SEI fictício") -> bytes:
    return (
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>'
        f"</head><body>{corpo}</body></html>"
    ).encode()


class Manipulador(BaseHTTPRequestHandler):
    server_version = "SEIficticio/1"

    def log_message(self, *a):  # silencioso
        pass

    def _enviar(self, status: int, corpo: bytes, tipo="text/html; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _com_sessao(self) -> bool:
        return "SEIFICT=ok" in (self.headers.get("Cookie") or "")

    def _contar(self):
        with ESTADO.trava:
            ESTADO.requisicoes += 1
            ESTADO.metodos[self.command] = ESTADO.metodos.get(self.command, 0) + 1

    def do_POST(self):
        self._contar()
        self._enviar(405, _pagina("Escrita não permitida (fictício)."))

    do_PUT = do_DELETE = do_PATCH = do_POST

    def do_GET(self):
        self._contar()
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/_ficticio/estatisticas":
            with ESTADO.trava:
                dado = {"requisicoes": ESTADO.requisicoes, "metodos": ESTADO.metodos,
                        "rodada": ESTADO.rodada}  # fmt: skip
            return self._enviar(200, json.dumps(dado).encode(), "application/json")
        if url.path == "/_ficticio/avancar":
            with ESTADO.trava:
                ESTADO.rodada += 1
            return self._enviar(200, b'{"ok":true}', "application/json")
        if url.path == "/_ficticio/falhar":
            with ESTADO.trava:
                ESTADO.falhar_proximos = int(q.get("n", "0"))
            return self._enviar(200, b'{"ok":true}', "application/json")
        if url.path == "/sei/entrar_ficticio":
            return self._enviar(200, _pagina("Sessão fictícia aberta."),
                                extra={"Set-Cookie": "SEIFICT=ok; Path=/"})  # fmt: skip
        if url.path != "/sei/controlador.php":
            return self._enviar(404, _pagina("Não encontrado"))
        if not self._com_sessao():
            return self._enviar(200, _pagina('<form id="frmLogin">Entrar (fictício)</form>'))
        acao = q.get("acao", "")
        if acao == "procedimento_controlar":
            return self._lista(int(q.get("pagina", "0")))
        if acao == "procedimento_trabalhar":
            return self._processo(int(q.get("id_procedimento", "0")))
        if acao == "arvore_visualizar":
            return self._arvore(int(q.get("id_procedimento", "0")))
        if acao == "documento_visualizar":
            return self._documento(int(q.get("id_documento", "0")))
        return self._enviar(404, _pagina("Ação desconhecida"))

    def _lista(self, pagina: int):
        todos = ESTADO.processos()
        ini = pagina * POR_PAGINA
        fatia = todos[ini : ini + POR_PAGINA]
        linhas = "".join(
            f'<tr class="proc"><td><a class="processo" data-id="{i}" data-numero="{ESTADO.numero(i)}" '
            f'data-mov="{ESTADO.mov(i)}" href="controlador.php?acao=procedimento_trabalhar'
            f'&amp;id_procedimento={i}">{ESTADO.numero(i)}</a></td></tr>'
            for i in fatia
        )
        prox = ""
        if ini + POR_PAGINA < len(todos):
            prox = f'<a rel="next" href="controlador.php?acao=procedimento_controlar&amp;pagina={pagina + 1}">próxima</a>'
        self._enviar(200, _pagina(f'<table id="lista">{linhas}</table>{prox}'))

    def _processo(self, i: int):
        if i not in ESTADO.processos():
            return self._enviar(404, _pagina("Processo inexistente"))
        if ESTADO.restrito(i):
            return self._enviar(403, _pagina("Acesso restrito a este processo (fictício)."))
        self._enviar(
            200,
            _pagina(
                f'<h1 id="numero">{ESTADO.numero(i)}</h1><p id="espec">Inspeção fictícia {i}</p>'
                f'<a id="arvore" href="controlador.php?acao=arvore_visualizar&amp;id_procedimento={i}">árvore</a>'
            ),
        )

    def _arvore(self, i: int):
        if i not in ESTADO.processos() or ESTADO.restrito(i):
            return self._enviar(403, _pagina("Sem permissão"))
        itens = "".join(
            f'<li><a class="doc" data-id="{d["id"]}" data-versao="{d["versao"]}" '
            f'data-titulo="{d["titulo"]}" href="controlador.php?acao=documento_visualizar'
            f'&amp;id_documento={d["id"]}">{d["titulo"]}</a></li>'
            for d in ESTADO.documentos(i)
        )
        self._enviar(200, _pagina(f'<ul id="arvore-docs">{itens}</ul>'))

    def _documento(self, did: int):
        with ESTADO.trava:
            if ESTADO.falhar_proximos > 0:
                ESTADO.falhar_proximos -= 1
                return self._enviar(503, _pagina("Indisponível (falha injetada)"))
        i = (did - 5_000_000) // 10
        for d in ESTADO.documentos(i):
            if d["id"] == did:
                return self._enviar(200, _pagina(f'<div id="conteudo">{d["texto"]}</div>'))
        self._enviar(404, _pagina("Documento inexistente"))


def criar(porta: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    srv = criar(porta)
    print(
        f"SEI fictício em http://127.0.0.1:{srv.server_address[1]}/ (Ctrl+C para parar)", flush=True
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        time.sleep(0)
