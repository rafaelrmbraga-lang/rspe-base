"""Executor da bateria de casos simulados: insere os casos (RSPE, ficha, dados manuais) numa CÓPIA da base, abre pela Api
da tela (rspe_app.Api, como a janela faz), monta a lista e confere cada verificação do caso com o registro completo
(Api.registro). Uso: python roda_casos.py [casos.json] [--vazia] [--so S001,S002]
--vazia: base nova só com os casos (rápido); sem a opção, cópia da base real 08.10 + casos."""
import sys, types, os, json, re, shutil, sqlite3, tempfile
from datetime import datetime, date
AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
BASE_REAL = os.environ.get("APTO_BASE_REAL", "")  # cópia de uma base real (opcional); sem ela, só os casos
sys.path.insert(0, REPO)
wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0; sys.modules["webview"] = wv
import rspe_app as app
import rspe_view as rv

HOJE = date(2026, 10, 12)


class _DT(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(HOJE.year, HOJE.month, HOJE.day, 12, 0, 0)


app.datetime = _DT  # data de referência fixa (a tela usa datetime.now())


def _norm(t):
    return app._norm(t)


def preparar(casos, vazia):
    destino = os.path.join(AQUI, "base_sim.sqlite")
    for x in (destino, destino + "-journal"):
        if os.path.exists(x):
            os.remove(x)
    if not vazia:
        shutil.copy(BASE_REAL, destino)
    b = app.Base(destino)
    agora = "12/10/2026 10:00"
    for c in casos:
        for r in [c["rspe"]] + list(c.get("extra_rspe") or []):
            dados = json.dumps(r, ensure_ascii=False)
            b.con.execute("INSERT OR REPLACE INTO assistidos VALUES (?,?,?,?,?,?)",
                          (r["processo_execucao"], r["nome"], r["data_geracao_rspe"], r["arquivo"], agora, dados))
            b.con.execute("INSERT OR REPLACE INTO rspe_historico VALUES (?,?,?,?,?)",
                          (r["processo_execucao"], r["data_geracao_rspe"], r["arquivo"], agora, dados))
        f = c.get("ficha")
        if f:
            f = dict(f)
            f.setdefault("versao_leitura", 0)  # releitura pelos eventos (rspe_ficha.atualizar)
            b.con.execute("INSERT OR REPLACE INTO fichas VALUES (?,?,?,?,?,?)",
                          (c["processo"], c["processo"], _norm(f.get("nome", "")), f.get("data_impressao", ""), agora, json.dumps(f, ensure_ascii=False)))
        for campo, valor in (c.get("manuais") or {}).items():
            b.con.execute("INSERT OR REPLACE INTO dados_manuais VALUES (?,?,?,?)", (c["processo"], campo, valor, "2026-10-12T10:00:00"))
    b.con.commit()
    b.fechar()
    return destino


def _txt(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def comparar(op, real, v):
    t = _txt(real)
    if op == "eq":
        return real == v or t == _txt(v)
    if op == "contem":
        return all(x.lower() in t.lower() for x in (v if isinstance(v, list) else [v]))
    if op == "nao_contem":
        return all(x.lower() not in t.lower() for x in (v if isinstance(v, list) else [v]))
    if op == "regex":
        return re.search(v, t, re.I | re.S) is not None
    if op == "vazio":
        return not real
    if op == "nao_vazio":
        return bool(real)
    if op == "em":
        return real in v or t in v
    raise ValueError(op)


def conferir(j, ch):
    t = ch["t"]
    if t == "campo":
        real = j.get(ch["campo"])
        return comparar(ch["op"], real, ch["v"]), real
    if t == "presc":
        L = (j.get("presc_linhas") or [])
        if ch["i"] >= len(L):
            return False, "sem linha %d (%d linhas)" % (ch["i"], len(L))
        real = L[ch["i"]].get(ch["campo"])
        return comparar(ch["op"], real, ch["v"]), real
    if t == "aud":
        its = [i for i in (j.get("aud_itens") or []) if i.get("tipo") == ch["tipo"]]
        if ch.get("nivel"):
            its = [i for i in its if i.get("nivel") == ch["nivel"]]
        if ch.get("contem"):
            cs = ch["contem"] if isinstance(ch["contem"], list) else [ch["contem"]]
            its = [i for i in its if all(x.lower() in (i.get("titulo", "") + " " + i.get("detalhe", "")).lower() for x in cs)]
        real = [(i["nivel"], i["titulo"]) for i in its] or [(i["nivel"], i["tipo"], i["titulo"][:120]) for i in (j.get("aud_itens") or [])]
        return (bool(its) == ch["presente"]), real
    raise ValueError(t)


CAMPOS_RESUMO = ("regime", "prog", "prog_sit", "prog_dias", "liv", "liv_sit", "termino", "ext_sit", "ext_termino", "ext_cor", "presc_ppe", "presc_retro",
                 "presc_cor", "i22", "i24", "i25", "c24", "c25", "imp", "falta", "falta_full", "fd_sit", "fd_remidos", "fd_atestar", "fd_estudo",
                 "aud_resumo", "fd_sit_det", "fd_rem_det", "ext_hipoteses", "estado_exec", "parada_rot", "cumprimento", "frac_prog", "frac_liv", "dbase", "db")


def main():
    args = sys.argv[1:]
    arq = next((a for a in args if a.endswith(".json")), os.path.join(AQUI, "casos.json"))
    vazia = "--vazia" in args or not BASE_REAL
    so = None
    if "--so" in args:
        so = set(args[args.index("--so") + 1].split(","))
    casos = json.load(open(arq, encoding="utf-8"))
    if so:
        casos = [c for c in casos if c["id"] in so]
    caminho = preparar(casos, vazia)
    tmp = tempfile.mkdtemp()
    app.pasta_app = lambda: tmp
    app.CONFIG = os.path.join(tmp, "c.json")
    app._abrir = lambda c: None
    api = app.Api()
    api._js = lambda *a: None
    api.abrir_base(caminho)
    api.listar()
    todos = {m.get("id"): m for m in (api._modelos or []) + (getattr(api, "_ocultos", None) or [])}
    visiveis = {m.get("id") for m in (api._modelos or [])}
    saida, nf, nt = [], 0, 0
    for c in casos:
        m = todos.get(c["processo"])
        res = {"id": c["id"], "grupo": c["grupo"], "titulo": c["titulo"], "conta": c["conta"], "processo": c["processo"],
               "na_lista": c["processo"] in visiveis, "checks": []}
        if m is None:
            res["erro"] = "registro não montado"
            saida.append(res)
            nf += 1
            continue
        j = api._json_de(m)
        if c.get("acoes"):
            # ações da tela depois de abrir a base (ex.: "+ Adicionar atestado" = Api.fd_adicionar), como o clique faz
            for a in c["acoes"]:
                getattr(api, a["metodo"])(*a["args"])
            rr = api.registro(c["processo"])
            j = (rr.get("parcial") or [None])[0] or api._json_de(next(x for x in (api._modelos or []) + (api._ocultos or []) if x.get("id") == c["processo"]))
        for ch in c["checks"]:
            try:
                okk, real = conferir(j, ch)
            except Exception as e:
                okk, real = False, "exceção: %r" % e
            nt += 1
            nf += 0 if (okk or ch.get("decisao")) else 1
            res["checks"].append(dict(ch, ok=okk, real=real if not okk else None))
        res["resumo"] = {k: j.get(k) for k in CAMPOS_RESUMO}
        res["aud"] = [(i["nivel"], i["tipo"], i["titulo"]) for i in j.get("aud_itens") or []]
        res["presc"] = [{k: L.get(k) for k in ("crime", "pena", "prazo_ppe", "ppe_termo", "ppe_status", "ppe_previsao", "prazo_ppp", "retro_status", "art115", "reinc")}
                        for L in j.get("presc_linhas") or []]
        saida.append(res)
    json.dump(saida, open(os.path.join(tmp, "resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    linhas = []
    for r in saida:
        falhas = [x for x in r.get("checks", []) if not x["ok"]]
        fe = [x for x in falhas if not x.get("decisao")]
        st = "ERRO-MONTAGEM" if r.get("erro") else ("OK" if not falhas else ("FALHA %d/%d" % (len(fe), len(r["checks"])) if fe else "DIVERGE (decisão jurídica)"))
        linhas.append("%s [%s] %s - %s" % (r["id"], r["grupo"], r["titulo"], st))
        for x in falhas:
            linhas.append("    %s %s %s %s %s -> real: %s" % ("d" if x.get("decisao") else "x", x.get("campo") or x.get("tipo") or x.get("i"), x["op"] if "op" in x else ("presente" if x.get("presente") else "ausente"),
                                                         _txt(x.get("v") or x.get("contem")), ("(%s)" % x["nota"]) if x.get("nota") else "", _txt(x["real"])[:600]))
    open(os.path.join(tmp, "resumo.txt"), "w", encoding="utf-8").write("\n".join(linhas) + "\n\n%d verificações, %d falhas\n" % (nt, nf))
    print("\n".join(linhas))
    print("\n%d casos, %d verificações, %d falhas" % (len(saida), nt, nf))
    return nf


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
