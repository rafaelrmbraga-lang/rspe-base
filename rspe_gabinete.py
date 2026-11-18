"""Base do gabinete: o que não pertence a uma base da Execução (uma por comarca ou unidade). Hoje guarda os Atendimentos (fila
do SAP do dia, o registro de cada atendimento, as pendências, o Fluxo e o Controle do mês); depois, o SEI e o Quadro.

Um arquivo só, "gabinete.sqlite", na pasta de dados do APTO (ao lado das bases). Cada atendimento e cada pendência é uma linha
(JSON do mesmo formato da extensão APTO Atendimentos 1.5.0, para importar o backup dela sem conversão); ajustes, frases prontas e
configuração ficam em chave-valor. A extensão do navegador manda a fila e o Fato Narrado lidos no SAP; aqui eles se juntam ao
atendimento do dia pelo nome, sem nunca apagar o que a pessoa escreveu (mesma regra do comum.js da extensão)."""
import json
import os
import random
import re
import sqlite3
import string
import threading
import time
import unicodedata
from datetime import date, datetime

COLECOES = ("atendimentos", "pecas")
CHAVES = ("ajustes", "modelos", "config")
# campos que a tela grava; o resto (fato, fatoLido, rk, chegada, statusSap, unidade) vem do SAP e a tela não apaga
CAMPOS_TELA = ("nome", "hora", "processos", "contato", "quem", "assistida", "forma", "formaManual", "abertura", "corpo", "status",
               "msg", "concluido", "chamadoEm", "data", "origem", "criadoEm", "id")
COPIAS = 10


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


def chave_nome(s):
    """nome sem as anotações entre parênteses do SAP, ex.: "(Usar este perfil)"."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)?", " ", norm(s))).strip()


MINUSC = {"DA", "DE", "DO", "DAS", "DOS", "E"}


def nome_proprio(s):
    t = re.sub(r"\s+", " ", str(s or "")).strip()
    if t != t.upper():
        return t
    out = []
    for i, w in enumerate(t.lower().split(" ")):
        out.append(w if i > 0 and w.upper() in MINUSC else w[:1].upper() + w[1:])
    return " ".join(out)


def novo_id():
    base = format(int(time.time() * 1000), "x")
    return base + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))


def hoje_iso():
    return date.today().isoformat()


def mesclar(lista, dado):
    """Junta (ou cria) o atendimento do dia pelo nome; nunca apaga o que a pessoa já escreveu. Devolve o atendimento."""
    k = chave_nome(dado.get("nome"))
    a = next((x for x in lista if x.get("data") == dado.get("data") and chave_nome(x.get("nome")) == k), None)
    if not a:
        a = {"id": novo_id(), "data": dado.get("data"), "hora": "",
             "nome": nome_proprio(re.sub(r"\s+", " ", re.sub(r"\([^)]*\)?", " ", str(dado.get("nome") or ""))).strip()),
             "processos": [], "contato": "", "quem": "", "assistida": False, "forma": "presencial", "formaManual": False,
             "abertura": True, "corpo": "", "status": "agendado", "fato": None, "origem": "sap", "criadoEm": int(time.time() * 1000)}
        lista.append(a)
    if dado.get("hora") and not a.get("hora"):
        a["hora"] = dado["hora"]
    for c in ("rk", "unidade", "statusSap"):
        if dado.get(c):
            a[c] = dado[c]
    if dado.get("forma") and not a.get("formaManual"):
        a["forma"] = dado["forma"]
    if dado.get("chegada") or re.search(r"PRESENTE", str(dado.get("statusSap") or ""), re.I):
        if dado.get("chegada"):
            a["chegada"] = dado["chegada"]
        if a.get("status") == "agendado":
            a["status"] = "presente"
    fato = dado.get("fato")
    if fato:
        a["fato"] = fato
        a.setdefault("processos", [])
        if not a["processos"] and fato.get("processos"):
            a["processos"] = list(fato["processos"])
        if not a.get("contato") and fato.get("contato"):
            a["contato"] = fato["contato"]
        if not a.get("quem") and fato.get("quem"):
            a["quem"] = fato["quem"]
        if not dado.get("forma") and fato.get("virtual") and not a.get("formaManual"):
            a["forma"] = "virtual"
    if dado.get("fatoLido"):
        a["fatoLido"] = dado["fatoLido"]
    return a


def data_para(lista, nome, hoje=None):
    """O Fato Narrado lido é do atendimento de hoje ou do próximo agendado com esse nome."""
    hoje = hoje or hoje_iso()
    k = chave_nome(nome)
    prox = sorted((x for x in lista if chave_nome(x.get("nome")) == k and (x.get("data") or "") >= hoje), key=lambda x: x["data"])
    return prox[0]["data"] if prox else hoje


class Gabinete:
    """Acesso à gabinete.sqlite (uma conexão, protegida por trava: a tela e o servidor da extensão gravam ao mesmo tempo)."""

    def __init__(self, caminho):
        self.caminho = caminho
        os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        self._trava = threading.RLock()
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        with self._con:
            for c in COLECOES:
                self._con.execute("CREATE TABLE IF NOT EXISTS %s (id TEXT PRIMARY KEY, data TEXT, json TEXT NOT NULL, atualizado TEXT)" % c)
            self._con.execute("CREATE TABLE IF NOT EXISTS kv (chave TEXT PRIMARY KEY, json TEXT NOT NULL, atualizado TEXT)")
            self._con.execute("CREATE INDEX IF NOT EXISTS atendimentos_data ON atendimentos(data)")

    def fechar(self):
        with self._trava:
            self._con.close()

    # ---- leitura ----
    def lista(self, col):
        with self._trava:
            return [json.loads(j) for (j,) in self._con.execute("SELECT json FROM %s ORDER BY data, id" % col)]

    def kv(self, chave, padrao=None):
        with self._trava:
            r = self._con.execute("SELECT json FROM kv WHERE chave=?", (chave,)).fetchone()
        return json.loads(r[0]) if r else padrao

    def tudo(self):
        return {"atendimentos": self.lista("atendimentos"), "pecas": self.lista("pecas"), "ajustes": self.kv("ajustes", {}),
                "modelos": self.kv("modelos"), "config": self.kv("config", {})}

    # ---- gravação ----
    def _gravar(self, col, x):
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dia = x.get("data") or x.get("feitoEm") or ""
        self._con.execute("INSERT INTO %s(id, data, json, atualizado) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, "
                          "json=excluded.json, atualizado=excluded.atualizado" % col, (x["id"], dia, json.dumps(x, ensure_ascii=False), agora))

    def gravar_kv(self, chave, valor):
        with self._trava, self._con:
            self._con.execute("INSERT INTO kv(chave, json, atualizado) VALUES(?,?,?) ON CONFLICT(chave) DO UPDATE SET json=excluded.json, "
                              "atualizado=excluded.atualizado", (chave, json.dumps(valor, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def mudar(self, diff):
        """Mudanças vindas da tela: {colecao: {upsert: [...], remover: [ids]}, ajustes|modelos|config: valor}. No atendimento, o que
        veio do SAP depois que a tela leu (Fato Narrado, chegada) é mantido. Devolve o que de fato ficou gravado (para a tela)."""
        out = {}
        with self._trava, self._con:
            for col in COLECOES:
                d = diff.get(col)
                if not isinstance(d, dict):
                    continue
                ups = []
                for x in d.get("upsert") or []:
                    if not isinstance(x, dict) or not x.get("id"):
                        continue
                    if col == "atendimentos":
                        r = self._con.execute("SELECT json FROM atendimentos WHERE id=?", (x["id"],)).fetchone()
                        if r:
                            atual = json.loads(r[0])
                            for k in list(x.keys()):
                                if k not in CAMPOS_TELA and k in atual:
                                    x[k] = atual[k]
                            for k, v in atual.items():
                                x.setdefault(k, v)
                    self._gravar(col, x)
                    ups.append(x)
                rem = [i for i in (d.get("remover") or []) if isinstance(i, str)]
                for i in rem:
                    self._con.execute("DELETE FROM %s WHERE id=?" % col, (i,))
                out[col] = {"upsert": ups, "remover": rem}
            for k in CHAVES:
                if k in diff:
                    self._con.execute("INSERT INTO kv(chave, json, atualizado) VALUES(?,?,?) ON CONFLICT(chave) DO UPDATE SET json=excluded.json, "
                                      "atualizado=excluded.atualizado", (k, json.dumps(diff[k], ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    out[k] = diff[k]
        return out

    # ---- o que vem do SAP (extensão) ----
    def receber_fila(self, itens):
        """Fila "Assistidos em Espera" lida no SAP: [{nome, data, hora, rk, forma, chegada, unidade, statusSap}]."""
        mud, novos = [], 0
        with self._trava, self._con:
            datas = sorted({str(x.get("data") or "") for x in itens if isinstance(x, dict)})
            lista = [json.loads(j) for (j,) in self._con.execute(
                "SELECT json FROM atendimentos WHERE data IN (%s)" % ",".join("?" * len(datas)), datas)] if datas else []
            for x in itens:
                if not isinstance(x, dict) or not x.get("nome") or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(x.get("data") or "")):
                    continue
                antes = len(lista)
                antigo = next((json.dumps(a, sort_keys=True) for a in lista if a.get("data") == x["data"] and chave_nome(a.get("nome")) == chave_nome(x["nome"])), None)
                a = mesclar(lista, _limpo(x))
                novos += len(lista) > antes
                if json.dumps(a, sort_keys=True) != antigo:
                    self._gravar("atendimentos", a)
                    mud.append(a)
        return {"novos": novos, "mudados": mud}

    def receber_fato(self, d):
        """Fato Narrado lido no SAP: {nome, fato|null, forma, fatoLido}."""
        if not isinstance(d, dict) or not d.get("nome"):
            return None
        with self._trava, self._con:
            hoje = hoje_iso()
            k = chave_nome(d["nome"])
            lista = [a for a in (json.loads(j) for (j,) in self._con.execute("SELECT json FROM atendimentos WHERE data>=?", (hoje,)))
                     if chave_nome(a.get("nome")) == k]
            dado = _limpo({"nome": d["nome"], "data": data_para(lista, d["nome"], hoje), "fato": d.get("fato") or None,
                           "forma": d.get("forma") or "", "fatoLido": d.get("fatoLido") or datetime.now().isoformat()})
            a = mesclar(lista, dado)
            self._gravar("atendimentos", a)
        return a

    def resumo_dia(self, dia=None):
        dia = dia or hoje_iso()
        with self._trava:
            L = [json.loads(j) for (j,) in self._con.execute("SELECT json FROM atendimentos WHERE data=?", (dia,))]
        return {"total": len(L), "lidos": sum(1 for a in L if a.get("fatoLido")), "presentes": sum(1 for a in L if a.get("status") == "presente")}

    # ---- backup da extensão (Exportar tudo .json) e cópias ----
    def importar_backup(self, x):
        if not isinstance(x, dict) or x.get("app") != "APTO Atendimentos":
            raise ValueError("o arquivo não é um backup do APTO Atendimentos")
        n = 0
        with self._trava, self._con:
            for col in COLECOES:
                ids = {i for (i,) in self._con.execute("SELECT id FROM %s" % col)}
                for y in x.get(col) or []:
                    if isinstance(y, dict) and y.get("id") and y["id"] not in ids:
                        self._gravar(col, y)
                        n += 1
        aj = dict(x.get("ajustes") or {})
        aj.update(self.kv("ajustes", {}))
        self.gravar_kv("ajustes", aj)
        if x.get("modelos") and not self.kv("modelos"):
            self.gravar_kv("modelos", x["modelos"])
        if x.get("config") and not self.kv("config"):
            self.gravar_kv("config", x["config"])
        return n

    def copia_do_dia(self, pasta):
        """Uma cópia por dia (guarda as 10 últimas), feita ao abrir o programa."""
        try:
            os.makedirs(pasta, exist_ok=True)
            alvo = os.path.join(pasta, "gabinete %s.sqlite" % hoje_iso())
            if not os.path.exists(alvo):
                with self._trava:
                    dst = sqlite3.connect(alvo)
                    with dst:
                        self._con.backup(dst)
                    dst.close()
            velhas = sorted(n for n in os.listdir(pasta) if n.startswith("gabinete ") and n.endswith(".sqlite"))
            for n in velhas[:-COPIAS]:
                os.remove(os.path.join(pasta, n))
            return alvo
        except (OSError, sqlite3.Error):
            return None


def _limpo(x):
    """só os campos esperados, com tamanho limitado (o que chega da página do SAP é dado, não instrução)."""
    def t(v, n=300):
        return str(v)[:n] if v is not None else ""
    out = {k: t(x.get(k)) for k in ("nome", "data", "hora", "rk", "forma", "chegada", "unidade", "statusSap", "fatoLido") if x.get(k)}
    if out.get("forma") not in (None, "", "presencial", "virtual"):
        out.pop("forma")
    f = x.get("fato")
    if isinstance(f, dict):
        out["fato"] = {"data": t(f.get("data"), 40), "defensor": t(f.get("defensor"), 200), "texto": t(f.get("texto"), 20000),
                       "processos": [t(p, 30) for p in (f.get("processos") or [])][:5], "contato": t(f.get("contato"), 400),
                       "quem": t(f.get("quem"), 30), "virtual": bool(f.get("virtual")), "pedido": t(f.get("pedido"), 4000)}
    return out


AVISO_SAP = ("o SAP não está aberto com a extensão do APTO. Abra o SAP na tela de atendimento (Assistidos em Espera) e confira se a "
             "extensão do APTO está instalada e ligada; depois recarregue a aba do SAP (F5).")
AVISO_SEI = ("o SEI não está aberto com a extensão do APTO. Entre no SEI da Defensoria (numa aba do navegador) e abra o Controle de "
             "Processos; se já está aberto, recarregue a aba do SEI (F5).")
AVISO_SEEU = ("o SEEU não está aberto com a extensão do APTO. Entre no SEEU (numa aba do navegador); se já está aberto, recarregue a aba "
              "do SEEU (F5).")
# pedidos de cada sistema e quanto tempo esperar a resposta (a leitura do SEI e a do SEEU respondem logo e seguem informando o andamento)
TIPOS_SAP = {"chamarSap": 45, "selecionarSap": 45, "lerFilaSap": 1200, "pararFilaSap": 15}
TIPOS_SEI = {"lerSei": 20, "pararSei": 15}
TIPOS_SEEU = {"lerMesa": 20, "pararMesa": 15}


class Comandos:
    """Pedidos da tela para a aba do sistema (SAP: Chamar, Ver no SAP, Ler a fila; SEI: Ler o SEI; SEEU: Ler a Mesa). A extensão,
    na aba aberta e logada, pergunta a cada 2 ou 3 s se há pedido; quem pede espera a resposta. Nenhum pedido fica guardado depois
    de respondido ou vencido."""

    TIPOS = TIPOS_SAP

    def __init__(self, tipos=None, aviso=AVISO_SAP, nome="SAP"):
        if tipos is not None:
            self.TIPOS = tipos
        self.aviso = aviso
        self.nome = nome
        self._trava = threading.Lock()
        self._fila = []
        self._seq = 0
        self.visto = 0.0          # última vez que a extensão perguntou (a aba do SAP está aberta)
        self.leitura = None       # andamento da leitura da fila, como a extensão informa

    def pedir(self, tipo, dados, esperar_extensao=8.0):
        if tipo not in self.TIPOS:
            return {"erro": "pedido desconhecido"}
        if time.time() - self.visto > esperar_extensao:
            return {"erro": self.aviso}
        with self._trava:
            self._seq += 1
            c = {"id": self._seq, "tipo": tipo, "nome": str((dados or {}).get("nome") or "")[:300], "rk": str((dados or {}).get("rk") or "")[:80],
                 "todos": bool((dados or {}).get("todos")), "modo": str((dados or {}).get("modo") or "")[:30],
                 "retomar": (dados or {}).get("retomar") if isinstance((dados or {}).get("retomar"), int) else None,
                 "opcoes": (dados or {}).get("opcoes") if isinstance((dados or {}).get("opcoes"), dict) else None, "criado": time.time(), "pego": 0.0, "evento": threading.Event(), "resposta": None}
            self._fila.append(c)
        prazo = self.TIPOS[tipo]
        if not c["evento"].wait(10):
            if not c["pego"]:
                self._tirar(c)
                return {"erro": "a extensão não pegou o pedido: recarregue a aba do %s (F5) e tente de novo." % self.nome}
        if not c["evento"].is_set() and not c["evento"].wait(prazo):
            self._tirar(c)
            return {"erro": "o %s não respondeu a tempo" % self.nome}
        self._tirar(c)
        return c["resposta"] or {"erro": "o %s não respondeu" % self.nome}

    def _tirar(self, c):
        with self._trava:
            if c in self._fila:
                self._fila.remove(c)

    def proximo(self):
        """Chamado pela extensão: entrega o próximo pedido não pego (e marca a aba do SAP como aberta)."""
        self.visto = time.time()
        with self._trava:
            for c in self._fila:
                if not c["pego"]:
                    c["pego"] = time.time()
                    # avisa quem espera que a extensão pegou (a espera longa começa agora)
                    return {k: c[k] for k in ("id", "tipo", "nome", "rk", "todos", "modo", "retomar", "opcoes")}
        return None

    def responder(self, cid, resposta):
        with self._trava:
            c = next((x for x in self._fila if x["id"] == cid), None)
        if not c:
            return False
        c["resposta"] = resposta if isinstance(resposta, dict) else {"erro": "resposta inválida"}
        c["evento"].set()
        return True

    def estado(self):
        return {"aberto": time.time() - self.visto < 8, "visto": self.visto, "leitura": self.leitura}


def pasta_do_mes(raiz, i_mes):
    """Pasta do mês dentro de "2. Atendimentos": acha pelo nome ("8. Novembro") ou cria com o próximo número."""
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    alvo = meses[i_mes]
    numerados = 0
    for n in sorted(os.listdir(raiz)):
        if not os.path.isdir(os.path.join(raiz, n)):
            continue
        if re.match(r"^\d+\.", n):
            numerados += 1
        if norm(re.sub(r"^\d+\.\s*", "", n)) == norm(alvo):
            return os.path.join(raiz, n)
    p = os.path.join(raiz, "%d. %s" % (numerados + 1, alvo))
    os.makedirs(p, exist_ok=True)
    return p

