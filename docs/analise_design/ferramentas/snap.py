"""Fotografia do estilo calculado do APTO (dados fictícios): para cada cena, cada elemento (e ::before/::after) com as
propriedades visuais e a caixa (x, y, largura, altura). Usada na consolidação do CSS da 7.18.0: cada etapa tinha de dar
a mesma fotografia (ou só as diferenças pretendidas).
Uso: python snap.py <base.sqlite> <saida.json> [cena...]   (base fictícia: python monta_base.py <base.sqlite> 1)
Comparar: python snapdiff.py antes.json depois.json"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ponte
base, OUT = sys.argv[1], sys.argv[2]; SO = set(sys.argv[3:])
from playwright.sync_api import sync_playwright
PROPS = ["display","position","top","right","bottom","left","z-index","float","box-sizing","overflow-x","overflow-y","visibility","opacity",
 "color","background-color","background-image","background-position","background-size","background-repeat",
 "border-top-width","border-right-width","border-bottom-width","border-left-width","border-top-style","border-right-style","border-bottom-style","border-left-style",
 "border-top-color","border-right-color","border-bottom-color","border-left-color",
 "border-top-left-radius","border-top-right-radius","border-bottom-right-radius","border-bottom-left-radius",
 "box-shadow","outline-style","outline-width","outline-color","outline-offset",
 "font-family","font-size","font-weight","font-style","font-variant-numeric","line-height","letter-spacing","text-transform","text-align","text-decoration-line","text-overflow","white-space","word-break","overflow-wrap","vertical-align",
 "padding-top","padding-right","padding-bottom","padding-left","margin-top","margin-right","margin-bottom","margin-left",
 "width","height","min-width","max-width","min-height","max-height",
 "flex-direction","flex-wrap","flex-grow","flex-shrink","flex-basis","justify-content","align-items","align-self","order","row-gap","column-gap",
 "grid-template-columns","grid-template-rows","grid-column-start","grid-column-end",
 "cursor","pointer-events","user-select","transform","transition-property","transition-duration","transition-timing-function","animation-name","animation-duration",
 "fill","stroke","stroke-width","list-style-type","table-layout","border-collapse","content","-webkit-line-clamp","filter","backdrop-filter","object-fit","resize","caret-color","accent-color"]
JS = r"""(PROPS)=>{ const out={}; const all=document.querySelectorAll('body *');
  const path=e=>{ const p=[]; while(e&&e!==document.body){ const par=e.parentElement; const i=par?[...par.children].indexOf(e):0; p.push(e.tagName.toLowerCase()+i); e=par; } return p.reverse().join('/'); };
  for(const e of all){ if(e.closest('script,style,#navTip')) continue; const k=path(e); const cs=getComputedStyle(e); const r=e.getBoundingClientRect();
    const v=PROPS.map(p=>cs.getPropertyValue(p)); v.push([Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)].join(','));
    v.push((e.getAttribute('class')||'')); out[k]=v.join('\u0001');
    for(const ps of ['::before','::after']){ const c=getComputedStyle(e,ps); if(c.content && c.content!=='none' && c.content!=='normal'){ out[k+ps]=PROPS.map(p=>c.getPropertyValue(p)).join('\u0001'); } } }
  return out; }"""
def cenas():
    clk = lambda sel: "(()=>{const e=document.querySelector(%s); if(e) e.click(); return !!e})()" % json.dumps(sel)
    nth = lambda sel, i: "(()=>{const e=[...document.querySelectorAll(%s)][%d]; if(e) e.click(); return !!e})()" % (json.dumps(sel), i)
    C = []
    for a in ["geral","prog","liv","ind","presc","ext","fd","aud","geo","base","teses","quadro"]: C.append(("aba_"+a, ["ui.irAba('%s')" % a]))
    C += [("presc_pp", ["ui.irAba('presc')", clk("#subtabs button:not(.on)")]),
          ("ind_dec2025", ["ui.irAba('ind')", nth(".dc-side .dc-it", 1)]),
          ("ind_dec2017", ["ui.irAba('ind')", nth(".dc-side .dc-it", 9)]),
          ("teses_monitor", ["ui.irAba('teses')", "ui.tesVer('monitor')"]),
          ("teses_tema", ["ui.irAba('teses')", "ui.tesVer('pesquisa')", nth(".jz-side [onclick]", 3)]),
          ("presc_linha", ["ui.irAba('presc')", "(()=>{const r=[...document.querySelectorAll('#card tbody tr')].find(t=>t.querySelector('td.first')&&!t.classList.contains('grp')); if(r){ (r.querySelector('td')||r).click(); } return !!r})()"]),
          ("aud_linha", ["ui.irAba('aud')", "(()=>{const r=[...document.querySelectorAll('#card tbody tr')].find(t=>/alerta/.test(t.innerText)); if(r) r.querySelector('td').click(); return !!r})()"]),
          ("fd_linha", ["ui.irAba('fd')", "(()=>{const r=[...document.querySelectorAll('#card tbody tr')].find(t=>/Simulado/.test(t.innerText)); if(r) r.querySelector('td').click(); return !!r})()"]),
          ("ficha_135", ["ui.irAba('prog')", "ui.abrir(ui.dados.registros.find(r=>/135/.test(r.nome)).id)"]),
          ("ficha_093", ["ui.irAba('fd')", "ui.abrir(ui.dados.registros.find(r=>/ 093$/.test(r.nome)).id)"]),
          ("ficha_001", ["ui.irAba('ind')", "ui.abrir(ui.dados.registros.find(r=>/ 001$/.test(r.nome)).id)"]),
          ("tl_indulto", ["ui.irAba('ind')", "ui.indTL(ui.dados.registros.find(r=>/ 001$/.test(r.nome)).id)"]),
          ("tl_ext", ["ui.irAba('ext')", clk("#card .mini.dbtn, #card [onclick*='extTL'], #card [onclick*='TL(']")]),
          ("modal_ajuda", ["ui.irAba('prog')", "ui.ajuda()"]),
          ("modal_calc", ["ui.irAba('prog')", "ui.cpAbrir()"]),
          ("modal_relat", ["ui.irAba('prog')", "ui.modalRelatorios()"]),
          ("modal_excel", ["ui.irAba('prog')", "ui.modalExportar('xlsx')"]),
          ("modal_atend", ["ui.irAba('geral')", "ui.atendimentos()"]),
          ("modal_copias", ["ui.irAba('prog')", "ui.modalCopias()"]),
          ("menu_exp", ["ui.irAba('prog')", "ui.menu('mExp')"]),
          ("menu_imp", ["ui.irAba('prog')", "ui.menu('mImp')"]),
          ("combinar", ["ui.irAba('prog')", "(()=>{const b=[...document.querySelectorAll('button')].find(x=>/Combinar filtros/.test(x.innerText)); if(b) b.click(); return !!b})()"]),
          ("busca_vazia", ["ui.irAba('prog')", "document.getElementById('q').value='zzzz';ui.filtrar()"]),
          ("letra_maior", ["ui.irAba('prog')", "ui.letra(1)"]),
          ("menu_recolhido", ["ui.irAba('prog')", "ui.menuAlternar()"]),
          ("qd_cartao", ["ui.irAba('quadro')"]),
         ]
    return C
LIMPA = """(()=>{ try{ document.getElementById('q').value=''; }catch(e){}
  document.querySelectorAll('.modal.on,.mb.on,.menu.on,.pop.on').forEach(m=>m.classList.remove('on'));
  try{ ui.fecharDrawer(); }catch(e){} try{ if(ui._letra) {} }catch(e){} })()"""
ATRIB = json.load(open(os.environ["ATRIB"])) if os.environ.get("ATRIB") else None   # {"cenas": {cena: [caminhos]}, "sels": [seletor...]}
JS_AT = r"""([paths, sels])=>{ const byPath=p=>{ let e=document.body; for(const seg of p.split('/')){ const m=seg.match(/^([a-z0-9-]+?)(\d+)$/); if(!e||!m) return null; e=e.children[+m[2]]; } return e; };
  const S=sels.map(s=>s.replace(/::?(before|after|placeholder|selection|-webkit-[a-z-]+)/g,''));
  const out={}; for(const p of paths){ const base=p.replace(/::(before|after)$/,''); const e=byPath(base); if(!e) continue; const hit=[]; S.forEach((s,i)=>{ try{ if(s.trim()&&e.matches(s)) hit.push(i); }catch(x){} }); out[p]=hit; } return out; }"""
VISTOS = json.load(open(os.environ["VISTOS"])) if os.environ.get("VISTOS") else None   # [seletor...]: quais aparecem em alguma cena
JS_V = r"""(sels)=>sels.map(s=>{ const t=s.replace(/::?(before|after|placeholder|selection|-webkit-[a-z-]+)/g,''); if(/:(hover|focus|active|focus-visible|focus-within|checked|disabled)/.test(t)) return false; try{ return !!document.querySelector(t||'*'); }catch(e){ return false; } })"""
if VISTOS is not None: ATRIB = {"cenas": {}, "sels": []}
res = {}; t0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    def pagina(api, jan, w=1440, h=860):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="pt-BR")
        pg = ctx.new_page(); pg.on("dialog", lambda d: d.dismiss())
        pg.add_init_script("try{localStorage.clear()}catch(e){}")
        ponte.abrir(pg, api, jan); return ctx, pg
    # sem base: tela inicial
    if (not SO or "inicial" in SO) and (VISTOS is not None or ATRIB is None or "inicial" in ATRIB["cenas"]):
        api0, jan0 = ponte.criar(None); ctx, pg = pagina(api0, jan0)
        pg.wait_for_function("document.querySelector('.welcome.on')", timeout=60000); pg.wait_for_timeout(900)
        res["inicial"] = pg.evaluate(JS_V, VISTOS) if VISTOS is not None else (pg.evaluate(JS_AT, [ATRIB["cenas"]["inicial"], ATRIB["sels"]]) if ATRIB is not None else pg.evaluate(JS, PROPS)); ctx.close()
    api, jan = ponte.criar(base)
    for (w, h, suf) in [(1440, 860, ""), (1366, 728, "@1366")]:
        ctx, pg = pagina(api, jan, w, h)
        pg.wait_for_function("document.querySelector('tbody tr')", timeout=180000); pg.wait_for_timeout(900)
        for nome, passos in cenas():
            if suf and nome not in ("aba_prog", "aba_ind", "ind_dec2025", "aba_fd", "aba_ext", "ficha_135", "aba_base", "aba_quadro"): continue
            if SO and nome + suf not in SO: continue
            pg.evaluate(LIMPA); pg.evaluate("ui.irAba('geral')"); pg.wait_for_timeout(250)
            for s in passos:
                try: pg.evaluate(s)
                except Exception as e: print("passo falhou", nome, str(e)[:120])
                pg.wait_for_timeout(700)
            pg.wait_for_timeout(600)
            pg.evaluate("document.getElementById('toast')&&document.getElementById('toast').classList.remove('on')"); pg.wait_for_timeout(300)
            if VISTOS is not None: res[nome + suf] = pg.evaluate(JS_V, VISTOS)
            elif ATRIB is not None:
                if nome + suf in ATRIB["cenas"]: res[nome + suf] = pg.evaluate(JS_AT, [ATRIB["cenas"][nome + suf], ATRIB["sels"]])
            else: res[nome + suf] = pg.evaluate(JS, PROPS)
            if nome == "letra_maior": pg.evaluate("ui.letra(-1)"); pg.wait_for_timeout(300)
            if nome == "menu_recolhido": pg.evaluate("ui.menuAlternar()"); pg.wait_for_timeout(300)
        ctx.close()
    b.close()
json.dump(res, open(OUT, "w"), ensure_ascii=False)
print("cenas", len(res), "elementos", sum(len(v) for v in res.values()), "%.0fs" % (time.time() - t0))
