"""Telas SEEU (Mesa do Defensor) e SEI no APTO (7.21), no navegador (node + Playwright, se houver), com dados fictícios: o SEI vem
da base do gabinete de verdade (documentos fictícios lidos pelas regras do NUSPEN); a triagem do SEEU, no formato que a extensão
envia. Confere contadores que filtram, prazo com forma e texto, ligação com a base aberta, validar/rejeitar e enviar ao Quadro.
Rodar: python teste_ui_sei_seeu.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
node = shutil.which("node")
if not node:
    print("ok: (sem node: teste das telas SEEU e SEI não executado)")
    sys.exit(0)
import rspe_gabinete as rgab  # noqa: E402
import rspe_sei as rsei  # noqa: E402

tmp = tempfile.mkdtemp()
g = rgab.Gabinete(os.path.join(tmp, "g.sqlite"))
s = rsei.Sei(g)
ses = s.iniciar("todos")["sessao"]
docs = {"70": "DESPACHO\nTrata-se de inspeção fictícia. Determino a expedição de ofício à direção do EPMF, com prazo de 30(trinta) dias para resposta.",
        "71": "OFÍCIO Nº 9000002/99/000123/2026 - NUSPEN (FICTÍCIO)\nÀ Direção do EPMF.\nSolicita-se: (1) quantidade de pessoas custodiadas; (2) condições de alimentação.\nFica estipulado prazo de 15(quinze) dias para a resposta."}
s.receber_lote(ses, [{"tipo": "processo", "id_sei": "7", "numero": "99/000123/2026", "especificacao": "Inspeção fictícia no EPMF", "unidade": "NUSPEN"}] +
               [{"tipo": "documento", "id_sei": k, "processo": "99/000123/2026", "titulo": "Despacho" if k == "70" else "Ofício", "versao": "v1", "conteudo": v, "hash": rsei.sha(v)}
                for k, v in docs.items()] +
               [{"tipo": "processo", "id_sei": "8", "numero": "99/000124/2026", "especificacao": "Outro processo fictício", "unidade": "NUSPEN"}])
resumo = s.resumo()
resumo["leitura"] = {"aberto": True, "andamento": {"fase": "concluida", "processos": 2, "novos": 2, "modificados": 0, "falhas": 0, "quando": 0}}
proc = {p["numero"]: s.processo(p["numero"]) for p in resumo["processos"]}
g.fechar()
br = lambda d: d.strftime("%d/%m/%Y")
hoje = date.today()
triagem = {"quando": 1763460000000, "situacao": 2, "situacaoNome": "Lidas e aguardando análise", "recebida": "2026-11-18 10:00:00", "linhas": [
    {"processo": "7000117-54.2016.8.12.0001", "executado": "FULANO DE TAL FICTICIO", "defensor": "Defensor Fictício", "aba": "Manifestação", "situacao": 2,
     "ultimoDia": br(hoje + timedelta(days=1)), "prazo": "10 dias", "dataEnvio": br(hoje - timedelta(days=9)), "url": "https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do?_tj=x",
     "classe": "Execução da Pena", "assunto": "", "final": "0001",
     "analise": {"status": "ok", "quando": 1, "pendencia": {"texto": "Manifestação sobre o cálculo", "juntar": ""}, "motivo": {"nome": "Despacho", "seq": "160", "data": "01/11/2026", "resumo": "Diga a defesa sobre o cálculo."},
                 "decisao": {"nome": "Decisão", "seq": "158", "data": "20/10/2026", "resumo": "Homologo o cálculo."}, "mesma": False,
                 "providencia": {"texto": "Impugnar o cálculo (data-base)", "tipo": "Manifestação", "urgente": True}, "alertas": [{"txt": "data-base divergente", "nivel": "alto"}], "temas": []}},
    {"processo": "7000999-11.2020.8.12.0001", "executado": "BELTRANA FICTICIA", "defensor": "Outra Defensora", "aba": "Ciência", "situacao": 2,
     "ultimoDia": br(hoje + timedelta(days=12)), "prazo": "5 dias", "dataEnvio": br(hoje - timedelta(days=2)), "url": "", "classe": "Execução da Pena", "assunto": "", "final": "0001", "analise": None}]}
import rspe_seeu as rseeu  # noqa: E402
g2 = rgab.Gabinete(os.path.join(tmp, "g2.sqlite"))
se = rseeu.Seeu(g2)
se.receber(dict(triagem, abas=["Manifestação", "Ciência"]))
triagem = {k: v for k, v in triagem.items() if k != "linhas"}
triagem.update(itens=se.listar(), pecas=rseeu.PECAS, leitura={"aberto": True, "andamento": None})
g2.fechar()
fx = os.path.join(tmp, "fixture.json")
json.dump({"resumo": resumo, "processos": proc, "triagem": triagem}, open(fx, "w", encoding="utf-8"), ensure_ascii=False)
r = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_ui_sei_seeu.js"), fx], capture_output=True, text=True, timeout=300)
print((r.stdout or r.stderr).strip())
sys.exit(r.returncode)
