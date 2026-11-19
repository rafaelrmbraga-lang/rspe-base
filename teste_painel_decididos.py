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
# indulto do decreto cuja comutação já foi concedida: pena comutada - fora das pendências, em "não cabe"
m2 = dict(m, i25="Verificar", i25_txt="A verificar · art. 9º, XII, XIII", c25="Concedido", c25_txt="Concedido · 23/09/2026")
o2 = rp.montar(r, m2, h)
assert not any(a["id"] == "i25" for a in o2["alertas"]) and any("comutação do mesmo decreto já foi concedida em 23/09/2026" in x["motivo"] for x in o2["nao_cabe"]), o2["nao_cabe"]
# a hipótese mais provável (e só ela) no cartão do indulto; a lista inteira fica na conta
assert rp._hipotese_provavel(["✔ Inciso I: pena ≤ 8 anos sem VGA, exige 1/5 (cumprido 1a de 6a).", "? Inciso XII: estudo. Depende de dado que o RSPE não traz."]) \
    == "inciso I (pena ≤ 8 anos sem VGA, exige 1/5)"
assert rp._hipotese_provavel(["? Inciso XII: pena ≤ 12 anos - estudo. Depende de dado que o RSPE não traz.", "? Inciso VII: regime aberto, cumprido 1/5"]) \
    == "inciso VII (regime aberto, cumprido 1/5), a verificar"
assert rp._hipotese_provavel(["Decreto 12.790/2025 · data de referência 25/12/2025."]) == ""
# medidas que valem hoje: condições do regime atual (o do RSPE), nada de encerrada
assert not rp._medida_vigente({"titulo": "Condições De Cumprimento Do Regime Semiaberto", "status": "ATIVA"}, "aberto")
assert rp._medida_vigente({"titulo": "Condições De Cumprimento Do Regime Aberto", "status": "ATIVA"}, "aberto")
assert not rp._medida_vigente({"titulo": "Substituição De Pena Privativa Por Restritiva De Direito", "status": "FINALIZADA"}, "aberto (nao iniciado)")
# fração com a data de vigência impressa pelo SEEU ("até 24/03/2026") ou com o número da lei: a data não é fração (era 24/3 = 800%)
from fractions import Fraction  # noqa: E402
assert rs.parse_fracao("20% - Art.112, III, da LEP até 24/03/2026") == Fraction(1, 5)
assert rs.parse_fracao("40% - Art.112, V, da LEP até 24/03/2026") == Fraction(2, 5)
assert rs.parse_fracao("Art. 112, § 3º, Lei 13.769/2018 (1/8)") == Fraction(1, 8) and rs.parse_fracao("1/6 - Comum") == Fraction(1, 6)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False)
print('ok: painel - decidido no SEEU não alerta, não alcançado afastado, aviso de cadastro recolhido, recálculo da progressão num cartão só, ANPP sem alerta de condenação, indulto de decreto já comutado, hipótese mais provável, medidas vigentes, fração com data de vigência')
