"""Extensão "APTO - RSPE do SEEU": manifesto (permissões mínimas, só o domínio do SEEU, sem conexão própria), sintaxe dos
scripts e as funções puras de comum.js (nº CNJ, nome de pasta seguro, caminho do arquivo, endereço aceito, chave do dia).
As funções JS rodam no node, se houver; sem node, só o manifesto é conferido."""
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(AQUI, "extensao_seeu")
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


m = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))
ok(m["manifest_version"] == 3, "manifesto v3")
ok(sorted(m["permissions"]) == ["downloads", "storage"], "permissões mínimas: %s" % m["permissions"])
ok(m["host_permissions"] == ["https://seeu.pje.jus.br/*", "https://seeu-transfer.s3.sa-east-1.amazonaws.com/*", "https://seeu-transfer.s3.amazonaws.com/*",
                             "https://app.siapen.ms.gov.br/*", "https://*.defensoria.ms.def.br/*", "http://127.0.0.1:47321/*"],
   "só o SEEU (e o servidor de arquivos do SEEU), o SIAPEN, o SAP da Defensoria e o APTO deste computador: %s" % m["host_permissions"])
ok([c["matches"] for c in m["content_scripts"]] == [["https://seeu.pje.jus.br/seeu/*"], ["https://app.siapen.ms.gov.br/*"], ["https://app.siapen.ms.gov.br/*"],
                                                   ["https://*.defensoria.ms.def.br/sap/*"]], "scripts só no SEEU, no SIAPEN e no SAP")
ok([c.get("world") for c in m["content_scripts"]] == [None, None, "MAIN", None] and m["content_scripts"][2]["js"] == ["siapen_pagina.js"],
   "só o siapen_pagina.js roda no mundo da página")
# SAP: só leitura - a lupa "Visualizar" (designar=0) é o único botão de linha clicado; nunca "Designar Assistido"
sap = open(os.path.join(EXT, "sap.js"), encoding="utf-8").read()
ok("bt-pesquisar" in sap and "'designar'\\s*:\\s*'0'" in sap and "bt-designar" not in sap and "bt-atendimentos" not in sap,
   "SAP: só a lupa Visualizar (designar=0)")
bg = open(os.path.join(EXT, "background.js"), encoding="utf-8").read()
ok("rspeAuto: true" in bg and 'if (!c.rspeAuto && !forcar && !lote) return { ok: false, motivo: "rspe automático desligado" };' in bg,
   "chave do RSPE automático: desligada, só o botão do painel (forcar) e o lote baixam")
# downloads da triagem (petição, planilha): o nome guardado pela página é sugerido pelo service worker (sem isso o
# Chrome nomeia pelo código interno do blob)
ok('"nomeBlob:" + item.url' in bg and 'sugerir({ filename: nome, conflictAction: "uniquify" })' in bg,
   "nome dos downloads da triagem aplicado no onDeterminingFilename")
tj = open(os.path.join(EXT, "triagem.js"), encoding="utf-8").read()
ok('chrome.storage.session.set({ ["nomeBlob:" + url]: n })' in tj, "a triagem guarda o nome do download antes de baixar")
ok('id="rspeAuto"' in open(os.path.join(EXT, "popup.html"), encoding="utf-8").read(), "opção do RSPE automático no painel")
ok(m["content_security_policy"]["extension_pages"].endswith("connect-src 'self' https://seeu.pje.jus.br https://seeu-transfer.s3.sa-east-1.amazonaws.com https://seeu-transfer.s3.amazonaws.com http://127.0.0.1:47321"),
   "conexão própria só com os arquivos da extensão (modelos), o SEEU, o servidor de arquivos do SEEU (PDF das movimentações) e o APTO deste computador")
for f in ["background.js", "content.js", "siapen.js", "siapen_pagina.js", "sap.js", "comum.js", "popup.js", "popup.html", "triagem.html", "triagem.js", "triagem_core.js"] + list(m["icons"].values()):
    ok(os.path.isfile(os.path.join(EXT, f)), "arquivo %s" % f)

node = shutil.which("node")
if node:
    for f in ("background.js", "content.js", "siapen.js", "siapen_pagina.js", "sap.js", "comum.js", "popup.js", "triagem_core.js"):
        r = subprocess.run([node, "--check", os.path.join(EXT, f)], capture_output=True, text=True)
        ok(r.returncode == 0, "sintaxe de %s: %s" % (f, r.stderr.strip()))
    js = r"""
const A = require(process.argv[1]);
const t = (c, m) => { if (!c) { console.log("FALHA: " + m); process.exitCode = 1; } };
t(A.cnj("Processo 0044586-22.2017.8.12.0001 (ATIVO)") === "0044586-22.2017.8.12.0001", "cnj formatado");
t(A.cnj("00445862220178120001") === "0044586-22.2017.8.12.0001", "cnj só dígitos");
t(A.cnj("sem número") === "", "cnj ausente");
t(A.pastaSegura('2ª VEP') === "2ª VEP", "acento e ª mantidos");
t(A.pastaSegura('a/b:c*?"<>|d. ') === "a b c d", "caracteres proibidos: " + A.pastaSegura('a/b:c*?"<>|d. '));
t(A.pastaSegura("CON") === "_CON", "nome reservado");
t(A.pastaSegura("..") === "", "só pontos");
const cfg = { raiz: "APTO", base: "2ª VEP" };
t(A.caminhoArquivo(cfg, "0044586-22.2017.8.12.0001", "2026-10-13") === "APTO/2ª VEP/0044586-22.2017.8.12.0001_2026-10-13.pdf", "caminho com base");
t(A.caminhoArquivo({ raiz: "" , base: "" }, "", "2026-10-13") === "APTO/RSPE_sem_numero_2026-10-13.pdf", "caminho sem base nem nº");
t(A.caminhoArquivo({ raiz: "../x", base: "../../Windows" }, "1", "2026-10-13").indexOf("..") < 0, "sem subir de pasta");
const U = A.urlRspeDoId("100000009157098", "relatorioSituacaoProcessualExecutoriaV2");
t(U === "https://seeu.pje.jus.br/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=100000009157098", "endereço do RSPE pelo id");
t(A.urlRspeValida(U), "url do RSPE");
t(!A.urlRspeValida(U.replace("https:", "http:")), "http recusado");
t(!A.urlRspeValida(U.replace("seeu.pje.jus.br", "seeu.pje.jus.br.evil.com")), "outro domínio recusado");
t(!A.urlRspeValida(U.replace("emitirRelatorioSituacaoProcessualExecutoria", "carregarJustificativa")), "outra ação do SEEU recusada");
t(!A.urlRspeValida("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do"), "outra página recusada");
// o link fica dentro do script do SEEU (gerarResaQuadroAcoes com o id; gerarResa com o id numa variável)
const h1 = "function gerarResaQuadroAcoes() { openWindow('/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=100000009157098','Visualizar Pdf',600,470); }";
const h2 = 'function gerarResa() { var idProcessoExecucaoPenal = 100000009157098; var acao = "/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=" + idProcessoExecucaoPenal;';
const h3 = 'var acao = "/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=carregarJustificativa&numeroProcesso=" + numeroProcesso;';
t(JSON.stringify(A.rspeNoHtml(h1)) === JSON.stringify({ id: "100000009157098", report: "relatorioSituacaoProcessualExecutoriaV2" }), "RSPE no script (id no endereço)");
t((A.rspeNoHtml(h2) || {}).id === "100000009157098", "RSPE no script (id na variável)");
t(A.rspeNoHtml(h3) === null, "outra ação não é RSPE");
t(A.ehPdf(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])) && !A.ehPdf(new Uint8Array([0x3c, 0x68, 0x74, 0x6d, 0x6c])), "PDF x página");
t(A.chaveDia(cfg, "00445862220178120001", "2026-10-13") === "0044586-22.2017.8.12.0001|2ª VEP|2026-10-13", "chave do dia");
t(/^\d{4}-\d{2}-\d{2}$/.test(A.hojeISO()), "data de hoje");
t(A.caminhoFicha(cfg, "joão da silva", "2026-10-13") === "APTO/2ª VEP/FD_JOÃO_DA_SILVA_2026-10-13.pdf", "caminho da ficha: " + A.caminhoFicha(cfg, "joão da silva", "2026-10-13"));
t(A.chaveFicha(cfg, "joão  da silva", "2026-10-13") === "FD:JOÃO DA SILVA|2ª VEP|2026-10-13", "chave da ficha");
// nºs de processo no texto do atendimento do SAP (com e sem pontuação; CPF não é nº de processo)
t(JSON.stringify(A.cnjsNoTexto("GR Nº 0000123-45.2014.8.12.0054 - e 00001234520148120054; PEP 7654321-00.2020.8.12.0001, cpf 123.456.789-09"))
  === JSON.stringify(["0000123-45.2014.8.12.0054", "7654321-00.2020.8.12.0001"]), "nºs CNJ do texto");
// listas em qualquer formato: cabeçalho, nome; mãe; CPF; ID; data; numeração; vírgula; repetidos
const L = A.pessoasDaLista("NOME;MÃE\nFulano de Tal ; Maria de Tal\n1. Beltrano Silva\t123.456.789-09\t4321\nNOME DO ASSISTIDO\nCiclano Souza, 01/02/1990, mãe: Ana Souza\n\nFulano de Tal ; Maria de Tal");
t(JSON.stringify(L) === JSON.stringify([{ nome: "FULANO DE TAL", mae: "MARIA DE TAL", cpf: "", num: "" }, { nome: "BELTRANO SILVA", mae: "", cpf: "12345678909", num: "4321" },
  { nome: "CICLANO SOUZA", mae: "ANA SOUZA", cpf: "", num: "" }]), "lista de pessoas: " + JSON.stringify(L));
"""
    r = subprocess.run([node, "-e", js, os.path.join(EXT, "comum.js")], capture_output=True, text=True)
    ok(r.returncode == 0 and "FALHA" not in r.stdout, "funções de comum.js: %s %s" % (r.stdout.strip(), r.stderr.strip()))

# APTO: cria Downloads\APTO\<base> para cada base, vigia Downloads\APTO sempre (além da pasta escolhida) e informa as bases
# à extensão em 127.0.0.1 (só para extensões; página da internet recebe 403)
import tempfile
import types
import urllib.request
import urllib.error
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
sys.path.insert(0, AQUI)
import rspe_app as app  # noqa: E402
tmp = tempfile.mkdtemp()
antigo = os.environ.get("USERPROFILE")
os.environ["USERPROFILE"] = tmp
try:
    api = app.Api.__new__(app.Api)
    conf = {}
    api._cfg = lambda: dict(conf)
    api._cfg_gravar = lambda **k: conf.update(k)
    api._js = lambda *a: None
    api.base = None
    api._vigia_ultima = ""
    api.vigia_info = lambda: {"bases": ["2ª VEP", "5ª vep"]}
    ext = os.path.join(tmp, "Downloads", "APTO")
    api._pastas_extensao()
    ok(os.path.isdir(os.path.join(ext, "2ª VEP")) and os.path.isdir(os.path.join(ext, "5ª vep")), "pastas das bases criadas em Downloads\\APTO")
    ok(api._vigia_raizes() == [ext], "sem pasta escolhida, vigia Downloads\\APTO: %s" % api._vigia_raizes())
    outra = os.path.join(tmp, "outra"); os.makedirs(outra)
    conf.update(pasta_vigiada=outra, vigiar=True)
    ok(api._vigia_raizes() == [outra, ext], "pasta escolhida e Downloads\\APTO: %s" % api._vigia_raizes())
    conf.update(pasta_vigiada=ext)
    ok(api._vigia_raizes() == [ext], "Downloads\\APTO escolhida: vigiada uma vez só")
    conf.update(vigiar=False)
    ok(api._vigia_raizes() == [], "pasta vigiada desativada: nada é lido")
    # Downloads como pasta escolhida: Downloads\APTO é lida a partir dela mesma (base = subpasta de APTO), não como base "APTO"
    conf.update(pasta_vigiada=os.path.join(tmp, "Downloads"), vigiar=True)
    rz = api._vigia_raizes()
    pdf = os.path.join(ext, "2ª VEP", "x.pdf"); open(pdf, "wb").write(b"%PDF-1.4")
    vistos = []
    for dp, subs, nomes in os.walk(rz[0]):
        subs[:] = [d for d in subs if not any(app._mesma_pasta(os.path.join(dp, d), x) for x in rz if app._dentro_da_pasta(x, rz[0]))]
        vistos += nomes
    ok("x.pdf" not in vistos and app.base_da_pasta(ext, pdf) == "2ª VEP", "subpasta de outra pasta vigiada fica com a sua base")
    # servidor para a extensão
    app.PORTA_EXTENSAO = 47399
    srv = api._extensao_servidor()
    ok(srv is not None, "servidor da extensão aberto")
    def pedir(caminho, origem=None):
        rq = urllib.request.Request("http://127.0.0.1:47399" + caminho, headers={"Origin": origem} if origem else {})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(rq, timeout=5) as r:
                return r.status, json.loads(r.read().decode("utf-8")), r.headers.get("Access-Control-Allow-Origin")
        except urllib.error.HTTPError as e:
            return e.code, None, None
    st, j, acao = pedir("/apto", "chrome-extension://abcdefghijklmnop")
    ok(st == 200 and j["bases"] == ["2ª VEP", "5ª vep"] and j["aberta"] == "" and acao == "chrome-extension://abcdefghijklmnop",
       "extensão recebe as bases: %s %s" % (st, j))
    ok(pedir("/apto", "https://site.qualquer")[0] == 403, "página da internet recebe 403")
    ok(pedir("/outra", "chrome-extension://abc")[0] == 403, "só /apto")
    api.base = types.SimpleNamespace(caminho=os.path.join(tmp, "bases", "2ª VEP.sqlite"))
    ok(pedir("/apto")[1]["aberta"] == "2ª VEP", "base aberta informada")
    if srv:
        srv.shutdown(); srv.server_close()
finally:
    if antigo is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = antigo
    shutil.rmtree(tmp, ignore_errors=True)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: extensão SEEU/SIAPEN/SAP (manifesto, permissões mínimas, sintaxe, nº do processo, pasta segura, caminho, endereço aceito, pastas e bases ligadas ao APTO, lista de pessoas, nºs do SAP)%s"
      % ("" if node else " - sem node: só o manifesto"))
