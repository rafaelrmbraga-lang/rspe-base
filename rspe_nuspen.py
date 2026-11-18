"""Gestão do NUSPEN dentro do APTO (7.27): o que o sistema do NUSPEN (nuspen-sei, Django) fazia depois da leitura do SEI,
reescrito sobre a base do gabinete (SQLite), ligado ao SEI, ao Quadro e ao Relatório do APTO.

- Demanda ≠ processo SEI (N:N, ADR-003): a demanda junta processos e providências; "concluído no SEI" não é "resolvido".
- Providência (obrigação, ADR-011): a mesma linha que a leitura do SEI sugere (sei_obrigacoes); ganha demanda, achado,
  prioridade, observações, quem assina, e a situação de CUMPRIMENTO, separada da resposta (RF50 × RF51).
- Prazo (ADR-012): natureza (expresso, calculado, não identificado), origem, finalidade, termo inicial com fonte, regra de
  contagem (só a aprovada calcula; só dias corridos), alterações (prorrogação, suspensão, retomada) sem apagar o anterior.
  Nunca inventado: faltou dado, abre-se uma LACUNA.
- Validação humana por tipo (ADR-014): obrigação, prazo e avaliações nascem sugestão; só a decisão de uma pessoa (com "Quem")
  vale como fato; cada decisão fica no histórico.
- Comunicação (ofício): estado DERIVADO (aguardando envio, aguardando resposta, resposta sem juntada, resposta juntada);
  reiterações e respostas só acrescentam; avaliação da resposta e do cumprimento em separado.
- Inspeções: achados com categoria, gravidade, recomendação, acompanhamento; recorrência SUGERIDA por regra (mesmo
  estabelecimento, mesma categoria, inspeção anterior) e só vale confirmada; achados nunca são fundidos.
- Minutas: determinísticas (sem IA, nada sai do computador), só com fatos validados, cada frase com a sua fonte; versões
  só acrescentam.
- Nada se apaga: remoção lógica com quem e motivo; histórico (nus_historico) de toda mudança.
"""
import json
import re
from datetime import date, datetime, timedelta

LIMITE = 3000
STATUS_FATO = ("validada", "ajustada")

TIPOS_OBRIGACAO = [("elaborar_relatorio", "Elaborar relatório"), ("expedir_oficio", "Expedir ofício"), ("responder", "Responder"),
                   ("providencia_material", "Providência material"), ("retornar_solicitante", "Retornar ao solicitante"), ("outro", "Outro")]
ORIGENS_OBRIGACAO = [("despacho", "Despacho"), ("relatorio", "Relatório"), ("recomendacao", "Recomendação"), ("decisao", "Decisão"),
                     ("solicitacao_externa", "Solicitação externa"), ("manual", "Manual")]
CUMPRIMENTO = [("nao_avaliada", "Não avaliada"), ("cumprida", "Cumprida"), ("parcial", "Parcialmente cumprida"), ("pendente", "Pendente"),
               ("sem_comprovacao", "Sem comprovação"), ("prejudicada", "Prejudicada")]
PRIORIDADES = [("baixa", "Baixa"), ("normal", "Normal"), ("alta", "Alta")]
SITUACOES_DEMANDA = [("nova", "Nova"), ("em_analise", "Em análise"), ("em_andamento", "Em andamento"), ("aguardando_resposta", "Aguardando resposta"),
                     ("atendida_parcialmente", "Atendida parcialmente"), ("atendida", "Atendida"), ("nao_atendida", "Não atendida"), ("cancelada", "Cancelada")]
TIPOS_DEMANDA = [("inspecao", "Inspeção prisional"), ("denuncia", "Denúncia"), ("ministerio_publico", "Solicitação do Ministério Público"),
                 ("judicial", "Demanda judicial"), ("administrativa", "Administrativa"), ("outra", "Outra")]
NATUREZAS = [("expresso", "Expresso"), ("calculado", "Calculado"), ("nao_identificado", "Não identificado")]
ORIGENS_PRAZO = [("externo", "Externo"), ("interno", "Interno"), ("legal", "Legal"), ("definido_pela_coordenacao", "Definido pela coordenação"),
                 ("nao_informada", "Não informada (a definir na validação)")]
FINALIDADES = [("elaboracao", "Elaboração"), ("expedicao", "Expedição"), ("resposta", "Resposta"), ("retorno", "Retorno"), ("reiteracao", "Reiteração"),
               ("outra", "Outra")]
ALTERACOES_PRAZO = [("prorrogacao", "Prorrogação"), ("suspensao", "Suspensão"), ("retomada", "Retomada"), ("alteracao", "Alteração")]
TIPOS_LACUNA = [("prazo_sem_termo", "Prazo sem termo inicial"), ("prazo_nao_identificado", "Prazo não identificado"),
                ("resposta_ausente", "Resposta ausente"), ("documento_citado_ausente", "Documento citado ausente"), ("outro", "Outro")]
AVAL_RESPOSTA = [("atende", "Atende"), ("parcial", "Atende parcialmente"), ("ciencia", "Só ciência"), ("nao_atende", "Não atende"),
                 ("nao_pertinente", "Não pertinente")]
AVAL_CUMPRIMENTO = [("cumprida", "Cumprida"), ("parcial", "Parcialmente cumprida"), ("pendente", "Pendente"), ("sem_comprovacao", "Sem comprovação"),
                    ("prejudicada", "Prejudicada")]
CATEGORIAS = [("superlotacao", "Superlotação"), ("saude", "Saúde"), ("alimentacao", "Alimentação"), ("higiene", "Higiene e água"), ("agua", "Água"),
              ("estrutura", "Estrutura"), ("violencia", "Violência e segurança"), ("assistencia_juridica", "Assistência jurídica"),
              ("educacao_trabalho", "Educação e trabalho"), ("outra", "Outra")]
GRAVIDADES = [("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta")]
SITUACOES_ACHADO = [("identificado", "Identificado"), ("em_acompanhamento", "Em acompanhamento"), ("persiste", "Persiste"), ("resolvido", "Resolvido"),
                    ("nao_verificado", "Não verificado")]
ORDEM_COMUNICACAO = ("aguardando_envio", "aguardando_resposta", "resposta_sem_juntada", "resposta_juntada")
ETAPAS = ("Relatório de inspeção", "Identificação das providências", "Elaboração dos ofícios", "Aprovação humana", "Envio manual no SEI",
          "Recebimento das respostas", "Identificação das juntadas", "Análise do cumprimento", "Resolução")
BLOCOS = [("abertura", "Abertura (fórmula do modelo)"), ("dados", "Dados objetivos do caso"), ("conclusao", "Conclusão (condicional até a verificação)"),
          ("consequencia", "Consequência em tempo"), ("omissao", "Omissão registrada, delimitada no tempo"), ("pedido", "Pedido (fórmula do modelo)"),
          ("fecho", "Fecho (fórmula do modelo)")]
_PEDIDO = "Ante o exposto, solicita-se a conferência da providência e, se for o caso, a reiteração da comunicação."
MODELOS_EMBUTIDOS = {
    "modelo-nuspen-v0": {"nome": "Padrão (blocos)", "descricao": "Só os quatro blocos: dados objetivos, conclusão no condicional, consequência "
                         "em tempo e omissão delimitada no tempo. Sem abertura nem fecho.", "formulas": {}},
    "despacho-v1": {"nome": "Despacho", "descricao": "Abertura de despacho, blocos do padrão, pedido condicional e fecho.",
                    "formulas": {"abertura": "Trata-se de acompanhamento da providência registrada {documento}.", "pedido": _PEDIDO,
                                 "fecho": "Cumpra-se."}},
    "oficio-v1": {"nome": "Ofício", "descricao": "Ofício ao destinatário da providência: vocativo, referência ao documento, o pedido com o prazo validado e o fecho.",
                  "blocos": ["abertura", "dados", "pedido", "fecho"],
                  "formulas": {"abertura": "{vocativo}", "pedido": "Solicito a Vossa Senhoria as providências necessárias quanto ao exposto{prazo}, com o "
                               "envio da resposta a esta unidade.", "fecho": "Atenciosamente."}},
    "reiteracao-v1": {"nome": "Ofício de reiteração", "descricao": "Reitera o ofício enviado e não respondido: referência, a omissão delimitada no tempo, "
                      "o pedido e o fecho.", "blocos": ["abertura", "dados", "omissao", "pedido", "fecho"],
                      "formulas": {"abertura": "{vocativo}", "pedido": "Reitero o pedido anterior, solicitando a resposta{prazo}.", "fecho": "Atenciosamente."}},
    "manifestacao-v1": {"nome": "Manifestação à coordenação", "descricao": "Abertura dirigida ao coordenador, blocos do padrão, pedido e fecho.",
                        "formulas": {"abertura": "Prezado Coordenador,", "pedido": _PEDIDO, "fecho": "Atenciosamente."}},
}
RESSALVA = ("a existência de resposta juntada a outro processo, de prorrogação ou suspensão do prazo e de providência não importada "
            "para o sistema")
COLUNAS_PROVIDENCIA = ("Identificada", "Aguardando início", "Em elaboração", "Aguardando envio", "Aguardando resposta", "Aguardando reiteração",
                       "Resposta recebida", "Juntada identificada", "Em análise", "Cumprida parcialmente", "Cumprida integralmente", "Não cumprida",
                       "Encerrada", "Rejeitada")

TABELAS = """
CREATE TABLE IF NOT EXISTS nus_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, objeto TEXT, obj_id INTEGER, campo TEXT, de TEXT, para TEXT,
  motivo TEXT, quem TEXT, quando TEXT);
CREATE INDEX IF NOT EXISTS nus_historico_obj ON nus_historico(objeto, obj_id);
CREATE TABLE IF NOT EXISTS nus_demandas (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto TEXT, descricao TEXT, tipo TEXT, prioridade TEXT,
  destinatario TEXT, situacao TEXT, responsavel TEXT, aberta_em TEXT, removido_em TEXT, removido_por TEXT, motivo_remocao TEXT);
CREATE TABLE IF NOT EXISTS nus_demanda_processos (demanda INTEGER, processo TEXT, quando TEXT, quem TEXT, desvinculado_em TEXT,
  PRIMARY KEY (demanda, processo));
CREATE TABLE IF NOT EXISTS nus_regras (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, descricao TEXT, dias TEXT, feriados TEXT,
  fonte_normativa TEXT, aprovada INTEGER DEFAULT 0, aprovada_por TEXT, aprovada_em TEXT, vigencia_inicio TEXT, vigencia_fim TEXT, criada TEXT, quem TEXT);
CREATE TABLE IF NOT EXISTS nus_prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, obrigacao INTEGER, finalidade TEXT, natureza TEXT, origem TEXT,
  termo_inicial TEXT, fonte_termo TEXT, quantidade INTEGER, unidade TEXT, regra INTEGER, vencimento TEXT, fonte_doc INTEGER, fonte_trecho TEXT,
  status TEXT DEFAULT 'sugestao', criado TEXT, quem TEXT);
CREATE INDEX IF NOT EXISTS nus_prazos_obr ON nus_prazos(obrigacao);
CREATE TABLE IF NOT EXISTS nus_prazo_alteracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, prazo INTEGER, tipo TEXT, data TEXT, vencimento_anterior TEXT,
  novo_vencimento TEXT, motivo TEXT, fonte TEXT, quem TEXT, quando TEXT);
CREATE TABLE IF NOT EXISTS nus_lacunas (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, descricao TEXT, obrigacao INTEGER, prazo INTEGER,
  aberta INTEGER DEFAULT 1, criada TEXT, fechada_em TEXT, fechada_por TEXT, motivo TEXT);
CREATE TABLE IF NOT EXISTS nus_comunicacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto TEXT, documento INTEGER, processo TEXT, destinatario TEXT,
  meio TEXT, data_envio TEXT, criada TEXT, quem TEXT, removido_em TEXT, removido_por TEXT, motivo_remocao TEXT);
CREATE TABLE IF NOT EXISTS nus_com_obrigacoes (comunicacao INTEGER, obrigacao INTEGER, PRIMARY KEY (comunicacao, obrigacao));
CREATE TABLE IF NOT EXISTS nus_reiteracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacao INTEGER, data TEXT, documento INTEGER, quem TEXT, quando TEXT);
CREATE TABLE IF NOT EXISTS nus_respostas (id INTEGER PRIMARY KEY AUTOINCREMENT, comunicacao INTEGER, data_recebimento TEXT, documento INTEGER,
  observacao TEXT, quem TEXT, quando TEXT);
CREATE TABLE IF NOT EXISTS nus_avaliacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, alvo TEXT, alvo_id INTEGER, resultado TEXT, fonte TEXT,
  status TEXT DEFAULT 'sugestao', quem TEXT, quando TEXT);
CREATE INDEX IF NOT EXISTS nus_avaliacoes_alvo ON nus_avaliacoes(alvo, alvo_id);
CREATE TABLE IF NOT EXISTS nus_inspecoes (id INTEGER PRIMARY KEY AUTOINCREMENT, estabelecimento TEXT, municipio TEXT, data TEXT, observacoes TEXT,
  criada TEXT, quem TEXT, removido_em TEXT, removido_por TEXT, motivo_remocao TEXT);
CREATE TABLE IF NOT EXISTS nus_insp_documentos (inspecao INTEGER, documento INTEGER, PRIMARY KEY (inspecao, documento));
CREATE TABLE IF NOT EXISTS nus_achados (id INTEGER PRIMARY KEY AUTOINCREMENT, inspecao INTEGER, descricao TEXT, categoria TEXT, gravidade TEXT,
  recomendacao TEXT, situacao TEXT DEFAULT 'identificado', documento INTEGER, anterior INTEGER, criado TEXT, quem TEXT);
CREATE TABLE IF NOT EXISTS nus_modelos (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, versao INTEGER, nome TEXT, descricao TEXT, abertura TEXT,
  pedido TEXT, fecho TEXT, quem TEXT, criado TEXT, UNIQUE (slug, versao));
CREATE TABLE IF NOT EXISTS nus_minutas (id INTEGER PRIMARY KEY AUTOINCREMENT, obrigacao INTEGER, criada TEXT, quem TEXT, removido_em TEXT,
  removido_por TEXT, motivo_remocao TEXT);
CREATE TABLE IF NOT EXISTS nus_minuta_versoes (id INTEGER PRIMARY KEY AUTOINCREMENT, minuta INTEGER, numero INTEGER, modelo TEXT, quem TEXT, data TEXT,
  data_conferencia TEXT, status TEXT DEFAULT 'sugestao', UNIQUE (minuta, numero));
CREATE TABLE IF NOT EXISTS nus_minuta_frases (id INTEGER PRIMARY KEY AUTOINCREMENT, versao INTEGER, ordem INTEGER, bloco TEXT, texto TEXT, fonte TEXT,
  editada INTEGER DEFAULT 0);
"""
# colunas que a providência ganha na tabela das obrigações sugeridas pelo SEI
COLUNAS_OBRIGACAO = (("demanda", "INTEGER"), ("situacao_cumprimento", "TEXT DEFAULT 'nao_avaliada'"), ("prioridade", "TEXT DEFAULT 'normal'"),
                     ("observacoes", "TEXT"), ("responsavel", "TEXT"), ("responsavel_assinatura", "TEXT"), ("aguarda_decisao", "INTEGER DEFAULT 0"),
                     ("achado", "INTEGER"), ("removido_em", "TEXT"), ("removido_por", "TEXT"), ("motivo_remocao", "TEXT"), ("valor_original", "TEXT"))
COLUNAS_DECISAO = (("quem", "TEXT"), ("valor_anterior", "TEXT"), ("valor_novo", "TEXT"))


class Erro(ValueError):
    """Regra do domínio: a mensagem vai para a tela."""


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _t(v, n=300):
    return str(v if v is not None else "").strip()[:n]


def data_iso(v, campo="data", obrigatoria=False):
    """dd/mm/aaaa ou aaaa-mm-dd -> aaaa-mm-dd ('' se vazia e não obrigatória)."""
    s = str(v or "").strip()
    if not s:
        if obrigatoria:
            raise Erro("Informe a %s." % campo)
        return ""
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    iso = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else s[:10]
    try:
        date.fromisoformat(iso)
    except ValueError:
        raise Erro("%s inválida: use dd/mm/aaaa." % campo.capitalize()) from None
    return iso


def br(iso):
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[:4]) if iso and len(iso) >= 10 else ""


def rotulo(escolhas, valor):
    return dict(escolhas).get(valor, valor or "")


def _quem(quem):
    q = _t(quem, 100)
    if not q:
        raise Erro("Escolha quem está registrando (campo Quem, no alto da tela).")
    return q


DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


class Nuspen:
    def __init__(self, gabinete):
        self.g = gabinete
        self._con = gabinete._con
        self._trava = gabinete._trava
        with self._trava, self._con:
            # as tabelas do SEI (sei_obrigacoes, sei_decisoes) vêm de rspe_sei; garante que existam antes de estender
            import rspe_sei
            self._con.executescript(rspe_sei.TABELAS)
            self._con.executescript(TABELAS)
            for tab, cols in (("sei_obrigacoes", COLUNAS_OBRIGACAO), ("sei_decisoes", COLUNAS_DECISAO), ("nus_comunicacoes", (("peca", "TEXT"),)),
                              ("nus_reiteracoes", (("peca", "TEXT"),))):
                tem = [r[1] for r in self._con.execute("PRAGMA table_info(%s)" % tab)]
                for c, tp in cols:
                    if c not in tem:
                        self._con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tab, c, tp))

    # ---------------------------------------------------------------- ligações com o resto do APTO (Quadro e produção do mês)
    pecas_mudadas = None

    def _pecas(self, upsert=(), remover=()):
        """Muda o Quadro/produção do gabinete e guarda o que mudou, para a tela do Quadro ser avisada (rspe_gabinete_api.nus)."""
        up, rm = [p for p in upsert if p], [r for r in remover if r]
        if not up and not rm:
            return
        self.g.mudar({"pecas": {"upsert": up, "remover": rm}})
        if self.pecas_mudadas is None:
            self.pecas_mudadas = {"upsert": [], "remover": []}
        self.pecas_mudadas["upsert"] += up
        self.pecas_mudadas["remover"] += rm

    def tirar_mudancas(self):
        m, self.pecas_mudadas = self.pecas_mudadas, None
        return m

    def sincronizar_quadro(self):
        """O cartão do Quadro de cada providência leva o vencimento VALIDADO (o mais próximo), e acompanha prorrogação e suspensão."""
        with self._trava:
            ligados = self._q("SELECT id, quadro FROM sei_obrigacoes WHERE quadro IS NOT NULL AND quadro<>'' AND removido_em IS NULL").fetchall()
            if not ligados:
                return 0
            pecas = {p["id"]: p for p in self.g.lista("pecas")}
            up = []
            for oid, pid in ligados:
                p = pecas.get(pid)
                if not p or p.get("status") != "pendente":
                    continue
                datas = sorted(v for v in (self._venc_efetivo(x) for x in self._prazos_de(oid) if x["status"] in STATUS_FATO) if v)
                novo = datas[0] if datas else ""
                if (p.get("prazo") or "") != novo and (novo or p.get("prazoDoSei")):
                    up.append(dict(p, prazo=novo, prazoDoSei=bool(novo)))
        self._pecas(up)
        return len(up)

    def _peca_oficio(self, pid, data, assunto, processo, quem):
        """O ofício enviado (ou reiterado) conta na produção do mês: coluna "Ofícios" do CONTROLE."""
        import rspe_gabinete as rgab
        import time as _time
        ant = next((x for x in self.g.lista("pecas") if pid and x.get("id") == pid), None)
        p = dict(ant) if ant else {"id": rgab.novo_id(), "tipo": "OFICIO", "nome": "", "status": "feito", "coluna": "fazer", "origem": "sei", "atendimentoId": "",
                                   "criadoEm": int(_time.time() * 1000)}
        p.update(processo=_t(processo, 30), data=data, feitoEm=data, obs=("Ofício (SEI): %s · %s" % (assunto, quem))[:500])
        self._pecas([p])
        return p["id"]

    # ---------------------------------------------------------------- comum
    def arquivos_pdf(self):
        import rspe_sei
        return rspe_sei.Sei.arquivos(self)

    def _q(self, sql, *a):
        return self._con.execute(sql, a)

    def _um(self, sql, *a):
        return self._con.execute(sql, a).fetchone()

    def _dicts(self, sql, *a):
        c = self._con.execute(sql, a)
        nomes = [x[0] for x in c.description]
        return [dict(zip(nomes, r)) for r in c.fetchall()]

    def _hist(self, objeto, oid, campo, de, para, quem, motivo=""):
        self._q("INSERT INTO nus_historico(objeto, obj_id, campo, de, para, motivo, quem, quando) VALUES(?,?,?,?,?,?,?,?)",
                objeto, int(oid), campo, _t(de, 600), _t(para, 600), _t(motivo, 600), quem, _agora())

    def historico_de(self, objeto, oid):
        with self._trava:
            return self._dicts("SELECT campo, de, para, motivo, quem, quando FROM nus_historico WHERE objeto=? AND obj_id=? ORDER BY id DESC", objeto, int(oid))

    def quem_lista(self):
        return self.g.kv("nusQuem", [])

    def quem_gravar(self, nomes):
        lista = sorted({_t(n, 100) for n in (nomes or []) if _t(n, 100)})
        self.g.gravar_kv("nusQuem", lista)
        return lista

    def remover(self, objeto, oid, quem, motivo):
        """Remoção lógica (nada se apaga): demanda, obrigacao, comunicacao, inspecao, minuta."""
        tab = {"demanda": "nus_demandas", "obrigacao": "sei_obrigacoes", "comunicacao": "nus_comunicacoes", "inspecao": "nus_inspecoes",
               "minuta": "nus_minutas"}.get(objeto)
        if not tab:
            raise Erro("Não se remove este tipo.")
        quem = _quem(quem)
        if not _t(motivo):
            raise Erro("A remoção exige o motivo (nada se apaga: fica no histórico).")
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM %s WHERE id=? AND removido_em IS NULL" % tab, int(oid)):
                raise Erro("Registro não encontrado (ou já removido).")
            self._q("UPDATE %s SET removido_em=?, removido_por=?, motivo_remocao=? WHERE id=?" % tab, _agora(), quem, _t(motivo, 600), int(oid))
            if objeto == "comunicacao":  # o ofício removido sai da produção do mês (o registro fica, com o motivo)
                ps = [r[0] for r in self._q("SELECT peca FROM nus_comunicacoes WHERE id=? UNION SELECT peca FROM nus_reiteracoes WHERE comunicacao=?",
                                            int(oid), int(oid)).fetchall() if r[0]]
                self._pecas(remover=ps)
            self._hist(objeto, oid, "remoção lógica", "", "removido", quem, motivo)
        return {"ok": True}

    # ---------------------------------------------------------------- demandas
    def _validar_demanda(self, campo, valor):
        valor = _t(valor, LIMITE + 1)
        if campo == "assunto" and not valor:
            raise Erro("O assunto não pode ficar vazio.")
        if len(valor) > LIMITE or (campo == "assunto" and len(valor) > 300):
            raise Erro("O texto passa do limite.")
        for c, esc in (("situacao", SITUACOES_DEMANDA), ("tipo", TIPOS_DEMANDA), ("prioridade", PRIORIDADES)):
            if campo == c and valor not in dict(esc):
                raise Erro("%s inválida." % c.capitalize())
        return valor

    def demanda_criar(self, dados, quem):
        quem = _quem(quem)
        d = dict(dados or {})
        v = {c: self._validar_demanda(c, d.get(c, padrao)) for c, padrao in (("assunto", ""), ("descricao", ""), ("tipo", "outra"),
                                                                             ("prioridade", "normal"), ("destinatario", ""))}
        with self._trava, self._con:
            c = self._q("INSERT INTO nus_demandas(assunto, descricao, tipo, prioridade, destinatario, situacao, responsavel, aberta_em) VALUES(?,?,?,?,?,?,?,?)",
                        v["assunto"], v["descricao"], v["tipo"], v["prioridade"], v["destinatario"], "nova", _t(d.get("responsavel") or quem, 100),
                        date.today().isoformat())
            did = c.lastrowid
            self._hist("demanda", did, "criação", "", v["assunto"], quem)
            for p in d.get("processos") or []:
                self._vincular_processo(did, p, quem)
        return {"ok": True, "id": did}

    CAMPOS_DEMANDA = {"assunto": "Assunto", "descricao": "Descrição", "tipo": "Tipo", "prioridade": "Prioridade", "destinatario": "Destinatário",
                      "situacao": "Situação", "responsavel": "Responsável"}

    def demanda_editar(self, did, campo, valor, quem, motivo=""):
        quem = _quem(quem)
        if campo not in self.CAMPOS_DEMANDA:
            raise Erro("Este campo não pode ser editado.")
        novo = self._validar_demanda(campo, valor)
        if campo == "situacao" and novo == "cancelada" and not _t(motivo):
            raise Erro("Informe a justificativa para cancelar.")
        with self._trava, self._con:
            r = self._um("SELECT %s FROM nus_demandas WHERE id=? AND removido_em IS NULL" % campo, int(did))
            if not r:
                raise Erro("Demanda não encontrada.")
            if (r[0] or "") == novo:
                return {"ok": True, "igual": True}
            self._q("UPDATE nus_demandas SET %s=? WHERE id=?" % campo, novo, int(did))
            de, para = (rotulo(SITUACOES_DEMANDA, r[0]), rotulo(SITUACOES_DEMANDA, novo)) if campo == "situacao" else (r[0] or "", novo)
            self._hist("demanda", did, self.CAMPOS_DEMANDA[campo], de, para, quem, motivo)
        return {"ok": True}

    def _vincular_processo(self, did, processo, quem):
        processo = _t(processo, 60)
        if not processo:
            return False
        r = self._um("SELECT desvinculado_em FROM nus_demanda_processos WHERE demanda=? AND processo=?", int(did), processo)
        if r and r[0] is None:
            return False
        if r:
            self._q("UPDATE nus_demanda_processos SET desvinculado_em=NULL, quando=?, quem=? WHERE demanda=? AND processo=?", _agora(), quem, int(did), processo)
        else:
            self._q("INSERT INTO nus_demanda_processos(demanda, processo, quando, quem) VALUES(?,?,?,?)", int(did), processo, _agora(), quem)
        self._hist("demanda", did, "vínculo com processo", "", processo, quem)
        return True

    def demanda_vincular_processo(self, did, processo, quem):
        quem = _quem(quem)
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM nus_demandas WHERE id=? AND removido_em IS NULL", int(did)):
                raise Erro("Demanda não encontrada.")
            novo = self._vincular_processo(did, processo, quem)
        return {"ok": True, "ja": not novo}

    def demanda_desvincular_processo(self, did, processo, quem, motivo):
        quem = _quem(quem)
        if not _t(motivo):
            raise Erro("Informe o motivo para desvincular.")
        with self._trava, self._con:
            n = self._q("UPDATE nus_demanda_processos SET desvinculado_em=? WHERE demanda=? AND processo=? AND desvinculado_em IS NULL",
                        _agora(), int(did), _t(processo, 60)).rowcount
            if not n:
                raise Erro("O processo não está vinculado a esta demanda.")
            self._hist("demanda", did, "vínculo com processo", processo, "(desvinculado)", quem, motivo)
        return {"ok": True}

    def demanda_vincular_providencia(self, did, oid, quem):
        return self.obrigacao_editar(oid, "demanda", did, quem)

    def demandas(self):
        with self._trava:
            ds = self._dicts("SELECT * FROM nus_demandas WHERE removido_em IS NULL ORDER BY id DESC")
            procs = {}
            for d, p in self._q("SELECT demanda, processo FROM nus_demanda_processos WHERE desvinculado_em IS NULL ORDER BY quando").fetchall():
                procs.setdefault(d, []).append(p)
            obr = {}
            for d, st, cum, n in self._q("SELECT demanda, status, situacao_cumprimento, COUNT(*) FROM sei_obrigacoes WHERE demanda IS NOT NULL "
                                         "AND removido_em IS NULL GROUP BY demanda, status, situacao_cumprimento").fetchall():
                x = obr.setdefault(d, {"total": 0, "validadas": 0, "cumpridas": 0, "sugestoes": 0})
                x["total"] += n
                x["validadas"] += n if st in STATUS_FATO else 0
                x["sugestoes"] += n if st == "sugestao" else 0
                x["cumpridas"] += n if cum == "cumprida" else 0
        for d in ds:
            d["processos"] = procs.get(d["id"], [])
            d["providencias"] = obr.get(d["id"], {"total": 0, "validadas": 0, "cumpridas": 0, "sugestoes": 0})
            d["situacao_nome"] = rotulo(SITUACOES_DEMANDA, d["situacao"])
            d["tipo_nome"] = rotulo(TIPOS_DEMANDA, d["tipo"])
        return ds

    def demanda(self, did):
        d = next((x for x in self.demandas() if x["id"] == int(did)), None)
        if not d:
            return None
        d["obrigacoes"] = self.obrigacoes({"demanda": int(did)})
        d["historico"] = self.historico_de("demanda", did)
        return d

    # ---------------------------------------------------------------- providências (obrigações)
    OCOLS = ("id", "documento", "processo", "tipo", "origem", "descricao", "destinatario", "frase", "regra", "prazo_quantidade", "prazo_unidade",
             "prazo_frase", "prazo_natureza", "finalidade", "status", "motivo", "decidido_em", "criado", "quadro", "demanda", "situacao_cumprimento",
             "prioridade", "observacoes", "responsavel", "responsavel_assinatura", "aguarda_decisao", "achado", "valor_original")

    def _obrigacoes_raw(self, onde="1=1", *a):
        return self._dicts("SELECT %s FROM sei_obrigacoes WHERE removido_em IS NULL AND %s ORDER BY id DESC" % (", ".join(self.OCOLS), onde), *a)

    def obrigacoes(self, filtro=None):
        f = dict(filtro or {})
        onde, a = ["1=1"], []
        for k in ("id", "demanda", "achado", "processo"):
            if f.get(k) not in (None, ""):
                onde.append("%s=?" % k)
                a.append(f[k])
        if f.get("status"):
            onde.append("status=?")
            a.append(f["status"])
        hoje = date.today()
        with self._trava:
            obr = self._obrigacoes_raw(" AND ".join(onde), *a)
            docs = {r[0]: r[1] for r in self._q("SELECT id, titulo FROM sei_documentos").fetchall()}
            dem = {r[0]: r[1] for r in self._q("SELECT id, assunto FROM nus_demandas WHERE removido_em IS NULL").fetchall()}
            for o in obr:
                o["documento_titulo"] = docs.get(o["documento"], "")
                o["demanda_assunto"] = dem.get(o["demanda"], "")
                o["tipo_nome"] = rotulo(TIPOS_OBRIGACAO, o["tipo"])
                o["cumprimento_nome"] = rotulo(CUMPRIMENTO, o["situacao_cumprimento"] or "nao_avaliada")
                o["prazo"] = self._situacao_prazo(self._prazos_de(o["id"]), hoje)
                o["comunicacao"] = self._estado_com_obrigacao(o["id"])
                o["estado"] = self._estado_de_leitura(o, hoje)
        if f.get("estado"):
            obr = [o for o in obr if o["estado"] == f["estado"]]
        return obr

    def obrigacao(self, oid):
        with self._trava:
            r = self._obrigacoes_raw("id=?", int(oid))
        if not r:
            return None
        o = self.obrigacoes({"id": int(oid)})[0]
        hoje = date.today()
        with self._trava:
            o["prazos"] = []
            for p in self._prazos_de(int(oid)):
                p["alteracoes"] = self._dicts("SELECT * FROM nus_prazo_alteracoes WHERE prazo=? ORDER BY id", p["id"])
                p["vencimento_efetivo"] = self._venc_efetivo(p)
                p["situacao"] = self._situacao_prazo([p], hoje)
                p["natureza_nome"], p["origem_nome"], p["finalidade_nome"] = (rotulo(NATUREZAS, p["natureza"]), rotulo(ORIGENS_PRAZO, p["origem"]),
                                                                              rotulo(FINALIDADES, p["finalidade"]))
                o["prazos"].append(p)
            o["lacunas"] = self._dicts("SELECT * FROM nus_lacunas WHERE obrigacao=? ORDER BY id", int(oid))
            o["comunicacoes"] = [self._comunicacao_dict(c) for c in self._dicts("SELECT c.* FROM nus_comunicacoes c JOIN nus_com_obrigacoes x ON "
                                                                                 "x.comunicacao=c.id WHERE x.obrigacao=? AND c.removido_em IS NULL", int(oid))]
            o["avaliacoes_cumprimento"] = self._dicts("SELECT * FROM nus_avaliacoes WHERE alvo='obrigacao' AND alvo_id=? ORDER BY id DESC", int(oid))
            o["decisoes"] = self._dicts("SELECT de, para, motivo, quem, quando, valor_anterior, valor_novo FROM sei_decisoes WHERE obrigacao=? ORDER BY id DESC", int(oid))
            o["etapas"] = self._etapas(o)
            o["minutas"] = self._dicts("SELECT * FROM nus_minutas WHERE obrigacao=? AND removido_em IS NULL", int(oid))
            if o.get("achado"):
                o["achado_dados"] = (self._dicts("SELECT a.*, i.estabelecimento, i.data AS insp_data FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao "
                                                 "WHERE a.id=?", o["achado"]) or [None])[0]
        o["historico"] = self.historico_de("obrigacao", oid)
        o["campos_faltantes"] = self.campos_faltantes(o)
        return o

    def obrigacao_criar(self, dados, quem):
        """Providência registrada à mão (ou a partir de um achado): é fato desde já (quem registrou responde por ela)."""
        quem = _quem(quem)
        d = dict(dados or {})
        desc = _t(d.get("descricao"), LIMITE)
        if not desc:
            raise Erro("Descreva a providência.")
        tipo = d.get("tipo") or "outro"
        origem = d.get("origem") or "manual"
        if tipo not in dict(TIPOS_OBRIGACAO) or origem not in dict(ORIGENS_OBRIGACAO):
            raise Erro("Tipo ou origem inválidos.")
        fonte = _t(d.get("fonte"), 1000) or "registrada à mão por %s" % quem
        with self._trava, self._con:
            c = self._q("INSERT INTO sei_obrigacoes(documento, processo, tipo, origem, descricao, destinatario, frase, regra, status, criado, demanda, "
                        "achado, prioridade, responsavel, situacao_cumprimento) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        d.get("documento") or None, _t(d.get("processo"), 60), tipo, origem, desc, _t(d.get("destinatario")), fonte, "manual",
                        "validada", _agora(), d.get("demanda") or None, d.get("achado") or None, d.get("prioridade") or "normal",
                        _t(d.get("responsavel") or "", 100), "nao_avaliada")
            oid = c.lastrowid
            self._q("INSERT INTO sei_decisoes(obrigacao, de, para, motivo, quando, quem) VALUES(?,?,?,?,?,?)", oid, "", "validada",
                    "registrada à mão", _agora(), quem)
            self._hist("obrigacao", oid, "criação", "", desc[:200], quem)
            if d.get("achado"):
                self._hist("achado", d["achado"], "providência vinculada", "", desc[:200], quem)
        return {"ok": True, "id": oid}

    CAMPOS_OBRIGACAO = {"prioridade": "Prioridade", "observacoes": "Observações", "destinatario": "Destinatário", "responsavel": "Responsável",
                        "responsavel_assinatura": "Responsável pela assinatura", "aguarda_decisao": "Encaminhada à coordenação", "demanda": "Demanda",
                        "achado": "Achado de inspeção", "tipo": "Tipo"}

    def obrigacao_editar(self, oid, campo, valor, quem, motivo=""):
        quem = _quem(quem)
        if campo not in self.CAMPOS_OBRIGACAO:
            raise Erro("Este campo não pode ser editado.")
        if campo == "prioridade" and valor not in dict(PRIORIDADES):
            raise Erro("Prioridade inválida.")
        if campo == "tipo" and valor not in dict(TIPOS_OBRIGACAO):
            raise Erro("Tipo inválido.")
        if campo in ("demanda", "achado"):
            valor = int(valor) if valor not in (None, "", 0, "0") else None
            if valor is None and not _t(motivo):
                raise Erro("Informe o motivo para desvincular.")
        elif campo == "aguarda_decisao":
            valor = 1 if valor in (True, 1, "1", "true", "sim") else 0
        else:
            valor = _t(valor, LIMITE)
        with self._trava, self._con:
            r = self._um("SELECT %s, descricao FROM sei_obrigacoes WHERE id=? AND removido_em IS NULL" % campo, int(oid))
            if not r:
                raise Erro("Providência não encontrada.")
            if r[0] == valor:
                return {"ok": True, "igual": True}
            if campo == "demanda" and valor and not self._um("SELECT 1 FROM nus_demandas WHERE id=? AND removido_em IS NULL", valor):
                raise Erro("Demanda não encontrada.")
            self._q("UPDATE sei_obrigacoes SET %s=? WHERE id=?" % campo, valor, int(oid))
            self._hist("obrigacao", oid, self.CAMPOS_OBRIGACAO[campo], r[0] if r[0] is not None else "", valor if valor is not None else "(desvinculada)",
                       quem, motivo)
            if campo == "demanda":
                for d, txt in ((r[0], "(desvinculada)"), (valor, r[1][:200])):
                    if d:
                        self._hist("demanda", d, "vínculo com providência", "" if d == valor else r[1][:200], txt if d != valor else r[1][:200], quem, motivo)
        return {"ok": True}

    def obrigacao_decidir(self, oid, decisao, quem, justificativa="", novo_texto=""):
        """Validar, rejeitar (justificativa), ajustar (novo texto + justificativa) ou voltar a sugestão. Validada com prazo no texto:
        o prazo vem como SUGESTÃO (natureza expressa, sem vencimento) e abre-se a lacuna do termo inicial."""
        quem = _quem(quem)
        if decisao not in ("validada", "rejeitada", "ajustada", "sugestao"):
            raise Erro("Decisão inválida.")
        if decisao in ("rejeitada", "ajustada") and not _t(justificativa):
            raise Erro("Rejeitar ou ajustar exige justificativa.")
        if decisao == "ajustada" and not _t(novo_texto):
            raise Erro("O ajuste exige o novo texto da providência.")
        with self._trava, self._con:
            o = self._um("SELECT status, descricao, prazo_quantidade, prazo_unidade, prazo_frase, prazo_natureza, documento, finalidade FROM sei_obrigacoes "
                         "WHERE id=? AND removido_em IS NULL", int(oid))
            if not o:
                raise Erro("Providência não encontrada.")
            if o[0] == "substituida":
                raise Erro("A sugestão é de uma versão substituída do documento.")
            anterior, novo = (o[1], _t(novo_texto, LIMITE)) if decisao == "ajustada" else ("", "")
            if decisao == "ajustada":
                self._q("UPDATE sei_obrigacoes SET descricao=?, valor_original=COALESCE(valor_original, ?) WHERE id=?", novo, o[1], int(oid))
            self._q("UPDATE sei_obrigacoes SET status=?, motivo=?, decidido_em=? WHERE id=?", decisao, _t(justificativa, 600), _agora(), int(oid))
            self._q("INSERT INTO sei_decisoes(obrigacao, de, para, motivo, quando, quem, valor_anterior, valor_novo) VALUES(?,?,?,?,?,?,?,?)",
                    int(oid), o[0], decisao, _t(justificativa, 600), _agora(), quem, anterior, novo)
            if decisao in STATUS_FATO and not self._um("SELECT 1 FROM nus_prazos WHERE obrigacao=?", int(oid)):
                fin = "resposta" if o[7] == "resposta" else "outra"
                if o[2] is not None:
                    self._prazo_inserir(int(oid), "expresso", fin, "nao_informada", "", "", int(o[2]), o[3] or "", None, "", o[6], o[4] or "", quem)
                elif o[5] == "nao_identificado":
                    self._prazo_inserir(int(oid), "nao_identificado", fin, "nao_informada", "", "", None, "", None, "", o[6], "", quem)
        return {"ok": True}

    def _etapas(self, o):
        coms = o.get("comunicacoes") or []
        resps = [r for c in coms for r in c["respostas"]]
        avaliou = any(a["status"] in STATUS_FATO for a in o.get("avaliacoes_cumprimento") or [])
        feitas = [True, True, bool(coms), any(c["data_envio"] for c in coms), any(c["data_envio"] for c in coms), bool(resps),
                  any(r["documento"] for r in resps), avaliou, o.get("situacao_cumprimento") == "cumprida"]
        notas = {0: "documento de origem da providência", 3: "sem registro próprio; inferida pelo envio", 4: "etapa humana externa, registrada pela pessoa"}
        out, atual = [], False
        for i, (rot, feita) in enumerate(zip(ETAPAS, feitas)):
            est = "feita" if feita else ("pendente" if atual else "atual")
            atual = atual or not feita
            out.append({"rotulo": rot, "estado": est, "externa": i == 4, "nota": notas.get(i, "")})
        return out

    def _estado_de_leitura(self, o, hoje):
        """Estado da providência (só leitura, derivado das dimensões; nada é gravado)."""
        if o["status"] == "rejeitada":
            return "Rejeitada"
        if o["status"] not in STATUS_FATO:
            return "Identificada"
        cum = {"cumprida": "Cumprida integralmente", "parcial": "Cumprida parcialmente", "sem_comprovacao": "Não cumprida", "prejudicada": "Encerrada",
               "pendente": "Em análise"}
        if (o.get("situacao_cumprimento") or "nao_avaliada") in cum:
            return cum[o["situacao_cumprimento"]]
        com = o.get("comunicacao") or "sem_comunicacao"
        if com == "sem_comunicacao":
            m = self._um("SELECT MAX(v.status) FROM nus_minutas n JOIN nus_minuta_versoes v ON v.minuta=n.id WHERE n.obrigacao=? AND n.removido_em IS NULL", o["id"])
            return "Em elaboração" if m and m[0] else "Aguardando início"
        if com == "aguardando_envio":
            return "Aguardando envio"
        if com == "aguardando_resposta":
            venc = [p for p in self._prazos_de(o["id"]) if p["status"] in STATUS_FATO and (self._venc_efetivo(p) or "9999") < hoje.isoformat()]
            return "Aguardando reiteração" if venc else "Aguardando resposta"
        avaliada = self._um("SELECT 1 FROM nus_avaliacoes a JOIN nus_respostas r ON a.alvo='resposta' AND a.alvo_id=r.id JOIN nus_com_obrigacoes x "
                            "ON x.comunicacao=r.comunicacao WHERE x.obrigacao=? LIMIT 1", o["id"])
        if avaliada:
            return "Em análise"
        return "Juntada identificada" if com == "resposta_juntada" else "Resposta recebida"

    def campos_faltantes(self, o):
        faltam = []
        if not o.get("destinatario"):
            faltam.append("destinatário")
        if not o.get("responsavel"):
            faltam.append("responsável")
        if not o.get("responsavel_assinatura"):
            faltam.append("responsável pela assinatura")
        if not any(p["status"] in STATUS_FATO for p in o.get("prazos") or []):
            faltam.append("prazo validado")
        if not o.get("processo"):
            faltam.append("processo de origem")
        return faltam

    # ---------------------------------------------------------------- prazos
    def regras(self):
        with self._trava:
            return self._dicts("SELECT * FROM nus_regras ORDER BY nome")

    def regra_criar(self, dados, quem):
        """Regra de contagem: o conteúdo é decisão da coordenação; nada vem pré-cadastrado. Nasce NÃO aprovada."""
        quem = _quem(quem)
        d = dict(dados or {})
        nome = _t(d.get("nome"), 120)
        if not nome:
            raise Erro("Dê um nome à regra.")
        if d.get("dias") not in ("corridos", "uteis"):
            raise Erro("Escolha dias corridos ou dias úteis.")
        with self._trava, self._con:
            if self._um("SELECT 1 FROM nus_regras WHERE nome=?", nome):
                raise Erro("Já existe uma regra com esse nome.")
            c = self._q("INSERT INTO nus_regras(nome, descricao, dias, feriados, fonte_normativa, aprovada, vigencia_inicio, vigencia_fim, criada, quem) "
                        "VALUES(?,?,?,?,?,0,?,?,?,?)", nome, _t(d.get("descricao"), LIMITE), d["dias"], _t(d.get("feriados"), LIMITE),
                        _t(d.get("fonte_normativa")), data_iso(d.get("vigencia_inicio"), "vigência"), data_iso(d.get("vigencia_fim"), "vigência"), _agora(), quem)
            self._hist("regra", c.lastrowid, "criação", "", nome, quem)
        return {"ok": True, "id": c.lastrowid}

    def regra_aprovar(self, rid, quem, aprovar=True, motivo=""):
        quem = _quem(quem)
        with self._trava, self._con:
            r = self._um("SELECT aprovada FROM nus_regras WHERE id=?", int(rid))
            if not r:
                raise Erro("Regra não encontrada.")
            if not aprovar and not _t(motivo):
                raise Erro("Informe o motivo para retirar a aprovação.")
            self._q("UPDATE nus_regras SET aprovada=?, aprovada_por=?, aprovada_em=? WHERE id=?", 1 if aprovar else 0, quem, _agora(), int(rid))
            self._hist("regra", rid, "aprovação", "aprovada" if r[0] else "não aprovada", "aprovada" if aprovar else "não aprovada", quem, motivo)
        return {"ok": True}

    def _prazos_de(self, oid):
        return self._dicts("SELECT * FROM nus_prazos WHERE obrigacao=? ORDER BY id", int(oid))

    def _venc_efetivo(self, p):
        u = self._um("SELECT novo_vencimento FROM nus_prazo_alteracoes WHERE prazo=? ORDER BY data DESC, id DESC LIMIT 1", p["id"])
        return u[0] if u and u[0] else (p.get("vencimento") or "")

    def calcular_vencimento(self, regra, termo, quantidade, unidade):
        """Só com regra APROVADA, de dias corridos, termo inicial e quantidade em dias. Senão: sem vencimento."""
        if not regra or not regra["aprovada"] or not termo or quantidade is None or unidade != "dias" or regra["dias"] != "corridos":
            return ""
        return (date.fromisoformat(termo) + timedelta(days=int(quantidade))).isoformat()

    def _prazo_inserir(self, oid, natureza, finalidade, origem, termo, fonte_termo, quantidade, unidade, regra_id, vencimento, fonte_doc, fonte_trecho, quem,
                       status="sugestao"):
        c = self._q("INSERT INTO nus_prazos(obrigacao, finalidade, natureza, origem, termo_inicial, fonte_termo, quantidade, unidade, regra, vencimento, "
                    "fonte_doc, fonte_trecho, status, criado, quem) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", oid, finalidade, natureza, origem, termo,
                    _t(fonte_termo, 1000), quantidade, unidade, regra_id, vencimento, fonte_doc, _t(fonte_trecho, 1000), status, _agora(), quem)
        pid = c.lastrowid
        if natureza == "nao_identificado":
            self._q("INSERT INTO nus_lacunas(tipo, descricao, obrigacao, prazo, criada) VALUES(?,?,?,?,?)", "prazo_nao_identificado",
                    "Nenhum prazo identificado no documento de origem.", oid, pid, _agora())
        elif natureza == "expresso" and not vencimento:
            self._q("INSERT INTO nus_lacunas(tipo, descricao, obrigacao, prazo, criada) VALUES(?,?,?,?,?)", "prazo_sem_termo",
                    "Prazo expresso sem data de vencimento nem termo inicial documentado.", oid, pid, _agora())
        self._hist("prazo", pid, "criação", "", "%s %s %s" % (rotulo(NATUREZAS, natureza), quantidade or "", unidade or ""), quem)
        return pid

    def prazo_registrar(self, oid, dados, quem):
        """Prazo informado pela pessoa. Calculado: regra aprovada (dias corridos), termo inicial e a fonte do termo. Expresso com data
        no documento: o vencimento é o do documento. Nunca se presume termo inicial."""
        quem = _quem(quem)
        d = dict(dados or {})
        nat = d.get("natureza")
        if nat not in dict(NATUREZAS):
            raise Erro("Escolha a natureza do prazo.")
        fin, ori = d.get("finalidade") or "outra", d.get("origem") or "nao_informada"
        if fin not in dict(FINALIDADES) or ori not in dict(ORIGENS_PRAZO):
            raise Erro("Finalidade ou origem inválidas.")
        qtd = d.get("quantidade")
        qtd = int(qtd) if str(qtd or "").strip().isdigit() else None
        un = _t(d.get("unidade") or ("dias" if qtd is not None else ""), 20)
        termo = data_iso(d.get("termo_inicial"), "data do termo inicial")
        venc = data_iso(d.get("vencimento"), "data de vencimento")
        fonte = _t(d.get("fonte"), 1000)
        if not fonte:
            raise Erro("Diga a fonte do prazo (documento e trecho).")
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM sei_obrigacoes WHERE id=? AND removido_em IS NULL", int(oid)):
                raise Erro("Providência não encontrada.")
            regra = None
            if d.get("regra"):
                regra = (self._dicts("SELECT * FROM nus_regras WHERE id=?", int(d["regra"])) or [None])[0]
            if nat == "calculado":
                if not regra or not regra["aprovada"]:
                    raise Erro("Prazo calculado exige regra de contagem aprovada pela coordenação.")
                if not termo or not _t(d.get("fonte_termo")):
                    raise Erro("Prazo calculado exige termo inicial documentado (com a fonte).")
                if regra["dias"] == "uteis":
                    raise Erro("Dias úteis exigem calendário de feriados aprovado (decisão pendente): não é calculado.")
                if qtd is None or un != "dias":
                    raise Erro("Só é calculada a contagem em dias: confira quantidade e unidade.")
                venc = self.calcular_vencimento(regra, termo, qtd, un)
            elif nat == "nao_identificado":
                venc, qtd, un = "", None, ""
            elif venc and not regra and not fonte:
                raise Erro("Vencimento sem regra só com a data expressa no documento (fonte).")
            pid = self._prazo_inserir(int(oid), nat, fin, ori, termo, d.get("fonte_termo"), qtd, un, regra["id"] if regra else None, venc, d.get("fonte_doc"),
                                      fonte, quem)
        return {"ok": True, "id": pid}

    def prazo_decidir(self, pid, decisao, quem, justificativa=""):
        quem = _quem(quem)
        if decisao not in ("validada", "rejeitada", "sugestao"):
            raise Erro("Decisão inválida.")
        if decisao == "rejeitada" and not _t(justificativa):
            raise Erro("Rejeitar exige justificativa.")
        with self._trava, self._con:
            r = self._um("SELECT status FROM nus_prazos WHERE id=?", int(pid))
            if not r:
                raise Erro("Prazo não encontrado.")
            self._q("UPDATE nus_prazos SET status=? WHERE id=?", decisao, int(pid))
            self._hist("prazo", pid, "validação", r[0], decisao, quem, justificativa)
        return {"ok": True}

    def prazo_completar(self, pid, dados, quem):
        """Completa o prazo SUGERIDO (origem, finalidade, termo inicial com fonte, regra): o anterior fica no histórico."""
        quem = _quem(quem)
        d = dict(dados or {})
        with self._trava, self._con:
            p = (self._dicts("SELECT * FROM nus_prazos WHERE id=?", int(pid)) or [None])[0]
            if not p:
                raise Erro("Prazo não encontrado.")
            if p["status"] in STATUS_FATO:
                raise Erro("Prazo já validado: use prorrogação, suspensão ou alteração.")
            novo = dict(p)
            for k in ("origem", "finalidade"):
                if d.get(k):
                    novo[k] = d[k]
            if d.get("termo_inicial") is not None:
                novo["termo_inicial"] = data_iso(d.get("termo_inicial"), "data do termo inicial")
                novo["fonte_termo"] = _t(d.get("fonte_termo"), 1000)
                if novo["termo_inicial"] and not novo["fonte_termo"]:
                    raise Erro("Diga de onde vem o termo inicial (documento e trecho).")
            if d.get("vencimento"):
                novo["vencimento"] = data_iso(d["vencimento"], "data de vencimento")
            if d.get("regra"):
                regra = (self._dicts("SELECT * FROM nus_regras WHERE id=?", int(d["regra"])) or [None])[0]
                if not regra:
                    raise Erro("Regra não encontrada.")
                novo["regra"] = regra["id"]
                calc = self.calcular_vencimento(regra, novo["termo_inicial"], novo["quantidade"], novo["unidade"])
                if calc:
                    novo["natureza"], novo["vencimento"] = "calculado", calc
            for k in ("origem", "finalidade", "termo_inicial", "fonte_termo", "vencimento", "regra", "natureza"):
                if novo[k] != p[k]:
                    self._q("UPDATE nus_prazos SET %s=? WHERE id=?" % k, novo[k], int(pid))
                    self._hist("prazo", pid, k, p[k] or "", novo[k] or "", quem)
            if novo["vencimento"] or novo["termo_inicial"]:
                self._q("UPDATE nus_lacunas SET aberta=0, fechada_em=?, fechada_por=?, motivo=? WHERE prazo=? AND tipo='prazo_sem_termo' AND aberta=1",
                        _agora(), quem, "termo inicial/vencimento informado", int(pid))
        return {"ok": True}

    def prazo_alterar(self, pid, dados, quem):
        quem = _quem(quem)
        d = dict(dados or {})
        tipo = d.get("tipo")
        if tipo not in dict(ALTERACOES_PRAZO):
            raise Erro("Escolha o tipo de alteração.")
        if not _t(d.get("motivo")):
            raise Erro("A alteração de prazo exige o motivo.")
        if not _t(d.get("fonte")):
            raise Erro("Diga a fonte da alteração (documento e trecho).")
        with self._trava, self._con:
            p = (self._dicts("SELECT * FROM nus_prazos WHERE id=?", int(pid)) or [None])[0]
            if not p:
                raise Erro("Prazo não encontrado.")
            ant = self._venc_efetivo(p)
            novo = data_iso(d.get("novo_vencimento"), "novo vencimento") if tipo != "suspensao" else data_iso(d.get("novo_vencimento"), "novo vencimento")
            self._q("INSERT INTO nus_prazo_alteracoes(prazo, tipo, data, vencimento_anterior, novo_vencimento, motivo, fonte, quem, quando) VALUES(?,?,?,?,?,?,?,?,?)",
                    int(pid), tipo, data_iso(d.get("data") or date.today().isoformat(), "data", True), ant, novo, _t(d.get("motivo"), 600),
                    _t(d.get("fonte"), 1000), quem, _agora())
            self._hist("prazo", pid, rotulo(ALTERACOES_PRAZO, tipo), br(ant), br(novo) or "(sem data)", quem, d.get("motivo"))
        return {"ok": True}

    def _situacao_prazo(self, prazos, hoje):
        """Resumo do prazo: só prazo VALIDADO conta como fato; não validado nunca vira "vencido"."""
        validados = [p for p in prazos if p["status"] in STATUS_FATO]
        com_data = sorted((self._venc_efetivo(p), p) for p in validados if self._venc_efetivo(p))
        if com_data:
            d = date.fromisoformat(com_data[0][0])
            txt = "%s (%s)" % (d.strftime("%d/%m/%Y"), DIAS_SEMANA[d.weekday()])
            dias = (d - hoje).days
            if dias < 0:
                return {"rotulo": "Venceu em %s, há %d dia%s" % (txt, -dias, "s" if dias != -1 else ""), "nivel": "crit", "ordem": 0, "data": d.isoformat(), "dias": dias}
            if dias == 0:
                return {"rotulo": "Vence hoje, %s" % txt, "nivel": "urg", "ordem": 1, "data": d.isoformat(), "dias": 0}
            return {"rotulo": "Vence em %s, %s" % (txt, "falta 1 dia" if dias == 1 else "faltam %d dias" % dias), "nivel": "urg" if dias <= 2 else "prox",
                    "ordem": 1, "data": d.isoformat(), "dias": dias}
        q = lambda p: ("%s %s" % (p["quantidade"], p["unidade"] or "")).strip() if p["quantidade"] is not None else "prazo sem quantidade"
        if validados:
            return {"rotulo": "%s — contagem não definida" % q(validados[0]), "nivel": "neu", "ordem": 2}
        if prazos:
            nat = [p for p in prazos if p["natureza"] != "nao_identificado"]
            if nat:
                return {"rotulo": "Prazo sugerido (não validado): %s" % q(nat[0]), "nivel": "med", "ordem": 2}
        return {"rotulo": "Prazo não identificado", "nivel": "neu", "ordem": 3}

    def prazos(self):
        """Todos os prazos (painel de prazos): vencidos primeiro, depois os com data, os sem data e os sugeridos."""
        hoje = date.today()
        with self._trava:
            ps = self._dicts("SELECT p.*, o.descricao AS obrigacao_descricao, o.processo, o.status AS obrigacao_status FROM nus_prazos p JOIN sei_obrigacoes o "
                             "ON o.id=p.obrigacao WHERE o.removido_em IS NULL AND o.status<>'rejeitada' AND p.status<>'rejeitada'")
            for p in ps:
                p["vencimento_efetivo"] = self._venc_efetivo(p)
                p["situacao"] = self._situacao_prazo([p], hoje)
                p["natureza_nome"], p["origem_nome"] = rotulo(NATUREZAS, p["natureza"]), rotulo(ORIGENS_PRAZO, p["origem"])
        return sorted(ps, key=lambda p: (p["situacao"]["ordem"], p["situacao"].get("data") or "9999", p["id"]))

    def lacunas(self, abertas=True):
        with self._trava:
            return self._dicts("SELECT l.*, o.descricao AS obrigacao_descricao, o.processo FROM nus_lacunas l LEFT JOIN sei_obrigacoes o ON o.id=l.obrigacao "
                               "WHERE (? = 0 OR l.aberta=1) ORDER BY l.id DESC", 1 if abertas else 0)

    def lacuna_fechar(self, lid, quem, motivo):
        quem = _quem(quem)
        if not _t(motivo):
            raise Erro("Diga como a lacuna foi resolvida.")
        with self._trava, self._con:
            n = self._q("UPDATE nus_lacunas SET aberta=0, fechada_em=?, fechada_por=?, motivo=? WHERE id=? AND aberta=1", _agora(), quem, _t(motivo, 600),
                        int(lid)).rowcount
            if not n:
                raise Erro("Lacuna não encontrada (ou já fechada).")
            self._hist("lacuna", lid, "fechada", "aberta", "fechada", quem, motivo)
        return {"ok": True}

    def lacuna_abrir(self, dados, quem):
        quem = _quem(quem)
        d = dict(dados or {})
        if d.get("tipo") not in dict(TIPOS_LACUNA) or not _t(d.get("descricao")):
            raise Erro("Escolha o tipo e descreva o que falta.")
        with self._trava, self._con:
            c = self._q("INSERT INTO nus_lacunas(tipo, descricao, obrigacao, prazo, criada) VALUES(?,?,?,?,?)", d["tipo"], _t(d["descricao"], LIMITE),
                        d.get("obrigacao") or None, d.get("prazo") or None, _agora())
            self._hist("lacuna", c.lastrowid, "aberta", "", _t(d["descricao"], 200), quem)
        return {"ok": True, "id": c.lastrowid}

    # ---------------------------------------------------------------- comunicações, respostas, avaliações
    def _estado_comunicacao(self, c, respostas):
        if not c["data_envio"]:
            return "aguardando_envio"
        if not respostas:
            return "aguardando_resposta"
        return "resposta_juntada" if any(r["documento"] for r in respostas) else "resposta_sem_juntada"

    def _comunicacao_dict(self, c):
        c = dict(c)
        c["respostas"] = self._dicts("SELECT * FROM nus_respostas WHERE comunicacao=? ORDER BY id", c["id"])
        for r in c["respostas"]:
            r["avaliacoes"] = self._dicts("SELECT * FROM nus_avaliacoes WHERE alvo='resposta' AND alvo_id=? ORDER BY id DESC", r["id"])
        c["reiteracoes"] = self._dicts("SELECT * FROM nus_reiteracoes WHERE comunicacao=? ORDER BY id", c["id"])
        c["obrigacoes"] = [r[0] for r in self._q("SELECT obrigacao FROM nus_com_obrigacoes WHERE comunicacao=?", c["id"]).fetchall()]
        c["estado"] = self._estado_comunicacao(c, c["respostas"])
        c["estado_nome"] = {"aguardando_envio": "Aguardando envio", "aguardando_resposta": "Aguardando resposta",
                            "resposta_sem_juntada": "Resposta sem juntada", "resposta_juntada": "Resposta juntada"}[c["estado"]]
        return c

    def _estado_com_obrigacao(self, oid):
        cs = self._dicts("SELECT c.* FROM nus_comunicacoes c JOIN nus_com_obrigacoes x ON x.comunicacao=c.id WHERE x.obrigacao=? AND c.removido_em IS NULL", oid)
        if not cs:
            return "sem_comunicacao"
        # a comunicação menos avançada manda: não se declara respondido o que ainda aguarda
        est = [self._estado_comunicacao(c, self._dicts("SELECT documento FROM nus_respostas WHERE comunicacao=?", c["id"])) for c in cs]
        return min(est, key=ORDEM_COMUNICACAO.index)

    def comunicacoes(self):
        with self._trava:
            return [self._comunicacao_dict(c) for c in self._dicts("SELECT * FROM nus_comunicacoes WHERE removido_em IS NULL ORDER BY id DESC")]

    def comunicacao_criar(self, dados, quem):
        """Ofício (ou e-mail) que cumpre ou cobra providências. O APTO não envia: só registra o que a pessoa fez no SEI."""
        quem = _quem(quem)
        d = dict(dados or {})
        if not _t(d.get("assunto")) or not _t(d.get("destinatario")):
            raise Erro("Informe o assunto e o destinatário.")
        obr = [int(x) for x in d.get("obrigacoes") or []]
        with self._trava, self._con:
            envio = data_iso(d.get("data_envio"), "data de envio")
            c = self._q("INSERT INTO nus_comunicacoes(assunto, documento, processo, destinatario, meio, data_envio, criada, quem) VALUES(?,?,?,?,?,?,?,?)",
                        _t(d["assunto"]), d.get("documento") or None, _t(d.get("processo"), 60), _t(d["destinatario"]), _t(d.get("meio") or "ofício", 60),
                        envio, _agora(), quem)
            cid = c.lastrowid
            if envio:
                self._q("UPDATE nus_comunicacoes SET peca=? WHERE id=?", self._peca_oficio(None, envio, _t(d["assunto"]), _t(d.get("processo"), 60), quem), cid)
            for o in obr:
                self._q("INSERT OR IGNORE INTO nus_com_obrigacoes VALUES(?,?)", cid, o)
                self._hist("obrigacao", o, "comunicação", "", _t(d["assunto"], 200), quem)
            self._hist("comunicacao", cid, "criação", "", _t(d["assunto"], 200), quem)
        return {"ok": True, "id": cid}

    def comunicacao_envio(self, cid, data, quem):
        quem = _quem(quem)
        iso = data_iso(data, "data de envio", True)
        with self._trava, self._con:
            r = self._um("SELECT data_envio FROM nus_comunicacoes WHERE id=? AND removido_em IS NULL", int(cid))
            if not r:
                raise Erro("Comunicação não encontrada.")
            self._q("UPDATE nus_comunicacoes SET data_envio=? WHERE id=?", iso, int(cid))
            self._hist("comunicacao", cid, "envio registrado", br(r[0] or ""), br(iso), quem)
            c = self._um("SELECT assunto, processo, peca FROM nus_comunicacoes WHERE id=?", int(cid))
            self._q("UPDATE nus_comunicacoes SET peca=? WHERE id=?", self._peca_oficio(c[2], iso, c[0], c[1], quem), int(cid))
        return {"ok": True}

    def comunicacao_vincular(self, cid, oid, quem):
        quem = _quem(quem)
        with self._trava, self._con:
            self._q("INSERT OR IGNORE INTO nus_com_obrigacoes VALUES(?,?)", int(cid), int(oid))
            self._hist("comunicacao", cid, "providência vinculada", "", str(oid), quem)
        return {"ok": True}

    def reiterar(self, cid, data, quem, documento=None):
        quem = _quem(quem)
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM nus_comunicacoes WHERE id=? AND removido_em IS NULL AND data_envio<>''", int(cid)):
                raise Erro("Só se reitera comunicação já enviada.")
            c = self._um("SELECT assunto, processo FROM nus_comunicacoes WHERE id=?", int(cid))
            pid = self._peca_oficio(None, data_iso(data, "data", True), "reiteração: " + c[0], c[1], quem)
            self._q("INSERT INTO nus_reiteracoes(comunicacao, data, documento, quem, quando, peca) VALUES(?,?,?,?,?,?)", int(cid), data_iso(data, "data", True),
                    documento or None, quem, _agora(), pid)
            self._hist("comunicacao", cid, "reiteração", "", br(data_iso(data, "data", True)), quem)
        return {"ok": True}

    def resposta_registrar(self, cid, data, quem, documento=None, observacao=""):
        """Resposta recebida: NÃO é cumprimento. Sem documento = ainda sem juntada."""
        quem = _quem(quem)
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM nus_comunicacoes WHERE id=? AND removido_em IS NULL", int(cid)):
                raise Erro("Comunicação não encontrada.")
            c = self._q("INSERT INTO nus_respostas(comunicacao, data_recebimento, documento, observacao, quem, quando) VALUES(?,?,?,?,?,?)", int(cid),
                        data_iso(data, "data de recebimento", True), documento or None, _t(observacao, LIMITE), quem, _agora())
            self._hist("comunicacao", cid, "resposta recebida", "", br(data_iso(data, "data", True)), quem)
        return {"ok": True, "id": c.lastrowid}

    def resposta_juntar(self, rid, documento, quem):
        quem = _quem(quem)
        if not documento:
            raise Erro("Escolha o documento da juntada.")
        with self._trava, self._con:
            r = self._um("SELECT comunicacao, documento FROM nus_respostas WHERE id=?", int(rid))
            if not r:
                raise Erro("Resposta não encontrada.")
            if r[1]:
                raise Erro("A resposta já tem juntada (registre outra resposta).")
            self._q("UPDATE nus_respostas SET documento=? WHERE id=?", int(documento), int(rid))
            self._hist("comunicacao", r[0], "juntada identificada", "", "documento %s" % documento, quem)
        return {"ok": True}

    def avaliar(self, alvo, alvo_id, resultado, fonte, quem):
        """Avaliação da RESPOSTA (não toca o cumprimento) ou do CUMPRIMENTO da providência. Nasce sugestão."""
        quem = _quem(quem)
        esc = {"resposta": AVAL_RESPOSTA, "obrigacao": AVAL_CUMPRIMENTO}.get(alvo)
        if not esc or resultado not in dict(esc):
            raise Erro("Resultado inválido.")
        if not _t(fonte):
            raise Erro("Diga em que se baseia a avaliação (documento e trecho).")
        with self._trava, self._con:
            c = self._q("INSERT INTO nus_avaliacoes(alvo, alvo_id, resultado, fonte, status, quem, quando) VALUES(?,?,?,?,?,?,?)", alvo, int(alvo_id),
                        resultado, _t(fonte, 1000), "sugestao", quem, _agora())
            self._hist("avaliacao", c.lastrowid, "avaliação registrada", "", rotulo(esc, resultado), quem)
        return {"ok": True, "id": c.lastrowid}

    def avaliacao_decidir(self, aid, decisao, quem, justificativa=""):
        """Só a avaliação VALIDADA vale; a do cumprimento muda a situação da providência (a última validada)."""
        quem = _quem(quem)
        if decisao not in ("validada", "rejeitada"):
            raise Erro("Decisão inválida.")
        if decisao == "rejeitada" and not _t(justificativa):
            raise Erro("Rejeitar exige justificativa.")
        with self._trava, self._con:
            a = self._um("SELECT alvo, alvo_id, status FROM nus_avaliacoes WHERE id=?", int(aid))
            if not a:
                raise Erro("Avaliação não encontrada.")
            self._q("UPDATE nus_avaliacoes SET status=? WHERE id=?", decisao, int(aid))
            self._hist("avaliacao", aid, "validação", a[2], decisao, quem, justificativa)
            if a[0] == "obrigacao":
                u = self._um("SELECT resultado FROM nus_avaliacoes WHERE alvo='obrigacao' AND alvo_id=? AND status IN ('validada','ajustada') "
                             "ORDER BY quando DESC, id DESC LIMIT 1", a[1])
                novo = u[0] if u else "nao_avaliada"
                ant = self._um("SELECT situacao_cumprimento FROM sei_obrigacoes WHERE id=?", a[1])[0]
                if ant != novo:
                    self._q("UPDATE sei_obrigacoes SET situacao_cumprimento=? WHERE id=?", novo, a[1])
                    self._hist("obrigacao", a[1], "cumprimento", rotulo(CUMPRIMENTO, ant), rotulo(CUMPRIMENTO, novo), quem)
        return {"ok": True}

    # ---------------------------------------------------------------- inspeções
    def inspecoes(self):
        with self._trava:
            ins = self._dicts("SELECT * FROM nus_inspecoes WHERE removido_em IS NULL ORDER BY data DESC, id DESC")
            for i in ins:
                i["achados"] = self._achados_de(i["id"])
        return ins

    def _achados_de(self, iid):
        a = self._dicts("SELECT * FROM nus_achados WHERE inspecao=? ORDER BY id", iid)
        for x in a:
            x["categoria_nome"], x["gravidade_nome"], x["situacao_nome"] = (rotulo(CATEGORIAS, x["categoria"]), rotulo(GRAVIDADES, x["gravidade"]),
                                                                            rotulo(SITUACOES_ACHADO, x["situacao"]))
            x["providencias"] = [dict(id=r[0], descricao=r[1], status=r[2], cumprimento=r[3]) for r in self._q(
                "SELECT id, descricao, status, situacao_cumprimento FROM sei_obrigacoes WHERE achado=? AND removido_em IS NULL", x["id"]).fetchall()]
        return a

    def inspecao(self, iid):
        with self._trava:
            i = (self._dicts("SELECT * FROM nus_inspecoes WHERE id=? AND removido_em IS NULL", int(iid)) or [None])[0]
            if not i:
                return None
            i["achados"] = self._achados_de(i["id"])
            for a in i["achados"]:
                a["recorrencias_sugeridas"] = self._sugerir_recorrencias(a, i)
                a["cadeia"] = self._cadeia(a)
            i["documentos"] = self._dicts("SELECT d.id, d.titulo, d.processo FROM nus_insp_documentos x JOIN sei_documentos d ON d.id=x.documento WHERE x.inspecao=?",
                                          int(iid))
            ant = self._um("SELECT id FROM nus_inspecoes WHERE lower(trim(estabelecimento))=lower(trim(?)) AND data<? AND removido_em IS NULL ORDER BY data DESC LIMIT 1",
                           i["estabelecimento"], i["data"])
            i["anterior"] = ant[0] if ant else None
        i["historico"] = self.historico_de("inspecao", iid)
        return i

    def inspecao_criar(self, dados, quem):
        quem = _quem(quem)
        d = dict(dados or {})
        est = _t(d.get("estabelecimento"), 200)
        if not est:
            raise Erro("Informe o estabelecimento.")
        dt = data_iso(d.get("data"), "data da inspeção", True)
        if dt > date.today().isoformat():
            raise Erro("A data da inspeção não pode ser futura.")
        with self._trava, self._con:
            c = self._q("INSERT INTO nus_inspecoes(estabelecimento, municipio, data, observacoes, criada, quem) VALUES(?,?,?,?,?,?)", est,
                        _t(d.get("municipio"), 120), dt, _t(d.get("observacoes"), LIMITE), _agora(), quem)
            self._hist("inspecao", c.lastrowid, "criação", "", "%s em %s" % (est, br(dt)), quem)
            for doc in d.get("documentos") or []:
                self._q("INSERT OR IGNORE INTO nus_insp_documentos VALUES(?,?)", c.lastrowid, int(doc))
        return {"ok": True, "id": c.lastrowid}

    def inspecao_documento(self, iid, documento, quem):
        quem = _quem(quem)
        with self._trava, self._con:
            self._q("INSERT OR IGNORE INTO nus_insp_documentos VALUES(?,?)", int(iid), int(documento))
            self._hist("inspecao", iid, "documento vinculado", "", str(documento), quem)
        return {"ok": True}

    def achado_registrar(self, iid, dados, quem):
        quem = _quem(quem)
        d = dict(dados or {})
        desc = _t(d.get("descricao"), LIMITE + 1)
        if not desc:
            raise Erro("Descreva a situação identificada.")
        if len(desc) > LIMITE or len(d.get("recomendacao") or "") > LIMITE:
            raise Erro("O texto passa do limite.")
        cat, grav = d.get("categoria") or "outra", d.get("gravidade") or "media"
        if cat not in dict(CATEGORIAS) or grav not in dict(GRAVIDADES):
            raise Erro("Categoria ou gravidade inválidas.")
        with self._trava, self._con:
            if not self._um("SELECT 1 FROM nus_inspecoes WHERE id=? AND removido_em IS NULL", int(iid)):
                raise Erro("Inspeção não encontrada.")
            c = self._q("INSERT INTO nus_achados(inspecao, descricao, categoria, gravidade, recomendacao, situacao, documento, criado, quem) VALUES(?,?,?,?,?,?,?,?,?)",
                        int(iid), desc, cat, grav, _t(d.get("recomendacao"), LIMITE), "identificado", d.get("documento") or None, _agora(), quem)
            self._hist("inspecao", iid, "situação identificada", "", desc[:200], quem)
        return {"ok": True, "id": c.lastrowid}

    def achado_situacao(self, aid, nova, quem, motivo=""):
        quem = _quem(quem)
        if nova not in dict(SITUACOES_ACHADO):
            raise Erro("Situação inválida.")
        with self._trava, self._con:
            r = self._um("SELECT situacao FROM nus_achados WHERE id=?", int(aid))
            if not r:
                raise Erro("Achado não encontrado.")
            if r[0] == nova:
                return {"ok": True, "igual": True}
            self._q("UPDATE nus_achados SET situacao=? WHERE id=?", nova, int(aid))
            self._hist("achado", aid, "situação do acompanhamento", rotulo(SITUACOES_ACHADO, r[0]), rotulo(SITUACOES_ACHADO, nova), quem, motivo)
        return {"ok": True}

    def _sugerir_recorrencias(self, a, i):
        """Candidatos por regra (mesmo estabelecimento, mesma categoria, inspeção anterior). Não vincula nada."""
        return self._dicts("SELECT a.id, a.descricao, a.situacao, i.data FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao WHERE "
                           "lower(trim(i.estabelecimento))=lower(trim(?)) AND i.data<? AND a.categoria=? AND a.id<>? AND i.removido_em IS NULL "
                           "ORDER BY i.data DESC, a.id DESC", i["estabelecimento"], i["data"], a["categoria"], a["id"])

    def _cadeia(self, a):
        elos, x, vistos = [], a, set()
        while x and x.get("anterior") and x["anterior"] not in vistos:
            vistos.add(x["anterior"])
            x = (self._dicts("SELECT a.id, a.descricao, a.situacao, a.anterior, i.data FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao WHERE a.id=?",
                             x["anterior"]) or [None])[0]
            if x:
                elos.insert(0, x)
        return elos

    def recorrencia_confirmar(self, aid, anterior, quem, motivo=""):
        quem = _quem(quem)
        with self._trava, self._con:
            a = self._um("SELECT i.estabelecimento, i.data, a.anterior FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao WHERE a.id=?", int(aid))
            b = self._um("SELECT i.estabelecimento, i.data FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao WHERE a.id=?", int(anterior))
            if not a or not b:
                raise Erro("Achado não encontrado.")
            if a[0].strip().lower() != b[0].strip().lower():
                raise Erro("Os achados são de estabelecimentos diferentes.")
            if b[1] >= a[1]:
                raise Erro("O achado anterior deve ser de uma inspeção mais antiga.")
            self._q("UPDATE nus_achados SET anterior=? WHERE id=?", int(anterior), int(aid))
            self._hist("achado", aid, "recorrência confirmada", str(a[2] or ""), "achado #%s (%s)" % (anterior, br(b[1])), quem, motivo)
        return {"ok": True}

    def achado_providencia(self, aid, dados, quem):
        """Cada achado gera providências próprias: a recomendação vira providência (origem: recomendação), ligada ao achado."""
        d = dict(dados or {})
        with self._trava:
            a = self._um("SELECT a.recomendacao, a.descricao, i.estabelecimento, i.data FROM nus_achados a JOIN nus_inspecoes i ON i.id=a.inspecao WHERE a.id=?",
                         int(aid))
        if not a:
            raise Erro("Achado não encontrado.")
        d.setdefault("descricao", a[0] or a[1])
        d.setdefault("origem", "recomendacao")
        d.setdefault("fonte", "inspeção em %s (%s): %s" % (a[2], br(a[3]), a[1][:300]))
        d["achado"] = int(aid)
        return self.obrigacao_criar(d, quem)

    def comparar(self, anterior, atual):
        """Recorrente, somente na anterior (pode ter sido sanado) e nova."""
        with self._trava:
            A, B = self._achados_de(int(anterior)), self._achados_de(int(atual))
        linhas, ligados = [], set()
        for a in A:
            seg = next((b for b in B if b["anterior"] == a["id"]), None)
            if seg:
                ligados.add(seg["id"])
            linhas.append({"categoria": a["categoria_nome"], "situacao": "recorrente" if seg else "somente_na_anterior", "anterior": a, "atual": seg})
        linhas += [{"categoria": b["categoria_nome"], "situacao": "nova", "anterior": None, "atual": b} for b in B if b["id"] not in ligados]
        return sorted(linhas, key=lambda x: (x["categoria"], x["situacao"]))

    # ---------------------------------------------------------------- minutas
    def modelos(self):
        out = [dict(id=k, versao=0, embutido=True, **v) for k, v in MODELOS_EMBUTIDOS.items()]
        with self._trava:
            for r in self._dicts("SELECT * FROM nus_modelos ORDER BY slug, versao"):
                out.append({"id": "%s-v%d" % (r["slug"], r["versao"]), "slug": r["slug"], "versao": r["versao"], "embutido": False, "nome": r["nome"],
                            "descricao": r["descricao"], "formulas": {"abertura": r["abertura"], "pedido": r["pedido"], "fecho": r["fecho"] or ""}})
        return out

    def modelo_cadastrar(self, dados, quem):
        """Modelo da instituição: só acrescenta; mudar = versão seguinte do mesmo nome curto."""
        quem = _quem(quem)
        d = dict(dados or {})
        slug = re.sub(r"[^a-z0-9-]", "", _t(d.get("slug"), 40).lower())
        if not slug or not _t(d.get("nome")) or not _t(d.get("abertura")) or not _t(d.get("pedido")):
            raise Erro("Informe nome curto, nome, abertura e pedido.")
        with self._trava, self._con:
            v = (self._um("SELECT MAX(versao) FROM nus_modelos WHERE slug=?", slug)[0] or 0) + 1
            self._q("INSERT INTO nus_modelos(slug, versao, nome, descricao, abertura, pedido, fecho, quem, criado) VALUES(?,?,?,?,?,?,?,?,?)", slug, v,
                    _t(d["nome"], 120), _t(d.get("descricao"), LIMITE), _t(d["abertura"], LIMITE), _t(d["pedido"], LIMITE), _t(d.get("fecho"), LIMITE), quem, _agora())
        return {"ok": True, "id": "%s-v%d" % (slug, v)}

    def _frases(self, o, hoje, modelo):
        proc = o.get("processo") or "(processo não identificado)"
        tem_doc = bool(o.get("documento"))
        numero = (o.get("documento_titulo") or "documento %s" % o["documento"]) if tem_doc else "registro do núcleo"
        fonte = "%s · «%s»" % (numero, (o.get("frase") or "")[:300])
        s = [("dados", ("No processo %s, o documento %s registra: «%s»." % (proc, numero, o.get("frase") or o["descricao"])) if tem_doc else
              ("No processo %s, consta registro do núcleo: «%s»." % (proc, o.get("frase") or o["descricao"])), fonte),
             ("dados", "A providência identificada é: %s%s." % (o["descricao"].rstrip("."), ", dirigida a %s" % o["destinatario"] if o.get("destinatario") else ""), fonte)]
        val = [p for p in o.get("prazos") or [] if p["status"] in STATUS_FATO]
        for p in val:
            q = ("%s %s" % (p["quantidade"], p["unidade"] or "")).strip() if p["quantidade"] else "sem quantidade"
            s.append(("dados", "Consta prazo %s de %s (origem: %s; %s)." % (rotulo(NATUREZAS, p["natureza"]).lower(), q, rotulo(ORIGENS_PRAZO, p["origem"]).lower(),
                                                                          "contagem: regra registrada" if p["regra"] else "contagem não definida"), p["fonte_trecho"] or fonte))
        coms = o.get("comunicacoes") or []
        for c in coms:
            if c["data_envio"]:
                s.append(("dados", "Foi registrado ofício a %s em %s (%s)." % (c["destinatario"], br(c["data_envio"]), c["assunto"]), fonte))
            for r in c["respostas"]:
                for av in r["avaliacoes"]:
                    if av["status"] in STATUS_FATO:
                        s.append(("dados", "A resposta recebida em %s foi avaliada como: %s." % (br(r["data_recebimento"]), rotulo(AVAL_RESPOSTA, av["resultado"]).lower()),
                                  av["fonte"]))
        ult = next((a for a in o.get("avaliacoes_cumprimento") or [] if a["status"] in STATUS_FATO), None)
        cumprida = False
        if ult is None:
            s.append(("conclusao", "Estaria, em tese, pendente o cumprimento da providência, ressalvada a verificação de %s." % RESSALVA, fonte))
        elif ult["resultado"] in ("sem_comprovacao", "pendente"):
            s.append(("conclusao", "Não há comprovação do cumprimento da providência, conforme avaliação validada em %s." % br(ult["quando"]), ult["fonte"]))
        else:
            cumprida = ult["resultado"] == "cumprida"
            s.append(("conclusao", "A providência foi avaliada como %s, conforme avaliação validada em %s." % (rotulo(AVAL_CUMPRIMENTO, ult["resultado"]).lower(),
                                                                                                             br(ult["quando"])), ult["fonte"]))
        for p in val:
            v = p.get("vencimento_efetivo") or ""
            if v and v < hoje.isoformat() and not cumprida:
                s.append(("consequencia", "O prazo venceu em %s; entre essa data e a conferência de %s há %d dias (diferença entre as datas documentadas, sem "
                          "regra de contagem aprovada)." % (br(v), hoje.strftime("%d/%m/%Y"), (hoje - date.fromisoformat(v)).days), p["fonte_trecho"] or fonte))
                break
        if not cumprida:
            base = "Sem que, até a conferência realizada em %s, constasse dos autos importados" % hoje.strftime("%d/%m/%Y")
            env = [c for c in coms if c["data_envio"]]
            sem = [c for c in env if not c["respostas"]]
            if not coms:
                s.append(("omissao", "%s registro de comunicação ou de outra providência para o cumprimento." % base, fonte))
            elif not env:
                s.append(("omissao", "%s registro de envio do ofício «%s»." % (base, coms[0]["assunto"]), fonte))
            elif sem:
                s.append(("omissao", "%s resposta de %s ao ofício enviado em %s." % (base, sem[0]["destinatario"], br(sem[0]["data_envio"])), fonte))
        if modelo.get("blocos"):
            s = [x for x in s if x[0] == "dados"][:2] + [x for x in s if x[0] == "omissao" and "omissao" in modelo["blocos"]]
        f = modelo.get("formulas") or {}
        if f:
            pv = next((p for p in val if p.get("vencimento_efetivo")), None) or next(iter(val), None)
            prazo = (" até %s" % br(pv["vencimento_efetivo"])) if pv and pv.get("vencimento_efetivo") else \
                (" no prazo de %s %s" % (pv["quantidade"], pv["unidade"] or "dias")) if pv and pv.get("quantidade") else ""
            dest = o.get("destinatario") or ""
            ctx = {"documento": ("no documento %s" % numero) if tem_doc else "em registro do núcleo", "pagina": "", "prazo": prazo,
                   "destinatario": dest or "[destinatário]", "processo": proc, "vocativo": ("A %s," % dest) if dest else "[Destinatário],"}
            s.insert(0, ("abertura", f["abertura"].format(**ctx), "fórmula do modelo %s" % modelo["nome"]))
            s.append(("pedido", f["pedido"].format(**ctx), "fórmula do modelo %s" % modelo["nome"]))
            if f.get("fecho"):
                s.append(("fecho", f["fecho"].format(**ctx), "fórmula do modelo %s" % modelo["nome"]))
        return s

    def minuta_gerar(self, oid, modelo_id, quem):
        """Minuta SUGERIDA para uma providência VALIDADA; só com fatos validados; cada frase com a fonte."""
        quem = _quem(quem)
        o = self.obrigacao(oid)
        if not o:
            raise Erro("Providência não encontrada.")
        if o["status"] not in STATUS_FATO:
            raise Erro("A providência precisa estar validada para gerar a minuta.")
        modelo = next((m for m in self.modelos() if m["id"] == modelo_id), None)
        if not modelo:
            raise Erro("Modelo de minuta desconhecido.")
        hoje = date.today()
        frases = self._frases(o, hoje, modelo)
        with self._trava, self._con:
            m = self._um("SELECT id FROM nus_minutas WHERE obrigacao=? AND removido_em IS NULL ORDER BY id LIMIT 1", int(oid))
            mid = m[0] if m else self._q("INSERT INTO nus_minutas(obrigacao, criada, quem) VALUES(?,?,?)", int(oid), _agora(), quem).lastrowid
            n = (self._um("SELECT MAX(numero) FROM nus_minuta_versoes WHERE minuta=?", mid)[0] or 0) + 1
            vid = self._q("INSERT INTO nus_minuta_versoes(minuta, numero, modelo, quem, data, data_conferencia) VALUES(?,?,?,?,?,?)", mid, n, modelo_id, quem,
                          _agora(), hoje.isoformat()).lastrowid
            for i, (bl, tx, fo) in enumerate(frases, 1):
                self._q("INSERT INTO nus_minuta_frases(versao, ordem, bloco, texto, fonte) VALUES(?,?,?,?,?)", vid, i, bl, tx, _t(fo, 1000))
            self._hist("obrigacao", oid, "minuta gerada", "", "versão %d (%s)" % (n, modelo["nome"]), quem)
        return {"ok": True, "minuta": mid, "versao": vid}

    def minuta(self, mid):
        with self._trava:
            m = (self._dicts("SELECT * FROM nus_minutas WHERE id=?", int(mid)) or [None])[0]
            if not m:
                return None
            m["versoes"] = self._dicts("SELECT * FROM nus_minuta_versoes WHERE minuta=? ORDER BY numero DESC", int(mid))
            for v in m["versoes"]:
                v["frases"] = self._dicts("SELECT * FROM nus_minuta_frases WHERE versao=? ORDER BY ordem", v["id"])
                v["texto_para_sei"] = self._texto_para_sei(v["frases"])
        m["campos_faltantes"] = self.campos_faltantes(self.obrigacao(m["obrigacao"]) or {})
        return m

    @staticmethod
    def _texto_para_sei(frases):
        blocos = {}
        for f in frases:
            blocos.setdefault(f["bloco"], []).append(f["texto"].strip())
        return "\n\n".join(" ".join(p) for p in blocos.values())

    def minuta_editar(self, vid, edicoes, quem):
        """Nova versão com as edições (frase em branco sai); a fonte de cada frase fica."""
        quem = _quem(quem)
        ed = {int(k): str(v) for k, v in dict(edicoes or {}).items()}
        with self._trava, self._con:
            v = (self._dicts("SELECT * FROM nus_minuta_versoes WHERE id=?", int(vid)) or [None])[0]
            if not v:
                raise Erro("Versão não encontrada.")
            n = self._um("SELECT MAX(numero) FROM nus_minuta_versoes WHERE minuta=?", v["minuta"])[0] + 1
            nv = self._q("INSERT INTO nus_minuta_versoes(minuta, numero, modelo, quem, data, data_conferencia) VALUES(?,?,?,?,?,?)", v["minuta"], n, v["modelo"],
                         quem, _agora(), v["data_conferencia"]).lastrowid
            o = 0
            for f in self._dicts("SELECT * FROM nus_minuta_frases WHERE versao=? ORDER BY ordem", int(vid)):
                tx = ed.get(f["id"], f["texto"]).strip()
                if not tx:
                    continue
                o += 1
                self._q("INSERT INTO nus_minuta_frases(versao, ordem, bloco, texto, fonte, editada) VALUES(?,?,?,?,?,?)", nv, o, f["bloco"], tx, f["fonte"],
                        1 if f["editada"] or tx != f["texto"].strip() else 0)
        return {"ok": True, "versao": nv}

    def minuta_restaurar(self, mid, numero, quem):
        quem = _quem(quem)
        with self._trava, self._con:
            v = self._um("SELECT id FROM nus_minuta_versoes WHERE minuta=? AND numero=?", int(mid), int(numero))
            if not v:
                raise Erro("Versão inexistente.")
        r = self.minuta_editar(v[0], {}, quem)
        with self._trava, self._con:
            self._hist("minuta", mid, "versão restaurada", "", "versão %s" % numero, quem)
        return r

    def minuta_validar(self, vid, decisao, quem, justificativa=""):
        quem = _quem(quem)
        if decisao not in ("validada", "rejeitada"):
            raise Erro("Decisão inválida.")
        if decisao == "rejeitada" and not _t(justificativa):
            raise Erro("Rejeitar exige justificativa.")
        with self._trava, self._con:
            v = self._um("SELECT minuta, status, numero FROM nus_minuta_versoes WHERE id=?", int(vid))
            if not v:
                raise Erro("Versão não encontrada.")
            self._q("UPDATE nus_minuta_versoes SET status=? WHERE id=?", decisao, int(vid))
            self._hist("minuta", v[0], "versão %d" % v[2], v[1], decisao, quem, justificativa)
        return {"ok": True}

    # ---------------------------------------------------------------- painel, histórico, relatório, busca
    def painel(self):
        """Contagens para a Visão geral: só o validado conta como fato (sugestões em separado)."""
        obr = self.obrigacoes()
        validas = [o for o in obr if o["status"] in STATUS_FATO]
        est = {}
        for o in validas:
            est[o["estado"]] = est.get(o["estado"], 0) + 1
        prazos = self.prazos()
        return {"providencias": len(validas), "sugestoes": sum(1 for o in obr if o["status"] == "sugestao"), "por_estado": est,
                "vencidos": sum(1 for p in prazos if p["status"] in STATUS_FATO and p["situacao"]["ordem"] == 0),
                "vencem_7": sum(1 for p in prazos if p["status"] in STATUS_FATO and p["situacao"]["ordem"] == 1 and p["situacao"].get("dias", 99) <= 7),
                "lacunas": len(self.lacunas()), "demandas_abertas": sum(1 for d in self.demandas() if d["situacao"] not in ("atendida", "cancelada")),
                "comunicacoes_aguardando": sum(1 for c in self.comunicacoes() if c["estado"] in ("aguardando_envio", "aguardando_resposta")),
                "inspecoes": len(self.inspecoes()), "colunas": list(COLUNAS_PROVIDENCIA)}

    def historico_geral(self, filtro=None):
        f = dict(filtro or {})
        onde, a = ["1=1"], []
        if f.get("quem"):
            onde.append("quem=?")
            a.append(f["quem"])
        if f.get("objeto"):
            onde.append("objeto=?")
            a.append(f["objeto"])
        if f.get("desde"):
            onde.append("substr(quando,1,10)>=?")
            a.append(data_iso(f["desde"], "data"))
        if f.get("ate"):
            onde.append("substr(quando,1,10)<=?")
            a.append(data_iso(f["ate"], "data"))
        with self._trava:
            h = self._dicts("SELECT objeto, obj_id, campo, de, para, motivo, quem, quando FROM nus_historico WHERE %s ORDER BY id DESC LIMIT 1000" % " AND ".join(onde), *a)
            d = self._dicts("SELECT 'obrigacao' AS objeto, obrigacao AS obj_id, 'validação' AS campo, de, para, motivo, quem, quando FROM sei_decisoes "
                            "WHERE quem IS NOT NULL ORDER BY id DESC LIMIT 1000")
        if f.get("quem"):
            d = [x for x in d if x["quem"] == f["quem"]]
        if f.get("objeto") and f["objeto"] != "obrigacao":
            d = []
        if f.get("desde"):
            d = [x for x in d if x["quando"][:10] >= data_iso(f["desde"], "data")]
        if f.get("ate"):
            d = [x for x in d if x["quando"][:10] <= data_iso(f["ate"], "data")]
        return sorted(h + [x for x in d if x["campo"] == "validação" and x["para"] != x["de"]], key=lambda x: x["quando"], reverse=True)[:1000]

    def relatorio(self, desde="", ate=""):
        """Relatório de gestão do período: providências por estado e cumprimento, prazos vencidos, comunicações, inspeções."""
        de, ate = data_iso(desde, "data inicial") or "0000-00-00", data_iso(ate, "data final") or "9999-99-99"
        obr = [o for o in self.obrigacoes() if o["status"] in STATUS_FATO and de <= (o["criado"] or "")[:10] <= ate]
        cum = {}
        for o in obr:
            cum[o["cumprimento_nome"]] = cum.get(o["cumprimento_nome"], 0) + 1
        coms = [c for c in self.comunicacoes() if de <= (c["data_envio"] or c["criada"] or "")[:10] <= ate]
        ins = [i for i in self.inspecoes() if de <= i["data"] <= ate]
        achs = [a for i in ins for a in i["achados"]]
        return {"periodo": [desde, ate], "providencias": len(obr), "por_cumprimento": cum, "por_estado": {e: sum(1 for o in obr if o["estado"] == e)
                for e in COLUNAS_PROVIDENCIA if any(o["estado"] == e for o in obr)},
                "vencidos": [p for p in self.prazos() if p["status"] in STATUS_FATO and p["situacao"]["ordem"] == 0],
                "comunicacoes": len(coms), "enviadas": sum(1 for c in coms if c["data_envio"]), "respondidas": sum(1 for c in coms if c["respostas"]),
                "reiteracoes": sum(len(c["reiteracoes"]) for c in coms), "inspecoes": len(ins), "achados": len(achs),
                "achados_por_gravidade": {g: sum(1 for a in achs if a["gravidade"] == k) for k, g in GRAVIDADES},
                "achados_resolvidos": sum(1 for a in achs if a["situacao"] == "resolvido")}

    def buscar(self, termo):
        """Busca em processos, documentos, providências, demandas, comunicações e inspeções (sem acento, sem diferença de caixa)."""
        import unicodedata
        tira = lambda s: "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")
        t = tira(termo).strip()
        if len(t) < 3:
            raise Erro("Digite ao menos 3 letras.")
        out = []
        with self._trava:
            fontes = [("processo", "SELECT numero AS id, original || ' · ' || COALESCE(especificacao,'') AS txt FROM sei_processos"),
                      ("documento", "SELECT id, processo || ' · ' || COALESCE(titulo,'') || ' · ' || COALESCE(texto,'') AS txt FROM sei_documentos WHERE substituido_por IS NULL"),
                      ("obrigacao", "SELECT id, COALESCE(processo,'') || ' · ' || descricao || ' · ' || COALESCE(frase,'') || ' · ' || COALESCE(destinatario,'') AS txt "
                                    "FROM sei_obrigacoes WHERE removido_em IS NULL"),
                      ("demanda", "SELECT id, assunto || ' · ' || COALESCE(descricao,'') || ' · ' || COALESCE(destinatario,'') AS txt FROM nus_demandas WHERE removido_em IS NULL"),
                      ("comunicacao", "SELECT id, assunto || ' · ' || destinatario AS txt FROM nus_comunicacoes WHERE removido_em IS NULL"),
                      ("inspecao", "SELECT id, estabelecimento || ' · ' || COALESCE(municipio,'') || ' · ' || COALESCE(observacoes,'') AS txt FROM nus_inspecoes WHERE removido_em IS NULL"),
                      ("achado", "SELECT inspecao AS id, descricao || ' · ' || COALESCE(recomendacao,'') AS txt FROM nus_achados")]
            for tipo, sql in fontes:
                for oid, txt in self._q(sql).fetchall():
                    n = tira(txt)
                    i = n.find(t)
                    if i >= 0:
                        ini = max(0, i - 60)
                        out.append({"tipo": tipo, "id": oid, "trecho": ("…" if ini else "") + str(txt)[ini:i + len(t) + 80]})
                        if len(out) >= 200:
                            return out
        return out

    # ---------------------------------------------------------------- o que mudou, novidades, perguntas prontas
    def o_que_mudou(self):
        """Eventos das leituras ainda não vistos, por tipo e por processo, com a sugestão de cada um (NUSPEN, eventos.py)."""
        import rspe_sei
        with self._trava:
            ev = self._dicts("SELECT e.id, e.processo, e.tipo, e.descricao, e.quando, e.documento, e.sugestao, e.confirmado FROM sei_eventos e "
                             "WHERE COALESCE(e.visto,0)=0 ORDER BY e.id DESC LIMIT 500")
        for e in ev:
            e["rotulo"] = rspe_sei.EVENTOS.get(e["tipo"], e["tipo"])
            e["ligacao"] = rspe_sei.LIGACAO.get(e["sugestao"] or "", "")
        por = {}
        for e in ev:
            por.setdefault(e["rotulo"], 0)
            por[e["rotulo"]] += 1
        return {"total": len(ev), "eventos": ev, "por_tipo": por}

    def marcar_visto(self, quem):
        """O marco "visto até" avança só quando a pessoa marca (o resumo não some sozinho)."""
        quem = _quem(quem)
        with self._trava, self._con:
            self._q("UPDATE sei_eventos SET visto=1 WHERE COALESCE(visto,0)=0")
        marcos = dict(self.g.kv("nusVisto", {}))
        marcos[quem] = _agora()
        self.g.gravar_kv("nusVisto", marcos)
        return {"ok": True}

    def novidades(self, quem):
        """Desde a última vez que esta pessoa marcou "visto": só contagens reais."""
        desde = dict(self.g.kv("nusVisto", {})).get(_t(quem, 100), "")
        with self._trava:
            c = lambda sql: self._um(sql, desde)[0]
            out = {"desde": desde,
                   "documentos": c("SELECT COUNT(*) FROM sei_documentos WHERE recebido>? AND substituido_por IS NULL"),
                   "sugestoes": c("SELECT COUNT(*) FROM sei_obrigacoes WHERE criado>? AND status='sugestao' AND removido_em IS NULL"),
                   "respostas": c("SELECT COUNT(*) FROM nus_respostas WHERE quando>?"),
                   "decisoes": c("SELECT COUNT(*) FROM sei_decisoes WHERE quando>?"),
                   "inspecoes": c("SELECT COUNT(*) FROM nus_inspecoes WHERE criada>? AND removido_em IS NULL")}
        hoje = date.today().isoformat()
        out["prazos_vencidos"] = sum(1 for p in self.prazos() if p["status"] in STATUS_FATO and p["situacao"]["ordem"] == 0
                                     and (p["vencimento_efetivo"] or "") > (desde[:10] or "0000") and p["vencimento_efetivo"] < hoje)
        return out

    def evento_encerramento(self, eid, quem, motivo):
        """Arquivamento só SUGERE: confirmado, as providências abertas do processo vão à coordenação (não são cumpridas nem encerradas)."""
        quem = _quem(quem)
        if not _t(motivo):
            raise Erro("Diga por que confirma o possível arquivamento.")
        with self._trava, self._con:
            e = self._um("SELECT processo, sugestao, confirmado FROM sei_eventos WHERE id=?", int(eid))
            if not e or e[1] != "encerramento":
                raise Erro("Evento sem sugestão de encerramento.")
            n = 0
            for (oid,) in self._q("SELECT id FROM sei_obrigacoes WHERE processo=? AND removido_em IS NULL AND COALESCE(aguarda_decisao,0)=0 AND "
                                  "COALESCE(situacao_cumprimento,'nao_avaliada') NOT IN ('cumprida','prejudicada') AND status<>'rejeitada'", e[0]).fetchall():
                self._q("UPDATE sei_obrigacoes SET aguarda_decisao=1 WHERE id=?", oid)
                self._hist("obrigacao", oid, "possível arquivamento do processo", "", "encaminhada à coordenação", quem, motivo)
                n += 1
            self._q("UPDATE sei_eventos SET confirmado=1 WHERE id=?", int(eid))
        return {"ok": True, "encaminhadas": n}

    PERGUNTAS = [("oficios_aguardando", "Quais ofícios ainda aguardam resposta?"), ("pendentes_por_destinatario", "Quais providências pendentes há, por destinatário?"),
                 ("respostas_incompletas", "Quais respostas recebidas não atenderam integralmente?"), ("documentos_semana", "Quais documentos chegaram nesta semana?"),
                 ("demandas_categoria", "Quais demandas existem, por categoria?"), ("decisao_coordenador", "Quais assuntos aguardam decisão do coordenador?"),
                 ("achados_graves", "Quais achados graves de inspeção não foram resolvidos?")]

    def perguntas(self):
        return self.PERGUNTAS

    def consultar(self, pid):
        """Pergunta pronta, consulta fixa (sem IA): cada linha aponta a origem; sem dados, "sem evidência suficiente"."""
        tit = dict(self.PERGUNTAS).get(pid)
        if not tit:
            raise Erro("Pergunta desconhecida.")
        L = []
        if pid == "oficios_aguardando":
            L = [{"texto": "%s · para %s · enviado em %s%s" % (c["assunto"], c["destinatario"], br(c["data_envio"]), " · %d reiteração(ões)" % len(c["reiteracoes"])
                                                                if c["reiteracoes"] else ""), "ir": ["com", c["id"]]} for c in self.comunicacoes() if c["estado"] == "aguardando_resposta"]
        elif pid == "pendentes_por_destinatario":
            for o in sorted((o for o in self.obrigacoes() if o["status"] in STATUS_FATO and o["situacao_cumprimento"] not in ("cumprida", "prejudicada")),
                            key=lambda o: (o["destinatario"] or "~", o["id"])):
                L.append({"texto": "%s · %s · %s" % (o["destinatario"] or "(sem destinatário)", o["descricao"][:120], o["estado"]), "ir": ["prov", o["id"]]})
        elif pid == "respostas_incompletas":
            for c in self.comunicacoes():
                for r in c["respostas"]:
                    for a in r["avaliacoes"]:
                        if a["status"] in STATUS_FATO and a["resultado"] != "atende":
                            L.append({"texto": "%s · resposta de %s · %s" % (c["assunto"], br(r["data_recebimento"]), rotulo(AVAL_RESPOSTA, a["resultado"])), "ir": ["com", c["id"]]})
        elif pid == "documentos_semana":
            desde = (date.today() - timedelta(days=7)).isoformat()
            with self._trava:
                L = [{"texto": "%s · %s · %s" % (br(r[2]), r[0], r[1]), "ir": ["proc", r[3]]} for r in self._q(
                    "SELECT processo, titulo, recebido, processo FROM sei_documentos WHERE recebido>=? AND substituido_por IS NULL ORDER BY recebido DESC", desde).fetchall()]
        elif pid == "demandas_categoria":
            L = [{"texto": "%s · %s · %s" % (d["tipo_nome"], d["assunto"], d["situacao_nome"]), "ir": ["dem", d["id"]]} for d in sorted(self.demandas(), key=lambda d: d["tipo_nome"])]
        elif pid == "decisao_coordenador":
            L = [{"texto": "%s · %s" % (o["descricao"][:140], o["processo"] or ""), "ir": ["prov", o["id"]]} for o in self.obrigacoes() if o.get("aguarda_decisao")]
        elif pid == "achados_graves":
            L = [{"texto": "%s (%s) · %s · %s" % (i["estabelecimento"], br(i["data"]), a["descricao"][:120], a["situacao_nome"]), "ir": ["insp", i["id"]]}
                 for i in self.inspecoes() for a in i["achados"] if a["gravidade"] == "alta" and a["situacao"] != "resolvido"]
        return {"id": pid, "titulo": tit, "linhas": L, "nota": "" if L else "Sem evidência suficiente nos dados registrados."}

    def em_lote(self, acao, ids, quem, motivo=""):
        """Ação em lote (com prévia na tela): cada item passa pela mesma regra da ação individual, com histórico por item."""
        quem = _quem(quem)
        feitos, erros = 0, []
        for i in [int(x) for x in ids or []][:500]:
            try:
                if acao == "validar":
                    self.obrigacao_decidir(i, "validada", quem)
                elif acao == "rejeitar":
                    self.obrigacao_decidir(i, "rejeitada", quem, motivo)
                elif acao in ("prioridade_alta", "prioridade_normal"):
                    self.obrigacao_editar(i, "prioridade", acao.split("_")[1], quem, motivo)
                elif acao == "coordenacao":
                    self.obrigacao_editar(i, "aguarda_decisao", 1, quem, motivo)
                else:
                    raise Erro("Ação desconhecida.")
                feitos += 1
            except Erro as e:
                erros.append("%s: %s" % (i, e))
        return {"ok": True, "feitos": feitos, "erros": erros}

    # ---------------------------------------------------------------- escolhas para a tela
    @staticmethod
    def escolhas():
        return {k: v for k, v in (("tipos_obrigacao", TIPOS_OBRIGACAO), ("origens_obrigacao", ORIGENS_OBRIGACAO), ("cumprimento", CUMPRIMENTO),
                                  ("prioridades", PRIORIDADES), ("situacoes_demanda", SITUACOES_DEMANDA), ("tipos_demanda", TIPOS_DEMANDA),
                                  ("naturezas", NATUREZAS), ("origens_prazo", ORIGENS_PRAZO), ("finalidades", FINALIDADES),
                                  ("alteracoes_prazo", ALTERACOES_PRAZO), ("tipos_lacuna", TIPOS_LACUNA), ("aval_resposta", AVAL_RESPOSTA),
                                  ("aval_cumprimento", AVAL_CUMPRIMENTO), ("categorias", CATEGORIAS), ("gravidades", GRAVIDADES),
                                  ("situacoes_achado", SITUACOES_ACHADO), ("blocos", BLOCOS))}


# métodos que a tela pode chamar (rspe_gabinete_api.nus): leitura e registro; nada que apague
PUBLICOS = {"quem_lista", "quem_gravar", "remover", "demanda_criar", "demanda_editar", "demanda_vincular_processo", "demanda_desvincular_processo",
            "demanda_vincular_providencia", "demandas", "demanda", "obrigacoes", "obrigacao", "obrigacao_criar", "obrigacao_editar", "obrigacao_decidir",
            "regras", "regra_criar", "regra_aprovar", "prazo_registrar", "prazo_decidir", "prazo_completar", "prazo_alterar", "prazos", "lacunas",
            "lacuna_fechar", "lacuna_abrir", "comunicacoes", "comunicacao_criar", "comunicacao_envio", "comunicacao_vincular", "reiterar",
            "resposta_registrar", "resposta_juntar", "avaliar", "avaliacao_decidir", "inspecoes", "inspecao", "inspecao_criar", "inspecao_documento",
            "achado_registrar", "achado_situacao", "recorrencia_confirmar", "achado_providencia", "comparar", "modelos", "modelo_cadastrar",
            "minuta_gerar", "minuta", "minuta_editar", "minuta_restaurar", "minuta_validar", "painel", "historico_geral", "relatorio", "buscar",
            "escolhas", "historico_de", "o_que_mudou", "marcar_visto", "novidades", "evento_encerramento", "perguntas", "consultar", "em_lote", "arquivos_pdf"}
