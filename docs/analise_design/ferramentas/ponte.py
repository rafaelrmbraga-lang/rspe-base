import os
"""Ponte local: carrega ui.html no Chromium (Playwright) e liga window.__mockApi à classe Api REAL do rspe_app.py,
no mesmo processo. Data de referência fixa em 12/10/2026 (a mesma dos casos simulados). Só dados fictícios."""
import sys, os, json, types, tempfile, queue, traceback
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "casos_simulados"))
wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0; sys.modules["webview"] = wv
import roda_casos  # noqa: fixa datetime.now() em 12/10/2026 dentro do rspe_app
import rspe_app as app
import urllib.request
def _offline(*a, **k):
    raise OSError("sem rede (simulação offline)")
urllib.request.urlopen = _offline  # o app é usado offline; evita travar baixando dados prisionais/legislação

TMP = tempfile.mkdtemp(prefix="apto_ui_")
for _n in os.listdir(REPO):  # recursos do programa (teses_auto.bin, base_juridica.json, fontes...) ao lado da config temporária
    if not _n.endswith(".sqlite") and not os.path.exists(os.path.join(TMP, _n)):
        os.symlink(os.path.join(REPO, _n), os.path.join(TMP, _n))
app.pasta_app = lambda: TMP
app.CONFIG = os.path.join(TMP, "c.json")
app._abrir = lambda c: None
SAIDA = os.path.join(TMP, "saidas"); os.makedirs(SAIDA, exist_ok=True)

MOCK = r"""
(() => {
  const run = (js) => { (js||[]).forEach(c => { try { (0,eval)(c); } catch(e) { console.log('js ponte', e); } }); };
  window.__mockApi = new Proxy({}, { get: (t, k) => {
    if (k === 'then' || typeof k !== 'string') return undefined;
    return (...a) => window.__py(k, JSON.stringify(a)).then(s => { const o = JSON.parse(s); setTimeout(() => run(o.js), 0); if (o.exc) throw new Error(o.exc); return o.r; });
  }});
  setInterval(() => { if (window.__pump) window.__pump().then(s => run(JSON.parse(s))); }, 250);
})();
"""


class Janela:
    def __init__(self):
        self.q = queue.Queue()
        self.dialogo = None  # resposta do próximo diálogo de arquivo

    def evaluate_js(self, c):
        self.q.put(c)

    def create_file_dialog(self, tipo, **kw):
        r = self.dialogo
        if callable(r):
            r = r(tipo, kw)
        return r

    def drena(self):
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                return out


def criar(base=None):
    """Cria a Api e abre a base ANTES de iniciar o Playwright (dentro do laço do Playwright a abertura trava)."""
    api = app.Api()
    jan = Janela()
    api._janela = jan
    if base:
        api.abrir_base(base)
    return api, jan


def ligar(page, api, jan):

    def py(nome, args):
        try:
            r = getattr(api, nome)(*json.loads(args))
            return json.dumps({"r": r, "js": jan.drena()}, ensure_ascii=False, default=str)
        except Exception as e:
            traceback.print_exc()
            return json.dumps({"r": None, "exc": repr(e), "js": jan.drena()})

    page.expose_function("__py", py)
    page.expose_function("__pump", lambda: json.dumps(jan.drena()))
    page.add_init_script(MOCK)
    return api, jan


def abrir(page, api, jan):
    ligar(page, api, jan)
    page.goto("file://" + os.path.join(REPO, "ui.html"))
    return api, jan
