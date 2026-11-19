"""SEEU fictício: páginas do processo de execução no visual do SEEU (capa, abas e detalhe do processo criminal), geradas a
partir de um registro no formato do RSPE (os casos simulados). Serve ao protótipo do painel, aos testes do leitor das abas
(rspe_seeu_abas) e ao teste de ponta a ponta da extensão. Nenhum dado real.

O VISUAL segue as capturas de tela oficiais do SEEU (TJSP, "Informações do processo de execução criminal - SEEU MP e DPE",
atualizado em 20/02/2026; "Mesa de trabalho - Promotor/Defensor", 20/02/2026): barra azul-escura com a marca, barra de menu
clara, capa com o número (vermelho se preso), dados do sentenciado e o gráfico da pena cumprida, pendências, botões de
atividade e as abas em duas linhas. A MARCAÇÃO HTML é uma suposição (as capturas não mostram o código da página): rótulo e
valor em linhas de tabela, tabelas com cabeçalho. O leitor das abas procura pelo TEXTO dos rótulos e dos cabeçalhos, não
pela marcação; ainda assim, só a página real confirma - conferir com o HTML salvo do SEEU antes do uso."""
import html
import re

ESC = html.escape
ABAS = [("tabInformacoesGerais", "Informações Gerais"), ("tabInformacoesAdicionais", "Informações Adicionais"),
        ("tabMedidasDiversas", "Medidas Diversas da Prisão"), ("tabPartes", "Partes"), ("tabMovimentacoesProcesso", "Movimentações"),
        ("tabProcessosCriminais", "Processos Criminais"), ("tabEventos", "Eventos"), ("tabIncidentesConcedidos", "Incidentes Concedidos"),
        ("tabIncidentesNaoConcedidos", "Incidentes Não-Concedidos"), ("tabIncidentesPendentes", "Incidentes Pendentes"),
        ("tabMandados", "Mandados/Alvarás de Soltura-Ocorrências"), ("tabBNMP3", "BNMP3")]
URL_ABA = "/seeu/visualizacaoProcesso.do?actionType=visualizar&selectedIcon=%s"
URL_CRIM = "/seeu/processo/criminal/processoCriminal.do?actionType=visualizar&idProcessoCriminal=%d"

CSS = """
body{margin:0;background:#f0f0f0;font:12px/1.35 "Segoe UI",Verdana,Arial,sans-serif;color:#333}
a{color:#1a5fa8;text-decoration:none}
.topo{background:#1c3a5e;color:#fff;height:44px;display:flex;align-items:center;padding:0 14px;gap:14px}
.marca{display:flex;align-items:center;gap:6px;font:600 22px/1 Arial,sans-serif;letter-spacing:-.5px}
.marca i{width:22px;height:22px;border:3px solid #fff;border-radius:50%;display:inline-block;position:relative}
.marca i:after{content:"";position:absolute;inset:4px;border:2px solid #fff;border-radius:50%}
.cnj{font:700 18px/1 Arial,sans-serif;opacity:.65;border-left:1px solid rgba(255,255,255,.3);padding-left:12px}
.teste{background:#e05252;color:#fff;border-radius:12px;padding:3px 12px;font-weight:600;font-size:11.5px}
.orgao{margin:0 auto;background:#3b5f8a;border-radius:6px;padding:6px 16px;font-size:12px;min-width:280px;text-align:center}
.icones{display:flex;gap:16px;opacity:.9}.icones span{width:16px;height:16px;border:2px solid #fff;border-radius:50%;display:inline-block}
.usuario{font-size:12.5px}
.menu{background:#4a77a8;color:#fff;height:22px;display:flex;align-items:center;gap:14px;padding:0 14px;font-size:11.5px;font-weight:600}
.conteudo{padding:14px 18px}
.capa{background:#f7f7f7;border:1px solid #ddd;padding:10px 14px 6px;position:relative}
.capa h3{margin:0;font:600 16px Arial,sans-serif;color:#1c3a5e}.capa h3 .num{color:#d40000}.capa h3 .num.solto{color:#1a8a2e}
.tram{font-size:11px;color:#666;font-weight:600;margin-bottom:10px;border-bottom:1px solid #ddd;padding-bottom:8px}
table.form{border-collapse:collapse}table.form td{padding:2px 4px;vertical-align:top}
table.form td.r{color:#7a7a8c;text-align:right;white-space:nowrap;padding-right:4px}
table.form td.r b{color:#333}
.grafico{position:absolute;right:40px;top:60px;text-align:center;width:130px}
.grafico .tot{font:600 15px Arial;color:#1c3a5e;margin-top:6px}.grafico .lin{font-size:11.5px;color:#666;text-align:right}
.grafico .lin b{color:#1f8fa0}.grafico .lin.rest b{color:#555}
.sec{font:700 11.5px Arial;color:#777;text-transform:uppercase;margin:14px 0 6px}
.prio{border-left:4px solid #d40000;color:#d40000;font-weight:700;padding-left:8px;margin-left:220px}
.botoes{display:flex;justify-content:flex-end;gap:2px;margin:10px 0 14px}
.botoes span{background:#4a90d9;color:#fff;padding:6px 16px;font-size:12px}
.botoes span:first-child{border-radius:14px 0 0 14px}.botoes span.v{background:#8f7f9a;border-radius:0 14px 14px 0}
.abas{display:flex;flex-wrap:wrap;gap:0 2px;padding-left:28px}
.abas a{background:#e6e6e6;border:1px solid #c8c8c8;border-bottom:0;color:#444;padding:7px 14px 6px;font-size:11.5px;border-radius:3px 3px 0 0;margin-top:2px}
.abas a.on{background:#1c3a5e;color:#fff;font-weight:700}
.corpo-aba{background:#f5f5f5;border:1px solid #1c3a5e;border-top-width:2px;padding:14px 18px;min-height:240px}
.calc h4{font:700 12px Arial;color:#1c3a5e;margin:12px 0 4px;border-bottom:1px dotted #bbb;padding-bottom:2px;display:flex;justify-content:space-between}
.calc h4 a{font-weight:400}
.titulo-calc{font-weight:700;color:#1c3a5e;border-bottom:1px solid #ddd;padding-bottom:3px}
table.grade{border-collapse:collapse;width:100%;background:#fff;font-size:11.5px}
table.grade th{background:#dde3ea;color:#333;padding:7px 6px;border:1px solid #fff}
table.grade td{padding:7px 6px;text-align:center;border-bottom:1px solid #e3e3e3}
table.grade tr:nth-child(even) td{background:#f2f4f6}
table.grade tr.detalhe td{text-align:left;color:#555;background:#fafafa;font-size:11px}
.contagem{border-left:3px solid #999;padding-left:8px;color:#667;font-weight:700;margin:4px 0 12px}
.arvore div{padding:2px 0}.arvore .n1{padding-left:18px}.arvore .n2{padding-left:36px}.arvore .n3{padding-left:54px}
.rodape-aba{display:flex;justify-content:flex-end;gap:2px;margin-top:14px}
.rodape-aba span{background:#5a7fa8;color:#fff;border-radius:10px;padding:3px 10px;font-size:11px}
h2.det{font:700 14px Arial;color:#1c3a5e;margin:8px 0;border-bottom:1px solid #ccc}
h3.det{font:700 13px Arial;color:#1c3a5e;margin:14px 0 4px;border-bottom:1px dotted #ccc}
"""


def _dias(p):
    m = re.match(r"(\d+)a(\d+)m(\d+)d", str(p or "").replace(" ", ""))
    return int(m.group(1)) * 365 + int(m.group(2)) * 30 + int(m.group(3)) if m else None


def _linhas(pares):
    return '<table class="form">' + "".join('<tr><td class="r">%s:</td><td>%s</td></tr>' % (ESC(k), ESC(str(v or ""))) for k, v in pares) + "</table>"


def _preso(r):
    reg = (r.get("regime_atual") or "").lower()
    return ("fechado" in reg or "semiaberto" in reg) and "ATIVO" in (r.get("status_execucao") or "ATIVO").upper()


def capa(r):
    t, c = _dias(r.get("pena_total")), _dias(r.get("pena_cumprida"))
    pct = max(0, min(100, round(c * 100 / t))) if t and c is not None else 0
    rjic = "(RJI: %s; CPF: %s; RG: %s);" % ("0000000000", r.get("cpf") or "Não Cadastrado", r.get("rg") or "Não Cadastrado")
    dados = [("Número Antigo", r.get("numero_antigo") or ""), ("Juízo", r.get("vara") or ""),
             ("Sentenciado", "%s %s" % (r.get("nome") or "", rjic)), ("Nome da Mãe", r.get("nome_mae") or ""),
             ("Advogados/Defensoria", "Defensoria Pública (Promovido)"), ("Status BNMP", ""), ("Último Local Prisão SISDEPEN", ""),
             ("Classe Processual", "386 - Execução da Pena"), ("Assunto Principal", "7791 - Pena Privativa de Liberdade"),
             ("Nível de Sigilo", "Público"), ("Sumário da Pena", "Clique no campo para detalhamento")]
    return f"""<div class="capa" id="capaProcesso">
<h3>Execução <span class="num{'' if _preso(r) else ' solto'}" id="numeroProcesso">{ESC(r.get('processo_execucao') or '')}</span></h3>
<input type="hidden" id="processoNumeroFormatado" value="{ESC(r.get('processo_execucao') or '')}">
<div class="tram">2190 dia(s) em tramitação</div>
{_linhas(dados)}
<div class="grafico" id="graficoPena"><svg width="96" height="96" viewBox="0 0 36 36" role="img" aria-label="{pct}% cumprida">
<circle cx="18" cy="18" r="15.9" fill="none" stroke="#dcdcdc" stroke-width="3.4"/>
<circle cx="18" cy="18" r="15.9" fill="none" stroke="#1f8fa0" stroke-width="3.4" stroke-dasharray="{pct} 100" transform="rotate(-90 18 18)"/>
<text x="18" y="19" text-anchor="middle" font-size="8" font-weight="700" fill="#1f8fa0">{pct}%</text>
<text x="18" y="24" text-anchor="middle" font-size="2.4" fill="#1f8fa0">CUMPRIDA</text></svg>
<div class="tot" id="penaTotal">{ESC(r.get('pena_total') or '')}</div>
<div class="lin">Cumprida: <b id="penaCumprida">{ESC(r.get('pena_cumprida') or '')}</b></div>
<div class="lin rest">Restante: <b id="penaRestante">{ESC(r.get('pena_remanescente') or '')}</b></div></div>
<div class="sec">Prioridades e condições de acompanhamento</div><div class="prio"{'' if _preso(r) else ' style="border-color:#1a8a2e;color:#1a8a2e"'}>{'Réu Preso' if _preso(r) else 'Réu Solto'}</div>
<div class="sec">Pendências</div><div style="padding-left:150px;color:#7a7a8c">Juntadas a realizar : <a>Juntar MANIFESTAÇÃO referente ao movimento - PROFERIDO DESPACHO DE MERO EXPEDIENTE</a></div>
</div>
<div class="botoes"><span>Novo Lembrete</span><span>Autuar Recurso de Agravo</span><span>Petição Eletrônica</span><span>Situação Carcerária</span><span>Navegar</span><span>Exportar ▼</span><span class="v">Voltar</span></div>"""


def _contagens(r):
    inc = r.get("_incidentes") or []
    return {"tabProcessosCriminais": len({c.get("processo_criminal") for c in r.get("_crimes") or []}), "tabEventos": len(r.get("_eventos") or []),
            "tabIncidentesConcedidos": sum(1 for i in inc if i.get("situacao") == "CONCEDIDO"), "tabMedidasDiversas": 0, "tabMandados": 0}


def abas(r, ativa):
    n = _contagens(r)
    out = []
    for i, (id_, rot) in enumerate(ABAS):
        txt = rot + (" (%d)" % n[id_] if id_ in n else "")
        out.append('<a id="%s" href="%s" class="%s">%s</a>' % (id_, URL_ABA % id_, "on" if id_ == ativa else "", ESC(txt)))
    return '<div class="abas" id="abasProcesso">' + "".join(out) + "</div>"


def _formula(prev, frac):
    return "%s" % (prev or "")


def aba_conteudo(r, aba):
    if aba == "tabInformacoesGerais":
        return _linhas([("Comarca/Subseção", "%s - %s" % (r.get("tribunal") or "TJMS", r.get("comarca") or "")), ("Autuação", "05/10/2020 às 00:00:00"),
                        ("Situação", "ARQUIVADO" if "ARQUIV" in (r.get("status_execucao") or "").upper() else "PROCESSO DISTRIBUÍDO"), ("Competência", "Vara de Execução Penal"), ("Juízo", r.get("vara") or ""),
                        ("Juiz", "Juiz Exemplo (Juiz de Direito)"), ("Extinto", "Não" if "ATIVO" in (r.get("status_execucao") or "ATIVO").upper() else "Sim")])
    if aba == "tabInformacoesAdicionais":
        # sem data prevista, o SEEU mostra a observação entre parênteses (como no RSPE: "(Em regime aberto deferido em ...)")
        prog = r.get("progressao_previsao_seeu") or ("(%s)" % r["progressao_obs_seeu"] if r.get("progressao_obs_seeu") else "")
        liv = r.get("livramento_previsao_seeu") or ("(%s)" % r["livramento_obs_seeu"] if r.get("livramento_obs_seeu") else "")
        fp = r.get("fracao_progressao_aplicada") or ""
        fl = r.get("fracao_livramento_aplicada") or ""
        return (_linhas([("Regime Atual", r.get("regime_atual") or ""), ("Situação Carcerária", "Preso" if _preso(r) else "Solto")]) +
                '<div class="calc"><div class="titulo-calc">Cálculo dos Requisitos Temporais <a>Atualizar Cálculo</a></div>'
                '<h4>Progressão de Regime <a>Cálculo Manual/Automático</a></h4>' +
                _linhas([("Data Base", r.get("data_base_seeu") or ""), ("Fração", fp), ("Data do Requisito Temporal", prog)]) +
                '<h4>Livramento Condicional <a>Cálculo Manual/Automático</a></h4>' +
                _linhas([("Data Base", r.get("livramento_data_base_seeu") or ""), ("Fração", fl), ("Data do Requisito Temporal", liv)]) +
                '<h4>Término de Pena <a>Cálculo Manual/Automático</a></h4>' +
                _linhas([("Total de Interrupção", r.get("total_interrupcoes") or ""), ("Saldo dias Remidos", r.get("saldo_remidos") or ""),
                         ("Data do Requisito Temporal", r.get("termino_previsao_seeu") or "")]) +
                '<h4>Linha do Tempo/Indulto e Comutação</h4><h4>Linha do Tempo Detalhada</h4></div>'
                '<div class="rodape-aba"><span>Situação Carcerária</span><span>Atestado de Pena</span><span>Linha do Tempo</span></div>')
    if aba == "tabPartes":
        return _linhas([("Sentenciado", r.get("nome") or ""), ("CPF", r.get("cpf") or ""), ("RG", r.get("rg") or ""),
                        ("Data de Nascimento", r.get("data_nascimento") or ""), ("Nome da Mãe", r.get("nome_mae") or ""),
                        ("Defensoria Pública", "Defensoria Pública do Estado (Promovido)")])
    if aba == "tabProcessosCriminais":
        procs = []
        for c in r.get("_crimes") or []:
            if c.get("processo_criminal") not in procs:
                procs.append(c.get("processo_criminal"))
        h = ['<div class="arvore"><div>[Abrir Tudo] [Fechar Tudo]</div><div>Processo de Execução Penal</div>']
        for k, p in enumerate(procs, 1):
            cs = [c for c in r["_crimes"] if c.get("processo_criminal") == p]
            sit = cs[0].get("processo_situacao") or ""
            h.append('<div class="n1"><a href="%s">Processo Criminal %s</a>%s</div>' % (URL_CRIM % k, ESC(p or ""), (" (%s)" % ESC(sit)) if sit else ""))
            h.append('<div class="n2">%s - PRINCIPAL - ATIVA</div>' % ESC((cs[0].get("pena_total_processo") or "").split(" - ")[0]))
            for c in cs:
                h.append('<div class="n3">%s - %s</div>' % (ESC(c.get("pena_imposta") or ""), ESC(c.get("artigo") or "")))
        return "".join(h) + "</div>"
    if aba == "tabEventos":
        linhas = []
        for k, e in enumerate(r.get("_eventos") or [], 1):
            linhas.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>Físico</td><td>ATIVO</td></tr>" % (
                26588000 + k, ESC(e.get("tipo") or ""), ESC(e.get("motivo") or ""), ESC(e.get("data") or e.get("data_referencia") or "")))
            linhas.append('<tr class="detalhe"><td></td><td colspan="5">Complemento: %s · Data da Decisão: %s · Processos Selecionados: %s</td></tr>' % (
                ESC(e.get("complemento") or ""), ESC(e.get("data_decisao") or ""), ESC(e.get("processos") or "")))
        return _grade(len(r.get("_eventos") or []), ["Nº do Incidente", "Tipo do Incidente", "Complemento", "Data de Referência", "Eletrônico/Físico", "Situação"], linhas)
    sits = {"tabIncidentesConcedidos": "CONCEDIDO", "tabIncidentesNaoConcedidos": "NÃO CONCEDIDO", "tabIncidentesPendentes": "PENDENTE"}
    if aba in sits:
        inc = [i for i in r.get("_incidentes") or [] if i.get("situacao") == sits[aba]]
        linhas = []
        for k, i in enumerate(inc, 1):
            linhas.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>05/10/2020</td><td></td><td>%s</td><td>Juiz Exemplo</td><td>ATIVO</td></tr>" % (
                26621000 + k, ESC(i.get("tipo") or ""), ESC(i.get("complemento") or ""), ESC(i.get("data_referencia") or ""), ESC(i.get("data_decisao") or "")))
            linhas.append('<tr class="detalhe"><td></td><td colspan="8">Motivo: %s · Data: %s · Processos Selecionados: %s</td></tr>' % (
                ESC(i.get("motivo") or ""), ESC(i.get("data") or ""), ESC(i.get("processos") or "")))
        return _grade(len(inc), ["Nº do Incidente", "Tipo do Incidente", "Complemento", "Data de Referência", "Data de Autuação", "Petição",
                                 "Data de Decisão", "Juiz", "Situação"], linhas)
    return '<p style="color:#777">Nenhum registro encontrado.</p>'


def _grade(n, cab, linhas):
    return ('<div class="contagem">%d registro(s) encontrado(s), exibindo de 1 até %d</div><table class="grade"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (n, n, "".join("<th>%s</th>" % ESC(c) for c in cab), "".join(linhas)))


def processo_criminal(r, k):
    """Página do processo criminal (hiperlink do número na aba Processos Criminais): dados gerais, sentença, penas e, uma linha
    por artigo, o que o cálculo usa (lei, artigo, pena, data da infração, violência, reincidência, frações)."""
    procs = []
    for c in r.get("_crimes") or []:
        if c.get("processo_criminal") not in procs:
            procs.append(c.get("processo_criminal"))
    p = procs[k - 1]
    cs = [c for c in r["_crimes"] if c.get("processo_criminal") == p]
    c0 = cs[0]
    art = []
    for c in cs:
        art.append("<tr>%s</tr>" % "".join("<td>%s</td>" % ESC(str(c.get(x) or "")) for x in (
            "lei", "artigo", "tipo_penal", "pena_imposta", "data_infracao", "vga", "resultado_morte", "reincidente_comum", "reincidente_especifico",
            "comando_orcrim", "fracao_progressao", "fracao_livramento", "extinto_rspe" if "extinto_rspe" in c else "extinto", "suspenso", "data_extincao")))
    return ('<h2 class="det">Processo Criminal</h2>' +
            '<h3 class="det">Dados Gerais</h3>' + _linhas([("Definitiva ou Provisória", "Definitiva"), ("Tipo de Processo Criminal", c0.get("tipo_processo") or ""),
                                                        ("Número Único", "%s%s" % (p or "", (" (%s)" % c0["processo_situacao"]) if c0.get("processo_situacao") else "")),
                                                        ("Vara de Origem", c0.get("vara_condenacao") or ""),
                                                        ("Data de Recebimento da Denuncia", c0.get("data_denuncia") or "")]) +
            '<h3 class="det">Sentença 1º Grau</h3>' + _linhas([("Data da Sentença", c0.get("data_sentenca") or ""),
                                                             ("Data de Trânsito em Julgado do Ministério Público", c0.get("transito_mp") or ""),
                                                             ("Data de Trânsito Julgado do Processo", c0.get("transito_processo") or "")]) +
            '<h3 class="det">Penas</h3>' + _grade(1, ["Pena Imposta", "Regime de Pena", "Concedido"],
                                                  ["<tr><td>%s</td><td>%s</td><td>Sim</td></tr>" % (ESC(c0.get("pena_total_processo") or ""), ESC(c0.get("regime_sentenca") or ""))]) +
            '<h3 class="det">Artigos Incursos</h3>' + _grade(len(cs), ["Lei", "Artigo", "Tipo Penal", "Pena Imposta", "Data da Infração", "Violência ou Grave Ameaça",
                                                                      "Resultado Morte", "Reincidente Comum", "Reincidente Específico",
                                                                      "Comando de Organização Criminosa", "Fração Progressão", "Fração Livramento",
                                                                      "Extinto", "Suspensão da Pena", "Data da Extinção"], art))


def pagina(r, aba="tabInformacoesAdicionais", corpo=None):
    """Página inteira do processo, como o navegador a recebe (capa + abas + a aba pedida)."""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>SEEU - Sistema Eletrônico de Execução Unificado</title><style>{CSS}</style></head>
<body><div class="topo"><span class="marca"><i></i>seeu</span><span class="cnj">CNJ</span><span class="teste">Atenção! Você está em um ambiente de testes.</span>
<span class="orgao">{ESC(r.get('tribunal') or 'TJMS')} - Defensoria Pública (fictício) ▾</span><span class="icones"><span></span><span></span><span></span><span></span></span><span class="usuario">Defensor Exemplo</span></div>
<div class="menu"><span>⌕</span><span>Início</span><span>Processos</span><span>Audiências</span><span>Outros</span></div>
<div class="conteudo">{capa(r)}{abas(r, aba)}<div class="corpo-aba" id="{aba}Conteudo">{corpo if corpo is not None else aba_conteudo(r, aba)}</div></div></body></html>"""


def abas_dict(r):
    """As páginas no formato que o leitor das abas recebe da extensão: {"capa", "gerais", "adicionais", ..., "crim:1", ...}."""
    chave = {"tabInformacoesGerais": "gerais", "tabInformacoesAdicionais": "adicionais", "tabPartes": "partes", "tabProcessosCriminais": "criminais",
             "tabEventos": "eventos", "tabIncidentesConcedidos": "concedidos", "tabIncidentesNaoConcedidos": "nao_concedidos",
             "tabIncidentesPendentes": "pendentes"}
    out = {"capa": pagina(r, "tabInformacoesAdicionais")}
    for id_, k in chave.items():
        out[k] = pagina(r, id_)
    procs = []
    for c in r.get("_crimes") or []:
        if c.get("processo_criminal") not in procs:
            procs.append(c.get("processo_criminal"))
    for k in range(1, len(procs) + 1):
        out["crim:%d" % k] = pagina(r, "tabProcessosCriminais", processo_criminal(r, k))
    return out


def paginas(r):
    """Todas as páginas que o leitor busca, por endereço (o que o SEEU devolveria a cada pedido)."""
    out = {URL_ABA % id_: pagina(r, id_) for id_, _ in ABAS}
    procs = []
    for c in r.get("_crimes") or []:
        if c.get("processo_criminal") not in procs:
            procs.append(c.get("processo_criminal"))
    for k in range(1, len(procs) + 1):
        out[URL_CRIM % k] = pagina(r, "tabProcessosCriminais", processo_criminal(r, k))
    return out
