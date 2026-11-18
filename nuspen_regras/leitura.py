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


# ---- OCR opcional (7.28, APTO): só se o Tesseract estiver instalado neste computador; o texto vem marcado como lido por OCR ----
def tesseract_embutido():
    """O Tesseract que vem com o APTO (7.29): pasta "tesseract" ao lado do APTO.exe (ou na pasta do código, ao rodar pelo Python)."""
    import os
    import sys

    bases = [os.path.dirname(sys.executable)] if getattr(sys, "frozen", False) else []
    bases.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for b in bases:
        for nome in ("tesseract.exe", "tesseract"):
            c = os.path.join(b, "tesseract", nome)
            if os.path.isfile(c):
                return c
    return None


def tesseract():
    """Caminho do tesseract: o que vem com o APTO; senão o do computador (PATH ou a instalação padrão no Windows); None se não houver."""
    import os
    import shutil

    achado = tesseract_embutido() or shutil.which("tesseract")
    if achado:
        return achado
    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.isfile(c):
            return c
    return None


def ocr_pagina(caminho: Path | str, numero: int, exe: str, resolucao: int = 200) -> str:
    """Texto de UMA página (numero a partir de 1) pelo Tesseract (português; sem o idioma, o padrão). '' se falhar."""
    import os
    import subprocess
    import tempfile

    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        img = pdf.pages[numero - 1].to_image(resolution=resolucao)
        fd, png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            img.save(png)
            dados = os.path.join(os.path.dirname(exe), "tessdata")
            extra = ["--tessdata-dir", dados] if os.path.isdir(dados) else []  # o português que vem com o APTO
            sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no Windows, sem piscar uma janela preta por página
            for idioma in (["-l", "por"], []):
                r = subprocess.run([exe, png, "stdout", *extra, *idioma], capture_output=True, text=True, timeout=90, creationflags=sem_janela)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout
            return ""
        finally:
            try:
                os.remove(png)
            except OSError:
                pass
