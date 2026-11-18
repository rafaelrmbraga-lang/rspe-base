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
MODULOS = ["rspe_painel", "rspe_motor", "rspe_scraper", "rspe_view", "rspe_ficha", "rspe_regras", "rspe_decretos", "rspe_prescricao",
           "rspe_auditoria", "rspe_reincidencia", "rspe_remicao", "rspe_calc", "rspe_indulto_tl"]
DADOS = ["base_juridica.json"]
PYODIDE_VERSAO = "0.27.7"  # Python 3.12.7, o mesmo 3.12 da compilação do APTO (.github/workflows/build.yml)
PYODIDE_TGZ = "https://registry.npmjs.org/pyodide/-/pyodide-%s.tgz" % PYODIDE_VERSAO
PYODIDE_SHA256 = "89d5d952675eb08e11286e52c7238f1248ce71726e896db9703e73bef23dc343"  # sha256 do .tgz do npm (conferido ao baixar)
PYODIDE_ARQS = ["pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "package.json"]
# a leitura de PDF não entra no painel: o motor só importa o pdfplumber (usado para ler arquivos, nunca no cálculo)
STUB_PDFPLUMBER = '"""Substituto do pdfplumber no painel do SEEU: o motor não lê PDF (a leitura é do APTO)."""\n\n\ndef open(*a, **k):\n    raise RuntimeError("leitura de PDF indisponível no painel")\n'


def sha(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def versao_apto():
    with open(os.path.join(RAIZ, "rspe_app.py"), encoding="utf-8") as f:
        return re.search(r'^VERSAO = "([^"]+)"', f.read(), re.M).group(1)


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
    with open(os.path.join(py, "pdfplumber.py"), "w", encoding="utf-8") as f:
        f.write(STUB_PDFPLUMBER)
    arqs["pdfplumber.py"] = sha(os.path.join(py, "pdfplumber.py"))
    with open(os.path.join(RAIZ, "base_juridica.json"), encoding="utf-8") as f:
        bj = json.load(f).get("versao") or ""
    info = {"versao": versao_apto(), "base_juridica": bj, "pyodide": PYODIDE_VERSAO, "arquivos": arqs}
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
    info = copiar_motor()
    print("motor %s (base jurídica %s): %d arquivos" % (info["versao"], info["base_juridica"], len(info["arquivos"])))
    if "--sem-pyodide" not in sys.argv:
        print("Pyodide %s %s" % (PYODIDE_VERSAO, "baixado" if baixar_pyodide() else "já presente"))
