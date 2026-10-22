"""Remição na ficha disciplinar (SIAPEN) x RSPE.

Leitura (funções de leitura e de nome de setor): vínculos de trabalho da ficha (máquina de estados: aberto do início até a baixa),
atestados de trabalho (regex tolerante; vários segmentos por atestado) e os nomes de setor/empresa (chave, sinônimos, nome parecido).
Modelo da aba Ficha (7.14), sem ligar remição a atestado - o RSPE não diz a origem de cada remição:
  - comparacao: totais (remição concedida no RSPE x documentos de remição desta execução na ficha), diferença com tolerância de
    3 dias, pontos a conferir (fatos de data e o que a ficha não valora), documentos da ficha com o peticionamento;
  - trabalho_x_atestados: cada período de trabalho da ficha ligado ao atestado que o cobre (automático, possível, sugerido, sem
    atestado ou vinculado na conferência).
"""
import bisect
import itertools
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
# (7.14.5) "Atestado e Trabalho n 171/21": o "de" grafado "e" e o ano com 2 algarismos
RE_AT = re.compile(r"ATESTADO(?:\s+(?:D?E\s+)?TRABALHO)?(?:\s+PRISIONAL)?(?:\s*/?\s*[A-Z]{2,8}\s*-?(?=\s*N))?\s*,?\s*(?:N\s*[.ºO°ª]{0,2}|Nº|N°|NO\.?)?\s*[.:]?\s*(\d{1,5})(?!\d)(?!\s*DIAS?\b)(?:\s*/\s*(\d{4}|[A-Z]{2,8}|\d{2}(?![\d/])))?")
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


def ausencias_ficha(eventos):
    """(7.14.2, de volta da 7.13) Dias sem trabalho dentro do vínculo, registrados na ficha: isolamento em cela disciplinar ("isolado
    preventivamente ... por 10 dias") e saída temporária (saída e retorno confirmados, ou "devendo retornar em d"). Conjunto de datas
    (o dia do retorno conta como trabalhado)."""
    import rspe_ficha as _rf
    out, sai = set(), None
    rng = lambda a, b: {a + timedelta(days=i) for i in range((b - a).days + 1)} if a and b and a <= b else set()
    for e in eventos or []:
        d, u = _dt(e.get("data") or ""), re.sub(r"\s+", " ", _sa(e.get("texto")))
        if not d:
            continue
        if re.search(r"SAIDA CONFIRMADA DO BENEFICIO", u):
            sai = d
        elif re.search(r"RETORNO CONFIRMADO DO BENEFICIO", u) and sai:
            if d > sai and (d - sai).days <= 10:
                out |= rng(sai, d - timedelta(days=1))
            sai = None
        m = re.search(r"SAIDA TEMPORARIA.*?(?:DEVENDO RETORNAR|RETORNO PREVISTO)\D{0,40}?(\d{2}/\d{2}/\d{4})", u)
        if m and _dt(m.group(1)) and d < _dt(m.group(1)) <= d + timedelta(days=10):
            out |= rng(d, _dt(m.group(1)) - timedelta(days=1))
        m = re.search(r"(?:ISOLAD\w*|CELA DISCIPLINAR|ISOLAMENTO)\D{0,60}?(?:POR|DE)\s*(\d{1,2})\s*(?:\(\w+\)\s*)?DIAS", u)
        if m and not u.startswith("MUDANCA DE CELA") and 0 < int(m.group(1)) <= 30:
            out |= rng(d, d + timedelta(days=int(m.group(1)) - 1))
    try:
        for a, b in _rf.saidas_temporarias_retorno(eventos or []):
            if a and b and 0 < (b - a).days <= 10:
                out |= rng(a, b - timedelta(days=1))
    except Exception:
        pass
    return out


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
# peticionado/protocolado/juntado (não "nada a peticionar"); envio pelo ESAJ, o sistema anterior ao SEEU
# valor da remição por aprovação em exame (Res. CNJ 391/2021, art. 3º, p. único: base de 1.600 h no ensino fundamental e 1.200 h no
# médio, ÷ 12 = 133,33 e 100 dias, divididos pelas áreas do exame - 4 no ENCCEJA, 5 no ENEM com a redação: de 20 dias, uma área do
# ENEM, a 133,33 dias, o ENCCEJA fundamental inteiro), mais 1/3 com a conclusão certificada (LEP, art. 126, § 5º)
TXT_VALOR_EXAME = ("o valor depende das áreas aprovadas e do nível (Res. CNJ 391/2021, art. 3º: de 20 dias, uma área do ENEM, a 133,33 dias, "
                   "o ensino fundamental completo; mais 1/3 com a conclusão certificada - LEP, art. 126, § 5º)")
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
    import difflib
    kb = setor_chave(b)[0]
    # vários setores no atestado ("PRENDE BEM E PAIVA LANGUERIE"): cada um; grafia variante (LANGERIE x LINGERIE) pela semelhança
    for x in _nomes_lista(_sa(a)) or [y.strip() for y in str(a).split(",") if y.strip()] or [a]:
        ka = setor_chave(x)[0]
        if mesmo_setor(ka, kb) or setor_parecido(ka, kb) or palavra_comum(x, b):
            return True
        if ka and kb and min(len(ka), len(kb)) >= 5 and difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.85:
            return True
    return False


def _dias_seg_sab(a, b):
    """Dias de segunda a sábado de a a b (estimativa dos dias úteis possíveis de trabalho)."""
    if not a or not b or b < a:
        return 0
    n = (b - a).days + 1
    return n - sum(1 for i in range(n) if (a + timedelta(days=i)).weekday() == 6)


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


def trabalho_x_atestados(f, hoje=None, manuais=None, vinculos=None, inicio=None, reservas=None):
    """Seção C da aba Ficha: cada período de trabalho registrado na ficha (f["trabalho"], sem os duplicados contidos em outro do mesmo
    setor e sem o "setor educacional", que é estudo) cortado pelos períodos dos atestados. Cada parte coberta liga ao atestado:
      auto     - Vinculado automaticamente: o período bate e o nome confere, ou não havia outro trabalho no mesmo período;
      possivel - Possível · confirmar: o período bate, o nome não confere e havia outro trabalho ao mesmo tempo;
      provavel - Sugerido · confirmar: atestado sem período no texto. O período implícito vai do dia seguinte ao fim do atestado
                 anterior até a emissão; ficam com ele as partes sem atestado desse intervalo com o mesmo nome (cada setor do
                 atestado, separado por "E" ou vírgula, com tolerância de grafia). Sem nome que confira, ou quando os dias do
                 atestado pedem mais do que o setor nomeado comporta (o atestado só nomeia o setor final), ficam todas as partes do
                 intervalo, se os dias × 3 baterem com os dias úteis possíveis (segunda a sábado; de 75% a 110%). Com bem menos dias
                 do que o intervalo comporta, só o trecho final. O que vem depois da emissão fica "sem atestado";
      sem      - Sem atestado: nenhuma cobertura (lacuna de até 2 dias não conta);
      manual   - Vinculado por você (vinculos: {chave do período: chave do atestado | "sem"}; vínculo de atestado que não existe
                 mais fica órfão e é ignorado).
    inicio: início desta execução (o trabalho que terminou antes fica de fora). reservas: remições do RSPE sem documento na ficha
    ({ref, dias}, de comparacao); o trabalho mais próximo da referência de cada uma fica com ela, e não com o atestado sem período
    emitido depois que só o absorve pela capacidade (dias declarados maiores do que o trabalho do intervalo). Devolve {linhas, ats,
    n_vinc, n_tot, dias_sem, ult_at, inferidos} (inferidos: período implícito de cada atestado sem período, com os dias úteis possíveis)."""
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
        if re.search(r"\bEDUCACIONA", _sa(s)):
            continue  # "passa a exercer atividade no Setor Educacional": estudo, não trabalho
        if any(u["a"] <= a and b <= u["b"] and re.sub(r"\W", "", _sa(u["s"])) == re.sub(r"\W", "", _sa(s)) for u in uni):
            continue  # o mesmo vínculo repetido (ou contido em outro do mesmo setor)
        # (7.14.3) vínculo sem baixa: o fim é só a saída da unidade (ou evasão/transferência), não o desligamento do setor
        uni.append({"a": a, "b": b, "s": s, "aberto": not t.get("fim"), "ext": bool(t.get("externo")), "jornada": t.get("jornada") or "",
                    "sem_baixa": bool(t.get("fim")) and (t.get("motivo_fim") or "").startswith("saída/evasão/transferência"),
                    "baixa_tardia": _dt(t.get("baixa_tardia") or "") if t.get("fim") else None})
    blocos = []
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
                partes.append([cur, ini - timedelta(days=1), None, False, None])
            partes.append([max(ini, cur), fim, ch, nome, None])
            cur = fim + timedelta(days=1)
        if cur <= u["b"] and (u["b"] - cur).days + 1 > LACUNA_IGNORADA:
            partes.append([cur, u["b"], None, False, None])
        conc_ = lambda a, b, u=u: any(o is not u and o["a"] <= b and a <= o["b"] for o in uni)  # outro trabalho no mesmo período
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
        blocos.append((u, jun, conc_))
    # atestados sem período no texto: o período implícito (do fim do atestado anterior até a emissão), conferido pelos dias
    inferidos = {}

    def uteis(cs, a0, b0):
        dd = set()
        for _u, p in cs:
            x, y = max(p[0], a0), min(p[1], b0)
            dd |= {x + timedelta(days=i) for i in range((y - x).days + 1) if (x + timedelta(days=i)).weekday() != 6} if x <= y else set()
        return dd

    # (7.14.4) decisão do usuário: o saldo de remição sem documento cobre primeiro o trabalho mais próximo da referência da remição (do
    # mais próximo para o mais antigo, dias × 3 de segunda a sábado), ANTES de o atestado sem período emitido depois absorver o trabalho
    # do intervalo só pela capacidade; o atestado fica com o restante. (O atestado cujos dias batem com o intervalo continua com tudo.)
    reserv_ = []
    if reservas:
        import rspe_ficha as _rf
        # os mesmos dias que o saldo conta na comparação: pela jornada (segunda a sábado sem ela), fora do isolamento e da saída
        # temporária e sem os dias já cobertos por atestado com período
        aus0 = ausencias_ficha(f.get("eventos"))
        cob0 = {p[0] + timedelta(days=i) for _u, jun, _c in blocos for p in jun if p[2] for i in range((p[1] - p[0]).days + 1)}
        livres0 = sorted({d for u, jun, _c in blocos for p in jun if not p[2]
                          for d in _rf.dias_jornada_set(p[0], min(p[1], imp), u["jornada"], u["a"]) if d not in aus0 and d not in cob0})
        tomados = set()
        for x in sorted([x for x in reservas if x.get("ref") and x.get("dias")], key=lambda x: x["ref"]):
            pega = set(sorted((d for d in livres0 if d <= x["ref"] and d not in tomados), reverse=True)[:int(round(x["dias"] * 3))])
            tomados |= pega
            reserv_.append((x["ref"], pega))

    def _sem_reserva(esc, em):
        """As partes escolhidas sem os dias reservados às remições sem documento com referência anterior à emissão: a parte é cortada
        (o trecho reservado fica sem atestado, para o saldo; o resto continua com o atestado)."""
        res = set().union(*[pg for ref, pg in reserv_ if ref < em]) if reserv_ else set()
        if not res:
            return esc
        out_ = []
        for u, p in esc:
            rs_ = sorted(d for d in res if p[0] <= d <= p[1])
            if not rs_:
                out_.append((u, p))
                continue
            lo, hi = rs_[0], rs_[-1]
            if (lo - p[0]).days <= LACUNA_IGNORADA:
                lo = p[0]
            if (p[1] - hi).days <= LACUNA_IGNORADA:
                hi = p[1]
            jun = next(j for uu, j, _c in blocos if uu is u)
            k = next(i for i, x in enumerate(jun) if x is p)
            pecas = ([[p[0], lo - timedelta(days=1), None, False, None]] if lo > p[0] else []) + [[lo, hi, None, False, None]] + (
                [[hi + timedelta(days=1), p[1], None, False, None]] if hi < p[1] else [])
            jun[k:k + 1] = pecas
            out_ += [(u, q) for q in pecas if not (q[0] == lo and q[1] == hi)]
        return out_

    for at in [x for x in ats if not x["segs"] and x["emissao"]]:
        em = at["emissao"]
        ant = [max(y for _x, y, _n in o["segs"]) if o["segs"] else o["emissao"] for o in ats
               if o is not at and o["emissao"] and (o["emissao"] < em or (o["emissao"] == em and ats.index(o) < ats.index(at)))]
        s0 = (max(ant) + timedelta(days=1)) if ant else date.min
        cands = [(u, p) for u, jun, _c in blocos for p in jun if not p[2] and not p[4] and p[1] >= s0 and p[0] <= em]
        if not cands:
            continue
        nomeados = [c for c in cands if at["empresa"] and _nome_confere(at["empresa"], c[0]["s"])]
        need = float(at["dias"] or 0) * 3
        bate = lambda cs: need and 0.75 * len(uteis(cs, s0, em)) <= need <= len(uteis(cs, s0, em)) * 1.1 + 3
        # o trabalho contínuo que termina na emissão (partes encadeadas, com intervalo de até 30 dias)
        blk, ini_b = [], None
        for c in sorted(cands, key=lambda c: c[1][1], reverse=True):
            if ini_b is not None and c[1][1] < ini_b - timedelta(days=30):
                break
            blk.append(c)
            ini_b = min(ini_b or c[1][0], c[1][0])
        esc = None
        # o que bate: o trabalho contínuo até a emissão (que inclui o setor nomeado) ou só o setor nomeado - o mais próximo de dias × 3
        # ou as últimas partes com o nome (as mais recentes, inteiras, enquanto couberem nos dias do atestado)
        suf = []
        for c in sorted(nomeados, key=lambda c: c[1][1], reverse=True):
            w_c = len(uteis(suf + [c], s0, em))
            if need and suf and w_c > need * 1.1 + 3:
                break
            suf.append(c)
        opc = [cs for cs in ((blk if (not at["empresa"] or any(c in nomeados for c in blk)) else []), nomeados, suf) if cs and bate(cs)]
        if opc:
            esc = min(opc, key=lambda cs: abs(need / max(1, len(uteis(cs, s0, em))) - 1))
        elif nomeados and (not need or need <= len(uteis(nomeados, s0, em)) * 1.1 + 3):
            esc = nomeados
        elif (nomeados or not at["empresa"]) and bate(cands):
            esc = cands  # o atestado só nomeia o setor final (ou não nomeia): os dias batem com todo o trabalho do intervalo
        if esc is None and nomeados:
            # o nome confere, mas os dias passam do possível: sugerido mesmo assim, com todo o trabalho contínuo até a emissão quando ele
            # inclui o setor nomeado (o aviso de dias implausíveis aponta)
            esc = blk if any(c in nomeados for c in blk) else nomeados
        if (esc is None and not at["empresa"] and need and s0 != date.min
                and len(uteis(cands, s0, em)) <= need * 1.1 + 3):
            # (7.14.3) atestado sem período e sem setor que declara mais dias do que todo o trabalho sem atestado do intervalo (do fim do
            # atestado anterior à emissão): todo esse trabalho cabe nele (teste de capacidade) - sugerido, não "pedir atestado" (o
            # pedido sairia em dobro com o atestado que já está na ficha)
            esc = cands = _sem_reserva(cands, em)
        if (esc is None and not at["empresa"] and need and s0 != date.min and blk and all(c in blk for c in cands)
                and any(p[0] <= em <= p[1] + timedelta(days=LACUNA_IGNORADA) for _u, p in blk)
                and need <= len(uteis(blk, s0, em)) * 1.1 + 3):
            # (7.14.5) atestado sem período e sem setor emitido durante o trabalho contínuo que vem do fim do atestado anterior (a mesma
            # sequência de atestados do mesmo trabalho), com menos dias do que o intervalo comporta: cobre esse trabalho (o trecho final,
            # quando os dias são bem menores) - sugerido, e não "sem atestado" com "pode ter sido remido com atestado que a ficha não registra"
            esc = blk
        if (esc is None and not at["empresa"] and need and s0 == date.min and blk and all(c in blk for c in cands)
                and any(p[0] <= em <= p[1] + timedelta(days=LACUNA_IGNORADA) for _u, p in blk)
                and 0.75 * len(uteis(blk, s0, em)) <= need <= ((em - min(p[0] for _u, p in blk)).days + 1) * 1.02 + 3):
            # (7.14.7) o primeiro atestado da ficha, sem período e sem setor, emitido durante o único trabalho contínuo, com os dias
            # trabalhados declarados (contados em dias corridos, 1.554 para 1.556) que cobrem esse trabalho do início até a emissão:
            # sugerido para esse trabalho, e não "sem atestado" (o trecho reservado ao saldo sem documento fica fora)
            esc = _sem_reserva(blk, em)
        if not esc:
            continue
        # (7.14.2) os dias declarados passam do trabalho escolhido: o trabalho sem atestado anterior no mesmo intervalo (do mais próximo
        # para o mais antigo) entra enquanto couber nos dias declarados - sem ele, o atestado não fecha (sugerido, não "pedir atestado")
        if need and s0 != date.min and len(uteis(esc, s0, em)) < need:  # (só com o atestado anterior delimitando o intervalo)
            esc = list(esc)
            for c in sorted([c for c in cands if c not in esc and c[1][1] < min(p[0] for _u, p in esc)], key=lambda c: c[1][1], reverse=True):
                if len(uteis(esc + [c], s0, em)) > need * 1.1 + 3:
                    break
                esc.append(c)
                if len(uteis(esc, s0, em)) >= need:
                    break
        dd = sorted(uteis(esc, s0, em))
        a_win = s0
        if need and dd and need < 0.6 * len(dd):
            # bem menos dias do que o intervalo comporta: o atestado cobre o trecho final (os dias úteis mais recentes)
            k_ = int(round(need / 0.85))
            a_win = dd[-k_] if 0 < k_ <= len(dd) else a_win
        usados = []
        for u, p in esc:
            jun = next(j for uu, j, _c in blocos if uu is u)
            if p[1] < a_win:
                continue
            k = next(i for i, x in enumerate(jun) if x is p)
            if p[1] > em and (p[1] - em).days > LACUNA_IGNORADA:
                jun.insert(k + 1, [em + timedelta(days=1), p[1], None, False, None])
                p[1] = em
            if p[0] < a_win and (a_win - p[0]).days > LACUNA_IGNORADA:
                jun.insert(k, [p[0], a_win - timedelta(days=1), None, False, None])
                p[0] = a_win
            p[4] = at["chave"]
            usados.append(p)
        if usados:
            i0 = min(p[0] for p in usados)
            inferidos[at["chave"]] = {"ini": i0, "fim": em, "uteis": len(uteis([(None, p) for p in usados], i0, em)), "dias": at["dias"]}
    linhas = []
    for u, jun, conc_ in blocos:
        for a, b, ch, nome, sug in jun:
            st = ("auto" if (nome or not conc_(a, b)) else "possivel") if ch else "provavel" if sug else "sem"
            ch_t = chave_trabalho(u["s"], a)
            man = vinculos.get(ch_t)
            confirmado_sem = False
            if man == "sem":
                st, sug, ch, confirmado_sem = "sem", None, None, True
            elif man and man in por_chave:
                st, sug, ch = "manual", None, man
            alvo = por_chave.get(ch or sug or "")
            em_curso = u["aberto"] and b == u["b"]
            local = setor_chave(u["s"])[1] if u["s"] else "Trabalho"
            local = re.sub(r"^([a-z]{1,3})(?=\s)", lambda m: m.group(1).upper(), local)  # "fe Freitas Valdez" -> "FE Freitas Valdez"
            linhas.append({"chave": ch_t, "local": local,
                           "ini": a, "fim": b, "periodo": "%s a %s%s" % (_f(a), _f(b), " (em curso na impressão da ficha)" if em_curso else (
                               " (fim suposto: início de outro setor; a ficha só dá baixa em %s)" % _f(u["baixa_tardia"]))
                               if u.get("baixa_tardia") and b == u["b"] and u["baixa_tardia"] > b else ""),
                           "dias": (b - a).days + 1, "at": alvo["num"] if alvo else "", "at_chave": alvo["chave"] if alvo else "",
                           "st": st, "como": "período e nome da empresa" if nome else "período (único trabalho no período)",
                           "sem_confirmado": confirmado_sem, "em_curso": em_curso, "externo": u["ext"], "jornada": u["jornada"],
                           "vinc": (u["a"], u["b"], u["s"]), "sem_baixa": u["sem_baixa"]})
    sem_dias = set()
    for L in linhas:
        if L["st"] == "sem":
            sem_dias |= {L["ini"] + timedelta(days=i) for i in range(L["dias"])}
    lista = [{"chave": a["chave"], "num": a["num"], "emissao": _f(a["emissao"]), "manual": a["manual"], "emp": a["empresa"],
              "per": ("período " + " e ".join("%s a %s" % (_f(x), _f(y)) for x, y, _n in a["segs"])) if a["segs"] else "sem período no texto"}
             for a in ats]
    return {"linhas": linhas, "ats": lista, "n_tot": len(linhas), "n_vinc": sum(1 for L in linhas if L["st"] in ("auto", "manual")),
            "dias_sem": len(sem_dias), "ult_at": None if ult == date.min else ult, "inferidos": inferidos}


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


# siglas de unidade penal que os atestados citam ("ATESTADO ... Nº 24/2024/ST/EPRSAA-A/AGEPEN"; o órgão AGEPEN não é unidade)
SIGLAS_UNIDADES_PENAIS = {"IPCG", "PDIB", "EPJFC", "PJFC", "CPAIG", "CPAG", "PTRAN", "PHAC", "PED", "EPRB", "UPRB", "EPMR", "EPA", "EPMC", "PSMTL",
                          "EPRSAA", "EPRACA", "EPRACAG", "CPAC", "EPFIIZ", "EPFSA", "EPMRSAAC", "EPB", "PEMRFG", "UMMVE"}


def _texto_atestado(f, a):
    """Texto do lançamento do atestado na ficha: o do dia da emissão que fala de atestado e cita o número."""
    em = _dt(a.get("data") or "")
    n0 = re.sub(r"\D", "", (a.get("numero") or "").split("/")[0]).lstrip("0")
    for e in f.get("eventos") or []:
        u = _sa(e.get("texto"))
        if em and _dt(e.get("data") or "") == em and re.search(r"ATEST", u) and (not n0 or re.search(r"(?<!\d)0*%s(?!\d)" % n0, u)):
            return e.get("texto") or ""
    return ""


def _sigla_da_unidade(sigla, unidade):
    """A sigla é a da unidade? Pelas grafias da ficha (rspe_ficha._mesma_unidade) ou pelas iniciais do nome ("EPMR" = "Estabelecimento
    Penal Maximo Romero de Jardim"; "EPRSAA" = "... de Regime Semiaberto e Aberto de Aquidauana")."""
    import rspe_ficha as _rf
    if _rf._mesma_unidade(sigla, unidade):
        return True
    ws = [w for w in re.sub(r"[^A-Z0-9 ]", " ", _sa(unidade)).split() if w not in ("DE", "DA", "DO", "DOS", "DAS", "E")]
    ini = "".join(w[0] for w in ws)
    return len(sigla) >= 3 and (ini.startswith(sigla) or sigla.startswith(ini) and len(ini) >= 3)


def _pet_texto(texto, d):
    """Peticionamento de certidão, curso, leitura ou exame pelo próprio lançamento da ficha."""
    if RE_PETICIONADO.search(re.sub(r"\s+", " ", _sa(texto))) or re.search(r"ENVIAD\w*,?\s+(?:VIA|AO|PARA|NO)\b", _sa(texto)):
        return "peticionado em %s" % _f(d), True, d
    return "registrado em %s (a ficha não registra o peticionamento)" % _f(d), False, None


def _segs_doc(d, trab=None):
    """(7.14.5) Trechos trabalhados do documento com o peso de cada um em dias remidos: [(início, fim, dias)]. Pelos dias de cada trecho
    quando o atestado os dá; senão, os dias do documento repartidos pelos dias de segunda a sábado; sem período no texto, o período
    implícito (trabalho_x_atestados). Sem período nenhum: []."""
    if not d.get("dias"):
        return []
    sr = [x for x in d.get("_segs_rem") or [] if x[0] and x[1] and x[0] <= x[1]]
    if sr and all(x[2] for x in sr):
        return [(a, b, float(w)) for a, b, w in sr]
    segs = list(d.get("_segs") or [])
    if not segs and trab:
        inf = (trab.get("inferidos") or {}).get(d.get("chave"))
        if inf and inf.get("ini") and inf.get("fim"):
            segs = [(inf["ini"], inf["fim"])]
    segs = [(a, b) for a, b in segs if a and b and a <= b]
    if not segs:
        return []
    tot = float(sum(_dias_seg_sab(a, b) for a, b in segs)) or 1.0
    return [(a, b, float(d["dias"]) * _dias_seg_sab(a, b) / tot) for a, b in segs]


def _base_127(rem_, expl, desta, post, trab=None):
    """(7.14.5) A base da perda por falta grave pelo período trabalhado (LEP, art. 127: a falta alcança o tempo remido pelo trabalho
    anterior a ela, declarado ou não): o período dos documentos da ficha ligados a cada remição do RSPE, os atestados ainda não
    declarados (posteriores à última remição) e o trabalho sem atestado. Para rspe_auditoria.perdas_por_falta(ficha=...)."""
    periodos = {}
    for i, ds in (expl or {}).items():
        x = rem_[i]
        segs = [_segs_doc(d, trab) for d in ds]
        if x.get("decisao") and segs and all(segs):
            periodos[(x["decisao"], float(x["dias"]))] = [s_ for ss in segs for s_ in ss]
    ligados = {id(d) for ds in (expl or {}).values() for d in ds}
    pend = []
    for d in post or []:
        if d["tipo"] != "Atestado de trabalho" or id(d) in ligados or d.get("provavel") or d.get("ja_rem") or d.get("hom") or d not in desta:
            continue
        ss = _segs_doc(d, trab)
        if ss:
            pend.append({"n": float(d["dias"]), "ini": min(a for a, _b, _w in ss), "fim": max(b for _a, b, _w in ss),
                         "rot": "atestado nº %s" % d["num"] if d.get("num") and d["num"] != "s/n" else "atestado de %s" % _f(d["emissao"])})
    ativ = [(L["ini"], L["fim"]) for L in (trab or {}).get("linhas") or [] if L.get("st") == "sem" and L.get("ini") and L.get("fim")]
    return {"periodos": periodos, "pendentes": pend, "atividade": ativ}


def comparacao(r, f, hoje=None, manuais=None, homologados=None, trab=None):
    """Seções A, B, D e E da aba Ficha no modelo da 7.14 (sem ligar remição a atestado):
    A) totais - remição concedida no RSPE x documentos de remição desta execução na ficha (atestados, certidões e cursos com horas
       ÷ 12, leitura 4 dias por obra) e a diferença (tolerância de 3 dias), com o estimado à parte;
    B) pontos a conferir - fatos de data e o que a ficha não valora;
    D) documentos da ficha com o peticionamento e a situação factual (✓ Homologado: homologados = chaves marcadas);
    E) remições do RSPE (data, referência, dias), sem origem.
    trab: resultado de trabalho_x_atestados (o trabalho sem atestado fora do saldo de remição sem documento vira "pedir atestado")."""
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
        fo_ = fora_de(a.get("autos"), fim or em, ini, fim)
        nota_ = ""
        if fo_.startswith("dirigido a outros autos") and em and a.get("dias_remidos") and any(
                x["ref"] and abs((x["ref"] - em).days) <= 1 and abs(x["dias"] - float(a["dias_remidos"])) <= 1 for x in R["remicoes"]):
            # (7.14.2) a ficha cita outros autos, mas o RSPE desta execução tem remição do mesmo valor com referência na data do
            # atestado: a remição entrou aqui - o atestado é desta execução
            fo_, nota_ = "", "a ficha cita outros autos (%s), mas a remição consta aqui" % a.get("autos")
        doc("Atestado de trabalho", a.get("numero") or "s/n", em, ("%s a %s" % (_f(ini), _f(fim))) if ini and fim else "sem período no texto",
            a.get("dias_trabalhados") or None, float(a.get("dias_remidos") or 0) or None, pet, ok, pdt,
            fo_, chave_atestado(a.get("numero"), em), defensoria=dfn,
            sem_valor="" if a.get("dias_remidos") else "atestado sem os dias remidos no texto da ficha")
        docs[-1]["nota_autos"] = nota_
        docs[-1]["nota_ano"] = ("ano corrigido (%s) · conferir" % a["ano_corrigido"]) if a.get("ano_corrigido") else ""
        sg_ = [(_dt(t.get("inicio")), _dt(t.get("fim"))) for t in a.get("trechos") or []]
        docs[-1]["_segs"] = [x for x in sg_ if x[0] and x[1] and x[0] <= x[1]] or ([(ini, fim)] if ini and fim and ini <= fim else [])
        # (7.14.5) os dias remidos de cada trecho (quando o atestado os dá): a parte da remição anterior à falta grave (art. 127)
        docs[-1]["_segs_rem"] = [(_dt(t.get("inicio")), _dt(t.get("fim")), _num(str(t["rem"])) if t.get("rem") is not None else None)
                                 for t in a.get("trechos") or [] if _dt(t.get("inicio")) and _dt(t.get("fim"))]
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
    for e in f.get("estudos") or []:
        # (7.14.3) atestado de estudo com os dias de remição declarados: documento da comparação (as datas invertidas na ficha, com
        # "conferir datas"); sem os dias declarados, continua como estimativa pelas horas (estudo sem certidão)
        if not (e.get("dias_remidos") and e.get("data") and (e.get("curso") or "").startswith("Atestado de estudo")):
            continue
        d = _dt(e["data"])
        a, b = _dt(e.get("inicio") or ""), _dt(e.get("fim") or "")
        inv = bool(a and b and b < a)
        if inv:
            a, b = b, a
        pet, ok, pdt = _pet_texto(e.get("texto"), d)
        doc("Atestado de estudo", e["curso"].replace("Atestado de estudo", "").replace("nº", "").strip(), d,
            ("%s a %s" % (_f(a), _f(b))) if a and b and a != b else "", None, float(e["dias_remidos"]), pet, ok, pdt, fora_de("", b or d, a, b),
            "fd:edu:at:%s:%s" % (e["curso"], e["data"]))
        docs[-1]["nota_ano"] = "datas invertidas na ficha (%s a %s) · conferir datas" % (_f(b), _f(a)) if inv else ""
        docs[-1]["horas"] = e.get("horas")
        e["_doc"] = True
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
        doc("Leitura", ("%s%s%s" % ("Jornada da Leitura no Cárcere · " if "JORNADA DA LEITURA" in _sa(x.get("texto")) else "",
                                    rs.pl(ob, "obra", "obras") if ob else "obras não informadas", (" · ciclo " + x["ciclo"]) if x.get("ciclo") else "")),
            d, ", ".join(x.get("meses") or []) or (x.get("ref_mes") or ""), None, (4.0 * ob) if ob else None, pet, ok, pdt, fora_de("", d),
            "fd:lei:%s" % x.get("data"), sem_valor="" if ob else "%s sem o número de obras" % (
                "certificado" if "JORNADA DA LEITURA" in _sa(x.get("texto")) else "relatório de leitura"))
    for x in f.get("exames") or []:
        d = _dt(x.get("data") or "")
        # o peticionamento está no lançamento do exame ("Peticionado Certificado do ENEM 2025 no Sistema SEEU"): o texto do dia
        tx = x.get("texto") or " ".join(e.get("texto") or "" for e in f.get("eventos") or []
                                        if _dt(e.get("data") or "") == d and re.search(r"ENCCEJA|ENEM", _sa(e.get("texto"))))
        pet, ok, pdt = _pet_texto(tx or x.get("exame"), d)
        if not ok:
            pet = "registrado em %s" % _f(d)
        dx = doc("Exame", x.get("exame") or "", d, "", None, None, pet, ok, pdt, fora_de(x.get("autos"), d),
            "fd:exa:%s:%s" % (_rf._norm(x.get("exame") or ""), x.get("data")),
            sem_valor=TXT_VALOR_EXAME)
        dx["cert"] = bool(x.get("certificado"))
    docs.sort(key=lambda d: d["emissao"] or date.min)
    # (7.14.3) certidão de semestre sem a carga horária: estimativa pela matrícula da ficha (dias letivos do semestre com matrícula,
    # segunda a sexta fora do recesso, × 4 h ÷ 12). No semestre interrompido (matrícula encerrada no meio dele), a estimativa aparece
    # no documento; em qualquer semestre, ela decide a qual certidão uma remição pertence quando há mais de uma candidata
    for d in docs:
        m_ = re.match(r"(\d)º semestre de (\d{4})", d.get("num") or "")
        if d["tipo"] != "Certidão de frequência escolar" or d["dias"] or not m_:
            continue
        y_ = int(m_.group(2))
        s0, s1 = (date(y_, 1, 1), date(y_, 6, 30)) if m_.group(1) == "1" else (date(y_, 7, 1), date(y_, 12, 31))
        dl, fins = set(), []
        for e in f.get("estudos") or []:
            a, b = _dt(e.get("inicio") or ""), _dt(e.get("fim") or "") or imp
            if not a or not b or b < a or e.get("horas"):
                continue
            x_, z_ = max(a, s0, inicio or a), min(b, s1)
            if x_ > z_:
                continue
            dl |= {x for x in _rf.dias_jornada_set(x_, z_, "seg-sex") if not _rf.em_recesso(x)}
            if e.get("fim"):
                fins.append(b)
        if len(dl) < 3:
            continue
        corte = max(fins) if fins and max(fins) < s1 - timedelta(days=10) and max(fins) >= max(dl) else None
        d["estim"] = {"dias": round(len(dl) * _rf.HORAS_DIA_ESTUDO / 12.0, 2), "letivos": len(dl), "corte": corte}
        if corte:
            d["sem_valor"] += "; semestre interrompido: estimativa ≈ %s dias (%s até o fim da matrícula em %s × %d h ÷ 12)" % (
                _nf(d["estim"]["dias"]), rs.pl(len(dl), "dia letivo", "dias letivos"), _f(corte), _rf.HORAS_DIA_ESTUDO)
    desta = [d for d in docs if not d["fora"]]
    # (7.14.2) atestado contido em outros: o período (pelos trechos; havendo trabalho na ficha, só os dias com trabalho registrado) já
    # está 90% ou mais nos demais atestados desta execução e os dias declarados passam do que a parte nova comporta - "contido no nº X:
    # não se soma" e sai do total; com metade ou mais repetida, soma-se só a parte nova (dias de segunda a sábado ÷ 3). Do mais repetido
    # para o menos (e, no empate, do maior para o menor), deixando por último o que tem remição do mesmo valor no RSPE: o atestado
    # cumulativo sai e os parciais ficam.
    dset_ = lambda segs: {a + timedelta(days=i) for a, b in segs for i in range((b - a).days + 1)}
    trab_d = set()
    for t in f.get("trabalho") or []:
        a, b = _dt(t.get("inicio") or ""), _dt(t.get("fim") or "") or imp
        if a and b and a <= b:
            trab_d |= dset_([(a, b)])
    ats_c = [d for d in docs if d["tipo"] == "Atestado de trabalho" and not d["fora"] and d.get("_segs") and d["dias"]]
    ds_ = {id(d): dset_(d["_segs"]) for d in ats_c}
    # o atestado com remição do mesmo valor no RSPE (decidida depois da emissão) é o que foi apreciado: fica; sai o que o repete
    tem_rem = lambda d: any(x["decisao"] and d["emissao"] and 0 <= (x["decisao"] - d["emissao"]).days <= 1095 and abs(x["dias"] - d["dias"]) <= 1
                            for x in R["remicoes"])
    # o mesmo período em dois atestados (reemissão: um contém 90% ou mais do outro, nos dois sentidos): fica o que tem remição do mesmo
    # valor no RSPE (7.14.3) e, entre os dois com ou sem ela, o de mais dias
    for d in sorted(ats_c, key=lambda d: (tem_rem(d), d["dias"], d["emissao"] or date.min)):
        for o in ats_c:
            if o is d or o.get("contido") or d.get("contido"):
                continue
            x_ = ds_[id(d)] & ds_[id(o)]
            if len(x_) >= 0.9 * len(ds_[id(d)]) and len(x_) >= 0.9 * len(ds_[id(o)]) and (tem_rem(d), d["dias"]) <= (tem_rem(o), o["dias"]):
                d["contido"], d["dias_soma"] = "repete o período do atestado nº %s (reemissão?): não se soma" % o["num"], 0.0
    def _cob0(d):
        base = (ds_[id(d)] & trab_d) or ds_[id(d)]
        return len(base & set().union(*[ds_[id(o)] for o in ats_c if o is not d])) / float(len(base) or 1)
    for d in sorted(ats_c, key=lambda d: (tem_rem(d), -_cob0(d), -len(ds_[id(d)]))):
        outros = [o for o in ats_c if o is not d and not o.get("contido")]
        base = (ds_[id(d)] & trab_d) or ds_[id(d)]
        quem = [o for o in outros if ds_[id(o)] & base]
        cob = set().union(*[ds_[id(o)] for o in quem]) & base if quem else set()
        if not quem or len(cob) < 0.5 * len(base):
            continue
        novo = sum(1 for x in base - cob if x.weekday() != 6) / 3.0
        if d["dias"] <= novo * 1.1 + 1:
            continue  # os dias declarados cabem na parte nova: o atestado já conta só o que não estava nos outros
        nums = _lista(["nº %s" % o["num"] for o in sorted(quem, key=lambda o: o["emissao"] or date.min)])
        if len(cob) >= 0.9 * len(base):
            d["contido"], d["dias_soma"] = "contido %s: não se soma" % ("nos atestados " + nums if len(quem) > 1 else "no atestado " + nums), 0.0
        else:
            d["dias_soma"] = round(novo, 2)
            d["contido"] = "repete parte %s: soma-se só a parte nova (≈ %s dias)" % (("dos atestados " if len(quem) > 1 else "do atestado ") + nums, _nf(novo))
    soma = lambda L: round(sum((d["dias_soma"] if "dias_soma" in d else d["dias"]) or 0 for d in L), 2)
    at_ = [d for d in desta if d["tipo"] == "Atestado de trabalho"]
    man_ = [d for d in desta if d["tipo"].endswith("(informado por você)")]
    est_ = [d for d in desta if d["tipo"] in ("Certidão de frequência escolar", "Curso de qualificação", "Atestado de estudo")]
    lei_ = [d for d in desta if d["tipo"] == "Leitura"]
    comp = round(soma(at_) + soma(man_) + soma(est_) + soma(lei_), 2)
    dif = round(comp - R["concedido"], 2)
    rspe_maior = dif < -TOL_COMPARACAO
    contidos = [d for d in desta if d.get("contido")]
    desta = [d for d in desta if not (d.get("contido") and d["dias_soma"] == 0)]  # o contido não casa com remição nem gera ponto
    # ---- indicação por valor e data (sem vínculo, sem mudar totais, sem ✓): remição do RSPE com o mesmo valor do documento (até 1 dia
    # de diferença) decidida de 0 a 180 dias depois da emissão = "provavelmente remido"; cada remição serve a um documento só (o
    # primeiro em ordem de data). Depois: exame x remição de 25 dias ou mais decidida até 365 dias depois (sem o valor na ficha) e
    # leitura x remição menor, múltipla de 4, decidida até 180 dias depois (remida a menor?) ----
    rem_ = R["remicoes"]
    orig = {}  # índice da remição do RSPE -> documento que ela provavelmente remiu

    def _ref_min(d_):
        """(7.14.2) Início do que o documento comprova: a remição com referência anterior a ele não pode ser dele - o início do período
        do atestado, o ano do exame, o início do semestre da certidão, o primeiro mês do curso ou da leitura."""
        if d_.get("_segs"):
            return min(a for a, _b in d_["_segs"])
        ps = (d_.get("periodo") or "").split(" a ")
        if len(ps) == 2 and _dt(ps[0]):
            return _dt(ps[0])
        m_ = re.match(r"(\d)º semestre de (\d{4})", d_.get("num") or "")
        if m_:
            return date(int(m_.group(2)), 1 if m_.group(1) == "1" else 7, 1)
        if d_["tipo"] == "Exame":
            m_ = re.search(r"(20\d{2})", d_.get("num") or "")
            return date(int(m_.group(1)), 1, 1) if m_ else None
        ms = [date(int(y), int(mm), 1) for mm, y in re.findall(r"\b(\d{2})/(\d{4})\b", d_.get("periodo") or "") if 1 <= int(mm) <= 12]
        return min(ms) if ms else None

    ref_ok = lambda x, d_: not x["ref"] or not _ref_min(d_) or x["ref"] >= _ref_min(d_)

    def _livres(d_, ate, cond, chave=None):
        cs = [i for i, x in enumerate(rem_) if i not in orig and x["decisao"] and d_["emissao"] and 0 <= (x["decisao"] - d_["emissao"]).days <= ate
              and cond(x) and ref_ok(x, d_)]
        return (min(cs, key=lambda i: chave(rem_[i])) if chave else cs[0]) if cs else None

    for d in sorted([d for d in desta if d["dias"] and d["emissao"]], key=lambda d: d["emissao"]):
        i = _livres(d, 180, lambda x, d=d: abs(x["dias"] - d["dias"]) <= 1)
        if i is None and d.get("horas") and abs(d["horas"] / 12.0 - d["dias"]) > 1:
            # (7.14.4) atestado de estudo/curso com a carga horária: os dias declarados não fecham com remição próxima, mas a carga
            # horária ÷ 12 fecha (180 h -> 15 dias) - essa é a ligação provável, antes da do mesmo valor declarado decidida anos depois
            # (o valor de padrão de leitura - 4, 8, 12, 16 - só quando fecha exato: senão pode ser a leitura)
            i = _livres(d, 180, lambda x, v=d["horas"] / 12.0: abs(x["dias"] - v) <= 1 and (
                abs(x["dias"] - v) < 0.5 or not (x["dias"] <= 16 and x["dias"] % 4 == 0)))
            if i is not None:
                d["provavel_horas"] = round(d["horas"] / 12.0, 2)
        if i is not None:
            orig[i], d["provavel"], d["provavel_dias"] = d, _f(rem_[i]["decisao"]), rem_[i]["dias"]
    # (7.14.2) o mesmo valor decidido até 3 anos depois da emissão (atestado apreciado mais tarde, com ou sem registro de peticionamento;
    # não a leitura, de valores pequenos e repetidos), antes do exame e da certidão sem valor: o valor exato vem primeiro
    for d in sorted([d for d in desta if d["dias"] and d["emissao"] and not d.get("provavel") and d["tipo"] != "Leitura"], key=lambda d: d["emissao"]):
        i = _livres(d, 1095, lambda x, d=d: abs(x["dias"] - d["dias"]) <= 1)
        if i is not None:
            # decisão do usuário: "provavelmente remido" só até 180 dias; depois disso o mesmo valor só explica a remição (não a
            # deixa "sem documento") e aparece como "mesmo valor decidido em ...: conferir"
            orig[i], d["provavel"], d["provavel_tarde"], d["provavel_dias"] = d, _f(rem_[i]["decisao"]), True, rem_[i]["dias"]
    # (7.14.7) atestado com dias declarados e remição de valor próximo (do valor do atestado a 10% acima) decidida na mesma semana da
    # emissão: a ligação provável é esse atestado (131 dias no atestado, 138 decididos no mesmo dia), antes do exame ou da certidão sem
    # valor - o exame não fica "possivelmente remido" por uma remição que o atestado do mesmo dia explica
    for d in sorted([d for d in desta if d["dias"] and d["emissao"] and not d.get("provavel") and d["tipo"] not in ("Leitura", "Exame")],
                    key=lambda d: d["emissao"]):
        i = _livres(d, 7, lambda x, d=d: d["dias"] - 1 <= x["dias"] <= d["dias"] * 1.1 + 1, chave=lambda x, d=d: abs(x["dias"] - d["dias"]))
        if i is not None:
            orig[i], d["provavel"], d["provavel_dias"] = d, _f(rem_[i]["decisao"]), rem_[i]["dias"]
    # exame e certidão/curso sem o valor na ficha: a remição (não de leitura) decidida até 180 dias depois, com referência posterior ao
    # início da prova ou do período - de 10 dias ou mais no exame; na certidão e no curso, também a pequena (1 dia de um semestre curto).
    # O exame primeiro (o certificado de conclusão do ENCCEJA antes), depois a certidão e o curso; no exame, o valor da tabela do CNJ (Res. 391/2021, art. 3º: áreas de 20 dias no
    # ENEM, 25 ou 33,33 no ENCCEJA, níveis inteiros de 100 e 133,33 e o acréscimo de 1/3 da conclusão) antes de qualquer outro
    nome_doc0 = lambda d: (("a certidão do %s" % d["num"]) if d["tipo"] == "Certidão de frequência escolar" and d.get("num") else
                           ("o curso (%s)" % d["num"]) if d["tipo"] == "Curso de qualificação" and d.get("num") else d["tipo"].lower())
    tab_ = sorted({round(v * k_ * f_, 2) for v in (20.0, 25.0, 100 / 3.0) for k_ in range(1, 6) for f_ in (1, 4 / 3.0)})
    na_tab = lambda v: any(abs(v - t) <= 1 for t in tab_)
    sem_v = [d for d in desta if not d["dias"] and d["emissao"] and d["tipo"] in ("Exame", "Certidão de frequência escolar", "Curso de qualificação")]
    for d in sorted(sem_v, key=lambda d: (d["tipo"] != "Exame", not d.get("cert"), d["emissao"])):
        minimo = 10 if d["tipo"] == "Exame" else 1
        # (7.14.7) teto do exame (Res. CNJ 391/2021, art. 3º): ENEM, até o ensino médio inteiro (1.200 h ÷ 12 = 100 dias; o ENEM não
        # certifica a conclusão desde 2017, sem o +1/3); ENCCEJA, até o fundamental inteiro com a conclusão (1.600 h ÷ 12 × 4/3 ≈ 177,78)
        teto = 400 if d["tipo"] != "Exame" else 100 if re.search(r"ENEM", d.get("num") or "", re.I) else 1600 / 12.0 * 4 / 3.0 \
            if re.search(r"ENCCEJA", d.get("num") or "", re.I) else 400
        i = _livres(d, 180, lambda x, m=minimo, t=teto: m <= x["dias"] <= t + 1 and not (x["dias"] <= 16 and x["dias"] % 4 == 0),
                    chave=(lambda x: (not na_tab(x["dias"]), x["decisao"])) if d["tipo"] == "Exame" else None)
        if i is not None and d["tipo"] != "Exame":
            # (7.14.3) outra certidão ou curso sem valor, peticionado antes da decisão, também pode ser desta remição: liga-se só quando o
            # valor fecha com a estimativa (de 75% a 110%, ± 1 dia) da certidão sozinha ou somada às outras; senão, "conferir"
            x = rem_[i]
            outros_ = [o for o in sem_v if o is not d and o["tipo"] != "Exame" and not o.get("provavel_ex") and not o.get("rem_conf")
                       and o["emissao"] and 0 <= (x["decisao"] - o["emissao"]).days <= 180 and ref_ok(x, o)]
            if outros_:
                se_ = lambda g: sum(o["estim"]["dias"] for o in g)
                fecha = lambda g: 0.75 * se_(g) - 1 <= x["dias"] <= 1.1 * se_(g) + 1
                grupo = None
                if all(o.get("estim") for o in [d] + outros_):
                    ok_ = [g for g in [[d]] + [[d] + list(c) for k in (1, 2) for c in itertools.combinations(outros_, k)] if fecha(g)]
                    grupo = min(ok_, key=lambda g: abs(se_(g) - x["dias"])) if ok_ else None
                orig[i] = d
                if grupo is None:
                    d["rem_conf"] = "a remição de %s dias de %s pode ser deste documento ou %s%s: conferir" % (
                        _nf(x["dias"]), _f(x["decisao"]), _lista(["%s (%s)" % (re.sub(r"^a ", "da ", re.sub(r"^o ", "do ", nome_doc0(o))), _f(o["emissao"])) for o in outros_]),
                        (" (estimativas ≈ %s)" % _lista([_nf(o["estim"]["dias"]) for o in [d] + outros_ if o.get("estim")])) if d.get("estim") else "")
                    if all(o.get("estim") for o in [d] + outros_) and x["dias"] < 0.75 * se_([d] + outros_) - 1:
                        # (7.14.7) as certidões peticionadas antes da decisão somam bem mais do que a remição (duas certidões semestrais,
                        # ≈ 28 + ≈ 35, e uma só remição de 33): provável pendência de uma delas - amarelo, não "nada a requerer"
                        d["pend_prov"] = "%s peticionad%s antes da decisão de %s (estimativas ≈ %s = %s dias) e uma só remição de %s dias: " \
                            "provavelmente uma delas ainda não foi apreciada - conferir nos autos e, se for o caso, requerer a remição pendente" % (
                                _lista([nome_doc0(o) for o in [d] + outros_]), "as" if all(o["tipo"].startswith("Certid") for o in [d] + outros_) else "os",
                                _f(x["decisao"]), " + ".join(_nf(o["estim"]["dias"]) for o in [d] + outros_), _nf(se_([d] + outros_)), _nf(x["dias"]))
                        d["pend_docs"] = [o["chave"] for o in [d] + outros_]
                    continue
                for o in grupo:
                    o["provavel_ex"] = "%s (%s dias%s)" % (
                        _f(x["decisao"]), _nf(x["dias"]),
                        ("; estimativa ≈ %s" % _nf(se_(grupo))) if len(grupo) == 1 else
                        ", somad%s %s: estimativas ≈ %s = %s" % ("o" if o["tipo"] == "Curso de qualificação" else "a",
                                                                 _lista([re.sub(r"^a ", "à ", re.sub(r"^o ", "ao ", nome_doc0(z))) for z in grupo if z is not o]),
                                                                 " + ".join(_nf(z["estim"]["dias"]) for z in grupo), _nf(se_(grupo))))
                    if o["estim"].get("corte"):
                        o["provavel_ex"] += "; semestre interrompido em %s" % _f(o["estim"]["corte"])
                continue
        if i is not None:
            orig[i], d["provavel_ex"] = d, "%s (%s dias)" % (_f(rem_[i]["decisao"]), _nf(rem_[i]["dias"]))
    menor = []
    for d in [d for d in desta if d["tipo"] == "Leitura" and d["dias"] and not d.get("provavel")]:
        i = _livres(d, 180, lambda x, d=d: x["dias"] < d["dias"] - 1 and x["dias"] % 4 == 0)
        if i is not None:
            orig[i] = d
            menor.append((d, rem_[i]))
    # ---- estimados (fora da conta): trabalho sem atestado (todo o da execução) e estudo sem certidão ----
    ult_at = max([d["emissao"] if d["periodo"].startswith("sem período") else _dt(d["periodo"].split(" a ")[-1]) for d in at_ + man_
                  if d["emissao"]] or [None], key=lambda x: x or date.min)
    # fora da estimativa: fuga, liberdade, livramento e regime aberto do RSPE (sem trabalho a remir na unidade - LEP, art. 126, § 6º)
    fora_ = fora_da_unidade(r, imp, f)
    livre = lambda d: not any(x <= d <= y for x, y, _m in fora_) and (not inicio or d >= inicio)
    pedir, talvez, itens_p, itens_t, acomp, acomp_l = set(), set(), [], [], [], []
    conferir, itens_c = set(), []
    # (7.14.2) saldo de remição sem documento. Cada remição do RSPE é ligada aos documentos da ficha que a explicam: o mesmo valor (até 1
    # dia de diferença) decidido até 3 anos depois da emissão, com ou sem registro de peticionamento, ou a soma de 2 ou 3 documentos
    # (não de leitura) emitidos antes da decisão. Só a remição que sobra (sem documento) pode cobrir trabalho sem atestado - do trabalho mais próximo da
    # referência da remição para o mais antigo, até os dias da remição × 3 acabarem; o que não couber é "pedir atestado". A remição
    # pequena (menos de 10 dias) ou de padrão de leitura (4, 8, 12, 16) sem documento não cobre trabalho.
    expl = {i: [d] for i, d in orig.items()}
    usados_ = set(id(d) for d in orig.values())
    # (7.14.5) a leitura entra na soma com outro documento (atestado de 53,33 + leitura de 8 = remição de 61), decidida até 180 dias
    # depois dela e com a soma exata (até meio dia); só leituras, não (valores pequenos e repetidos)
    cand_ = lambda x: [d for d in desta if d["dias"] and d["emissao"] and id(d) not in usados_ and x["decisao"]
                       and 0 <= (x["decisao"] - d["emissao"]).days <= (180 if d["tipo"] == "Leitura" else 1095) and ref_ok(x, d)]
    _soma_ok = lambda cb, x: (abs(sum(d["dias"] for d in cb) - x["dias"]) <= (0.5 if any(d["tipo"] == "Leitura" for d in cb) else 1)
                              and any(d["tipo"] != "Leitura" for d in cb))
    for i, x in enumerate(rem_):
        if i in expl or not x["decisao"]:
            continue
        cs = sorted(cand_(x), key=lambda d: d["emissao"], reverse=True)[:12]  # os mais próximos da decisão
        achou = None
        for k in (2, 3):
            achou = next((cb for cb in itertools.combinations(cs, k) if _soma_ok(cb, x)), None)
            if achou:
                break
        if achou:
            expl[i] = list(achou)
            usados_ |= {id(d) for d in achou}
            for d in achou:
                d["provavel"] = _f(x["decisao"])
                if d["emissao"] and (x["decisao"] - d["emissao"]).days > 180:
                    d["provavel_tarde"] = True
                d["soma_com"] = [("a leitura (%s)" % o["num"]) if o["tipo"] == "Leitura" else ("o nº %s" % o["num"]) if o["num"] else
                                 "%s %s" % ("a" if o["tipo"].startswith("Certid") else "o", o["tipo"].lower()) for o in achou if o is not d]
                d["soma_rem"] = x["dias"]
    # (7.14.2) atestado ainda sem decisão (emitido ou peticionado depois da última remição) cujo período contém a referência de uma remição
    # sem documento decidida antes da emissão: essa remição provavelmente veio de atestado parcial do mesmo período, que a ficha não
    # registra - pede-se só a diferença ("pedir ≈ 157 (244 − 87)"), conferindo a decisão antes de requerer
    for d in [d for d in at_ + man_ if d["dias"] and not d["hom"] and d in desta and d["data_ref"] and (not ult_dec or d["data_ref"] > ult_dec)]:
        ps = d["periodo"].split(" a ")
        a0, b0 = (_dt(ps[0]), _dt(ps[1])) if len(ps) == 2 else (None, None)
        if not a0 or not b0:
            continue
        ja = [(i, x) for i, x in enumerate(rem_) if i not in expl and x["ref"] and a0 <= x["ref"] <= b0 and x["decisao"]
              and x["decisao"] <= (d["emissao"] or x["decisao"]) and not (x["dias"] <= 16 and x["dias"] % 4 == 0)]
        if ja and sum(x["dias"] for _i, x in ja) < d["dias"] - 1:
            for i, _x in ja:
                expl[i] = [d]
            d["ja_rem"] = [x for _i, x in ja]
            d["dias_pedir"] = round(d["dias"] - sum(x["dias"] for _i, x in ja), 2)
            d["ja_rem_txt"] = _lista(["%s dias de %s%s" % (_nf(x["dias"]), _f(x["decisao"]), (", ref. %s" % _f(x["ref"])) if x["ref"] != x["decisao"] else "")
                                      for _i, x in ja])
    sem_doc = sorted([x for i, x in enumerate(rem_) if i not in expl and x["ref"] and x["dias"] >= 10 and not (x["dias"] <= 16 and x["dias"] % 4 == 0)],
                     key=lambda x: x["ref"])
    corte = sem_doc[-1]["ref"] if sem_doc else None
    linhas_ = (trab or {}).get("linhas") or []
    cobertos = set()  # dias de trabalho cobertos por atestado (de qualquer vínculo): não contam de novo no vínculo simultâneo
    for L in linhas_:
        if L["st"] != "sem":
            cobertos |= {L["ini"] + timedelta(days=i) for i in range(L["dias"])}
    dias_l = {}
    aus_ = ausencias_ficha(f.get("eventos"))  # isolamento e saída temporária: dias sem trabalho dentro do vínculo
    # (7.14.2) trabalho em período em que esta execução estava interrompida pela liberdade (liberdade provisória, soltura...): à parte,
    # fora da custódia desta execução - como o atestado do mesmo período
    em_int = lambda d: next((x for x in interr if x[0] <= d <= x[1]), None)
    aparte = []
    for L in linhas_:
        if L["st"] == "sem":
            ds_ = {d for d in _rf.dias_jornada_set(L["ini"], min(L["fim"], imp), L.get("jornada") or "", L["ini"])
                   if livre(d) and d not in cobertos and d not in aus_}
            fo_ = {d for d in ds_ if em_int(d)}
            if fo_:
                x_ = em_int(min(fo_))
                aparte.append("%s, %s a %s (%s, %s a %s)" % (L["local"], _f(min(fo_)), _f(max(fo_)), x_[2], _f(x_[0]), _f(x_[1])))
                L["aparte"] = True
            dias_l[id(L)] = ds_ - fo_
    # trabalho em curso há até 90 dias, sem remição sem documento depois do início: acompanhar (fora do saldo e do pedido)
    recente = {k for k, L in ((id(L), L) for L in linhas_ if L["st"] == "sem") if L.get("em_curso") and dias_l[k]
               and (hoje - min(dias_l[k])).days <= 90 and not any(x["ref"] >= min(dias_l[k]) for x in sem_doc)}
    pool = set().union(*[v for k, v in dias_l.items() if k not in recente]) if dias_l else set()
    # (7.14.2) atestado que declara mais dias trabalhados do que o seu período comporta (segunda a sábado): o excesso é, quase sempre,
    # trabalho anterior ao período, sem atestado próprio - entra como saldo a partir do início do período, como a remição sem documento
    exc_ = []
    for d in at_ + man_:
        ps = d["periodo"].split(" a ")
        a0, b0 = (_dt(ps[0]), _dt(ps[1])) if len(ps) == 2 else (None, None)
        need = d["trab"] or (d["dias"] or 0) * 3
        if d in desta and a0 and b0 and need:
            sobra = need - _dias_seg_sab(a0, b0)
            if sobra >= 10:
                exc_.append({"dias": round(sobra / 3.0, 2), "ref": a0 - timedelta(days=1), "decisao": None,
                             "txt": "excesso de %s dias trabalhados do atestado nº %s sobre o período %s" % (_nf(sobra), d["num"], d["periodo"])})
    cobre, saldo_txt = set(), []
    for x in sorted(sem_doc + exc_, key=lambda x: x["ref"]):
        # dias até a referência (com a sobra de até uma semana: o mesmo período), do mais próximo para o mais antigo
        livres_ = pool - cobre
        cab = sorted((d for d in livres_ if d <= x["ref"]), reverse=True)
        n_ = int(round(x["dias"] * 3))
        pega = set(cab[:n_])
        if pega and len(pega) < n_:
            # vínculo já coberto que termina até uma semana depois da referência: a sobra é o mesmo período
            tocados = set().union(*[v for v in dias_l.values() if v & pega and max(v) <= x["ref"] + timedelta(days=7)])
            pega |= set(sorted(d for d in livres_ & tocados if x["ref"] < d <= x["ref"] + timedelta(days=7))[:n_ - len(pega)])
        for v in dias_l.values():
            # sobra pequena antes da referência, no mesmo vínculo já coberto - até 3 dias trabalhados (1 de remição, frações) ou 10% do
            # vínculo (a estimativa de segunda a sábado passa dos dias de fato trabalhados): fica com ele
            sob = {d for d in v - cobre - pega if d <= x["ref"]}
            # (no excesso de um atestado, até 25%: os dias declarados são os de fato trabalhados, menos que a estimativa)
            if v & pega and len(sob) <= max(3, (0.25 if x.get("txt") else 0.1) * len({d for d in v if d <= x["ref"]})):
                pega |= sob
        for v in dias_l.values():
            # migalha de até 3 dias de um vínculo que fica quase todo fora do saldo (1 dia de remição, frações): fica com o resto dele
            if 0 < len(v & pega) <= 3 and len(v - pega - cobre) > 3:
                pega -= v
        cobre |= pega
        saldo_txt.append(x.get("txt") or "%s dias de %s" % (_nf(x["dias"]), _f(x["decisao"] or x["ref"])))
    for L in linhas_:
        if L["st"] != "sem":
            continue
        dias_ = dias_l[id(L)]
        antes = dias_ & cobre
        if antes and len(dias_ - antes) <= 3:
            antes = set(dias_)  # sobra de até 3 dias trabalhados (1 de remição) na mesma linha: o mesmo período
        if id(L) in recente:
            # trabalho em curso há até 90 dias: o atestado do período ainda não costuma ter sido emitido - acompanhar (fora da conta)
            acomp.append("%s, desde %s: ≈ %s até a impressão da ficha" % (L["local"], _f(min(dias_)), rs.pl(len(dias_), "dia trabalhado", "dias trabalhados")))
            acomp_l.append({"local": L["local"], "ini": min(dias_), "dias": round(len(dias_) / 3.0, 2)})
            L["acomp_dias"] = round(len(dias_) / 3.0, 2)
            continue
        if L.get("em_curso") and dias_:
            L["curso_dias"] = (hoje - min(dias_)).days  # há quantos dias corridos o trabalho sem atestado está em curso (texto)
        # (7.14.3) vínculo sem baixa de mais de um ano (a ficha registra o início e só a saída da unidade, anos depois): o trecho
        # depois do último dia documentado do vínculo (remição que o cobre ou atestado) não é trabalho certo - "a conferir", não
        # "pedir atestado"
        conf_ = set()
        if L.get("sem_baixa") and (L["vinc"][1] - L["vinc"][0]).days > 365:
            doc_ = ([max(antes)] if antes else []) + [o["fim"] for o in linhas_ if o is not L and o.get("vinc") == L["vinc"] and o["st"] != "sem"]
            if doc_:
                conf_ = {d for d in dias_ - antes if d > max(doc_)}
        for conj, outro, lst, tot, k_ in ((antes, dias_ - antes, itens_t, talvez, "talvez"), (dias_ - antes - conf_, antes | conf_, itens_p, pedir, "pedir"),
                                          (conf_, dias_ - conf_, itens_c, conferir, "conf")):
            novos = conj - tot
            tot |= conj
            L[k_ + "_dias"] = round(len(novos) / 3.0, 2)  # remição estimada desta linha, sem repetir dias de vínculos simultâneos
            if novos:
                L[k_ + "_ini"], L[k_ + "_fim"] = min(novos), max(novos)  # o trecho que entra na estimativa
                # trechos separados pela parte da outra lista (saldo no meio do vínculo): um a um, com as mesmas datas no texto e no pedido
                tr_, ou_ = [], sorted(outro)
                for d in sorted(novos):
                    if tr_ and bisect.bisect_right(ou_, tr_[-1][1]) == bisect.bisect_left(ou_, d):
                        tr_[-1][1] = d
                    else:
                        tr_.append([d, d])
                L[k_ + "_trechos"] = [tuple(t) for t in tr_]
                lst.append("%s, %s: ≈ %s" % (L["local"], " e ".join("%s a %s" % (_f(a), _f(b)) for a, b in tr_),
                                              rs.pl(len(novos), "dia trabalhado", "dias trabalhados")))
    # estudo: a estimativa começa depois do último semestre certificado (certidão desta execução)
    cert_fim = None
    for d in est_:
        if d["tipo"] != "Certidão de frequência escolar":
            continue
        m_ = re.match(r"(\d)º semestre de (\d{4})", d["num"] or "")
        fim_c = (date(int(m_.group(2)), 6, 30) if m_.group(1) == "1" else date(int(m_.group(2)), 12, 31)) if m_ else d["emissao"]
        cert_fim = max(x for x in (cert_fim, fim_c) if x) if fim_c else cert_fim
    est_estim, est_dias = [], set()
    for e in f.get("estudos") or []:
        if e.get("_doc"):
            continue  # (7.14.3) atestado de estudo com dias declarados: já é documento da comparação
        a, b = _dt(e.get("inicio") or ""), _dt(e.get("fim") or "") or imp
        # (7.14.2) atestado de estudo com as datas invertidas (início depois do fim): continua na tela, com "conferir datas"
        inv = bool(a and b and b < a and e.get("horas") and e.get("fim"))
        if inv:
            a, b = b, a
        if not a or not b or b < a or (inicio and b < inicio) or (cert_fim and b <= cert_fim):
            continue
        if not e.get("fim") and (imp - max(a, _dt(e.get("ult_registro_edu") or "") or a)).days > 365:
            continue  # matrícula aberta há mais de um ano sem registro escolar: a ficha não mostra frequência
        if cert_fim and a <= cert_fim and not e.get("horas"):
            a = cert_fim + timedelta(days=1)
        if e.get("horas"):
            est_estim.append({"txt": "%s, %s a %s: %s h declaradas na ficha ≈ %s%s" % (
                e["curso"] if (e.get("curso") or "").startswith("Atestado") else (e.get("curso") or "Estudo").title(), _f(a), _f(b), _nf(e["horas"]), rs.pl(int(e["horas"] // 12), "dia", "dias"),
                " (datas invertidas na ficha: conferir datas)" if inv else ""), "dias": e["horas"] / 12.0, "fim": b})
            continue
        dl = {d for d in _rf.dias_jornada_set(a, b, "seg-sex") if not _rf.em_recesso(d)} - est_dias
        est_dias |= dl
        if len(dl) >= 3:
            h = len(dl) * _rf.HORAS_DIA_ESTUDO
            est_estim.append({"txt": "%s, %s a %s: ≈ %s × %d h = %d h ≈ %s" % (
                (e.get("curso") or "Estudo").title(), _f(a), _f(b), rs.pl(len(dl), "dia letivo", "dias letivos"), _rf.HORAS_DIA_ESTUDO, h,
                rs.pl(int(h // 12), "dia", "dias")), "dias": h / 12.0, "fim": b})
    acomp_dias = round(sum(L.get("acomp_dias") or 0 for L in (trab or {}).get("linhas") or []), 2)
    estim = round(len(pedir) / 3.0 + len(talvez) / 3.0 + len(conferir) / 3.0 + acomp_dias + sum(x["dias"] for x in est_estim), 2)
    # ---- pontos a conferir (B) ----
    pontos = []

    def ponto(rot, cor, texto, tipo, curto=None, docs_=None):
        pontos.append({"rot": rot, "cor": cor, "texto": texto, "tipo": tipo, "curto": curto or texto, "docs": docs_ or []})

    nome_doc = lambda d: "%s%s" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") and d["num"] else (" · " + d["num"]) if d["num"] else "")
    dec_txt = ("da última decisão de remição do RSPE (%s)" % _f(ult_dec)) if ult_dec else "de qualquer remição no RSPE (o RSPE não tem remição concedida)"
    dec_a = ("à última decisão de remição do RSPE (%s)" % _f(ult_dec)) if ult_dec else "a qualquer remição no RSPE (o RSPE não tem remição concedida)"
    vivos = [d for d in desta if not d["hom"]]
    if contidos:
        ponto("Atestado repetido", "cinza", "%s - o período já está em outros atestados desta execução (atestado cumulativo): a comparação não "
              "soma os dias em dobro." % "; ".join("%s (%s, %s dias): %s" % (nome_doc(d), d["periodo"], _nf(d["dias"]), d["contido"]) for d in contidos),
              "contido", docs_=contidos)
    post = [d for d in vivos if d["data_ref"] and (not ult_dec or d["data_ref"] > ult_dec)]
    # vermelho: fato documental certo e com valor (atestado com os dias, sem peticionamento, posterior à última decisão)
    verm = [d for d in post if d["tipo"] == "Atestado de trabalho" and not d["pet_ok"] and d["dias"] and not d.get("ja_rem")]
    for d in verm:
        d["vermelho"] = True
    if verm:
        ponto("Sem peticionamento", "vermelho", "%s, emitido%s depois %s e sem registro de peticionamento na ficha: conferir nos autos se foi "
              "juntado; se não, pedir o peticionamento à unidade (%s)." % (
                  _lista(["%s (%s, %s dias)" % (nome_doc(d), _f(d["emissao"]), _nf(d["dias"])) for d in verm]), "s" if len(verm) > 1 else "",
                  dec_txt, rs.pl(len(verm), "documento", "documentos")), "sem_pet_posterior",
              curto="%s sem registro de peticionamento e posterior%s %s - conferir nos autos" % (
                  _lista([nome_doc(d) for d in verm]), "es" if len(verm) > 1 else "", dec_a), docs_=verm)
    p2 = [d for d in post if d not in verm]
    for d in [d for d in p2 if d.get("ja_rem")]:
        ponto("Remição no período", "amarelo", "%s (%s dias, %s): o RSPE tem remição sem documento na ficha com referência dentro do período do "
              "atestado (%s) - provavelmente de atestado parcial do mesmo período. Pedir ≈ %s (%s − %s), conferindo a decisão antes de requerer." % (
                  nome_doc(d), _nf(d["dias"]), d["periodo"], d["ja_rem_txt"], _nf(d["dias_pedir"]), _nf(d["dias"]),
                  _nf(sum(x["dias"] for x in d["ja_rem"]))), "ja_remido_periodo", docs_=[d],
              curto="%s: pedir ≈ %s (%s − %s) - conferir a remição de %s antes de requerer" % (
                  nome_doc(d), _nf(d["dias_pedir"]), _nf(d["dias"]), _nf(sum(x["dias"] for x in d["ja_rem"])),
                  _lista([_f(x["decisao"]) for x in d["ja_rem"]])))
    if p2:
        ponto("Posterior à última remição", "amarelo", "%s: emitido%s ou peticionado%s depois %s - provável pendência: conferir nos autos se "
              "já foi apreciado." % (_lista(["%s (%s%s)" % (nome_doc(d), _f(d["data_ref"]), (", %s dias" % _nf(d["dias"])) if d["dias"] else "") for d in p2]),
                                     "s" if len(p2) > 1 else "", "s" if len(p2) > 1 else "", dec_txt), "posterior",
              curto="%s posterior%s %s" % (_lista(["%s%s" % (nome_doc(d), (" (%s dias)" % _nf(d["dias"])) if d["dias"] else "") for d in p2]),
                                          "es" if len(p2) > 1 else "", dec_a), docs_=p2)
    dfn = [d for d in vivos if d["defensoria"] and d not in verm and not d.get("provavel")]
    if dfn:
        ponto("A conferir", "amarelo", "%s: enviado à Defensoria, sem registro de protocolo na ficha - conferir se a Defensoria o juntou aos autos." % (
            _lista(["%s (%s dias, %s)" % (nome_doc(d), _nf(d["dias"]), _f(d["emissao"])) for d in dfn])), "defensoria", docs_=dfn)
    sem_pet = [d for d in vivos if not d["pet_ok"] and not d["defensoria"] and d not in post and d["tipo"] != "Exame" and not d.get("provavel")]
    prov = [d for d in vivos if d.get("provavel") and not d["pet_ok"] and d not in post]
    if prov:
        ponto("Provavelmente remido", "cinza", "Sem registro de peticionamento na ficha, mas o RSPE tem remição do mesmo valor (ou da soma "
              "de documentos) decidida depois da emissão: %s - provavelmente remido; conferir nos autos (indicação por valor e data, sem vínculo)." % _lista(
                  ["%s (%s, %s → remição de %s%s)" % (nome_doc(d), _f(d["emissao"]), ("%s h ÷ 12 = %s dias; a ficha declara %s" % (
                      d["horas"], _nf(d["provavel_horas"]), _nf(d["dias"]))) if d.get("provavel_horas") else "%s dias" % _nf(d["dias"]), d["provavel"],
                                                          ((", somado %s" % _lista([re.sub(r"^a ", "à ", re.sub(r"^o ", "ao ", n_)) for n_ in d["soma_com"]])) if d.get("soma_com") else "") +
                                                          ("; decidida mais de 180 dias depois" if d.get("provavel_tarde") else "")) for d in prov]),
              "provavel_remido", docs_=prov)
    if sem_pet:
        ponto("A conferir", "amarelo", "Sem registro de peticionamento na ficha: %s - conferir nos autos se foi juntado e apreciado." % (
            _lista(["%s (%s%s)" % (nome_doc(d), _f(d["emissao"]), (", %s dias" % _nf(d["dias"])) if d["dias"] else "") for d in sem_pet])), "sem_pet",
              docs_=sem_pet)
    for d in [d for d in vivos if d["tipo"] == "Exame"]:
        if d.get("provavel_ex"):
            ponto("Exame", "cinza", "Exame: %s (%s) - o RSPE tem remição decidida em %s, possivelmente deste exame; conferir nos autos com "
                  "quantas áreas (%s)." % (d["num"], d["pet"], d["provavel_ex"], d["sem_valor"]), "exame", docs_=[d])
        else:
            ponto("A conferir", "amarelo", "Exame: %s (%s) - %s; conferir se já foi remido e com quantas áreas." % (
                d["num"], d["pet"], d["sem_valor"]), "exame", docs_=[d])
    for d, x in menor:
        d["menor"] = "%s dias em %s" % (_nf(x["dias"]), _f(x["decisao"]))
        ponto("Aviso", "cinza", "Leitura (%s, %s pela ficha): a remição seguinte do RSPE é de %s dias, decidida em %s - conferir se foi "
              "remida a menor (Res. CNJ 391/2021, art. 5º: 4 dias por obra)." % (_f(d["emissao"]), rs.pl(int(d["dias"]), "dia", "dias"),
                                                                              _nf(x["dias"]), _f(x["decisao"])), "leitura_menor", docs_=[d],
              curto="leitura de %s: %s pela ficha, o RSPE deu %s em %s - remida a menor? conferir" % (
                  _f(d["emissao"]), _nf(d["dias"]), _nf(x["dias"]), _f(x["decisao"])))
    for d in [d for d in vivos if d.get("pend_prov")]:
        ponto("A conferir", "amarelo", "Provável pendência: %s." % d["pend_prov"], "pend_cert",
              docs_=[o for o in vivos if o["chave"] in d["pend_docs"]] or [d])
    sv = [d for d in vivos if d["sem_valor"] and d["tipo"] != "Exame" and not d.get("provavel_ex")]
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
    # dias implausíveis: os dias trabalhados declarados (ou, sem eles, os dias de remição × 3) passam dos dias corridos do período do
    # atestado - ou do período implícito, no atestado sem período (com os dias trabalhados declarados, o aviso de capacidade já aponta)
    inf_ = (trab or {}).get("inferidos") or {}
    for d in at_:
        ps = d["periodo"].split(" a ")
        a0, b0 = (_dt(ps[0]), _dt(ps[1])) if len(ps) == 2 else (None, None)
        if not a0 and inf_.get(d["chave"]):
            a0, b0 = inf_[d["chave"]]["ini"], inf_[d["chave"]]["fim"]
        poss = (b0 - a0).days + 1 if a0 and b0 and b0 >= a0 else 0
        need = d["trab"] or (d["dias"] or 0) * 3
        if poss and need > poss + 3 and not (d["trab"] and len(ps) == 2):
            ponto("Aviso", "cinza", "Atestado nº %s: %s %s, mas %s (%s a %s) tem %s - dias implausíveis: conferir o atestado (o juízo pode "
                  "mandar retificar)." % (d["num"], _nf(d["dias"]) + " dias de remição" if not d["trab"] else "%s trabalhados" % d["trab"],
                                          "pedem %s dias trabalhados" % _nf(need) if not d["trab"] else "declarados",
                                          "o período" if len(ps) == 2 else "o período implícito", _f(a0), _f(b0),
                                          rs.pl(poss, "dia corrido", "dias corridos")), "implausivel", docs_=[d],
                  curto="atestado nº %s: %s dias de remição para %s - dias implausíveis, conferir" % (d["num"], _nf(d["dias"]), rs.pl(poss, "dia corrido", "dias corridos")))
    # (7.14.1) atestado de outra unidade: o texto cita a sigla de uma unidade penal diferente daquela em que a ficha mostra o assistido
    # durante todo o período do atestado, e a ficha não registra trabalho nesse período - aviso para conferir se o atestado é dele
    # e se o período está certo (não muda a conta)
    tl_un = _rf.linha_unidades_exibicao(f)
    trab_f = [(_dt(t.get("inicio") or ""), _dt(t.get("fim") or "") or imp) for t in f.get("trabalho") or []]
    at_chave = {chave_atestado(a.get("numero"), _dt(a.get("data") or "")): a for a in f.get("atestados") or []}
    for d in at_:
        a = at_chave.get(d["chave"])
        if not a:
            continue
        ps = d["periodo"].split(" a ")
        a0, b0 = (_dt(ps[0]), _dt(ps[1])) if len(ps) == 2 else (None, None)
        if not a0 or not b0 or any(x and y and x <= b0 and a0 <= y for x, y in trab_f):
            continue
        un_ini = [u for e_, u in tl_un if e_ <= a0]
        if not un_ini or any(a0 < e_ <= b0 for e_, _u in tl_un):
            continue  # unidade desconhecida no início do período, ou mudança de unidade dentro dele
        un_p = un_ini[-1]
        sig = sorted({s for s in re.findall(r"\b[A-Z]{2,8}\b", _sa(_texto_atestado(f, a))) if s in SIGLAS_UNIDADES_PENAIS})
        if sig and not any(_sigla_da_unidade(s, un_p) for s in sig):
            ponto("Aviso", "cinza", "Atestado nº %s (%s) cita %s, mas a ficha mostra o assistido em %s em todo o período, sem trabalho registrado - "
                  "conferir se o atestado é deste assistido e se o período está certo." % (d["num"], d["periodo"], _lista(sig), _rf.nome_unidade(un_p)),
                  "outra_unidade", docs_=[d],
                  curto="atestado nº %s cita %s, mas a ficha mostra o assistido em %s no período, sem trabalho - conferir" % (
                      d["num"], _lista(sig), _rf.nome_unidade(un_p)))
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
        ponto("Pedir atestado", "amarelo", "Trabalho registrado na ficha sem atestado%s: %s (≈ %s de remição, estimativa "
              "de segunda a sábado - ou pela jornada registrada na ficha - até a impressão da ficha, %s). Pedir o atestado à unidade. Não entra na comparação." % (
                  " e fora do saldo de remição do RSPE que nenhum documento explica" if (sem_doc or exc_) else " nem remição do RSPE que o explique",
                  "; ".join(itens_p), _nf(len(pedir) / 3.0), _f(imp)),
              "pedir_atestado", curto="trabalho sem atestado (≈ %s dias de remição): pedir atestado" % _nf(len(pedir) / 3.0))
    if conferir:
        ponto("Vínculo sem baixa", "amarelo", "Trabalho sem atestado depois do último dia documentado do vínculo (remição ou atestado), sem baixa "
              "na ficha - a ficha registra o início do trabalho e só a saída da unidade: %s (≈ %s de remição). Não há prova de que o trabalho "
              "continuou até a saída: conferir com a unidade antes de pedir o atestado. Não entra na comparação." % (
                  "; ".join(itens_c), _nf(len(conferir) / 3.0)), "sem_baixa",
              curto="trabalho sem baixa na ficha depois da última remição do vínculo (≈ %s dias de remição): conferir com a unidade se "
                    "continuou até a saída" % _nf(len(conferir) / 3.0))
    if aparte:
        ponto("À parte", "cinza", "Trabalho sem atestado em período em que esta execução estava interrompida: %s - fora da custódia desta "
              "execução, não entra na estimativa (a remição desse trabalho é da execução em que a pessoa estava presa)." % "; ".join(aparte),
              "trabalho_aparte")
    if acomp:
        ponto("Em curso", "cinza", "Trabalho em curso há até 90 dias, sem atestado: %s (≈ %s de remição) - o atestado do período ainda não costuma "
              "ter sido emitido: acompanhar e pedir ao fim do período. Não entra na comparação." % ("; ".join(acomp), _nf(acomp_dias)), "em_curso")
    if talvez:
        ponto("Pode já estar remido", "amarelo", "Trabalho sem atestado na ficha coberto pelo saldo de remição do RSPE que nenhum documento da "
              "ficha explica ou pelos dias que um atestado declara além do seu período (%s), do trabalho mais próximo da remição para o mais antigo: %s (≈ %s de remição). Pode ter sido remido com atestado "
              "que a ficha não registra - conferir nos autos antes de pedir." % (_lista(saldo_txt), "; ".join(itens_t), _nf(len(talvez) / 3.0)),
              "talvez_remido", curto="trabalho sem atestado coberto pela remição sem documento: pode já estar remido - conferir")
    for x in f.get("estudo_cancelado_sem_matricula") or []:
        d_ = _dt(x.get("data") or "")
        if d_ and (not inicio or d_ >= inicio):
            # cancelamento lançado no dia da saída da unidade ("Saida do Presidio"): a matrícula era da unidade de onde ele saiu, e é
            # a ela que se pede a certidão (a ficha já mostra a unidade de destino nesse dia)
            un_ = ""
            if re.search(r"SAIDA D[OA] (?:PRESIDIO|UNIDADE)|TRANSFER", _sa(x.get("texto"))) or any(
                    _dt(e.get("data") or "") == d_ and re.search(r"SAIDA DA UNIDADE PENAL", _sa(e.get("texto"))) for e in f.get("eventos") or []):
                tl_ = [(a_, u_) for a_, u_ in _rf.linha_unidades_exibicao(f) if a_ < d_]
                un_ = _rf.nome_unidade(tl_[-1][1]) if tl_ else ""
                if un_ == _rf.SEM_UNIDADE:
                    un_ = ""
            art_ = "da" if re.match(r"(?:PENITENCI|COLONIA|UNIDADE|CASA|CADEIA)", _sa(un_)) else "do"
            ponto("Estudo a conferir", "amarelo", "A ficha registra o cancelamento de matrícula em %s%s, mas não a matrícula nem o período: pedir a "
                  "certidão de frequência escolar%s e conferir nos autos se houve remição (LEP, art. 126, § 1º, I)." % (
                      _f(d_), (", na saída %s %s" % (art_, un_)) if un_ else "", (" %s %s" % ("à" if art_ == "da" else "ao", un_)) if un_ else ""), "estudo_sem_matricula",
                  curto="matrícula cancelada em %s%s sem a matrícula registrada: pedir a certidão de frequência" % (
                      _f(d_), (" (%s)" % un_) if un_ else ""))
    for x in est_estim:
        # estudo que vai além da última decisão de remição pode estar sem remição: ponto a conferir; o anterior, só informação
        ponto("Estudo sem certidão", "amarelo" if not ult_dec or x["fim"] > ult_dec else "cinza", "%s (estimativa, sem certidão de horas na ficha) - conferir nos autos se a certidão foi juntada; se "
              "não, pedir a certidão de horas. Não entra na comparação." % x["txt"], "estudo_estimado")
    # perdas de dias remidos (LEP, art. 127): os testes da Auditoria (1/3 da remição até a falta, perda sem falta datada, perda sobre
    # remição posterior à falta, duplicidade) - regra de lei, não depende de saber a origem da remição
    if R["perdido"]:
        import rspe_auditoria as _ra
        try:
            its_ = _ra._perda_remidos(r.get("_incidentes") or [], R["perdido"], r.get("_eventos") or [],
                                      ficha=_base_127(rem_, expl, desta, post, trab))
        except Exception:
            its_ = []
        for it in its_:
            if it.get("nivel") != "info":
                ponto("Perda (art. 127)", "amarelo", "%s: %s" % (it["titulo"], it.get("detalhe") or ""), "perda", curto=it["titulo"])
    # ---- conclusão em linguagem simples: a favor da ficha, direta (amarelo); RSPE maior, uma frase informativa (cinza) ----
    if dif > TOL_COMPARACAO:
        concl, concl_cor = ("A ficha comprova %s dias a mais do que o RSPE concedeu. Conferir nos autos se cada atestado foi apreciado." % _nf(dif),
                            "amarelo")
    elif dif >= -TOL_COMPARACAO:
        concl, concl_cor = "Sem diferença: dentro da tolerância de 3 dias (frações).", "verde"
    else:
        # (7.14.2) a diferença pode vir de documentos fora da ficha ou de documentos da ficha sem valor (ENEM/ENCCEJA, cursos ou certidões
        # sem carga horária): quando houver, quais
        sv_ = [d for d in desta if d["sem_valor"] and not d["dias"]]
        concl, concl_cor = ("O RSPE concedeu %s dias a mais do que a ficha comprova (documentos fora da ficha ou sem valor na ficha - ENEM/ENCCEJA, "
                            "cursos ou certidões sem carga horária%s). %s" % (
                                _nf(-dif), ("; na ficha, sem valor: %s" % _lista([nome_doc(d) + (" (%s)" % _f(d["emissao"]) if d["emissao"] else "") for d in sv_]))
                                if sv_ else "", _sem_pedido_totais(post, ult_dec, nome_doc)), "cinza")
        if any(d.get("pend_prov") for d in desta):
            # (7.14.7) certidões peticionadas que somam bem mais do que a remição decidida: provável pendência (amarelo)
            concl = concl.replace("Nada a requerer por esta conta.", "A diferença de totais, sozinha, não gera pedido; mas há provável "
                                  "pendência de certidão peticionada e não apreciada: ver os pontos.")
            concl_cor = "amarelo"
    pouco = R["concedido"] > 1.3 * comp + TOL_COMPARACAO
    # ---- situação factual de cada documento (D) ----
    for d in docs:
        if d["fora"]:
            d["sit"], d["cor"] = "À parte: " + d["fora"], "cinza"
        elif d["hom"]:
            d["sit"], d["cor"] = "Homologado (marcado na conferência)", "verde"
        elif d.get("contido") and d["dias_soma"] == 0:
            d["sit"], d["cor"] = d["contido"][0].upper() + d["contido"][1:], "cinza"
        elif d.get("vermelho"):
            d["sit"], d["cor"] = "Sem peticionamento e posterior à última remição", "vermelho"
        elif d.get("ja_rem"):
            d["sit"], d["cor"] = "Pedir ≈ %s (%s − %s): conferir a remição de %s antes de requerer" % (
                _nf(d["dias_pedir"]), _nf(d["dias"]), _nf(sum(x["dias"] for x in d["ja_rem"])), _lista([_f(x["decisao"]) for x in d["ja_rem"]])), "amarelo"
        elif d in post:
            d["sit"], d["cor"] = ("Posterior à última remição (%s)" % _f(ult_dec)) if ult_dec else "Sem remição no RSPE", "amarelo"
        elif d.get("provavel"):
            d["sit"], d["cor"] = (("Soma de mesmo valor decidida em %s (soma com %s = %s dias; mais de 180 dias depois da emissão): conferir"
                                   if d.get("provavel_tarde") else "Provavelmente remido em %s (soma com %s = %s dias): conferir") % (
                d["provavel"], _lista(d["soma_com"]), _nf(d["soma_rem"])) if d.get("soma_com") else
                ("Provavelmente remido em %s (%s dias pela carga horária: %s h ÷ 12; a ficha declara %s): conferir" % (
                    d["provavel"], _nf(d["provavel_horas"]), d["horas"], _nf(d["dias"]))) if d.get("provavel_horas") else
                ("Mesmo valor decidido em %s (mais de 180 dias depois da emissão): conferir" if d.get("provavel_tarde") else
                 "Provavelmente remido em %s (mesmo valor): conferir") % d["provavel"]), "cinza"
            # (7.14.5) valor próximo, não igual (51 no RSPE, 50 no atestado; não a fração truncada, 47 x 47,66): diz os dois
            pv_ = d.get("provavel_dias")
            if pv_ is not None and not d.get("soma_com") and not d.get("provavel_horas") and round(pv_) != round(d["dias"] or 0) and int(pv_) != int(d["dias"] or 0):
                d["sit"] = d["sit"].replace("Mesmo valor decidido", "Valor próximo decidido").replace(
                    "(mesmo valor)", "(valor próximo: %s dias no RSPE, %s no documento)" % (_nf(pv_), _nf(d["dias"])))
        elif d.get("rem_conf"):
            d["sit"], d["cor"] = d["rem_conf"][0].upper() + d["rem_conf"][1:], "cinza"
        elif d.get("provavel_ex"):
            d["sit"], d["cor"] = "Possivelmente remido em %s: conferir %s" % (d["provavel_ex"], "as áreas" if d["tipo"] == "Exame" else "as horas"), "cinza"
        elif d.get("menor"):
            d["sit"], d["cor"] = "Remida a menor? RSPE: %s - conferir" % d["menor"], "cinza"
        elif not d["pet_ok"]:
            d["sit"], d["cor"] = "Sem registro de peticionamento", "amarelo"
        else:
            d["sit"], d["cor"] = "Peticionado · conferir a decisão", "cinza"
    for d in docs:
        if d.get("contido") and d.get("dias_soma"):
            d["sit"] += " · " + d["contido"]
        for k_ in ("nota_autos", "nota_ano"):
            if d.get(k_):
                d["sit"] += " · " + d[k_]
    # RSPE maior que a ficha: o que seria amarelo vira cinza (informativo). Ficam com a cor só o pedido de atestado do trabalho depois
    # da última remição de trabalho e o documento vermelho (com dias, sem peticionamento, depois da última decisão)
    if rspe_maior:
        for p_ in pontos:
            if p_["cor"] == "amarelo" and p_["tipo"] not in ("pedir_atestado", "pend_cert"):
                p_["cor"], p_["cor0"] = "cinza", "amarelo"
        for d in docs:
            if d["cor"] == "amarelo":
                d["cor"] = "cinza"
    outra = outra_execucao(r, f)
    onde = onde_diferenca(dif, docs, post, verm, pontos, trab, ult_dec, rspe_maior, acomp_l)
    return {"onde": onde, "rspe_maior": rspe_maior, "outra_exec": outra, "acomp": acomp_l, "corte": corte, "_sem_doc": sem_doc, "R": R, "docs": docs, "at_desta": soma(at_), "n_desta": len(at_), "man": soma(man_), "n_man": len(man_), "est_comp": soma(est_),
            "leitura": soma(lei_), "obras": int(round(soma(lei_) / 4)), "fora": [d for d in docs if d["fora"]], "comp": comp, "dif": dif,
            "estim": estim, "dif_estim": round(dif + estim, 2), "pouco": pouco, "concl": concl, "concl_cor": concl_cor, "pontos": pontos,
            "pedir_dias": len(pedir) / 3.0, "talvez_dias": len(talvez) / 3.0, "conf_dias": len(conferir) / 3.0, "est_estim": est_estim, "est_cert_fim": cert_fim, "impressao": imp, "inicio": inicio,
            "ult_at": ult_at, "post": post, "vermelho": verm, "faltas_127": faltas_graves(r, f)}


def _sem_pedido_totais(post, ult_dec, nome_doc):
    """(7.14.5) Fecho da conclusão "RSPE maior": a diferença de totais, sozinha, não gera pedido - mas o documento com dias posterior à
    última remição do RSPE (o vermelho e o pedido de declaração) não está nas remições dele e continua a requerer."""
    pend = [d for d in post or [] if d.get("dias") and not d.get("provavel") and not d.get("hom")]
    if not pend:
        return "Nada a requerer por esta conta."
    return ("A diferença de totais, sozinha, não gera pedido; mas %s, posterior%s à última remição do RSPE%s, não %s nas remições dele: "
            "ver os pontos e o pedido abaixo." % (
                _lista(["%s %s%s (%s dias)" % ("a" if re.match(r"(?:Certid|Leitura)", d["tipo"]) else "o", nome_doc(d)[0].lower(), nome_doc(d)[1:],
                                                 _nf(d["dias"])) for d in pend]), "es" if len(pend) > 1 else "",
                " (%s)" % _f(ult_dec) if ult_dec else "", "estão" if len(pend) > 1 else "está"))


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
        out.append({"doc": d, "data": fim or d["emissao"], "dias": d.get("dias_pedir") or d["dias"],
                    "rotulo": "%s%s (%s dias)" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") and d["num"] else
                                                                       (" · " + d["num"]) if d["num"] else "", _nf(d["dias"]))})
    return out


def outra_execucao(r, f):
    """RSPE de outra execução associado à ficha pelo nome? Aviso no topo da aba Ficha: o RSPE é de outro tribunal estadual (a ficha do
    SIAPEN é de unidade prisional de MS) ou a ficha cita processos, nenhum está no RSPE e todos são de outro tribunal. "" sem sinal."""
    fic = {re.sub(r"\D", "", x or "") for x in f.get("autos") or []} - {""}
    procs = {re.sub(r"\D", "", p or "") for p in _procs_r(r)} - {""}
    ex = re.sub(r"\D", "", r.get("processo_execucao") or "")
    if fic & (procs | {ex} - {""}):
        return ""  # (7.14.7) a ficha cita o número do próprio RSPE (peticionamentos nos autos desta execução): é o RSPE desta execução
    t = _sa(" ".join(str(r.get(k) or "") for k in ("tribunal", "vara")))
    m = re.search(r"\bTJ([A-Z]{2})\b", t)
    if m and m.group(1) != "MS":
        return ("RSPE de outra execução? O RSPE é do TJ%s (%s) e a ficha é de unidade prisional de MS: conferir se é o RSPE desta execução "
                "antes de usar a comparação." % (m.group(1), re.sub(r"\s+", " ", r.get("vara") or "").strip()))
    jtr = lambda x: x[13:16] if len(x) == 20 else ""  # segmento J.TR do número CNJ (8.12 = TJMS)
    if fic and procs and not fic & procs and jtr(ex) and all(jtr(x) and jtr(x) != jtr(ex) for x in fic):
        return ("RSPE de outra execução? A ficha não cita nenhum dos processos do RSPE (execução %s): conferir se é o RSPE desta execução "
                "antes de usar a comparação." % (r.get("processo_execucao") or "?"))
    return ""


def onde_diferenca(dif, docs, post, verm, pontos, trab, ult_dec, rspe_maior=False, acomp=None):
    """Visão inicial da aba Ficha - "Onde pode estar a diferença": até 4 linhas objetivas, cada uma com o que conferir e onde. Ordem:
    (1) fato - documento desta execução emitido ou peticionado depois da última decisão de remição (o sem peticionamento primeiro) e,
    havendo diferença a favor da ficha, o documento sem registro de peticionamento (sem remição de mesmo valor) ou enviado à Defensoria;
    (2) "Pedir atestado": trabalho sem atestado, do mais recente ao mais antigo, com o trecho que entra na estimativa; (3) numa linha só,
    o trabalho sem atestado que "pode já estar remido"; (4) trabalho em curso há até 90 dias, a acompanhar; (5) vínculo a confirmar;
    (6) os demais pontos a conferir e os avisos de leitura remida a menor e de dias implausíveis. Passando de 4, as 3 primeiras e
    "… e mais N". RSPE maior que a ficha: o amarelo vira cinza, salvo o pedido de atestado e o vermelho. Sem nada: "Sem diferença a conferir."."""
    out = []
    am = "cinza" if rspe_maior else "amarelo"
    dias_ = lambda v: "%s %s" % (_nf(v), "dia" if _nf(v) == "1" else "dias")
    dec = ("sem decisão de remição posterior no RSPE (última: %s)" % _f(ult_dec)) if ult_dec else "sem remição no RSPE"

    def nome(d):
        n_ = "%s%s" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") and d.get("num") else (" · " + d["num"]) if d.get("num") else "")
        per = d.get("periodo") or ""
        return n_ + ((" de " + per) if per and not per.startswith("sem período") else "") + ((" (%s)" % dias_(d["dias"])) if d.get("dias") else "")

    for d in verm + [d for d in post if d not in verm]:
        quando = ("peticionado em %s" % _f(d["data_ref"])) if d["pet_ok"] else "emitido em %s, sem registro de peticionamento" % _f(d["emissao"])
        ja_ = (" - pedir ≈ %s (%s − %s): conferir antes a remição de %s, com referência dentro do período" % (
            _nf(d["dias_pedir"]), _nf(d["dias"]), _nf(sum(x["dias"] for x in d["ja_rem"])), _lista([_f(x["decisao"]) for x in d["ja_rem"]]))) if d.get("ja_rem") else ""
        out.append({"t": "%s, %s, %s%s" % (nome(d), quando, dec, ja_), "c": "vermelho" if d in verm else am})
    if dif > TOL_COMPARACAO:
        for d in [d for d in docs if not d["fora"] and not d["hom"] and d not in post and not d["pet_ok"] and d.get("dias") and not d.get("provavel")]:
            out.append({"t": "%s %s - conferir se foi juntado e apreciado" % (nome(d), "enviado à Defensoria, sem registro de protocolo" if d["defensoria"]
                                                                                else "sem registro de peticionamento"), "c": "amarelo"})
    if dif > TOL_COMPARACAO and not out:
        out.append({"t": "Diferença de %s a favor da ficha, sem documento posterior à última remição: conferir nos autos se cada atestado foi "
                         "apreciado e com quantos dias" % dias_(dif), "c": "amarelo"})
    L_ = (trab or {}).get("linhas") or []
    for L in sorted([L for L in L_ if L.get("pedir_dias")], key=lambda L: L["pedir_fim"], reverse=True):
        # vínculo em curso (já passou dos 90 dias): a estimativa vai até a impressão da ficha - o texto diz isso e há quanto tempo
        # o trabalho está em curso (o motivo de pedir o atestado e não só acompanhar)
        ate = ("%s (impressão da ficha; em curso há %d dias)" % (_f(L["pedir_fim"]), L["curso_dias"])) if L.get("em_curso") and L.get("curso_dias") \
            and (L["fim"] - L["pedir_fim"]).days <= 7 else _f(L["pedir_fim"])
        tr_ = L.get("pedir_trechos") or [(L["pedir_ini"], L["pedir_fim"])]
        per_ = " e ".join("de %s a %s" % (_f(a_), ate if b_ == L["pedir_fim"] else _f(b_)) for a_, b_ in tr_)
        out.append({"t": "Pedir atestado: trabalho em %s %s, sem atestado (≈ %s de remição)" % (
            L["local"], per_, dias_(L["pedir_dias"])), "c": "amarelo"})
    tz = sorted([L for L in L_ if L.get("talvez_dias")], key=lambda L: L["talvez_fim"], reverse=True)
    if tz:
        it = ["%s de %s a %s" % (L["local"], _f(L["talvez_ini"]), _f(L["talvez_fim"])) for L in tz[:3]]
        out.append({"t": "Pode já estar remido (trabalho sem atestado coberto pela remição do RSPE sem documento na ficha): %s (≈ %s) - conferir "
                         "nos autos antes de pedir" % (_lista(it) if len(tz) <= 3 else ", ".join(it) + " e mais %d" % (len(tz) - 3),
                                                       dias_(sum(L["talvez_dias"] for L in tz))), "c": am})
    for a_ in acomp or []:
        out.append({"t": "Acompanhar: trabalho em %s em curso desde %s, sem atestado (≈ %s até a impressão da ficha)" % (
            a_["local"], _f(a_["ini"]), dias_(a_["dias"])), "c": "cinza"})
    conf = [L for L in L_ if L["st"] in ("possivel", "provavel")]
    if conf:
        ats = list(dict.fromkeys(L["at"] for L in conf if L["at"]))
        out.append({"t": "%s com vínculo %s: confirmar %s nº %s" % (
            rs.pl(len(conf), "período", "períodos"), "sugerido" if all(L["st"] == "provavel" for L in conf) else "possível ou sugerido"
            if any(L["st"] == "provavel" for L in conf) else "possível",
            "o atestado" if len(ats) == 1 else "os atestados", _lista(ats)), "c": am})
    ja = {"sem_pet_posterior", "posterior", "pedir_atestado", "talvez_remido", "ja_remido_periodo"} | ({"sem_pet", "defensoria"} if dif > TOL_COMPARACAO else set())
    for p_ in pontos:
        if ((p_.get("cor0") or p_["cor"]) == "amarelo" and p_["tipo"] not in ja) or p_["tipo"] in ("leitura_menor", "implausivel", "outra_unidade"):
            t_ = p_["curto"]
            out.append({"t": t_[0].upper() + t_[1:], "c": p_["cor"]})
    if len(out) > 4:
        out = out[:3] + [{"t": "… e mais %d na visualização detalhada" % (len(out) - 3), "c": "cinza"}]
    if not out and rspe_maior:
        # (7.14.2) RSPE maior que a ficha sem nenhum ponto (ficha sem documentos, p. ex.): informativo, não "sem diferença"
        out.append({"t": "RSPE maior que a ficha em %s: documentos fora da ficha ou sem valor na ficha - nada a requerer por esta conta" % dias_(-dif),
                    "c": "cinza"})
    return out or [{"t": "Sem diferença a conferir.", "c": "verde"}]
