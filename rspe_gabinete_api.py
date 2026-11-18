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
import rspe_nuspen as rnus
import rspe_sei as rsei
import rspe_seeu as rseeu

LOG = logging.getLogger("rspe")
MAX_CORPO = 20 * 1024 * 1024         # tamanho máximo de um pedido da extensão (um lote do SEI tem até 25 documentos)
LINKS_PERMITIDOS = ("https://wa.me/", "https://api.whatsapp.com/")


ABAS_MESA = {"5": "Manifestação", "2": "Ciência", "7": "Razões/Contrarrazões"}


def _opcoes_mesa(o, guardar=False):
    """Só o que a triagem aceita: abas (5, 2, 7), situação (1 a 3), etapa (1 ou 2), reler tudo e os filtros da etapa 2."""
    o = o if isinstance(o, dict) else {}
    s = lambda v, n=80: str(v or "")[:n]
    r = {"abas": [a for a in (o.get("abas") or []) if str(a) in ABAS_MESA][:3], "situacao": s(o.get("situacao"), 1) if s(o.get("situacao"), 1) in ("1", "2", "3") else "1",
         "forcar": bool(o.get("forcar")), "faixa": re.sub(r"[^0-9,;\- ]", "", s(o.get("faixa"), 40)),
         "defensores": [s(d, 120) for d in (o.get("defensores") or []) if d][:30], "tipo": s(o.get("tipo"), 60), "prov": s(o.get("prov"), 60), "busca": s(o.get("busca"), 80)}
    if guardar:
        r["faixas"] = [{"nome": s(f.get("nome"), 40), "faixa": re.sub(r"[^0-9,;\- ]", "", s(f.get("faixa"), 40))} for f in (o.get("faixas") or []) if isinstance(f, dict) and f.get("nome")][:20]
    else:
        r["etapa"] = "2" if str(o.get("etapa")) == "2" else "1"
    return r


class GabineteApi:
    """Mistura da Api: precisa de self._janela, self._js, self._pasta_dados e self._recurso (definidos no rspe_app)."""

    _gab = None
    _sei_obj = None
    _nus_obj = None
    _gab_trava = threading.Lock()
    _cmd = None
    _sap_aberto = None
    _seeu_obj = None
    _cmds = None          # SEI e SEEU: {sistema: Comandos}
    _andamento = None     # SEI e SEEU: último andamento da leitura informado pela extensão

    # ---- base do gabinete ----
    def _gabinete(self):
        with self._gab_trava:
            if self._gab is None:
                self._gab = rgab.Gabinete(os.path.join(self._pasta_dados, "gabinete.sqlite"))
                self._gab.copia_do_dia(os.path.join(self._pasta_dados, "copias", "gabinete"))
            return self._gab

    def _sei(self):
        g = self._gabinete()
        with self._gab_trava:
            if self._sei_obj is None:
                self._sei_obj = rsei.Sei(g)
            return self._sei_obj

    def _nus(self):
        g = self._gabinete()
        self._sei()  # as tabelas do SEI antes das da gestão
        with self._gab_trava:
            if self._nus_obj is None:
                self._nus_obj = rnus.Nuspen(g)
            return self._nus_obj

    def sei_importar_pdf(self, quem="", caminhos=None):
        """PDF do processo do SEI (ou anexo): escolhidos na janela; cada um é lido, separado pelo rodapé e analisado (sugestões)."""
        if not caminhos:
            c = self._janela.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=("PDF (*.pdf)",)) if self._janela else None
            caminhos = list(c or [])
        if not caminhos:
            return {"cancelado": True}
        out = [self._sei().importar_pdf(c, os.path.join(self._pasta_dados, "originais_sei"), quem) for c in caminhos[:50]]
        self._js("window.ui && ui.seiEvento && ui.seiEvento({})")
        return {"ok": True, "arquivos": out}

    def nus(self, metodo, args=None):
        """Gestão do NUSPEN (demandas, providências, prazos, comunicações, inspeções, minutas, histórico): um ponto de entrada
        para a tela, só com os métodos públicos (rspe_nuspen.PUBLICOS); regra do domínio volta como {"erro": ...}."""
        if metodo not in rnus.PUBLICOS:
            return {"erro": "função desconhecida"}
        a = args if isinstance(args, list) else ([] if args is None else [args])
        N = self._nus()
        try:
            r = getattr(N, metodo)(*a)
        except rnus.Erro as e:
            N.tirar_mudancas()
            return {"erro": str(e)}
        except (TypeError, ValueError) as e:
            N.tirar_mudancas()
            logging.getLogger("rspe").exception("nus %s", metodo)
            return {"erro": "dados inválidos (%s)" % e}
        if metodo in ("prazo_decidir", "prazo_completar", "prazo_alterar", "prazo_registrar", "obrigacao_decidir", "em_lote"):
            N.sincronizar_quadro()  # o cartão do Quadro acompanha o vencimento validado
        m = N.tirar_mudancas()
        if m:
            self._atd_evento("mudou", {"pecas": m})
        if metodo not in ("obrigacoes", "demandas", "prazos", "lacunas", "comunicacoes", "inspecoes", "regras", "modelos", "historico_geral", "buscar",
                          "obrigacao", "demanda", "inspecao", "minuta", "painel", "relatorio", "escolhas", "quem_lista", "comparar", "historico_de",
                          "o_que_mudou", "novidades", "perguntas", "consultar", "arquivos_pdf"):
            self._js("window.ui && ui.nusMudou && ui.nusMudou(%s)" % json.dumps(metodo))
        return r if r is not None else {"erro": "não encontrado"}

    def _seeu(self):
        g = self._gabinete()
        with self._gab_trava:
            if self._seeu_obj is None:
                self._seeu_obj = rseeu.Seeu(g)
            return self._seeu_obj

    def _cmd_de(self, sist):
        """Fila de pedidos da tela para a aba do SEI ou do SEEU (a do SAP é _comandos)."""
        with self._gab_trava:
            if self._cmds is None:
                self._cmds = {"sei": rgab.Comandos(rgab.TIPOS_SEI, rgab.AVISO_SEI, "SEI"), "seeu": rgab.Comandos(rgab.TIPOS_SEEU, rgab.AVISO_SEEU, "SEEU")}
                self._andamento = {"sei": None, "seeu": None}
                threading.Thread(target=self._abas_vigiar, daemon=True).start()
            return self._cmds[sist]

    def _abas_vigiar(self):
        """Avisa a tela quando a aba do SEI ou do SEEU (com a extensão) aparece ou some."""
        antes = {}
        while True:
            time.sleep(2)
            for sist, c in self._cmds.items():
                aberto = c.estado()["aberto"]
                if antes.get(sist) != aberto:
                    antes[sist] = aberto
                    self._js("window.ui && ui.%sEvento && ui.%sEvento(%s)" % (sist, sist, json.dumps({"estado": self._estado_leitura(sist)}, ensure_ascii=False)))

    def _estado_leitura(self, sist):
        c = self._cmd_de(sist)
        return {"aberto": c.estado()["aberto"], "andamento": self._andamento.get(sist)}

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

    # ---- SEI (função SEI): o que a extensão leu no SEI ----
    def sei_resumo(self):
        return self._sei().resumo()

    def sei_processo(self, numero):
        return self._sei().processo(str(numero or "")) or {"erro": "processo não encontrado"}

    def sei_decidir(self, oid, status, motivo=""):
        return self._sei().decidir(oid, status, motivo)

    def sei_para_quadro(self, oid):
        """A obrigação vira um cartão do Quadro (fila "A fazer"), com o processo SEI e o prazo como está no documento."""
        o = self._sei().obrigacao(oid)
        if not o:
            return {"erro": "obrigação desconhecida"}
        if o["quadro"]:
            return {"erro": "já está no Quadro"}
        prazo = (" · prazo no documento: %s %s (sem vencimento calculado)" % (o["prazo_quantidade"], o["prazo_unidade"])) if o["prazo_quantidade"] is not None else ""
        p = {"id": rgab.novo_id(), "tipo": "", "processo": "SEI " + o["processo"], "nome": "SEI " + o["processo"], "data": rgab.hoje_iso(),
             "status": "pendente", "coluna": "fazer", "prazo": "", "obs": (o["descricao"] + prazo)[:500], "origem": "sei", "atendimentoId": "",
             "criadoEm": int(time.time() * 1000)}
        self._gabinete().mudar({"pecas": {"upsert": [p]}})
        self._sei().marcar_quadro(oid, p["id"])
        N = self._nus()
        N.sincronizar_quadro()  # já com o vencimento, se houver prazo validado
        m = N.tirar_mudancas() or {"upsert": []}
        self._atd_evento("mudou", {"pecas": {"upsert": [x for x in self._gabinete().lista("pecas") if x["id"] == p["id"]], "remover": m.get("remover", [])}})
        return {"ok": True}

    def sei_estado(self):
        return self._estado_leitura("sei")

    def sei_ler(self, modo="todos"):
        """Botão "Ler o SEI": o pedido vai para a aba do SEI (já logada); a extensão lê ali, com o leitor do NUSPEN, e informa o andamento.
        Uma leitura interrompida continua de onde parou (a sessão e o cursor ficam na base do gabinete)."""
        modo = modo if modo in ("todos", "novos", "documentos_novos") else "todos"
        retomar = self._sei().sessao_interrompida()
        r = self._cmd_de("sei").pedir("lerSei", {"modo": modo, "retomar": retomar})
        if r.get("ok"):
            self._andamento["sei"] = {"fase": "iniciando", "modo": modo, "quando": time.time()}
        return r

    def sei_parar(self):
        return self._cmd_de("sei").pedir("pararSei", {})

    # ---- SEEU (função SEEU): as intimações da Mesa do Defensor, guardadas até a pessoa concluir ----
    def seeu_triagem(self):
        t = self._gabinete().kv("seeu_triagem") or {}
        t["itens"] = self._seeu().listar()
        t["pecas"] = rseeu.PECAS
        t["leitura"] = self._estado_leitura("seeu")
        t["prefs"] = self.seeu_prefs()
        return t

    def seeu_estado(self):
        return self._estado_leitura("seeu")

    def seeu_prefs(self):
        """Abas, situação e filtros da Mesa como a pessoa deixou na função SEEU (os mesmos da triagem da extensão)."""
        return self._gabinete().kv("seeu_prefs", {}) or {}

    def seeu_prefs_gravar(self, prefs):
        self._gabinete().gravar_kv("seeu_prefs", _opcoes_mesa(prefs, guardar=True))
        return {"ok": True}

    def seeu_ler(self, opcoes=None):
        """Botões "1 · Ler a Mesa" e "2 · Ler processos e decisões": a extensão abre a triagem (a mesma da extensão, que não inicia
        prazo) com as abas, a situação e os filtros escolhidos aqui, e roda a etapa pedida."""
        o = _opcoes_mesa(opcoes or {})
        self._gabinete().gravar_kv("seeu_prefs", dict(self.seeu_prefs(), **{k: v for k, v in o.items() if k != "etapa"}))
        r = self._cmd_de("seeu").pedir("lerMesa", {"opcoes": o})
        if r.get("ok"):
            self._andamento["seeu"] = {"fase": "iniciando", "quando": time.time()}
        return r

    def seeu_planilha(self, chaves):
        """Planilha (xlsx) das intimações da lista, na ordem da tela."""
        from openpyxl import Workbook
        from openpyxl.styles import Font
        itens = {x["chave"]: x for x in self._seeu().listar()}
        ws_linhas = [itens[k] for k in (chaves or []) if k in itens]
        if not ws_linhas:
            return {"erro": "nenhuma intimação na lista"}
        wb = Workbook()
        ws = wb.active
        ws.title = "Mesa do SEEU"
        cab = ["Final", "Processo", "Assistido", "Defensor", "Aba", "Enviado em", "Último dia", "Prazo", "Motivo", "Última decisão", "Providência sugerida",
               "Urgente", "Situação no APTO", "Baixa", "Data da baixa", "Observação"]
        ws.append(cab)
        for c in ws[1]:
            c.font = Font(bold=True)
        for l in ws_linhas:
            a = l.get("analise") or {}
            pv = a.get("providencia") or {}
            b = l.get("baixa") or {}
            st = "concluída" if l.get("status") == "concluido" else ("saiu da Mesa" if l.get("foraDaMesa") else "em aberto")
            ws.append([l.get("final"), l.get("processo"), l.get("executado"), l.get("defensor"), l.get("aba"), l.get("dataEnvio"), l.get("ultimoDia"), l.get("prazo"),
                       (a.get("pendencia") or {}).get("texto", ""), (a.get("decisao") or {}).get("nome", ""), pv.get("texto", ""), "sim" if pv.get("urgente") else "",
                       st, b.get("pecaNome", ""), "/".join(reversed(str(b.get("data") or "").split("-"))) if b.get("data") else "", b.get("obs", "")])
        for col, w in zip("ABCDEFGHIJKLMNOP", (6, 27, 32, 22, 16, 12, 12, 10, 40, 24, 40, 8, 14, 20, 12, 30)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"
        nome = "Mesa do SEEU %s.xlsx" % time.strftime("%d-%m-%Y")
        c = self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("Excel (*.xlsx)",)) if self._janela else None
        c = c[0] if isinstance(c, (list, tuple)) and c else c
        if not c:
            return {"cancelado": True}
        try:
            wb.save(c)
        except OSError as e:
            return {"erro": "não foi possível gravar (%s)" % e}
        return {"ok": True, "caminho": c}

    # ---- Importar / Exportar únicos (barra do APTO): cópia do gabinete (Atendimentos, Quadro, produção, frases) ----
    def gabinete_exportar(self):
        d = self._gabinete().tudo()
        d = {k: d.get(k) for k in ("atendimentos", "pecas", "ajustes", "modelos", "config")}
        d.update(app="APTO Atendimentos", exportadoEm=time.strftime("%Y-%m-%dT%H:%M:%S"))
        nome = "APTO gabinete %s.json" % time.strftime("%Y-%m-%d")
        c = self._janela.create_file_dialog(webview.SAVE_DIALOG, save_filename=nome, file_types=("Cópia do gabinete (*.json)",)) if self._janela else None
        c = c[0] if isinstance(c, (list, tuple)) and c else c
        if not c:
            return {"cancelado": True}
        try:
            with open(c, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except OSError as e:
            return {"erro": "não foi possível gravar (%s)" % e}
        return {"ok": True, "caminho": c}

    def gabinete_importar(self, caminho=None):
        """Junta uma cópia (.json do APTO ou da extensão APTO Atendimentos antiga): só entra o que ainda não existe; nada é apagado."""
        if not caminho:
            c = self._janela.create_file_dialog(webview.OPEN_DIALOG, file_types=("Cópia do gabinete (*.json)",)) if self._janela else None
            caminho = c[0] if isinstance(c, (list, tuple)) and c else c
        if not caminho:
            return {"cancelado": True}
        try:
            with open(caminho, encoding="utf-8") as f:
                n = self._gabinete().importar_backup(json.load(f))
        except (OSError, ValueError) as e:
            return {"erro": "Não foi possível importar: %s" % e}
        d = self._gabinete().tudo()  # a tela do painel recebe tudo (só junta: o que já estava fica)
        self._atd_evento("mudou", {"atendimentos": {"upsert": d["atendimentos"]}, "pecas": {"upsert": d["pecas"]}, "ajustes": d["ajustes"],
                                   **{k: d[k] for k in ("modelos", "config") if d.get(k) is not None}})
        return {"ok": True, "novos": n, "msg": "Cópia importada: %d registro(s) novo(s)." % n}

    def seeu_parar(self):
        return self._cmd_de("seeu").pedir("pararMesa", {})

    # peça da baixa -> aba da Execução em que o pedido pode ser marcado como feito
    PECA_ABA = {"PROG": "prog", "LC": "liv", "INDULTO": "ind", "COMUT": "ind", "PRESC": "presc", "EXT": "ext", "REMICAO": "fd"}

    def seeu_concluir(self, chave, peca="", data="", obs="", quem=""):
        r = self._seeu().concluir(chave, peca, data, obs, quem)
        if r.get("peca"):
            self._atd_evento("mudou", {"pecas": {"upsert": [r["peca"]]}})
            if peca in self.PECA_ABA:  # a tela oferece marcar o pedido na base aberta da Execução (com um clique)
                r["sugerir_pedido"] = {"aba": self.PECA_ABA[peca], "processo": r["peca"].get("processo", ""), "data": r["peca"].get("feitoEm", "")}
        return r

    def seeu_reabrir(self, chave):
        r = self._seeu().reabrir(chave)
        if r.get("removidas"):
            self._atd_evento("mudou", {"pecas": {"remover": r["removidas"]}})
        if r.get("voltou"):
            self._atd_evento("mudou", {"pecas": {"upsert": [r["voltou"]]}})
        return r

    def seeu_atribuir(self, chave, quem=""):
        return self._seeu().atribuir(chave, quem)

    def agenda(self):
        """Agenda única (7.28): os prazos do Quadro (pendências), da Mesa do SEEU (intimações em aberto) e do SEI (prazos VALIDADOS), com a
        data em aaaa-mm-dd. Prazo do SEI que já está num cartão do Quadro aparece uma vez só (pelo cartão)."""
        itens = []
        pend = [p for p in self._gabinete().lista("pecas") if p.get("status") == "pendente"]
        for p in pend:
            if p.get("prazo"):
                itens.append({"data": p["prazo"], "origem": "quadro", "titulo": " · ".join(x for x in (p.get("nome"), p.get("obs") or "") if x)[:160],
                              "processo": p.get("processo", ""), "id": p["id"]})
        for l in self._seeu().listar():
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", str(l.get("ultimoDia") or ""))
            if l.get("status") != "concluido" and m and not l.get("quadro"):
                itens.append({"data": "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)), "origem": "seeu", "titulo": "%s · %s" % (l.get("executado") or "", l.get("aba") or ""),
                              "processo": l.get("processo", ""), "id": l["chave"]})
        no_quadro = {p["id"] for p in pend}
        with self._gabinete()._trava:
            cartao = dict(self._gabinete()._con.execute("SELECT id, quadro FROM sei_obrigacoes WHERE quadro IS NOT NULL").fetchall()) if self._sei() else {}
        for p in self._nus().prazos():
            if p["status"] in ("validada", "ajustada") and p.get("vencimento_efetivo") and cartao.get(p["obrigacao"]) not in no_quadro:
                itens.append({"data": p["vencimento_efetivo"], "origem": "sei", "titulo": p["obrigacao_descricao"][:160], "processo": p.get("processo") or "",
                              "id": p["obrigacao"]})
        return sorted(itens, key=lambda x: (x["data"], x["origem"]))

    def contadores(self):
        """Números na barra do topo: SEEU (intimações em aberto que vencem hoje ou já venceram) e SEI (prazos validados vencidos ou de hoje)."""
        hoje = time.strftime("%Y-%m-%d")
        n_seeu = 0
        for l in self._seeu().listar():
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", str(l.get("ultimoDia") or ""))
            if l.get("status") != "concluido" and m and "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) <= hoje:
                n_seeu += 1
        n_sei = sum(1 for p in self._nus().prazos() if p["status"] in ("validada", "ajustada") and p["situacao"]["ordem"] <= 1
                    and (p["vencimento_efetivo"] or "9999") <= hoje)
        return {"seeu": n_seeu, "sei": n_sei}

    def seeu_para_quadro(self, processo, nome, texto, ultimo_dia="", chave=""):
        """A providência sugerida pela triagem vira cartão do Quadro (A fazer), com o último dia da Mesa como prazo."""
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", str(ultimo_dia or ""))
        p = {"id": rgab.novo_id(), "tipo": "", "processo": str(processo or "")[:30], "nome": rgab.nome_proprio(str(nome or ""))[:200], "data": rgab.hoje_iso(),
             "status": "pendente", "coluna": "fazer", "prazo": "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else "",
             "obs": ("Mesa do SEEU: " + str(texto or ""))[:500], "origem": "seeu", "atendimentoId": "", "criadoEm": int(time.time() * 1000)}
        self._gabinete().mudar({"pecas": {"upsert": [p]}})
        if chave:
            self._seeu().ligar_quadro(chave, p["id"])
        self._atd_evento("mudou", {"pecas": {"upsert": [p]}})
        return {"ok": True}

    # ---- Quadro único (7.26): a Execução manda para o mesmo Quadro do gabinete ----
    ABA_PECA = {"prog": "PROG", "liv": "LC", "ind": "INDULTO", "presc": "PRESC", "ext": "EXT", "fd": "REMICAO"}

    @staticmethod
    def _dig(x):
        return re.sub(r"\D", "", str(x or ""))

    @staticmethod
    def _iso(d):
        d = str(d or "").strip()
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", d)
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else (d if re.match(r"^\d{4}-\d{2}-\d{2}$", d) else "")

    def _nome_base(self):
        b = getattr(self, "base", None)
        try:
            return b.nome if b else ""
        except Exception:
            return ""

    def quadro_enviar(self, c):
        """Da Execução para o Quadro: {processo, nome, obs, prazo (dd/mm/aaaa), aba, coluna}. Uma pendência aberta por processo e
        benefício: se já existe, não duplica."""
        c = dict(c or {})
        proc, aba = str(c.get("processo") or "").strip()[:40], str(c.get("aba") or "")[:20]
        if not proc and not (c.get("nome") or "").strip():
            return {"erro": "Escolha o assistido."}
        prazo = self._iso(c.get("prazo"))
        if c.get("prazo") and not prazo:
            return {"erro": "Prazo inválido: use dd/mm/aaaa."}
        g = self._gabinete()
        dg = self._dig(proc)
        for x in g.lista("pecas"):
            if x.get("status") == "pendente" and dg and self._dig(x.get("processo")) == dg and (x.get("aba") or "") == aba and x.get("origem") == "execucao":
                return {"ok": True, "ja": True, "msg": "Já está no Quadro (%s)." % ("fila " + {"doc": "Aguardando documento", "naoEnc": "Não encaminhou"}.get(x.get("coluna"), "A fazer"))}
        coluna = c.get("coluna") if c.get("coluna") in ("doc", "fazer", "naoEnc") else "fazer"
        p = {"id": rgab.novo_id(), "tipo": self.ABA_PECA.get(aba, ""), "processo": proc, "nome": rgab.nome_proprio(str(c.get("nome") or ""))[:200],
             "data": rgab.hoje_iso(), "status": "pendente", "coluna": coluna, "prazo": prazo, "obs": str(c.get("obs") or "").strip()[:500],
             "origem": "execucao", "aba": aba, "base": self._nome_base(), "atendimentoId": "", "criadoEm": int(time.time() * 1000)}
        g.mudar({"pecas": {"upsert": [p]}})
        self._atd_evento("mudou", {"pecas": {"upsert": [p]}})
        return {"ok": True, "peca": p, "msg": "Enviado ao Quadro."}

    def quadro_pendencias(self, processo):
        """Pendências abertas do Quadro para o processo (de qualquer origem: atendimento, Execução, SEEU)."""
        dg = self._dig(processo)
        if not dg:
            return []
        return [x for x in self._gabinete().lista("pecas") if x.get("status") == "pendente" and self._dig(x.get("processo")) == dg]

    def quadro_pedido_feito(self, processo, aba, data=""):
        """Pedido marcado na Execução: as pendências do mesmo processo e benefício ganham a etiqueta "Pedido feito"."""
        aba = aba.split("_")[0] if str(aba).startswith("ind_") else str(aba or "")
        dg, mud = self._dig(processo), []
        for x in self._gabinete().lista("pecas"):
            if dg and x.get("status") == "pendente" and self._dig(x.get("processo")) == dg and (x.get("aba") or "") == aba:
                mud.append(dict(x, etiqueta="pedido", pedidoEm=self._iso(data) or rgab.hoje_iso()))
        if mud:
            self._gabinete().mudar({"pecas": {"upsert": mud}})
            self._atd_evento("mudou", {"pecas": {"upsert": mud}})
        return len(mud)

    def quadro_migrar_base(self):
        """Uma vez por base: os cartões do antigo "Quadro do Usuário" (não arquivados) viram pendências do Quadro único, na fila
        "A fazer", com a coluna e a etiqueta antigas na observação. As tabelas antigas ficam como estavam (nada é apagado)."""
        b = getattr(self, "base", None)
        if not b:
            return 0
        g = self._gabinete()
        chave = "quadroMigrado:" + os.path.abspath(b.caminho)
        if g.kv(chave):
            return 0
        q = b.quadro()
        cols = {x["id"]: x["nome"] for x in q["colunas"]}
        with b.lock:
            nomes = dict(b.con.execute("SELECT processo, nome FROM assistidos").fetchall())
        novas = []
        for c in q["cartoes"]:
            if c.get("arquivado"):
                continue
            obs = " · ".join(x for x in (c.get("titulo"), c.get("obs"), "coluna antiga: " + cols.get(c.get("coluna"), "")) if x and not x.endswith(": "))
            novas.append({"id": rgab.novo_id(), "tipo": self.ABA_PECA.get(c.get("aba") or "", ""), "processo": c.get("processo") or "",
                          "nome": rgab.nome_proprio(nomes.get(c.get("processo"), "") or c.get("titulo") or "")[:200], "data": rgab.hoje_iso(),
                          "status": "pendente", "coluna": "fazer", "prazo": self._iso(c.get("prazo")), "obs": obs[:500], "origem": "execucao",
                          "aba": c.get("aba") or "", "base": b.nome, "etiqueta": c.get("etiqueta") or "", "atendimentoId": "",
                          "criadoEm": int(time.time() * 1000), "doQuadroDaBase": c["id"]})
        if novas:
            g.mudar({"pecas": {"upsert": novas}})
            self._atd_evento("mudou", {"pecas": {"upsert": novas}})
        g.gravar_kv(chave, {"quando": rgab.hoje_iso(), "cartoes": len(novas)})
        return len(novas)

    def abrir_seeu(self, url):
        """Abre o processo no SEEU, no navegador (onde a pessoa está logada)."""
        u = str(url or "")
        if not u.startswith("https://seeu.pje.jus.br/"):
            return {"erro": "endereço não permitido"}
        webbrowser.open(u)
        return {"ok": True}

    # ---- pedidos da extensão (servidor local) ----
    def _ext_get(self, caminho, cab=None):
        cab = cab or {}
        if caminho == "/atd/comando":
            return {"cmd": self._comandos().proximo()}
        if caminho in ("/sei/comando", "/seeu/comando"):
            return {"cmd": self._cmd_de(caminho.split("/")[1]).proximo()}
        if caminho == "/sei/token":
            return {"token": self._sei().token}
        if caminho == "/api/sync/ping/":
            if not self._sei().token_ok(cab.get("Authorization")):
                return {"__status": 401, "erro": "token inválido ou expirado"}
            return {"ok": True, "laboratorio": False, "expira_em": None, "conhecidos": self._sei().contagens()}
        return None

    def _ext_sei(self, caminho, corpo, cab):
        """A mesma API de sincronização do NUSPEN (a extensão do SEI não muda), autenticada pelo token do APTO."""
        s = self._sei()
        if not s.token_ok(cab.get("Authorization")):
            return {"__status": 401, "erro": "token inválido ou expirado"}
        if caminho == "/api/sync/sessoes/":
            return s.iniciar(str(corpo.get("modo") or "todos"), corpo.get("retomar"))
        if caminho == "/api/sync/conhecidos/":
            ids = corpo.get("ids")
            if not isinstance(ids, list) or len(ids) > rsei.LIMITE_IDS:
                return {"__status": 400, "erro": "informe até 2000 ids"}
            return {"conhecidos": s.conhecidos(ids)}
        if caminho == "/api/sync/token/revogar/":
            s.revogar()
            return {"revogado": True}
        m = re.match(r"^/api/sync/sessoes/(\d+)/(itens|concluir)/$", caminho)
        if m:
            try:
                if m.group(2) == "itens":
                    if not isinstance(corpo.get("itens", []), list):
                        return {"__status": 400, "erro": "JSON inválido"}
                    r = s.receber_lote(int(m.group(1)), corpo.get("itens", []), corpo.get("cursor"))
                    if r["novos"] or r["modificados"]:
                        self._js("window.ui && ui.seiEvento && ui.seiEvento()")
                    return r
                r = s.concluir(int(m.group(1)), corpo)
                self._js("window.ui && ui.seiEvento && ui.seiEvento()")
                return r
            except KeyError:
                return {"__status": 404, "erro": "sessão desconhecida"}
        return None

    def _ext_post(self, caminho, corpo, cab=None):
        cab = cab or {}
        if caminho.startswith("/api/sync/"):
            return self._ext_sei(caminho, corpo, cab)
        if caminho == "/painel/dossie":
            # painel no SEEU: dados pessoais do assistido - só com o token que o APTO entrega à extensão (GET /sei/token)
            if not self._sei().token_ok(cab.get("Authorization")):
                return {"__status": 401, "erro": "token inválido ou expirado"}
            return self._painel_dossie(corpo.get("processo"))
        if caminho == "/painel/abrir":
            if not self._sei().token_ok(cab.get("Authorization")):
                return {"__status": 401, "erro": "token inválido ou expirado"}
            return self._painel_abrir(corpo.get("processo"))
        if caminho == "/seeu/triagem":
            t = corpo.get("triagem")
            if not isinstance(t, dict):
                return {"__status": 400, "erro": "triagem inválida"}
            t["recebida"] = time.strftime("%Y-%m-%d %H:%M:%S")
            r = self._seeu().receber(t)
            t.pop("linhas", None)  # as intimações ficam na tabela seeu_itens; aqui só o resumo da última triagem
            self._gabinete().gravar_kv("seeu_triagem", t)
            self._js("window.ui && ui.seeuEvento && ui.seeuEvento()")
            return dict(r, ok=True)
        if caminho in ("/sei/resposta", "/seeu/resposta"):
            ok = self._cmd_de(caminho.split("/")[1]).responder(int(corpo.get("id") or 0), corpo.get("resposta"))
            return {"ok": ok}
        if caminho in ("/sei/andamento", "/seeu/andamento"):
            sist = caminho.split("/")[1]
            a = corpo.get("andamento")
            if not isinstance(a, dict):
                return {"__status": 400, "erro": "andamento inválido"}
            a = {k: a[k] for k in list(a)[:40] if isinstance(a[k], (str, int, float, bool, type(None), list))}
            a["quando"] = time.time()
            self._cmd_de(sist)
            self._andamento[sist] = a
            self._js("window.ui && ui.%sEvento && ui.%sEvento(%s)" % (sist, sist, json.dumps({"estado": self._estado_leitura(sist)}, ensure_ascii=False)))
            return {"ok": True}
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
