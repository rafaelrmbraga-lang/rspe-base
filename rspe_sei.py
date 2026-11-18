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
CREATE TABLE IF NOT EXISTS sei_arquivos (sha256 TEXT PRIMARY KEY, nome TEXT, caminho TEXT, paginas INTEGER, sem_texto TEXT, documentos INTEGER,
  importado TEXT, quem TEXT);
CREATE TABLE IF NOT EXISTS sei_recebimentos (id INTEGER PRIMARY KEY AUTOINCREMENT, sha256 TEXT, nome TEXT, quando TEXT, quem TEXT);
CREATE TABLE IF NOT EXISTS sei_decisoes (id INTEGER PRIMARY KEY AUTOINCREMENT, obrigacao INTEGER, de TEXT, para TEXT, motivo TEXT, quando TEXT);
CREATE INDEX IF NOT EXISTS sei_decisoes_obr ON sei_decisoes(obrigacao);
CREATE TABLE IF NOT EXISTS sei_eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, sessao INTEGER, processo TEXT, tipo TEXT, descricao TEXT, quando TEXT);
"""


EVENTOS = {"despacho_decisao": "Despacho ou decisão", "oficio_expedido": "Ofício expedido", "resposta_recebida": "Resposta recebida",
           "documento_outro_orgao": "Documento de outro órgão", "arquivamento_conclusao": "Arquivamento ou conclusão", "reabertura": "Reabertura",
           "mudanca_unidade": "Mudança de unidade", "documento_alterado": "Documento alterado", "documento_inacessivel": "Documento deixou de estar acessível",
           "documento_novo": "Documento novo"}
LIGACAO = {"providencia": "providência determinada (sugerida, a validar)", "analise": "análise pendente (receber não é cumprir)",
           "encerramento": "sugere encerrar providências abertas: só com confirmação humana"}
_ARQUIVAMENTO = re.compile(r"\barquiv(e|em)-se\b|\bencerr(e|em)-se\b|\bconclu(a|am)-se o processo\b|\bprocesso (arquivado|concluido)\b|\bconclusao do processo\b")
_REABERTURA = re.compile(r"\breabert(ura|o|a)\b|\breabr(a|am)-se\b|\bdesarquiv")


def classificar_evento(tipo_codigo, texto):
    """O que o documento novo significa para o processo (NUSPEN, eventos.py): pelo tipo e pelo conteúdo."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    tipos = []
    if _ARQUIVAMENTO.search(t):
        tipos.append("arquivamento_conclusao")
    if _REABERTURA.search(t):
        tipos.append("reabertura")
    if tipo_codigo in ("A1", "A7"):
        tipos.append("despacho_decisao")
    if tipo_codigo == "A6":
        tipos.append("oficio_expedido")
    if tipo_codigo in ("B1", "B9") or extrair_indicios_resposta(texto or "", tipo_codigo):
        tipos.append("resposta_recebida")
    elif tipo_codigo.startswith("B"):
        tipos.append("documento_outro_orgao")
    return tipos or ["documento_novo"]


def sha_txt(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


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
            tem_ev = [r[1] for r in self._con.execute("PRAGMA table_info(sei_eventos)")]
            for c, t in (("documento", "INTEGER"), ("sugestao", "TEXT"), ("visto", "INTEGER DEFAULT 0"), ("confirmado", "INTEGER DEFAULT 0")):
                if c not in tem_ev:
                    self._con.execute("ALTER TABLE sei_eventos ADD COLUMN %s %s" % (c, t))
            if "indicios" not in [r[1] for r in self._con.execute("PRAGMA table_info(sei_documentos)")]:
                self._con.execute("ALTER TABLE sei_documentos ADD COLUMN indicios TEXT")
            # 7.26: retrato da lista do Controle de Processos (para a Visão geral): atribuição, marcadores, tipo, interessados,
            # "não visualizado" no SEI; e quando o APTO viu o processo pela 1ª vez e recebeu documento novo/alterado
            tem = [r[1] for r in self._con.execute("PRAGMA table_info(sei_processos)")]
            for c, t in (("atribuicao", "TEXT"), ("marcadores", "TEXT"), ("tipo", "TEXT"), ("interessados", "TEXT"), ("nao_visualizado", "INTEGER"),
                         ("primeiro_visto", "TEXT"), ("primeiro_sessao", "INTEGER"), ("ultimo_doc", "TEXT")):
                if c not in tem:
                    self._con.execute("ALTER TABLE sei_processos ADD COLUMN %s %s" % (c, t))

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
            self._retrato(s, dados.get("retrato"))
            if dados.get("lista_completa") and isinstance(dados.get("listados"), list):
                vistos = {str(x) for x in dados["listados"]}
                for (num, ids) in self._con.execute("SELECT numero, id_sei FROM sei_processos").fetchall():
                    fora = 0 if ids in vistos else 1
                    self._con.execute("UPDATE sei_processos SET fora_da_lista=? WHERE numero=?", (fora, num))
        return {"status": "concluida"}

    # ---- importação de PDF (o processo baixado do SEI, ou um anexo em PDF): como no NUSPEN ----
    def importar_pdf(self, caminho, pasta_originais, quem="", processo_hint="", titulo_hint="", id_hint="", nome_hint=""):
        """Lê o PDF página a página, separa os documentos pelo rodapé do SEI, classifica e aplica as regras (tudo sugestão).
        O original fica imutável (cópia com o SHA-256 no nome); o mesmo arquivo de novo só registra o recebimento. Página só de
        imagem fica sem texto (sem OCR neste computador): é avisada, nunca dada como lida."""
        import os
        import shutil
        from nuspen_regras.leitura import extrair_paginas
        from nuspen_regras.segmentacao import segmentar
        with open(caminho, "rb") as f:
            if f.read(5) != b"%PDF-":
                return {"erro": "O arquivo não é um PDF."}
            f.seek(0)
            h = hashlib.sha256()
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        sha = h.hexdigest()
        nome = nome_hint or os.path.basename(caminho)
        with self._trava, self._con:
            self._con.execute("INSERT INTO sei_recebimentos(sha256, nome, quando, quem) VALUES(?,?,?,?)", (sha, nome, _agora(), _t(quem, 100)))
            ja = self._con.execute("SELECT documentos, sem_texto FROM sei_arquivos WHERE sha256=?", (sha,)).fetchone()
        if ja:
            return {"ok": True, "novo": False, "nome": nome, "documentos": ja[0], "sem_texto": json.loads(ja[1] or "[]"),
                    "msg": "%s já tinha sido importado (o mesmo arquivo): só o recebimento foi registrado." % nome}
        try:
            paginas = extrair_paginas(caminho)
        except Exception as e:  # pdfplumber/pdfminer levantam tipos variados
            return {"erro": "Não foi possível ler o PDF (%s)." % type(e).__name__}
        paginas, por_ocr = self._ocr(caminho, paginas)
        segs = segmentar(paginas)
        os.makedirs(pasta_originais, exist_ok=True)
        destino = os.path.join(pasta_originais, "%s.pdf" % sha)
        if not os.path.exists(destino):
            shutil.copyfile(caminho, destino)
        por_num = {p.numero: p for p in paginas}
        # trecho sem rodapé fica no processo que predomina no arquivo (é um processo baixado do SEI); sem nenhum, no nome do arquivo
        from collections import Counter
        mais = Counter(sg.processo for sg in segs if sg.processo).most_common(1)
        principal = next((sg.processo_original for sg in segs if mais and sg.processo == mais[0][0]), None) or processo_hint or None
        ses = self.iniciar("pdf")["sessao"]
        itens, procs = [], {}
        for i, sg in enumerate(segs, 1):
            texto = "\n".join(por_num[n].texto for n in sg.paginas if por_num[n].texto).strip()
            if not texto:
                continue
            proc = sg.processo_original or principal or "PDF %s" % nome[:40]
            chave = normalizar_numero_processo(proc) or proc
            if chave not in procs:
                procs[chave] = proc
                # processo já lido do SEI (anexo dele, ou PDF do mesmo processo): não troca o id nem a especificação dele
                if not self._con.execute("SELECT 1 FROM sei_processos WHERE numero=?", (chave,)).fetchone():
                    itens.append({"tipo": "processo", "id_sei": "pdf-%s-%s" % (sha[:10], proc), "numero": proc, "especificacao": "", "unidade": "",
                                  "adaptador": "pdf"})
            faixa = "p. %d" % sg.paginas[0] if len(sg.paginas) == 1 else "p. %d–%d" % (sg.paginas[0], sg.paginas[-1])
            idd = sg.id_documento if sg.id_documento and not sg.id_repetido else ("%s-%d" % (id_hint, i) if id_hint else "%s-%d" % (sha[:10], i))
            rot = sg.rotulo or (titulo_hint if titulo_hint and sg.orfao else "trecho sem rodapé do SEI" if sg.orfao else "documento")
            itens.append({"tipo": "documento", "id_sei": "pdf-%s" % idd, "processo": proc, "titulo": "%s (PDF %s, %s)" % (rot, nome[:60], faixa),
                          "versao": sha[:12], "conteudo": texto, "hash": sha_txt(texto), "adaptador": "pdf"})
        r = self.receber_lote(ses, itens)
        self.concluir(ses, {"requisicoes": 0, "duracao_s": 0})
        sem = [p.numero for p in paginas if p.leitura == "sem_texto"]
        prej = [p.numero for p in paginas if p.leitura == "prejudicada"]
        ndoc = sum(1 for x in itens if x["tipo"] == "documento")
        with self._trava, self._con:
            self._con.execute("INSERT INTO sei_arquivos(sha256, nome, caminho, paginas, sem_texto, documentos, importado, quem) VALUES(?,?,?,?,?,?,?,?)",
                              (sha, nome, destino, len(paginas), json.dumps(sem), ndoc, _agora(), _t(quem, 100)))
        aviso = []
        if por_ocr:
            aviso.append("%d página(s) escaneada(s) lida(s) por OCR (confiança baixa: confira o texto): %s" % (len(por_ocr), ", ".join(map(str, por_ocr[:20]))))
        if sem:
            aviso.append("%d página(s) sem texto (escaneadas: %s, não foram lidas): %s" % (
                len(sem), "o OCR não conseguiu ler" if self.ocr_exe() else "sem OCR neste computador", ", ".join(map(str, sem[:20]))))
        if prej:
            aviso.append("%d página(s) com leitura prejudicada: %s" % (len(prej), ", ".join(map(str, prej[:20]))))
        orf = sum(1 for sg in segs if sg.orfao)
        if orf:
            aviso.append("%d trecho(s) sem o rodapé do SEI (ficam como documento à parte, para conferir)" % orf)
        return {"ok": True, "novo": True, "nome": nome, "paginas": len(paginas), "documentos": ndoc, "processos": list(procs.values()), "novos": r["novos"],
                "sem_texto": sem, "avisos": aviso, "msg": "%s: %d página(s), %d documento(s) em %d processo(s)." % (nome, len(paginas), ndoc, len(procs))}

    ocr_exe = staticmethod(lambda: __import__("nuspen_regras.leitura", fromlist=["tesseract"]).tesseract())
    ocr_pagina = staticmethod(lambda caminho, n, exe: __import__("nuspen_regras.leitura", fromlist=["ocr_pagina"]).ocr_pagina(caminho, n, exe))

    def _ocr(self, caminho, paginas):
        """Páginas só de imagem: lidas pelo Tesseract, se houver (texto marcado; o original não muda). Até 60 páginas por arquivo."""
        from nuspen_regras.leitura import PaginaLida, classificar_leitura
        sem = [p.numero for p in paginas if p.leitura == "sem_texto"]
        exe = self.ocr_exe() if sem else None
        if not exe:
            return paginas, []
        lidas, out = [], []
        for p in paginas:
            if p.leitura == "sem_texto" and len(lidas) < 60:
                try:
                    t = self.ocr_pagina(caminho, p.numero, exe)
                except Exception:  # Tesseract ou a renderização falharam: a página continua sem texto
                    t = ""
                if t.strip():
                    lidas.append(p.numero)
                    p = PaginaLida(numero=p.numero, texto="[lido por OCR, confiança baixa]\n" + t, leitura=classificar_leitura(t))
            out.append(p)
        return out, lidas

    def arquivos(self):
        with self._trava:
            return [dict(zip(("sha256", "nome", "paginas", "sem_texto", "documentos", "importado", "quem"), r)) for r in self._con.execute(
                "SELECT sha256, nome, paginas, sem_texto, documentos, importado, quem FROM sei_arquivos ORDER BY importado DESC").fetchall()]

    def _retrato(self, s, retrato):
        """O que a lista do Controle de Processos mostrou nesta leitura (todos os processos da página, também os não relidos)."""
        if not isinstance(retrato, list):
            return
        for x in retrato[:LIMITE_IDS]:
            if not isinstance(x, dict) or not x.get("id"):
                continue
            marc = [{"nome": _t(m.get("nome"), 120), "texto": _t(m.get("texto"), 300)} for m in (x.get("marcadores") or [])[:20] if isinstance(m, dict) and m.get("nome")]
            vals = (_t(x.get("atribuicao"), 120), json.dumps(marc, ensure_ascii=False), _t(x.get("tipo"), 200),
                    _t("; ".join(str(i) for i in (x.get("interessados") or [])[:10]), 500), 1 if x.get("naoVisualizado") else 0)
            n = self._con.execute("UPDATE sei_processos SET atribuicao=?, marcadores=?, tipo=?, interessados=?, nao_visualizado=? WHERE id_sei=?",
                                  (*vals, _t(x.get("id"), 80))).rowcount
            if not n and x.get("numero"):
                original = _t(x.get("numero"), 60)
                num = normalizar_numero_processo(original) or original
                self._con.execute("INSERT OR IGNORE INTO sei_processos(numero, original, id_sei, especificacao, unidade, ultima_movimentacao, atualizado, "
                                  "fora_da_lista, primeiro_visto, primeiro_sessao) VALUES(?,?,?,?,?,?,?,0,?,?)",
                                  (num, original, _t(x.get("id"), 80), _t(x.get("especificacao"), 500), "", "", _agora(), _agora(), s))
                self._con.execute("UPDATE sei_processos SET atribuicao=?, marcadores=?, tipo=?, interessados=?, nao_visualizado=? WHERE numero=?", (*vals, num))

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
        """Lote da extensão. O anexo PDF (7.28) passa pela importação de PDF depois do lote (rodapé, classificação, regras)."""
        itens = itens if isinstance(itens, list) else []
        anexos = [d for d in itens if isinstance(d, dict) and d.get("tipo") == "anexo"]
        r = self._receber_lote(sid, [d for d in itens if not (isinstance(d, dict) and d.get("tipo") == "anexo")], cursor)
        for d in anexos[:20]:
            x = self._anexo(sid, d)
            r["novos"] += x.get("novos", 0)
        return r

    def _anexo(self, sid, d):
        import base64
        import os
        import tempfile
        id_sei, proc, titulo = _t(d.get("id_sei"), 80), _t(d.get("processo"), 60), _t(d.get("titulo"))
        try:
            b = base64.b64decode(str(d.get("pdf_b64") or ""), validate=True)
        except Exception:
            b = b""
        with self._trava, self._con:
            s = self._sessao(sid)
            if not b or hashlib.sha256(b).hexdigest() != str(d.get("hash") or ""):
                self._marcar(s, "documento", id_sei, "falha", "anexo: hash divergente ou vazio", processo=proc)
                return {"erro": "anexo inválido"}
        pasta = os.path.join(os.path.dirname(os.path.abspath(self.g.caminho)), "originais_sei")
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b)
            r = self.importar_pdf(tmp, pasta, "leitura do SEI", processo_hint=proc, titulo_hint=titulo, id_hint=id_sei, nome_hint=titulo or "anexo")
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        with self._trava, self._con:
            self._marcar(self._sessao(sid), "documento", id_sei, "analisado" if r.get("ok") else "falha", r.get("erro", ""), hash=d.get("hash"),
                         processo=proc, titulo=titulo, adaptador=d.get("adaptador"))
        return r

    def _receber_lote(self, sid, itens, cursor=None):
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
        self._con.execute("UPDATE sei_processos SET primeiro_visto=?, primeiro_sessao=? WHERE numero=? AND primeiro_visto IS NULL", (_agora(), s, num))
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
        for tipo in classificar_evento(cl.codigo or "", _frases_por_linha(_sem_rodape(texto))):
            sug = {"resposta_recebida": "analise", "arquivamento_conclusao": "encerramento"}.get(tipo, "")
            if tipo == "despacho_decisao" and self._con.execute("SELECT 1 FROM sei_obrigacoes WHERE documento=? LIMIT 1", (novo,)).fetchone():
                sug = "providencia"
            self._con.execute("INSERT INTO sei_eventos(sessao, processo, tipo, descricao, quando, documento, sugestao) VALUES(?,?,?,?,?,?,?)",
                              (s, num, tipo, _t(titulo, 300), _agora(), novo, sug))
        self._marcar(s, "documento", id_sei, "analisado", versao=d.get("versao"), hash=h, processo=original, titulo=titulo, adaptador=d.get("adaptador"))
        self._con.execute("UPDATE sei_processos SET ultimo_doc=? WHERE numero=?", (_agora(), num))
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
            pc = ("numero", "original", "especificacao", "unidade", "ultima_movimentacao", "atualizado", "fora_da_lista", "atribuicao", "marcadores", "tipo",
                  "interessados", "nao_visualizado", "primeiro_visto", "primeiro_sessao", "ultimo_doc")
            procs = [dict(zip(pc, r)) for r in self._con.execute("SELECT %s FROM sei_processos ORDER BY atualizado DESC" % ", ".join(pc))]
            sess = self._con.execute("SELECT id, iniciada FROM sei_sessoes WHERE status='concluida' ORDER BY id DESC LIMIT 2").fetchall()
            desde = sess[0][1] if sess else None
            novos_doc = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_documentos WHERE recebido>=? AND substituido_por IS NULL GROUP BY processo",
                                               (desde,)).fetchall()) if desde else {}
            prazos = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_obrigacoes WHERE status IN ('sugestao','validada') AND prazo_natureza='expresso' "
                                            "GROUP BY processo").fetchall())
            por_proc = {}
            for num, st, n in self._con.execute("SELECT processo, status, COUNT(*) FROM sei_obrigacoes GROUP BY processo, status"):
                por_proc.setdefault(num, {})[st] = n
            docs = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_documentos WHERE substituido_por IS NULL GROUP BY processo").fetchall())
            falhas = dict(self._con.execute("SELECT processo, COUNT(*) FROM sei_itens WHERE estado='falha' GROUP BY processo").fetchall())
            ult = self._con.execute("SELECT id, modo, status, iniciada, concluida, novos, modificados, falhas FROM sei_sessoes ORDER BY id DESC LIMIT 1").fetchone()
            for p in procs:
                p["marcadores"] = json.loads(p["marcadores"] or "[]")
                p["docs_novos"] = novos_doc.get(p["numero"], 0)
                p["prazos"] = prazos.get(p["numero"], 0)
                # entrou desde a última leitura: visto pela 1ª vez na última leitura concluída, havendo uma anterior para comparar
                p["entrou_agora"] = bool(len(sess) > 1 and p["primeiro_sessao"] and p["primeiro_sessao"] > sess[1][0])
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
                "leituras": len(sess), "agora": _agora(),
                # gravado antes da correção dos acentos (lido como UTF-8): some quando o processo é lido de novo
                "acentos_quebrados": q("SELECT COUNT(*) FROM sei_processos WHERE especificacao LIKE ?", "%\ufffd%")
                + q("SELECT COUNT(*) FROM sei_documentos WHERE substituido_por IS NULL AND (texto LIKE ? OR titulo LIKE ?)", "%\ufffd%", "%\ufffd%"),
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
