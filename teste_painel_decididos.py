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
# os dois avisos que pedem o mesmo recálculo da progressão viram um cartão só, com as duas razões e a base legal sem repetir
from datetime import date  # noqa: E402
mm = {"aud_itens": [{"nivel": "verificar", "tipo": "remicao-preterita-apos-progressao", "titulo": "R", "detalhe": "remição",
                     "fundamento": "LEP, arts. 126, § 8º, e 128; STJ, Tema 1165."},
                    {"nivel": "verificar", "tipo": "semiaberto-referencia-desatualizada", "ref": "07/02/2026", "titulo": "D", "detalhe": "redução",
                     "fundamento": "LEP, arts. 111 e 112; STJ, Tema 1165 (a data da progressão é a do preenchimento dos requisitos)."}]}
rc = [x for x in rp.montar({}, mm, date(2026, 11, 19))["alertas"] if x["id"] == "recalc"]
assert len(rc) == 1 and rc[0]["titulo"] == "Pedir o recálculo da progressão de 07/02/2026: remição e redução da pena lançadas depois dela", rc
assert rc[0]["conta"] == ["1) remição", "2) redução"] and rc[0]["fundamento"].count("Tema 1165") == 1, rc
# medida sem condenação (o assunto principal da capa diz): ANPP não alerta "sem condenação"/"não iniciou", sem marcos, benefícios
# nem hipóteses afastadas; sem a capa, o mesmo RSPE continua apontando a falta de condenação
r0 = dict(c["rspe"], _crimes=[], pena_total="", pena_cumprida="", pena_remanescente="", regime_atual="Aberto (não iniciado)", data_base_seeu="",
          progressao_previsao_seeu="", livramento_previsao_seeu="", termino_previsao_seeu="")
for k in list(r0):
    if k.startswith("_") and isinstance(r0[k], list):
        r0[k] = []
t0, _ = ra.montar_texto(seeu.abas_dict(r0), "12/10/2026")
sem = json.loads(rp.analisar_rspe(json.dumps({"textos": [t0], "hoje": "12/10/2026"})))
assert any(re.search("sem condena", a["titulo"], re.I) for a in sem["alertas"]), sem["alertas"]
anpp = json.loads(rp.analisar_rspe(json.dumps({"textos": [t0], "hoje": "12/10/2026",
                                               "capa": {"classe": "12729 - Execução de Medidas Alternativas no Juízo Comum",
                                                        "assunto": "15056 - Acordo de Não Persecução Penal"}})))
assert anpp["especial"]["tipo"] == "anpp" and anpp["regime"] == "ANPP" and not anpp["alertas"] and not anpp["marcos"] and not anpp["nao_cabe"], anpp
assert anpp["assinatura"] != sem["assinatura"] and anpp["chave"] == sem["chave"]
assert rp.medida_alternativa({"assunto": "Transação Penal"})["tipo"] == "transacao" and rp.medida_alternativa({"assunto": "7791 - Pena Privativa de Liberdade"}) is None
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False)
print('ok: painel - decidido no SEEU não alerta, não alcançado afastado, aviso de cadastro recolhido, recálculo da progressão num cartão só, ANPP sem alerta de condenação')
