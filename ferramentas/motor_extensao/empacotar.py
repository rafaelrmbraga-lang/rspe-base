"""Empacota o motor do APTO para a extensão (painel no SEEU): copia OS MESMOS arquivos .py do APTO e a base jurídica
embutida para extensao_seeu/motor/py/, grava motor.json (versão do APTO, sha256 de cada arquivo) e, se faltar, baixa o
Pyodide fixado (mesmo Python 3.12 da compilação do APTO) para extensao_seeu/motor/pyodide/, conferindo o sha256.
Nada é editado nos arquivos copiados: a extensão roda o código do APTO byte a byte.
Uso: python ferramentas/motor_extensao/empacotar.py [--sem-pyodide]"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESTINO = os.path.join(RAIZ, "extensao_seeu", "motor")
# os módulos que o painel usa (rspe_painel importa rspe_motor, que importa os demais; alguns entram por import tardio)
MODULOS = ["rspe_painel", "rspe_seeu_abas", "rspe_pdf_paginas", "rspe_motor", "rspe_scraper", "rspe_view", "rspe_ficha", "rspe_regras", "rspe_decretos", "rspe_prescricao",
           "rspe_auditoria", "rspe_reincidencia", "rspe_remicao", "rspe_calc", "rspe_indulto_tl", "rspe_resumo", "rspe_relatorio"]
DADOS = ["base_juridica.json", "logo_defensoria.png"]  # o logo vai no resumo para o assistido (o mesmo do APTO)
# resumo para o assistido: o PDF sai do MESMO gerador do APTO (rspe_relatorio), com as fontes do APTO, o reportlab em Python
# puro NA MESMA VERSÃO instalada com o APTO (PyPI, sha256 conferido) e o Pillow do próprio Pyodide (para o logo). Carregados
# só quando o resumo é pedido (motor/extra).
PILLOW = "pillow-10.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl"
PILLOW_URL = "https://cdn.jsdelivr.net/pyodide/v%s/full/%s"
PYODIDE_VERSAO = "0.27.7"  # Python 3.12.7, o mesmo 3.12 da compilação do APTO (.github/workflows/build.yml)
PYODIDE_TGZ = "https://registry.npmjs.org/pyodide/-/pyodide-%s.tgz" % PYODIDE_VERSAO
PYODIDE_SHA256 = "89d5d952675eb08e11286e52c7238f1248ce71726e896db9703e73bef23dc343"  # sha256 do .tgz do npm (conferido ao baixar)
PYODIDE_ARQS = ["pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "package.json"]
# pdfplumber no painel: só a montagem do texto a partir dos caracteres (pdfplumber.utils.text e o que ele usa, Python puro,
# licença MIT), copiada SEM alteração do pdfplumber instalado com o APTO; os caracteres vêm do pdf.js (rspe_pdf_paginas).
# A abertura de arquivo (pdfplumber.open, que precisa do pdfminer) fica de fora.
STUB_PDFPLUMBER = '"""pdfplumber no painel do SEEU: só pdfplumber.utils.text (copiado do pdfplumber do APTO); os caracteres vêm do pdf.js."""\n\n\ndef open(*a, **k):\n    raise RuntimeError("abertura de PDF indisponível no painel: os caracteres vêm do pdf.js")\n'
STUB_UTILS = '"""Só o que pdfplumber.utils.text usa (sem pdfinternals, que precisa do pdfminer)."""\n'
PDFPLUMBER_COPIA = ["_typing.py", "utils/text.py", "utils/clustering.py", "utils/generic.py", "utils/geometry.py", "../pdfplumber-*.dist-info/licenses/LICENSE.txt"]


def sha(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def versao_apto():
    with open(os.path.join(RAIZ, "rspe_app.py"), encoding="utf-8") as f:
        return re.search(r'^VERSAO = "([^"]+)"', f.read(), re.M).group(1)


def montar_pdfplumber(destino):
    """destino/pdfplumber: o pacote mínimo do painel. Devolve {caminho relativo: sha256}."""
    import glob
    import pdfplumber as _p
    orig = os.path.dirname(_p.__file__)
    base = os.path.join(destino, "pdfplumber")
    os.makedirs(os.path.join(base, "utils"), exist_ok=True)
    out = {}
    with open(os.path.join(base, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(STUB_PDFPLUMBER)
    with open(os.path.join(base, "utils", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(STUB_UTILS)
    for rel in PDFPLUMBER_COPIA:
        achados = glob.glob(os.path.join(orig, rel))
        if not achados:
            raise SystemExit("pdfplumber instalado sem %s: instale o requirements.txt" % rel)
        nome = "LICENSE-pdfplumber.txt" if rel.endswith("LICENSE.txt") else rel
        shutil.copyfile(achados[0], os.path.join(base, nome))
    for raiz, _d, fs in os.walk(base):
        for x in fs:
            c = os.path.join(raiz, x)
            out[os.path.relpath(c, destino).replace(os.sep, "/")] = sha(c)
    return out


def baixar_extras():
    """reportlab (Python puro, a versão instalada com o APTO) e Pillow (do Pyodide) para o resumo do assistido."""
    import reportlab
    ex = os.path.join(DESTINO, "extra")
    os.makedirs(ex, exist_ok=True)
    feitos = []
    v = reportlab.Version
    meta = json.loads(urllib.request.urlopen("https://pypi.org/pypi/reportlab/%s/json" % v, timeout=60).read())
    roda = next((u for u in meta["urls"] if u["filename"].endswith("-py3-none-any.whl")), None)
    if not roda:
        raise SystemExit("reportlab %s sem a versão em Python puro no PyPI: o resumo do painel precisa dela" % v)
    for f in os.listdir(ex):
        if f.startswith("reportlab-") and f != roda["filename"]:
            os.remove(os.path.join(ex, f))  # versão antiga
    alvos = [(roda["filename"], roda["url"], roda["digests"]["sha256"])]
    lock = json.load(open(os.path.join(DESTINO, "pyodide", "pyodide-lock.json"), encoding="utf-8"))["packages"]["pillow"]
    alvos.append((PILLOW, PILLOW_URL % (PYODIDE_VERSAO, PILLOW), lock["sha256"]))
    for nome, url, esperado in alvos:
        c = os.path.join(ex, nome)
        if os.path.exists(c) and sha(c) == esperado:
            continue
        dados = urllib.request.urlopen(url, timeout=120).read()
        if hashlib.sha256(dados).hexdigest() != esperado:
            raise SystemExit("%s baixado não confere com o sha256 esperado: recusado" % nome)
        with open(c, "wb") as f:
            f.write(dados)
        feitos.append(nome)
    return feitos


def copiar_motor():
    py = os.path.join(DESTINO, "py")
    if os.path.isdir(py):
        shutil.rmtree(py)
    os.makedirs(py)
    arqs = {}
    for m in MODULOS:
        shutil.copyfile(os.path.join(RAIZ, m + ".py"), os.path.join(py, m + ".py"))
        arqs[m + ".py"] = sha(os.path.join(py, m + ".py"))
    for d in DADOS:
        shutil.copyfile(os.path.join(RAIZ, d), os.path.join(py, d))
        arqs[d] = sha(os.path.join(py, d))
    for nome, sha_ in montar_pdfplumber(py).items():
        arqs[nome] = sha_
    os.makedirs(os.path.join(py, "fontes"))
    for f in sorted(os.listdir(os.path.join(RAIZ, "fontes"))):
        if f.endswith(".ttf") or f.startswith("LICENCA"):
            shutil.copyfile(os.path.join(RAIZ, "fontes", f), os.path.join(py, "fontes", f))
            arqs["fontes/" + f] = sha(os.path.join(py, "fontes", f))
    with open(os.path.join(RAIZ, "base_juridica.json"), encoding="utf-8") as f:
        bj = json.load(f).get("versao") or ""
    extras = {}
    ex = os.path.join(DESTINO, "extra")
    if os.path.isdir(ex):
        for f in sorted(os.listdir(ex)):
            extras[f] = sha(os.path.join(ex, f))
    info = {"versao": versao_apto(), "base_juridica": bj, "pyodide": PYODIDE_VERSAO, "arquivos": arqs, "extras": extras}
    with open(os.path.join(DESTINO, "motor.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1, sort_keys=True)
    return info


def baixar_pyodide():
    dest = os.path.join(DESTINO, "pyodide")
    if all(os.path.exists(os.path.join(dest, a)) for a in PYODIDE_ARQS):
        return False
    os.makedirs(dest, exist_ok=True)
    dados = urllib.request.urlopen(PYODIDE_TGZ, timeout=120).read()
    if hashlib.sha256(dados).hexdigest() != PYODIDE_SHA256:
        raise SystemExit("Pyodide baixado não confere com o sha256 fixado: pacote recusado")
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as t:
        for a in PYODIDE_ARQS:
            m = t.getmember("package/" + a)
            with t.extractfile(m) as src, open(os.path.join(dest, a), "wb") as out:
                shutil.copyfileobj(src, out)
    return True


if __name__ == "__main__":
    if "--sem-pyodide" not in sys.argv:
        print("Pyodide %s %s" % (PYODIDE_VERSAO, "baixado" if baixar_pyodide() else "já presente"))
        print("extras do resumo: %s" % (", ".join(baixar_extras()) or "já presentes"))
    info = copiar_motor()
    print("motor %s (base jurídica %s): %d arquivos, %d extras" % (info["versao"], info["base_juridica"], len(info["arquivos"]), len(info["extras"])))
