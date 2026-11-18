"""SEEU no APTO (função SEEU): as intimações da Mesa do Defensor lidas pela triagem da extensão ficam guardadas na base do gabinete
até a pessoa concluir. A leitura é a mesma da extensão (não inicia prazo no SEEU); o APTO só guarda e mostra.

- Cada intimação é uma linha: aba | processo | data de envio (uma intimação nova do mesmo processo é outra linha).
- Triagem nova: atualiza as que continuam na Mesa e marca "saiu da Mesa" as que não aparecem mais (só se a triagem leu a mesma aba e
  a mesma situação). Nada sai do APTO por isso: só a pessoa conclui.
- Concluir com baixa: a peça feita (tipo da tabela CONTROLE - 3ª DPEP) e a data entram como pendência feita, e contam na produção do
  mês (função Relatório). Concluir sem baixa: não conta. Reabrir desfaz (a peça lançada sai da contagem)."""
import json
import re
import time
from datetime import datetime

import rspe_gabinete as rgab

TABELA = """CREATE TABLE IF NOT EXISTS seeu_itens (chave TEXT PRIMARY KEY, processo TEXT, json TEXT NOT NULL, status TEXT, primeiro_visto TEXT,
  ultimo_visto TEXT, fora_da_mesa TEXT, concluido_em TEXT, baixa TEXT)"""
# peças da tabela CONTROLE - 3ª DPEP (mesmos códigos do painel de atendimentos, comum.js); "Atendimentos" não é peça
PECAS = {"PP": "Pedido de Providência", "AGEX": "AgEx", "HC": "HC", "ED": "ED", "MANIF": "Manifestações", "ST": "Saída Temporária",
         "PROG": "Progressão", "LC": "LC", "INDULTO": "Indulto", "COMUT": "Comutação", "PRESC": "Prescrição", "EXT": "Extinção",
         "MONIT": "Flex. Monitoramento", "DOMIC": "Domiciliar", "REMICAO": "Remição", "DETRACAO": "Detração", "PRD": "Subs. PRD",
         "JUST": "Justificativas", "CIENCIA": "Ciência", "OFICIO": "Ofícios"}


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def chave_de(l):
    return "%s|%s|%s" % (str(l.get("aba") or "")[:40], str(l.get("processo") or "")[:30], str(l.get("dataEnvio") or "")[:20])


class Seeu:
    def __init__(self, gabinete):
        self.g = gabinete
        self._con = gabinete._con
        self._trava = gabinete._trava
        with self._trava, self._con:
            self._con.execute(TABELA)
            tem = [r[1] for r in self._con.execute("PRAGMA table_info(seeu_itens)")]
            for c in ("atribuido", "quadro"):  # 7.28: quem cuida da intimação; o cartão do Quadro ligado a ela
                if c not in tem:
                    self._con.execute("ALTER TABLE seeu_itens ADD COLUMN %s TEXT" % c)

    def receber(self, t):
        """Triagem da extensão: {quando, situacao, abas: [nomes], linhas: [...]}. Devolve {novas, atualizadas, sairam}."""
        linhas = [l for l in (t.get("linhas") or []) if isinstance(l, dict) and l.get("processo")]
        abas = {str(a) for a in (t.get("abas") or [])} or {str(l.get("aba") or "") for l in linhas}
        sit = t.get("situacao")
        agora = _agora()
        res = {"novas": 0, "atualizadas": 0, "sairam": 0}
        with self._trava, self._con:
            vistas = set()
            for l in linhas:
                k = chave_de(l)
                vistas.add(k)
                r = self._con.execute("SELECT status FROM seeu_itens WHERE chave=?", (k,)).fetchone()
                dado = json.dumps(l, ensure_ascii=False)[:200000]
                if r:
                    self._con.execute("UPDATE seeu_itens SET json=?, ultimo_visto=?, fora_da_mesa=NULL WHERE chave=?", (dado, agora, k))
                    res["atualizadas"] += 1
                else:
                    self._con.execute("INSERT INTO seeu_itens(chave, processo, json, status, primeiro_visto, ultimo_visto) VALUES(?,?,?,?,?,?)",
                                      (k, str(l.get("processo"))[:30], dado, "aberto", agora, agora))
                    res["novas"] += 1
            # as que não vieram nesta triagem (mesma aba e mesma situação lidas): saíram da Mesa, mas ficam até a pessoa concluir
            for k, j in self._con.execute("SELECT chave, json FROM seeu_itens WHERE status='aberto' AND fora_da_mesa IS NULL").fetchall():
                if k in vistas:
                    continue
                l = json.loads(j)
                if str(l.get("aba") or "") in abas and (sit is None or l.get("situacao") in (None, sit)):
                    self._con.execute("UPDATE seeu_itens SET fora_da_mesa=? WHERE chave=?", (agora, k))
                    res["sairam"] += 1
        return res

    def listar(self):
        with self._trava:
            rows = self._con.execute("SELECT chave, json, status, primeiro_visto, ultimo_visto, fora_da_mesa, concluido_em, baixa, atribuido, quadro "
                                     "FROM seeu_itens").fetchall()
        out = []
        for k, j, st, pv, uv, fora, conc, baixa, atr, qd in rows:
            l = json.loads(j)
            l.update(chave=k, status=st, primeiroVisto=pv, ultimoVisto=uv, foraDaMesa=fora or "", concluidoEm=conc or "",
                     baixa=json.loads(baixa) if baixa else None, atribuido=atr or "", quadro=qd or "")
            out.append(l)
        # histórico do processo: as outras intimações dele (anteriores ou de outra aba), com a baixa de cada uma
        por = {}
        for l in out:
            por.setdefault(re.sub(r"\D", "", str(l.get("processo") or "")), []).append(l)
        for l in out:
            l["anteriores"] = sorted(({"aba": x.get("aba"), "dataEnvio": x.get("dataEnvio"), "status": x["status"], "concluidoEm": x["concluidoEm"],
                                      "baixa": (x["baixa"] or {}).get("pecaNome", "")} for x in por.get(re.sub(r"\D", "", str(l.get("processo") or "")), [])
                                     if x["chave"] != l["chave"]), key=lambda x: x["concluidoEm"] or x["dataEnvio"] or "", reverse=True)
        return out

    def atribuir(self, chave, quem):
        """Quem cuida desta intimação (vazio = ninguém)."""
        with self._trava, self._con:
            n = self._con.execute("UPDATE seeu_itens SET atribuido=? WHERE chave=?", (str(quem or "")[:100], str(chave))).rowcount
        return {"ok": True} if n else {"erro": "intimação não encontrada"}

    def ligar_quadro(self, chave, peca_id):
        with self._trava, self._con:
            self._con.execute("UPDATE seeu_itens SET quadro=? WHERE chave=?", (str(peca_id)[:40], str(chave)))

    def _item(self, chave):
        r = self._con.execute("SELECT json, status, baixa FROM seeu_itens WHERE chave=?", (str(chave),)).fetchone()
        return (json.loads(r[0]), r[1], json.loads(r[2]) if r[2] else None) if r else (None, None, None)

    def concluir(self, chave, peca="", data="", obs="", quem=""):
        """Conclui a intimação. Com peça (código do CONTROLE) e data (dd/mm/aaaa ou aaaa-mm-dd): a peça conta na produção do mês."""
        if peca and peca not in PECAS:
            return {"erro": "peça desconhecida"}
        iso = ""
        if peca:
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str(data or "")) or None
            iso = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else str(data or "")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
                return {"erro": "informe a data da peça (dd/mm/aaaa)"}
        with self._trava:
            l, st, _ = self._item(chave)
            qd = (self._con.execute("SELECT quadro FROM seeu_itens WHERE chave=?", (str(chave),)).fetchone() or [None])[0]
        if not l:
            return {"erro": "intimação não encontrada"}
        if st == "concluido":
            return {"erro": "já concluída"}
        baixa = {"peca": peca, "pecaNome": PECAS.get(peca, ""), "data": iso, "obs": str(obs or "")[:500], "pecaId": "", "quem": str(quem or "")[:100],
                 "doQuadro": False}
        cartao = next((x for x in self.g.lista("pecas") if qd and x.get("id") == qd and x.get("status") == "pendente"), None)
        p = None
        if peca:
            if cartao:  # o cartão do Quadro desta intimação vira a peça feita: conta uma vez só
                p = dict(cartao, tipo=peca, status="feito", feitoEm=iso, obs=(str(cartao.get("obs") or "") + (" · baixa: " + obs if obs else ""))[:500])
                baixa["doQuadro"] = True
            else:
                p = {"id": rgab.novo_id(), "tipo": peca, "processo": str(l.get("processo") or "")[:30], "nome": rgab.nome_proprio(str(l.get("executado") or ""))[:200],
                     "data": iso, "status": "feito", "feitoEm": iso, "coluna": "fazer", "prazo": "", "obs": ("Mesa do SEEU (%s): %s" % (l.get("aba") or "", obs or ""))[:500],
                     "origem": "seeu", "atendimentoId": "", "criadoEm": int(time.time() * 1000)}
            baixa["pecaId"] = p["id"]
            self.g.mudar({"pecas": {"upsert": [p]}})
        elif cartao:  # concluída sem peça: o cartão sai do Quadro (arquivado, não conta)
            p = dict(cartao, status="arquivado", feitoEm=rgab.hoje_iso())
            baixa["pecaId"], baixa["doQuadro"] = p["id"], True
            self.g.mudar({"pecas": {"upsert": [p]}})
        with self._trava, self._con:
            self._con.execute("UPDATE seeu_itens SET status='concluido', concluido_em=?, baixa=? WHERE chave=?", (_agora(), json.dumps(baixa, ensure_ascii=False), str(chave)))
        return {"ok": True, "peca": p}

    def reabrir(self, chave):
        with self._trava:
            l, st, baixa = self._item(chave)
        if not l:
            return {"erro": "intimação não encontrada"}
        rem, volta = [], None
        if baixa and baixa.get("pecaId") and baixa.get("doQuadro"):  # o cartão do Quadro volta a ser pendência
            c = next((x for x in self.g.lista("pecas") if x.get("id") == baixa["pecaId"]), None)
            if c:
                volta = dict(c, status="pendente", feitoEm="", tipo="" if c.get("status") == "feito" else c.get("tipo", ""))
                self.g.mudar({"pecas": {"upsert": [volta]}})
        elif baixa and baixa.get("pecaId"):
            rem = [baixa["pecaId"]]
            self.g.mudar({"pecas": {"remover": rem}})
        with self._trava, self._con:
            self._con.execute("UPDATE seeu_itens SET status='aberto', concluido_em=NULL, baixa=NULL WHERE chave=?", (str(chave),))
        return {"ok": True, "removidas": rem, "voltou": volta}
