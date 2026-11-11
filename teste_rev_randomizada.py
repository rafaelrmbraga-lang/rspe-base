"""Teste de regressão da revisão independente e randomizada das regras (11/2026): rol de hediondos, progressão, livramento,
extinção e indulto. Cada caso reproduz, com dados fictícios, uma causa de erro achada na revisão; a conta e o fundamento estão no
campo "conta". Os casos rodam pela Api da tela (casos_simulados/roda_casos.py), numa base nova, com a data de referência fixa
de 12/10/2026. Rodar: python teste_rev_randomizada.py (sai com código 1 se alguma verificação falhar)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "casos_simulados"))
from base_casos import CP, DROGAS, REG, AUD, C, D, F, anos, caso, crime, ev, inc, interr, prisao, proc_crim, rspe  # noqa: E402

ECA = "8069/90 - Estatuto da Criança e do Adolescente"
L15358 = "15358/26 - Marco Legal do Combate ao Crime Organizado"
FURTO = "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa"
TRAF = "CAPUT: Importar, exportar, remeter, preparar, produzir, fabricar, adquirir, vender drogas, Reclusão: 5 a 15 anos E Multa"
casos = []


def um(k, titulo, conta, crimes, checks, ini, eventos=None, incidentes=None, **kw):
    """Caso de uma execução: prisão em `ini` pelos crimes não extintos, regime inicial fechado."""
    ativos = [c for c in crimes if c.get("extinto") != "Sim"]
    procs = ", ".join(c["processo_criminal"] for c in ativos)
    kw.setdefault("pena", sum(c["_dias"] for c in ativos))
    r = rspe(k, crimes, eventos or [prisao(ini, procs, "PRISÃO DEFINITIVA")], incidentes or [inc(REG, "Fechado - Regime Inicial", "", ini)], ini=ini, **kw)
    casos.append(caso(k, "revisão randomizada", titulo, conta, r, checks))


# ------------------------------------------------------------------ rol de hediondos (Lei 8.072/90, art. 1º)
HED_S, HED_N = '"hediondo": "S"', '"hediondo": "N"'
SEM_ALERTA_HED = [AUD("seeu-tratou-como-hediondo-mas-o-tipo-nao-consta", False), AUD("percentual-de-progressao-diverge", False),
                  AUD("fracao-de-livramento-diverge", False)]
k = 91001
um(k, "CP 122, § 4º (por rede), fato de 2024: hediondo",
   "Lei 8.072/90, art. 1º, X (Lei 14.811/2024, vigência 15/01/2024): induzimento a suicídio ou automutilação por rede de computadores (art. 122, caput e § 4º).",
   [crime(proc_crim(k, 2024), "ART 122: Induzimento, instigação ou auxílio a suicídio ou a automutilação", anos(3), "01/03/2024",
          tipo="§ 4º: A pena é aumentada até o dobro se a conduta é realizada por meio da rede de computadores, de rede social ou transmitida em tempo real",
          fp="40% - Hediondo Primário", fl="2/3 - Hediondo")],
   [C("crimes_det", "contem", HED_S)] + SEM_ALERTA_HED, "05/10/2025", prog="01/01/2028", liv="01/01/2029")
k = 91002
um(k, "CP 122, caput, fato de 2024: não hediondo",
   "Sem o § 4º (rede de computadores), o art. 122 não está no rol.",
   [crime(proc_crim(k, 2024), "ART 122: Induzimento, instigação ou auxílio a suicídio ou a automutilação", anos(1, 6), "01/03/2024",
          tipo="CAPUT: Induzir ou instigar alguém a suicidar-se ou a praticar automutilação, Reclusão: 6 meses a 2 anos", fp="16% - Comum Primário")],
   [C("crimes_det", "contem", HED_N)], "05/10/2025", prog="01/01/2028")
for k, art, tipo in [
        (91003, "ART 241-A: Oferecer, trocar, disponibilizar", "CAPUT: Oferecer, trocar, disponibilizar, transmitir, Reclusão: 4 a 10 anos E Multa"),
        (91004, "ART 240: Produzir, reproduzir", "CAPUT: Produzir, reproduzir, dirigir, fotografar, Reclusão: 4 a 10 anos E Multa"),
        (91005, "ART 241-D: Aliciar, assediar", "CAPUT: Aliciar, assediar, convidar, instigar, Reclusão: 3 a 5 anos E Multa"),
        (91006, "ART 244-A: Submeter criança ou adolescente à exploração sexual", "CAPUT: Submeter criança ou adolescente, Reclusão: 4 a 10 anos E Multa"),
        (91007, "ART 241: Vender ou expor à venda", "CAPUT: Vender ou expor à venda fotografia, vídeo, Reclusão: 4 a 10 anos E Multa")]:
    um(k, "ECA %s, fato de 01/09/2026: hediondo (Lei 15.487/2026)" % art.split(":")[0],
       "Lei 8.072/90, art. 1º, p. ú., VII, na redação da Lei 15.487/2026 (DOU e vigência em 07/08/2026): o SEEU acerta ao tratar como hediondo "
       "(70% e livramento com 2/3) - sem alerta.",
       [crime(proc_crim(k, 2026), art, anos(6), "01/09/2026", sentenca="01/10/2026", transito="03/10/2026", lei=ECA, tipo=tipo,
              fp="70% - Hediondo Primário", fl="2/3 - Hediondo")],
       [C("crimes_det", "contem", HED_S)] + SEM_ALERTA_HED, "02/09/2026", prog="01/01/2031", liv="01/01/2031")
k = 91008
um(k, "ECA 240, caput, fato de 2025: não hediondo (hediondez só desde 07/08/2026)",
   "Antes da Lei 15.487/2026, só o § 1º do art. 240 e o art. 241-B eram hediondos (Lei 14.811/2024): fato anterior não é hediondo (CF, art. 5º, XL).",
   [crime(proc_crim(k, 2025), "ART 240: Produzir, reproduzir", anos(5), "01/09/2025", lei=ECA,
          tipo="CAPUT: Produzir, reproduzir, dirigir, fotografar, Reclusão: 4 a 8 anos E Multa", fp="16% - Comum Primário")],
   [C("crimes_det", "contem", HED_N), AUD("percentual-de-progressao-diverge", False)], "05/10/2025", prog="01/01/2028")
k = 91009
um(k, "ECA 241-B, § 4º (acessar ou visualizar), fato de 2026: não hediondo",
   "O p. ú., VII, refere só o caput do art. 241-B; o § 4º foi criado pela própria Lei 15.487/2026 e ficou fora do rol.",
   [crime(proc_crim(k, 2026), "ART 241-B: Adquirir, possuir ou armazenar", anos(3), "01/09/2026", sentenca="01/10/2026", transito="03/10/2026", lei=ECA,
          tipo="§ 4º: Incorre na mesma pena prevista no caput quem acessar ou visualizar aplicações de internet", fp="1/6 - Comum")],
   [C("crimes_det", "contem", HED_N)], "02/09/2026", prog="01/01/2028")
k = 91010
um(k, "ECA 241-B, caput, fato de 2025: hediondo (Lei 14.811/2024)",
   "O art. 241-B é hediondo desde 15/01/2024: o SEEU acerta (40% e 2/3).",
   [crime(proc_crim(k, 2025), "ART 241-B: Adquirir, possuir ou armazenar", anos(3), "01/09/2025", lei=ECA,
          tipo="CAPUT: Adquirir, possuir ou armazenar, Reclusão: 1 a 4 anos E Multa", fp="40% - Hediondo Primário", fl="2/3 - Hediondo")],
   [C("crimes_det", "contem", HED_S)] + SEM_ALERTA_HED, "05/10/2025", prog="01/01/2028", liv="01/01/2028")

# ------------------------------------------------------------------ progressão
GOLPE = ("ART 359-L: Abolição violenta do Estado Democrático de Direito",
         "CAPUT: Tentar, com emprego de violência ou grave ameaça, abolir o Estado Democrático de Direito, Reclusão: 4 a 8 anos")
k = 91101
um(k, "Título XII do CP, reincidente (anterior sem violência), SEEU 30%: legal 20%",
   "LEP, art. 112, III (Lei 15.402/2026, retroativa): o crime do Título XII ficou fora dos incisos I e II; o reincidente cumpre 20% - não os 25% da "
   "analogia do reincidente não específico em crime violento.",
   [crime(proc_crim(k + 500, 2020), "ART 155: Furto", anos(1), "10/03/2020", sentenca="10/10/2020", transito="10/12/2020", tipo=FURTO, extinto="Sim",
          data_extincao="15/01/2022", regime="Aberto"),
    crime(proc_crim(k, 2022), GOLPE[0], anos(6), "11/02/2022", sentenca="10/09/2022", transito="10/11/2022", tipo=GOLPE[1], vga="S", rc="S", fp="30% - Reincidente")],
   [AUD("percentual-de-progressao-diverge", True, contem="20%", nivel="alerta"), AUD("reincidente-vga-percentual-se-nao-especifica", False)],
   "01/04/2023", prog="19/01/2025")


def _depurada(k, ext_ant, marc, checks, titulo, conta):
    um(k, titulo, conta,
       [crime(proc_crim(k + 500, 2008), "ART 33: Tráfico de drogas", anos(1, 8), "06/06/2008", sentenca="10/12/2008", transito="21/02/2009", lei=DROGAS, tipo=TRAF,
              extinto="Sim", data_extincao=ext_ant, regime="Aberto", fp="2/5 - Hediondo", fl="2/3 - Hediondo"),
        crime(proc_crim(k + 600, 2019), "ART 155: Furto", anos(1), "10/03/2019", sentenca="10/10/2019", transito="10/12/2019", tipo=FURTO, extinto="Sim",
              data_extincao="15/01/2021", regime="Aberto"),
        crime(proc_crim(k, 2022), "ART 33: Tráfico de drogas", anos(6), "10/05/2022", sentenca="10/12/2022", transito="10/02/2023", lei=DROGAS, tipo=TRAF,
              rc="S", re_=marc, fp="60% - Hediondo reincidente", fl="2/3 - Hediondo")],
       checks, "01/04/2023", prog="06/11/2026")


_depurada(91102, "23/03/2010", "N", [AUD("percentual-de-progressao-diverge", True, contem="40%", nivel="alerta"), AUD("percentual-de-progressao-confere", False)],
          "Anterior por tráfico depurada (extinta em 2010, fato de 2022), reincidente por furto: 40%, não 60%",
          "CP, art. 64, I: a condenação de 2008, extinta há mais de 5 anos, não gera reincidência; a reincidência (pelo furto) é genérica: 40% "
          "(STJ, Tema 1084; STF, Tema 1169).")
_depurada(91103, "23/03/2010", "S", [AUD("reincidencia-especifica-confere-com-o-rspe", False), AUD("reincidencia-especifica-nao-demonstrada-no-rspe", True)],
          "O mesmo, marcado reincidente específico: a específica não está demonstrada",
          "A única condenação anterior por crime hediondo ou equiparado está depurada (CP, art. 64, I).")
_depurada(91104, "23/03/2019", "S", [AUD("reincidencia-especifica-confere-com-o-rspe", True), AUD("percentual-de-progressao-diverge", False)],
          "Controle: anterior por tráfico extinta em 2019 (não depurada), marcado específico: 60% confere",
          "Entre a extinção (2019) e o fato (2022) não passaram 5 anos: reincidente específico (LEP, art. 112, VII).")


def _falta(k, db, prog, checks, titulo, conta, evs=None, falta=("12/07/2025", "20/09/2025")):
    p = proc_crim(k, 2021)
    um(k, titulo, conta, [crime(p, "ART 155: Furto", 1155, "10/03/2021", tipo=FURTO, fp="16% - Art.112, I, da LEP")], checks, "04/02/2025",
       eventos=evs(p) if evs else None,
       incidentes=[inc(REG, "Fechado - Regime Inicial", "", "04/02/2025"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", falta[0], falta[1], falta[0])],
       db=db, prog=prog)


_falta(91105, "20/09/2025", "15/02/2026",
       [AUD("data-base-na-decisao-da-falta-grave", True, contem="a data certa é 12/07/2025", nivel="alerta"), AUD("data-base-confere-com-o-rspe", False),
        C("db_motivo", "contem", "Súmula 534")],
       "Data-base do SEEU na data da decisão que homologou a falta grave (20/09/2025), falta de 12/07/2025: alerta",
       "Súmula 534/STJ: o prazo da progressão recomeça no cometimento da infração (12/07/2025), não na decisão; o SEEU atrasa cerca de 59 dias "
       "(70 dias x 84%).")
_falta(91106, "12/07/2025", "18/12/2025", [AUD("data-base-confere-com-o-rspe", True), AUD("data-base-na-decisao-da-falta-grave", False)],
       "Controle: data-base na data da falta grave (12/07/2025): confere", "Súmula 534/STJ.")
_falta(91107, "20/09/2025", "15/02/2026",
       [AUD("data-base-na-decisao-da-falta-grave", True, contem=["a data certa é 01/08/2025", "recaptura"], nivel="alerta")],
       "Fuga em 12/07/2025, recaptura em 01/08/2025, falta homologada em 20/09/2025, data-base do SEEU na decisão: a certa é a da recaptura",
       "Na fuga (falta permanente), a data-base é a da recaptura (01/08/2025), não a da decisão que homologou a falta (Súmula 534/STJ).",
       evs=lambda p: [prisao("04/02/2025", p, "PRISÃO DEFINITIVA"), interr("12/07/2025", "FUGA", p), prisao("01/08/2025", p, "RECAPTURA/REINÍCIO DE CUMPRIMENTO")])

# ------------------------------------------------------------------ livramento
for k, art, tipo, fl, liv, checks in [
        (91201, "ART 2: Domínio social estruturado", "CAPUT, I: utilizar violência ou grave ameaça para intimidar a população, Reclusão: 20 a 40 anos", "1/1 - Hediondo", "",
         [AUD("fracao-de-livramento-diverge", False), C("liv_sit", "contem", "Vedado"), AUD("fato-em-livramento-vedado", True, contem="art. 2º, § 4º, III")]),
        (91202, "ART 3: Favorecimento ao domínio social estruturado", "CAPUT, V: fornecer informações em apoio a organização criminosa ultraviolenta, Reclusão: 12 a 20 anos E Multa",
         "1/1 - Hediondo", "", [AUD("fracao-de-livramento-diverge", False), C("liv_sit", "contem", "Vedado")]),
        (91203, "ART 2: Domínio social estruturado", "CAPUT, I: utilizar violência ou grave ameaça para intimidar a população, Reclusão: 20 a 40 anos", "2/3 - Hediondo",
         "26/01/2041", [AUD("fracao-de-livramento-diverge", False), C("liv_sit", "contem", "veda o livramento"), C("liv", "contem", "26/01/2041")])]:
    um(k, "Lei 15.358/2026, %s, SEEU %s: livramento vedado pela lei" % (art.split(":")[0].lower(), fl.split(" ")[0]),
       "Lei 15.358/2026, art. 2º, § 4º, III (\"insuscetíveis de ... livramento condicional\"), e art. 3º, p. ú.: o 1/1 do SEEU é o correto; se o SEEU "
       "imprime 2/3 e data, a aba ressalva a vedação.",
       [crime(proc_crim(k, 2026), art, anos(22), "02/05/2026", sentenca="20/08/2026", transito="25/09/2026", lei=L15358, tipo=tipo, vga="S",
              fp="70% - Art.112, V, da LEP", fl=fl)],
       checks, "01/06/2026", eventos=[prisao("01/06/2026", proc_crim(k, 2026), "PRISÃO EM FLAGRANTE")], prog="01/01/2040", liv=liv)
k = 91204
p = proc_crim(k, 2019)
um(k, "Livramento revogado e data de livramento impressa pelo SEEU: ressalva do art. 88 do CP",
   "CP, art. 88, e LEP, art. 142: revogado, o livramento não se concede de novo quanto à mesma pena (salvo LEP, art. 141) - a aba não manda só "
   "\"requerer\", e a revogação não conta como pedido concedido.",
   [crime(p, "ART 155: Furto", anos(8), "10/03/2019", tipo="§ 4º: Furto qualificado, Reclusão: 2 a 8 anos E Multa", fp="16% - Art.112, I, da LEP")],
   [C("liv_sit", "contem", ["livramento revogado em 01/03/2023", "conferir antes de requerer"]), C("liv_sit", "nao_contem", "RSPE - requerer"),
    C("liv_sit_full", "nao_contem", "concedido 2x")],
   "10/01/2020",
   eventos=[prisao("10/01/2020", p, "PRISÃO DEFINITIVA"), ev("INTERRUPÇÃO", "LIVRAMENTO CONDICIONAL", "01/10/2022"), prisao("01/03/2023", p, "RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
   incidentes=[inc(REG, "Fechado - Regime Inicial", "", "10/01/2020"), inc("LIVRAMENTO CONDICIONAL", "01/10/2022", "25/09/2022", "01/10/2022", procs=p),
               inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "01/03/2023", "01/03/2023", procs=p)],
   interrompidos=151, db="01/03/2023", prog="20/12/2023", liv="20/06/2023")
for k, fl, liv, checks in [
        (91205, "1/3 - Comum Primário", F(D("10/04/2021") + timedelta(days=anos(12) // 3)),
         [AUD("hediondo-com-resultado-morte-fato-em-livramento", True, contem="o RSPE aplica 1/3"),
          AUD("hediondo-com-resultado-morte-fato-em-livramento", False, contem="O RSPE aplica 1/1"), C("liv_sit", "contem", "veda o livramento"),
          C("liv_sit", "nao_contem", "RSPE - requerer")]),
        (91206, "1/1 - Hediondo com resultado morte", "", [AUD("hediondo-com-resultado-morte-fato-em-livramento", True, contem="O RSPE aplica 1/1"), C("liv_sit", "contem", "Vedado")])]:
    um(k, "Homicídio qualificado consumado em 2021, primário, SEEU %s no livramento" % fl.split(" ")[0],
       "LEP, art. 112, VI, a (Lei 13.964/2019): vedado o livramento. O texto da Auditoria diz o que o RSPE de fato aplica; com data impressa, a aba "
       "ressalva a vedação em vez de mandar requerer.",
       [crime(proc_crim(k, 2021), "ART 121: Homicídio qualificado", anos(12), "10/03/2021", tipo="§ 2º, IV: à traição, de emboscada, Reclusão: 12 a 30 anos",
              vga="S", morte="S", fp="50% - Art.112, VI, a, da LEP", fl=fl)],
       checks, "10/04/2021", eventos=[prisao("10/04/2021", proc_crim(k, 2021), "PRISÃO EM FLAGRANTE")], prog="09/04/2027", liv=liv)
k = 91207
um(k, "Pena total inferior a 2 anos com data de livramento no RSPE: ressalva do art. 83, caput",
   "CP, art. 83, caput: pena igual ou superior a 2 anos (somadas, art. 84). A aba mantém a data do SEEU, com a ressalva, sem mandar só \"requerer\".",
   [crime(proc_crim(k, 2025), "ART 155: Furto", anos(1, 11, 29), "10/03/2025", tipo=FURTO, fp="16% - Art.112, I, da LEP")],
   [C("liv_sit", "contem", "pena total inferior a 2 anos"), C("liv_sit", "nao_contem", "RSPE - requerer")], "01/02/2026", prog="27/05/2026", liv="30/09/2026")


def _priv(k, tipo_atual, fl, checks, titulo, conta, pena=anos(4)):
    ant = crime(proc_crim(k + 500, 2015), "ART 33: Tráfico de drogas", anos(5), "10/03/2015", sentenca="20/11/2015", transito="20/01/2016", lei=DROGAS, tipo=TRAF,
                extinto="Sim", data_extincao="15/06/2021", fp="2/5 - Hediondo primário", fl="2/3 - Hediondo")
    c = crime(proc_crim(k, 2025), "ART 33: Tráfico de drogas", pena, "10/03/2025", sentenca="26/09/2025", transito="25/11/2025", lei=DROGAS, tipo=tipo_atual,
              rc="S", re_="S", fp="20% - Art.112, II, da LEP" if "§" in tipo_atual else "60% - Hediondo reincidente", fl=fl)
    um(k, titulo, conta, [ant, c], checks, "09/04/2025", eventos=[prisao("09/04/2025", proc_crim(k, 2025), "PRISÃO EM FLAGRANTE")], pena=pena,
       prog="20/01/2026", liv="" if fl.startswith("1/1") else F(D("09/04/2025") + timedelta(days=int(pena * 2 / 3))))


_priv(91208, "§ 4º: Tráfico privilegiado (redução de 1/6 a 2/3), Reclusão: 5 a 15 anos E Multa", "1/1 - Hediondo reincidente",
      [AUD("fracao-de-livramento-diverge", True, contem="(1/2", nivel="alerta"), C("liv_sit", "nao_contem", "Vedado")],
      "Tráfico privilegiado marcado reincidente específico, SEEU 1/1 no livramento: legal 1/2",
      "O art. 33, § 4º, não é hediondo (LEP, art. 112, § 5º) nem está no art. 44, p. ú., da Lei 11.343/06: a vedação do reincidente específico não o "
      "alcança - fração 1/2 (CP, art. 83, II).")
_priv(91209, "§ 2º: Induzir, instigar ou auxiliar alguém ao uso indevido de droga, Detenção: 1 a 3 anos E Multa", "2/3 - Hediondo",
      [AUD("fracao-de-livramento-diverge", True, contem="(1/2", nivel="alerta")],
      "Art. 33, § 2º, marcado reincidente específico, SEEU 2/3 no livramento: legal 1/2",
      "O art. 44, p. ú., da Lei 11.343/06 só alcança o art. 33, caput e § 1º, e os arts. 34 a 37.", pena=anos(2, 6))
_priv(91210, TRAF, "1/1 - Hediondo reincidente", [AUD("fracao-de-livramento-diverge", False), C("liv_sit", "contem", "Vedado")],
      "Controle: tráfico do caput, reincidente específico em tráfico (anterior não depurada): livramento vedado",
      "Lei 11.343/06, art. 44, p. ú.; CP, art. 83, V.", pena=anos(6))

# ------------------------------------------------------------------ extinção
k = 91301
um(k, "Término do SEEU em 2106 (pena de 110 anos desde 1996): a data é lida e o art. 75 é conferido",
   "CP, art. 75 (30 anos para fato de 1995): máximo em 31/05/2026, já ultrapassado. O término posterior a 2100 não é lixo de leitura.",
   [crime(proc_crim(k, 1995), "ART 121: Homicídio", anos(110), "10/03/1995", tipo="§ 2º, I: Homicídio qualificado, Reclusão: 12 a 30 anos", vga="S", morte="S")],
   [C("ext_termino", "contem", "/2106"), AUD("limite-de-cumprimento-art-75", True, contem="31/05/2026", nivel="alerta")], "01/06/1996",
   incidentes=[inc(REG, "Fechado - Regime Inicial", "01/06/1996", "01/06/1996")])


def _s617(k, ref, checks, titulo):
    p = proc_crim(k, 2019)
    c = crime(p, "ART 157: Roubo", anos(5), "10/03/2019", sentenca="10/10/2019", transito="10/12/2019",
              tipo="CAPUT: Subtrair coisa móvel alheia, mediante grave ameaça ou violência, Reclusão: 4 a 10 anos E Multa", vga="S")
    um(k, titulo, "Súmula 617/STJ; CP, art. 90; LEP, art. 146: o período de prova (livramento em 01/03/2022) terminou em março de 2025 sem suspensão; a "
       "revogação só foi DECIDIDA em 10/06/2025 - vale a data da decisão, não a de referência do incidente.",
       [c], checks, "01/03/2020",
       eventos=[prisao("01/03/2020", p, "PRISÃO DEFINITIVA"), interr("01/03/2022", "LIVRAMENTO CONDICIONAL"), prisao("20/06/2025", p, "RECAPTURA/REINÍCIO DE CUMPRIMENTO")],
       incidentes=[inc(REG, "Fechado - Regime Inicial", "01/03/2020", "01/03/2020"), inc("LIVRAMENTO CONDICIONAL", "01/03/2022", "25/02/2022", "01/03/2022"),
                   inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "", "10/06/2025", ref, procs=p)],
       term="17/06/2028", db="20/06/2025", pena_cumprida="3a3m19d", pena_remanescente="1a8m16d", total_interrupcoes="3a3m21d")


S617 = [C("ext_sit", "eq", "Extinção cabível"), C("ext_hipoteses", "contem", ["Súmula 617", "decidida em 10/06/2025"])]
_s617(91302, "15/01/2025", S617, "Revogação do livramento decidida depois do fim do período de prova, com data de referência dentro dele: Súmula 617")
_s617(91303, "10/06/2025", S617, "Controle: decisão e referência da revogação depois do fim do período de prova: Súmula 617")


def _susp(k, susp, checks, titulo):
    p = proc_crim(k, 2020)
    incs = [inc(REG, "Fechado - Regime Inicial", "01/03/2021", "01/03/2021"), inc("LIVRAMENTO CONDICIONAL", "01/03/2023", "24/02/2023", "01/03/2023")]
    if susp:
        incs.append(inc("SUSPENSÃO DE LIVRAMENTO CONDICIONAL", "", susp, susp, procs=p))
    um(k, titulo, "LEP, art. 145, e CP, art. 89: suspenso o livramento antes do fim do período de prova, a extinção depende do desfecho; sem suspensão, "
       "CP, art. 90, e Súmula 617/STJ.",
       [crime(p, "ART 155: Furto", anos(4), "10/03/2020", sentenca="10/10/2020", transito="10/12/2020", tipo=FURTO)], checks, "01/03/2021",
       eventos=[prisao("01/03/2021", p, "PRISÃO DEFINITIVA"), interr("01/03/2023", "LIVRAMENTO CONDICIONAL")], incidentes=incs,
       term="27/02/2025", regime="Livramento Condicional - ATIVO", livramento_obs_seeu="(Em livramento condicional deferido em 01/03/2023)",
       pena_cumprida="4a0m0d", pena_remanescente="0a0m0d")


_susp(91304, "10/06/2024", [C("ext_sit", "eq", "Extinção a verificar"), C("ext_hipoteses", "contem", ["suspenso em 10/06/2024", "art. 145"])],
      "Livramento suspenso antes do fim do período de prova, término do SEEU já passado: extinção a verificar")
_susp(91305, "", [C("ext_sit", "eq", "Extinção cabível"), C("ext_hipoteses", "contem", "Súmula 617")],
      "Controle: livramento sem suspensão e período de prova expirado: extinção cabível")

# ------------------------------------------------------------------ execução
tmp = tempfile.mkdtemp()
arq = os.path.join(tmp, "casos_rev_randomizada.json")
with open(arq, "w", encoding="utf-8") as f:
    json.dump(casos, f, ensure_ascii=False)
env = dict(os.environ, APTO_SIM_DESTINO=os.path.join(tmp, "base.sqlite"), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
p = subprocess.run([sys.executable, os.path.join(AQUI, "casos_simulados", "roda_casos.py"), arq, "--vazia"], capture_output=True, text=True, env=env)
fim = (p.stdout.strip().splitlines() or [""])[-1]
if p.returncode != 0:
    print("FALHOU (revisão randomizada): " + fim)
    print("\n".join(l for l in p.stdout.splitlines() if " - FALHA" in l or l.startswith("    x") or "ERRO" in l))
    print(p.stderr[-2000:])
    sys.exit(1)
print("ok: revisão randomizada (%s)" % fim)
