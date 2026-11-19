# -*- coding: utf-8 -*-
"""Páginas de PDF no formato que o leitor de ficha do APTO usa (o do pdfplumber), montadas a partir dos caracteres que o
pdf.js extrai no navegador (painel da extensão): texto, posição (x0, x1, top, bottom), tamanho e nome da fonte de cada
caractere. O texto da página e as palavras saem pelas MESMAS funções do pdfplumber (pdfplumber.utils.text, Python puro,
licença MIT; no navegador vão copiadas sem alteração), então a leitura da ficha (rspe_ficha.extrair_paginas_pdf) é a mesma
do APTO. Só o que o leitor de ficha usa: chars, width, height, extract_text(), extract_words() e filter()."""
from pdfplumber.utils.text import chars_to_textmap, extract_words


class Pagina:
    def __init__(self, chars, width, height):
        self.chars = chars
        self.width, self.height = width, height
        self.bbox = (0, 0, width, height)

    def extract_text(self, **kw):
        return chars_to_textmap(self.chars, layout_bbox=self.bbox, layout_width=self.width, layout_height=self.height, **kw).as_string

    def extract_words(self, **kw):
        return extract_words(self.chars, **kw)

    def filter(self, fn):
        return Pagina([c for c in self.chars if fn(c)], self.width, self.height)


def char(texto, x0, x1, top, bottom, size, fontname, doctop):
    """Um caractere com os campos do pdfplumber que o leitor e o pdfplumber.utils.text usam."""
    return {"object_type": "char", "text": texto, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "doctop": doctop,
            "y0": None, "y1": None, "width": x1 - x0, "height": bottom - top, "size": size, "fontname": fontname, "upright": True}


def paginas(dados):
    """[{"largura", "altura", "chars": [[texto, x0, x1, top, bottom, size, fonte], ...]}, ...] (o que a extensão manda) ->
    [Pagina]. doctop: a posição no documento (as páginas empilhadas), como no pdfplumber."""
    out, acima = [], 0.0
    for p in dados or []:
        w, h = float(p["largura"]), float(p["altura"])
        cs = []
        for t, x0, x1, top, bot, size, fonte in p.get("chars") or []:
            c = char(t, float(x0), float(x1), float(top), float(bot), float(size), fonte or "", acima + float(top))
            c["y0"], c["y1"] = h - c["bottom"], h - c["top"]
            cs.append(c)
        out.append(Pagina(cs, w, h))
        acima += h
    return out


def de_pdfplumber(pagina):
    """Os caracteres de uma página do pdfplumber no formato que a extensão manda (para os testes de paridade)."""
    return {"largura": float(pagina.width), "altura": float(pagina.height),
            "chars": [[c["text"], c["x0"], c["x1"], c["top"], c["bottom"], c["size"], c.get("fontname") or ""] for c in pagina.chars]}
