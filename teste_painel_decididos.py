"""Painel: decreto já decidido no RSPE (indulto indeferido, comutação concedida) não é ponto a verificar e não aparece; indulto não alcançado vai para as hipóteses afastadas; aviso de cadastro sem efeito para o assistido (pena da ficha
diferente da do RSPE) sai dos alertas e fica nas observações recolhidas. Uso: python teste_painel_decididos.py [saida.json]"""
import json
import os
import re
import sys
import types

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_painel as rp  # noqa: E402
import rspe_scraper as rs  # noqa: E402
import rspe_seeu_abas as ra  # noqa: E402
import rspe_view as rv  # noqa: E402
import seeu  # noqa: E402

c = json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))[34]
t,_=ra.montar_texto(seeu.abas_dict(c['rspe']),'12/10/2026')
p=json.loads(rp.analisar_rspe(json.dumps({'textos':[t],'hoje':'12/10/2026'})))
m,h=rp._ULTIMO[re.sub(r'\D','',p['processo'])]

m=rv.json_seguro({k:v for k,v in m.items() if k!='_bruto'})
m.update(i25='Indeferido',i25_txt='Indeferido · 27/08/2026',c25='Concedido',c25_txt='Concedido · 27/08/2026',
         i22='Não alcançado',i22_txt='Não alcançado · sentença posterior à publicação · fato posterior segue')
m['aud_itens']=list(m.get('aud_itens') or [])+[{'nivel':'verificar','titulo':'Pena na ficha (13a2m13d) difere da pena total do RSPE (9a2m10d)','detalhe':'A unidade trabalha com outra pena.','fundamento':'LEP'}]
r=rs.extrair_paginas([t],'x')
out=rp.montar(r,m,h)
al=[a['titulo'] for a in out['alertas']]
assert not any(re.match(r'(Indulto|Comutação) 2025|Indulto 2022',x) for x in al), al
assert 'decididos' not in out and not any(re.match(r'(Indulto|Comutação) 2025', x['titulo']) for x in out['confere'] + out['nao_cabe'])
assert any('Indulto 2022' in x['titulo'] for x in out['nao_cabe'])
assert [o['titulo'][:13] for o in out['observacoes']]==['Pena na ficha'], out['observacoes']
assert not any(x.startswith('Pena na ficha') for x in al)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False)
print('ok: painel - decidido no SEEU não alerta, não alcançado afastado, aviso de cadastro recolhido')
