"""Gestão do NUSPEN no APTO (7.27), com dados fictícios: as regras do sistema do NUSPEN reescritas sobre a base do gabinete.
Confere: demanda ≠ processo (N:N, com histórico e desvínculo com motivo); providência sugerida pela leitura do SEI validada,
ajustada (texto anterior preservado) ou rejeitada (com justificativa); prazo do documento vira SUGESTÃO, com lacuna do termo
inicial; prazo calculado só com regra APROVADA de dias corridos e termo documentado; dias úteis não calculam; prorrogação
guarda o vencimento anterior; prazo não validado nunca "vence"; comunicação com estado derivado; resposta ≠ cumprimento;
só a avaliação validada muda o cumprimento; inspeção com achados, recorrência só confirmada, providência do achado e
comparação; minuta só de providência validada, com as frases e as fontes, versões só acrescentam; nada se apaga; tudo com
"Quem". Rodar: python teste_nuspen_gestao.py"""
import os
import sys
import tempfile
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rspe_gabinete as rgab  # noqa: E402
import rspe_nuspen as rn  # noqa: E402
import rspe_sei as rsei  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def erro(f, *a, contem=""):
    try:
        f(*a)
    except rn.Erro as e:
        return contem in str(e)
    return False


tmp = tempfile.mkdtemp()
g = rgab.Gabinete(os.path.join(tmp, "g.sqlite"))
s = rsei.Sei(g)
N = rn.Nuspen(g)
Q = "Servidora Fictícia"
ok(N.quem_gravar([Q, "Coordenador Fictício", Q]) == ["Coordenador Fictício", Q], "lista do Quem sem repetição")

# ---- leitura do SEI (fictícia): duas obrigações num ofício, uma num despacho ----
ses = s.iniciar("todos")["sessao"]
of = ("OFÍCIO Nº 1/2026/NUSPEN\nAo Ilmo. Senhor\nFULANO FICTÍCIO\nDiretor do Presídio Fictício\nAssunto: inspeção\nSenhor Diretor,\n"
      "Solicito informações sobre o fornecimento de água, no prazo de 10 (dez) dias.\nAtenciosamente,\nDEFENSOR FICTÍCIO")
desp = "DESPACHO\nTrata-se de inspeção fictícia. Determino a expedição de ofício à direção do EPMF com urgência. Cumpra-se."
s.receber_lote(ses, [{"tipo": "processo", "id_sei": "7", "numero": "99/000123/2026", "especificacao": "Inspeção fictícia"},
                     {"tipo": "documento", "id_sei": "70", "processo": "99/000123/2026", "titulo": "Ofício", "versao": "v1", "conteudo": of, "hash": rsei.sha(of)},
                     {"tipo": "documento", "id_sei": "71", "processo": "99/000123/2026", "titulo": "Despacho", "versao": "v1", "conteudo": desp, "hash": rsei.sha(desp)}])
obr = N.obrigacoes()
ok(len(obr) == 2 and all(o["estado"] == "Identificada" for o in obr), "sugestões da leitura: Identificada: %s" % [(o["descricao"], o["estado"]) for o in obr])
o1 = next(o for o in obr if o["prazo_quantidade"] == 10)
o2 = next(o for o in obr if o["id"] != o1["id"])
ok(o1["prazo"]["rotulo"] == "Prazo não identificado", "antes de validar, nenhum prazo registrado: %s" % o1["prazo"])

# ---- validação humana (ADR-014) ----
ok(erro(N.obrigacao_decidir, o1["id"], "validada", ""), "sem Quem não registra")
ok(erro(N.obrigacao_decidir, o2["id"], "rejeitada", Q, "", contem="justificativa"), "rejeitar exige justificativa")
ok(N.obrigacao_decidir(o1["id"], "validada", Q)["ok"], "validar")
d1 = N.obrigacao(o1["id"])
ok(len(d1["prazos"]) == 1 and d1["prazos"][0]["status"] == "sugestao" and d1["prazos"][0]["natureza"] == "expresso" and d1["prazos"][0]["quantidade"] == 10
   and not d1["prazos"][0]["vencimento"], "prazo do documento vira sugestão expressa, sem vencimento: %s" % d1["prazos"])
ok([l["tipo"] for l in d1["lacunas"]] == ["prazo_sem_termo"], "lacuna: prazo sem termo inicial")
ok(d1["prazo"]["rotulo"].startswith("Prazo sugerido (não validado): 10 dias"), "prazo não validado não vence: %s" % d1["prazo"])
ok(d1["decisoes"][0]["quem"] == Q and d1["estado"] == "Aguardando início", "decisão com Quem; estado Aguardando início: %s" % d1["estado"])
ok(N.obrigacao_decidir(o2["id"], "ajustada", Q, "texto mais claro", "Expedir ofício à direção do EPMF (água)")["ok"], "ajustar")
d2 = N.obrigacao(o2["id"])
ok(d2["descricao"].startswith("Expedir ofício à direção") and d2["valor_original"] and d2["decisoes"][0]["valor_anterior"], "ajuste preserva o texto anterior")
ok(d2["prazos"][0]["natureza"] == "nao_identificado" and [l["tipo"] for l in d2["lacunas"]] == ["prazo_nao_identificado"], "urgência sem número: prazo não identificado + lacuna")

# ---- prazos: regra de contagem só aprovada calcula; dias úteis não; alterações guardam o anterior ----
r_uteis = N.regra_criar({"nome": "Úteis (fictícia)", "dias": "uteis"}, Q)["id"]
r = N.regra_criar({"nome": "Corridos (fictícia)", "dias": "corridos", "fonte_normativa": "decisão fictícia da coordenação"}, Q)["id"]
pid = d1["prazos"][0]["id"]
termo = (date.today() - timedelta(days=15)).isoformat()
ok(erro(N.prazo_registrar, o1["id"], {"natureza": "calculado", "quantidade": 10, "termo_inicial": termo, "fonte_termo": "AR fictício", "regra": r, "fonte": "x"}, Q,
        contem="aprovada"), "regra não aprovada não calcula")
ok(N.prazo_completar(pid, {"termo_inicial": termo, "fonte_termo": "recebimento do ofício (AR fictício)", "regra": r, "origem": "externo", "finalidade": "resposta"}, Q)["ok"],
   "completar o prazo sugerido")
p = N.obrigacao(o1["id"])["prazos"][0]
ok(not p["vencimento"] and p["natureza"] == "expresso", "regra não aprovada: continua sem vencimento: %s" % p["vencimento"])
N.regra_aprovar(r, "Coordenador Fictício")
N.regra_aprovar(r_uteis, "Coordenador Fictício")
N.prazo_completar(pid, {"regra": r}, Q)
d1 = N.obrigacao(o1["id"])
p = d1["prazos"][0]
venc = (date.fromisoformat(termo) + timedelta(days=10)).isoformat()
ok(p["natureza"] == "calculado" and p["vencimento"] == venc, "regra aprovada de dias corridos: vencimento = termo + 10: %s" % p["vencimento"])
ok(not [l for l in d1["lacunas"] if l["aberta"]], "lacuna do termo fechada quando o termo é informado")
ok(d1["prazo"]["rotulo"].startswith("Prazo sugerido"), "ainda não validado: não vence")
ok(erro(N.prazo_registrar, o1["id"], {"natureza": "calculado", "quantidade": 5, "termo_inicial": termo, "fonte_termo": "x", "regra": r_uteis, "fonte": "x"}, Q,
        contem="úteis"), "dias úteis não calculam")
N.prazo_decidir(pid, "validada", Q)
d1 = N.obrigacao(o1["id"])
ok(d1["prazo"]["ordem"] == 0 and "Venceu" in d1["prazo"]["rotulo"] and d1["estado"] == "Aguardando início", "validado e vencido: %s" % d1["prazo"])
novo = (date.today() + timedelta(days=5)).isoformat()
ok(erro(N.prazo_alterar, pid, {"tipo": "prorrogacao", "novo_vencimento": novo, "fonte": "ofício fictício"}, Q, contem="motivo"), "alteração exige motivo")
N.prazo_alterar(pid, {"tipo": "prorrogacao", "novo_vencimento": novo, "motivo": "pedido da unidade", "fonte": "ofício fictício de prorrogação"}, Q)
d1 = N.obrigacao(o1["id"])
ok(d1["prazos"][0]["alteracoes"][0]["vencimento_anterior"] == venc and d1["prazos"][0]["vencimento_efetivo"] == novo and "faltam 5 dias" in d1["prazo"]["rotulo"],
   "prorrogação guarda o anterior e muda o vigente: %s" % d1["prazo"])

# ---- demanda (N:N) ----
did = N.demanda_criar({"assunto": "Água no Presídio Fictício", "tipo": "inspecao", "processos": ["99/000123/2026", "99/000999/2026"]}, Q)["id"]
N.obrigacao_editar(o1["id"], "demanda", did, Q)
N.obrigacao_editar(o2["id"], "demanda", did, Q)
D = N.demanda(did)
ok(D["processos"] == ["99/000123/2026", "99/000999/2026"] and len(D["obrigacoes"]) == 2 and D["providencias"]["validadas"] == 2, "demanda com dois processos e duas providências")
ok(erro(N.demanda_desvincular_processo, did, "99/000999/2026", Q, "", contem="motivo"), "desvincular exige motivo")
N.demanda_desvincular_processo(did, "99/000999/2026", Q, "processo de outra unidade")
ok(N.demanda(did)["processos"] == ["99/000123/2026"], "desvinculado (fica no histórico)")
ok(erro(N.demanda_editar, did, "situacao", "cancelada", Q, contem="justificativa"), "cancelar exige justificativa")
N.demanda_editar(did, "situacao", "em_andamento", Q)
ok([h["campo"] for h in N.demanda(did)["historico"]][:2] == ["Situação", "vínculo com processo"], "histórico da demanda")

# ---- comunicação, resposta ≠ cumprimento ----
cid = N.comunicacao_criar({"assunto": "Ofício fictício sobre a água", "destinatario": "Direção do Presídio Fictício", "obrigacoes": [o1["id"]]}, Q)["id"]
ok(N.obrigacao(o1["id"])["estado"] == "Aguardando envio", "ofício registrado, sem envio: Aguardando envio")
N.comunicacao_envio(cid, date.today().strftime("%d/%m/%Y"), Q)
ok(N.obrigacao(o1["id"])["estado"] == "Aguardando resposta", "enviado: Aguardando resposta")
ok(erro(N.reiterar, 999, "01/01/2026", Q), "reiterar só comunicação existente e enviada")
N.reiterar(cid, date.today().isoformat(), Q)
rid = N.resposta_registrar(cid, date.today().isoformat(), Q)["id"]
d1 = N.obrigacao(o1["id"])
ok(d1["estado"] == "Resposta recebida" and d1["situacao_cumprimento"] == "nao_avaliada", "resposta recebida não é cumprimento")
doc = g._con.execute("SELECT id FROM sei_documentos WHERE id_sei='71'").fetchone()[0]
N.resposta_juntar(rid, doc, Q)
ok(N.obrigacao(o1["id"])["estado"] == "Juntada identificada", "juntada identificada")
ok(erro(N.resposta_juntar, rid, doc, Q, contem="já tem"), "juntada não se sobrescreve")
ar = N.avaliar("resposta", rid, "parcial", "resposta fictícia: só parte das informações", Q)["id"]
ok(N.obrigacao(o1["id"])["situacao_cumprimento"] == "nao_avaliada", "avaliar a resposta não toca o cumprimento")
ac = N.avaliar("obrigacao", o1["id"], "parcial", "vistoria fictícia", Q)["id"]
ok(N.obrigacao(o1["id"])["situacao_cumprimento"] == "nao_avaliada", "avaliação de cumprimento sugerida ainda não vale")
N.avaliacao_decidir(ac, "validada", "Coordenador Fictício")
d1 = N.obrigacao(o1["id"])
ok(d1["situacao_cumprimento"] == "parcial" and d1["estado"] == "Cumprida parcialmente", "avaliação validada muda o cumprimento: %s" % d1["estado"])
ok([e["estado"] for e in d1["etapas"]][:8] == ["feita"] * 8 and d1["etapas"][8]["estado"] == "atual", "nove etapas: %s" % [e["estado"] for e in d1["etapas"]])

# ---- inspeções ----
antiga = N.inspecao_criar({"estabelecimento": "Presídio Fictício", "municipio": "Campo Grande", "data": (date.today() - timedelta(days=200)).isoformat()}, Q)["id"]
nova = N.inspecao_criar({"estabelecimento": "presídio fictício ", "data": date.today().isoformat()}, Q)["id"]
ok(erro(N.inspecao_criar, {"estabelecimento": "X", "data": (date.today() + timedelta(days=1)).isoformat()}, Q, contem="futura"), "inspeção não pode ser futura")
a0 = N.achado_registrar(antiga, {"descricao": "Falta de água fictícia", "categoria": "agua", "gravidade": "alta", "recomendacao": "Regularizar o abastecimento"}, Q)["id"]
N.achado_registrar(antiga, {"descricao": "Celas sem ventilação (fictício)", "categoria": "estrutura"}, Q)
a1 = N.achado_registrar(nova, {"descricao": "Água ainda intermitente (fictício)", "categoria": "agua", "gravidade": "alta",
                               "recomendacao": "Instalar caixa d'água"}, Q)["id"]
N.achado_registrar(nova, {"descricao": "Falta de médico (fictício)", "categoria": "saude"}, Q)
I = N.inspecao(nova)
ach = next(a for a in I["achados"] if a["id"] == a1)
ok([x["id"] for x in ach["recorrencias_sugeridas"]] == [a0] and not ach["anterior"] and I["anterior"] == antiga, "recorrência só SUGERIDA (mesmo estabelecimento, categoria)")
ok(erro(N.recorrencia_confirmar, a0, a1, Q, contem="mais antiga"), "recorrência só para trás")
N.recorrencia_confirmar(a1, a0, Q)
C = N.comparar(antiga, nova)
ok(sorted(x["situacao"] for x in C) == ["nova", "recorrente", "somente_na_anterior"], "comparação das inspeções: %s" % [x["situacao"] for x in C])
pa = N.achado_providencia(a1, {}, Q)["id"]
pd = N.obrigacao(pa)
ok(pd["origem"] == "recomendacao" and pd["achado"] == a1 and pd["descricao"] == "Instalar caixa d'água" and pd["status"] == "validada", "providência do achado")
N.achado_situacao(a1, "persiste", Q, "vistoria fictícia")
ok(N.inspecao(nova)["achados"][0]["situacao"] == "persiste", "acompanhamento do achado")

# ---- minuta ----
ok(erro(N.minuta_gerar, o1["id"] + 1000, "despacho-v1", Q), "providência inexistente")
s2 = s.iniciar("todos")["sessao"]
desp2 = "DESPACHO\nDetermino a elaboração de relatório fictício."
s.receber_lote(s2, [{"tipo": "documento", "id_sei": "72", "processo": "99/000123/2026", "titulo": "Despacho", "versao": "v1", "conteudo": desp2, "hash": rsei.sha(desp2)}])
sug = next(o for o in N.obrigacoes() if o["status"] == "sugestao")
ok(erro(N.minuta_gerar, sug["id"], "despacho-v1", Q, contem="validada"), "minuta só de providência validada")
m = N.minuta_gerar(o1["id"], "despacho-v1", Q)
M = N.minuta(m["minuta"])
v = M["versoes"][0]
blocos = [f["bloco"] for f in v["frases"]]
ok(blocos[0] == "abertura" and "dados" in blocos and "conclusao" in blocos and blocos[-1] == "fecho" and all(f["fonte"] for f in v["frases"]), "minuta com blocos e fontes: %s" % blocos)
ok("parcialmente cumprida" in v["texto_para_sei"] and "Cumpra-se." in v["texto_para_sei"], "texto para o SEI usa só o validado")
f0 = v["frases"][1]
e = N.minuta_editar(v["id"], {f0["id"]: f0["texto"] + " (editado)", v["frases"][2]["id"]: ""}, Q)
M = N.minuta(m["minuta"])
ok(len(M["versoes"]) == 2 and M["versoes"][0]["numero"] == 2 and M["versoes"][0]["frases"][1]["editada"] and len(M["versoes"][0]["frases"]) == len(v["frases"]) - 1,
   "edição cria versão nova (frase em branco sai); a anterior fica")
N.minuta_restaurar(m["minuta"], 1, Q)
ok(len(N.minuta(m["minuta"])["versoes"]) == 3, "restaurar cria versão nova")
cad = N.modelo_cadastrar({"slug": "ofício", "nome": "Ofício (fictício)", "abertura": "Senhor Diretor,", "pedido": "Solicito providências."}, Q)
ok(cad["id"] == "ofcio-v1" and N.modelo_cadastrar({"slug": "ofcio", "nome": "Ofício (fictício)", "abertura": "Prezado,", "pedido": "Solicito."}, Q)["id"] == "ofcio-v2",
   "modelo da instituição versionado: %s" % cad)

# ---- nada se apaga; histórico, painel, relatório, busca ----
ok(erro(N.remover, "demanda", did, Q, "", contem="motivo"), "remoção exige motivo")
N.remover("demanda", did, Q, "duplicada (fictício)")
ok(not N.demandas() and g._con.execute("SELECT removido_por FROM nus_demandas WHERE id=?", (did,)).fetchone()[0] == Q, "remoção lógica: some da lista, fica na base")
H = N.historico_geral({"quem": "Coordenador Fictício"})
ok(H and all(h["quem"] == "Coordenador Fictício" for h in H), "histórico geral por Quem")
P = N.painel()
ok(P["providencias"] == 3 and P["sugestoes"] == 1 and P["por_estado"].get("Cumprida parcialmente") == 1, "painel: %s" % P)
R = N.relatorio()
ok(R["providencias"] == 3 and R["inspecoes"] == 2 and R["achados"] == 4 and R["reiteracoes"] == 1, "relatório de gestão: %s" % {k: R[k] for k in ("providencias", "inspecoes", "achados")})
ok({x["tipo"] for x in N.buscar("agua")} >= {"documento", "obrigacao", "achado"}, "busca sem acento: %s" % {x["tipo"] for x in N.buscar("agua")})
ok(set(rn.PUBLICOS) <= set(dir(N)), "métodos públicos existem: %s" % (set(rn.PUBLICOS) - set(dir(N))))

# ---- importação de PDF (processo baixado do SEI, fictício do NUSPEN): rodapé separa os documentos; mesmo arquivo não duplica ----
PDF = os.path.join(AQUI, "extensao_seeu_testes", "pdfs_nuspen", "processo_t1_ficticio.pdf")
orig = os.path.join(tmp, "originais")
r = s.importar_pdf(PDF, orig, Q)
ok(r["ok"] and r["novo"] and r["paginas"] == 18 and r["documentos"] == 16 and r["processos"] == ["99/000123/2026"], "PDF: 18 páginas, 16 documentos, 1 processo: %s" % r.get("msg"))
ok(any("sem o rodapé" in a for a in r["avisos"]), "trecho sem rodapé avisado")
ok(os.path.exists(os.path.join(orig, rsei.hashlib.sha256(open(PDF, "rb").read()).hexdigest() + ".pdf")), "original guardado com o SHA-256 no nome")
r2 = s.importar_pdf(PDF, orig, Q)
ok(r2["ok"] and not r2["novo"] and "já tinha sido importado" in r2["msg"], "mesmo arquivo: só o recebimento")
docs = s.processo("99/000123/2026")["documentos"]
ok(any("PDF processo_t1_ficticio.pdf, p. 2–3" in d["titulo"] for d in docs), "documento com as páginas do PDF")
ok(erro(lambda: None) is False and s.importar_pdf(__file__, orig, Q).get("erro") == "O arquivo não é um PDF.", "só PDF")
# ---- OCR opcional: sem Tesseract, a página escaneada é avisada; com ele (simulado aqui), o texto vem marcado ----
from nuspen_regras.leitura import PaginaLida  # noqa: E402
pags = [PaginaLida(1, "", "sem_texto"), PaginaLida(2, "texto nativo", "ok")]
s.ocr_exe = lambda: None
ok(s._ocr("x.pdf", pags) == (pags, []), "sem Tesseract: nada muda")
s.ocr_exe = lambda: "tesseract"
s.ocr_pagina = lambda c, n, e: "Determino a expedição de ofício fictício."
pp, lidas = s._ocr("x.pdf", pags)
ok(lidas == [1] and pp[0].texto.startswith("[lido por OCR, confiança baixa]") and pp[1].texto == "texto nativo", "com Tesseract: página escaneada lida e marcada")
s.ocr_exe = type(s).ocr_exe
s.ocr_pagina = type(s).ocr_pagina
# ---- o que mudou nas leituras, novidades desde a visita, encerramento só confirmado ----
M = N.o_que_mudou()
ok(M["total"] > 0 and "Resposta recebida" in M["por_tipo"] and any(e["sugestao"] == "providencia" for e in M["eventos"]), "eventos com sugestão: %s" % M["por_tipo"])
nv = N.novidades(Q)
ok(nv["documentos"] >= 16 and not nv["desde"], "novidades antes da primeira visita: %s" % nv)
N.marcar_visto(Q)
ok(N.o_que_mudou()["total"] == 0 and N.novidades(Q)["documentos"] == 0 and N.novidades("Coordenador Fictício")["documentos"] >= 16, "visto por pessoa")
arq = "DESPACHO\nNada mais havendo, arquive-se o processo."
s3 = s.iniciar("todos")["sessao"]
s.receber_lote(s3, [{"tipo": "documento", "id_sei": "73", "processo": "99/000123/2026", "titulo": "Despacho", "versao": "v1", "conteudo": arq, "hash": rsei.sha(arq)}])
ev = next(e for e in N.o_que_mudou()["eventos"] if e["sugestao"] == "encerramento")
ok(erro(N.evento_encerramento, ev["id"], Q, "", contem="por que"), "encerramento exige motivo")
enc = N.evento_encerramento(ev["id"], Q, "despacho fictício de arquivamento")
ok(enc["encaminhadas"] >= 1 and N.obrigacao(o2["id"])["aguarda_decisao"] == 1 and N.obrigacao(o2["id"])["situacao_cumprimento"] == "nao_avaliada",
   "arquivamento confirmado: providências abertas à coordenação, sem cumprir: %s" % enc)
# ---- perguntas prontas e lote ----
ok(N.consultar("decisao_coordenador")["linhas"] and N.consultar("achados_graves")["linhas"], "perguntas prontas com origem")
ok(N.consultar("respostas_incompletas")["nota"] == "Sem evidência suficiente nos dados registrados.", "sem dado: sem evidência (a avaliação da resposta não foi validada)")
sugs = [o["id"] for o in N.obrigacoes() if o["status"] == "sugestao"]
L = N.em_lote("validar", sugs + [99999], Q)
ok(L["feitos"] == len(sugs) and len(L["erros"]) == 1 and not [o for o in N.obrigacoes() if o["status"] == "sugestao"], "validar em lote, item a item: %s" % L)
# ---- 7.28: Quadro com o vencimento validado; ofício enviado e reiteração na produção do mês; minuta de ofício ----
import time as _tm  # noqa: E402
pq = {"id": "q1", "tipo": "", "processo": "99/000123/2026", "nome": "SEI", "data": date.today().isoformat(), "status": "pendente", "coluna": "fazer",
      "prazo": "", "obs": "", "origem": "sei", "atendimentoId": "", "criadoEm": int(_tm.time() * 1000)}
g.mudar({"pecas": {"upsert": [pq]}})
s.marcar_quadro(o1["id"], "q1")
N.sincronizar_quadro()
ok(next(x for x in g.lista("pecas") if x["id"] == "q1")["prazo"] == novo, "cartão do Quadro com o vencimento validado (prorrogado)")
novo2 = (date.today() + timedelta(days=9)).isoformat()
N.prazo_alterar(pid, {"tipo": "prorrogacao", "novo_vencimento": novo2, "motivo": "nova prorrogação", "fonte": "ofício fictício"}, Q)
N.sincronizar_quadro()
ok(next(x for x in g.lista("pecas") if x["id"] == "q1")["prazo"] == novo2, "o cartão acompanha a prorrogação")
of_ = [x for x in g.lista("pecas") if x.get("tipo") == "OFICIO" and x.get("origem") == "sei"]
ok(len(of_) == 2 and all(x["status"] == "feito" for x in of_), "envio e reiteração contam como Ofícios na produção: %d" % len(of_))
cid2 = N.comunicacao_criar({"assunto": "Outro ofício fictício", "destinatario": "Unidade Fictícia", "data_envio": date.today().isoformat()}, Q)["id"]
ok(len([x for x in g.lista("pecas") if x.get("tipo") == "OFICIO"]) == 3, "ofício já enviado ao registrar: conta")
N.remover("comunicacao", cid2, Q, "registrado em duplicidade (fictício)")
ok(len([x for x in g.lista("pecas") if x.get("tipo") == "OFICIO"]) == 2, "ofício removido sai da produção")
mo = N.minuta(N.minuta_gerar(o1["id"], "oficio-v1", Q)["minuta"])["versoes"][0]
tx = mo["texto_para_sei"]
ok(tx.startswith("A FULANO FICTÍCIO, Diretor do Presídio Fictício,") and "até " in tx and "Atenciosamente." in tx and "conclusao" not in [f["bloco"] for f in mo["frases"]],
   "minuta de ofício: vocativo, prazo validado, sem conclusão: %s" % tx[:160])
mr = N.minuta(N.minuta_gerar(o2["id"], "reiteracao-v1", Q)["minuta"])["versoes"][0]
ok([f["bloco"] for f in mr["frases"]][0] == "abertura" and "pedido" in [f["bloco"] for f in mr["frases"]], "minuta de reiteração")
g.fechar()
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: gestão do NUSPEN no APTO (demandas N:N, validação por tipo com Quem, prazos com regra aprovada e alterações, lacunas, comunicação derivada, "
      "resposta ≠ cumprimento, inspeções com recorrência confirmada, minutas com fontes e versões, nada se apaga, histórico, painel, relatório, busca)")
