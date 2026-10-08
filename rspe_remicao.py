"""Conciliação da remição pelo trabalho: ficha disciplinar (SIAPEN) x RSPE.

Etapas (cada uma documentada na função própria):
  1. vínculos de trabalho da ficha como máquina de estados (aberto do início até a baixa; nunca "baixa sem início";
     a baixa só é antecipada com prova em atestado - "baixa tardia");
  2. atestados da ficha (regex tolerante; vários segmentos por atestado, somados; atestado em lote/sem período com os
     períodos inferidos dos vínculos entre a última cobertura e a emissão; validação de capacidade e de 1/3);
  3. casamento atestado x remição do RSPE (só incidentes REMIÇÃO): número, dias iguais após truncar a fração, ordem
     cronológica. A cobertura vem do período do atestado; a data de referência só é checada (ref >= fim do período e
     ref <= decisão), sem janela e sem estender a cobertura;
  4. status: CONCILIADO, NAO_LANCADO (atestado emitido sem remição: verificar peticionamento), SEM_ATESTADO (pedir
     atestado), LACUNA (verificar se houve trabalho), DIVERGENCIA (dias diferentes além do truncamento);
  5. resíduo de fração (soma de trabalhados/3 exata x dias concedidos);
  6. estimativa seg.-sáb. só onde não há atestado nem remição;
  7. validações de datas.
Saída: tabela conciliada, pendências acionáveis e alertas de qualidade dos dados.
"""
import math
import re
from datetime import date, timedelta

import rspe_scraper as rs

DT = r"(\d{2}[./]\d{2}[./]\d{2,4})"
SEPD = r"\s*(?:A|À|ATÉ|ATE|-)\s*"

# nomes de setor que a ficha e os atestados usam para o mesmo vínculo: base jurídica, remicao.setores_sinonimos (editável sem
# mexer no programa); a lista abaixo só vale se a base não trouxer nenhuma
ALIAS_PADRAO = [(r"\bHORTA\b|\bAGS\b", "AGS", "Ags Prestadora - Me (Horta)"),
                (r"\bPAIVA\b", "PAIVA", "Paiva Lingerie"),
                (r"\bPRENDE ?BEM\b|\bPRENDEBEM|\bPRENDEDORES\b", "PRENDEBEM", "Prendebem (prendedores)")]


def sinonimos():
    try:
        import rspe_regras as rg
        lst = (rg.carregar().get("remicao") or {}).get("setores_sinonimos") or []
        out = [(x["padrao"], x["chave"], x.get("nome") or x["chave"]) for x in lst if x.get("padrao") and x.get("chave")]
        return out or ALIAS_PADRAO
    except Exception:
        return ALIAS_PADRAO


def _sa(t):
    return rs._sem_acento(t or "").upper()


def _dt(txt):
    """dd/mm/aa(aa) ou dd.mm.aaaa -> date (anos fora de 1900-2100: None)."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{2,4})", txt or "")
    if not m:
        return None
    a = int(m.group(3))
    a = a + (2000 if a < 70 else 1900) if a < 100 else a
    try:
        d = date(a, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return d if 1900 <= d.year <= 2100 else None


def _f(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _num(t):
    try:
        s = str(t).strip(" .,")
        if re.search(r",\d", s) or re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
            return float(s.replace(".", "").replace(",", "."))  # "140,33" ou "1.359" (milhar)
        return float(s)
    except ValueError:
        return 0.0


# dias trabalhados com milhar ("1.359 DIAS TRABALHADOS")
NDIAS = r"(\d{1,3}(?:\.\d{3})+|\d+)"


def _fmtn(v):
    if v is None:
        return "—"
    return ("%d" % v) if abs(v - round(v)) < 1e-9 else ("%.2f" % v).replace(".", ",")


def setor_chave(nome):
    """(chave, nome de exibição) do setor: tira prefixos ("PP - ", "EMPRESA", "SETOR DE", "FUNÇÃO") e junta as variações."""
    u = _sa(nome).strip(" ,.;:-")
    u = re.sub(r"^(?:NA\s+|NO\s+)?(?:FUNCAO|SETOR(?: DE TRABALHO)?(?: DE)?|EMPRESA)\s+", "", u)
    u = re.sub(r"^(?:PP|CC|A1|R1)\s*-\s*", "", u).strip(" ,.;:-")
    u = re.sub(r"^EMPRESA\s+", "", u)
    for pad, ch, disp in sinonimos():
        if re.search(pad, u):
            return ch, disp
    ch = re.sub(r"\W", "", u)[:12] or "?"
    disp = " ".join(w.capitalize() if len(w) > 2 else w.lower() for w in u.split()) or "Setor não identificado"
    return ch, disp


def setor_parecido(a, b):
    """Nome de setor citado no atestado x vínculo da ficha, tolerando erro de digitação ("PLIGONAL", "POLIGNAL") e sufixo
    ("FAXINA LTDA" x "FAXINA DO CORREDOR"): mesma chave, começo comum de 5 letras ou grafia 80% igual."""
    if mesmo_setor(a, b):
        return True
    if not a or not b:
        return False
    import difflib
    pre = len(__import__("os").path.commonprefix([a, b]))
    return pre >= 5 or (min(len(a), len(b)) >= 6 and difflib.SequenceMatcher(None, a[:10], b[:10]).ratio() >= 0.8)


_GENERICAS = {"EMPRESA", "SETOR", "TRABALHO", "SERVICOS", "SERVICO", "GERAIS", "MANUTENCAO", "PREDIAL", "AUXILIAR", "LTDA", "OFICINA", "FUNCAO",
              "PAVILHAO", "INTERNO", "EXTERNO"}


def palavra_comum(a, b):
    """Nomes de setor com uma palavra própria em comum ("SETOR JURIDICO" x "Auxiliar Juridico"; "PINTOR" x "Manutenção Predial - Pintor")."""
    pa = {w for w in re.findall(r"[A-Z]{5,}", _sa(a)) if w not in _GENERICAS}
    pb = {w for w in re.findall(r"[A-Z]{5,}", _sa(b)) if w not in _GENERICAS}
    return bool(pa & pb)


def _nomes_lista(setor):
    """Setores de uma lista do atestado ("PRENDE BEM, FAXINA E COZINHA"), sem o que não é nome de setor."""
    out = []
    for x in re.split(r"\s+E\s+|,", setor or ""):
        x = re.sub(r"^(?:DE|DA|DO|NO|NA)\s+|^DE(?=PRENDE)", "", x.strip(" .;:-()"))
        if not x or re.match(r"^(TRABALHO\b|IPCG\b|AG\.|\d|TOTALIZANDO)", x) or re.search(r"\bDIAS?\b", x):
            continue
        out.append(x)
    return out


def mesmo_setor(a, b):
    """Mesma chave, ou uma é o começo da outra ("POLIGONAL" x "POLIGONALENG")."""
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)))


# --------------------------------------------------------------------------- #
# Etapa 1 - vínculos
# --------------------------------------------------------------------------- #
RE_INI = [re.compile(r"INICIOU ATIVIDADES? LABORA(?:L|IS),?\s*(?:NO SETOR DE TRABALHO|NO SETOR(?: DE)?)\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)"),
          re.compile(r"PASSA A EXERCER ATIVIDADE LABORAL,?\s*NO SETOR(?: DE)?\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)")]
RE_FIM = [re.compile(r"DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)"),
          re.compile(r"ENCERROU ATIVIDADES? LABORA(?:L|IS),?\s*NO SETOR(?: DE)?\s*(.+?)(?:,|$)")]
RE_SAIDA = re.compile(r"SAIDA DA UNIDADE PENAL|EVASAO|TRANSFERENCIA|\bFUGA\b")
_FIMNOME = r"(?:\s+-\s+(?:COMUNICACAO|CI\b|OF\b|OFICIO|DOC)|\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+DELIBERAD|\s+UTILIZANDO|\s+APENAS|\s+POR\s|\s+A PEDIDO|\s+DEVIDO|\s+COM\s|,|\.|\(|/INTERNAMENTE|$)"
# outras redações do SIAPEN (levantadas nas fichas da PDIB, IPCG, CPAIG, PED, EPJFC): início, troca de setor e fim
RE_INI2 = [re.compile(r"(?:RE)?INICIOU SUAS ATI[VN]IDADES LABORAIS,?\s*(?:NESTA\s+UP\s*)?(?:NO SETOR(?: DE| DA| DO)?|N[OA])\s+(.+?)" + _FIMNOME),
           re.compile(r"\bINI?CIA ATIVIDADE LABORAL(?: EXTERNA| INTERNA| EXTERNAMENTE| INTERNAMENTE)?,?\s+(?:NA EMPRESA|NO SETOR(?: DE| DA| DO)?|NA|NO|COMO)\s+(.+?)" + _FIMNOME),
           re.compile(r"CADASTRADO NA ATIVIDADE LABORAL(?: EXTERNA| INTERNA)?\s+NA EMPRESA\s+(.+?)" + _FIMNOME),
           re.compile(r"PASSA A TRABALHAR N[AO]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?(.+?)" + _FIMNOME),
           re.compile(r"PASS(?:A|OU) A EXERCER (?:SUAS )?ATIVIDADES? LABORA(?:L|IS)\s+N[AO]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?(.+?)" + _FIMNOME),
           re.compile(r"\bINICIA(?:-| )SE SUAS ATIVIDADES? LABORA(?:L|IS),?\s*N[AO]\s+(.+?)" + _FIMNOME),
           re.compile(r"\b(?:RE)?INICIA (?:A |O )?(?:TRABALHO LABORAL|ATIVIDADES? LABORA(?:L|IS))(?: EXTERNA| INTERNA)?\s+(?:NA EMPRESA|NO SETOR(?: DE| DA| DO)?|NA|NO)\s+(.+?)" + _FIMNOME),
           re.compile(r"(?:FOI )?CADASTRADO NO SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"PASSA A (?:LABORAR|PRESTAR SERVICO|PRESTAR SERVICOS)\s+N[AO]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?(.+?)" + _FIMNOME),
           re.compile(r"PASSA PRESTAR SERVICOS?\s+N[AO]\s+(?:SETOR(?: DE| DA| DO)?\s+)?(.+?)" + _FIMNOME),
           re.compile(r"INICIOU OS TRABALHOS NO SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"FOI INTEGRADO AO SETOR DE TRABALHO\s+(.+?)" + _FIMNOME),
           # "COMEÇA NO TRABALHO DE SERVIÇOS GERAIS", "COMEÇA NO TRABALHO INTERNO-LAVOURA/CI...", "foi ingressado nas atividades laborais da
           # EMPRESA PRENDE BEM", "passa a contar os dias trabalhados para fins de remição, na Empresa Prendebem"
           re.compile(r"\bCOMECA NO TRABALHO(?: INTERNO| EXTERNO)?\s*(?:DE|-|NA|NO)?\s*(.+?)(?:/|" + _FIMNOME[3:]),
           re.compile(r"INGRESSADO NAS ATIVIDADES LABORAIS D[AO]\s+(?:EMPRESA\s+|SETOR(?: DE| DA| DO)?\s+)?(.+?)" + _FIMNOME),
           re.compile(r"PASSA A CONTAR OS DIAS TRABALHADOS\b.*?\bN[AO]\s+(?:EMPRESA\s+|SETOR(?: DE| DA| DO)?\s+)?(.+?)" + _FIMNOME)]
# "Sem efeito. Reeducando continua trabalhando na empresa X": desfaz o desligamento anterior do mesmo setor
RE_CONTINUA = re.compile(r"SEM EFEITO\.?\s*(?:O\s+)?(?:REEDUCANDO|INTERNO|CUSTODIADO) CONTINUA TRABALHANDO N[AO]\s+(?:EMPRESA\s+|SETOR(?: DE)?\s+)?(.+?)" + _FIMNOME)
RE_REMANEJ = [re.compile(r"REMANEJADO E INICIA ATIVIDADE LABORAL(?: EXTERNA| INTERNA)?\s+NA EMPRESA\s+(.+?)" + _FIMNOME),
              re.compile(r"REMANEJADO DE ATIVIDADE LABORAL ONDE DESE?MPENHARA LABOR NA EMPRESA\s+(.+?)" + _FIMNOME),
              re.compile(r"REMANEJADO (?:DE ATIVIDADE LABORAL )?(?:DO SETOR (?:DE |DA |DO )?.+? )?PARA (?:O SETOR(?: DE| DA| DO)?|A EMPRESA|ATIVIDADE LABORAL(?: EXTERNA| INTERNA)? NA EMPRESA)\s+(.+?)" + _FIMNOME),
              re.compile(r"REMANEJADO (?:INTERNAMENTE |EXTERNAMENTE )?PARA (?:A |O )?(?:ATIVIDADE (?:EXTERNA|INTERNA) NA (?:EMP\.?|EMPRESA)\s+|EMPRESA\s+)?(?!CELA|SOLARIO|RAIO|ALA\b|PAVILHAO)(.+?)" + _FIMNOME)]
RE_FIM2 = [re.compile(r"DESLIGADO (?:DE |DA )?(?:SUAS? )?ATIVIDADES? LABORA(?:L|IS),?\s*(?:DO|NO) SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"DESLIGADO DO SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"DEIXA DE TRABALHAR NO SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"EXCLUIDO DO SETOR(?: DE| DA| DO)?\s+(.+?)" + _FIMNOME),
           re.compile(r"PEDIU DESLIGAMENTO D[AO]\s+(?:EMPRESA\s+|SETOR(?: DE| DA| DO)?\s+)?(.+?)" + _FIMNOME)]
# fim sem setor: encerra todos os vínculos abertos
RE_FIM_GERAL = re.compile(r"NAO RETORNOU DO TRABALHO|RETIRADO DO TRABALHO|\bSAI DO TRABALHO\b|DESLIGA[DG]O DO TRABALHO|DESLIGAMENTO DO (?:LABOR|TRABALHO)|AFASTOU-SE DO TRABALHO|SOLICITOU AFASTAMENTO DO SETOR DE TRABALHO|DESLIGADO DO TRABALHO|DESLIGADO (?:DE |DA )?(?:SUAS? )?ATIVIDADES? LABORA(?:L|IS)(?!,?\s*(?:DO|NO) SETOR)|AFASTADO DO TRABALHO")
RE_LIBERACAO = re.compile(r"^LIBERACAO DO SETOR DE TRABALHO")
RE_SEM_EFEITO = re.compile(r"TORNAR SEM EFEITO O LANCAMENTO DO DIA\s+(\d{2}/\d{2}/\d{2,4}),?\s*REFERENTE AO SETOR DE TRABALHO")
# regra de reserva para o texto livre das unidades (cada época e unidade escreve de um jeito): verbo de início/fim + palavra de
# trabalho; escola, curso, cela, saúde e prisão domiciliar ficam de fora
_NAO_TRAB = re.compile(r"(?<!NAO )RETORNOU DO TRABALHO|EMBRIAGUEZ|EDUCA|PEDAGOG|SAUDE|ESCOLA|CURSO|MATRICULA|(?:DA|PARA|PARA A|NA) CELA (?!LIVRE)|CELA [IVX]+\b|CELA \d|PRISAO DOMICILIAR|PERNOITE|ADVERTENCIA|NAO RETORNOU|TESTE DE TRABALHO")
_PALAVRA_TRAB = r"(?:ATIVIDADES?\s+(?:LABORA(?:L|IS|TIVA)|INTRAMUROS)|TRABALHO|LABOR|SETOR|QUADRO|SERVICOS?|FUNCAO|EMPRESA|EMPREITEIRA|PRODUCAO|CONVENIO)"
RE_INI_RESERVA = re.compile(r"\b(?:INICI\w*|REINICI\w*|RETORN\w*|PASSA A (?:FAZER PARTE|EXERCER|TRABALHAR|DESEMPENHAR|DESENVOLVER|PRESTAR|LABORAR)|PASSA AO|PASSOU A \w+|"
                            r"CADASTRAD\w*|INTEGRAD\w*|REMANEJAD\w*)\b.{0,60}?" + _PALAVRA_TRAB)
RE_FIM_RESERVA = re.compile(r"\b(?:DESLIGA[DG]\w*|AFAST\w*|DEIXA (?:DE (?:TRABALHAR|LABORAR|FAZER PARTE|EXERCER|PRESTAR)|ATIVIDADE)|EXCLUID\w*)\b")
_SETOR_EM = [r"\bPARA (?:O |A )?(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+|OFICINA DE\s+|FUNCAO DE\s+)?(.+?)", r"\bPASSA AO TRABALHO (?:INTERNO|EXTERNO)?\s*[-/]?\s*(.+?)",
             r"\b(?:N[OA]|AO|DO|DA) SETOR(?: DE| DA| DO)?\s+(.+?)", r"\bNA EMPRESA\s+(.+?)", r"\bNA EMPREITEIRA\s+(.+?)",
             r"\bFUNCAO DE\s+(.+?)", r"\bNA PRODUCAO DE\s+(.+?)", r"\bNO CONVENIO\s+(.+?)", r"\bNA OFICINA DE\s+(.+?)"]


def _setor_livre(u, remanejo=False):
    """Nome do setor num lançamento em texto livre (no remanejamento, o setor de destino, depois de "PARA"). O "setor de trabalho"
    que assina o lançamento ("conforme determinação do setor de trabalho ag. Vega") não é o setor."""
    u = re.split(r"\b(?:CONFORME|DELIBERA\w*|DETERMINA\w*|AUTORIZA\w*|ANOTACAO)\b", u)[0]
    for rx in (_SETOR_EM if remanejo else _SETOR_EM[1:]):
        m = re.search(rx + r"(?:\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+DELIBERAD|\s+POR\s|\s+A PEDIDO|\s+DEVIDO|\s+EM VIRTUDE|\s+APOS|"
                           r"\s+COM\s|\s+E PASSA|,|\.|\(|$)", u)
        if m and m.group(1).strip() and len(m.group(1).strip()) <= 60:
            return m.group(1).strip()
    return ""


RE_OUTROS = RE_INI2 + RE_REMANEJ + RE_FIM2 + [RE_FIM_GERAL, RE_LIBERACAO, RE_SEM_EFEITO, RE_CONTINUA, RE_INI_RESERVA, RE_FIM_RESERVA]


def vinculos(eventos, hoje):
    """Vínculos por setor: aberto no início, fechado na baixa do mesmo setor. Um novo início em OUTRO setor não fecha o
    anterior (nada se encerra por inferência); novo início no MESMO setor fecha o anterior na véspera (sem baixa na ficha).
    O remanejamento ("remanejado para o setor X") encerra os vínculos abertos e abre o novo; o desligamento sem setor
    ("desligado do trabalho", "afastado do trabalho") encerra todos; a "Liberação do Setor de Trabalho" encerra todos só
    quando não vem junto da baixa de um setor no mesmo dia. Lançamento tornado sem efeito ("tornar sem efeito o lançamento
    do dia X, referente ao setor de trabalho") é ignorado. Baixa sem vínculo aberto: o vínculo encerrado pela saída da
    unidade não é reaberto; sem nenhum vínculo do setor, fica registrada como alerta (nunca como linha "baixa sem início").
    Vínculo que fica aberto até hoje sem nenhuma baixa recebe "duvida" quando foi aberto no mesmo dia de outro setor
    (provável registro duplicado) ou quando, depois dele, houve início em outro setor ou liberação do trabalho: desde essa
    data o período não entra em dias (fica "a conferir")."""
    abertos, fechados, avisos = {}, [], []
    anulados = set()
    for e in eventos:
        m = RE_SEM_EFEITO.search(_sa(e.get("texto")))
        if m and _dt(m.group(1)):
            anulados.add(_dt(m.group(1)))
    eventos = [e for e in eventos if not (_dt(e.get("data")) in anulados and re.search(r"TRABALH|LABORA|SETOR", _sa(e.get("texto"))))]
    baixa_no_dia = {_dt(e.get("data")) for e in eventos if any(p.search(_sa(e.get("texto"))) for p in RE_FIM + RE_FIM2)}
    marcos = []  # (data, motivo): inícios e liberações que tornam duvidoso um vínculo esquecido aberto

    def abrir(ch, disp, d, txt=""):
        if re.match(r"ESCOLA|EDUCA|ESTUD", _sa(disp)):
            return  # setor "Escola" lançado como trabalho: é estudo (lido em rspe_ficha._estudos)
        ch = next((k for k in abertos if mesmo_setor(k, ch)), ch)
        if ch in abertos and abertos[ch]["ini"] == d:
            return  # o mesmo início lançado duas vezes no dia: um vínculo só
        if ch in abertos:
            v = abertos.pop(ch)
            v.update(fim=d - timedelta(days=1), motivo_fim="sem baixa na ficha (novo início no mesmo setor)", sem_baixa=True)
            fechados.append(v)
        abertos[ch] = {"chave": ch, "setor": disp, "ini": d, "fim": None, "motivo_fim": "", "fim_ficha": None, "txt_ini": "%s - %s" % (_f(d), txt)}
        marcos.append((d, "início em %s" % disp, ch))

    def fechar_todos(d, motivo, txt=""):
        for ch in list(abertos):
            v = abertos.pop(ch)
            v.update(fim=d, fim_ficha=d, motivo_fim=motivo, txt_fim="%s - %s" % (_f(d), txt) if txt else "")
            fechados.append(v)

    for e in eventos:
        d, u = _dt(e.get("data")), _sa(e.get("texto"))
        if not d:
            continue
        cela = u.startswith("MUDANCA DE CELA")
        m = RE_CONTINUA.search(u)
        if m:
            ch, _disp = setor_chave(m.group(1))
            ult = [v for v in fechados if mesmo_setor(v["chave"], ch)]
            if ult and not any(mesmo_setor(k, ch) for k in abertos):
                v = ult[-1]
                fechados.remove(v)
                v.update(fim=None, fim_ficha=None, motivo_fim="", por_saida=False)
                abertos[v["chave"]] = v
            continue
        m = None if (cela or re.search(r"\bCELA\b(?! LIVRE)|SOLARIO", u) and "SETOR" not in u) else next((x for x in (p.search(u) for p in RE_REMANEJ) if x), None)
        if m and m.group(1).strip():
            fechar_todos(d - timedelta(days=1), "remanejado para outro setor", e.get("texto", ""))
            ch, disp = setor_chave(m.group(1))
            abrir(ch, disp, d, e.get("texto", ""))
            continue
        m = next((x for x in (p.search(u) for p in RE_INI + ([] if cela else RE_INI2)) if x), None)
        if m and m.group(1).strip():
            ch, disp = setor_chave(m.group(1))
            abrir(ch, disp, d, e.get("texto", ""))
            continue
        m = next((x for x in (p.search(u) for p in RE_FIM + ([] if cela else RE_FIM2)) if x), None)
        if m and m.group(1).strip():
            ch, disp = setor_chave(m.group(1))
            mm = re.search(r"MOTIVO:\s*(.+?)\s*\.?\s*$", u)
            mot = (mm.group(1).strip(" .") if mm else "") or "baixa"
            ch = next((k for k in abertos if mesmo_setor(k, ch)), ch)
            if ch in abertos:
                v = abertos.pop(ch)
                v.update(fim=d, fim_ficha=d, motivo_fim=mot, txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                fechados.append(v)
            else:
                ult = [v for v in fechados if mesmo_setor(v["chave"], ch)]
                if ult and ult[-1].get("por_saida") and ult[-1]["fim"] == d:
                    # baixa no dia da saída: só registra o motivo. Baixa posterior (às vezes anos depois, já em outra
                    # unidade: "motivo: saída do presídio") não reabre o vínculo encerrado pela saída
                    ult[-1].update(motivo_fim=mot, txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                elif not ult:
                    avisos.append({"tipo": "baixa_sem_inicio", "data": d, "setor": disp})
            continue
        if not cela and RE_FIM_GERAL.search(u):
            fechar_todos(d, "desligado do trabalho", e.get("texto", ""))
            continue
        if not cela and not _NAO_TRAB.search(u) and not re.search(r"\bATESTADO\b|\bATP\b", u):
            # (o lançamento do atestado - "Data Inicial d ... no setor X" - não é início nem fim de vínculo)
            # texto livre: "deixa de trabalhar como barbeiro e passa a desempenhar a função de cela livre" = fim + início
            fim_ = RE_FIM_RESERVA.search(u)
            ini_ = RE_INI_RESERVA.search(u)
            if fim_ and (not ini_ or fim_.start() < ini_.start()):
                nome = _setor_livre(u[:ini_.start()] if ini_ else u)
                ch = setor_chave(nome)[0] if nome else None
                alvo = [k for k in abertos if ch and mesmo_setor(k, ch)] or ([] if ch else list(abertos))
                for k in alvo:
                    v = abertos.pop(k)
                    v.update(fim=d, fim_ficha=d, motivo_fim="desligado do trabalho", txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                    fechados.append(v)
                if not ini_:
                    continue
            if ini_:
                rem = "REMANEJAD" in ini_.group(0)
                nome = _setor_livre(u[ini_.start():], rem)
                if nome:
                    if rem:
                        fechar_todos(d - timedelta(days=1), "remanejado para outro setor", e.get("texto", ""))
                    ch, disp = setor_chave(nome)
                    abrir(ch, disp, d, e.get("texto", ""))
                    continue
        if RE_LIBERACAO.search(u):
            mm = re.search(r"MOTIVO:\s*(.+?)\s*\.?\s*$", u)
            if d not in baixa_no_dia:
                fechar_todos(d, "liberação do setor de trabalho" + ((": " + mm.group(1).strip(" .").lower()) if mm else ""), e.get("texto", ""))
            marcos.append((d, "liberação do setor de trabalho", None))
            continue
        if abertos and RE_SAIDA.search(u):
            for ch in list(abertos):
                v = abertos.pop(ch)
                v.update(fim=d, fim_ficha=d, motivo_fim="saída/transferência/evasão", por_saida=True, txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                fechados.append(v)
    out = fechados + list(abertos.values())
    # setor desativado no SIAPEN ("XXDESATIVADO6098"): é o código antigo de um setor real; aberto no mesmo dia de outro setor
    # ("passa a trabalhar no setor X"), os dois são um vínculo só - fica o nome real, com as datas do registro desativado
    for v in [v for v in out if re.match(r"XX ?DESATIV", _sa(v["setor"]))]:
        par = [w for w in out if w is not v and not re.match(r"XX ?DESATIV", _sa(w["setor"])) and abs((w["ini"] - v["ini"]).days) <= 1]
        if len(par) == 1:
            w = par[0]
            v.update(chave=w["chave"], setor=w["setor"], setor_desativado=True)
            if w["fim"] is None or w["fim"] == v["fim"]:  # o outro registro ficou aberto ou fecha junto: duplicado
                out.remove(w)
                if abertos.get(w["chave"]) is w:
                    del abertos[w["chave"]]
        else:
            v["setor"] = "Setor desativado no SIAPEN (%s)" % v["setor"]
    for v in fechados:
        if re.search(r"A?DEQUACAO DO MAPA", _sa(v.get("motivo_fim"))):
            # baixa por "adequação do mapa do SIAPEN": correção de cadastro, não fim de trabalho - o que sobra sem atestado fica a conferir
            v["duvida"], v["duvida_desde"] = "baixa por adequação do mapa do SIAPEN (correção de cadastro)", v["ini"]
    # vínculo sem baixa própria, encerrado só pela saída da unidade (às vezes anos depois), durante o qual outro setor começou e
    # terminou com baixa própria (trabalhos que vieram e foram com este "aberto"): a mesma dúvida do vínculo esquecido aberto, desde
    # o início desse outro setor. Setores simultâneos encerrados juntos pela saída não entram na dúvida
    for v in [v for v in fechados if v.get("por_saida") and (v["fim"] - v["ini"]).days > 90]:
        dentro = sorted(w["ini"] for w in fechados if w is not v and not mesmo_setor(w["chave"], v["chave"]) and not w.get("por_saida")
                        and v["ini"] < w["ini"] and w["fim"] < v["fim"])
        if dentro:
            v["duvida"], v["duvida_desde"] = "sem baixa na ficha (encerrado só pela saída da unidade em %s); depois houve início e baixa em " \
                                             "outro setor em %s" % (_f(v["fim"]), _f(dentro[0])), dentro[0]
    for v in abertos.values():
        dep = [(d, mot) for d, mot, ch in marcos if d > v["ini"] and ch != v["chave"]]
        if not dep:
            continue  # nada depois do início: é o trabalho atual
        if any(w is not v and w["ini"] == v["ini"] for w in out):
            v["duvida"], v["duvida_desde"] = ("aberto no mesmo dia de outro setor, sem baixa na ficha, e depois houve %s em %s (provável registro "
                                              "duplicado)" % (dep[0][1], _f(dep[0][0]))), v["ini"]
        else:
            v["duvida"], v["duvida_desde"] = "sem baixa na ficha; depois houve %s em %s" % (dep[0][1], _f(dep[0][0])), dep[0][0]
    out.sort(key=lambda v: v["ini"])
    return out, avisos


# --------------------------------------------------------------------------- #
# Etapa 2 - atestados
# --------------------------------------------------------------------------- #
RE_AT = re.compile(r"ATESTADO(?:\s+(?:DE\s+)?TRABALHO)?(?:\s+PRISIONAL)?(?:\s*/?\s*[A-Z]{2,8}\s*-?(?=\s*N))?\s*,?\s*(?:N\s*[.ºO°ª]{0,2}|Nº|N°|NO\.?)?\s*[.:]?\s*(\d{1,5})(?!\d)(?!\s*DIAS?\b)(?:\s*/\s*(\d{4}|[A-Z]{2,8}))?")
# trecho do atestado: "função X (d a d) [totalizando|sendo] N dia(s) trabalhado(s) e R (dias) remidos"; o segundo trecho pode vir
# sem o nome da função ("; (d a d) N dias ...") - herda o setor do anterior
RE_SEG = re.compile(r"([^,;()]{0,60}?)\s*\(\s*" + DT + SEPD + DT + r"\s*\)\s*,?\s*(?:TOTALIZANDO\s*|SENDO\s*)?" + NDIAS + r"\s*(?:DIAS?\s*)?TRABALHAD[OA]S?\s*(?:E/OU|E|,)?\s*([\d.,]+)\s*(?:DIAS?\s*)?REMID[OA]S?")
# totais: "N dias trabalhados [e|e/ou|,|sendo|equivalentes a|...] R dias remidos/a remir", "N dias de trabalho e R dias de remição",
# "tempo de trabalho: N dias ... tempo de remição: R", "remiu R dias com N dias de trabalho" (grupos trab, rem)
RE_TOT = [re.compile(r"(?<![\d/.,])" + NDIAS + r"\s*(?:DIAS?\s*)?(?:TOTAIS\s+)?(?:DE\s+)?TRABALHAD[OA]S?\b(?:\s*\(\s*" + DT + SEPD + DT + r"\s*\))?[^\d]{0,40}?(?P<rem>\d[\d.,]*)\s*(?:DIAS?\s*)?(?:DE\s+)?(?:A\s+(?:SEREM\s+)?)?REMI"),
          re.compile(r"(?<![\d/.,])" + NDIAS + r"\s*DIAS DE TRABALHO\b[^\d]{0,40}?(?P<rem>\d[\d.,]*)\s*DIAS DE (?:TEMPO DE )?REMICAO"),
          re.compile(r"(?:TEMPO (?:TOTAL )?DE TRABALHO|TEMPO TRABALHADO|DIAS TRABALHADOS)[^:\d]{0,40}:?\s*" + NDIAS + r"\s*(?:DIAS?)?(?:\s*TRABALHADOS)?\W{0,4}"
                     r"(?:DIAS REMIDOS|TEMPO (?:TOTAL )?DE REMICAO|REMICAO)[^:\d]{0,20}:?\s*(?:DE\s*)?(?P<rem>\d[\d.,]*)"),
          re.compile(r"REMIU\s*(?P<rem>\d[\d.,]*)\s*DIAS\s*COM\s*" + NDIAS + r"\s*DIAS DE TRABALHO"),
          re.compile(r"(?<![\d/.,])" + NDIAS + r"\s*DIAS?\s*TRABALHAD[OA]S?\b[^\d]{0,60}?REMICAO[^\d]{0,20}?(?P<rem>\d[\d.,]*)")]
# período "d a d" ou "data inicial d até data final d"
RE_PER = re.compile(DT + r"(?:" + SEPD + r"|\s*;?\s*(?:ATE\s+)?DATA FINAL\s*:?\s*)" + DT)
RE_SO_REM = re.compile(r"(?:COM\s*)?(\d[\d.,]*)\s*DIAS?\s*(?:DE\s*REMICAO|REMIDOS|A REMIR)|TEMPO (?:TOTAL )?DE REMICAO\W*(?:DE\s*)?(\d[\d.,]*)\s*DIAS|"
                       r"\bREMIR\s*(\d[\d.,]*)\s*DIAS|TOTAL DE DIAS REMIDOS\W*(\d[\d.,]*)")
# atestado de estudo, curso ou leitura lançado como "atestado de trabalho" (remição pelo estudo: rspe_ficha._estudos)
RE_AT_ESTUDO = re.compile(r"ESTUDANTE|TEMPO (?:TOTAL )?DE (?:TRABALHO/)?ESTUDO|\d\s*/?\s*H/A\b|HORAS?.AULA|REMICAO P(?:OR|ELA) LEITURA|CARGA HORARIA")
RE_AT_ESTUDO2 = re.compile(r"\bESTUDO\b|FREQUENCIA ESCOLAR|\bCURSO\b|LEITURA")
_NUM_EXT = (r"(?:UM|UMA|DOIS|DUAS|TRES|QUATRO|CINCO|SEIS|SETE|OITO|NOVE|DEZ|ONZE|DOZE|TREZE|QUATORZE|CATORZE|QUINZE|DEZESSEIS|DEZESSETE|DEZOITO|DEZENOVE|"
            r"VINTE|TRINTA|QUARENTA|CINQUENTA|SESSENTA|SETENTA|OITENTA|NOVENTA|CEM|CENTO|DUZENTOS|TREZENTOS|QUATROCENTOS|QUINHENTOS|SEISCENTOS|"
            r"SETECENTOS|OITOCENTOS|NOVECENTOS|MIL|VIRGULA|E|DIAS?)")


_VAL_EXT = {"UM": 1, "UMA": 1, "DOIS": 2, "DUAS": 2, "TRES": 3, "QUATRO": 4, "CINCO": 5, "SEIS": 6, "SETE": 7, "OITO": 8, "NOVE": 9, "DEZ": 10,
            "ONZE": 11, "DOZE": 12, "TREZE": 13, "QUATORZE": 14, "CATORZE": 14, "QUINZE": 15, "DEZESSEIS": 16, "DEZESSETE": 17, "DEZOITO": 18,
            "DEZENOVE": 19, "VINTE": 20, "TRINTA": 30, "QUARENTA": 40, "CINQUENTA": 50, "SESSENTA": 60, "SETENTA": 70, "OITENTA": 80, "NOVENTA": 90,
            "CEM": 100, "CENTO": 100, "DUZENTOS": 200, "TREZENTOS": 300, "QUATROCENTOS": 400, "QUINHENTOS": 500, "SEISCENTOS": 600,
            "SETECENTOS": 700, "OITOCENTOS": 800, "NOVECENTOS": 900}
_PAL_EXT = r"(?:" + "|".join(sorted(_VAL_EXT, key=len, reverse=True)) + r")"


def _extenso(txt):
    """ "DUZENTOS E SETENTA E SETE" -> 277; "MIL E DUZENTOS" -> 1200."""
    tot = cur = 0
    for w in re.findall(r"[A-Z]+", txt):
        if w == "MIL":
            tot += (cur or 1) * 1000
            cur = 0
        elif w in _VAL_EXT:
            cur += _VAL_EXT[w]
    return tot + cur


_MESES = ["JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]


def _norm_at(u):
    """Texto do atestado (sem acento, maiúsculo) com os números por extenso, parênteses e abreviações normalizados."""
    u = re.sub(r"[´`]", "", u)  # ´ATESTADO DE TRABALHO´ Nº ...
    u = re.sub(r"\(\s*(\d[\d.,]*)\s*\)", r" \1 ", u)  # "(180) dias trabalhados"
    u = re.sub(r"\(\s*" + _NUM_EXT + r"(?:\s+" + _NUM_EXT + r")*\s*\)", " ", u)  # "05 (CINCO) DIAS", "(SETENTA DIAS)"
    u = re.sub(r"(?<=\d)\s+" + _NUM_EXT + r"(?:\s+" + _NUM_EXT + r")*\s*\)", " ", u)  # parêntese aberto faltando
    u = re.sub(r"\(\s*[A-Z ]{6,}\s*\)", " ", u)  # números por extenso entre parênteses
    u = re.sub(r"(?<=\d)\s+\(?\s*(?:" + _NUM_EXT + r"\s+)*?" + _NUM_EXT + r"(?=\s+DIAS?\b)", " ", u)  # "REMIR 109 CENTO E NOVE DIAS", "165 (CENTO ... CINCO DIAS"
    # dias só por extenso, sem algarismo ("referente a duzentos e setenta e sete dias remidos"): vira o número
    u = re.sub(r"(?<![\d(])\b((?:" + _PAL_EXT + r"|MIL)(?:\s+(?:E\s+)?(?:" + _PAL_EXT + r"|MIL))*)(?=\s+DIAS?\b)",
               lambda m: str(_extenso(m.group(1))) if _extenso(m.group(1)) else m.group(0), u)
    u = re.sub(r"(?<=\d)\s*IAS\b", " DIAS", u)  # "126 ias de remição" (falta o "D")
    u = re.sub(r"\b(\d{1,4})\s?T\s+(\d{1,4}(?:[.,]\d+)?)\s?R\b", r"\1 DIAS TRABALHADOS E \2 DIAS REMIDOS", u)  # "292/24 228T 76R"
    u = re.sub(r"(\d{2})\.\.(\d{4})", r"\1.\2", u)  # "17.11..2021"
    u = re.sub(r"\b(\d{1,2}) DE (JANEIRO|FEVEREIRO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO) DE (\d{4})\b",
               lambda m: "%02d/%02d/%s" % (int(m.group(1)), _MESES.index(m.group(2)) + 1, m.group(3)), u)  # "21 de março de 2014"
    u = re.sub(r"REMISS", "REMIC", u)  # "tempo de remissão"
    u = re.sub(r"\bATETADO\b", "ATESTADO", u)
    u = re.sub(r"(\d)\s*DT\s*[/-]?\s*(\d[\d.,]*)\s*DR\b", r"\1 DIAS TRABALHADOS E \2 DIAS REMIDOS", u)  # "234DT / 78DR"
    u = re.sub(r"(\d{2}[./]\d{2}[./]\d{4})(\d{1,4}\s*DIAS)", r"\1 \2", u)  # "25.11.2020434 dias"
    u = re.sub(r"(TRABALHAD[OA]S)(\d)", r"\1 \2", u)
    u = re.sub(r"\b(\d{2}/\d{2}/)0(\d{4})\b", r"\1\2", u)  # ano digitado com 5 dígitos ("04/04/02025")
    # parêntese de abertura faltando no período ("função Prendebem 19/06/2023 a 22/10/2023) totalizando ..."): repõe
    u = re.sub(r"(?<![(\d/.])(\s)(" + DT + SEPD + DT + r"\s*\))", lambda m: m.group(1) + "(" + m.group(2)
               if u[:m.start()].count("(") <= u[:m.start()].count(")") else m.group(0), u)
    return re.sub(r"\s+", " ", u)


def _totais(u):
    """(trabalhados, remidos) declarados no texto do atestado; (None, None) se não houver."""
    for p in RE_TOT:
        ms = list(p.finditer(u))
        # vários trechos com dias ("13 dias trabalhados no setor A e 4,3 remidos; ... totalizando 26 ..."): vale o total
        m = next((x for x in ms if re.search(r"(?<!SUB)TOTAL\w*\W*(?:DE\W*)?$", u[max(0, x.start() - 20):x.start()])), ms[0] if ms else None)
        if m:
            nt = next(g for i, g in enumerate(m.groups(), 1) if g and i != p.groupindex["rem"])
            return int(_num(nt)), _num(m.group("rem"))
    m = RE_SO_REM.search(u)
    if m:
        return None, _num(next(g for g in m.groups() if g))
    return None, None


def _limpa_setor(t):
    t = re.sub(r"^.*?\b(?:FUNCAO|SETOR DE|SETOR|NA EMPRESA|EMPRESA)\s+", "", t.strip(" ,.;:-"))
    t = re.sub(r"\s+(?:NO|DO|NUM) PERIODO\b.*$|\s+DESDE\b.*$", "", t)
    return t.strip(" ,.;:-")


def _atp(u, d, e):
    """ATP (atestado de trabalho prisional) do SIAPEN: "EMITIDO ATP Nº 105/2023; SETOR; DATA INICIAL: d; DATA FINAL: d; [SETOR:
    DATA INICIAL ...]; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: N DIAS TRABALHADOS; TEMPO DE REMIÇÃO: R DIAS REMIDOS"."""
    mn = re.search(r"\bATP\s*(?:N[^\s\d]*\s*)?(\d{1,4})\s*/\s*(\d{2,4})", u) or RE_AT.search(u)
    mt = re.search(r"TEMPO DE TRABALHO[^:\d]*:?\s*" + NDIAS + r"\s*DIAS", u) or re.search(NDIAS + r"\s*(?:DIAS?\s*)?TRABALHAD", u)
    # "tempo de remição: R dias", "R dias remidos" ou "o tempo de REMIÇÃO totalizou R dias" (modelo "PROTOCOLADO ... Data Inicial ... até Data Final")
    mr = re.search(r"TEMPO (?:TOTAL )?DE REMICAO[^:]*:\s*([\d.,]+)\s*DIAS", u) or re.search(r"([\d.,]+)\s*(?:DIAS?\s*)?REMIDOS", u) or \
        re.search(r"TEMPO (?:TOTAL )?DE REMICAO\s*(?:TOTALIZOU|FOI DE|E DE|DE)\s*([\d.,]+)\s*DIAS", u)
    if not mr:
        return None
    segs = []
    for m in re.finditer(r"(?:^|;|-|:)\s*([A-Z][A-Z /]{3,40}?)?\s*[;:-]?\s*DATA(?: INICIAL)?\s*:?\s*(\d{2}[./]\d{2}[./]\d{2,4})\s*(?:;?\s*(?:ATE\s+)?DATA FINAL\s*:?|" + SEPD + r")\s*(\d{2}[./]\d{2}[./]\d{2,4})", u):
        nome = (m.group(1) or "").strip(" ;:-")
        nome = "" if not nome or nome.startswith(("EMITIDO", "ATP")) else nome
        if not nome:
            nome = (segs[-1]["setor_txt"] if segs else (re.search(r"ATP\s*N\S*\s*[\d/]+\s*[;:-]?\s*([A-Z][A-Z /]{3,40}?)\s*[;:-]", u) or [None, ""])[1])
        segs.append({"setor_txt": (nome or "").strip(), "ini": _dt(m.group(2)), "fim": _dt(m.group(3)), "trab": None, "rem": None, "inferido": False})
    if not segs:
        # "Data Inicial d até Data Final d no SETOR DE X[, Data Inicial ...]": o setor vem depois do período
        for m in re.finditer(r"DATA INICIAL\s*:?\s*" + DT + r"\s*;?\s*(?:ATE\s+)?DATA FINAL\s*:?\s*" + DT +
                             r"(?:\s*,?\s*N[OA]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?([A-Z][A-Z0-9 /&.]{1,40}?)(?=\s*(?:,|;|\.|\(|\bE\b|\bNO QUAL\b|$)))?", u):
            segs.append({"setor_txt": (m.group(3) or "").strip(), "ini": _dt(m.group(1)), "fim": _dt(m.group(2)), "trab": None, "rem": None, "inferido": False})
    if not segs:
        # "referente ao período de d a d", "período: d a d", "tempo de trabalho de d a d", "período de d d" (sem o "a")
        mp = re.search(r"(?:PERIODO|TRABALHO)\s*:?\s*(?:DE\s*)?" + DT + r"(?:" + SEPD + r"|\s+)" + DT, u) or re.search(DT + SEPD + DT, u)
        if mp:
            segs.append({"setor_txt": "", "ini": _dt(mp.group(1)), "fim": _dt(mp.group(2)), "trab": None, "rem": None, "inferido": False})
    trab = int(_num(mt.group(1))) if mt else None
    rem = _num(mr.group(1))
    if len(segs) == 1:
        segs[0].update(trab=trab, rem=rem)
    if not segs:
        segs = [{"setor_txt": "", "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True}]
    for s in segs:
        if s["ini"] is None and not s["inferido"]:
            s["inferido"] = True  # data ilegível na ficha ("26/06/224"): período inferido
        s["chave"], s["setor"] = setor_chave(s["setor_txt"]) if s["setor_txt"] else (None, "")
    num = (mn.group(1).zfill(3) + ("/" + mn.group(2) if mn.group(2) else "")) if mn else ""
    return {"id": "at:%s:%s" % (num or "s/n", _f(d)), "numero": num, "emissao": d, "segs": segs, "trab": trab, "rem": rem,
            "lote": any(s["inferido"] for s in segs), "origem": "ficha", "texto": e.get("texto", ""), "tipo_doc": "ATP"}


def _procs_r(r):
    """Números da execução e das ações penais do RSPE (para saber se o atestado foi peticionado nestes autos)."""
    return [r.get("processo_execucao")] + [c.get("processo_criminal") for c in r.get("_crimes") or []]


def atestados(eventos):
    """Atestados de trabalho da ficha, um por documento, com os segmentos (setor, período, trabalhados, remidos)."""
    out = []
    for e in eventos:
        d = _dt(e.get("data"))
        u = _norm_at(re.sub(r"\s+", " ", _sa(e.get("texto"))))
        if not d:
            continue
        # atestado de estudo, curso ou leitura ("tipo: estudante", "tempo de estudo: 200 h/a", "frequência escolar"): não é trabalho
        if (RE_AT_ESTUDO.search(u) and not re.search(NDIAS + r"\s*DIAS\s*TRABALHAD", u)) or \
                (RE_AT_ESTUDO2.search(u) and not re.search(r"TRABALHAD|TEMPO DE TRABALHO|DIAS DE TRABALHO", u)):
            continue
        # ATP do SIAPEN, com ou sem "Nº" ("ATP 29/2021"), ou o mesmo modelo sem a sigla ("Data Inicial: ...; Tempo de Remissão: ...")
        if re.search(r"\bATP\s*(?:N\S*\s*)?\d", u) or (re.search(r"\bDATA INICIAL\b", u) and re.search(r"TEMPO (?:TOTAL )?DE (?:TRABALHO|REMICAO)", u)):
            a = _atp(u, d, e)
            if a:
                out.append(a)
            continue
        if "ATESTADO" not in u and not re.search(r"\bAT\s*N\S*\s*\d", u):  # "AT Nº253/PDIB COM 51 DIAS REMIDOS"
            continue
        if re.search(r"ATESTADO DE (?:PENA|CONDUTA|MATRICULA|FREQUENCIA|SAUDE|OBITO)|ATESTADO MEDICO", u):
            continue
        mn = RE_AT.search(u) or re.search(r"\bAT\s*N[^\s\d]*\s*(\d{1,4})(?:\s*/\s*(\d{4}|[A-Z]{2,8}))?", u)
        # "o atestado nº 022/2025 deverá ser substituído pelo atestado nº 042/2025, referente ...": o lançamento traz o atestado NOVO
        # (o antigo sai da conta adiante, pela substituição)
        msub = re.search(r"SUBSTITUID[OA]\s+PEL[OA]\b", u)
        if msub and RE_AT.search(u, msub.end()):
            mn = RE_AT.search(u, msub.end())
        segs = []
        for m in RE_SEG.finditer(u):
            nome = _limpa_setor(re.sub(r"^.*?(?:NO SISTEMA SEEU|AUTOS N?[ºO°]?\s*[\d.-]+)\s*,?", "", m.group(1)))
            if not nome and segs:
                nome = segs[-1]["setor_txt"]
            segs.append({"setor_txt": nome, "ini": _dt(m.group(2)), "fim": _dt(m.group(3)), "trab": int(_num(m.group(4))), "rem": _num(m.group(5)), "inferido": False})
        trab = rem = None
        pp = list(re.finditer(r"([^,;()]{0,60}?)\s*\(\s*" + DT + SEPD + DT + r"\s*\)", u))
        if len(segs) == 1 and len(pp) > 1:
            # "função A (d a d) e função B (d a d) totalizando N dias trabalhados e R remidos": o total é do atestado, não da última função
            trab, rem = segs[0]["trab"], segs[0]["rem"]
            segs = [{"setor_txt": _limpa_setor(re.sub(r"^.*?(?:NO SISTEMA SEEU|AUTOS N?[ºO°]?\s*[\d.-]+)\s*,?|^\s*E\s+", "", m.group(1))),
                     "ini": _dt(m.group(2)), "fim": _dt(m.group(3)), "trab": None, "rem": None, "inferido": False} for m in pp]
        elif segs:
            trab, rem = sum(s["trab"] for s in segs), round(sum(s["rem"] for s in segs), 2)
        else:
            trab, rem = _totais(u)
            # períodos citados ("período de d a d, e ... de d a d"; "data inicial d até data final d")
            pers = []
            for m_ in RE_PER.finditer(u):
                p_ = (_dt(m_.group(1)), _dt(m_.group(2)))
                if p_[0] and p_[1] and p_ not in [x[:2] for x in pers]:
                    pers.append(p_ + (m_.start(), m_.end()))
            if trab is None and rem is None:
                # só o período, sem os dias ("ATESTADO DE TRABALHO PRISIONAL Nº 124/2025 - DE 14/12/2024 - 02/05/2025"): atestado com
                # dias desconhecidos, que cobre o período; pedido, aviso ou cancelamento não é atestado
                if not (mn and pers) or re.search(r"SOLICIT|AGUARD|SEM EFEITO|REQUISIT", u) or (re.search(r"SUBSTITU", u) and not msub):
                    continue
            # período único: "período (trabalhado) de d a d" / "d a d"
            mp = (re.search(r"PERIODO(?: TRABALHADO)?\s*(?:DE\s*)?" + DT + r"(?:" + SEPD + r"|\s+)" + DT, u) or re.search(DT + SEPD + DT, u)) if len(pers) < 2 else None
            setor = ""
            u_ = re.sub(r"SETOR DE TRABALHO\s*[-–]\s*[^.;,]*", " ", u)  # quem assina ("SETOR DE TRABALHO - PP ARAUJO - IPCG") não é o setor
            ms_ = re.search(r"(?:NA FUNCAO|FUNCAO|SETOR(?: DE)?|NA EMPRESA)\s+(.+?)(?:\s+\(|\s+DE\s+\d|\s+\d{2}/|,|\.|\s+NAO RESTANDO|\s+COM\s+\d|$)", u_)
            if ms_:
                setor = ms_.group(1).strip()
            trecho = re.split(r"\s*,?\s*TOTALIZANDO|\s+COM\s+[\d.,]+\s*DIAS|\s+NAO RESTANDO", u.split("ATESTADO", 1)[-1])[0]
            lst = [] if mp else re.findall(r"(?:^|-|,|EMPRESA|SETOR(?: DE)?)\s*([A-Z][A-Z0-9&.' ]{1,40}?)\s+(\d{2}/\d{2}/\d{4})\s+(?:A\s+|ATE\s+)?(\d{2}/\d{2}/\d{4})", trecho)
            ini_lst = [] if mp or lst or len(pers) >= 2 else re.findall(r"(?:^|,|\bE\b|SETOR(?: DE)?)\s*([A-Z][A-Z ]{2,40}?)\s+(?:DESDE\s+)?(\d{2}/\d{2}/?\d{4})(?!\s*(?:A|ATE|-)\s*\d)", trecho)
            if len(pers) >= 2:
                # vários períodos e um total só ("período de d a d, e ... de d a d"; "de d a d calculado N dias trabalhados na X; de ..."):
                # um trecho por período; os dias de cada um só quando o texto os dá e fecham com o total (senão, ficam no atestado inteiro)
                for j, (i0, f0, ini_, fim_) in enumerate(pers):
                    depois = u[fim_:pers[j + 1][2] if j + 1 < len(pers) else len(u)]
                    antes = u[pers[j - 1][3] if j else 0:ini_]
                    if j == len(pers) - 1 and depois.rfind("TOTAL") > 0:
                        depois = depois[:depois.rfind("TOTAL")]  # o total do atestado não é do último período
                    if re.match(r"\s*,?\s*(?:O INTERNO\s+|O PRESO\s+)?NAO\s+(?:EFETUOU|TRABALHOU|EXERCEU|HOUVE)", depois):
                        continue  # "de d a d o interno não efetuou qualquer atividade": intervalo sem trabalho
                    mt_ = re.search(NDIAS + r"\s*(?:DIAS?\s*)?TRABALHAD", depois)
                    mr_ = re.search(r"(\d[\d.,]*)\s*(?:DIAS?\s*)?REMIDOS", depois)
                    # setor: depois do período ("(setor de X)", "dias trabalhados na X") ou antes dele ("na empresa X de d a d")
                    mnm = (re.match(r"\s*\(?\s*(?:N[OA]\s+)?(?:SETOR(?: DE)?|FUNCAO(?: DE)?)\s+([A-Z][A-Z0-9&.'/ ]{1,40}?)\s*(?=\)|,|\.|;|\bE\b|\bNO QUAL\b|\bDATA\b|$)", depois)
                           or re.search(r"TRABALHAD\w*\s+N[OA]\s+(?:SETOR(?: DE)?\s+|EMPRESA\s+)?([A-Z][A-Z0-9&.'/ ]{1,40}?)\s*(?=;|,|\.\s|\bE\b|$)", depois)
                           or re.search(r"(?:\bN[OA]\s+(?:EMPRESA\s+|SETOR(?: DE)?\s+)?|\bEMPRESA\s+|\bSETOR(?: DE)?\s+)([A-Z][A-Z0-9&.'/ ]{1,40}?)\s*(?:DE|DATA INICIAL:?)?\s*$", antes))
                    nome = re.sub(r"\s+DE$|^(?:E|NA|NO|NAS|NOS)\s+", "", _limpa_setor(mnm.group(1))) if mnm else ""
                    if re.search(r"PERIODO|CORRESPONDENTE|REFERENTE|TRABALHAD|\bDIAS?\b", nome):
                        nome = ""
                    segs.append({"setor_txt": nome, "ini": i0, "fim": f0, "trab": int(_num(mt_.group(1))) if mt_ else None,
                                 "rem": _num(mr_.group(1)) if mr_ and mt_ else None, "inferido": False})
                if not (trab is not None and all(s_["trab"] is not None for s_ in segs) and abs(sum(s_["trab"] for s_ in segs) - trab) <= 1):
                    for s_ in segs:
                        s_.update(trab=None, rem=None)
            elif mp:
                segs.append({"setor_txt": setor, "ini": _dt(mp.group(1)), "fim": _dt(mp.group(2)), "trab": trab, "rem": rem, "inferido": False})
            elif lst and all(_dt(a_) and _dt(b_) and _dt(a_) <= _dt(b_) for _, a_, b_ in lst):
                # lista "EMPRESA A d1 d2 - EMPRESA B d3 d4": cada empresa com o seu período
                for n_, a_, b_ in lst:
                    segs.append({"setor_txt": _limpa_setor(n_), "ini": _dt(a_), "fim": _dt(b_), "trab": None, "rem": None, "inferido": False})
                if len(segs) == 1:
                    segs[0].update(trab=trab, rem=rem)
            elif len(ini_lst) >= 2:
                # lista "SETOR A DESDE d1, SETOR B d2 ... A ESTA DATA": cada setor da sua data até a véspera do seguinte
                ds = [(_limpa_setor(re.sub(r"^(?:E|DE)\s+", "", n_)), _dt(re.sub(r"(\d{2}/\d{2})/?(\d{4})", r"\1/\2", d_))) for n_, d_ in ini_lst]
                ds = [x for x in ds if x[1]]
                for k_, (n_, d_) in enumerate(ds):
                    f_ = (ds[k_ + 1][1] - timedelta(days=1)) if k_ + 1 < len(ds) else d
                    if f_ >= d_:
                        segs.append({"setor_txt": n_, "ini": d_, "fim": f_, "trab": None, "rem": None, "inferido": False})
            if segs:
                pass
            else:
                # atestado em lote / sem período: os setores citados ("setor de A, B e C") delimitam a inferência; a lista
                # vai até "com N dias" (a vírgula separa setores, não encerra o nome)
                ml = re.search(r"(?:NA FUNCAO|FUNCAO|SETOR(?:ES)?(?: DE)?|NA EMPRESA)\s*(.+?)(?:\s+COM\s+[\d.,]+\s*DIAS|\s+NAO RESTANDO|\s*,?\s*TOTALIZANDO|\s+\d+\s*DIAS|\s+REFERENTE|\s+\(|\.\s|\.$|$)", u_)
                if ml:
                    setor = ml.group(1).strip()
                nomes = _nomes_lista(setor)
                segs = [{"setor_txt": n, "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True} for n in nomes] or \
                       [{"setor_txt": "", "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True}]
        for s in segs:
            s["chave"], s["setor"] = setor_chave(s["setor_txt"]) if s["setor_txt"] else (None, "")
        num = (mn.group(1).zfill(3) + ("/" + mn.group(2) if mn.group(2) else "")) if mn else ""
        out.append({"id": "at:%s:%s" % (num or "s/n", _f(d)), "numero": num, "emissao": d, "segs": segs, "trab": trab, "rem": rem,
                    "lote": any(s["inferido"] for s in segs), "origem": "ficha", "texto": e.get("texto", "")})
        # atestado de estudo no mesmo lançamento ("... 209 dias remidos. E Atestado de Trabalho 07/2018, de estudo, ... 6 dias
        # remidos"): não é trabalho, mas o juízo costuma decidir os dois juntos (215 = 209 + 6) - entra só no casamento
        me_ = re.search(r"\bE\s+(?:O\s+)?ATESTADO\b[^.;]{0,80}?\bESTUDO\b[^;]*?([\d.,]+)\s*(?:DIAS?\s*)?REMID", u)
        if me_ and rem is not None and me_.start() > u.find("REMID"):
            out[-1]["rem_estudo"] = _num(me_.group(1))
    # etapa do documento: "peticionado" no SEEU (ou protocolado/enviado aos autos) x só "emitido" pela unidade; um
    # peticionamento registrado depois com o mesmo número também conta
    for a in out:
        u = _sa(a["texto"])
        a["peticionado"] = _f(a["emissao"]) if re.search(r"PETICION|PROTOCOLAD|ENVIAD\w* (?:VIA|AO|PARA|NO)|JUNTAD", u) else ""
        ma = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", u)
        a["autos"] = ma.group(0) if ma else ""
    for e in eventos:
        u = re.sub(r"\s+", " ", _sa(e.get("texto")))
        if not re.search(r"PETICION|PROTOCOLAD", u):
            continue
        mn = RE_AT.search(u) or re.search(r"\bATP\s*N\S*\s*(\d{1,4})(?:\s*/\s*(\d{2,4}))?", u)
        if not mn:
            continue
        n0 = mn.group(1).lstrip("0")
        for a in out:
            if not a["peticionado"] and a["numero"] and a["numero"].split("/")[0].lstrip("0") == n0 and _dt(e.get("data")) and _dt(e.get("data")) >= a["emissao"]:
                a["peticionado"] = _f(_dt(e.get("data")))
    # atestado retificado: o novo substitui o anterior de mesmo número (não soma)
    for a in [a for a in out if re.search(r"RETIFICAD", _sa(a["texto"])) and a["numero"]]:
        for b in [b for b in out if b is not a and b["numero"] == a["numero"] and b["emissao"] <= a["emissao"]]:
            out.remove(b)
            a["peticionado"] = a["peticionado"] or b.get("peticionado", "")
    # atestado tornado sem efeito ("TORNAR SEM EFEITO O ATESTADO DE TRABALHO PRISIONAL Nº 022/2025") sai da conta
    for e in eventos:
        m = re.search(r"SEM EFEITO O ATESTADO\D{0,40}?(\d{1,4})\b", _sa(e.get("texto")))
        if m and _dt(e.get("data")):
            out = [a for a in out if not (a["numero"] and a["numero"].split("/")[0].lstrip("0") == m.group(1).lstrip("0") and a["emissao"] <= _dt(e.get("data")))]
    # atestado substituído por outro de número diferente ("... em substituição ao atestado de trabalho nº 649/2014"; "o atestado
    # nº 022/2025 deverá ser substituído pelo nº 042/2025"): o substituído sai da conta
    for e in eventos:
        u = re.sub(r"\s+", " ", _sa(e.get("texto")))
        d = _dt(e.get("data"))
        m = re.search(r"EM SUBSTITUICAO A[O]?\b\D{0,60}?(\d{1,4})\b", u) or re.search(r"ATESTADO\D{0,40}?(\d{1,4})\S*\s+DEVERA SER SUBSTITUIDO", u)
        if not (m and d):
            continue
        proprio = (RE_AT.search(u[:m.start()]) or [None, ""])[1] if "SUBSTITUICAO" in m.group(0) else ""
        n0 = m.group(1).lstrip("0")
        if n0 and n0 != (proprio or "").lstrip("0"):
            out = [a for a in out if not (a["numero"] and a["numero"].split("/")[0].lstrip("0") == n0 and a["emissao"] <= d)]
    # atestado lançado só com o período (dias desconhecidos) e registrado de novo com os dias: fica o registro com os dias
    out = [a for a in out if a["rem"] is not None or a["trab"] is not None
           or not any(b is not a and b["numero"] == a["numero"] and b["rem"] is not None for b in out)]
    # o mesmo atestado lançado duas vezes no dia (emissão e peticionamento; "0094/2026" e "094/2026"; um deles sem número): um só
    def _mesmo(a, b):
        return (a["emissao"] == b["emissao"] and a["rem"] is not None and (a["trab"], a["rem"]) == (b["trab"], b["rem"])
                and (not a["numero"] or not b["numero"] or a["numero"].lstrip("0") == b["numero"].lstrip("0")))
    fora = []
    for a in sorted(out, key=lambda a: not a["numero"]):  # fica o que tem número
        if any(_mesmo(a, b) for b in out if b is not a and b not in fora and (b["numero"] or not a["numero"]) and (bool(b["numero"]) > bool(a["numero"]) or out.index(b) < out.index(a))):
            fora.append(a)
    out = [a for a in out if a not in fora]
    vistos, uniq = set(), []
    for a in out:  # o mesmo lançamento repetido na ficha (mesma data e mesmo texto) é um atestado só
        k = (a["emissao"], re.sub(r"\s+", " ", a["texto"]).strip())
        if k not in vistos:
            vistos.add(k)
            uniq.append(a)
    out = uniq
    out.sort(key=lambda a: a["emissao"])
    return out


def atestados_manuais(manuais):
    """Atestados de trabalho informados pelo operador ("+ Adicionar atestado"), com trechos opcionais."""
    out = []
    for m_ in manuais or []:
        d = m_.get("dados") or {}
        if (d.get("tipo") or "Trabalho") != "Trabalho":
            continue
        segs = []
        for ln in (d.get("trechos") or "").splitlines():
            p = [x.strip() for x in ln.split(";")]
            if len(p) >= 3 and _dt(p[1]) and _dt(p[2]):
                ch, disp = setor_chave(p[0])
                segs.append({"setor_txt": p[0], "chave": ch, "setor": disp, "ini": _dt(p[1]), "fim": _dt(p[2]),
                             "trab": int(_num(p[3])) if len(p) > 3 and p[3] else None, "rem": _num(p[4]) if len(p) > 4 and p[4] else None, "inferido": False})
        if not segs and _dt(d.get("inicio")) and _dt(d.get("fim")):
            ch, disp = setor_chave(d.get("descricao") or "") if d.get("descricao") else (None, "")
            segs.append({"setor_txt": d.get("descricao") or "", "chave": ch, "setor": disp, "ini": _dt(d["inicio"]), "fim": _dt(d["fim"]),
                         "trab": None, "rem": None, "inferido": False})
        trab = int(_num(d["trabalhados"])) if d.get("trabalhados") else (sum(s["trab"] or 0 for s in segs) or None)
        rem = _num(d["remidos"]) if d.get("remidos") else (round(sum(s["rem"] or 0 for s in segs), 2) or None)
        if not rem and not trab:
            continue
        emi = _dt(d.get("emissao") or "") or max((s["fim"] for s in segs if s["fim"]), default=None)
        if not emi:
            continue
        if not segs:
            segs = [{"setor_txt": "", "chave": None, "setor": "", "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True}]
        num = (d.get("numero") or "").strip()
        out.append({"id": "man:%s" % m_.get("id"), "numero": num, "emissao": emi, "segs": segs, "trab": trab, "rem": rem,
                    "lote": any(s["inferido"] for s in segs), "origem": "operador", "texto": "Informado pela equipe: " + (d.get("descricao") or ""),
                    # lançado pela equipe a partir dos autos: está juntado (peticionado), mesmo sem registro na ficha
                    "peticionado": "nos autos (informado pela equipe)", "autos": ""})
    return out


# --------------------------------------------------------------------------- #
# Etapas 2-7
# --------------------------------------------------------------------------- #
def _dias_seg_sab(a, b):
    import rspe_ficha as rf
    return rf.dias_trabalho(a, b, "")


def _dias_set(a, b):
    """Dias de trabalho (seg.-sáb., sem feriados) entre a e b, como conjunto."""
    import rspe_ficha as rf
    fer = set()
    for y in range(a.year, b.year + 1):
        fer |= rf.feriados(y)
    return {a + timedelta(days=k) for k in range((b - a).days + 1) if (a + timedelta(days=k)).weekday() < 6 and a + timedelta(days=k) not in fer}


# interrupção da custódia em que não há trabalho a remir: fuga, soltura, livramento, aberto (a interrupção por prisão em outro
# processo, outra comarca ou conversão da prisão segue com o preso na unidade)
RE_INT_FORA = re.compile(r"FUGA|EVAS|LIBERDADE|LIVRAMENTO|ALVARA|SOLTURA|RELAXAMENTO|FIANCA|HABEAS|DESCUMPRIMENTO|FINAL DA PRISAO|"
                         r"REGIME ABERTO|RESTRITIVA|BENEFICIO|INDULTO|^CUMPRIMENTO DA PENA")


def fora_da_unidade(r, hoje, f=None):
    """Períodos do RSPE em que o trabalho não gera remição a estimar: interrupção da custódia por fuga, soltura ou livramento
    (até a nova prisão), período de prova do livramento e regime aberto (LEP, art. 126, caput e § 6º: no aberto só o estudo).
    A ficha prevalece quando mostra a pessoa presa: a entrada em unidade de custódia (fechado, semiaberto, provisória) encerra
    o período na véspera; no aberto e no livramento, o dia em unidade de custódia segundo a ficha também fica fora do corte.
    [(início, fim, motivo)]."""
    import rspe_ficha as rf
    tl = rf.linha_unidades(f) if f else []
    custodia = [(d, (rf.classificar_unidade(u)[0] or "")) for d, u in tl]

    def ate_entrada(a, b):
        ent = [d for d, c in custodia if a < d <= b and c in ("fechado", "semiaberto", "provisorio", "federal")]
        return (a, min(ent) - timedelta(days=1)) if ent else (a, b)

    def fora_de_custodia(a, b):
        # trechos de a..b em que a última entrada da ficha não é unidade de custódia (ou não há entrada registrada)
        cortes = [a] + [d for d, _c in custodia if a < d <= b]
        out_ = []
        for k, c0 in enumerate(cortes):
            c1 = (cortes[k + 1] - timedelta(days=1)) if k + 1 < len(cortes) else b
            ult = [c for d, c in custodia if d <= c0]
            if not ult or ult[-1] not in ("fechado", "semiaberto", "provisorio", "federal"):
                out_.append((c0, c1))
        return out_
    out = []
    evs = sorted(((rs.to_date(e.get("data") or ""), e) for e in r.get("_eventos") or []), key=lambda x: x[0] or date.min)
    ab = None
    for d, e in evs:
        if not d:
            continue
        if "INTERRUP" in _sa(e.get("tipo")):
            if ab is None and RE_INT_FORA.search(_sa(e.get("motivo")).strip()):
                ab = (d, (e.get("motivo") or "").strip().lower())
        elif ab:
            if d > ab[0]:
                out.append(ate_entrada(ab[0], d - timedelta(days=1)) + (ab[1],))
            ab = None
    if ab:
        out.append(ate_entrada(ab[0], hoje) + (ab[1],))
    per = []
    try:
        per = [(a, (b - timedelta(days=1)) if b else hoje, "livramento condicional")
               for a, b in rs.periodos_livramento(r.get("_eventos") or [], r.get("_incidentes") or [])]
    except Exception:
        pass
    # regime aberto: da decisão que o fixou até a próxima fixação de outro regime
    regs = []
    for i in r.get("_incidentes") or []:
        if i.get("situacao") != "CONCEDIDO" or "REGIME" not in _sa(i.get("tipo")) or "DATA-BASE" in _sa(i.get("tipo")):
            continue
        ds = [x for x in (_dt(i.get("data_referencia") or ""), _dt(i.get("data_decisao") or "")) if x]
        if ds:
            aberto = _sa(i.get("complemento")).startswith("ABERTO")
            regs.append((max(ds) if aberto else min(ds), aberto))
    regs.sort()
    for k, (d, aberto) in enumerate(regs):
        if aberto:
            fim = next((d2 for d2, ab2 in regs[k + 1:] if not ab2 and d2 > d), None)
            per.append((d, (fim - timedelta(days=1)) if fim else hoje, "regime aberto"))
    for a, b, mot in per:
        out += [(x, y, mot) for x, y in fora_de_custodia(a, b)]
    return sorted(x for x in out if x[1] >= x[0])


def ausencias_ficha(eventos):
    """Dias sem trabalho dentro do vínculo, registrados na ficha: isolamento em cela disciplinar ("isolado preventivamente
    ... por 10 dias") e saída temporária (saída e retorno confirmados, ou "devendo retornar em d"). [(início, fim, motivo)]."""
    out, sai = [], None
    for e in eventos or []:
        d, u = _dt(e.get("data")), re.sub(r"\s+", " ", _sa(e.get("texto")))
        if not d:
            continue
        if re.search(r"SAIDA CONFIRMADA DO BENEFICIO", u):
            sai = d
        elif re.search(r"RETORNO CONFIRMADO DO BENEFICIO", u) and sai:
            if d > sai:
                out.append((sai, d - timedelta(days=1), "saída temporária"))
            sai = None
        m = re.search(r"SAIDA TEMPORARIA.*?(?:DEVENDO RETORNAR|RETORNO PREVISTO)\D{0,40}?(\d{2}/\d{2}/\d{4})", u)
        if m and _dt(m.group(1)) and d < _dt(m.group(1)) <= d + timedelta(days=10):
            out.append((d, _dt(m.group(1)) - timedelta(days=1), "saída temporária"))
        m = re.search(r"(?:ISOLAD\w*|CELA DISCIPLINAR|ISOLAMENTO)\D{0,60}?(?:POR|DE)\s*(\d{1,2})\s*(?:\(\w+\)\s*)?DIAS", u)
        if m and not u.startswith("MUDANCA DE CELA") and 0 < int(m.group(1)) <= 30:
            out.append((d, d + timedelta(days=int(m.group(1)) - 1), "isolamento"))
    return sorted(set(out))


def remicoes_rspe(r):
    """Só incidentes REMIÇÃO concedidos, com dias, data da decisão e data de referência."""
    out = []
    for i in r.get("_incidentes", []):
        if not rs.e_remicao_concedida(i):
            continue
        m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento", ""), re.I)
        if not m:
            continue
        dec = _dt(i.get("data_decisao") or "") or _dt(i.get("data_referencia") or "")
        ref = _dt(i.get("data_referencia") or "") or dec
        num = re.search(r"ATESTADO\D{0,12}(\d{1,4}(?:/\d{4})?)", _sa((i.get("complemento") or "") + " " + (i.get("motivo") or "")))
        out.append({"dias": _num(m.group(1)), "decisao": dec, "ref": ref, "numero": num.group(1) if num else "", "usada": None})
    out.sort(key=lambda x: x["decisao"] or date.min)
    return out


def conciliar(r, f, hoje=None, manuais=None, ini_exec=None, excluir_remicoes=None):
    """Concilia os atestados de trabalho da ficha (e os informados pelo operador) com as remições do RSPE.
    excluir_remicoes: datas de decisão de remições já atribuídas a outra origem (leitura, estudo)."""
    hoje = hoje or date.today()
    impressao = _dt(f.get("data_impressao") or "") or hoje
    evs = f.get("eventos") or []
    vinc, av_v = vinculos(evs, hoje)
    ats = atestados(evs) + atestados_manuais(manuais)
    ats.sort(key=lambda a: a["emissao"])
    rems = remicoes_rspe(r)
    for x in rems:
        if excluir_remicoes and (x["decisao"], x["dias"]) in excluir_remicoes:
            x["usada"] = "outra origem"
    alertas = []

    def alerta(tipo, texto, data=None):
        alertas.append({"tipo": tipo, "texto": texto, "data": data})

    for a in av_v:
        alerta("baixa sem início", "Baixa de %s em %s sem início registrado na ficha nem vínculo anterior do setor: conferir o período com a unidade." % (a["setor"], _f(a["data"])), a["data"])

    # ---- validação dos períodos explícitos (capacidade, ano trocado, 1/3) ----
    fim_ant = None
    for a in ats:
        # o texto cita mais períodos do que os trechos lidos: os dias podem ser de todos eles - não se aponta nem corrige "erro de ano"
        varios = len(RE_PER.findall(_norm_at(re.sub(r"\s+", " ", _sa(a.get("texto")))))) > len([s for s in a["segs"] if not s["inferido"]])
        for s in a["segs"]:
            if s["inferido"] or not s["ini"] or not s["fim"]:
                continue
            if s["fim"] < s["ini"]:
                # ano trocado no início ("Data Inicial 01/07/2023 até Data Final 05/10/2022"): com o ano anterior, o período fecha
                try:
                    i2 = s["ini"].replace(year=s["ini"].year - 1)
                except ValueError:
                    i2 = None
                ok_ = i2 and i2 <= s["fim"] and (s["fim"] - i2).days < 366
                alerta("data", "Atestado %s: fim (%s) anterior ao início (%s)%s." % (a["numero"] or "s/n", _f(s["fim"]), _f(s["ini"]),
                       ("; início provável %s (ano anterior) - conferir o atestado" % _f(i2)) if ok_ else ""), a["emissao"])
                if ok_:
                    s["ini_ficha"], s["ini"], s["corrigido"] = s["ini"], i2, True
            corridos = (s["fim"] - s["ini"]).days + 1
            if s["trab"] and s["trab"] > corridos and not varios:
                prop = (fim_ant + timedelta(days=1)) if fim_ant and fim_ant < s["fim"] else None
                ok = prop and s["trab"] <= (s["fim"] - prop).days + 1
                alerta("erro de ano", "Atestado %s: %s dias trabalhados não cabem no período %s a %s (%s corridos) - possível erro de ano na ficha%s." % (
                    a["numero"] or "s/n", s["trab"], _f(s["ini"]), _f(s["fim"]), corridos,
                    ("; início provável %s (dia seguinte ao fim do atestado anterior)" % _f(prop)) if ok else ""), a["emissao"])
                if ok:
                    s["ini_ficha"], s["ini"], s["corrigido"] = s["ini"], prop, True
            if s["fim"] > impressao:
                alerta("data", "Atestado %s: período até %s, depois da impressão da ficha (%s)." % (a["numero"] or "s/n", _f(s["fim"]), _f(impressao)), a["emissao"])
        fs = [s["fim"] for s in a["segs"] if s["fim"]]
        if fs:
            fim_ant = max(fs + ([fim_ant] if fim_ant else []))
        for s in a["segs"]:
            if s.get("trab") and s.get("rem") is not None and s["rem"] > s["trab"] / 3.0 + 1:
                s["rem_ficha"], s["rem"] = s["rem"], round(s["trab"] / 3.0, 2)
        if a["trab"] and a["rem"] is not None and abs(a["trab"] / 3.0 - a["rem"]) > 1:
            maior = a["rem"] > a["trab"] / 3.0 + 1
            alerta("proporção", "Atestado %s: %s trabalhados dariam %s remidos (1 a cada 3), consta %s%s." % (
                a["numero"] or "s/n", a["trab"], _fmtn(a["trab"] / 3.0), _fmtn(a["rem"]),
                " - a conta usa 1/3 dos dias trabalhados (LEP, art. 126, § 1º, II): conferir o atestado" if maior else ""), a["emissao"])
            if maior:
                # remidos acima de 1/3 dos dias trabalhados: erro de digitação da ficha ("171 trabalhados e 171 remidos")
                a["rem_ficha"], a["rem"] = a["rem"], round(a["trab"] / 3.0, 2)

    # ---- Etapa 3: casamento atestado x remição ----
    def livre(x):
        return x["usada"] is None

    def _fim_at(a):
        return max([s["fim"] for s in a["segs"] if s.get("fim")] or [None]) if any(s.get("fim") for s in a["segs"]) else None

    def _ini_at(a):
        return min([s["ini"] for s in a["segs"] if s.get("ini") and not s["inferido"]] or [None]) if any(s.get("ini") and not s["inferido"] for s in a["segs"]) else None

    def _alvos(rem, trab, est=None):
        # valores que o juízo pode ter concedido: remidos truncados ou arredondados (39,99 -> 40) e trabalhados / 3 (a conta do
        # juízo, quando a ficha digitou os remidos errado); com o atestado de estudo do mesmo lançamento, a soma dos dois
        out = {int(math.floor(rem + 1e-9)), int(round(rem))}
        if trab:
            out.add(int(math.floor(trab / 3.0 + 1e-9)))
        if est:
            out |= {int(math.floor(rem + est + 1e-9)), int(round(rem + est))}
        return out

    def _alvos_a(a):
        return _alvos(a["rem"], a["trab"], a.get("rem_estudo"))

    def _ref_no_periodo(a, x, k):
        """Remição decidida antes da data em que a ficha registra o atestado (emissão ou peticionamento lançados depois), mas
        com a data de referência no fim do período do atestado ou dentro dele: pode ser deste atestado. Sem período explícito
        (atestado em lote), a referência fica entre o atestado anterior e a emissão, com a decisão até 120 dias antes."""
        if not x["ref"]:
            return False
        ini_a, fim_a = _ini_at(a), _fim_at(a)
        if ini_a and fim_a:
            if abs((x["ref"] - fim_a).days) <= 5:
                return True
            return x["dias"] >= 10 and ini_a <= x["ref"] <= fim_a  # dias iguais e referência dentro do período
        ant = max([b["emissao"] for b in ats[:k] if b["rem"] is not None and b["emissao"] < a["emissao"]] or [date.min])
        return ant < x["ref"] <= a["emissao"] and (x["decisao"] or date.max) >= a["emissao"] - timedelta(days=120)

    for a in ats:
        a["remicao"], a["status"] = None, "NAO_LANCADO"
        # atestado com o período todo antes do início desta execução: é de outra custódia - não casa com remição desta execução
        # (fica "anterior a esta execução", adiante)
        ss_ = [s for s in a["segs"] if not s["inferido"] and s.get("fim")]
        a["_ant"] = bool(ini_exec and (all(s["fim"] < ini_exec for s in ss_) if ss_ else a["emissao"] < ini_exec))
    for k, a in enumerate(ats):
        if a["rem"] is None or a["_ant"]:
            continue
        lim = a["emissao"] - timedelta(days=5)
        fim_a = _fim_at(a)
        # remição cuja data de referência é o fim de OUTRO atestado de mesmos dias ainda sem par: é daquele (não deste)
        alheia = {_fim_at(b) for b in ats if b is not a and not b["remicao"] and b["rem"] is not None and _fim_at(b) != fim_a
                  and int(math.floor(b["rem"] + 1e-9)) == int(math.floor(a["rem"] + 1e-9))}
        cand = [x for x in rems if livre(x) and ((x["decisao"] or date.max) >= lim or _ref_no_periodo(a, x, k))
                and not (x["ref"] in alheia and x["ref"] != fim_a)]
        cand.sort(key=lambda x: x["ref"] != fim_a)  # a remição com referência no fim deste atestado vem primeiro (estável)
        x = next((x for x in cand if a["numero"] and x["numero"] and x["numero"].split("/")[0].zfill(3) == a["numero"].split("/")[0].zfill(3)), None) \
            or next((x for x in cand if int(math.floor(a["rem"] + 1e-9)) == int(math.floor(x["dias"] + 1e-9))), None) \
            or next((x for x in cand if int(math.floor(x["dias"] + 1e-9)) in _alvos_a(a)), None)
        if x:
            x["usada"], a["remicao"], a["status"] = a["id"], x, "CONCILIADO"
            if a["trab"] and a["rem"] < a["trab"] / 3.0 - 1 and int(math.floor(x["dias"] + 1e-9)) == int(math.floor(a["trab"] / 3.0 + 1e-9)):
                # remidos digitados abaixo de 1/3 ("121 trabalhados e 10,33 remidos") e o juízo concedeu trabalhados / 3: vale 1/3
                a["rem_ficha"], a["rem"] = a["rem"], round(a["trab"] / 3.0, 2)
                alerta("proporção", "Atestado %s: remidos digitados na ficha (%s) abaixo de 1/3 dos %s trabalhados; a remição do RSPE (%s) "
                       "confirma 1/3 - a conta usa %s." % (a["numero"] or "s/n", _fmtn(a["rem_ficha"]), a["trab"], rs.pl(int(x["dias"]), "dia", "dias"),
                                                          _fmtn(a["rem"])), a["emissao"])
    # (b2) uma remição para dois ou três atestados (o juízo decidiu os pedidos juntos): a soma dos dias fecha com a remição, e os
    # atestados foram emitidos até a decisão (no máximo 400 dias antes)
    from itertools import combinations
    for x in rems:
        if not livre(x) or not x["decisao"]:
            continue
        sol = [a for a in ats if not a["remicao"] and a["rem"] is not None and not a["_ant"]
               and x["decisao"] - timedelta(days=550) <= a["emissao"] <= x["decisao"] + timedelta(days=5)]
        achou = None
        for n in (2, 3):
            for comb in combinations(sol, n):
                s_ = sum(a["rem"] for a in comb)
                t_ = sum(a["trab"] for a in comb) if all(a["trab"] for a in comb) else None
                if int(x["dias"]) in _alvos(s_, t_) | {sum(int(math.floor(a["rem"] + 1e-9)) for a in comb)}:
                    achou = comb
                    break
            if achou or len(sol) > 12:
                break
        if not achou and x["dias"] >= 30:
            # diferença de 1 dia no arredondamento da soma (113 + 16 + 12 = 141 x 140), com atestados emitidos até 3 anos antes:
            # só quando uma única combinação fecha
            sol = [a for a in ats if not a["remicao"] and a["rem"] is not None and not a["_ant"]
                   and x["decisao"] - timedelta(days=1100) <= a["emissao"] <= x["decisao"] + timedelta(days=5)]
            if len(sol) <= 12:
                ach = [comb for n in (2, 3) for comb in combinations(sol, n)
                       if abs(sum(a["rem"] for a in comb) - x["dias"]) <= 1 + 1e-9
                       or abs(sum(int(math.floor(a["rem"] + 1e-9)) for a in comb) - x["dias"]) <= 1 + 1e-9]
                if len(ach) == 1:
                    achou = ach[0]
        if achou:
            x["usada"] = "+".join(a["id"] for a in achou)
            for a in achou:
                a["remicao"], a["status"] = x, "CONCILIADO"
                a["remicao_conjunta"] = len(achou)
    # (b3) um atestado lançado no RSPE em duas ou três linhas (mesma decisão ou decisões próximas, referências dentro do período do
    # atestado): a soma das linhas fecha com o atestado (164 = 52 + 112)
    for a in ats:
        ini_a, fim_a = _ini_at(a), _fim_at(a)
        if a["remicao"] or a["rem"] is None or a["_ant"] or not (ini_a and fim_a):
            continue
        cand = [x for x in rems if livre(x) and x["ref"] and x["decisao"] and ini_a <= x["ref"] <= fim_a + timedelta(days=5)
                and x["decisao"] >= ini_a][:10]
        achou = None
        for n in (2, 3):
            for comb in combinations(cand, n):
                if (max(y["decisao"] for y in comb) - min(y["decisao"] for y in comb)).days <= 60 and \
                        sum(int(math.floor(y["dias"] + 1e-9)) for y in comb) in _alvos_a(a):
                    achou = comb
                    break
            if achou:
                break
        if achou:
            for y in achou:
                y["usada"] = a["id"]
            x = dict(achou[-1], dias=sum(y["dias"] for y in achou), decisao=max(y["decisao"] for y in achou),
                     ref=max(y["ref"] for y in achou), linhas=len(achou))
            a["remicao"], a["status"] = x, "CONCILIADO"
    # (b4) remição com a data de referência no fim do período do atestado (±1 dia), decidida depois desse fim, mesmo com dias
    # diferentes: é deste atestado (102 dias com referência em 08/08/2023, fim do atestado de 69) - a diferença é conferida
    for a in ats:
        fim_a = _fim_at(a)
        if a["remicao"] or a["rem"] is None or a["_ant"] or not _ini_at(a) or a["origem"] != "ficha":
            continue
        x = next((x for x in rems if livre(x) and x["ref"] and abs((x["ref"] - fim_a).days) <= 1 and (x["decisao"] or date.min) >= fim_a), None)
        if x:
            # a mesma decisão em outras linhas com referência no período: soma, se aproxima dos dias do atestado
            outras = [y for y in rems if y is not x and livre(y) and y["decisao"] == x["decisao"] and y["ref"] and _ini_at(a) <= y["ref"] <= fim_a]
            if outras and abs(x["dias"] + sum(y["dias"] for y in outras) - a["rem"]) < abs(x["dias"] - a["rem"]):
                for y in outras:
                    y["usada"] = a["id"]
                x["usada"] = a["id"]
                x = dict(x, dias=x["dias"] + sum(y["dias"] for y in outras), linhas=len(outras) + 1)
            x["usada"], a["remicao"] = a["id"], x
            a["status"] = "CONCILIADO" if int(math.floor(x["dias"] + 1e-9)) in _alvos_a(a) or 0 <= x["dias"] - a["rem"] <= 1 + 1e-9 else "DIVERGENCIA"
    # (c) ordem cronológica: remição sem par exato entre esta emissão e a próxima -> divergência de dias
    for k, a in enumerate(ats):
        if a["remicao"] or a["rem"] is None or a["_ant"]:
            continue
        prox = min(next((b["emissao"] for b in ats[k + 1:] if b["emissao"] > a["emissao"]), date.max), a["emissao"] + timedelta(days=365))
        x = next((x for x in rems if livre(x) and a["emissao"] - timedelta(days=5) <= (x["decisao"] or date.max) < prox
                  and abs(x["dias"] - math.floor(a["rem"])) <= max(3, 0.3 * a["rem"])), None)
        if x:
            # a mesma decisão lançada em várias linhas do RSPE (referências dentro do período do atestado): soma as linhas
            ss_ = [s for s in a["segs"] if s.get("ini") and s.get("fim")]
            outras = [y for y in rems if y is not x and livre(y) and y["decisao"] == x["decisao"] and y["ref"]
                      and ss_ and min(s["ini"] for s in ss_) <= y["ref"] <= max(s["fim"] for s in ss_)]
            if outras and abs(x["dias"] + sum(y["dias"] for y in outras) - a["rem"]) < abs(x["dias"] - a["rem"]):
                for y in outras + [x]:
                    y["usada"] = a["id"]
                x = dict(x, dias=x["dias"] + sum(y["dias"] for y in outras), linhas=len(outras) + 1)
                a["remicao"] = x
                a["status"] = "CONCILIADO" if int(math.floor(x["dias"] + 1e-9)) in _alvos_a(a) else "DIVERGENCIA"
                continue
            # RSPE com até 1 dia a mais que o atestado (o juízo arredondou a fração para cima): não é divergência
            x["usada"], a["remicao"], a["status"] = a["id"], x, "CONCILIADO" if 0 <= x["dias"] - a["rem"] <= 1 + 1e-9 or int(math.floor(x["dias"] + 1e-9)) in _alvos_a(a) else "DIVERGENCIA"

    # atestado só com o período (dias desconhecidos): casa pelo número; pela data de referência no fim do período (±1 dia), com a
    # decisão depois desse fim - mesmo que a ficha registre o atestado depois da decisão; ou, sem número no RSPE, com a única
    # remição livre entre a emissão e o atestado seguinte (até 180 dias)
    for k, a in enumerate(ats):
        if a["rem"] is not None or a["trab"] is not None or a["remicao"] or a["_ant"]:
            continue
        x = next((x for x in rems if livre(x) and a["numero"] and x["numero"] and x["numero"].split("/")[0].zfill(3) == a["numero"].split("/")[0].zfill(3)), None)
        fim_a = _fim_at(a)
        if not x and fim_a and _ini_at(a):
            cand = [x for x in rems if livre(x) and x["ref"] and abs((x["ref"] - fim_a).days) <= 1 and (x["decisao"] or date.min) >= fim_a]
            x = cand[0] if len(cand) == 1 else None
        if not x:
            prox = min(next((b["emissao"] for b in ats[k + 1:] if b["emissao"] > a["emissao"]), date.max), a["emissao"] + timedelta(days=180))
            cand = [x for x in rems if livre(x) and a["emissao"] - timedelta(days=5) <= (x["decisao"] or date.max) < prox]
            x = cand[0] if len(cand) == 1 else None
        if x:
            x["usada"], a["remicao"], a["status"] = a["id"], x, "CONCILIADO"

    # ENCCEJA/ENEM: remição concedida até 150 dias depois do certificado registrado na ficha é dele
    exames = []
    for ex in f.get("exames") or []:
        de = _dt(ex.get("data"))
        x = next((x for x in rems if livre(x) and de and de <= (x["decisao"] or date.min) <= de + timedelta(days=150)), None) if de else None
        if x:
            x["usada"] = "exame"
            exames.append("%s em %s: provável %s (certificado registrado em %s)" % (rs.pl(int(x["dias"]), "dia", "dias"), _f(x["decisao"]), ex.get("exame"), _f(de)))
    if exames:
        alerta("origem", "Remições atribuídas a exame (não ao trabalho): " + "; ".join(exames) + " - conferir na decisão.", None)
    # remição já concedida com a data de referência dentro do período de um atestado emitido depois (o atestado novo repete
    # trabalho já remido: "Faxina de 17/08/2018 a 29/07/2019" e 87 dias com referência em 19/07/2019): é remição parcial do
    # período - fica pendente só o que o atestado tem além dela
    # (se a remição cabe no trabalho sem atestado logo antes do período do atestado, é daquele trabalho - não é parcial)
    def _cabe_antes(x, a, ini_a):
        fins = [s["fim"] for b in ats if b is not a for s in b["segs"] if not s["inferido"] and s.get("fim") and s["fim"] < ini_a]
        g0, g1 = (max(fins) + timedelta(days=1)) if fins else (ini_exec or date.min), ini_a - timedelta(days=1)
        if g0 > g1:
            return False
        dias_ = set()
        for v in vinc:
            a0, b0 = max(v["ini"], g0), min(v["fim"] or hoje, g1)
            if a0 <= b0:
                dias_ |= _dias_set(a0, b0)
        return x["dias"] <= len(dias_) / 3.0 + max(3, 0.1 * x["dias"])
    for x in rems:
        if not livre(x) or not x["ref"] or not x["decisao"]:
            continue
        for a in ats:
            ss_ = [s for s in a["segs"] if not s["inferido"] and s.get("ini") and s.get("fim")]
            if a["status"] != "NAO_LANCADO" or not a["rem"] or a["_ant"] or a["origem"] != "ficha" or not ss_ or x["decisao"] >= a["emissao"] - timedelta(days=5):
                continue
            if any(s["ini"] <= x["ref"] <= s["fim"] for s in ss_):
                # e a remição cabe no trecho do atestado até a referência (senão é de outro período ou origem)
                ini_a = min(s["ini"] for s in ss_)
                cabe_dentro = x["dias"] <= len(_dias_set(ini_a, x["ref"])) / 3.0 + max(3, 0.1 * x["dias"])
                if cabe_dentro and not _cabe_antes(x, a, ini_a):
                    x["usada"] = "parcial:" + a["id"]
                    a.setdefault("parciais", []).append(x)
                break
    # remição sem atestado na ficha: atestado não registrado (cobertura inferida até a data de referência), desde que haja
    # trabalho no período e nenhuma outra origem possível (estudo/leitura já excluídos)
    # remição de 4 a 24 dias, múltipla de 4, sem número de atestado no RSPE: padrão da leitura (4 dias por obra) - não é atribuída
    # ao trabalho (o trabalho do período fica na estimativa, a conferir na decisão)
    for x in rems:
        if not livre(x) or not x["ref"]:
            continue
        leit = not x["numero"] and 4 <= x["dias"] <= 24 and abs(x["dias"] / 4.0 - round(x["dias"] / 4.0)) < 1e-9
        a = {"id": "rem:%s" % _f(x["decisao"]), "numero": "", "emissao": x["ref"], "segs": [{"setor_txt": "", "chave": None, "setor": "", "ini": None, "fim": None,
             "trab": None, "rem": None, "inferido": True}], "trab": None, "rem": x["dias"], "lote": True, "origem": "rspe", "texto": "",
             "remicao": x, "status": "SEM_ORIGEM" if leit else "CONCILIADO", "_ant": False}
        if leit:
            a["sem_origem"], a["leitura"] = True, True
        x["usada"] = a["id"]
        ats.append(a)
    ats.sort(key=lambda a: (max([s["fim"] for s in a["segs"] if s["fim"]] or [a["emissao"]]), a["emissao"]))

    # ---- prova em atestado: baixa tardia / vínculo sem baixa ----
    expl = [(a, s) for a in ats for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]]
    for a, s in expl:  # setor do segmento sem nome: o vínculo da ficha no período
        if not s["chave"]:
            vs = [v for v in vinc if v["ini"] <= s["fim"] and (v["fim"] or hoje) >= s["ini"]]
            if len({v["chave"] for v in vs}) == 1:
                s["chave"], s["setor"] = vs[0]["chave"], vs[0]["setor"]
    for v in vinc:
        meus = [s for _, s in expl if mesmo_setor(s["chave"], v["chave"]) and s["fim"] >= v["ini"] and s["ini"] <= (v["fim"] or hoje)]
        if not meus:
            continue
        ult = max(meus, key=lambda s: s["fim"])
        fim_at = ult["fim"]
        doc = next(a for a, s in expl if s is ult)
        if (v["fim"] or hoje) <= fim_at + timedelta(days=1):
            continue
        # prova: outro setor atestado começando logo depois (transição documentada) e nenhum atestado do setor depois
        transicao = any(s["chave"] and not mesmo_setor(s["chave"], v["chave"]) and fim_at < s["ini"] <= fim_at + timedelta(days=31) for _, s in expl)
        depois = any(mesmo_setor(s["chave"], v["chave"]) and fim_at < s["ini"] <= (v["fim"] or hoje) for _, s in expl)
        if transicao and not depois:
            alerta("baixa tardia", "Baixa tardia na ficha: %s - ficha %s, atestado %s %s. Vale a data do atestado." % (
                v["setor"], ("baixa em " + _f(v["fim_ficha"])) if v.get("fim_ficha") else "sem baixa", doc["numero"] or "não registrado na ficha", _f(fim_at)), fim_at)
            v["fim_ficha_orig"], v["fim"], v["por_prova"] = v.get("fim_ficha"), fim_at, True
        elif v.get("sem_baixa"):
            alerta("baixa", "%s: vínculo sem baixa na ficha (encerrado na véspera do novo início, %s)." % (v["setor"], _f(v["fim"] + timedelta(days=1))), v["fim"])

    # ---- cobertura: segmentos inferidos (lote, sem período, remição sem atestado) ----
    # cada atestado sem período e cada remição sem atestado cobre só o trabalho que remiu: os dias de trabalho mais próximos da
    # emissão (ou da data de referência), até os dias trabalhados (remidos x 3), com folga de 30% + 10 dias; o restante do vínculo
    # volta à estimativa. Uma remição pequena (leitura, saldo) não "cobre" anos de trabalho.
    E = sorted((s["ini"], s["fim"]) for _, s in expl)
    inferidos = []  # (início, fim, origem) do que cada atestado inferido de fato cobriu
    try:
        import rspe_ficha as rf
        tl_un = rf.linha_unidades(f)
    except Exception:
        tl_un = []

    def _un(d):
        u_ = None
        for d_, x_ in tl_un:
            if d_ <= d:
                u_ = x_
        return u_

    def _menos(x0, x1, cobs):
        livres = [(x0, x1)]
        for c0, c1 in cobs:
            nv = []
            for y0, y1 in livres:
                if c1 < y0 or c0 > y1:
                    nv.append((y0, y1))
                    continue
                if y0 < c0:
                    nv.append((y0, c0 - timedelta(days=1)))
                if c1 < y1:
                    nv.append((c1 + timedelta(days=1), y1))
            livres = nv
        return livres

    def _corta(segs, need):
        # só os dias de trabalho mais recentes, até need x 1,15 + 10 (contados da emissão / referência para trás)
        # (a estimativa conta seg.-sáb.; muitos atestados contam seg.-sex.: folga de 30% + 10 dias)
        lim = int(need * 1.3) + 10
        ds = sorted(set().union(*(_dias_set(s["ini"], s["fim"]) for s in segs if s["fim"] >= s["ini"])), reverse=True) if segs else []
        if len(ds) <= lim:
            return segs, None
        corte = ds[lim - 1]
        return [dict(s, ini=max(s["ini"], corte)) for s in segs if s["fim"] >= corte], corte
    for a in sorted([a for a in ats if a["lote"] and a.get("status") != "SEM_ORIGEM"], key=lambda a: a["emissao"]):
        # início da janela: o dia seguinte à última cobertura por atestado da ficha (a remição sem atestado começa depois de qualquer
        # cobertura); o que outro atestado inferido já cobriu dentro dela fica de fora (nada é coberto duas vezes)
        cobs = E + [(c0, c1) for c0, c1, o_ in inferidos if a["origem"] == "rspe" or o_ != "rspe"]
        ult_cob = max([c1 for _, c1 in cobs if c1 <= a["emissao"]] or [None])
        ja = E + [(c0, c1) for c0, c1, _o in inferidos]
        w0 = (ult_cob + timedelta(days=1)) if ult_cob else (min([v["ini"] for v in vinc] or [a["emissao"]]))
        if ini_exec and w0 < ini_exec:
            w0 = max(w0, min([v["ini"] for v in vinc if (v["fim"] or hoje) >= ini_exec] or [ini_exec]))
        w1 = a["emissao"]
        nomes = {s["chave"]: s.get("setor_txt") or "" for s in a["segs"] if s["chave"]}
        novos = []
        for v in vinc:
            a0, b0 = max(v["ini"], w0), min(v["fim"] or hoje, w1)
            if a0 <= b0 and (not nomes or any(setor_parecido(v["chave"], n) or palavra_comum(v["setor"], t) for n, t in nomes.items())):
                for y0, y1 in _menos(a0, b0, ja):
                    novos.append({"setor_txt": v["setor"], "chave": v["chave"], "setor": v["setor"], "ini": y0, "fim": y1, "trab": None, "rem": None, "inferido": True})
        need = (a["trab"] or int(round((a["rem"] or 0) * 3))) if nomes and a["origem"] != "rspe" else 0
        tem = set().union(*(_dias_set(s["ini"], s["fim"]) for s in novos)) if novos else set()
        if need and len(tem) < need - 3:
            # atestado sem período que não cabe nos setores citados ("PRENDE BEM E FAXINA com 56 dias"): cobre também os outros
            # vínculos do intervalo, da emissão para trás, até os dias trabalhados (remidos x 3) - só na mesma unidade da emissão e
            # no ano anterior a ela (não alcança dias soltos de outra unidade ou de anos antes)
            u1 = _un(w1)
            outros = {}
            for v in vinc:
                a0, b0 = max(v["ini"], w0, w1 - timedelta(days=365)), min(v["fim"] or hoje, w1)
                if a0 <= b0 and not any(n_["chave"] == v["chave"] and n_["ini"] <= b0 and n_["fim"] >= a0 for n_ in novos):
                    for y0, y1 in _menos(a0, b0, ja):
                        for d in _dias_set(y0, y1) - tem:
                            if not tl_un or _un(d) == u1:
                                outros.setdefault(d, v)
            add = {}
            for d in sorted(outros, reverse=True):
                if len(tem) >= need:
                    break
                tem.add(d)
                add.setdefault(id(outros[d]), (outros[d], []))[1].append(d)
            for v, ds in add.values():
                novos.append({"setor_txt": v["setor"], "chave": v["chave"], "setor": v["setor"], "ini": min(ds), "fim": max(ds), "trab": None, "rem": None,
                              "inferido": True, "fora_da_lista": True})
        sem_v = [t for n, t in nomes.items() if not any(setor_parecido(v["chave"], n) or palavra_comum(v["setor"], t) for v in vinc)]
        if sem_v and a["origem"] != "rspe":
            alerta("setor sem vínculo", "Atestado %s de %s cita %s sem início de trabalho registrado na ficha: o período desse setor não aparece "
                   "na ficha - conferir o atestado." % (a["numero"] or "s/n", _f(a["emissao"]), ", ".join(sem_v)), a["emissao"])
        if a["origem"] == "rspe":
            # teste de capacidade: a remição não pode ser maior que 1/3 dos dias de trabalho do período inferido (seg.-sáb.). Se for,
            # ela abrange atestados da ficha ainda sem par, emitidos até a decisão (153 dias = atestado 087 de 92,66 + trabalho
            # anterior): esses atestados ficam conciliados e só o restante fica como atestado não registrado. Sem nenhum trabalho no
            # período, só se a soma dos atestados fecha com a remição (diferença de até 10%)
            x = a["remicao"]
            teto = len(tem) / 3.0
            absorvidos = []
            if a["rem"] > teto + max(5, 0.15 * teto):
                soma = 0.0
                for b in sorted([b for b in ats if b["origem"] in ("ficha", "operador") and b["status"] == "NAO_LANCADO" and b["rem"] and not b.get("_ant")
                                 and x["decisao"] - timedelta(days=800) <= b["emissao"] <= x["decisao"] + timedelta(days=5)],
                                key=lambda b: b["emissao"], reverse=True):
                    p = max(0.0, b["rem"] - sum(y["dias"] for y in b.get("parciais") or []))
                    if p and soma + p <= a["rem"] + 1 + 1e-9:
                        soma += p
                        absorvidos.append(b)
                        if a["rem"] - soma <= teto + max(5, 0.15 * teto):
                            break
                if absorvidos and not novos and a["rem"] - soma > max(5, 0.1 * a["rem"]):
                    absorvidos = []  # sem trabalho no período e a soma não fecha: origem não identificada
                if absorvidos:
                    for b in absorvidos:
                        b["remicao"], b["status"], b["remicao_conjunta"] = x, "CONCILIADO", len(absorvidos) + 1
                    x["usada"] = "+".join([a["id"]] + [b["id"] for b in absorvidos])
                    alerta("capacidade", "Remição de %s em %s (sem atestado na ficha) não cabe no período sem atestado (≈ %s de trabalho até a "
                           "referência %s): atribuída também aos atestados %s (%s) - conferir na decisão." % (
                               rs.pl(int(x["dias"]), "dia", "dias"), _f(x["decisao"]), rs.pl(len(tem), "dia", "dias"), _f(x["ref"]),
                               ", ".join(b["numero"] or "s/n" for b in absorvidos), _fmtn(round(soma, 2))), x["decisao"])
                    a["rem"] = round(a["rem"] - soma, 2)
                    if a["rem"] < 1 or not novos:
                        a["status"] = "ABSORVIDA"
                        continue
                    # o restante vem do trabalho anterior aos atestados absorvidos (sem atestado nem remição)
                    ini_b = min(_ini_at(b) or b["emissao"] for b in absorvidos)
                    uc = max([c1 for _, c1 in ja if c1 < ini_b] or [None])
                    v0 = (uc + timedelta(days=1)) if uc else min([v["ini"] for v in vinc] or [ini_b])
                    if ini_exec and v0 < ini_exec:
                        v0 = ini_exec
                    for v in vinc:
                        a0, b0 = max(v["ini"], v0), min(v["fim"] or hoje, ini_b - timedelta(days=1))
                        if a0 <= b0:
                            for y0, y1 in _menos(a0, b0, ja):
                                novos.append({"setor_txt": v["setor"], "chave": v["chave"], "setor": v["setor"], "ini": y0, "fim": y1, "trab": None,
                                              "rem": None, "inferido": True})
                    tem = set().union(*(_dias_set(s["ini"], s["fim"]) for s in novos))
                    teto = len(tem) / 3.0
                if not absorvidos and a["rem"] >= 20 and len(tem) >= 30 and a["rem"] > 1.5 * teto + 10:  # só o excesso evidente num período com trabalho registrado
                    alerta("capacidade", "Remição de %s em %s (sem atestado na ficha) maior que 1/3 dos dias de trabalho do período a que o programa "
                           "a atribuiu (≈ %s de %s a %s): a remição deve abranger outro período ou atestado - conferir na decisão." % (
                               rs.pl(int(x["dias"]), "dia", "dias"), _f(x["decisao"]), rs.pl(len(tem), "dia", "dias"), _f(w0), _f(w1)), x["decisao"])
        # a cobertura não passa do trabalho remido (remidos x 3 ou trabalhados, com folga de 30% + 10 dias): o vínculo anterior volta
        # à estimativa
        need_c = a["trab"] or int(round((a["rem"] or 0) * 3))
        if novos and need_c:
            novos, corte = _corta(novos, need_c)
            if corte:
                a["cobertura_limitada"] = corte
        a["_w1"] = w1
        if a["origem"] == "rspe" and not novos:
            # remição sem atestado e sem trabalho no período: origem não identificada (estudo, leitura, ENCCEJA...)
            a["status"], a["sem_origem"] = "SEM_ORIGEM", True
            continue
        # sem vínculo da ficha na janela: o período fica não identificado e não vira cobertura (não esconde trabalho de outra unidade
        # ou época); com o primeiro vínculo depois da emissão, não há período (nunca início depois do fim)
        a["segs"] = novos or [{"setor_txt": "", "chave": None, "setor": "não identificado na ficha", "ini": w0 if w0 <= w1 else None,
                               "fim": w1 if w0 <= w1 else None, "trab": None, "rem": None, "inferido": True, "sem_vinculo": True}]
        if a["trab"] and novos:
            cap = sum((s["fim"] - s["ini"]).days + 1 for s in a["segs"])
            if a["trab"] > cap:
                alerta("capacidade", "Atestado %s: %s dias trabalhados não cabem nos períodos inferidos da ficha (%s dias corridos de %s a %s) - conferir o período no atestado." % (
                    a["numero"] or "s/n", a["trab"], cap, _f(w0), _f(w1)), a["emissao"])
        inferidos += [(s["ini"], s["fim"], a["origem"]) for s in novos]
    # plausibilidade dos atestados sem período ainda sem remição: remidos acima de 1/3 dos dias de trabalho possíveis desde a
    # cobertura anterior por atestado com período da ficha (ou desde o início da custódia) até a emissão, descontados os remidos dos
    # outros atestados sem período emitidos no mesmo intervalo (que dividem esses dias; a emissão de um deles não é o fim do que
    # cobriu) - o valor é conferido no atestado e só o possível conta como exato (rspe_ficha.remicao_detalhada)
    for a in ats:
        if a["origem"] != "ficha" or not a["lote"] or a["status"] != "NAO_LANCADO" or not a["rem"] or not a.get("_w1"):
            continue
        w1 = a["_w1"]
        fins_ = [s_["fim"] for b_, s_ in expl if b_["origem"] != "rspe" and s_["fim"] < a["emissao"]]
        ant = max(fins_ or [None])
        p0 = (ant + timedelta(days=1)) if ant else min([v["ini"] for v in vinc] or [w1])
        if ini_exec and p0 < ini_exec:
            p0 = ini_exec
        if p0 >= w1:
            continue
        maxd = len(_dias_set(p0, w1))
        irmaos = [b for b in ats if b is not a and b["origem"] == "ficha" and b["lote"] and b.get("rem") and b.get("status") not in ("SEM_ORIGEM", "ABSORVIDA")
                  and p0 <= b["emissao"] < a["emissao"]]
        usado = sum(min(b["rem"], b.get("teto", b["rem"])) for b in irmaos)
        cap_ = maxd / 3.0 - usado
        if a["rem"] > cap_ + max(5, 0.1 * maxd / 3.0):
            a["teto"] = max(0, int(cap_))
            alerta("plausibilidade", "Atestado %s de %s: %s remidos acima do possível - de %s a %s há ≈ %s de trabalho (seg.-sáb.)%s, no máximo "
                   "≈ %s remidos. Conferir o número no atestado; a conta usa só o possível." % (
                       a["numero"] or "s/n", _f(a["emissao"]), _fmtn(a["rem"]), _f(p0), _f(w1), rs.pl(maxd, "dia", "dias"),
                       (" e %s remidos dos atestados %s, emitidos no mesmo intervalo" % (_fmtn(round(usado, 2)), ", ".join(b["numero"] or "s/n" for b in irmaos))) if irmaos else "",
                       a["teto"]), a["emissao"])
    so = [a for a in ats if a.get("status") == "SEM_ORIGEM" and not a.get("leitura")]
    if so:
        alerta("origem", "Remições sem atestado na ficha e sem trabalho no período (origem não identificada: estudo, leitura, ENCCEJA/ENEM ou atestado de "
                         "outra unidade): %s - conferir na decisão." % "; ".join("%s em %s" % (rs.pl(int(a["rem"]), "dia", "dias"), _f(a["remicao"]["decisao"])) for a in so), None)
    so = [a for a in ats if a.get("status") == "SEM_ORIGEM" and a.get("leitura")]
    if so:
        alerta("origem", "Remições sem atestado na ficha com dias múltiplos de 4 (padrão da leitura: 4 dias por obra): %s - não foram atribuídas ao "
                         "trabalho, que fica na estimativa; conferir a origem na decisão." % "; ".join(
                             "%s em %s" % (rs.pl(int(a["rem"]), "dia", "dias"), _f(a["remicao"]["decisao"])) for a in so), None)
    ats = [a for a in ats if a.get("status") not in ("SEM_ORIGEM", "ABSORVIDA")]

    # ---- coerência da data de referência (sem desfazer o casamento) ----
    for a in ats:
        x = a.get("remicao")
        if not x or a["origem"] == "rspe":
            continue
        fim_p = max([s["fim"] for s in a["segs"] if s["fim"]] or [None]) if any(s["fim"] for s in a["segs"]) else None
        if x["ref"] and fim_p and x["ref"] < fim_p:
            alerta("ref", "Remição de %s (atestado %s): data de referência %s anterior ao fim do período (%s)." % (
                rs.pl(int(x["dias"]), "dia", "dias"), a["numero"] or "s/n", _f(x["ref"]), _f(fim_p)), x["ref"])
        if x["ref"] and x["decisao"] and x["ref"] > x["decisao"]:
            alerta("ref", "Remição de %s: data de referência %s posterior à decisão %s." % (rs.pl(int(x["dias"]), "dia", "dias"), _f(x["ref"]), _f(x["decisao"])), x["ref"])

    # ---- sobreposição entre atestados (períodos explícitos) ----
    ex2 = [(a, s) for a in ats for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]]
    for i, (a, s) in enumerate(ex2):
        for b, t in ex2[i + 1:]:
            if a is not b and s["ini"] <= t["fim"] and t["ini"] <= s["fim"] and min(s["fim"], t["fim"]) >= max(s["ini"], t["ini"]) + timedelta(days=1):
                alerta("sobreposição", "Atestados %s e %s com períodos sobrepostos (%s a %s)." % (a["numero"] or "s/n", b["numero"] or "s/n",
                                                                                              _f(max(s["ini"], t["ini"])), _f(min(s["fim"], t["fim"]))), max(s["ini"], t["ini"]))

    # ---- vínculos sobrepostos (sem prova para encerrar um deles) ----
    vv = [v for v in vinc if not ini_exec or (v["fim"] or hoje) >= ini_exec]
    for i, v in enumerate(vv):
        for w in vv[i + 1:]:
            a0, b0 = max(v["ini"], w["ini"]), min(v["fim"] or hoje, w["fim"] or hoje)
            if not mesmo_setor(v["chave"], w["chave"]) and (b0 - a0).days >= 7:
                alerta("vínculos sobrepostos", "Vínculos sobrepostos na ficha: %s e %s de %s a %s - conferir com a unidade qual setor valia (sem atestado que prove a baixa)." % (
                    v["setor"], w["setor"], _f(a0), _f(b0)), a0)

    # ---- Etapa 4: lacunas (entre segmentos explícitos do mesmo atestado e entre atestados consecutivos) ----
    pend = []
    for a in ats:
        ss = sorted([s for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]], key=lambda s: s["ini"])
        for s, t in zip(ss, ss[1:]):
            if (t["ini"] - s["fim"]).days > 7:
                g0, g1 = s["fim"] + timedelta(days=1), t["ini"] - timedelta(days=1)
                entre = (" (entre %s e %s)" % (s["setor"], t["setor"])) if s["setor"] and t["setor"] and s["setor"] != t["setor"] else \
                    (" (%s)" % (s["setor"] or t["setor"])) if s["setor"] or t["setor"] else ""
                alerta("lacuna", "Lacuna de %s a %s no atestado %s%s." % (_f(g0), _f(g1), a["numero"] or "não registrado na ficha", entre), g0)
                pend.append({"data": g0, "status": "LACUNA", "texto": "%s a %s: sem vínculo comprovado (atestado %s)" % (_f(g0), _f(g1), a["numero"] or "s/n"),
                             "acao": "verificar se houve trabalho", "cor": "amarelo"})
    exp_docs = [(a, min(s["ini"] for s in a["segs"] if s["ini"]), max(s["fim"] for s in a["segs"] if s["fim"]))
                for a in ats if not a["lote"] and any(s["ini"] for s in a["segs"]) and any(s["fim"] for s in a["segs"])]
    for (a, _, f1), (b, i2, _) in zip(exp_docs, exp_docs[1:]):
        if (i2 - f1).days > 7 and (not ini_exec or f1 >= ini_exec):
            g0, g1 = f1 + timedelta(days=1), i2 - timedelta(days=1)
            alerta("lacuna", "Lacuna de %s a %s entre os atestados %s e %s." % (_f(g0), _f(g1), a["numero"] or "s/n", b["numero"] or "s/n"), g0)
            pend.append({"data": g0, "status": "LACUNA", "texto": "%s a %s: entre os atestados %s e %s" % (_f(g0), _f(g1), a["numero"] or "s/n", b["numero"] or "s/n"),
                         "acao": "verificar se houve trabalho", "cor": "amarelo"})

    # ---- Etapa 6: trabalho sem atestado nem remição (estimativa) ----
    cob = sorted([(s["ini"], s["fim"]) for a in ats for s in a["segs"] if s["ini"] and s["fim"] and not s.get("sem_vinculo")])
    # o que cobre o vínculo até a véspera do trecho livre: explica de onde vem a data de início (que não está na ficha)
    cob_doc = {}
    for a in ats:
        for s_ in a["segs"]:
            if s_["fim"]:
                x = a.get("remicao") or {}
                cob_doc[s_["fim"]] = (("remição de %s lançada no RSPE em %s, sem atestado na ficha (o programa a atribuiu a este trabalho até "
                                       "a data de referência)" % (rs.pl(int(a["rem"] or 0), "dia", "dias"), _f(x.get("decisao") or a["emissao"])))
                                      if a["origem"] == "rspe" else "atestado %s, até %s" % (a["numero"] or "s/n", _f(s_["fim"])))

    def _origem_ini(v, x0):
        o = cob_doc.get(x0 - timedelta(days=1)) if x0 > v["ini"] else None
        return (" [início em %s: antes disso, %s]" % (_f(x0), o)) if o else ""
    sem = []
    fora = fora_da_unidade(r, hoje, f)
    aus = ausencias_ficha(evs)

    def _aus(x0, x1):
        # isolamento e saída temporária dentro do trecho: dias fora da estimativa
        return [(max(c0, x0), min(c1, x1), mot) for c0, c1, mot in aus if c0 <= x1 and c1 >= x0]
    for v in vinc:
        a0, b0 = v["ini"], v["fim"] or hoje
        if ini_exec and b0 < ini_exec:
            continue
        a0 = max(a0, ini_exec) if ini_exec else a0
        livres = [(a0, b0)]
        # fuga, soltura, livramento e regime aberto registrados no RSPE: sem trabalho a estimar
        for c0, c1, mot in fora:
            if c0 <= b0 and c1 >= a0:
                v.setdefault("fora_rspe", []).append("%s (%s a %s)" % (mot, _f(max(c0, a0)), _f(min(c1, b0))))
        for c0, c1 in cob + [(c0, c1) for c0, c1, _m in fora]:
            nv = []
            for x0, x1 in livres:
                if c1 < x0 or c0 > x1:
                    nv.append((x0, x1))
                    continue
                if x0 < c0:
                    nv.append((x0, c0 - timedelta(days=1)))
                if c1 < x1:
                    nv.append((c1 + timedelta(days=1), x1))
            livres = nv
        dd = v.get("duvida_desde")
        if dd:
            # vínculo esquecido aberto: a partir da dúvida o período fica "a conferir" (sem dias no total)
            nv = []
            for x0, x1 in livres:
                if x1 < dd:
                    nv.append((x0, x1, False))
                elif x0 >= dd:
                    nv.append((x0, x1, True))
                else:
                    nv += [(x0, dd - timedelta(days=1), False), (dd, x1, True)]
            livres3 = nv
        else:
            livres3 = [(x0, x1, False) for x0, x1 in livres]
        for x0, x1, duv in livres3:
            if (x1 - x0).days < 1:
                continue
            ex_ = _aus(x0, x1)
            n = max(0, _dias_seg_sab(x0, x1) - len({d for c0, c1, _m in ex_ for d in _dias_set(c0, c1)}))
            em_curso = v["fim"] is None and x1 == hoje
            if duv:
                sem.append({"setor": v["setor"], "ini": x0, "fim": x1, "em_curso": em_curso, "est": n, "duvida": v["duvida"],
                            "trecho": " | ".join(x for x in (v.get("txt_ini"), v.get("txt_fim")) if x)})
                pend.append({"data": x0, "status": "A_CONFERIR", "texto": "%s, %s a %s: %s - sem dias no total (≈ %s se houve trabalho)" % (
                    v["setor"], _f(x0), "hoje" if em_curso else _f(x1), v["duvida"], rs.pl(n // 3, "dia remido", "dias remidos")),
                    "acao": "Conferir com a unidade se houve trabalho no período", "cor": "cinza"})
                continue
            sem.append({"setor": v["setor"], "ini": x0, "fim": x1, "em_curso": em_curso, "est": n, "origem": _origem_ini(v, x0).strip(" []"),
                        "trecho": " | ".join(x for x in (v.get("txt_ini"), v.get("txt_fim")) if x), "ausencias": ex_})
            if em_curso and (x1 - x0).days <= 90:
                # trabalho atual há até 90 dias: o atestado do período ainda não costuma ter sido emitido - não é ausência
                pend.append({"data": x0, "status": "EM_CURSO", "texto": "%s, desde %s: trabalho em curso, atestado do período ainda não emitido "
                             "(estimativa seg.-sáb.: ≈ %s, ≈ %d remidos)" % (v["setor"], _f(x0), rs.pl(n, "dia", "dias"), n // 3),
                             "acao": "Acompanhar (pedir o atestado ao fim do trimestre)", "cor": "verde"})
                continue
            pend.append({"data": x0, "status": "SEM_ATESTADO", "texto": "%s, %s a %s: sem atestado nem remição (estimativa seg.-sáb.: ≈ %s, ≈ %d remidos)%s" % (
                v["setor"], _f(x0), "hoje (em curso)" if em_curso else _f(x1), rs.pl(n, "dia", "dias"), n // 3, _origem_ini(v, x0)),
                "acao": "Pedir atestado", "cor": "amarelo"})

    # ---- atestado sem remição sobreposto a período já remido (cumulativo): só a parte não coberta fica pendente ----
    remidos_per = [(s["ini"], s["fim"], b) for b in ats if b.get("remicao") for s in b["segs"] if not s["inferido"] and s["ini"] and s["fim"]]
    for a in ats:
        ss = [s for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"] and s["fim"] >= s["ini"]]
        if a["status"] != "NAO_LANCADO" or not a["rem"] or not ss:
            continue
        if a.get("parciais"):
            # remição já concedida dentro do período (referência antes do fim): pendente o que o atestado tem além dela
            ja_ = sum(x["dias"] for x in a["parciais"])
            a["rem_pend"] = round(max(0.0, a["rem"] - ja_), 2)
            a["cobertos_por"] = ["remição de %s em %s (referência %s)" % (rs.pl(int(x["dias"]), "dia", "dias"), _f(x["decisao"]), _f(x["ref"])) for x in a["parciais"]]
            alerta("sobreposição", "Atestado %s (%s remidos) repete período já remido: %s, com referência dentro do período do atestado. Fica "
                   "pendente só a diferença (≈ %s) - conferir na decisão anterior os dias já remidos." % (
                       a["numero"] or "s/n", _fmtn(a["rem"]), "; ".join(a["cobertos_por"]), _fmtn(a["rem_pend"])), a["emissao"])
            continue
        tot = set().union(*(_dias_set(s["ini"], s["fim"]) for s in ss))
        cob_ = [(c0, c1, b) for c0, c1, b in remidos_per if b is not a and any(c0 <= s["fim"] and c1 >= s["ini"] for s in ss)]
        if not tot or not cob_:
            continue
        coberto = {d for d in tot if any(c0 <= d <= c1 for c0, c1, _b in cob_)}
        if len(coberto) < 3 or len(coberto) < len(tot) / 2.0:
            continue  # sobreposição parcial (datas trocadas, emendas): fica só o alerta de sobreposição
        a["rem_pend"] = int(math.floor(a["rem"] * (len(tot) - len(coberto)) / len(tot) + 1e-9))
        a["cobertos_por"] = list(dict.fromkeys("atestado " + (b["numero"] or "s/n") for _c0, _c1, b in cob_))
        alerta("sobreposição", "Atestado %s (%s remidos) cobre período já remido (%s): fica pendente só a parte não coberta "
               "(≈ %s, proporcional aos dias)." % (a["numero"] or "s/n", _fmtn(a["rem"]), ", ".join(a["cobertos_por"]), _fmtn(a["rem_pend"])), a["emissao"])

    # ---- pendências dos atestados ----
    for a in ats:
        if a["status"] == "NAO_LANCADO":
            if ini_exec and all((s["fim"] or a["emissao"]) < ini_exec for s in a["segs"]):
                a["status"] = "ANTERIOR"
                continue
            # nada a requerer: o período todo já foi remido por outro atestado ou remição (parte fora do período < 1 dia) ou o máximo
            # possível no período é zero - a linha sai do vermelho (fica para conferir)
            a["zerado"] = a["rem"] is not None and (("rem_pend" in a and a["rem_pend"] < 1) or a.get("teto") == 0)
            pend.append({"data": a["emissao"], "status": "NAO_LANCADO", "texto": "Atestado %s de %s (%s remidos%s) sem remição no RSPE%s" % (
                a["numero"] or "s/n", _f(a["emissao"]), _fmtn(a["rem"]),
                ("; ≈ %s fora do período já remido (%s)" % (_fmtn(a["rem_pend"]), ", ".join(a["cobertos_por"]))) if "rem_pend" in a else "",
                (" - peticionado no SEEU em %s" % a["peticionado"]) if a.get("peticionado") else " - sem registro de peticionamento na ficha"),
                "acao": "conferir na decisão anterior os dias já remidos (nada a requerer)" if a["zerado"] else
                "requerer a apreciação (vista às partes e decisão)" if a.get("peticionado") else "verificar a juntada nos autos e pedir o peticionamento à unidade",
                "cor": "cinza" if a["zerado"] else "vermelho"})
        elif a["status"] == "DIVERGENCIA":
            pend.append({"data": a["emissao"], "status": "DIVERGENCIA", "texto": "Atestado %s: %s remidos x remição de %s no RSPE (%s)" % (
                a["numero"] or "s/n", _fmtn(a["rem"]), rs.pl(int(a["remicao"]["dias"]), "dia", "dias"), _f(a["remicao"]["decisao"])),
                "acao": "conferir a decisão e requerer a diferença" if a["remicao"]["dias"] < math.floor(a["rem"]) else "conferir a decisão", "cor": "amarelo"})
    pend.sort(key=lambda p: p["data"] or date.min)

    # ---- Etapa 5: resíduo de fração ----
    conc = [a for a in ats if a["status"] == "CONCILIADO" and a["trab"] and a["remicao"]]
    exato = sum(a["trab"] for a in conc) / 3.0
    conced = sum(int(math.floor(a["remicao"]["dias"] + 1e-9)) for a in conc)
    frac = [(a["numero"], a["rem"] - math.floor(a["rem"])) for a in conc if a["rem"] and a["rem"] - math.floor(a["rem"]) > 1e-6]
    residuo = int(math.floor(exato - conced + 1e-6)) if conc else 0
    if residuo >= 1:
        alerta("resíduo", "Resíduo de fração: %s trabalhados / 3 = %s; concedidos %s - possível resíduo de %s, conferir o entendimento do juízo (frações: %s)." % (
            sum(a["trab"] for a in conc), _fmtn(exato), conced, rs.pl(residuo, "dia", "dias"),
            "; ".join("%s: %s" % (n or "s/n", _fmtn(round(x, 2))) for n, x in frac) or "—"), None)

    # ---- tabela conciliada ----
    rot = {"CONCILIADO": ("Conciliado", "verde"), "NAO_LANCADO": ("Atestado emitido não lançado", "vermelho"),
           "DIVERGENCIA": ("Divergência de dias", "amarelo"), "ANTERIOR": ("Anterior a esta execução", "cinza")}
    tabela = []
    for a in ats:
        if a["status"] == "ANTERIOR":
            continue
        x = a.get("remicao")
        tit = ("Atestado nº %s" % a["numero"]) if a["numero"] else ("Atestado não registrado na ficha" if a["origem"] == "rspe" else "Atestado s/n")
        if a["origem"] == "operador":
            tit += " (informado por você)"
        nota = ""
        if a["lote"]:
            nota = ("períodos inferidos dos vínculos da ficha até a data de referência da remição; a ficha não registra o atestado" if a["origem"] == "rspe"
                    else "períodos inferidos da ficha; o texto do atestado não os detalha")
        tabela.append({"id": a["id"], "atestado": tit, "emissao": _f(a["emissao"]) if a["origem"] != "rspe" else "",
                       "segs": [{"setor": s["setor"] or "não identificado", "per": "%s a %s" % (_f(s["ini"]), _f(s["fim"])) if s["ini"] else "período não informado",
                                 "trab": s.get("trab"), "rem": s.get("rem"), "inferido": s["inferido"],
                                 "corrigido": ("ficha: %s" % _f(s["ini_ficha"])) if s.get("corrigido") else ""} for s in a["segs"]],
                       "trab": a["trab"], "rem": _fmtn(a["rem"]) if a["rem"] is not None else "—",
                       "rspe": rs.pl(int(x["dias"]), "dia", "dias") if x else "—", "decisao": _f(x["decisao"]) if x else "—", "ref": _f(x["ref"]) if x else "—",
                       "status": a["status"], "rot": "Sem dias a requerer: período já remido" if a.get("zerado") else rot[a["status"]][0],
                       "cor": "cinza" if a.get("zerado") else rot[a["status"]][1], "nota": nota,
                       "peticionado": a.get("peticionado", ""), "texto": a.get("texto", ""), "autos": a.get("autos", ""),
                       "autos_outros": bool(a.get("autos")) and not any(re.sub(r"\D", "", a["autos"]) == re.sub(r"\D", "", x or "")
                                                                         for x in _procs_r(r)),
                       "chave": "fd:at:%s:%s" % (a["numero"] or "s/n", _f(a["emissao"]).replace("/", "."))})
    alertas.sort(key=lambda x: x["data"] or date.min)
    return {"tabela": tabela, "pendencias": pend, "alertas": alertas, "vinculos": vinc, "atestados": ats, "remicoes": rems,
            "sem_atestado": sem, "residuo": residuo}
