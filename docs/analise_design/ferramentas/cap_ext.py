import os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import os
import json, os, subprocess, time, sys
from playwright.sync_api import sync_playwright

EXT = os.path.join(REPO, "extensao_seeu")
OUT = os.path.join(REPO, "docs", "analise_design", "capturas")
PORT = 47999
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1", "-d", REPO],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
BASE = f"http://127.0.0.1:{PORT}/extensao_seeu/"

STUB = r"""
(() => {
  const C = window.__CEN = %s;
  const listeners = [];
  window.__listeners = listeners;
  const store = Object.assign({}, C.storage || {});
  window.chrome = {
    runtime: {
      id: "fake", getURL: (p) => location.origin + "/extensao_seeu/" + p,
      sendMessage: async (m) => {
        const r = (C.respostas || {})[m.tipo];
        if (m.tipo === "cfg") return C.cfgPagina || { avisoNaPagina: true };
        return r === undefined ? { ok: true } : JSON.parse(JSON.stringify(r));
      },
      onMessage: { addListener: (f) => listeners.push(f) },
    },
    tabs: {
      query: async () => C.abas || [],
      sendMessage: async (id, m) => { const r = (C.tabResp || {})[m.tipo]; if (r === "throw") throw new Error("x"); return r; },
      create: async () => ({}),
    },
    storage: { local: {
      get: async (k) => { const ks = Array.isArray(k) ? k : [k]; const o = {}; ks.forEach((x) => { if (x in store) o[x] = store[x]; }); return o; },
      set: async (o) => { Object.assign(store, o); },
    } },
    action: { setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {} },
  };
  window.close = () => {};
  window.prompt = () => null;
})();
"""

agora = int(time.time() * 1000)
P = lambda i: f"000{i:04d}-12.2025.8.12.0001"
cfg = {"ativo": True, "raiz": "APTO", "base": "@apto", "bases": ["Mutirão Fictício"], "avisoNaPagina": True}
apto_ok = {"ok": True, "bases": ["PED Fictício", "Presídio Modelo"], "aberta": "PED Fictício"}
log = [
    {"quando": agora - 60000, "processo": P(1), "base": "PED Fictício", "status": "ok"},
    {"quando": agora - 3600000, "processo": P(2), "base": "PED Fictício", "status": "ok", "manual": True},
    {"quando": agora - 7200000, "processo": P(3), "base": "PED Fictício", "status": "erro", "msg": "o SEEU não devolveu um PDF (sessão expirada?)"},
]
est = {"cfg": cfg, "apto": apto_ok, "log": log, "pausadoAte": 0, "hoje": 2}
seeu_tab = [{"id": 1, "url": "https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?x"}]

def popup_cen(**kw):
    c = {"respostas": {"estado": est, "loteEstado": None}, "abas": seeu_tab, "tabResp": {}}
    for k, v in kw.items():
        if k in ("estado", "loteEstado"): c["respostas"][k] = v
        else: c[k] = v
    return c

cenarios = {
    "inicial": (popup_cen(), None),
    "apto_fechado": (popup_cen(estado=dict(est, apto={"ok": False, "bases": [], "aberta": ""}, log=[], hoje=0)), None),
    "sucesso": (popup_cen(tabResp={"procurar": {"achou": True, "ok": True, "arquivo": "APTO/PED Fictício/" + P(1) + "_2026-10-22.pdf"}}), "#agora"),
    "erro_sem_seeu": (popup_cen(abas=[{"id": 1, "url": "https://www.google.com/"}]), "#agora"),
    "erro_rspe_nao_achado": (popup_cen(tabResp={"procurar": "throw"}), "#agora"),
    "desligada": (popup_cen(estado=dict(est, cfg=dict(cfg, ativo=False))), "#agora"),
    "pausada": (popup_cen(estado=dict(est, pausadoAte=agora + 600000, log=[{"quando": agora - 1000 * i, "processo": P(i), "base": "PED Fictício", "status": "erro", "msg": "sessão expirada: faça login no SEEU - extensão pausada por 10 minutos"} for i in range(1, 4)])), None),
    "lote_seeu": (popup_cen(loteEstado={"rodando": True, "sistema": "seeu", "base": "PED Fictício", "itens": [
        {"n": P(1), "status": "ok"}, {"n": P(2), "status": "repetido"}, {"n": P(3), "status": "erro", "msg": "processo não encontrado no SEEU"},
        {"n": P(4), "status": "rodando"}, {"n": P(5), "status": "fila"}, {"n": P(6), "status": "fila"}], "sapNomes": {}, "temSap": False}), None),
    "lote_sap": (popup_cen(loteEstado={"rodando": False, "sistema": "sap", "base": "PED Fictício", "itens": [
        {"n": "FULANO DE TAL", "status": "ok", "msg": P(7) + " · último atendimento 10/09/2026"},
        {"n": "BELTRANO DA SILVA", "status": "erro", "msg": "2 homônimos sem mãe na lista: não escolhido"},
        {"n": "CICRANO SOUZA", "status": "ok", "msg": P(8) + " · último atendimento 02/08/2026"}], "sapNomes": {}, "temSap": True}), None),
}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    alturas = {}
    for nome, (cen, clique) in ([] if os.environ.get('SO_AVISO') else cenarios.items()):
        pg = b.new_page(viewport={"width": 360, "height": 600}, device_scale_factor=1)
        pg.add_init_script(STUB % json.dumps(cen))
        pg.goto(BASE + "popup.html")
        pg.wait_for_timeout(500)
        if clique: pg.click(clique); pg.wait_for_timeout(400)
        if nome.startswith("lote"):
            pg.evaluate("document.getElementById('loteBox').open = true")
            pg.wait_for_timeout(300)
        alturas[nome] = pg.evaluate("document.documentElement.scrollHeight")
        pg.screenshot(path=f"{OUT}/extensao_popup_{nome}.png", full_page=True)
        if nome == "inicial":
            pg.screenshot(path=f"{OUT}/extensao_popup_inicial_600px.png", full_page=False)
            # foco por teclado
            for _ in range(3): pg.keyboard.press("Tab")
            pg.screenshot(path=f"{OUT}/extensao_popup_foco_teclado.png", clip={"x": 0, "y": 0, "width": 360, "height": 200})
            # dropdown text
            alturas["opcoes_select"] = pg.evaluate("[...document.querySelectorAll('#base option')].map(o=>o.text)")
        pg.close()
    print(json.dumps(alturas, ensure_ascii=False))
    if os.environ.get("SO_AVISO"): linhas=[]

    # triagem
    linhas, an = [], {}
    nomes = ["FULANO DE TAL", "BELTRANO DA SILVA", "CICRANO SOUZA", "JOÃO FICTÍCIO", "MARIA EXEMPLO"]
    defs = ["Defensor(a) A", "Defensor(a) B", "Defensor(a) A", "", "Defensor(a) B"]
    datas = ["22/10/2026", "24/10/2026", "30/10/2026", "21/10/2026", "05/11/2026"]
    for i in range(5):
        l = {"aba": 5 if i % 2 == 0 else 2, "processo": P(10 + i), "final": (10 + i) % 10, "executado": nomes[i], "defensor": defs[i],
             "ultimoDia": datas[i], "prazo": "10 dias", "dataEnvio": "10/10/2026", "url": "#", "classe": "Execução da Pena", "assunto": "", "seq": 30 + i}
        linhas.append(l)
    def k(l): return f"{l['aba']}|{l['processo']}"
    an[k(linhas[0])] = {"status": "ok", "quando": agora, "tipoMotivo": "Cálculo", "pendencia": {"movimento": "Juntada de Cálculo de Pena", "texto": "Manifestar sobre cálculo", "juntar": "Manifestação"},
        "motivo": {"seq": 40, "data": "08/10/2026", "nome": "Juntada de Cálculo", "doc": {"resumo": "Cálculo de liquidação de penas atualizado, data-base fictícia.", "alertas": [{"nivel": "alto", "txt": "falta grave reconhecida"}], "temas": ["cálculo"]}},
        "decisao": {"seq": 38, "data": "01/10/2026", "nome": "Decisão interlocutória", "doc": {"resumo": "Homologo o cálculo fictício de penas...", "alertas": [{"nivel": "medio", "txt": "regressão cautelar"}], "temas": ["regime"]}},
        "alertas": [{"nivel": "alto", "txt": "falta grave reconhecida"}, {"nivel": "medio", "txt": "regressão cautelar"}, {"nivel": "info", "txt": "remição pendente"}], "temas": ["cálculo", "regime"], "desde": [], "mesma": False}
    an[k(linhas[1])] = {"status": "erro", "erro": "movimentações não encontradas na página do processo", "quando": agora}
    an[k(linhas[2])] = {"status": "rodando"}
    an[k(linhas[3])] = {"status": "ok", "quando": agora, "tipoMotivo": "Progressão", "pendencia": {"movimento": "Pedido de progressão", "texto": "x"},
        "motivo": {"seq": 12, "data": "15/10/2026", "nome": "Pedido", "doc": {"resumo": "Requer progressão ao regime semiaberto (texto fictício).", "alertas": [], "temas": []}},
        "decisao": None, "alertas": [], "temas": ["progressão"], "desde": [], "mesma": False}
    tcen = {"abas": seeu_tab, "tabResp": {"triagemPing": {"ok": True, "logado": True}},
            "storage": {"triagemUltima": {"quando": agora, "situacao": 1, "linhas": linhas, "analises": an}}}
    for nome, cen in {"triagem_vazia": {"abas": [], "tabResp": {}}, "triagem_com_dados": tcen}.items():
        pg = b.new_page(viewport={"width": 1366, "height": 768})
        pg.add_init_script(STUB % json.dumps(cen))
        pg.goto(BASE + "triagem.html")
        pg.wait_for_timeout(1200)
        pg.screenshot(path=f"{OUT}/extensao_{nome}.png", full_page=True)
        if nome == "triagem_com_dados":
            pg.click("tr.l >> nth=0"); pg.wait_for_timeout(300)
            pg.screenshot(path=f"{OUT}/extensao_triagem_detalhe.png", full_page=True)
            pg.set_viewport_size({"width": 800, "height": 768}); pg.wait_for_timeout(300)
            pg.screenshot(path=f"{OUT}/extensao_triagem_800px.png", full_page=False)
        pg.close()

    # toast injetado no SEEU fictício
    fake = """<!doctype html><html><head><meta charset=utf-8><title>SEEU - Processo 0000001-12.2025.8.12.0001</title>
<style>body{margin:0;font:12px Verdana,Arial,sans-serif;background:#f2f2f2}#top{background:#1f4f7a;color:#fff;padding:10px 16px;font-weight:bold}
.box{background:#fff;margin:14px;border:1px solid #ccc;padding:12px}.box h3{margin:0 0 8px;color:#1f4f7a}table{border-collapse:collapse;width:100%}td{border:1px solid #ddd;padding:5px}
.btn{display:inline-block;background:#e9e9e9;border:1px solid #aaa;padding:4px 10px;margin:4px}</style></head><body>
<div id=top>SEEU · Sistema Eletrônico de Execução Unificado (página fictícia de teste)</div>
<input type=hidden id=processoNumeroFormatado value="00000011220258120001">
<div class=box><h3 id=informacoesProcessuais>Processo 0000001-12.2025.8.12.0001 — FULANO DE TAL (fictício)</h3>
<span class=btn>Situação Carcerária</span><span class=btn>Movimentações</span><span class=btn>Partes</span>
<table>""" + "".join(f"<tr><td>{i}</td><td>{20-i}/09/2026</td><td>Movimento fictício {i}</td><td>Servidor</td></tr>" for i in range(1, 22)) + """</table></div>
<script src="/extensao_seeu/comum.js"></script><script src="/extensao_seeu/content.js"></script></body></html>"""
    fpath = os.path.join(REPO, "docs", "analise_design", "capturas", "_seeu_ficticio.html")
    open(fpath, "w").write(fake)
    for nome, (txt, erro) in {"seeu_aviso_ok": ("APTO: RSPE salvo em Downloads\\APTO\\PED Fictício\\0000001-12.2025.8.12.0001_2026-10-22.pdf", False),
                              "seeu_aviso_erro": ("APTO: pausada depois de falhas seguidas; faça login no SEEU e clique em \"retomar\" no ícone do APTO", True)}.items():
        pg = b.new_page(viewport={"width": 1280, "height": 560})
        pg.add_init_script(STUB % json.dumps({"respostas": {"processoVisto": {"ok": True}, "podeBaixar": {"ok": False, "motivo": "desligada"}}}))
        pg.goto(f"http://127.0.0.1:{PORT}/docs/analise_design/capturas/_seeu_ficticio.html")
        pg.wait_for_timeout(500)
        pg.evaluate("([t,e]) => window.__listeners.forEach(f => f({tipo:'aviso', texto:t, erro:e}, {}, ()=>{}))", [txt, erro])
        pg.wait_for_timeout(500)
        pg.screenshot(path=f"{OUT}/extensao_injetado_{nome}.png")
        pg.screenshot(path=f"{OUT}/extensao_injetado_{nome}_zoom.png", clip={"x": 880, "y": 460, "width": 400, "height": 100})
        pg.close()
    os.remove(fpath)
    b.close()
srv.terminate()
