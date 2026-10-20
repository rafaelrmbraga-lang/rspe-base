"""Remição na ficha disciplinar (SIAPEN) x RSPE.

Leitura (funções de leitura e de nome de setor): vínculos de trabalho da ficha (máquina de estados: aberto do início até a baixa),
atestados de trabalho (regex tolerante; vários segmentos por atestado) e os nomes de setor/empresa (chave, sinônimos, nome parecido).
Modelo da aba Ficha (7.14), sem ligar remição a atestado - o RSPE não diz a origem de cada remição:
  - comparacao: totais (remição concedida no RSPE x documentos de remição desta execução na ficha), diferença com tolerância de
    3 dias, pontos a conferir (fatos de data e o que a ficha não valora), documentos da ficha com o peticionamento;
  - trabalho_x_atestados: cada período de trabalho da ficha ligado ao atestado que o cobre (automático, possível, sugerido, sem
    atestado ou vinculado na conferência).
"""
import re
from datetime import date, timedelta

import rspe_scraper as rs

DT = r"(\d{2}[./]\d{2}[./]\d{2,4})"
SEPD = r"\s*(?:A|À|ATÉ|ATE|-)\s*"

# nomes de setor que a ficha e os atestados usam para o mesmo vínculo: base jurídica, remicao.setores_sinonimos (editável sem
# mexer no programa); a lista abaixo só vale se a base não trouxer nenhuma
ALIAS_PADRAO = [(r"\bHORTA\b|\bAGS\b", "AGS", "Ags Prestadora - Me (Horta)"),
                (r"\bPAIVA\b|\bPAICA\b|\bPIVA\b|\bLINGERIE\b|\bLANGU?ERIE\b|^FABRICA$", "PAIVA", "Paiva Lingerie"),
                (r"\bPRENDE ?BEM\b|\bPRENDEBEM|\bPRENDEDOR(?:ES)?\b", "PRENDEBEM", "Prendebem (prendedores)")]


def sinonimos():
    """Sinônimos da base jurídica; os padrões do programa (ALIAS_PADRAO) valem junto, pela mesma chave - uma cópia antiga da base ao
    lado do programa não esconde as grafias acrescentadas depois ("Paica", "Langerie", "Prendedor de roupas")."""
    try:
        import rspe_regras as rg
        lst = (rg.carregar().get("remicao") or {}).get("setores_sinonimos") or []
        out = [(x["padrao"], x["chave"], x.get("nome") or x["chave"]) for x in lst if x.get("padrao") and x.get("chave")]
    except Exception:
        out = []
    if not out:
        return ALIAS_PADRAO
    for pad, ch, disp in ALIAS_PADRAO:
        i = next((i for i, x in enumerate(out) if x[1] == ch), None)
        if i is None:
            out.append((pad, ch, disp))
        elif out[i][0] != pad:
            out[i] = ("(?:%s)|(?:%s)" % (out[i][0], pad), ch, out[i][2])
    return out


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
    return ("%d" % round(v)) if abs(v - round(v)) < 1e-9 else ("%.2f" % v).replace(".", ",")


def setor_chave(nome):
    """(chave, nome de exibição) do setor: tira prefixos ("PP - ", "EMPRESA", "SETOR DE", "FUNÇÃO") e junta as variações."""
    u = _sa(nome).strip(" ,.;:-")
    # "atividade externa na empreiteira X", "trabalho interno - X" (texto livre): o nome é X
    u = re.sub(r"^(?:A |O )?(?:ATIVIDADE|TRABALHO)(?: LABORAL)?\s+(?:EXTERNA|INTERNA|EXTERNO|INTERNO)\s*(?:-\s*|/\s*|N[AO]\s+|JUNTO A[O]?\s+)"
               r"(?:EMPREITEIRA\s+|EMP\.?\s+|EMPRESA\s+)?(?=\w{3})", "", u)
    u = re.sub(r"^(?:NA\s+|NO\s+)?(?:FUNCAO|SETOR(?: DE TRABALHO)?(?: DE)?|EMPRESA)\s+", "", u)
    u = re.sub(r"^(?:PP|CC|A1|R1)\s*-\s*", "", u).strip(" ,.;:-")
    u = re.sub(r"^EMPRESA\s+", "", u)
    u = re.sub(r"^(?:O |A )?(?:DE|DA|DO)\s+(?=\w{4})", "", u).strip(" ,.;:-")  # "(para) o de cozinha"
    for pad, ch, disp in sinonimos():
        if re.search(pad, u):
            return ch, disp
    ch = re.sub(r"\W", "", u)[:12] or "?"
    disp = com_siglas(" ".join(w.capitalize() if len(w) > 2 else w.lower() for w in u.split())) or "Setor não identificado"
    return ch, disp


# siglas que ficam em caixa alta nos nomes de setor e de unidade (unidades penais de MS e órgãos que aparecem na ficha)
SIGLAS = {"IPCG", "UP", "UPs", "PED", "PDIB", "EPJFC", "CPAC", "CPAIG", "EPFIIZ", "EPFSA", "EPRACAG", "PHAC", "PTRAN", "UMMVE", "EPFI",
          "CTAP", "AGEPEN", "SIAPEN", "SENAC", "SENAI", "SESC", "SEBRAE", "EJA", "EAD", "ENCCEJA", "ENEM", "PCE", "UPRB", "EPRB", "CPPCG"}


def com_siglas(txt):
    """Devolve em caixa alta as siglas conhecidas de um nome já em caixa de título ("Ipcg Faxina da Up" -> "IPCG Faxina da UP")."""
    return re.sub(r"\b[\wÀ-ú]+\b", lambda m: m.group(0).upper() if m.group(0).upper() in SIGLAS else m.group(0), txt or "")


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


def _palavras_proprias(t):
    """Palavras próprias de um nome de setor, no singular ("BOLAS" -> "BOLA", "PRENDEDORES" -> "PRENDEDOR"): 5 letras ou mais, ou
    4 quando é o nome inteiro ("Edyp" x "R1 - Fundição Edyp"); sem as genéricas e sem a sigla da unidade ("EPJFC", "PDIB")."""
    ws = re.findall(r"[A-Z]+", _sa(t))
    out = set()
    for w in ws:
        if w in _GENERICAS or w in _SIGLAS_UN or len(w) < 4 or (len(w) == 4 and len(ws) > 1 and w not in ("BOLA", "COPA", "OBRA")):
            continue
        out.add(re.sub(r"(?<=[A-Z]{4})(?:ES|S)$", "", w) if len(w) > 5 else re.sub(r"(?<=[A-Z]{4})S$", "", w))
    return out


# siglas de unidade que vêm coladas ao nome do setor ("FÁBRICA PRENDEBEM/EPJFC", "CELA LIVRE PV 1 / EPJFC"): não identificam o setor
_SIGLAS_UN = {"IPCG", "PDIB", "EPJFC", "CPAIG", "CPAG", "PTRAN", "PHAC", "PED", "EPRB", "UPRB", "EPMR", "EPA", "EPMC", "PSMTL", "EPRSAA", "AGEPEN",
              # e o que é comum a empresas diferentes ("CONVÊNIO PREFEITURA DE ANASTÁCIO" x "PREFEITURA DE AQUIDAUANA")
              "EIRELI", "COMERCIO", "INDUSTRIA", "PREFEITURA", "MUNICIPAL", "CONVENIO", "CONSTRUCAO", "CONSTRUCOES", "MATERIAIS"}


def palavra_comum(a, b):
    """Nomes de setor com uma palavra própria em comum ("SETOR JURIDICO" x "Auxiliar Juridico"; "PINTOR" x "Manutenção Predial - Pintor";
    "Confecção de Bolas Freegol" x "Costura de Bola"; "Edyp" x "R1 - Fundição Edyp")."""
    if _palavras_proprias(a) & _palavras_proprias(b):
        return True
    wa, wb = re.findall(r"[A-Z]+", _sa(a)), re.findall(r"[A-Z]+", _sa(b))
    return any(len(x) == 1 and len(x[0]) == 4 and x[0] not in _SIGLAS_UN and x[0] not in _GENERICAS and x[0] in y for x, y in ((wa, wb), (wb, wa)))


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
RE_SAIDA = re.compile(r"SAIDA DA UNIDADE PENAL|EVASAO|TRANSFERENCIA|\bFUGA\b|"
                      # fichas antigas (texto livre): transferência, entrada em outra unidade, evasão, livramento, nova prisão
                      r"\bTRANSFERID[OA] (?:PARA|AO|A|NO|NA)\b|^\W*(?:NESTA DATA\W*)?(?:DEU ENTRADA|ENTRADA|(?:RE)?INGRESSOU|ADENTROU) N[OA]\s+(?!SETOR|TRABALHO)|"
                      r"\bEVADI(?:U|NDO)\b|BENEFICIADO COM (?:O )?LIVRAMENTO|SAIDA .{0,30}LIVRAMENTO CONDICIONAL|POR FORCA DE PRISAO PREVENTIVA|"
                      r"POSTO EM LIBERDADE|COLOCADO EM LIBERDADE")
# soltura nas redações antigas ("BENEFICIADO COM ALVARÁ DE SOLTURA", "SAIU MEDIANTE ALVARÁ DE SOLTURA"); não conta o alvará só citado
# (parecer, consulta, "aguardando", "não liberado") - o alvará de transferência de regime não é soltura
RE_SOLTURA = re.compile(r"BENEFICIAD[OA] COM (?:O )?ALVARA DE ?SOLTURA|"
                        r"\b(?:SAIU|SAIDA|DEU SAIDA|RECEBEU|EM CUMPRIMENTO AO|POR FORCA D[OE]|MEDIANTE|ATRAVES DO)\b.{0,80}?ALVARA DE ?SOLTURA")
# (sentença ou decisão transcrita na ficha - "expeça-se alvará de soltura" - não é a saída)
RE_SOLTURA_NAO = re.compile(r"PARECER|CONSULTA|AGUARDANDO|NAO (?:FOI )?LIBERAD|NAO FOI (?:COLOCAD|POST)|SENTENCA|DECISAO|DESPACHO|JULGO|EXPECA")
_FIMNOME = r"(?:\s+-\s+(?:COMUNICACAO|CI\b|OF\b|OFICIO|DOC)|\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+DELIBERAD|\s+UTILIZANDO|\s+APENAS|\s+POR\s|\s+A PEDIDO|\s+DEVIDO|\s+COM\s|\s+NESTA\s+(?:UP|UNIDADE|PENITENCIARIA|DATA)\b|\s*/?\s*\bCI\s*N?[º°O.:\s]{0,3}\d|,|\.|\((?![A-Z][A-Z ]{2,30}\))|/INTERNAMENTE|$)"
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
           re.compile(r"PASSA A CONTAR OS DIAS TRABALHADOS\b.*?\bN[AO]\s+(?:EMPRESA\s+|SETOR(?: DE| DA| DO)?\s+)?(.+?)" + _FIMNOME),
           # "foi autorizado a exercer atividades laborais no setor de X" / "autorizado a trabalhar no setor X" (7.14; o trabalho EXTERNO
           # autorizado pelo juízo não é início: rspe_ficha._RE_EXTERNO_AUTORIZADO)
           re.compile(r"AUTORIZAD[OA] A (?:EXERCER (?:SUAS )?ATIVIDADES? LABORA(?:L|IS)|TRABALHAR|LABORAR)\s+N[AO]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?(?!TRABALHO EXTERNO)(.+?)" + _FIMNOME)]
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
# lançamento padronizado do SIAPEN (início de trabalho): o texto livre do mesmo dia costuma descrever o mesmo início
RE_ESTRUT = re.compile(r"^\W*TRABALHO:\s*INICIOU ATIVIDADE LABORAL")
RE_TROCA_FUNCAO = re.compile(r"MOTIVO:\s*(?:(?:TROCA|MUDANCA|ALTERACAO)(?: DE)? (?:FUNCAO|SETOR|ATIVIDADE)|REMANEJAMENTO)")
RE_SEM_EFEITO = re.compile(r"TORNAR SEM EFEITO O LANCAMENTO DO DIA\s+(\d{2}/\d{2}/\d{2,4}),?\s*REFERENTE AO SETOR DE TRABALHO")
# regra de reserva para o texto livre das unidades (cada época e unidade escreve de um jeito): verbo de início/fim + palavra de
# trabalho; escola, curso, cela, saúde e prisão domiciliar ficam de fora
_NAO_TRAB = re.compile(r"(?<!NAO )RETORNOU DO TRABALHO|EMBRIAGUEZ|EDUCA|PEDAGOG|SAUDE|ESCOLA|CURSO|MATRICULA|(?:DA|PARA|PARA A|NA) CELA (?!LIVRE)|CELA [IVX]+\b|CELA \d|PRISAO DOMICILIAR|PERNOITE|ADVERTENCIA|NAO RETORNOU|TESTE DE TRABALHO")
_PALAVRA_TRAB = r"(?:ATIVIDADES?\s+(?:LABORA(?:L|IS|TIVA)|INTRAMUROS)|TRABALHO|TRABALHAR|LABOR|SETOR|QUADRO|SERVICOS?|FUNCAO|EMPRESA|EMPREITEIRA|PRODUCAO|CONVENIO)"
# (também "começou a trabalhar como X", "volta a trabalhar no setor X", "foi inserido no setor X" - 7.14)
RE_INI_RESERVA = re.compile(r"\b(?:INICI\w*|REINICI\w*|RETORN(?:A|OU|AR|ANDO)\b|PASSA A (?:FAZER PARTE|EXERCER|TRABALHAR|DESEMPENHAR|DESENVOLVER|PRESTAR|LABORAR)|PASSA AO|PASSOU A \w+|"
                            r"CADASTRAD\w*|INTEGRAD\w*|REMANEJAD\w*|INCIA|(?:COMEC|VOLT)\w* A (?=TRABALHAR|LABORAR|EXERCER|PRESTAR|DESEMPENHAR)|INSERID\w*)\b.{0,60}?" + _PALAVRA_TRAB)
# (também "deixou de trabalhar", "deixa de remir pena no setor X", "saiu do setor/beneficiamento X" - 7.14)
RE_FIM_RESERVA = re.compile(r"\b(?:DESLIGA[DG]\w*|AFAST\w*|DEIX(?:A|OU) (?:DE (?:TRABALHAR|LABORAR|FAZER PARTE|EXERCER|PRESTAR|REMIR)|ATIVIDADE)|EXCLUID\w*|"
                            r"SAIU D[OA] (?:SETOR|TRABALHO|EMPRESA|BENEFICIAMENTO|OFICINA|FUNCAO)\b)\b")
_SETOR_EM = [r"\bPARA (?:O |A )?(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+|OFICINA DE\s+|FUNCAO DE\s+)?(.+?)", r"\bPASSA AO TRABALHO (?:INTERNO|EXTERNO)?\s*[-/]?\s*(.+?)",
             r"\b(?:N[OA]|AO|DO|DA) SETOR(?: DE| DA| DO)?\s+(.+?)", r"\bNA EMPRESA\s+(.+?)", r"\bNA EMPREITEIRA\s+(.+?)",
             r"\bFUNCAO DE\s+(.+?)", r"\bNA PRODUCAO DE\s+(.+?)", r"\bNO CONVENIO\s+(.+?)", r"\bNA OFICINA DE\s+(.+?)",
             # sem preposição antes de "setor" ("atividade laboral interna setor das marmitas"), "trabalhar na X", "como X" (7.14)
             r"\bSETOR (?!(?:DE |DA |DO )?TRABALHO\b)(?:DE |DA |DO |DAS |DOS )?(.+?)", r"\bTRABALHAR N[AO]\s+(?:SETOR (?:DE |DA |DO )?)?(.+?)", r"\bCOMO\s+(.+?)"]


def _setor_livre(u, remanejo=False):
    """Nome do setor num lançamento em texto livre (no remanejamento, o setor de destino, depois de "PARA"). O "setor de trabalho"
    que assina o lançamento ("conforme determinação do setor de trabalho ag. Vega") não é o setor."""
    u = re.split(r"\b(?:CONFORME|DELIBERA\w*|DETERMINA\w*|AUTORIZA\w*|ANOTACAO)\b", u)[0]
    for rx in (_SETOR_EM if remanejo else _SETOR_EM[1:]):
        m = re.search(rx + r"(?:\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+DELIBERAD|\s+POR\s|\s+A PEDIDO|\s+DEVIDO|\s+EM VIRTUDE|\s+APOS|"
                           r"\s+COM\s|\s+E PASSA|\s+NESTA\b|\s+DESTA\b|\s+DA UNIDADE\b|\s*/?\s*\bCI\s*N?[º°O.:\s]{0,3}\d|,|\.|\(|;|$)", u)
        if m and m.group(1).strip() and len(m.group(1).strip()) <= 60:
            if re.match(r"(?:DISCIPLINA|SEGURANCA|PSICO|INTELIGENCIA|PRONTUARIO|SAUDE|EDUCA)", m.group(1).strip()):
                return ""  # setor administrativo citado ("à disposição do setor de disciplina"): não é trabalho
            return m.group(1).strip()
    return ""


RE_OUTROS = RE_INI2 + RE_REMANEJ + RE_FIM2 + [RE_FIM_GERAL, RE_LIBERACAO, RE_SEM_EFEITO, RE_CONTINUA, RE_INI_RESERVA, RE_FIM_RESERVA]


def _saida_unidade(u, texto):
    """Lançamento que encerra o trabalho por sair da unidade (saída, transferência, evasão, livramento, soltura, entrada em outra
    unidade nas fichas antigas, nova prisão vinda da delegacia): o texto sem as falsas fugas (tentativa, só citada, recaptura)."""
    import rspe_ficha as rf
    uf = _sa(rf._sem_fuga_falsa(texto))
    if re.match(r"MUDANCA DE CELA", u):
        return False
    if RE_SAIDA.search(uf):
        return True
    if RE_SOLTURA.search(uf) and not RE_SOLTURA_NAO.search(uf):
        return True
    # entrada estruturada vinda da delegacia: nova prisão (a custódia anterior acabou)
    return bool(rf.RE_ENTRADA_RUA.search(texto or ""))


def _rotulo_fim(txt):
    """Termo certo para o lançamento que encerrou o vínculo (a nota da data final cita a ficha como ela é)."""
    u = _sa(txt)
    u = re.sub(r"^\d{2}/\d{2}/\d{4}\s*-\s*", "", u)
    mot = re.search(r"motivo:\s*([^,.|]+)", txt or "", re.I)
    motv = (" - motivo: " + mot.group(1).strip()) if mot and mot.group(1).strip() else ""
    if re.match(r"\W*MUDANCA DE CELA", u):
        return "mudança de cela%s" % motv
    if re.match(r"\W*SAIDA DA UNIDADE PENAL", u):
        return "saída da unidade%s" % motv
    if re.search(r"DEIXA DE TRABALHAR|DEIXOU DE TRABALHAR", u):
        return "\"deixa de trabalhar\"%s" % motv
    if re.search(r"ESCOLTA|HOSPITAL|INTERNA[CD]|SANTA CASA|\bUPA\b", u):
        return "escolta/internação hospitalar"
    if re.search(r"EVADI|EVASAO|\bFUGA\b", u) and not re.search(r"DEIXA DE TRABALHAR", u):
        return "evasão"
    if re.search(r"LIVRAMENTO", u) and not re.search(r"DEIXA DE TRABALHAR", u):
        return "livramento condicional"
    if re.search(r"TRANSFERID|TRANSFERENCIA", u) and not re.search(r"DEIXA DE TRABALHAR", u):
        return "transferência"
    if re.search(r"(?:DEU ENTRADA|ENTRADA|INGRESSOU|ADENTROU) N[OA]\s|ENTRADA NA UNIDADE PENAL", u):
        return "entrada em outra unidade"
    if re.search(r"POSTO EM LIBERDADE|COLOCADO EM LIBERDADE|ALVARA DE SOLTURA", u):
        return "soltura"
    if re.search(r"PRISAO PREVENTIVA", u):
        return "nova prisão (preventiva)"
    if re.search(r"REMANEJAD", u):
        return "remanejado para outro setor"
    if re.search(r"LIBERACAO DO SETOR", u):
        return "liberação do setor de trabalho%s" % motv
    if re.search(r"DEIXA DE TRABALHAR|DEIXOU DE TRABALHAR", u):
        return "\"deixa de trabalhar\"%s" % motv
    if re.search(r"DESLIGAD|DESLIGAMENTO", u):
        return "desligado%s" % motv
    if re.search(r"AFAST", u):
        return "afastado%s" % motv
    if re.search(r"\bSAI DO TRABALHO|RETIRADO DO TRABALHO|NAO RETORNOU DO TRABALHO", u):
        return "saída do trabalho"
    if re.search(r"EXCLUID", u):
        return "excluído do setor"
    if re.search(r"ENCERR", u):
        return "encerrou a atividade"
    return "baixa%s" % motv


def vinculos(eventos, hoje, impressao=None):
    """Vínculos por setor: aberto no início, fechado na baixa do mesmo setor. Um novo início em OUTRO setor não fecha o
    anterior (nada se encerra por inferência); novo início no MESMO setor fecha o anterior na véspera (sem baixa na ficha).
    O remanejamento ("remanejado para o setor X") encerra os vínculos abertos e abre o novo; o desligamento sem setor
    ("desligado do trabalho", "afastado do trabalho") encerra todos; a "Liberação do Setor de Trabalho" encerra todos só
    quando não vem junto da baixa de um setor no mesmo dia. Lançamento tornado sem efeito ("tornar sem efeito o lançamento
    do dia X, referente ao setor de trabalho") é ignorado. Baixa sem vínculo aberto: o vínculo encerrado pela saída da
    unidade não é reaberto; sem nenhum vínculo do setor, fica registrada como alerta (nunca como linha "baixa sem início").
    Vínculo que fica aberto até hoje sem nenhuma baixa recebe "duvida" quando foi aberto no mesmo dia de outro setor
    (provável registro duplicado) ou quando, depois dele, houve início em outro setor ou liberação do trabalho (a liberação por troca
    de função que acompanha a baixa de um setor no mesmo dia não conta): desde essa
    data o período não entra em dias (fica "a conferir").
    Lançamento com data posterior à impressão da ficha (erro de digitação: "23.12.2026" numa ficha impressa em 05/10/2026) é
    ignorado, com aviso. A baixa com outra grafia do setor ("Artsanato" x "Artesanato"; "Setor de CRINA" x "Manufatura de Crina")
    fecha o único vínculo aberto parecido; o mesmo setor aberto duas vezes no mesmo dia (estruturado e texto livre: "IPCG
    ARTESANATO" e "SETOR DE ARTESANATO") é um vínculo só."""
    abertos, fechados, avisos = {}, [], []
    if impressao:
        fut = [e for e in eventos if _dt(e.get("data")) and _dt(e.get("data")) > impressao]
        for e in fut:
            avisos.append({"tipo": "data_futura", "data": _dt(e.get("data")), "texto": e.get("texto") or ""})
        eventos = [e for e in eventos if e not in fut]
    # isolamento / disciplinar: interrupção provável do trabalho (para o "retorna a exercer" sem baixa anterior)
    disc = sorted(_dt(e.get("data")) for e in eventos if _dt(e.get("data")) and
                  re.search(r"CELA DISCIPLINAR|ISOLAD[OA]|ISOLAMENTO|REGISTRO DE FALTA|DISCIPLINAR/", _sa(e.get("texto"))))
    anulados = set()
    for e in eventos:
        m = RE_SEM_EFEITO.search(_sa(e.get("texto")))
        if m and _dt(m.group(1)):
            anulados.add(_dt(m.group(1)))
    eventos = [e for e in eventos if not (_dt(e.get("data")) in anulados and re.search(r"TRABALH|LABORA|SETOR", _sa(e.get("texto"))))]
    baixa_no_dia = {_dt(e.get("data")) for e in eventos if any(p.search(_sa(e.get("texto"))) for p in RE_FIM + RE_FIM2)}
    marcos = []  # (data, motivo): inícios e liberações que tornam duvidoso um vínculo esquecido aberto

    def _aberto_de(ch, disp=""):
        # vínculo aberto do setor: mesma chave (ou prefixo), um nome a mais do mesmo vínculo, ou - outra grafia - o único parecido
        k = next((k for k in abertos if mesmo_setor(k, ch) or any(mesmo_setor(a, ch) for a in abertos[k].get("aliases", []))), None)
        if k or not ch:
            return k
        par = [k for k in abertos if setor_parecido(k, ch) or (disp and palavra_comum(abertos[k]["setor"], disp))]
        return par[0] if len(par) == 1 else None

    def abrir(ch, disp, d, txt=""):
        if re.match(r"ESCOLA|EDUCA|ESTUD", _sa(disp)):
            return  # setor "Escola" lançado como trabalho: é estudo (lido em rspe_ficha._estudos)
        ch = next((k for k in abertos if mesmo_setor(k, ch)), ch)
        if ch in abertos and abertos[ch]["ini"] == d:
            return  # o mesmo início lançado duas vezes no dia: um vínculo só
        estrut = bool(RE_ESTRUT.search(_sa(txt)))
        dup = next((k for k in abertos if k != ch and abertos[k]["ini"] == d and (setor_parecido(k, ch) or palavra_comum(abertos[k]["setor"], disp))), None)
        if not dup:
            # o lançamento padronizado do SIAPEN ("TRABALHO: Iniciou atividade laboral, no setor de trabalho IPCG RECICLAGEM DE LIXO") e
            # o texto livre do mesmo dia ("REMANEJADO PARA O SETOR DE COLETA DE LIXO") descrevem o mesmo início: um vínculo só, ainda que
            # os nomes não se pareçam. Só quando há um único vínculo aberto naquele dia, do outro tipo de lançamento
            mesmo_dia = [k for k in abertos if k != ch and abertos[k]["ini"] == d]
            if (len(mesmo_dia) == 1 and abertos[mesmo_dia[0]].get("estrut") is not None and abertos[mesmo_dia[0]]["estrut"] != estrut
                    and not any(re.match(r"XX ?DESATIV", _sa(x_)) for x_ in (disp, abertos[mesmo_dia[0]]["setor"]))):
                dup = mesmo_dia[0]
        if dup:
            # o mesmo setor aberto duas vezes no dia com grafias diferentes (lançamento estruturado e texto livre): um vínculo só
            abertos[dup].setdefault("aliases", []).append(ch)
            return
        if ch in abertos:
            v = abertos.pop(ch)
            v.update(fim=d - timedelta(days=1), motivo_fim="sem baixa na ficha (novo início no mesmo setor)", sem_baixa=True)
            # entre o início e o novo início, outro setor começou, ou houve isolamento (o "retorna a exercer" pressupõe a saída): o
            # vínculo não ficou aberto o tempo todo - desde aí, a conferir
            outro = sorted(x for x, _m, c in marcos if v["ini"] < x < d and c != ch)
            if outro:
                v["duvida"], v["duvida_desde"] = ("sem baixa na ficha; depois houve início em outro setor em %s, antes do novo início neste "
                                                  "setor em %s" % (_f(outro[0]), _f(d))), outro[0]
            elif re.search(r"\bRETORN|\bREINICI|\bVOLT", _sa(txt)):
                dd_ = [x for x in disc if v["ini"] < x < d]
                v["duvida"], v["duvida_desde"] = ("sem baixa na ficha; a ficha registra o retorno ao setor em %s%s" % (
                    _f(d), (" depois de isolamento/registro disciplinar em %s" % _f(dd_[0])) if dd_ else "")), (dd_[0] if dd_ else v["ini"])
            fechados.append(v)
        abertos[ch] = {"chave": ch, "setor": disp, "ini": d, "fim": None, "motivo_fim": "", "fim_ficha": None, "txt_ini": "%s - %s" % (_f(d), txt),
                       "estrut": estrut}
        marcos.append((d, "início em %s" % disp, ch))

    def fechar_todos(d, motivo, txt=""):
        for ch in list(abertos):
            if abertos[ch]["ini"] > d:
                continue  # aberto no próprio dia do remanejamento (início estruturado + "remanejado para"): não fecha antes de começar
            v = abertos.pop(ch)
            v.update(fim=d, fim_ficha=d, motivo_fim=motivo, txt_fim="%s - %s" % (_f(d), txt) if txt else "")
            fechados.append(v)

    for e in eventos:
        d, u = _dt(e.get("data")), _sa(e.get("texto"))
        if not d:
            continue
        cela = u.startswith("MUDANCA DE CELA")
        if cela:
            mc = re.search(r"MOTIVO:[^,]*?DEIXA(?:R|U)? DE TRABALHAR\s+(?:N[AO]|DO|DA|EM)\s+(?:SETOR\s+(?:DE\s+|DA\s+|DO\s+)?)?([^,]+?)\s*(?:,|$)", u)
            if mc:
                ch, disp = setor_chave(mc.group(1))
                k = _aberto_de(ch, disp)
                if k:
                    v = abertos.pop(k)
                    v.update(fim=d, fim_ficha=d, motivo_fim="mudança de cela: deixa de trabalhar", txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                    fechados.append(v)
                continue
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
            if re.match(r"TRABALHO\b(?!\s+(?:EXTERNO|INTERNO)\b)", _sa(m.group(1)).strip()):
                # "DESLIGADO DO SETOR DE TRABALHO POR FALTA DE PRODUTIVIDADE": o "setor de trabalho" é o setor administrativo, não o
                # nome do posto - desligamento sem setor, encerra os vínculos abertos
                fechar_todos(d, "desligado do trabalho" + ((": " + mot.lower()) if mm else ""), e.get("texto", ""))
                continue
            ch = _aberto_de(ch, disp) or ch
            if ch in abertos:
                v = abertos.pop(ch)
                v.update(fim=d, fim_ficha=d, motivo_fim=mot, txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                fechados.append(v)
            else:
                # o vínculo do setor já encerrado, também pelo outro nome do mesmo início (texto livre e lançamento padronizado)
                ult = [v for v in fechados if mesmo_setor(v["chave"], ch) or any(mesmo_setor(a, ch) for a in v.get("aliases", []))
                       or setor_parecido(v["chave"], ch)]
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
                alvo = [k for k in abertos if ch and mesmo_setor(k, ch)] or ([_aberto_de(ch, nome)] if ch and _aberto_de(ch, nome) else []) or ([] if ch else list(abertos))
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
            elif not RE_TROCA_FUNCAO.search(u):
                # liberação junto da baixa de um setor, sem ser troca de função ("encaminhado para a disciplinar"): a pessoa deixou o
                # trabalho - o outro registro que ficou aberto (lançamento duplicado) também se encerra; o início do próprio dia fica
                for ch in [k for k in abertos if abertos[k]["ini"] < d]:
                    v = abertos.pop(ch)
                    v.update(fim=d, fim_ficha=d, motivo_fim="liberação do setor de trabalho" + ((": " + mm.group(1).strip(" .").lower()) if mm else ""),
                             txt_fim="%s - %s" % (_f(d), e.get("texto", "")))
                    fechados.append(v)
            if not (d in baixa_no_dia and RE_TROCA_FUNCAO.search(u)):
                # a liberação por troca de função que acompanha a baixa de um setor no mesmo dia é dessa baixa: não põe em dúvida o
                # trabalho novo, aberto antes em outro setor (início na Cozinha em 30/06, baixa da Cela Livre e liberação em 01/07)
                marcos.append((d, "liberação do setor de trabalho", None))
            continue
        if abertos and _saida_unidade(u, e.get("texto", "")):
            for ch in list(abertos):
                if abertos[ch]["ini"] >= d and not re.match(r"\W*SAIDA DA UNIDADE PENAL", u):
                    continue  # (entrada na unidade e início do trabalho no mesmo dia, em qualquer ordem)
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
    # o início desse outro setor. Setores simultâneos encerrados juntos pela saída não entram na dúvida. A baixa do próprio setor com
    # motivo "Saída do Presídio" segue a mesma regra: costuma ser registro tardio, lançado quando a pessoa deixa a unidade
    for v in [v for v in fechados if (v.get("por_saida") or re.search(r"SAIDA DO PRESIDIO", _sa(v.get("motivo_fim")))) and (v["fim"] - v["ini"]).days > 90]:
        dentro = sorted(w["ini"] for w in fechados if w is not v and not mesmo_setor(w["chave"], v["chave"]) and not w.get("por_saida")
                        and not re.search(r"SAIDA DO PRESIDIO", _sa(w.get("motivo_fim"))) and v["ini"] < w["ini"] and w["fim"] < v["fim"])
        if dentro:
            v["duvida"], v["duvida_desde"] = ("sem baixa na ficha (encerrado só pela saída da unidade em %s); depois houve início e baixa em "
                                              "outro setor em %s" % (_f(v["fim"]), _f(dentro[0])) if v.get("por_saida") else
                                              "baixa com motivo \"saída do presídio\" em %s (registro tardio provável); antes dela, houve início e baixa "
                                              "em outro setor em %s" % (_f(v["fim"]), _f(dentro[0]))), dentro[0]
    for v in [v for v in fechados if not v.get("duvida") and (v.get("por_saida") or re.search(r"SAIDA DO PRESIDIO|TRANSFERENCIA DE PRESIDIO|"
                                                                                           r"SAIDA DA UNIDADE", _sa(v.get("motivo_fim"))))]:
        par = [w for w in fechados if w is not v and abs((w["ini"] - v["ini"]).days) <= 1 and not w.get("por_saida") and w.get("fim_ficha")
               and w["fim"] < v["fim"] - timedelta(days=30) and not re.search(r"SAIDA DO PRESIDIO|TRANSFERENCIA DE PRESIDIO", _sa(w.get("motivo_fim")))]
        if par:
            w = min(par, key=lambda w: w["fim"])
            v["duvida"], v["duvida_desde"] = ("aberto no mesmo dia de %s (provável registro duplicado), que teve baixa em %s; este só foi "
                                              "encerrado pela saída da unidade em %s" % (w["setor"], _f(w["fim"]), _f(v["fim"]))), w["fim"] + timedelta(days=1)
    for v in abertos.values():
        dep = [(d, mot) for d, mot, ch in marcos if d > v["ini"] and ch != v["chave"]]
        if not dep:
            continue  # nada depois do início: é o trabalho atual
        if any(w is not v and w["ini"] == v["ini"] for w in out):
            v["duvida"], v["duvida_desde"] = ("aberto no mesmo dia de outro setor, sem baixa na ficha, e depois houve %s em %s (provável registro "
                                              "duplicado)" % (dep[0][1], _f(dep[0][0]))), v["ini"]
        else:
            v["duvida"], v["duvida_desde"] = "sem baixa na ficha; depois houve %s em %s" % (dep[0][1], _f(dep[0][0])), dep[0][0]
    # jornada registrada no lançamento do início ("cumprindo carga horária de segunda a sexta, das 07:30 às 13:30", "escala 12x36"): a
    # estimativa do período usa essa jornada (sem ela, segunda a sábado - LEP, art. 33)
    import rspe_ficha as _rf
    for v in out:
        cands = [e for e in eventos if _dt(e.get("data")) and abs((_dt(e.get("data")) - v["ini"]).days) <= 1
                 and re.search(r"LABORA|TRABALH|EMPRESA|SETOR", _sa(e.get("texto"))) and _rf.jornada_do_texto(e.get("texto"))]
        if not cands:
            continue
        mesmo = [w for w in out if w is not v and abs((w["ini"] - v["ini"]).days) <= 1]
        if mesmo:
            # mais de um vínculo começou no dia: só o lançamento que cita este setor
            cands = [e for e in cands if palavra_comum(v["setor"], e.get("texto")) or any(palavra_comum(a, e.get("texto")) for a in v.get("aliases", []))]
        js = {_rf.jornada_do_texto(e.get("texto")) for e in cands}
        if len(js) == 1:
            v["jornada"] = js.pop()
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
# (também "com data inicial em d e final em d", "com início em d e término em d" e "de (d) a (d)")
RE_PER = re.compile(DT + r"\)?(?:" + SEPD + r"\(?|\s*;?\s*(?:ATE\s+)?DATA FINAL\s*:?\s*|\s*,?\s*E\s+(?:DATA\s+)?(?:FINAL|TERMINO|FIM)\s*(?:EM\b|:)?\s*)" + DT)
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
    # "05 (CINCO) DIAS", "70 (SETENTA DIAS)": o extenso repete o algarismo e sai; sem algarismo antes ("Totalizando (oitenta e seis) dias
    # trabalhados"), o extenso é o número
    u = re.sub(r"(\d\s*)?\(\s*(" + _NUM_EXT + r"(?:\s+" + _NUM_EXT + r")*)\s*\)",
               lambda m: (m.group(1) + " ") if m.group(1) else (" %d " % _extenso(m.group(2)) if _extenso(m.group(2)) else " "), u)
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
    u = re.sub(r"\bFAB\.\s*(?=[A-Z])", "FABRICA ", u)  # "na Fab. Prendebem": o ponto da abreviatura não encerra o nome do setor
    u = re.sub(r"\bEMP\.\s*(?=[A-Z])", "EMPRESA ", u)
    u = re.sub(r"(\d)\s*DT\s*[/-]?\s*(\d[\d.,]*)\s*DR\b", r"\1 DIAS TRABALHADOS E \2 DIAS REMIDOS", u)  # "234DT / 78DR"
    u = re.sub(r"(\d{2}[./]\d{2}[./]\d{4})(\d{1,4}\s*DIAS)", r"\1 \2", u)  # "25.11.2020434 dias"
    u = re.sub(r"(TRABALHAD[OA]S)(\d)", r"\1 \2", u)
    u = re.sub(r"\b(\d{2}/\d{2}/)0(\d{4})\b", r"\1\2", u)  # ano digitado com 5 dígitos ("04/04/02025")
    u = re.sub(r"\b(\d{2}/\d{2}/(?:19|20)\d{2})0(?=\s|\)|,|$)", r"\1", u)  # "(30/03/2021 a 17/08/20210 totalizando": zero a mais no fim
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
    t = re.sub(r"^(?:SENDO|NA|NO|E)\s+(?=\w{3})", "", t)  # "sendo Serviços Gerais (d a d) ...": "sendo" é palavra do texto
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
    ms_ = list(re.finditer(r"(?:^|;|-|:)\s*([A-Z][A-Z /]{3,40}?)?\s*[;:-]?\s*DATA(?: INICIAL)?\s*:?\s*(\d{2}[./]\d{2}[./]\d{2,4})\s*(?:;?\s*(?:ATE\s+)?DATA FINAL\s*:?|" + SEPD + r")\s*(\d{2}[./]\d{2}[./]\d{2,4})", u))
    # outros trechos do mesmo modelo, depois de "; ": o setor seguido de vírgula ("COSTURA DE BOLA, Data inicial: d; Data Final: d"), sem
    # o rótulo "DATA" ("Costura de Bolas: de 29.07.23 à 23.10.23") ou sem o "DATA INICIAL" ("PRENDEDORES DE ROUPAS: d; DATA FINAL: d")
    _D = r"(\d{2}[./]\d{2}[./]\d{2,4})"
    for rx in (r"(?:^|;)\s*([A-Z][A-Z /]{3,40}?)\s*,\s*DATA(?: INICIAL)?\s*:?\s*" + _D + r"\s*(?:;?\s*(?:ATE\s+)?DATA FINAL\s*:?|" + SEPD + r")\s*" + _D,
               r"(?:^|;)\s*(?!DATA\b|TEMPO\b|PERIODO\b)([A-Z][A-Z /]{3,40}?)\s*:\s*(?:DE\s*)?" + _D + r"(?:" + SEPD + r"|\s*;?\s*(?:ATE\s+)?DATA FINAL\s*:?\s*)" + _D):
        ms_ += [m for m in re.finditer(rx, u) if not any(m.start() < x.end() and x.start() < m.end() for x in ms_)]
    ms_.sort(key=lambda m: m.start())
    for m in ms_:
        nome = re.sub(r"^E\s+", "", (m.group(1) or "").strip(" ;:-"))  # "...; E CELA LIVRE DATA INICIAL d": o setor é "CELA LIVRE"
        nome = "" if not nome or nome.startswith(("EMITIDO", "ATP")) else nome
        if not nome:
            nome = (segs[-1]["setor_txt"] if segs else (re.search(r"ATP\s*N\S*\s*[\d/]+\s*[;:-]?\s*(?!DATA\b|TEMPO\b|PERIODO\b)([A-Z][A-Z /]{3,40}?)\s*[;:-]", u) or [None, ""])[1])
        segs.append({"setor_txt": (nome or "").strip(), "ini": _dt(m.group(2)), "fim": _dt(m.group(3)), "trab": None, "rem": None, "inferido": False})
    if not segs:
        # "Data Inicial d até Data Final d no SETOR DE X[, Data Inicial ...]": o setor vem depois do período
        for m in re.finditer(r"DATA INICIAL\s*:?\s*" + DT + r"\s*;?\s*(?:ATE\s+)?DATA FINAL\s*:?\s*" + DT +
                             r"(?:\s*,?\s*N[OA]\s+(?:SETOR(?: DE| DA| DO)?\s+|EMPRESA\s+)?([A-Z][A-Z0-9 /&.]{1,40}?)(?=\s*(?:,|;|\.|\(|\bE\b|\bNO QUAL\b|$)))?", u):
            segs.append({"setor_txt": (m.group(3) or "").strip(), "ini": _dt(m.group(1)), "fim": _dt(m.group(2)), "trab": None, "rem": None, "inferido": False})
    if not segs:
        # "referente ao período de d a d", "período: d a d", "tempo de trabalho de d a d", "período de d d" (sem o "a"), "com início em d e
        # término em d"
        mp = re.search(r"(?:PERIODO|TRABALHO)\s*:?\s*(?:DE\s*)?" + DT + r"(?:" + SEPD + r"|\s+)" + DT, u) or re.search(DT + SEPD + DT, u) or RE_PER.search(u)
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


def _mesmo_numero(a, b):
    """Mesmo número de atestado: o número sem zeros à esquerda e, quando os dois trazem o ano (4 dígitos), o mesmo ano."""
    if not a or not b:
        return False
    pa, pb = a.split("/"), b.split("/")
    if pa[0].lstrip("0") != pb[0].lstrip("0"):
        return False
    ya = pa[1] if len(pa) > 1 and re.fullmatch(r"\d{4}", pa[1]) else ""
    yb = pb[1] if len(pb) > 1 and re.fullmatch(r"\d{4}", pb[1]) else ""
    return not (ya and yb and ya != yb)


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
                sem_nada = bool(mn and not pers and re.search(r"(?:EMITID|ENCAMINHAD|EXPEDID)\w*\s+(?:O\s+)?ATESTADO", u)
                                and not re.search(r"PETICION|PROTOCOL|SOLICIT|AGUARD|SEM EFEITO|REQUISIT|SUBSTITU|RETIFIC", u))
                if not sem_nada and (not (mn and pers) or re.search(r"SOLICIT|AGUARD|SEM EFEITO|REQUISIT", u) or (re.search(r"SUBSTITU", u) and not msub)):
                    continue
            # período único: "período (trabalhado) de d a d" / "d a d"
            mp = (re.search(r"PERIODO(?: TRABALHADO)?\s*(?:DE\s*)?" + DT + r"(?:" + SEPD + r"|\s+)" + DT, u) or re.search(DT + SEPD + DT, u)
                  or RE_PER.search(u)) if len(pers) < 2 else None
            setor = ""
            u_ = re.sub(r"SETOR DE TRABALHO\s*[-–]\s*[^.;,]*", " ", u)  # quem assina ("SETOR DE TRABALHO - PP ARAUJO - IPCG") não é o setor
            ms_ = re.search(r"(?:NA FUNCAO|FUNCAO|SETOR(?: DE)?|NA EMPRESA)\s+(.+?)(?:\s+\(|\s+DE\s+\d|\s+\d{2}/|,|\.|\s+NAO RESTANDO|\s+COM\s+\d|$)", u_)
            if ms_:
                setor = _limpa_setor(ms_.group(1).strip()) or ms_.group(1).strip()  # "ARTESANATO NO PERÍODO" -> "ARTESANATO"
            trecho = re.split(r"\s*,?\s*TOTALIZANDO|\s+COM\s+[\d.,]+\s*DIAS|\s+NAO RESTANDO", u.split("ATESTADO", 1)[-1])[0]
            lst = [] if mp else re.findall(r"(?:^|-|,|EMPRESA|SETOR(?: DE)?)\s*([A-Z0-9][A-Z0-9&.'’ ]{1,40}?)\s+(\d{2}/\d{2}/\d{4})\s+(?:A\s+|ATE\s+)?(\d{2}/\d{2}/\d{4})", trecho)
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
        if trab is None and rem is None and not any(s["ini"] for s in segs):
            # atestado registrado sem dias nem período ("foi encaminhado Atestado de trabalho prisional nº 004/2019"): entra para conferir
            # (sem dias), mas não cobre período nenhum
            out[-1]["sem_cobertura"] = True
        # atestado de estudo no mesmo lançamento ("... 209 dias remidos. E Atestado de Trabalho 07/2018, de estudo, ... 6 dias
        # remidos"): não é trabalho, mas o juízo costuma decidir os dois juntos (215 = 209 + 6) - entra só no casamento
        me_ = re.search(r"\bE\s+(?:O\s+)?ATESTADO\b[^.;]{0,80}?\bESTUDO\b[^;]*?([\d.,]+)\s*(?:DIAS?\s*)?REMID", u)
        if me_ and rem is not None and me_.start() > u.find("REMID"):
            out[-1]["rem_estudo"] = _num(me_.group(1))
    # etapa do documento: "peticionado" no SEEU (ou protocolado/enviado aos autos) x só "emitido" pela unidade; um
    # peticionamento registrado depois com o mesmo número também conta
    for a in out:
        u = _sa(a["texto"])
        # "Enviado, via ESAJ, Atestado de Trabalho ...": envio ao juízo pelo sistema anterior ao SEEU (ESAJ) também é peticionamento
        a["peticionado"] = _f(a["emissao"]) if re.search(r"PETICION|PROTOCOLAD|ENVIAD\w*,?\s+(?:VIA|AO|PARA|NO)|JUNTAD|\b(?:VIA|NO|PELO) E-?SAJ\b", u) else ""
        a["esaj"] = bool(a["peticionado"] and re.search(r"\bE-?SAJ\b", u))
        ma = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", u)
        a["autos"] = ma.group(0) if ma else ""
    for e in eventos:
        u = re.sub(r"\s+", " ", _sa(e.get("texto")))
        if not re.search(r"PETICION|PROTOCOLAD|\b(?:VIA|NO|PELO) E-?SAJ\b", u):
            continue
        mn = RE_AT.search(u) or re.search(r"\bATP\s*N\S*\s*(\d{1,4})(?:\s*/\s*(\d{2,4}))?", u)
        dp_ = _dt(e.get("data"))
        if not mn or not dp_:
            continue
        cand = [a for a in out if not a["peticionado"] and _mesmo_numero(a["numero"], mn.group(1) + ("/" + mn.group(2) if mn.group(2) else ""))
                and dp_ >= a["emissao"]]
        if cand:  # o mesmo número em anos diferentes ("018/2024" e "018/2025"): só o atestado mais recente anterior ao peticionamento
            max(cand, key=lambda a: a["emissao"])["peticionado"] = _f(dp_)
            if re.search(r"\bE-?SAJ\b", u):
                max(cand, key=lambda a: a["emissao"])["esaj"] = True
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


def _dias_set(a, b):
    """Dias de trabalho (seg.-sáb., sem feriados) entre a e b, como conjunto."""
    import rspe_ficha as rf
    fer = set()
    for y in range(a.year, b.year + 1):
        fer |= rf.feriados(y)
    return {a + timedelta(days=k) for k in range((b - a).days + 1) if (a + timedelta(days=k)).weekday() < 6 and a + timedelta(days=k) not in fer}


RE_INT_FORA = re.compile(r"FUGA|EVAS|LIBERDADE|LIVRAMENTO|ALVARA|SOLTURA|RELAXAMENTO|FIANCA|HABEAS|DESCUMPRIMENTO|FINAL DA PRISAO|"
                         r"REGIME ABERTO|RESTRITIVA|BENEFICIO|INDULTO|^CUMPRIMENTO DA PENA")


def fora_da_unidade(r, hoje, f=None, presos=None):
    """Períodos do RSPE em que o trabalho não gera remição a estimar: interrupção da custódia por fuga, soltura ou livramento
    (até a nova prisão), período de prova do livramento e regime aberto (LEP, art. 126, caput e § 6º: no aberto só o estudo).
    A ficha prevalece quando mostra a pessoa presa: a entrada em unidade de custódia (fechado, semiaberto, provisória) encerra
    o período na véspera; no aberto e no livramento, o dia em unidade de custódia segundo a ficha também fica fora do corte.
    [(início, fim, motivo)]. presos (lista, opcional): recebe os trechos da interrupção do RSPE em que a ficha mostra a pessoa
    em unidade de custódia [(entrada, fim da interrupção, motivo)] - a custódia não muda; o trabalho nesses trechos fica a verificar."""
    import rspe_ficha as rf
    tl = rf.linha_unidades(f) if f else []
    custodia = [(d, (rf.classificar_unidade(u)[0] or "")) for d, u in tl]

    def ate_entrada(a, b, mot=""):
        ent = [d for d, c in custodia if a < d <= b and c in ("fechado", "semiaberto", "provisorio", "federal")]
        if ent and presos is not None:
            presos.append((min(ent), b, mot))
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
                out.append(ate_entrada(ab[0], d - timedelta(days=1), ab[1]) + (ab[1],))
            ab = None
    if ab:
        out.append(ate_entrada(ab[0], hoje, ab[1]) + (ab[1],))
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


RE_INT_LIBERDADE = re.compile(r"LIBERDADE|SOLTURA|ALVARA|RELAXAMENTO|FIANCA|HABEAS|CUMPRIMENTO|EXTIN|LIVRAMENTO")


def interrupcoes_liberdade(r, hoje):
    """Períodos em que o RSPE registra esta execução interrompida pela liberdade (liberdade provisória, soltura, alvará, relaxamento,
    fiança, habeas corpus, livramento, cumprimento), até o evento seguinte (nova prisão, reinício). Fuga e evasão não entram (a
    custódia pode ter seguido em outro registro). [(início, fim, motivo)]."""
    out, ab = [], None
    evs = sorted(((rs.to_date(e.get("data") or ""), e) for e in r.get("_eventos") or []), key=lambda x: x[0] or date.min)
    for d, e in evs:
        if not d:
            continue
        if "INTERRUP" in _sa(e.get("tipo")):
            if ab is None and RE_INT_LIBERDADE.search(_sa(e.get("motivo"))) and not re.search(r"FUGA|EVAS|ABANDON", _sa(e.get("motivo"))):
                ab = (d, (e.get("motivo") or "").strip().lower())
        elif ab:
            if d > ab[0]:
                out.append((ab[0], d - timedelta(days=1), ab[1]))
            ab = None
    if ab:
        out.append((ab[0], hoje, ab[1]))
    return out


def faltas_graves(r, f=None):
    """Faltas graves que podem custar até 1/3 dos dias remidos até elas (LEP, art. 127): homologadas ou pendentes no RSPE, evasões
    registradas no RSPE e faltas graves da ficha não arquivadas. [(data do fato, rótulo)], sem repetir a mesma falta (30 dias)."""
    out = []
    for i in r.get("_incidentes") or []:
        if i.get("_ficha") or "FALTA GRAVE" not in _sa(i.get("tipo")) or i.get("situacao") not in ("CONCEDIDO", "PENDENTE"):
            continue
        m = re.search(r"\d{2}/\d{2}/\d{4}", i.get("complemento") or "")
        d = (_dt(m.group(0)) if m else None) or _dt(i.get("data_referencia") or "") or _dt(i.get("data_decisao") or "")
        if d:
            out.append((d, "falta grave %s (%s)" % ("pendente de homologação" if i.get("situacao") == "PENDENTE" else "homologada", _f(d))))
    for e in r.get("_eventos") or []:
        if "INTERRUP" in _sa(e.get("tipo")) and re.search(r"FUGA|EVAS|ABANDONO", _sa(e.get("motivo"))):
            d = rs.to_date(e.get("data") or "")
            if d:
                out.append((d, "evasão (%s)" % _f(d)))
    for x in (f or {}).get("faltas") or []:
        d = _dt(x.get("data_fato") or "")
        if x.get("grave") and d and x.get("situacao") != "arquivada":
            out.append((d, "falta grave registrada na ficha, sem homologação no RSPE (%s)" % _f(d)))
    uniq = []
    for d, rot_ in sorted(out):
        if not any(abs((d - d2).days) <= 30 for d2, _r in uniq):
            uniq.append((d, rot_))
    return uniq



# --------------------------------------------------------------------------- #
# Remição (7.14): comparação por totais (RSPE x ficha) e trabalho da ficha x atestados
# O RSPE não diz de onde vem cada remição: o programa compara os totais, lista os documentos e os fatos de data, e liga
# cada período de trabalho da ficha ao atestado que o cobre (o operador confirma ou corrige). Não liga remição a atestado.
# --------------------------------------------------------------------------- #
TOL_COMPARACAO = 3.0  # diferença ficha x RSPE até 3 dias: arredondamento das frações
LACUNA_IGNORADA = 2  # trecho sem atestado de até 2 dias (fim de semana, troca de setor) não vira "sem atestado"
SUGESTAO_DIAS = 450  # atestado sem período: sugerido para o trabalho do mesmo nome iniciado até 450 dias antes da emissão
# peticionado/protocolado/juntado (não "nada a peticionar"); envio pelo ESAJ, o sistema anterior ao SEEU
RE_PETICIONADO = re.compile(r"PETICIONAD|PETICIONOU|PROTOCOLAD|PROTOCOLOU|JUNTAD|JUNTOU|\b(?:VIA|NO|PELO) E-?SAJ\b")


def _nf(v):
    """Número de dias para o texto: inteiro sem casas, fração com vírgula ("34,33")."""
    return "—" if v is None else _fmtn(round(v, 2))


def remicoes_do_rspe(r):
    """Remições concedidas e perdas de dias remidos do RSPE: {"remicoes": [{dias, decisao, ref}], "perdas": [...], concedido,
    perdido, saldo, ult_dec, ult_ref}. A origem de cada remição (trabalho, estudo, leitura, exame) não está no RSPE."""
    rem, per = [], []
    for i in r.get("_incidentes") or []:
        t = _sa(i.get("tipo"))
        if "REMI" not in t or (i.get("situacao") or "CONCEDIDO") != "CONCEDIDO":
            continue
        m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento") or "", re.I)
        if not m:
            continue
        dec = _dt(i.get("data_decisao") or "") or _dt(i.get("data_referencia") or "")
        x = {"dias": _num(m.group(1)), "decisao": dec, "ref": _dt(i.get("data_referencia") or "") or dec}
        (per if re.search(r"PERD|REVOG", t) else rem).append(x)
    rem.sort(key=lambda x: x["decisao"] or date.min)
    per.sort(key=lambda x: x["ref"] or date.min)
    conc = round(sum(x["dias"] for x in rem), 2)
    # dias perdidos: os do resumo do RSPE ("N dias remidos - P dias perdidos"); sem ele, a soma dos incidentes de perda
    perd = rs.saldo_remidos_num(r.get("saldo_remidos"))[1] or round(sum(x["dias"] for x in per), 2)
    return {"remicoes": rem, "perdas": per, "concedido": conc, "perdido": perd, "saldo": round(conc - perd, 2),
            "ult_dec": max([x["decisao"] for x in rem if x["decisao"]] or [None], key=lambda d: d or date.min),
            "ult_ref": max([x["ref"] for x in rem if x["ref"]] or [None], key=lambda d: d or date.min)}


def _nome_confere(a, b):
    """Nome de empresa/setor do atestado (a; vários separados por vírgula) confere com o do trabalho da ficha (b)? Pelas funções de
    nome de setor (setor_chave e sinônimos, mesmo_setor, setor_parecido, palavra_comum)."""
    if not a or not b:
        return False
    kb = setor_chave(b)[0]
    for x in [y.strip() for y in str(a).split(",") if y.strip()] or [a]:
        ka = setor_chave(x)[0]
        if mesmo_setor(ka, kb) or setor_parecido(ka, kb) or palavra_comum(x, b):
            return True
    return False


def chave_trabalho(setor, ini):
    """Chave estável do período de trabalho da ficha (vínculo manual): setor sem acento nem pontuação + início."""
    return "fd:vt:%s:%s" % (re.sub(r"[^A-Z0-9]", "", _sa(setor))[:40] or "SETOR", ini.strftime("%d.%m.%Y") if ini else "")


def chave_atestado(numero, emissao):
    """Chave estável do atestado da ficha (✓ Homologado e alvo do vínculo manual): número + emissão. A mesma das versões
    anteriores ("fd:at:<nº>:<dd.mm.aaaa>"): a marca antiga de conferido continua valendo como homologado."""
    return "fd:at:%s:%s" % (numero or "s/n", emissao.strftime("%d.%m.%Y") if emissao else "")


def _atestados_vinculo(f, manuais=None):
    """Atestados da ficha e os informados pela equipe ("Atestado juntado nos autos, não lançado na ficha"), com os trechos
    (início, fim, nome) e a chave estável."""
    out = []
    for a in f.get("atestados") or []:
        em = _dt(a.get("data") or "")
        segs = [(_dt(t.get("inicio")), _dt(t.get("fim")), t.get("setor") or a.get("empresa") or "") for t in a.get("trechos") or []]
        segs = [s for s in segs if s[0] and s[1] and s[0] <= s[1]]
        if not segs and _dt(a.get("periodo_inicio")) and _dt(a.get("periodo_fim")):
            segs = [(_dt(a["periodo_inicio"]), _dt(a["periodo_fim"]), a.get("empresa") or "")]
        out.append({"chave": chave_atestado(a.get("numero"), em), "num": a.get("numero") or "s/n", "emissao": em, "segs": segs,
                    "empresa": a.get("empresa") or "", "dias": a.get("dias_remidos"), "manual": False})
    for a in atestados_manuais(manuais):
        segs = [(s["ini"], s["fim"], s.get("setor_txt") or "") for s in a["segs"] if s.get("ini") and s.get("fim")]
        out.append({"chave": "fd:at:%s" % a["id"], "num": a["numero"] or "s/n", "emissao": a["emissao"], "segs": segs,
                    "empresa": ", ".join(s[2] for s in segs if s[2]), "dias": a["rem"], "manual": True})
    out.sort(key=lambda x: x["emissao"] or date.min)
    return out


def trabalho_x_atestados(f, hoje=None, manuais=None, vinculos=None, inicio=None):
    """Seção C da aba Ficha: cada período de trabalho registrado na ficha (f["trabalho"], sem os duplicados contidos em outro do mesmo
    setor) cortado pelos períodos dos atestados. Cada parte coberta liga ao atestado:
      auto     - Vinculado automaticamente: o período bate e o nome confere, ou não havia outro trabalho no mesmo período;
      possivel - Possível · confirmar: o período bate, o nome não confere e havia outro trabalho ao mesmo tempo;
      provavel - Sugerido · confirmar: parte sem atestado com período, mas há atestado sem período no texto, do mesmo nome, emitido
                 até 450 dias depois do início, e o trabalho é posterior ao último período atestado (o que vem depois da emissão
                 fica "sem atestado");
      sem      - Sem atestado: nenhuma cobertura (lacuna de até 2 dias não conta);
      manual   - Vinculado por você (vinculos: {chave do período: chave do atestado | "sem"}; vínculo de atestado que não existe
                 mais fica órfão e é ignorado).
    inicio: início desta execução (o trabalho que terminou antes fica de fora). Devolve {linhas, ats, n_vinc, n_tot, dias_sem, ult_at}."""
    hoje = hoje or date.today()
    imp = min(_dt(f.get("data_impressao") or "") or hoje, hoje)
    vinculos = vinculos or {}
    ats = _atestados_vinculo(f, manuais)
    por_chave = {a["chave"]: a for a in ats}
    ult = max([y for a in ats for (_x, y, _n) in a["segs"]] or [date.min])  # fim do último período atestado
    uni = []
    for t in sorted(f.get("trabalho") or [], key=lambda t: _dt(t.get("inicio")) or date.min):
        a, b = _dt(t.get("inicio")), _dt(t.get("fim")) or imp
        if not a or not b or b < a or (inicio and b < inicio):
            continue
        s = t.get("setor") or ""
        if any(u["a"] <= a and b <= u["b"] and re.sub(r"\W", "", _sa(u["s"])) == re.sub(r"\W", "", _sa(s)) for u in uni):
            continue  # o mesmo vínculo repetido (ou contido em outro do mesmo setor)
        uni.append({"a": a, "b": b, "s": s, "aberto": not t.get("fim"), "ext": bool(t.get("externo")), "jornada": t.get("jornada") or ""})
    linhas = []
    for u in uni:
        cob = []
        for at in ats:
            for (x, y, nome) in at["segs"]:
                ini, fim = max(x, u["a"]), min(y, u["b"])
                if ini <= fim:
                    cob.append((ini, fim, at["chave"], _nome_confere(nome or at["empresa"], u["s"])))
        cob.sort()
        cur, partes = u["a"], []
        for ini, fim, ch, nome in cob:
            if fim < cur:
                continue  # trecho já coberto por outro atestado
            if (ini - cur).days > LACUNA_IGNORADA:
                partes.append([cur, ini - timedelta(days=1), None, False])
            partes.append([max(ini, cur), fim, ch, nome])
            cur = fim + timedelta(days=1)
        if cur <= u["b"] and (u["b"] - cur).days + 1 > LACUNA_IGNORADA:
            partes.append([cur, u["b"], None, False])
        conc_ = lambda a, b: any(o is not u and o["a"] <= b and a <= o["b"] for o in uni)  # outro trabalho no mesmo período
        jun = []
        for p in partes:  # partes seguidas do mesmo atestado e com o mesmo resultado (automático ou possível): uma só
            if (jun and p[2] and jun[-1][2] == p[2] and p[0] <= jun[-1][1] + timedelta(days=1 + LACUNA_IGNORADA)
                    and (jun[-1][3] or not conc_(jun[-1][0], jun[-1][1])) == (p[3] or not conc_(p[0], p[1]))):
                jun[-1][1], jun[-1][3] = p[1], jun[-1][3] or p[3]
            else:
                jun.append(p)
        # trecho de até 2 dias coberto pelo mesmo atestado da parte vizinha (dia da troca de setor): fica com ela
        for x in [x for x in jun if x[2] and (x[1] - x[0]).days + 1 <= LACUNA_IGNORADA]:
            k = jun.index(x)
            viz = [y for y in (jun[k + 1] if k + 1 < len(jun) else None, jun[k - 1] if k else None) if y and y[2] == x[2]]
            if viz and len(jun) > 1:
                viz[0][0], viz[0][1] = min(viz[0][0], x[0]), max(viz[0][1], x[1])
                jun.remove(x)
        k = 0
        while k < len(jun):
            a, b, ch, nome = jun[k]
            k += 1
            st, sug = ("auto" if (nome or not conc_(a, b)) else "possivel") if ch else "sem", None
            if not ch and a > ult:
                cand = [at for at in ats if not at["segs"] and at["emissao"] and _nome_confere(at["empresa"], u["s"])
                        and 0 <= (at["emissao"] - a).days <= SUGESTAO_DIAS]
                if cand:
                    at = min(cand, key=lambda x: x["emissao"])
                    st, sug = "provavel", at["chave"]
                    em = at["emissao"]
                    if em < b and (b - em).days > LACUNA_IGNORADA:
                        # o atestado não cobre o que veio depois da emissão: essa parte fica sem atestado
                        jun.insert(k, [em + timedelta(days=1), b, None, False])
                        b = em
            ch_t = chave_trabalho(u["s"], a)
            man = vinculos.get(ch_t)
            confirmado_sem = False
            if man == "sem":
                st, sug, ch, confirmado_sem = "sem", None, None, True
            elif man and man in por_chave:
                st, sug, ch = "manual", None, man
            alvo = por_chave.get(ch or sug or "")
            em_curso = u["aberto"] and b == u["b"]
            linhas.append({"chave": ch_t, "local": setor_chave(u["s"])[1] if u["s"] else "Trabalho",
                           "ini": a, "fim": b, "periodo": "%s a %s%s" % (_f(a), _f(b), " (em curso na impressão da ficha)" if em_curso else ""),
                           "dias": (b - a).days + 1, "at": alvo["num"] if alvo else "", "at_chave": alvo["chave"] if alvo else "",
                           "st": st, "como": "período e nome da empresa" if nome else "período (único trabalho no período)",
                           "sem_confirmado": confirmado_sem, "em_curso": em_curso, "externo": u["ext"], "jornada": u["jornada"]})
    sem_dias = set()
    for L in linhas:
        if L["st"] == "sem":
            sem_dias |= {L["ini"] + timedelta(days=i) for i in range(L["dias"])}
    lista = [{"chave": a["chave"], "num": a["num"], "emissao": _f(a["emissao"]), "manual": a["manual"], "emp": a["empresa"],
              "per": ("período " + " e ".join("%s a %s" % (_f(x), _f(y)) for x, y, _n in a["segs"])) if a["segs"] else "sem período no texto"}
             for a in ats]
    return {"linhas": linhas, "ats": lista, "n_tot": len(linhas), "n_vinc": sum(1 for L in linhas if L["st"] in ("auto", "manual")),
            "dias_sem": len(sem_dias), "ult_at": None if ult == date.min else ult}


def _pet_atestado(f, a):
    """Registro do peticionamento do atestado na ficha: (texto, peticionado?, data do peticionamento, enviado à Defensoria?).
    Pelo lançamento do próprio atestado e por lançamento posterior que cite o mesmo número com "peticionado/protocolado/juntado"."""
    em = _dt(a.get("data") or "")
    num = _sa(a.get("numero"))
    n0, suf = num.split("/")[0].lstrip("0"), (num.split("/")[1] if "/" in num else "")
    # o número com o ano ou a sigla, quando o atestado os tem ("173/PDIB", "195/2022"): "1" sozinho casaria com qualquer texto
    rx = re.compile(r"(?<!\d)0*%s%s" % (re.escape(n0), (r"\s*/\s*" + re.escape(suf)) if suf else r"(?!\d)")) if n0 else None
    mesmo, depois = "", None
    for e in f.get("eventos") or []:
        d = _dt(e.get("data") or "")
        u = re.sub(r"\s+", " ", _sa(e.get("texto")))
        if not d or not re.search(r"ATEST|\bATP\b|\bAT\s*N", u) or (rx and not rx.search(u)):
            continue
        if d == em and not mesmo:
            mesmo = u
        elif em and d > em and RE_PETICIONADO.search(u) and rx and (depois is None or d < depois):
            depois = d
    if RE_PETICIONADO.search(mesmo):
        return "peticionado em %s" % _f(em), True, em, False
    if depois:
        return "peticionado em %s" % _f(depois), True, depois, False
    if re.search(r"ENCAMINHAD|ENVIAD|REMETID", mesmo) and "DEFENSOR" in mesmo:
        return "enviado à Defensoria em %s, sem registro de protocolo" % _f(em), False, None, True
    if re.search(r"ENVIAD\w*,?\s+(?:VIA|AO|PARA|NO)\s+(?:O\s+)?(?:JUIZ|PODER|SEEU|SISTEMA|FORUM|VARA|CARTORIO)", mesmo):
        return "peticionado em %s" % _f(em), True, em, False
    if re.search(r"PROMOTOR|\bPJ\b|MINISTERIO PUBLICO", mesmo):
        return "emitido a pedido da Promotoria em %s (a ficha não registra o protocolo)" % _f(em), False, None, False
    return "emitido em %s (a ficha não registra o peticionamento)" % _f(em), False, None, False


def _pet_texto(texto, d):
    """Peticionamento de certidão, curso, leitura ou exame pelo próprio lançamento da ficha."""
    if RE_PETICIONADO.search(re.sub(r"\s+", " ", _sa(texto))) or re.search(r"ENVIAD\w*,?\s+(?:VIA|AO|PARA|NO)\b", _sa(texto)):
        return "peticionado em %s" % _f(d), True, d
    return "registrado em %s (a ficha não registra o peticionamento)" % _f(d), False, None


def comparacao(r, f, hoje=None, manuais=None, homologados=None, trab=None):
    """Seções A, B, D e E da aba Ficha no modelo da 7.14 (sem ligar remição a atestado):
    A) totais - remição concedida no RSPE x documentos de remição desta execução na ficha (atestados, certidões e cursos com horas
       ÷ 12, leitura 4 dias por obra) e a diferença (tolerância de 3 dias), com o estimado à parte;
    B) pontos a conferir - fatos de data e o que a ficha não valora;
    D) documentos da ficha com o peticionamento e a situação factual (✓ Homologado: homologados = chaves marcadas);
    E) remições do RSPE (data, referência, dias), sem origem.
    trab: resultado de trabalho_x_atestados (o trabalho sem atestado depois do último atestado vira "pedir atestado")."""
    import rspe_ficha as _rf
    hoje = hoje or date.today()
    homologados = set(homologados or ())
    imp = min(_dt(f.get("data_impressao") or "") or hoje, hoje)
    R = remicoes_do_rspe(r)
    inicio = _rf.inicio_execucao(r)
    interr = interrupcoes_liberdade(r, hoje)
    procs = {re.sub(r"\D", "", p or "") for p in _procs_r(r)} - {""}
    ult_dec = R["ult_dec"]
    docs = []

    def fora_de(autos, ref, ini=None, fim=None):
        a_ = re.sub(r"\D", "", autos or "")
        if a_ and procs and a_ not in procs:
            return "dirigido a outros autos (%s)" % autos
        if inicio and ref and ref < inicio:
            return "anterior ao início desta execução (%s)" % _f(inicio)
        for x, y, mot in interr:
            if ini and fim and x <= ini and fim <= y:
                return "período em que esta execução estava interrompida (%s, %s a %s)" % (mot, _f(x), _f(y))
        return ""

    def doc(tipo, num, emissao, periodo, trab_, dias, pet, pet_ok, pet_data, fora, chave, defensoria=False, sem_valor=""):
        d = {"tipo": tipo, "num": num or "", "emissao": emissao, "periodo": periodo or "", "trab": trab_, "dias": dias, "pet": pet,
             "pet_ok": pet_ok, "data_ref": max([x for x in (emissao, pet_data) if x] or [None], key=lambda x: x or date.min),
             "fora": fora, "chave": chave, "hom": chave in homologados, "defensoria": defensoria, "sem_valor": sem_valor}
        docs.append(d)
        return d

    for a in f.get("atestados") or []:
        em = _dt(a.get("data") or "")
        ini, fim = _dt(a.get("periodo_inicio") or ""), _dt(a.get("periodo_fim") or "")
        pet, ok, pdt, dfn = _pet_atestado(f, a)
        doc("Atestado de trabalho", a.get("numero") or "s/n", em, ("%s a %s" % (_f(ini), _f(fim))) if ini and fim else "sem período no texto",
            a.get("dias_trabalhados") or None, float(a.get("dias_remidos") or 0) or None, pet, ok, pdt,
            fora_de(a.get("autos"), fim or em, ini, fim), chave_atestado(a.get("numero"), em), defensoria=dfn,
            sem_valor="" if a.get("dias_remidos") else "atestado sem os dias remidos no texto da ficha")
    for m_ in manuais or []:
        d_ = m_.get("dados") or {}
        rem = _num(str(d_.get("remidos") or "0").replace(",", ".")) if d_.get("remidos") else 0
        h_ = _num(str(d_.get("horas") or "0").replace(",", ".")) if d_.get("horas") else 0
        if not rem and h_ >= 12:
            rem = h_ / 12.0
        per = " a ".join(x for x in (d_.get("inicio") or "", d_.get("fim") or "") if x)
        doc("%s (informado por você)" % (d_.get("tipo") or "Outro"), d_.get("numero") or d_.get("descricao") or "",
            _dt(d_.get("emissao") or "") or _dt(d_.get("fim") or ""), per, int(_num(d_["trabalhados"])) if d_.get("trabalhados") else None,
            rem or None, "juntado nos autos (informado por você)", True, None, "", "fd:man:%s" % m_.get("id"),
            sem_valor="" if rem else "sem os dias remidos ou as horas")
    for c in f.get("certidoes_estudo") or []:
        d = _dt(c.get("data") or "")
        h = c.get("horas") or 0
        pet, ok, pdt = _pet_texto(c.get("texto"), d)
        sem_ = "" if h else "certidão sem a carga horária no texto da ficha"
        doc("Certidão de frequência escolar", ("%dº semestre de %s" % (c["semestre"], c["ano"])) if c.get("semestre") and c.get("ano") else "",
            d, "", None, (h / 12.0) if h else None, pet, ok, pdt, fora_de(c.get("autos"), d), "fd:edu:cert:%s" % c.get("data"), sem_valor=sem_)
    for c in f.get("cursos_peticionados") or []:
        d = _dt(c.get("data") or "")
        h = c.get("horas") or c.get("carga") or 0
        pet, ok, pdt = _pet_texto(c.get("texto"), d)
        doc("Curso de qualificação", ("meses " + ", ".join(c.get("meses") or [])) if c.get("meses") else "", d, ", ".join(c.get("meses") or []),
            None, (h / 12.0) if h else None, pet, ok, pdt, fora_de(c.get("autos"), d), "fd:edu:curso:%s" % c.get("data"),
            sem_valor="" if h else "curso sem a carga horária no texto da ficha")
    for x in f.get("leituras") or []:
        d = _dt(x.get("data") or "")
        # obras: as do relatório; sem elas, um por mês citado (PDIB) ou um por ciclo; sem nada disso, a ficha não dá o valor
        ob = x.get("obras") or len(x.get("meses") or []) or (1 if x.get("ciclo") else 0)
        pet, ok, pdt = _pet_texto(x.get("texto"), d)
        doc("Leitura", ("%s%s" % (rs.pl(ob, "obra", "obras") if ob else "obras não informadas", (" · ciclo " + x["ciclo"]) if x.get("ciclo") else "")),
            d, ", ".join(x.get("meses") or []) or (x.get("ref_mes") or ""), None, (4.0 * ob) if ob else None, pet, ok, pdt, fora_de("", d),
            "fd:lei:%s" % x.get("data"), sem_valor="" if ob else "relatório de leitura sem o número de obras")
    for x in f.get("exames") or []:
        d = _dt(x.get("data") or "")
        pet, ok, pdt = _pet_texto(x.get("texto") or x.get("exame"), d)
        if not ok:
            pet = "registrado em %s" % _f(d)
        doc("Exame", x.get("exame") or "", d, "", None, None, pet, ok, pdt, fora_de(x.get("autos"), d),
            "fd:exa:%s:%s" % (_rf._norm(x.get("exame") or ""), x.get("data")),
            sem_valor="o valor depende das áreas aprovadas e do nível (Res. CNJ 391/2021, art. 3º: de 25 a 133,33 dias)")
    docs.sort(key=lambda d: d["emissao"] or date.min)
    desta = [d for d in docs if not d["fora"]]
    soma = lambda L: round(sum(d["dias"] or 0 for d in L), 2)
    at_ = [d for d in desta if d["tipo"] == "Atestado de trabalho"]
    man_ = [d for d in desta if d["tipo"].endswith("(informado por você)")]
    est_ = [d for d in desta if d["tipo"] in ("Certidão de frequência escolar", "Curso de qualificação")]
    lei_ = [d for d in desta if d["tipo"] == "Leitura"]
    comp = round(soma(at_) + soma(man_) + soma(est_) + soma(lei_), 2)
    dif = round(comp - R["concedido"], 2)
    # ---- estimados (fora da conta): trabalho sem atestado depois do último atestado e estudo sem certidão ----
    ult_at = max([d["emissao"] if d["periodo"].startswith("sem período") else _dt(d["periodo"].split(" a ")[-1]) for d in at_ + man_
                  if d["emissao"]] or [None], key=lambda x: x or date.min)
    # fora da estimativa: fuga, liberdade, livramento e regime aberto do RSPE (sem trabalho a remir na unidade - LEP, art. 126, § 6º)
    fora_ = fora_da_unidade(r, imp, f)
    livre = lambda d: not any(x <= d <= y for x, y, _m in fora_)
    pedir, talvez, itens_p, itens_t, acomp = set(), set(), [], [], []
    corte = R["ult_ref"] if dif < -TOL_COMPARACAO else None  # o RSPE concedeu mais do que a ficha comprova: o trecho anterior pode já estar remido
    for L in (trab or {}).get("linhas") or []:
        if L["st"] != "sem" or (ult_at and L["fim"] <= ult_at):
            continue
        ini_ = max(L["ini"], ult_at + timedelta(days=1)) if ult_at else L["ini"]
        dias_ = {d for d in _rf.dias_jornada_set(ini_, min(L["fim"], imp), L.get("jornada") or "", L["ini"]) if livre(d)}
        antes = {d for d in dias_ if corte and d <= corte}
        if L.get("em_curso") and not antes and (hoje - ini_).days <= 90:
            # trabalho em curso há até 90 dias: o atestado do período ainda não costuma ter sido emitido - acompanhar (fora da conta)
            if dias_:
                acomp.append("%s, desde %s: ≈ %s até a impressão da ficha" % (L["local"], _f(ini_), rs.pl(len(dias_), "dia trabalhado", "dias trabalhados")))
                L["acomp_dias"] = round(len(dias_) / 3.0, 2)
            continue
        for conj, lst, tot, k_ in ((antes, itens_t, talvez, "talvez_dias"), (dias_ - antes, itens_p, pedir, "pedir_dias")):
            novos = conj - tot
            tot |= conj
            L[k_] = round(len(novos) / 3.0, 2)  # remição estimada desta linha, sem repetir dias de vínculos simultâneos
            if novos:
                lst.append("%s, %s a %s: ≈ %s" % (L["local"], _f(min(conj)), _f(max(conj)), rs.pl(len(novos), "dia trabalhado", "dias trabalhados")))
    est_estim, est_dias = [], set()
    for e in f.get("estudos") or []:
        a, b = _dt(e.get("inicio") or ""), _dt(e.get("fim") or "") or imp
        if not a or not b or b < a or (inicio and b < inicio):
            continue
        if not e.get("fim") and (imp - max(a, _dt(e.get("ult_registro_edu") or "") or a)).days > 365:
            continue  # matrícula aberta há mais de um ano sem registro escolar: a ficha não mostra frequência
        if e.get("horas"):
            est_estim.append({"txt": "%s, %s a %s: %s h declaradas na ficha ≈ %s" % (
                (e.get("curso") or "Estudo").title(), _f(a), _f(b), _nf(e["horas"]), rs.pl(int(e["horas"] // 12), "dia", "dias")), "dias": e["horas"] / 12.0, "fim": b})
            continue
        dl = {d for d in _rf.dias_jornada_set(a, b, "seg-sex") if not _rf.em_recesso(d)} - est_dias
        est_dias |= dl
        if len(dl) >= 3:
            h = len(dl) * _rf.HORAS_DIA_ESTUDO
            est_estim.append({"txt": "%s, %s a %s: ≈ %s × %d h = %d h ≈ %s" % (
                (e.get("curso") or "Estudo").title(), _f(a), _f(b), rs.pl(len(dl), "dia letivo", "dias letivos"), _rf.HORAS_DIA_ESTUDO, h,
                rs.pl(int(h // 12), "dia", "dias")), "dias": h / 12.0, "fim": b})
    acomp_dias = round(sum(L.get("acomp_dias") or 0 for L in (trab or {}).get("linhas") or []), 2)
    estim = round(len(pedir) / 3.0 + len(talvez) / 3.0 + acomp_dias + sum(x["dias"] for x in est_estim), 2)
    # ---- pontos a conferir (B) ----
    pontos = []

    def ponto(rot, cor, texto, tipo, curto=None, docs_=None):
        pontos.append({"rot": rot, "cor": cor, "texto": texto, "tipo": tipo, "curto": curto or texto, "docs": docs_ or []})

    nome_doc = lambda d: "%s%s" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") else (" · " + d["num"]) if d["num"] else "")
    dec_txt = ("da última decisão de remição do RSPE (%s)" % _f(ult_dec)) if ult_dec else "de qualquer remição no RSPE (o RSPE não tem remição concedida)"
    vivos = [d for d in desta if not d["hom"]]
    post = [d for d in vivos if d["data_ref"] and (not ult_dec or d["data_ref"] > ult_dec)]
    # vermelho: fato documental certo e com valor (atestado com os dias, sem peticionamento, posterior à última decisão)
    verm = [d for d in post if d["tipo"] == "Atestado de trabalho" and not d["pet_ok"] and d["dias"]]
    for d in verm:
        d["vermelho"] = True
    if verm:
        ponto("Sem peticionamento", "vermelho", "%s, emitido%s depois %s e sem registro de peticionamento na ficha: conferir nos autos se foi "
              "juntado; se não, pedir o peticionamento à unidade (%s)." % (
                  _lista(["%s (%s, %s dias)" % (nome_doc(d), _f(d["emissao"]), _nf(d["dias"])) for d in verm]), "s" if len(verm) > 1 else "",
                  dec_txt, rs.pl(len(verm), "documento", "documentos")), "sem_pet_posterior",
              curto="%s sem registro de peticionamento e posterior%s %s - conferir nos autos" % (
                  _lista([nome_doc(d) for d in verm]), "es" if len(verm) > 1 else "", dec_txt), docs_=verm)
    p2 = [d for d in post if d not in verm]
    if p2:
        ponto("Posterior à última remição", "amarelo", "%s: emitido%s ou peticionado%s depois %s - provável pendência: conferir nos autos se "
              "já foi apreciado." % (_lista(["%s (%s%s)" % (nome_doc(d), _f(d["data_ref"]), (", %s dias" % _nf(d["dias"])) if d["dias"] else "") for d in p2]),
                                     "s" if len(p2) > 1 else "", "s" if len(p2) > 1 else "", dec_txt), "posterior",
              curto="%s posterior%s %s" % (_lista([nome_doc(d) for d in p2]), "es" if len(p2) > 1 else "", dec_txt), docs_=p2)
    dfn = [d for d in vivos if d["defensoria"] and d not in verm]
    if dfn:
        ponto("A conferir", "amarelo", "%s: enviado à Defensoria, sem registro de protocolo na ficha - conferir se a Defensoria o juntou aos autos." % (
            _lista(["%s (%s dias, %s)" % (nome_doc(d), _nf(d["dias"]), _f(d["emissao"])) for d in dfn])), "defensoria", docs_=dfn)
    sem_pet = [d for d in vivos if not d["pet_ok"] and not d["defensoria"] and d not in post and d["tipo"] != "Exame"]
    if sem_pet:
        ponto("A conferir", "amarelo", "Sem registro de peticionamento na ficha: %s - conferir nos autos se foi juntado e apreciado." % (
            _lista(["%s (%s%s)" % (nome_doc(d), _f(d["emissao"]), (", %s dias" % _nf(d["dias"])) if d["dias"] else "") for d in sem_pet])), "sem_pet",
              docs_=sem_pet)
    for d in [d for d in vivos if d["tipo"] == "Exame"]:
        ponto("A conferir", "amarelo", "Exame: %s (registrado em %s) - %s; conferir se já foi remido e com quantas áreas." % (
            d["num"], _f(d["emissao"]), d["sem_valor"]), "exame", docs_=[d])
    sv = [d for d in vivos if d["sem_valor"] and d["tipo"] != "Exame"]
    if sv:
        ponto("A conferir", "amarelo", "Sem valor na ficha (fora da comparação): %s - conferir nos autos." % _lista(
            ["%s (%s: %s)" % (nome_doc(d), _f(d["emissao"]), d["sem_valor"]) for d in sv]), "sem_valor", docs_=sv)
    # teste de capacidade (só aviso): dias declarados x dias possíveis no período (segunda a sábado)
    for d in at_:
        ps = d["periodo"].split(" a ")
        if d["trab"] and len(ps) == 2 and _dt(ps[0]) and _dt(ps[1]):
            poss = _rf.dias_trabalho(_dt(ps[0]), _dt(ps[1]), "todos")
            if d["trab"] > poss + 2:
                ponto("Aviso", "cinza", "Atestado nº %s: %s trabalhados declarados para %s corridos no período (%s) - o atestado pode somar outro "
                      "período ou ter erro de digitação; conferir." % (d["num"], d["trab"], poss, d["periodo"]), "capacidade", docs_=[d])
    # 1/3 do atestado (LEP, art. 126, § 1º, II): conta do próprio documento - remidos acima de 1/3 (horas além da jornada?) e abaixo
    # de 1/3 com os dias trabalhados plausíveis (cabem no período): a conferir, sem valor a requerer
    for d in at_:
        ps = d["periodo"].split(" a ")
        if not (d["trab"] and d["dias"]):
            continue
        poss = _rf.dias_trabalho(_dt(ps[0]), _dt(ps[1]), "todos") if len(ps) == 2 and _dt(ps[0]) and _dt(ps[1]) else None
        if d["dias"] > d["trab"] / 3.0 + 1:
            ponto("Aviso", "cinza", "Atestado nº %s: %s remidos para %s trabalhados, acima de 1/3 (%s) - o atestado pode ter contado horas além da "
                  "jornada (LEP, art. 33) ou ter erro de digitação; conferir." % (d["num"], _nf(d["dias"]), d["trab"], _nf(d["trab"] / 3.0)), "terco_acima", docs_=[d])
        elif poss and d["trab"] <= poss + 2 and d["trab"] / 6.0 <= d["dias"] < d["trab"] / 3.0 - 1:
            ponto("A conferir", "amarelo", "Atestado nº %s: %s remidos para %s trabalhados, abaixo de 1/3 (%s) - conferir a conta do atestado e a "
                  "decisão (LEP, art. 126, § 1º, II)." % (d["num"], _nf(d["dias"]), d["trab"], _nf(d["trab"] / 3.0)), "terco_abaixo", docs_=[d])
    # afastamento do trabalho registrado na ficha: pandemia (remição ficta, STJ, Tema 1.120), acidente (continuidade, LEP, art. 126, § 4º)
    # ou saúde (a continuidade é só no acidente)
    trs = [(t, _dt(t.get("inicio") or ""), _dt(t.get("fim") or "")) for t in f.get("trabalho") or []]
    for t, a0, fim in trs:
        mf = _sa(t.get("motivo_fim"))
        if not fim or (inicio and fim < inicio):
            continue
        nome_ = setor_chave(t.get("setor") or "")[1] if t.get("setor") else "Trabalho"
        if re.search(r"COVID|PANDEMIA|CORONA ?VIRUS|SARS.?COV", mf):
            volta = min([x for _t, x, _f in trs if x and x > fim] or [None], key=lambda x: x or date.max)
            b_ = min(x for x in ((volta - timedelta(days=1)) if volta else None, date(2022, 4, 22), imp) if x)
            if b_ > fim:
                ponto("Remição ficta", "amarelo", "%s: trabalho suspenso pela pandemia de %s a %s (≈ %s de remição, estimativa de segunda a sábado até "
                      "o retorno ou o fim da emergência sanitária, 22/04/2022) - conferir com a unidade e requerer a remição ficta (STJ, Tema 1.120)." % (
                          nome_, _f(fim + timedelta(days=1)), _f(b_), _nf(_rf.dias_trabalho(fim + timedelta(days=1), b_) / 3.0)), "ficta")
        elif re.search(r"ACIDENT", mf):
            ponto("A conferir", "amarelo", "%s: afastamento por acidente de trabalho em %s - o preso impossibilitado de prosseguir no trabalho por "
                  "acidente continua a beneficiar-se da remição (LEP, art. 126, § 4º): conferir o período do afastamento e requerer a continuidade." % (
                      nome_, _f(fim)), "acidente")
        elif re.search(r"HOSPITAL|INTERNAD|INTERNACAO|SAUDE|MEDIC", mf):
            ponto("Aviso", "cinza", "%s: afastamento por saúde em %s - a continuidade da remição (LEP, art. 126, § 4º) é só no acidente: "
                  "conferir se foi acidente de trabalho." % (nome_, _f(fim)), "saude")
    if pedir:
        ponto("Pedir atestado", "amarelo", "Trabalho registrado na ficha depois do último atestado%s, sem atestado: %s (≈ %s de remição, estimativa "
              "de segunda a sábado - ou pela jornada registrada na ficha - até a impressão da ficha, %s). Pedir o atestado à unidade. Não entra na comparação." % (
                  (" e da última remição do RSPE (ref. %s)" % _f(corte)) if corte else "", "; ".join(itens_p), _nf(len(pedir) / 3.0), _f(imp)),
              "pedir_atestado", curto="trabalho depois do último atestado, sem atestado (≈ %s dias de remição): pedir atestado" % _nf(len(pedir) / 3.0))
    if acomp:
        ponto("Em curso", "cinza", "Trabalho em curso há até 90 dias, sem atestado: %s (≈ %s de remição) - o atestado do período ainda não costuma "
              "ter sido emitido: acompanhar e pedir ao fim do período. Não entra na comparação." % ("; ".join(acomp), _nf(acomp_dias)), "em_curso")
    if talvez:
        ponto("Pode já estar remido", "amarelo", "Trabalho sem atestado na ficha entre o último atestado e a última remição do RSPE (ref. %s): %s "
              "(≈ %s de remição). O RSPE já concedeu mais do que a ficha comprova: pode ter sido remido com atestado que a ficha não registra - "
              "conferir nos autos antes de pedir." % (_f(corte), "; ".join(itens_t), _nf(len(talvez) / 3.0)), "talvez_remido",
              curto="trabalho sem atestado antes da última remição: pode já estar remido - conferir")
    for x in f.get("estudo_cancelado_sem_matricula") or []:
        d_ = _dt(x.get("data") or "")
        if d_ and (not inicio or d_ >= inicio):
            ponto("Estudo a conferir", "amarelo", "A ficha registra o cancelamento de matrícula em %s, mas não a matrícula nem o período: pedir a "
                  "certidão de frequência escolar e conferir nos autos se houve remição (LEP, art. 126, § 1º, I)." % _f(d_), "estudo_sem_matricula",
                  curto="matrícula cancelada em %s sem a matrícula registrada: pedir a certidão de frequência" % _f(d_))
    for x in est_estim:
        # estudo que vai além da última decisão de remição pode estar sem remição: ponto a conferir; o anterior, só informação
        ponto("Estudo sem certidão", "amarelo" if not ult_dec or x["fim"] > ult_dec else "cinza", "%s (estimativa, sem certidão de horas na ficha) - conferir nos autos se a certidão foi juntada; se "
              "não, pedir a certidão de horas. Não entra na comparação." % x["txt"], "estudo_estimado")
    # perdas de dias remidos (LEP, art. 127): os testes da Auditoria (1/3 da remição até a falta, perda sem falta datada, perda sobre
    # remição posterior à falta, duplicidade) - regra de lei, não depende de saber a origem da remição
    if R["perdido"]:
        import rspe_auditoria as _ra
        try:
            its_ = _ra._perda_remidos(r.get("_incidentes") or [], R["perdido"], r.get("_eventos") or [])
        except Exception:
            its_ = []
        for it in its_:
            if it.get("nivel") != "info":
                ponto("Perda (art. 127)", "amarelo", "%s: %s" % (it["titulo"], it.get("detalhe") or ""), "perda", curto=it["titulo"])
    # ---- conclusão em linguagem simples ----
    if dif > TOL_COMPARACAO:
        concl = ("Verificar remição: a ficha comprova %s dias e o RSPE concedeu %s, diferença de %s dias a favor da ficha. A diferença "
                 "indica onde conferir, não o quanto requerer: conferir nos autos quais documentos ainda não foram apreciados." % (
                     _nf(comp), _nf(R["concedido"]), _nf(dif)))
    elif dif >= -TOL_COMPARACAO:
        concl = "Sem diferença: o RSPE concedeu %s dias e a ficha comprova %s (diferença dentro da tolerância de 3 dias, pelas frações)." % (
            _nf(R["concedido"]), _nf(comp))
    else:
        concl = ("Sem diferença a favor da ficha: o RSPE concedeu %s dias, mais do que a ficha comprova (%s). Os %s dias a mais vêm de documentos "
                 "que a ficha não registra ou não valora (outra unidade, penas somadas, cursos sem carga horária, exames, decisões antigas) - "
                 "informação, nada a requerer por esta conta." % (_nf(R["concedido"]), _nf(comp), _nf(-dif)))
    pouco = R["concedido"] > 1.3 * comp + TOL_COMPARACAO
    if pouco:
        concl += " Comparação pouco informativa: há remições de origem fora da ficha."
    n_p = len([p for p in pontos if p["cor"] != "cinza"])
    if n_p:
        concl += " Há %s (abaixo)." % rs.pl(n_p, "ponto a conferir", "pontos a conferir")
    # ---- situação factual de cada documento (D) ----
    for d in docs:
        if d["fora"]:
            d["sit"], d["cor"] = "À parte: " + d["fora"], "cinza"
        elif d["hom"]:
            d["sit"], d["cor"] = "Homologado (marcado na conferência)", "verde"
        elif d.get("vermelho"):
            d["sit"], d["cor"] = "Sem peticionamento e posterior à última remição", "vermelho"
        elif d in post:
            d["sit"], d["cor"] = ("Posterior à última remição (%s)" % _f(ult_dec)) if ult_dec else "Sem remição no RSPE", "amarelo"
        elif not d["pet_ok"]:
            d["sit"], d["cor"] = "Sem registro de peticionamento", "amarelo"
        else:
            d["sit"], d["cor"] = "Peticionado · conferir a decisão", "cinza"
    onde = onde_diferenca(dif, docs, post, verm, pontos, trab, ult_dec)
    return {"onde": onde, "R": R, "docs": docs, "at_desta": soma(at_), "n_desta": len(at_), "man": soma(man_), "n_man": len(man_), "est_comp": soma(est_),
            "leitura": soma(lei_), "obras": int(round(soma(lei_) / 4)), "fora": [d for d in docs if d["fora"]], "comp": comp, "dif": dif,
            "estim": estim, "dif_estim": round(dif + estim, 2), "pouco": pouco, "concl": concl, "pontos": pontos,
            "pedir_dias": len(pedir) / 3.0, "talvez_dias": len(talvez) / 3.0, "est_estim": est_estim, "impressao": imp, "inicio": inicio,
            "ult_at": ult_at, "post": post, "vermelho": verm, "faltas_127": faltas_graves(r, f)}


def _lista(itens):
    itens = [x for x in itens if x]
    return itens[0] if len(itens) == 1 else (", ".join(itens[:-1]) + " e " + itens[-1]) if itens else ""


def fatos_pendentes(N):
    """Documentos desta execução com fato certo (emitidos ou peticionados depois da última decisão de remição do RSPE, sem ✓ Homologado):
    os únicos dias que outras partes do programa (decretos, prioridade, relatórios) tratam como remição possivelmente pendente -
    sempre "a conferir nos autos". [{doc, data (fim do período ou emissão), dias, rotulo}]."""
    out = []
    for d in (N or {}).get("post") or []:
        if not d.get("dias"):
            continue
        ps = (d.get("periodo") or "").split(" a ")
        fim = _dt(ps[-1]) if len(ps) == 2 else None
        out.append({"doc": d, "data": fim or d["emissao"], "dias": d["dias"],
                    "rotulo": "%s%s (%s dias)" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") else
                                                                       (" · " + d["num"]) if d["num"] else "", _nf(d["dias"]))})
    return out


def onde_diferenca(dif, docs, post, verm, pontos, trab, ult_dec):
    """Visão inicial da aba Ficha - "Onde pode estar a diferença": até 4 linhas objetivas, cada uma com o que conferir e onde. Prioridade:
    (1) fato que explica a diferença - documento desta execução emitido ou peticionado depois da última decisão de remição (o sem
    peticionamento primeiro) e, havendo diferença a favor da ficha, o documento sem registro de peticionamento ou enviado à Defensoria;
    (2) trabalho sem atestado depois do último atestado (pedir atestado; antes da última remição, "pode já estar remido");
    (3) vínculo de trabalho a confirmar (possível ou sugerido); (4) os demais pontos a conferir. Sem nada: "Sem diferença a conferir."."""
    out = []
    dias_ = lambda v: "%s %s" % (_nf(v), "dia" if _nf(v) == "1" else "dias")
    dec = ("sem decisão de remição posterior no RSPE (última: %s)" % _f(ult_dec)) if ult_dec else "sem remição no RSPE"

    def nome(d):
        n_ = "%s%s" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") else (" · " + d["num"]) if d.get("num") else "")
        per = d.get("periodo") or ""
        return n_ + ((" de " + per) if per and not per.startswith("sem período") else "") + ((" (%s)" % dias_(d["dias"])) if d.get("dias") else "")

    for d in verm + [d for d in post if d not in verm]:
        quando = ("peticionado em %s" % _f(d["data_ref"])) if d["pet_ok"] else "emitido em %s, sem registro de peticionamento" % _f(d["emissao"])
        out.append({"t": "%s, %s, %s" % (nome(d), quando, dec), "c": "vermelho" if d in verm else "amarelo"})
    if dif > TOL_COMPARACAO:
        for d in [d for d in docs if not d["fora"] and not d["hom"] and d not in post and not d["pet_ok"] and d.get("dias")]:
            out.append({"t": "%s %s - conferir se foi juntado e apreciado" % (nome(d), "enviado à Defensoria, sem registro de protocolo" if d["defensoria"]
                                                                                else "sem registro de peticionamento"), "c": "amarelo"})
    if dif > TOL_COMPARACAO and not out:
        out.append({"t": "Diferença de %s a favor da ficha, sem documento posterior à última remição: conferir nos autos se cada atestado foi "
                         "apreciado e com quantos dias" % dias_(dif), "c": "amarelo"})
    L_ = (trab or {}).get("linhas") or []
    for L in L_:
        if L.get("pedir_dias") or L.get("talvez_dias"):
            q = []
            if L.get("pedir_dias"):
                q.append("≈ %s de remição depois da última remição: pedir atestado" % dias_(L["pedir_dias"]))
            if L.get("talvez_dias"):
                q.append("≈ %s antes %s: pode já estar remido - conferir" % (dias_(L["talvez_dias"]), "dela" if q else "da última remição"))
            out.append({"t": "Trabalho em %s de %s a %s, sem atestado (%s)" % (
                L["local"], _f(L["ini"]), "hoje (em curso)" if L.get("em_curso") else _f(L["fim"]), "; ".join(q)), "c": "amarelo"})
    conf = [L for L in L_ if L["st"] in ("possivel", "provavel")]
    if conf:
        ats = list(dict.fromkeys(L["at"] for L in conf if L["at"]))
        out.append({"t": "%s com vínculo %s: confirmar %s nº %s" % (
            rs.pl(len(conf), "período", "períodos"), "sugerido" if all(L["st"] == "provavel" for L in conf) else "possível ou sugerido"
            if any(L["st"] == "provavel" for L in conf) else "possível",
            "o atestado" if len(ats) == 1 else "os atestados", _lista(ats)), "c": "amarelo"})
    ja = {"sem_pet_posterior", "posterior", "pedir_atestado", "talvez_remido"} | ({"sem_pet", "defensoria"} if dif > TOL_COMPARACAO else set())
    for p_ in pontos:
        if p_["cor"] == "amarelo" and p_["tipo"] not in ja:
            t_ = p_["curto"]
            out.append({"t": t_[0].upper() + t_[1:], "c": "amarelo"})
    return out[:4] or [{"t": "Sem diferença a conferir.", "c": "verde"}]
