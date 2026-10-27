"""Roteiro de capturas da janela principal (dados fictícios). Uso: python roteiro.py <etapa> [base]
Etapas: abas, ficha, modais, estados, tamanhos, grande"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ponte
S = os.environ.get("APTO_TRABALHO", os.path.join(__import__("tempfile").gettempdir(), "apto_analise"))
REPO = ponte.REPO
CAP = os.path.join(REPO, "docs", "analise_design", "capturas")
os.makedirs(CAP, exist_ok=True)
os.makedirs(S, exist_ok=True)
etapa = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else S + "/bases/Comarca_Ficticia.sqlite"
api, jan = ponte.criar(None if etapa == "vazia" else base)
from playwright.sync_api import sync_playwright

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); LOG.append(s); print(s, flush=True)


def nova(p, w=1440, h=860, dsf=1):
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, locale="pt-BR")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: log("pageerror:", e))
    t = time.time()
    ponte.abrir(pg, api, jan)
    pg.wait_for_function("document.querySelector('tbody tr') || document.querySelector('.welcome.on')", timeout=120000)
    pg.wait_for_timeout(600)
    log("carregou em %.1fs" % (time.time() - t))
    return b, pg


def shot(pg, nome, full=False):
    pg.evaluate("document.getElementById('toast').classList.remove('on')")
    pg.wait_for_timeout(250)
    pg.screenshot(path=os.path.join(CAP, nome + ".png"), full_page=full)
    log("captura", nome)


def abas(pg):
    return pg.evaluate("ui.dados.abas.concat(ui.ABAS_EXTRA).map(a=>a.id)")


with sync_playwright() as p:
    if etapa == "abas":
        b, pg = nova(p)
        for a in abas(pg):
            pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(1500)
            shot(pg, "app_aba_%s_1440" % a)
    elif etapa == "tamanhos":
        # 1440x860 (janela padrão), 1100x600 (mínimo), 1920x1080; escala do Windows: 125% e 150% numa tela 1920x1080
        # => área útil em px CSS ~1536x816 (125%) e ~1280x680 (150%), descontada a barra de tarefas
        for (w, h, dsf, nome) in [(1100, 600, 1, "1100x600"), (1920, 1080, 1, "1920x1080"), (1536, 816, 1.25, "escala125_1536x816"), (1280, 680, 1.5, "escala150_1280x680"), (1366, 728, 1, "notebook_1366x728")]:
            b, pg = nova(p, w, h, dsf)
            pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(1200)
            shot(pg, "app_prog_%s" % nome)
            m = pg.evaluate("""()=>{const t=document.getElementById('tabs');const r=t.getBoundingClientRect();const c=document.getElementById('card').getBoundingClientRect();
              const tabs=[...t.children].map(x=>x.getBoundingClientRect().top); const linhas=new Set(tabs.map(Math.round)).size;
              return {abas_linhas:linhas, tabela_altura:Math.round(c.height), tabela_topo:Math.round(c.top), janela:innerHeight, rolagem_h:document.querySelector('.card').scrollWidth>document.querySelector('.card').clientWidth}}""")
            log(nome, json.dumps(m))
            b.close()
    elif etapa == "vazia":
        b, pg = nova(p)
        shot(pg, "app_tela_inicial_sem_base")
    elif etapa == "grande":
        b, pg = nova(p)
        n = pg.evaluate("ui.dados.registros.length"); log("registros", n)
        for a in ["geral", "prog", "ind", "presc"]:
            t = time.time(); pg.evaluate("id=>ui.irAba(id)", a); pg.wait_for_timeout(50)
            ms = pg.evaluate("()=>{const t=performance.now(); ui.render(); return performance.now()-t}")
            log("aba", a, "render ms %.0f" % ms, "linhas", pg.evaluate("document.querySelectorAll('tbody tr').length"), "nós DOM", pg.evaluate("document.getElementsByTagName('*').length"))
        ms = pg.evaluate("()=>{const t=performance.now(); document.getElementById('q').value='simulado caso 1'; ui.filtrar(); return performance.now()-t}")
        log("busca ms %.0f" % ms)
        pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(800)
        shot(pg, "app_base_grande_720_prog")

    elif etapa == "ficha":
        b, pg = nova(p)
        ids = pg.evaluate("ui.dados.registros.map(r=>r.id)")
        # S001 (prescrição aparente), S006 (indulto/decretos), um com ficha disciplinar
        pg.evaluate("ui.irAba('geral')")
        pg.evaluate("id=>ui.abrir(id)", ids[0]); pg.wait_for_timeout(2500)
        shot(pg, "app_ficha_assistido_topo")
        dh = pg.evaluate("document.querySelector('#drawer .db') ? document.querySelector('#drawer .db').scrollHeight : 0"); log("altura da ficha px", dh)
        for i, y in enumerate([900, 1800, 2700, 3600]):
            if y > dh: break
            pg.evaluate("y=>document.querySelector('#drawer .db').scrollTo(0,y)", y); pg.wait_for_timeout(300)
            shot(pg, "app_ficha_assistido_rolagem%d" % (i + 1))
        secs = pg.evaluate("[...document.querySelectorAll('#drawer .sec h3')].map(h=>h.textContent.trim())"); log("seções da ficha", json.dumps(secs, ensure_ascii=False))
        pg.evaluate("ui.fecharDrawer()"); pg.wait_for_timeout(400)
        # linha expandida da prescrição + linha do tempo
        pg.evaluate("ui.irAba('presc')"); pg.wait_for_timeout(800)
        pg.evaluate("id=>ui.expandir(id)", ids[0]); pg.wait_for_timeout(2000)
        shot(pg, "app_presc_linha_expandida")
        pg.evaluate("document.querySelector('tr.sub') && document.querySelector('tr.sub').scrollIntoView()"); pg.wait_for_timeout(400)
        shot(pg, "app_presc_linha_do_tempo")
        # progressão: só vencidos
        pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(600)
        pg.evaluate("ui.filtrarCor('vencido')"); pg.wait_for_timeout(600)
        shot(pg, "app_prog_filtro_vencido")
        r = pg.evaluate("ui.visiveis().filter(r=>ui.passaFiltro? true:true).length"); log("visiveis", r)
        # pedido feito
        fid = pg.evaluate("(document.querySelector('tbody tr.vencido, tbody tr.vermelho')||{}).dataset ? null : null")
        pg.evaluate("id=>ui.pedidoAbrir(id,'prog')", ids[5]); pg.wait_for_timeout(600)
        shot(pg, "app_modal_pedido_feito")
        pg.evaluate("ui.fecharModal()")
        # indulto: linha do tempo de um decreto
        pg.evaluate("ui.irAba('ind')"); pg.wait_for_timeout(800)
        pg.evaluate("id=>ui.indTL(id)", ids[5]); pg.wait_for_timeout(3000)
        shot(pg, "app_indulto_linha_do_tempo")
        pg.evaluate("document.querySelector('.tlv-body') && document.querySelector('.tlv-body').scrollTo(0,800)"); pg.wait_for_timeout(300)
        shot(pg, "app_indulto_linha_do_tempo_2")
        pg.evaluate("ui.fecharTLV && ui.fecharTLV()"); pg.wait_for_timeout(300)
        pg.evaluate("ui.irDec('2024')"); pg.wait_for_timeout(800)
        shot(pg, "app_indulto_decreto_2024")
        # auditoria expandida
        pg.evaluate("ui.irAba('aud')"); pg.wait_for_timeout(600)
        pg.evaluate("id=>ui.expandir(id)", ids[0]); pg.wait_for_timeout(1500)
        shot(pg, "app_auditoria_expandida")
        # ficha disciplinar com ficha
        fd = pg.evaluate("ui.dados.registros.filter(r=>r.fd_cor&&r.fd_cor!=='cinza').map(r=>r.id).slice(0,3)"); log("com ficha", fd)
        pg.evaluate("ui.irAba('fd')"); pg.wait_for_timeout(600)
        if fd:
            pg.evaluate("id=>ui.expandir(id)", fd[0]); pg.wait_for_timeout(1500)
            pg.evaluate("document.querySelector('tr.sub') && document.querySelector('tr.sub').scrollIntoView()"); pg.wait_for_timeout(300)
            shot(pg, "app_fd_expandida")
    elif etapa == "modais":
        b, pg = nova(p)
        for nome, js in [("ajuda", "ui.ajuda()"), ("exportar_excel", "ui.modalExportar('xlsx')"), ("relatorios_pdf", "ui.modalRelatorios()"),
                         ("copias", "ui.modalCopias()"), ("menu_base", "ui.menu('mBase')"), ("menu_exportar", "ui.menu('mExp')"),
                         ("calculadora", "ui.cpAbrir()"), ("atendimentos", "ui.atendimentos()"), ("pasta_vigiada", "ui.modalVigia()")]:
            try:
                pg.evaluate("()=>{try{%s}catch(e){console.log(e)}}" % js); pg.wait_for_timeout(1500)
                shot(pg, "app_modal_" + nome)
            except Exception as e:
                log("falhou", nome, e)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            pg.evaluate("ui.fecharModal&&ui.fecharModal(); document.querySelectorAll('.menu.on').forEach(m=>m.classList.remove('on')); const c=document.getElementById('calcWin'); if(c) c.remove()")
            pg.wait_for_timeout(300)
    elif etapa == "estados":
        b, pg = nova(p)
        # carregando a base
        pg.evaluate("document.getElementById('loadTit').textContent='Abrindo a base Comarca_Ficticia'; ui.carregando('Montando a lista (480 de 720)…'); document.getElementById('loadTempo').textContent='14 s · bases grandes podem levar mais de um minuto'; document.getElementById('loading').classList.add('on')")
        pg.wait_for_timeout(400); shot(pg, "app_estado_carregando_base")
        pg.evaluate("document.getElementById('loading').classList.remove('on')")
        # importação em andamento (300 PDFs)
        pg.evaluate("ui.progresso(137,300)"); pg.wait_for_timeout(300); shot(pg, "app_estado_importando_137_de_300")
        # resumo da importação com falhas
        av = ["SIMULADO_%03d.pdf: não parece um RSPE do SEEU (sem o cabeçalho 'Relatório da Situação Processual Executória')" % i for i in range(1, 6)]
        av += ["SIMULADO_%03d.pdf: ficha de SIMULADO CASO %03d - leitura parcial: sem a tabela de faltas" % (i, i) for i in range(10, 16)]
        av += ["SIMULADO_%03d.pdf: duplicado (mesmo processo e mesma data de geração)" % i for i in range(20, 32)]
        res = {"novos": 241, "atualizados": 31, "duplicados": 12, "historico": 4, "antigos": 4, "erros": 5, "fichas": 6, "incompletos": 3, "avisos": av}
        pg.evaluate("r=>ui.importado(r)", res); pg.wait_for_timeout(1200); shot(pg, "app_estado_importacao_concluida")
        pg.evaluate("ui.fecharModal()")
        # busca sem resultado
        pg.fill("#q", "zzzz inexistente"); pg.evaluate("ui.filtrar()"); pg.wait_for_timeout(600); shot(pg, "app_estado_busca_vazia")
        pg.fill("#q", ""); pg.evaluate("ui.filtrar()")
        # erro (toast)
        pg.evaluate("ui.toast('Base aberta só para consulta: nada foi gravado.')"); pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(CAP, "app_estado_erro_toast.png")); log("captura app_estado_erro_toast")
        # confirmação nativa: conta e mostra os textos dos confirm()
        # acessibilidade: o que recebe foco pelo Tab
        pg.evaluate("ui.irAba('prog')"); pg.wait_for_timeout(600)
        foc = []
        pg.mouse.click(5, 400)
        for i in range(25):
            pg.keyboard.press("Tab")
            foc.append(pg.evaluate("()=>{const e=document.activeElement; const cs=getComputedStyle(e); return (e.tagName+'.'+e.className+' '+(e.textContent||e.placeholder||'').trim().slice(0,30)+' | outline='+cs.outlineStyle+' '+cs.outlineWidth+' shadow='+(cs.boxShadow!=='none'))}"))
        log("ordem do Tab:\n  " + "\n  ".join(foc))
        pg.screenshot(path=os.path.join(CAP, "app_teclado_foco.png")); log("captura app_teclado_foco")
        a11y = pg.evaluate("""()=>{const q=s=>[...document.querySelectorAll(s)];
          const clic=q('[onclick]').filter(e=>!['BUTTON','A','INPUT','SELECT'].includes(e.tagName)&&!e.hasAttribute('tabindex'));
          const tipos={}; clic.forEach(e=>{const k=e.tagName+'.'+(e.className||'').toString().split(' ')[0]; tipos[k]=(tipos[k]||0)+1});
          const semNome=q('button').filter(b=>!(b.textContent.trim()||b.getAttribute('aria-label')||b.title));
          const soTitle=q('button').filter(b=>!b.textContent.trim()&&!b.getAttribute('aria-label')&&b.title);
          const inputs=q('input,select,textarea').filter(i=>!i.labels?.length&&!i.getAttribute('aria-label')&&!i.title);
          const peq=q('button,[onclick],input[type=checkbox]').filter(e=>{const r=e.getBoundingClientRect(); return r.width>0&&(r.width<24||r.height<24)});
          return {clicaveis_sem_teclado:clic.length, por_tipo:tipos, botoes_sem_nome:semNome.length, botoes_icone_so_title:soTitle.length, campos_sem_rotulo:inputs.length, alvos_menores_24px:peq.length, tr_clicavel_tabindex:q('tbody tr').filter(t=>t.tabIndex>=0).length, total_tr:q('tbody tr').length, aria:q('[aria-label],[aria-live],[role]').length}}""")
        log("a11y", json.dumps(a11y, ensure_ascii=False))
        # zoom do próprio app (botão A+)
        for k in range(3): pg.evaluate("ui.letra(1)")
        pg.wait_for_timeout(500); shot(pg, "app_letra_maior_3x")
    b.close()
open(S + "/log_%s.txt" % etapa, "w").write("\n".join(LOG))
