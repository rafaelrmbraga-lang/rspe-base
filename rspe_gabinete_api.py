"""Funções do APTO fora da Execução (Atendimentos, Quadro, Relatório), chamadas pela tela (pywebview) e pela extensão do navegador
(servidor local 127.0.0.1:47321). Entra na classe Api do rspe_app como mistura: usa self._janela e self._js de lá.

A tela de Atendimentos é o painel da extensão APTO Atendimentos (pasta "atendimentos", numa moldura da aba): o que ele gravava no
navegador passa a ir para a base do gabinete (rspe_gabinete), e os pedidos ao SAP (Chamar, Ver no SAP, Ler a fila) passam pela
extensão, que continua só lendo o SAP."""
import base64
import json
import logging
import os
import re
import threading
import time
import webbrowser

import webview

import rspe_gabinete as rgab

LOG = logging.getLogger("rspe")
MAX_CORPO = 4 * 1024 * 1024          # tamanho máximo de um pedido da extensão
LINKS_PERMITIDOS = ("https://wa.me/", "https://api.whatsapp.com/")


class GabineteApi:
    """Mistura da Api: precisa de self._janela, self._js, self._pasta_dados e self._recurso (definidos no rspe_app)."""

    _gab = None
    _gab_trava = threading.Lock()
    _cmd = None
    _sap_aberto = None

    # ---- base do gabinete ----
    def _gabinete(self):
        with self._gab_trava:
            if self._gab is None:
                self._gab = rgab.Gabinete(os.path.join(self._pasta_dados, "gabinete.sqlite"))
                self._gab.copia_do_dia(os.path.join(self._pasta_dados, "copias", "gabinete"))
            return self._gab

    def _comandos(self):
        if self._cmd is None:
            self._cmd = rgab.Comandos()
            threading.Thread(target=self._sap_vigiar, daemon=True).start()
        return self._cmd

    def _atd_evento(self, tipo, dados):
        self._js("window.ui && ui.atdEvento && ui.atdEvento(%s)" % json.dumps({"evento": tipo, "dados": dados}, ensure_ascii=False))

    def _sap_vigiar(self):
        """Avisa a tela quando a aba do SAP (com a extensão) aparece ou some."""
        while True:
            time.sleep(2)
            est = self._cmd.estado()
            if est["aberto"] != self._sap_aberto:
                self._sap_aberto = est["aberto"]
                self._atd_evento("sap", est)

    # ---- chamadas da tela (o painel, pela moldura) ----
    def atd_tudo(self):
        d = self._gabinete().tudo()
        d["sap"] = self._comandos().estado()
        return d

    def atd_mudar(self, diff):
        if not isinstance(diff, dict):
            return {"erro": "mudança inválida"}
        self._gabinete().mudar(diff)
        return {"ok": True}

    def atd_sap(self, tipo, dados=None):
        """Chamar / Ver no SAP / Ler a fila: o pedido vai para a extensão, que age na aba do SAP aberta e responde."""
        return self._comandos().pedir(tipo, dados or {})

    def atd_arquivo(self, caminho):
        """Arquivo do painel (modelo do relatório em Word, fontes, modelos de petição) em base64.
        Os modelos de petição (pasta "modelos") ficam fora do programa: na pasta "modelos_atendimentos" ao lado das bases."""
        c = str(caminho or "").replace("\\", "/").lstrip("/")
        if not c or ".." in c.split("/"):
            return {"erro": "caminho inválido"}
        if c.startswith("modelos/"):
            raiz = os.path.join(self._pasta_dados, "modelos_atendimentos")
            p = os.path.join(raiz, *c.split("/")[1:])
            if not os.path.isfile(p):
                return {"erro": 'modelo não encontrado. Copie a pasta "modelos" da extensão APTO Atendimentos para %s' % raiz}
        else:
            raiz = self._recurso("atendimentos")
            p = os.path.join(raiz, *c.split("/"))
        if not os.path.abspath(p).startswith(os.path.abspath(raiz)) or not os.path.isfile(p):
            return {"erro": "arquivo não encontrado: " + c}
        with open(p, "rb") as f:
            return {"b64": base64.b64encode(f.read()).decode("ascii")}

    # pastas de gravação escolhidas na tela (só neste computador)
    def _pastas(self):
        return self._gabinete().kv("pastas_locais", {}) or {}

    def atd_pastas(self):
        p = self._pastas()
        return {k: {"caminho": p.get(k, ""), "nome": os.path.basename(p.get(k, "").rstrip("\\/"))} for k in ("relatorio", "peticoes")}

    def atd_escolher_pasta(self, tipo):
        if tipo not in ("relatorio", "peticoes"):
            return {"erro": "pasta desconhecida"}
        d = self._janela.create_file_dialog(webview.FOLDER_DIALOG) if self._janela else None
        d = d[0] if isinstance(d, (list, tuple)) and d else d
        if not d:
            return {"cancelado": True}
        p = self._pastas()
        p[tipo] = d
        self._gabinete().gravar_kv("pastas_locais", p)
        return self.atd_pastas()

    def atd_limpar_pasta(self, tipo):
        p = self._pastas()
        p.pop(tipo, None)
        self._gabinete().gravar_kv("pastas_locais", p)
        return self.atd_pastas()

    def atd_salvar_arquivo(self, nome, b64, tipo="", mes=None, substituir=False):
        """Grava um arquivo gerado no painel. Relatório do dia: na pasta do mês dentro da pasta escolhida; petição: na pasta escolhida;
        sem pasta escolhida (ou planilha, backup): pergunta onde salvar."""
        nome = re.sub(r'[\\/:*?"<>|]+', " ", str(nome or "arquivo")).strip() or "arquivo"
        try:
            dados = base64.b64decode(b64 or "")
        except (ValueError, TypeError):
            return {"erro": "arquivo inválido"}
        pasta = self._pastas().get({"relatorio": "relatorio", "peticao": "peticoes"}.get(tipo, ""), "")
        alvo = None
        if pasta and os.path.isdir(pasta):
            try:
                destino = rgab.pasta_do_mes(pasta, int(mes)) if tipo == "relatorio" and mes is not None else pasta
                alvo = os.path.join(destino, nome)
                if os.path.exists(alvo) and not substituir:
                    return {"existe": True, "caminho": alvo}
            except (OSError, ValueError) as e:
                LOG.warning("atendimentos: pasta %s: %s", pasta, e)
                alvo = None
        if not alvo:
            ext = os.path.splitext(nome)[1].lower()
            tipos = {".docx": ("Word (*.docx)",), ".pdf": ("PDF (*.pdf)",), ".csv": ("Planilha (*.csv)",), ".json": ("Cópia (*.json)",)}.get(ext, ("Todos (*.*)",))
            c = self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=tipos) if self._janela else None
            c = c[0] if isinstance(c, (list, tuple)) and c else c
            if not c:
                return {"cancelado": True}
            alvo = c
        try:
            with open(alvo, "wb") as f:
                f.write(dados)
        except OSError as e:
            return {"erro": "não foi possível gravar em %s (%s)" % (alvo, e)}
        return {"ok": True, "caminho": alvo}

    def atd_abrir_link(self, url):
        u = str(url or "")
        if not u.startswith(LINKS_PERMITIDOS):
            return {"erro": "link não permitido"}
        webbrowser.open(u)
        return {"ok": True}

    # ---- pedidos da extensão (servidor local) ----
    def _ext_get(self, caminho):
        if caminho == "/atd/comando":
            return {"cmd": self._comandos().proximo()}
        return None

    def _ext_post(self, caminho, corpo):
        if caminho == "/atd/fila":
            r = self._gabinete().receber_fila(corpo.get("itens") or [])
            if r["mudados"]:
                self._atd_evento("mudou", {"atendimentos": {"upsert": r["mudados"]}})
            return {"ok": True, "novos": r["novos"], "resumo": self._gabinete().resumo_dia()}
        if caminho == "/atd/fato":
            a = self._gabinete().receber_fato(corpo)
            if a:
                self._atd_evento("mudou", {"atendimentos": {"upsert": [a]}})
            return {"ok": bool(a), "resumo": self._gabinete().resumo_dia()}
        if caminho == "/atd/resposta":
            ok = self._comandos().responder(int(corpo.get("id") or 0), corpo.get("resposta"))
            return {"ok": ok}
        if caminho == "/atd/leitura":
            self._comandos().leitura = {"msg": str(corpo.get("msg") or "")[:300], "lendo": bool(corpo.get("lendo")), "quando": time.time()}
            self._atd_evento("sap", self._comandos().estado())
            return {"ok": True}
        return None
