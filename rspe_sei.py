"""SEI no APTO: o que a extensão leu no SEI (só leitura, na sessão da própria pessoa) entra na base do gabinete. Traz do NUSPEN
(rafhaels1/nuspen-sei) a sincronização incremental (sessões, cursor de retomada, "conhecidos" por id + versão + hash) e as regras
de leitura (nuspen_regras: tipo do documento, obrigações, prazo expresso, sinalizações), sem mudar regra.

Princípios do NUSPEN mantidos: o APTO nunca fala com o SEI; o conteúdo do SEI é dado, não instrução; o original fica (hash
SHA-256 conferido); nada se apaga (versão anterior fica como "substituída"); obrigação e prazo extraídos são SUGESTÃO até a
pessoa validar; o prazo expresso não ganha vencimento calculado (a contagem não é presumida)."""
import hashlib
import json
import re
import secrets
import threading
from datetime import datetime

from nuspen_regras.classificacao import _sem_rodape, classificar_texto
from nuspen_regras.obrigacoes import VERSAO as VERSAO_OBRIGACOES
from nuspen_regras.obrigacoes import extrair_indicios_resposta, extrair_obrigacoes, extrair_prazo_do_texto, extrair_sinalizacoes
from nuspen_regras.rodape import encontrar_numeros_processo, normalizar_numero_processo

# ---- antes das regras do NUSPEN: as frases do documento como estão nas linhas ----
# As regras juntam o texto todo e cortam as frases só no ".", "!" ou "?". No ofício do SEI, o cabeçalho (número, data, "Ao Ilmo.
# Senhor", nome, cargo, assunto, vocativo) vem em linhas sem ponto: ficava emendado na frase da obrigação, e o "." de "Ilmo." cortava
# a linha do destinatário ("Ilmo"). Aqui cada linha sem pontuação final vira frase própria, as abreviaturas de tratamento perdem o
# ponto e o bloco do destinatário vira uma linha só: "Ao FULANO, Diretor do ...". O texto guardado do documento não muda.
_TRATAMENTO = r"(?:Ilustr[ií]ssim[oa]s?|Excelent[ií]ssim[oa]s?|Ilm[oa]s?\.?|Exm[oa]s?\.?|Senhor(?:a|es|as)?|Sr[as]?\.?|Dr[as]?\.?|Prof[as]?\.?|Doutor(?:a)?|Magn[ií]fic[oa])"
_ABREV = re.compile(r"\b(Ilm[oa]s?|Exm[oa]s?|Sr[as]?|Dr[as]?|Prof[as]?|MM|Exa|Sra?s?)\.(?=\s)")
_SO_TRATAMENTO = re.compile(r"^(À|Ao|Aos|Às|A)\s+(?:%s\s*)+$" % _TRATAMENTO, re.I)
_FIM_FRASE = re.compile(r"[.!?:;,]$")
_VOCATIVO = re.compile(r"^(?:Senhor(?:a|es|as)?|Prezad[oa]s?|Excelent[ií]ssim[oa]s?|Ilustr[ií]ssim[oa]s?|Atenciosamente|Respeitosamente|Cordialmente)\b.{0,60},$", re.I)
_NAO_DESTINATARIO = re.compile(r"^(?:Assunto|Ref|Refer[êe]ncia|Processo|SEI|Senhor|Senhora|Prezad)", re.I)


def _frases_por_linha(texto):
    linhas = [" ".join(x.split()) for x in str(texto or "").splitlines()]
    linhas = [_ABREV.sub(r"\1", x) for x in linhas if x]
    out, i = [], 0
    while i < len(linhas):
        x = linhas[i]
        m = _SO_TRATAMENTO.match(x)
        if m:  # "Ao Ilmo. Senhor" + nome + cargo (até 2 linhas, sem passar do assunto/vocativo)
            partes = []
            while i + 1 < len(linhas) and len(partes) < 2 and not _NAO_DESTINATARIO.match(linhas[i + 1]):
                partes.append(linhas[i + 1].rstrip(".,;"))
                i += 1
            x = "%s %s" % (m.group(1), ", ".join(partes)) if partes else x
        seguinte = linhas[i + 1] if i + 1 < len(linhas) else ""
        if seguinte and (seguinte[0].isupper() or seguinte[0].isdigit() or seguinte[0] == "("):
            if _VOCATIVO.match(x):
                x = x[:-1] + "."
            elif not _FIM_FRASE.search(x):
                x += "."
        out.append(x)
        i += 1
    return "\n".join(out)

LIMITE_CONTEUDO = 2_000_000   # caracteres por documento
LIMITE_IDS = 2000
ROTULO = {"determino": "Determinado", "reitere-se": "Reiterado", "reitero": "Reiterado", "encaminha-se": "Encaminhado",
          "encaminhe-se": "Encaminhar", "providencie-se": "Providenciar", "oficie-se": "Oficiar", "solicita-se": "Solicitado",
          "solicito": "Solicitado", "recomendo": "Recomendado", "recomenda-se": "Recomendado", "recomendacao": "Recomendação"}
STATUS_OBRIGACAO = ("sugestao", "validada", "rejeitada", "substituida")

TABELAS = """
CREATE TABLE IF NOT EXISTS sei_sessoes (id INTEGER PRIMARY KEY AUTOINCREMENT, modo TEXT, status TEXT, cursor TEXT, retomada_de INTEGER,
  iniciada TEXT, concluida TEXT, recebidos INTEGER DEFAULT 0, novos INTEGER DEFAULT 0, modificados INTEGER DEFAULT 0, falhas INTEGER DEFAULT 0,
  requisicoes INTEGER, duracao_s REAL);
CREATE TABLE IF NOT EXISTS sei_itens (tipo TEXT, id_sei TEXT, estado TEXT, versao TEXT, hash TEXT, processo TEXT, titulo TEXT, unidade TEXT,
  ultima_movimentacao TEXT, adaptador TEXT, mensagem TEXT, ultima_leitura TEXT, sessao INTEGER, PRIMARY KEY (tipo, id_sei));
CREATE TABLE IF NOT EXISTS sei_processos (numero TEXT PRIMARY KEY, original TEXT, id_sei TEXT, especificacao TEXT, unidade TEXT,
  ultima_movimentacao TEXT, atualizado TEXT, fora_da_lista INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sei_documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_sei TEXT, versao TEXT, processo TEXT, titulo TEXT,
  hash TEXT, texto TEXT, tipo_codigo TEXT, tipo_nome TEXT, tipo_confianca TEXT, tipo_sinais TEXT, prazo_expresso TEXT, processos_citados TEXT,
  sinalizacoes TEXT, recebido TEXT, substituido_por INTEGER, adaptador TEXT);
CREATE INDEX IF NOT EXISTS sei_documentos_proc ON sei_documentos(processo);
CREATE INDEX IF NOT EXISTS sei_documentos_idsei ON sei_documentos(id_sei);
CREATE TABLE IF NOT EXISTS sei_obrigacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, documento INTEGER, processo TEXT, tipo TEXT, origem TEXT,
  descricao TEXT, destinatario TEXT, frase TEXT, regra TEXT, prazo_quantidade INTEGER, prazo_unidade TEXT, prazo_frase TEXT,
  prazo_natureza TEXT, finalidade TEXT, status TEXT, motivo TEXT, decidido_em TEXT, criado TEXT, quadro TEXT);
CREATE INDEX IF NOT EXISTS sei_obrigacoes_proc ON sei_obrigacoes(processo);
CREATE TABLE IF NOT EXISTS sei_decisoes (id INTEGER PRIMARY KEY AUTOINCREMENT, obrigacao INTEGER, de TEXT, para TEXT, motivo TEXT, quando TEXT);
CREATE INDEX IF NOT EXISTS sei_decisoes_obr ON sei_decisoes(obrigacao);
CREATE TABLE IF NOT EXISTS sei_eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, sessao INTEGER, processo TEXT, tipo TEXT, descricao TEXT, quando TEXT);
"""


def sha(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _t(v, n=200):
    return str(v if v is not None else "")[:n]


class Sei:
    """A parte SEI da base do gabinete. Usa a conexão e a trava do Gabinete (rspe_gabinete)."""

    def __init__(self, gabinete):
        self.g = gabinete
        self._con = gabinete._con
        self._trava = gabinete._trava
        self.token = "apto_" + secrets.token_urlsafe(24)   # vale enquanto o APTO está aberto
        self._lote = threading.Lock()
        with self._trava, self._con:
            self._con.executescript(TABELAS)
            # 7.26: indícios de resposta (regra do NUSPEN): certidão/termo que cita resposta a ofício; manifestação que afirma atendimento
            if "indicios" not in [r[1] for r in self._con.execute("PRAGMA table_info(sei_documentos)")]:
                self._con.execute("ALTER TABLE sei_documentos ADD COLUMN indicios TEXT")

    # ---- autenticação da extensão (o token é entregue só a extensões, por GET /sei/token) ----
    def token_ok(self, cabecalho):
        c = str(cabecalho or "")
        return c.startswith("Bearer ") and secrets.compare_digest(c[7:].strip(), self.token)

    def revogar(self):
        self.token = "apto_" + secrets.token_urlsafe(24)

    # ---- o que já se conhece (para a leitura incremental) ----
    def contagens(self):
        with self._trava:
            r = dict(self._con.execute("SELECT tipo, COUNT(*) FROM sei_itens WHERE estado NOT IN ('falha','indisponivel') GROUP BY tipo").fetchall())
        return {"processos": r.get("processo", 0), "documentos": r.get("documento", 0)}

    def conhecidos(self, ids):
        out = {}
        with self._trava:
            for chave in ids[:LIMITE_IDS]:
                tipo, _, id_sei = str(chave).partition(":")
                r = self._con.execute("SELECT versao, hash, ultima_movimentacao FROM sei_itens WHERE tipo=? AND id_sei=? AND estado NOT IN ('falha','indisponivel')",
                                      (tipo, id_sei)).fetchone()
                if r and not self._acento_quebrado(tipo, id_sei):
                    out["%s:%s" % (tipo, id_sei)] = {"versao": r[0] or "", "hash": r[1] or "", "ultima_movimentacao": r[2] or ""}
        return out

    def _acento_quebrado(self, tipo, id_sei):
        """Lido antes da 7.26 (a página ISO-8859-1 decodificada como UTF-8: "Of\ufffdcio"): conta como desconhecido, para a
        próxima leitura, mesmo a de "só novos", trazer de novo com os acentos certos (o documento antigo fica como substituído)."""
        q = "%\ufffd%"
        if tipo == "documento":
            return bool(self._con.execute("SELECT 1 FROM sei_documentos WHERE id_sei=? AND substituido_por IS NULL AND (texto LIKE ? OR titulo LIKE ?) LIMIT 1",
                                          (id_sei, q, q)).fetchone())
        return bool(self._con.execute("SELECT 1 FROM sei_itens WHERE tipo=? AND id_sei=? AND titulo LIKE ?", (tipo, id_sei, q)).fetchone()
                    or self._con.execute("SELECT 1 FROM sei_processos WHERE id_sei=? AND especificacao LIKE ?", (id_sei, q)).fetchone())

    # ---- sessões ----
    def iniciar(self, modo="todos", retomar=None):
        with self._trava, self._con:
            cursor, anterior = {}, None
            if retomar:
                r = self._con.execute("SELECT id, status, cursor FROM sei_sessoes WHERE id=?", (int(retomar),)).fetchone()
                if r:
                    anterior = r[0]
                    cursor = json.loads(r[2] or "{}")
                    if r[1] == "em_andamento":
                        self._con.execute("UPDATE sei_sessoes SET status='interrompida' WHERE id=?", (r[0],))
            c = self._con.execute("INSERT INTO sei_sessoes(modo, status, cursor, retomada_de, iniciada) VALUES(?,?,?,?,?)",
                                  (_t(modo, 30), "em_andamento", json.dumps(cursor), anterior, _agora()))
            return {"sessao": c.lastrowid, "cursor": cursor, "conhecidos": {}}

    def sessao_interrompida(self):
        """A última leitura que não terminou (para o botão do APTO continuar de onde parou)."""
        with self._trava:
            r = self._con.execute("SELECT id, status FROM sei_sessoes ORDER BY id DESC LIMIT 1").fetchone()
        return r[0] if r and r[1] in ("em_andamento", "interrompida") else None

    def _sessao(self, sid):
        r = self._con.execute("SELECT id FROM sei_sessoes WHERE id=?", (int(sid),)).fetchone()
        if not r:
            raise KeyError("sessão desconhecida")
        return r[0]

    def concluir(self, sid, dados):
        with self._trava, self._con:
            s = self._sessao(sid)
            self._con.execute("UPDATE sei_sessoes SET status='concluida', concluida=?, requisicoes=?, duracao_s=? WHERE id=?",
                              (_agora(), int(dados.get("requisicoes") or 0), float(dados.get("duracao_s") or 0), s))
            # lista completa: processo que não aparece mais na lista fica marcado (nada é apagado)
            if dados.get("lista_completa") and isinstance(dados.get("listados"), list):
                vistos = {str(x) for x in dados["listados"]}
                for (num, ids) in self._con.execute("SELECT numero, id_sei FROM sei_processos").fetchall():
                    fora = 0 if ids in vistos else 1
                    self._con.execute("UPDATE sei_processos SET fora_da_lista=? WHERE numero=?", (fora, num))
        return {"status": "concluida"}

    # ---- itens lidos ----
    def _marcar(self, sid, tipo, id_sei, estado, mensagem="", **extra):
        campos = {k: _t(extra.get(k)) for k in ("versao", "hash", "processo", "titulo", "unidade", "ultima_movimentacao", "adaptador") if k in extra}
        atual = self._con.execute("SELECT 1 FROM sei_itens WHERE tipo=? AND id_sei=?", (tipo, id_sei)).fetchone()
        if not atual:
            self._con.execute("INSERT INTO sei_itens(tipo, id_sei) VALUES(?,?)", (tipo, id_sei))
        sets = ", ".join("%s=?" % k for k in campos)
        self._con.execute("UPDATE sei_itens SET estado=?, mensagem=?, ultima_leitura=?, sessao=?%s WHERE tipo=? AND id_sei=?" % (", " + sets if sets else ""),
                          (estado, _t(mensagem, 300), _agora(), sid, *campos.values(), tipo, id_sei))

    def receber_lote(self, sid, itens, cursor=None):
        res = {"novos": 0, "modificados": 0, "recebidos": 0, "falhas": 0}
        with self._lote, self._trava, self._con:
            s = self._sessao(sid)
            for d in itens if isinstance(itens, list) else []:
                if not isinstance(d, dict):
                    continue
                res["recebidos"] += 1
                tipo = d.get("tipo")
                if tipo == "processo":
                    self._processo(s, d)
                elif tipo == "documento":
                    r = self._documento(s, d)
                    if r in ("novo", "modificado"):
                        res["novos" if r == "novo" else "modificados"] += 1
                    elif r == "falha":
                        res["falhas"] += 1
                elif tipo in ("falha", "indisponivel"):
                    self._marcar(s, "documento" if tipo == "falha" else "processo", _t(d.get("id_sei"), 80) or "?", tipo,
                                 _t(d.get("motivo"), 300), processo=d.get("processo", ""))
                    res["falhas"] += tipo == "falha"
            if isinstance(cursor, dict):
                self._con.execute("UPDATE sei_sessoes SET cursor=? WHERE id=?", (json.dumps({k: int(v) for k, v in cursor.items() if k in ("pagina", "indice")}), s))
            self._con.execute("UPDATE sei_sessoes SET recebidos=recebidos+?, novos=novos+?, modificados=modificados+?, falhas=falhas+? WHERE id=?",
                              (res["recebidos"], res["novos"], res["modificados"], res["falhas"], s))
        return {"novos": res["novos"], "modificados": res["modificados"]}

    def _processo(self, s, d):
        original = _t(d.get("numero"), 60)
        num = normalizar_numero_processo(original) or original
        id_sei = _t(d.get("id_sei"), 80)
        unidade = _t(d.get("unidade"))
        ant = self._con.execute("SELECT unidade FROM sei_processos WHERE numero=?", (num,)).fetchone()
        if ant and ant[0] and unidade and ant[0] != unidade:
            self._evento(s, num, "mudanca_unidade", "%s → %s" % (ant[0], unidade))
        self._con.execute("INSERT INTO sei_processos(numero, original, id_sei, especificacao, unidade, ultima_movimentacao, atualizado, fora_da_lista) "
                          "VALUES(?,?,?,?,?,?,?,0) ON CONFLICT(numero) DO UPDATE SET id_sei=excluded.id_sei, especificacao=CASE WHEN excluded.especificacao<>'' "
                          "THEN excluded.especificacao ELSE especificacao END, unidade=CASE WHEN excluded.unidade<>'' THEN excluded.unidade ELSE unidade END, "
                          "ultima_movimentacao=excluded.ultima_movimentacao, atualizado=excluded.atualizado, fora_da_lista=0",
                          (num, original, id_sei, _t(d.get("especificacao"), 500), unidade, _t(d.get("ultima_movimentacao")), _agora()))
        self._marcar(s, "processo", id_sei, "analisado", processo=original, unidade=unidade, ultima_movimentacao=d.get("ultima_movimentacao"),
                     adaptador=d.get("adaptador"))
        vistos = d.get("documentos_vistos")
        if isinstance(vistos, list):
            vistos = {str(v) for v in vistos}
            for (ids,) in self._con.execute("SELECT id_sei FROM sei_itens WHERE tipo='documento' AND processo=? AND estado='analisado'", (original,)).fetchall():
                if ids not in vistos:
                    self._marcar(s, "documento", ids, "indisponivel", "não aparece mais na árvore do processo")
                    self._evento(s, num, "documento_inacessivel", "documento %s" % ids)

    def _evento(self, s, processo, tipo, descricao):
        self._con.execute("INSERT INTO sei_eventos(sessao, processo, tipo, descricao, quando) VALUES(?,?,?,?,?)", (s, processo, tipo, _t(descricao, 300), _agora()))

    def _documento(self, s, d):
        """'novo', 'modificado', 'igual' ou 'falha' (mesma regra do NUSPEN)."""
        id_sei = _t(d.get("id_sei"), 80)
        texto = str(d.get("conteudo", ""))
        original = _t(d.get("processo"), 60)
        if not id_sei or len(texto) > LIMITE_CONTEUDO:
            self._marcar(s, "documento", id_sei or "?", "falha", "conteúdo ausente ou grande demais", processo=original)
            return "falha"
        h = sha(texto)
        if d.get("hash") != h:
            self._marcar(s, "documento", id_sei, "falha", "hash divergente do informado pela extensão", processo=original)
            return "falha"
        it = self._con.execute("SELECT hash, estado FROM sei_itens WHERE tipo='documento' AND id_sei=?", (id_sei,)).fetchone()
        if it and it[0] == h and it[1] == "analisado":
            self._marcar(s, "documento", id_sei, "analisado", versao=d.get("versao"))
            return "igual"
        resultado = "modificado" if it and it[0] else "novo"
        titulo = _t(d.get("titulo"))
        num = normalizar_numero_processo(original) or original
        cl = classificar_texto(_sem_rodape(texto), titulo)
        prazo = extrair_prazo_do_texto(texto)
        citados = sorted({n.normalizado for n in encontrar_numeros_processo(texto)})
        frases = _frases_por_linha(_sem_rodape(texto))
        sin = [{"frase": x.frase[:500], "tipo": x.tipo, "descricao": x.descricao} for x in extrair_sinalizacoes(frases, cl.codigo or "")]
        ind = [{"frase": x.frase[:500], "oficio": x.oficio, "descricao": x.descricao} for x in extrair_indicios_resposta(frases, cl.codigo or "")]
        c = self._con.execute(
            "INSERT INTO sei_documentos(id_sei, versao, processo, titulo, hash, texto, tipo_codigo, tipo_nome, tipo_confianca, tipo_sinais, prazo_expresso, "
            "processos_citados, sinalizacoes, recebido, adaptador, indicios) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (id_sei, _t(d.get("versao"), 80), num, titulo, h, texto, cl.codigo or "", cl.nome or "", cl.confianca, json.dumps(cl.sinais, ensure_ascii=False),
             json.dumps({"quantidade": prazo.quantidade, "unidade": prazo.unidade, "trecho": prazo.trecho[:300]}, ensure_ascii=False) if prazo else "",
             json.dumps(citados), json.dumps(sin, ensure_ascii=False), _agora(), _t(d.get("adaptador")), json.dumps(ind, ensure_ascii=False)))
        novo = c.lastrowid
        if resultado == "modificado":
            self._substituir(id_sei, novo)
        self._obrigacoes(novo, num, texto, cl.codigo or "")
        self._marcar(s, "documento", id_sei, "analisado", versao=d.get("versao"), hash=h, processo=original, titulo=titulo, adaptador=d.get("adaptador"))
        if resultado == "modificado":
            self._evento(s, num, "documento_alterado", "%s (%s)" % (titulo, id_sei))
        return resultado

    def _substituir(self, id_sei, novo):
        """Versão anterior: fica guardada como substituída. Obrigação só sugerida sai junto; a validada fica, para conferir."""
        for (ant,) in self._con.execute("SELECT id FROM sei_documentos WHERE id_sei=? AND id<>? AND substituido_por IS NULL", (id_sei, novo)).fetchall():
            self._con.execute("UPDATE sei_documentos SET substituido_por=? WHERE id=?", (novo, ant))
            self._con.execute("UPDATE sei_obrigacoes SET status='substituida', motivo='documento substituído por nova versão', decidido_em=? "
                              "WHERE documento=? AND status='sugestao'", (_agora(), ant))
            self._con.execute("UPDATE sei_obrigacoes SET motivo='documento substituído por nova versão: conferir' WHERE documento=? AND status='validada'", (ant,))

    def _obrigacoes(self, doc, processo, texto, tipo_codigo):
        for c in extrair_obrigacoes(_frases_por_linha(_sem_rodape(texto)), tipo_codigo):
            pre = ROTULO.get(c.regra)
            descricao = "%s: %s" % (pre, c.objeto) if pre else c.objeto[:1].upper() + c.objeto[1:]
            natureza = "expresso" if c.prazo_quantidade is not None else ("nao_identificado" if c.prazo_sem_numero else "")
            self._con.execute(
                "INSERT INTO sei_obrigacoes(documento, processo, tipo, origem, descricao, destinatario, frase, regra, prazo_quantidade, prazo_unidade, "
                "prazo_frase, prazo_natureza, finalidade, status, criado) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc, processo, c.tipo, c.origem, descricao[:600], c.destinatario[:300], c.frase[:1000], "%s:%s" % (VERSAO_OBRIGACOES, c.regra),
                 c.prazo_quantidade, c.prazo_unidade, c.prazo_frase[:500], natureza, c.finalidade, "sugestao", _agora()))

    # ---- telas ----
    def resumo(self):
        with self._trava:
            q = lambda sql, *a: self._con.execute(sql, a).fetchone()[0]
            procs = [dict(zip(("numero", "original", "especificacao", "unidade", "ultima_movimentacao", "atualizado", "fora_da_lista"), r))
                     for r in self._con.execute("SELECT numero, original, especificacao, unidade, ultima_movimentacao, atualizado, fora_da_lista FROM sei_processos ORDER BY atualizado DESC")]
            por_proc = {}
            for num, st, n in self._con.execute("SELECT processo, status, COUNT(*) FROM sei_obrigacoes GROUP BY processo, status"):
                por_proc.setdefault(num, {})[st] = n
            docs = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_documentos WHERE substituido_por IS NULL GROUP BY processo").fetchall())
            falhas = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_itens WHERE estado='falha' GROUP BY processo").fetchall())
            ult = self._con.execute("SELECT id, modo, status, iniciada, concluida, novos, modificados, falhas FROM sei_sessoes ORDER BY id DESC LIMIT 1").fetchone()
            for p in procs:
                p["obrigacoes"] = por_proc.get(p["numero"], {})
                p["documentos"] = docs.get(p["numero"], 0)
                p["falhas"] = falhas.get(p["original"], 0)
            return {
                "processos": procs,
                "totais": {"processos": len(procs), "documentos": q("SELECT COUNT(*) FROM sei_documentos WHERE substituido_por IS NULL"),
                           "sugestoes": q("SELECT COUNT(*) FROM sei_obrigacoes WHERE status='sugestao'"),
                           "validadas": q("SELECT COUNT(*) FROM sei_obrigacoes WHERE status='validada'"),
                           "prazos": q("SELECT COUNT(*) FROM sei_obrigacoes WHERE status IN ('sugestao','validada') AND prazo_natureza='expresso'"),
                           "falhas": q("SELECT COUNT(*) FROM sei_itens WHERE estado='falha'")},
                "ultima": dict(zip(("id", "modo", "status", "iniciada", "concluida", "novos", "modificados", "falhas"), ult)) if ult else None,
            }

    def processo(self, numero):
        with self._trava:
            p = self._con.execute("SELECT numero, original, id_sei, especificacao, unidade, ultima_movimentacao, atualizado, fora_da_lista FROM sei_processos WHERE numero=?",
                                  (numero,)).fetchone()
            if not p:
                return None
            p = dict(zip(("numero", "original", "id_sei", "especificacao", "unidade", "ultima_movimentacao", "atualizado", "fora_da_lista"), p))
            cols = ("id", "id_sei", "versao", "titulo", "tipo_codigo", "tipo_nome", "tipo_confianca", "tipo_sinais", "prazo_expresso", "processos_citados",
                    "sinalizacoes", "recebido", "substituido_por", "texto", "indicios")
            docs = []
            for r in self._con.execute("SELECT %s FROM sei_documentos WHERE processo=? ORDER BY id" % ", ".join(cols), (numero,)):
                x = dict(zip(cols, r))
                for k in ("tipo_sinais", "processos_citados", "sinalizacoes", "indicios"):
                    x[k] = json.loads(x[k] or "[]")
                x["prazo_expresso"] = json.loads(x["prazo_expresso"]) if x["prazo_expresso"] else None
                x["texto"] = (x["texto"] or "")[:20000]
                docs.append(x)
            ocols = ("id", "documento", "tipo", "origem", "descricao", "destinatario", "frase", "regra", "prazo_quantidade", "prazo_unidade", "prazo_frase",
                     "prazo_natureza", "finalidade", "status", "motivo", "decidido_em", "quadro")
            obr = [dict(zip(ocols, r)) for r in self._con.execute("SELECT %s FROM sei_obrigacoes WHERE processo=? ORDER BY id" % ", ".join(ocols), (numero,))]
            hist = {}
            for o, de, para, mot, q in self._con.execute("SELECT obrigacao, de, para, motivo, quando FROM sei_decisoes WHERE obrigacao IN (SELECT id FROM sei_obrigacoes "
                                                         "WHERE processo=?) ORDER BY id", (numero,)):
                hist.setdefault(o, []).append({"de": de, "para": para, "motivo": mot, "quando": q})
            for o in obr:
                o["historico"] = hist.get(o["id"], [])
            ev = [dict(zip(("tipo", "descricao", "quando"), r)) for r in self._con.execute("SELECT tipo, descricao, quando FROM sei_eventos WHERE processo=? ORDER BY id DESC LIMIT 30", (numero,))]
            falhas = [dict(zip(("id_sei", "mensagem", "estado"), r)) for r in self._con.execute(
                "SELECT id_sei, mensagem, estado FROM sei_itens WHERE processo=? AND estado IN ('falha','indisponivel')", (p["original"],))]
            p.update(documentos=docs, obrigacoes=obr, eventos=ev, falhas=falhas)
            return p

    def decidir(self, oid, status, motivo=""):
        """A pessoa valida ou rejeita a sugestão (ou volta a sugestão); motivo obrigatório para rejeitar."""
        if status not in ("validada", "rejeitada", "sugestao"):
            return {"erro": "situação inválida"}
        if status == "rejeitada" and not str(motivo or "").strip():
            return {"erro": "diga o motivo para rejeitar"}
        with self._trava, self._con:
            r = self._con.execute("SELECT status FROM sei_obrigacoes WHERE id=?", (int(oid),)).fetchone()
            if not r:
                return {"erro": "obrigação desconhecida"}
            if r[0] == "substituida":
                return {"erro": "a sugestão é de uma versão substituída do documento"}
            agora = _agora()
            self._con.execute("UPDATE sei_obrigacoes SET status=?, motivo=?, decidido_em=? WHERE id=?", (status, _t(motivo, 500), agora, int(oid)))
            # cada decisão fica no histórico (voltar a sugestão não apaga o motivo da rejeição anterior)
            self._con.execute("INSERT INTO sei_decisoes(obrigacao, de, para, motivo, quando) VALUES(?,?,?,?,?)", (int(oid), r[0], status, _t(motivo, 500), agora))
        return {"ok": True}

    def marcar_quadro(self, oid, peca_id):
        with self._trava, self._con:
            self._con.execute("UPDATE sei_obrigacoes SET quadro=? WHERE id=?", (_t(peca_id, 40), int(oid)))

    def obrigacao(self, oid):
        with self._trava:
            r = self._con.execute("SELECT id, processo, descricao, prazo_quantidade, prazo_unidade, status, quadro FROM sei_obrigacoes WHERE id=?", (int(oid),)).fetchone()
        return dict(zip(("id", "processo", "descricao", "prazo_quantidade", "prazo_unidade", "status", "quadro"), r)) if r else None


def numero_valido(s):
    return bool(re.match(r"^[\w.\-/]{1,60}$", str(s or "")))
