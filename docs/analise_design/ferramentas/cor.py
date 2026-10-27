import itertools, math
def rgb(h): h=h.lstrip('#'); return [int(h[i:i+2],16)/255 for i in (0,2,4)]
def lin(c): return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def L(h): r,g,b=[lin(x) for x in rgb(h)]; return 0.2126*r+0.7152*g+0.0722*b
def cr(a,b): la,lb=sorted([L(a),L(b)],reverse=True); return (la+0.05)/(lb+0.05)
# Machado 2009, severidade 1.0
M={'protan':[[0.152286,1.052583,-0.204868],[0.114503,0.786281,0.099216],[-0.003882,-0.048116,1.051998]],
   'deutan':[[0.367322,0.860646,-0.227968],[0.280085,0.672501,0.047413],[-0.011820,0.042940,0.968881]],
   'tritan':[[1.255528,-0.076749,-0.178779],[-0.078411,0.930809,0.147602],[0.004733,0.691367,0.303900]]}
def sim(h,t):
    c=[lin(x) for x in rgb(h)]
    o=[max(0,min(1,sum(M[t][i][j]*c[j] for j in range(3)))) for i in range(3)]
    return o
def lab(c):
    X=0.4124*c[0]+0.3576*c[1]+0.1805*c[2]; Y=0.2126*c[0]+0.7152*c[1]+0.0722*c[2]; Z=0.0193*c[0]+0.1192*c[1]+0.9505*c[2]
    f=lambda t: t**(1/3) if t>0.008856 else 7.787*t+16/116
    fx,fy,fz=f(X/0.95047),f(Y),f(Z/1.08883); return (116*fy-16,500*(fx-fy),200*(fy-fz))
def dE(a,b): return math.dist(lab(a),lab(b))
tok=dict(bg='#F4F5F5',card='#FFFFFF',tx='#212529',tx2='#4F555A',tx3='#767C82',pri='#1D5A3B',
 r_tx='#A3201D',o_tx='#A85100',a_tx='#7E6200',g_tx='#1D6B37',b_tx='#2E4D6E',c_tx='#5B625E',
 r_bg='#F6E4E3',o_bg='#F7EADB',a_bg='#F5EDDA',g_bg='#E3EFE7',b_bg='#E6ECF2',c_bg='#ECEEEB',
 r_dot='#A3201D',o_dot='#C2620A',a_dot='#B38B00',g_dot='#2B8048',b_dot='#3F658D',c_dot='#9AA0A6')
print('== texto (AA normal 4.5:1)')
for k in ['tx','tx2','tx3','r_tx','o_tx','a_tx','g_tx','b_tx','c_tx','pri']:
    print('%-5s %s  branco %.2f  fundo-tela %.2f' % (k,tok[k],cr(tok[k],'#FFFFFF'),cr(tok[k],tok['bg'])), end='')
    bgk=k[0]+'_bg'
    print('  fundo-próprio %.2f' % cr(tok[k],tok[bgk]) if bgk in tok else '')
print('tx3 sobre linha selecionada pri-soft E7EEE9: %.2f' % cr(tok['tx3'],'#E7EEE9'))
print('cabeçalho #333 sobre #F0F1F2: %.2f' % cr('#333333','#F0F1F2'))
print('ícones de linha #C4CAD4 (fico) sobre branco: %.2f ; #8E958F (pin/cpn): %.2f' % (cr('#C4CAD4','#FFFFFF'),cr('#8E958F','#FFFFFF')))
print('placeholder (Chromium padrão #757575) sobre branco: %.2f' % cr('#757575','#FFFFFF'))
print('== marcas não textuais (WCAG 1.4.11 3:1) sobre branco')
for k in ['r_dot','o_dot','a_dot','g_dot','b_dot','c_dot']: print(k, tok[k], '%.2f'%cr(tok[k],'#FFFFFF'))
print('== selos dos decretos (texto branco 10,5px negrito sobre cor; AA 4.5:1)')
DEC={'cabe':'#2F7A4F','nao':'#A33A36','imp':'#8E2424','conc':'#5B7C9C','indef':'#6B5B8A','ver':'#B5651D','ped':'#1F2622'}
for k,v in DEC.items(): print(k, v, '%.2f'%cr('#FFFFFF',v))
print('== distinguibilidade (ΔE CIE76; <10 = difícil, <5 = quase igual) entre marcas de situação')
S={'vermelho':tok['r_dot'],'laranja':tok['o_dot'],'ambar':tok['a_dot'],'verde':tok['g_dot'],'azul':tok['b_dot'],'cinza':tok['c_dot']}
for t in [None,'protan','deutan','tritan']:
    pares=[]
    for (a,ha),(b,hb) in itertools.combinations(S.items(),2):
        ca=[lin(x) for x in rgb(ha)] if t is None else sim(ha,t); cb=[lin(x) for x in rgb(hb)] if t is None else sim(hb,t)
        pares.append((dE(ca,cb),a,b))
    pares.sort(); print(t or 'normal', ' | '.join('%s×%s %.0f'%(a,b,d) for d,a,b in pares[:5]))
print('== decretos: não cabe × impeditivo × a verificar')
for t in [None,'protan','deutan']:
    f=lambda h: [lin(x) for x in rgb(h)] if t is None else sim(h,t)
    print(t or 'normal', 'nao×imp %.0f'%dE(f(DEC['nao']),f(DEC['imp'])), 'nao×ver %.0f'%dE(f(DEC['nao']),f(DEC['ver'])), 'cabe×ver %.0f'%dE(f(DEC['cabe']),f(DEC['ver'])), 'cabe×nao %.0f'%dE(f(DEC['cabe']),f(DEC['nao'])))
