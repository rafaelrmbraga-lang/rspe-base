import sys, os, ponte
S = "/tmp/claude-0/-home-user-rspe-base/883108c0-aece-5660-92ba-781fc4fe86e8/scratchpad"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); W, H = map(int, sys.argv[2].split("x"))
api, jan = ponte.criar(S + "/bases2/Comarca_Ficticia.sqlite")
from playwright.sync_api import sync_playwright
erros = []
E = [
 ("importando", "ui.irAba('geral'); ui.progresso(137,300,2)"),
 ("resumo", "document.getElementById('impCard')&&document.getElementById('impCard').remove(); ui.modalAvisos('272 novos · 5 falhas', ['SIMULADO_001.pdf: não parece um RSPE do SEEU nem uma Ficha Disciplinar do SIAPEN','SIMULADO_002.pdf: idem','SIMULADO_050.pdf: SIMULADO CASO 050 - não foi possível ler a data-base'], false, {novos:241,atualizados:31,erros:2,erros_txt:['SIMULADO_001.pdf: não parece um RSPE do SEEU nem uma Ficha Disciplinar do SIAPEN','SIMULADO_002.pdf: idem'],incompletos:3,parciais:6,duplicados:12,antigos:4,sem_data:0})"),
 ("aviso_ok", "ui.fecharModal(); ui.irAba('prog'); ui.toast('Pedido registrado.',{desfazer:()=>{}})"),
 ("aviso_erro", "ui.toast('Base aberta só para consulta: nada foi gravado.')"),
 ("legenda", "ui.toastFechar(); ui.irAba('prog'); ui.ajuda()"),
 ("vazio", "ui.fecharModal(); document.getElementById('q').value='zzzz inexistente'; ui.filtrar()"),
 ("filtros", "ui.limparBusca(); ui.irAba('prog'); ui.fMarcar('vencidas',true); ui.fMarcar('pedsem',true); ui._fpOpen=true; ui.render()"),
 ("importar_menu", "ui.fLimpar(); ui._fpOpen=false; ui.render(); ui.menu('mImp')"),
 ("menu_trocado", "document.getElementById('mImp').classList.remove('on'); ui.menuAlternar()"),
]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg = b.new_page(viewport={"width": W, "height": H})
    pg.on("pageerror", lambda e: erros.append(str(e)))
    ponte.abrir(pg, api, jan); pg.wait_for_function("document.querySelector('tbody tr')", timeout=120000); pg.wait_for_timeout(600)
    pg.evaluate("try{localStorage.removeItem('apto_menu')}catch(e){}; ui.render()")
    for n, js in E:
        pg.evaluate(js); pg.wait_for_timeout(500); pg.screenshot(path=f"{OUT}/{n}.png")
    pg.evaluate("ui.menuAlternar()")
    b.close()
print("erros JS:", erros[:5])
