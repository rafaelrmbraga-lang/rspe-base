// APTO - Triagem da Mesa do Defensor (SEEU): funções puras, sem acesso ao Chrome. Usadas pela página da triagem
// (triagem.js) e pelos testes (node). Leem o HTML que o próprio SEEU devolve:
//   - Mesa do Defensor (mesaDefensor1Grau.do?actionType=listar): processo, assistido, defensor, datas e prazo;
//   - página do processo (visualizacaoProcesso.do): quadro "Pendências" (motivo da intimação) e movimentações;
//   - lista de arquivos de um movimento (movimentacaoArquivoDocumento.do): o link do PDF (arquivo.do);
//   - texto do PDF (extraído pelo pdf.js na página): resumo, dispositivo, prazo e alertas.
// Nada aqui faz pedido ao SEEU nem decide pelo defensor: é triagem, para ordenar e destacar.
(function (raiz) {
  "use strict";

  const ORIGEM = "https://seeu.pje.jus.br";
  // abas da Mesa do Defensor (finalidadeRemessa) e situações (rádio "Situação")
  const ABAS = { 5: "Manifestação", 2: "Ciência", 7: "Razões/Contrarrazões" };
  const SITUACOES = { 1: "Recebidas e não lidas", 2: "Lidas e aguardando análise", 3: "Aguardando assinatura" };
  const MESES = { janeiro: 1, fevereiro: 2, marco: 3, abril: 4, maio: 5, junho: 6, julho: 7, agosto: 8, setembro: 9, outubro: 10, novembro: 11, dezembro: 12 };

  // ---------------------------------------------------------------- texto
  const ENT = { nbsp: " ", amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", ordm: "º", ordf: "ª", sect: "§", deg: "°", ndash: "–", mdash: "—", laquo: "«", raquo: "»" };
  function entidades(s) {
    return String(s || "").replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
      if (e[0] === "#") {
        const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
        return n > 0 && n < 0x110000 ? String.fromCodePoint(n) : m;
      }
      const k = e.toLowerCase();
      return Object.prototype.hasOwnProperty.call(ENT, k) ? ENT[k] : m;
    });
  }
  // HTML -> texto de uma linha (sem tags, scripts e estilos; espaços juntados)
  function texto(html) {
    return entidades(String(html || "").replace(/<(script|style|template)\b[\s\S]*?<\/\1>/gi, " ").replace(/<[^>]*>/g, " "))
      .replace(/[\s\u00a0]+/g, " ").trim();
  }
  // minúsculas sem acento, para comparar
  function normal(s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
  }
  function cnj(t) {
    const m = /\b(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})\b/.exec(String(t || ""));
    return m ? `${m[1]}-${m[2]}.${m[3]}.${m[4]}.${m[5]}.${m[6]}` : "";
  }
  // "final" do nº: o último algarismo antes do traço (0011147-54... -> 7)
  function finalDoNumero(processo) {
    const m = /^(\d{7})-/.exec(cnj(processo));
    return m ? Number(m[1][6]) : null;
  }
  // endereço absoluto no SEEU (o HTML traz "/seeu/...", "https://seeu.pje.jus.br/seeu/..." ou relativo)
  function absoluto(href) {
    const h = entidades(String(href || "").trim());
    if (/^https?:\/\//i.test(h)) return h;
    if (h.startsWith("/")) return ORIGEM + h;
    return ORIGEM + "/seeu/" + h.replace(/^\.\//, "");
  }
  // dd/mm/aaaa -> número aaaammdd (0 se não for data)
  function dataNum(d) {
    const m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(d || "");
    return m ? Number(m[3] + m[2] + m[1]) : 0;
  }
  function dataBr(dia, mes, ano) {
    const p = (n) => String(n).padStart(2, "0");
    return `${p(dia)}/${p(mes)}/${ano}`;
  }

  // ---------------------------------------------------------------- faixas de final
  // "0-2, 5, 7 a 9" -> Set {0,1,2,5,7,8,9}; vazio -> null (sem filtro); texto inválido -> null
  function faixasFinal(txt) {
    const s = String(txt || "").trim().replace(/\s*(?:–|—|até|ate|\ba\b)\s*/gi, "-").replace(/\s*-\s*/g, "-");
    if (!s) return null;
    const r = new Set();
    for (const p of s.split(/[,;\s]+/)) {
      const m = /^(\d)-(\d)$/.exec(p);
      if (m) {
        let a = Number(m[1]), b = Number(m[2]);
        if (a > b) [a, b] = [b, a];
        for (let i = a; i <= b; i++) r.add(i);
      } else if (/^\d$/.test(p)) r.add(Number(p));
    }
    return r.size ? r : null;
  }

  // Set {0,1,2,5} -> "0-2, 5" (o inverso de faixasFinal, para os botões de 0 a 9)
  function faixaTexto(conj) {
    const v = [...(conj || [])].map(Number).filter((n) => n >= 0 && n <= 9).sort((x, y) => x - y);
    const partes = [];
    for (let i = 0; i < v.length; i++) {
      let j = i;
      while (j + 1 < v.length && v[j + 1] === v[j] + 1) j++;
      partes.push(j - i >= 2 ? `${v[i]}-${v[j]}` : j > i ? `${v[i]}, ${v[j]}` : `${v[i]}`);
      i = j;
    }
    return partes.join(", ");
  }

  // ---------------------------------------------------------------- Mesa do Defensor
  // {total, de, ate, pageSize, campos:{hidden do formulário}, linhas:[...]}
  function lerMesa(html) {
    html = String(html || "");
    const r = { total: 0, de: 0, ate: 0, pageSize: 0, campos: {}, linhas: [] };
    const nav = /(\d+)\s+registro\(s\)\s+encontrado\(s\)(?:,\s*exibindo de\s+(\d+)\s+at[ée]\s+(\d+))?/i.exec(texto(html));
    if (nav) { r.total = Number(nav[1]); r.de = Number(nav[2] || 0); r.ate = Number(nav[3] || 0); }
    const form = /<form[^>]*name="mesaDefensor1GrauForm"[\s\S]*?<\/form>/i.exec(html);
    for (const m of (form ? form[0] : html).matchAll(/<input[^>]*type="hidden"[^>]*>/gi)) {
      const nome = /name="([^"]+)"/i.exec(m[0]), valor = /value="([^"]*)"/i.exec(m[0]);
      if (nome) r.campos[nome[1]] = valor ? entidades(valor[1]) : "";
    }
    r.pageSize = Number(r.campos.pageSize || 0);
    const pedacos = html.split(/<tr\s+class="(?:even|odd)[^"]*"[^>]*>/i).slice(1);
    for (const p0 of pedacos) {
      const p = p0.split(/<tr\s+class="(?:even|odd)/i)[0];
      const link = /href="([^"]*visualizacaoProcesso\.do\?_tj=[0-9a-f]+)"/i.exec(p);
      if (!link) continue;
      const em = /<em[^>]*>\s*([^<]+?)\s*<\/em>/i.exec(p);
      const processo = cnj(em ? em[1] : p);
      if (!processo) continue;
      const seq = /<td[^>]*align="center"[^>]*>\s*(\d+)\s*<\/td>/i.exec(p);
      const classeM = /<td style="text-align:center">\s*<a[^>]*title="([^"]*)"[^>]*>[\s\S]*?<\/a>([\s\S]*?)<\/td>/i.exec(p);
      const exec = /Executado:[\s\S]*?<li[^>]*>([\s\S]*?)<\/li>/i.exec(p);
      const def = /<\/table>\s*<\/td>\s*<td>\s*([^<]*?)\s*<\/td>/i.exec(p);
      const datas = /(\d{2}\/\d{2}\/\d{4})\s*(?:<br\s*\/?>)\s*<font[^>]*>\s*(\d{2}\/\d{2}\/\d{4})/i.exec(p);
      const prazo = /(\d+)\s+dias?\s+(corridos|[úu]teis)/i.exec(texto(p));
      r.linhas.push({
        seq: seq ? seq[1] : "",
        processo,
        final: finalDoNumero(processo),
        url: absoluto(link[1]),
        classe: classeM ? entidades(classeM[1]).trim() : "",
        assunto: classeM ? texto(classeM[2]).replace(/^\(|\)$/g, "") : "",
        executado: exec ? texto(exec[1]) : "",
        defensor: def ? texto(def[1]) : "",
        dataEnvio: datas ? datas[1] : "",
        ultimoDia: datas ? datas[2] : "",
        prazo: prazo ? prazo[0].replace(/\s+/g, " ") : "",
      });
    }
    return r;
  }

  // ---------------------------------------------------------------- página do processo
  // pendências do quadro "Pendências": [{juntar:"MANIFESTAÇÃO", movimento:"JUNTADA DE CERTIDÃO", data:"13/10/2026", hora:"17:31", texto}]
  function lerPendencias(html) {
    const q = /<fieldset[^>]*id="quadroPendencias"[\s\S]*?<\/fieldset>/i.exec(String(html || ""));
    if (!q) return [];
    const t = texto(q[0]);
    const r = [];
    const re = /Juntar\s+(.+?)\s+referente ao movimento\s*-\s*(.+?)\s*\(\s*(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})(?:\s+[àa]s\s+(\d{1,2}):(\d{2}))?\s*\)/gi;
    for (const m of t.matchAll(re)) {
      const mes = MESES[normal(m[4])];
      r.push({
        juntar: m[1].trim(), movimento: m[2].trim(),
        data: mes ? dataBr(m[3], mes, m[5]) : "", hora: m[6] ? m[6].padStart(2, "0") + ":" + m[7] : "",
        texto: m[0],
      });
    }
    if (!r.length && /\S/.test(t.replace(/Pend[êe]ncias/i, ""))) r.push({ juntar: "", movimento: "", data: "", hora: "", texto: t.replace(/^Pend[êe]ncias\s*/i, "") });
    return r;
  }

  // movimentações: [{seq, data, hora, nome, complemento, papel, autor, cargo, semArquivo, ajax, arquivos}] (ordem da página: mais recente primeiro)
  function lerMovimentos(html) {
    html = String(html || "");
    const r = [];
    const inicios = [];
    const re = /<tr\s+class="([a-zA-Z]*)"\s+id="(mov1Grau[^"]*)"[^>]*>/g;
    let m;
    while ((m = re.exec(html))) inicios.push({ i: m.index, fim: re.lastIndex, classe: m[1], id: m[2] });
    inicios.forEach((x, k) => {
      const seg = html.slice(x.fim, k + 1 < inicios.length ? inicios[k + 1].i : Math.min(html.length, x.fim + 60000));
      const flags = x.id.replace(/\s+/g, "").split(",");
      const seq = /id do movimento:\s*\d+"[^>]*>\s*(\d+)\s*</i.exec(seg);
      if (!seq) return;
      const dh = /<td[^>]*>\s*(\d{2}\/\d{2}\/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)\s*<\/td>/i.exec(seg);
      const nomeM = /<b>([\s\S]*?)<\/b>([\s\S]*?)<\/td>/i.exec(seg);
      const ajax = /["'](\/seeu\/processo\/movimentacaoArquivoDocumento\.do\?_tj=[0-9a-f]+)["']/i.exec(seg);
      // autor: última célula da linha ("Nome <br> <b>Cargo</b>")
      const linha = seg.split(/<tr\s+id="rowmovimentacoes/i)[0];
      const autorM = /<td>\s*(?:<img[^>]*>\s*)?([^<]*?)\s*<br\s*\/?>\s*(?:<img[^>]*>\s*)?(?:<font[^>]*>\s*)?<b>([^<]*)<\/b>(?:\s*<\/font>)?\s*<\/td>\s*$/i.exec(linha.trim().replace(/<\/tr>\s*$/i, "").trim());
      r.push({
        seq: Number(seq[1]),
        data: dh ? dh[1] : "",
        hora: dh ? dh[2] : "",
        nome: nomeM ? texto(nomeM[1]) : "",
        complemento: nomeM ? texto(nomeM[2]) : "",
        papel: flags[1] || "",
        autor: autorM ? texto(autorM[1]) : "",
        cargo: autorM ? texto(autorM[2]) : "",
        semArquivo: flags.includes("SEMARQUIVO"),
        ajax: ajax ? absoluto(ajax[1]) : "",
        arquivos: lerArquivos(seg),
      });
    });
    return r;
  }

  function lerProcesso(html) {
    html = String(html || "");
    const campo = /processoNumeroFormatado["']?[^>]*?value=["'](\d{20})["']/i.exec(html) || /value=["'](\d{20})["'][^>]*processoNumeroFormatado/i.exec(html);
    const titulo = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(html);
    const cab = /Execu[çc][ãa]o\s+(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})/.exec(texto(html.slice(0, 400000)));
    return {
      processo: cnj(campo ? campo[1] : "") || (cab ? cab[1] : "") || cnj(titulo ? titulo[1] : ""),
      pendencias: lerPendencias(html),
      movimentos: lerMovimentos(html),
      temAbaMovimentos: /tabMovimentacoesProcesso/.test(html),
      login: paginaDeLogin(html),
    };
  }

  // sessão expirada: a tela de senha do SEEU
  function paginaDeLogin(html) {
    return /type\s*=\s*["']?password/i.test(String(html || ""));
  }

  // ---------------------------------------------------------------- arquivos de um movimento
  // [{ordem:"160.1", descricao:"Despacho", tipo:"Outros Documentos", assinatura:"...", nome:"online.pdf", url}]
  function lerArquivos(html) {
    html = String(html || "");
    const r = [];
    const re = /<a\b[^>]*href="([^"]*arquivo\.do\?_tj=[0-9a-f]+)"[^>]*>([\s\S]*?)<\/a>/gi;
    let ant = 0, m;
    while ((m = re.exec(html))) {
      const antes = texto(html.slice(ant, m.index));
      ant = re.lastIndex;
      const ordem = [...antes.matchAll(/(\d+\.\d+)/g)].pop();
      const desc = /Descri[çc][ãa]o:\s*(.+?)(?=\s+\d+\.\d+\s+Tipo de Documento:|\s+Tipo de Documento:|\s+Ass\.:|$)/i.exec(antes);
      const tipo = /Tipo de Documento:\s*(.+?)(?=\s+Ass\.:|$)/i.exec(antes);
      const ass = /Ass\.:\s*(.+?)(?=\s+Vers[ãa]o assinada|\s+Verso original|$)/i.exec(antes);
      r.push({
        ordem: ordem ? ordem[1] : "",
        descricao: desc ? desc[1].trim() : "",
        tipo: tipo ? tipo[1].trim() : "",
        assinatura: ass ? ass[1].trim() : "",
        nome: texto(m[2]),
        url: absoluto(m[1]),
      });
    }
    return r;
  }
  // arquivo principal do movimento (o ".1"; senão o primeiro PDF; senão o primeiro)
  function arquivoPrincipal(arquivos) {
    if (!arquivos || !arquivos.length) return null;
    return arquivos.find((a) => /\.1$/.test(a.ordem)) || arquivos.find((a) => /\.pdf$/i.test(a.nome)) || arquivos[0];
  }

  // ---------------------------------------------------------------- escolha dos movimentos
  // movimento que não ajuda a entender o caso (fica fora do "desde a decisão")
  const RUIDO = /^(CONFIRMADA A INTIMA|RECEBIDOS OS AUTOS|REMETIDOS OS AUTOS|DISPONIBILIZADO NO DJ|PUBLICADO|DECORRIDO PRAZO|LEITURA DE|EXPEDIDA? INTIMA|EXPEDI[ÇC][ÃA]O DE INTIMA)/i;
  const NAO_DECISAO = /^(REMETIDOS|EXPEDI|CONFIRMADA|RECEBIDOS|DISPONIBILIZADO|JUNTADA|CONCLUSOS|DISTRIBU|REDISTRIBU|PUBLICADO|DECORRIDO|ATO ORDINAT)/i;
  // ato do juiz com documento: decisão, despacho, sentença (papel JUIZ na linha do SEEU)
  function ehAtoDoJuiz(m) {
    if (!m || !m.ajax || NAO_DECISAO.test(m.nome)) return false;
    if (m.papel) return m.papel === "JUIZ";
    return /DECIS|SENTEN|DESPACHO/i.test(m.nome);
  }
  function ehMeroExpediente(m) {
    return /MERO EXPEDIENTE/i.test((m && m.nome) || "");
  }

  // pendência que corresponde à aba da Mesa (Ciência -> "Juntar CIÊNCIA"; Manifestação -> "Juntar MANIFESTAÇÃO")
  function pendenciaDaAba(pendencias, aba) {
    if (!pendencias || !pendencias.length) return null;
    const alvo = normal(aba || "").split("/")[0];
    return (alvo && pendencias.find((p) => normal(p.juntar).startsWith(alvo.slice(0, 6)))) || pendencias[0];
  }
  // o movimento citado na pendência: mesmo nome, mesma data e mesma hora:minuto; senão o mais recente com o nome
  function movimentoDaPendencia(pend, movimentos) {
    if (!pend || !pend.movimento) return null;
    const nome = normal(pend.movimento);
    const mesmos = movimentos.filter((m) => normal(m.nome) === nome);
    return mesmos.find((m) => m.data === pend.data && (!pend.hora || m.hora.slice(0, 5) === pend.hora)) ||
      mesmos.find((m) => m.data === pend.data) || mesmos.sort((a, b) => b.seq - a.seq)[0] || null;
  }
  // {pendencia, motivo, decisao, merito, desde:[movimentos depois da decisão, sem ruído, do mais antigo ao mais recente]}
  function escolher(proc, aba) {
    const movs = (proc.movimentos || []).slice().sort((a, b) => b.seq - a.seq);
    const pendencia = pendenciaDaAba(proc.pendencias, aba);
    const motivo = movimentoDaPendencia(pendencia, movs);
    const atos = movs.filter(ehAtoDoJuiz);
    const decisao = atos[0] || null;
    const merito = decisao && ehMeroExpediente(decisao) ? atos.find((m) => !ehMeroExpediente(m)) || null : null;
    const corte = decisao ? decisao.seq : 0;
    const desde = movs.filter((m) => m.seq > corte && !RUIDO.test(m.nome)).sort((a, b) => a.seq - b.seq);
    return { pendencia, motivo, decisao, merito, desde };
  }

  // tipo do motivo, para filtrar e agrupar
  function tipoDoMotivo(nome) {
    const n = normal(nome);
    if (!n) return "Outro";
    if (/certid/.test(n)) return "Certidão";
    if (/despacho|decis|senten/.test(n)) return "Decisão/despacho";
    if (/audiencia/.test(n)) return "Audiência";
    if (/calculo|atestado|liquida/.test(n)) return "Cálculo/atestado";
    if (/manifesta|parecer/.test(n)) return "Manifestação";
    if (/mandado/.test(n)) return "Mandado";
    if (/laudo|exame|pericia/.test(n)) return "Laudo/exame";
    if (/oficio|informa|peticao|documento|guia|comunica/.test(n)) return "Documento/ofício";
    return "Outro";
  }

  // ---------------------------------------------------------------- texto do PDF
  // itens do pdf.js ({str, transform:[a,b,c,d,x,y], width, height}) -> texto com as linhas na ordem da página
  // (o pdf.js entrega trechos em negrito fora de ordem; aqui se agrupa por linha e se ordena da esquerda para a direita)
  function itensParaTexto(itens) {
    const hor = [], ver = [];
    for (const it of itens || []) {
      if (!it || typeof it.str !== "string" || !it.transform) continue;
      if (!it.str.trim() && !(it.width > 0)) continue;
      (Math.abs(it.transform[1]) > 0.01 || Math.abs(it.transform[2]) > 0.01 ? ver : hor).push(it);
    }
    const linhas = [];
    for (const it of hor) {
      const y = it.transform[5], alt = Math.abs(it.transform[3]) || it.height || 10;
      let l = linhas.find((x) => Math.abs(x.y - y) <= Math.max(2, alt * 0.35));
      if (!l) { l = { y, alt, itens: [] }; linhas.push(l); }
      l.itens.push(it);
    }
    linhas.sort((a, b) => b.y - a.y);
    const saida = linhas.map((l) => {
      l.itens.sort((a, b) => a.transform[4] - b.transform[4]);
      let s = "", fim = null;
      for (const it of l.itens) {
        const x = it.transform[4];
        if (fim !== null) {
          const gap = x - fim;
          if (gap > l.alt * 0.12 && !/\s$/.test(s) && !/^\s/.test(it.str)) s += " ";
        }
        s += it.str;
        fim = x + (it.width || 0);
      }
      return s.replace(/\s+/g, " ").trim();
    }).filter(Boolean);
    const lateral = ver.map((it) => it.str).join("").replace(/\s+/g, " ").trim();
    return saida.join("\n") + (lateral ? "\n" + lateral : "");
  }

  const CABECALHO = /^(poder judici[áa]rio|tjms\b|tribunal de justi[çc]a|comarca de|\d+[ªa]? vara|vara de|autos n[ºo°]?\.?|processo n[ºo°]?\.?:|classe processual:|assunto principal:|autoridade\(s\):|executado\(s\):|exequente|executado:|reeducando:|sentenciado:)/i;
  const RODAPE = /^(documento assinado digitalmente|valida[çc][ãa]o em|seeu - processo:|\[\d+\.\d+\]|assinado digitalmente|\(assinado por certifica)/i;
  const FECHO = /^([A-ZÀ-Ú][\wÀ-ú]+(?:\s+[\wÀ-ú]+){0,4}),?\s+\d{1,2}(?:º)?\s+de\s+[a-zç]+\s+de\s+\d{4}\.?$/i;
  const ASSINA = /^(ju[ií]za?|ju[ií]z\(a\))\s+(de direito|substitut|federal)|^magistrad/i;

  // dados do carimbo do SEEU: "[160.1] PROFERIDO DESPACHO DE MERO EXPEDIENTE - Despacho em 02/10/2026"
  function carimbo(t) {
    const m = /\[(\d+\.\d+)\]\s*(.+?)\s+-\s+(.+?)\s+em\s+(\d{2}\/\d{2}\/\d{4})/.exec(String(t || ""));
    return m ? { ordem: m[1], movimento: m[2].trim(), descricao: m[3].trim(), data: m[4] } : null;
  }

  // corpo do documento: sem cabeçalho, rodapé de assinatura e linhas de validação
  function corpoDoDocumento(t) {
    const linhas = String(t || "").split(/\n/).map((x) => x.trim()).filter(Boolean);
    const corpo = [];
    let fim = false;
    for (const l of linhas) {
      if (RODAPE.test(l)) continue;
      if (fim) continue;
      if (FECHO.test(l) || ASSINA.test(l)) { fim = true; continue; }
      if (!corpo.length && CABECALHO.test(l)) continue;
      if (corpo.length < 3 && CABECALHO.test(l)) continue;
      corpo.push(l);
    }
    let s = corpo.join("\n");
    const vistos = /(^|\n)\s*(vistos(?: etc)?\.?,?|vistos e examinados[^\n]*)\s*(\n|$)/i.exec(s);
    if (vistos) s = s.slice(vistos.index + vistos[0].length);
    // junta as linhas quebradas no meio da frase
    return s.replace(/([^.:;!?)\]])\n(?=[a-zà-ú(])/g, "$1 ").replace(/[ \t]+/g, " ").trim();
  }

  // parte decisória (do último "Ante o exposto"/"Diante do exposto"... até o fim); senão o corpo inteiro
  function dispositivo(corpo) {
    const s = String(corpo || "");
    const re = /(ante o exposto|diante do exposto|isso posto|isto posto|posto isso|pelo exposto|em face do exposto|diante disso|assim sendo|do exposto|ante o acima exposto|por todo o exposto|por tais raz[õo]es|nesses termos|dessa forma)/gi;
    let ult = -1, m;
    while ((m = re.exec(s))) ult = m.index;
    return (ult >= 0 && ult > s.length * 0.25 ? s.slice(ult) : s).trim();
  }

  function resumir(s, max) {
    s = String(s || "").replace(/\s+/g, " ").trim();
    max = max || 420;
    if (s.length <= max) return s;
    const corte = s.slice(0, max);
    const p = Math.max(corte.lastIndexOf(". "), corte.lastIndexOf("; "));
    return (p > max * 0.55 ? corte.slice(0, p + 1) : corte.replace(/\s+\S*$/, "")) + " […]";
  }

  const NUM_EXT = { um: 1, uma: 1, dois: 2, duas: 2, tres: 3, quatro: 4, cinco: 5, seis: 6, sete: 7, oito: 8, nove: 9, dez: 10, quinze: 15, vinte: 20, trinta: 30, sessenta: 60, noventa: 90 };
  // alertas e temas de um texto (decisão, despacho ou certidão)
  function analisarTexto(t) {
    const n = normal(t);
    const alertas = [];
    const add = (nivel, txt) => { if (!alertas.some((a) => a.txt === txt)) alertas.push({ nivel, txt }); };
    // risco ao assistido
    const riscos = [
      [/internacao (cautelar|provisoria)|decretacao da internacao|internacao do sentenciado/, "internação"],
      [/regressao (cautelar|de regime|ao regime)|regredir|regrida|regressao/, "regressão"],
      [/mandado de prisao|expeca-se mandado de prisao|recolhimento ao carcere|decreto a prisao|prisao (cautelar|preventiva)/, "prisão"],
      [/sustacao cautelar|suspensao cautelar|suspendo (cautelarmente|o beneficio|o livramento)|suspensao (do livramento|do beneficio|da medida|do regime)/, "suspensão"],
      [/revog(o|acao|ar|ada|ado) (o |a |do |da )?(livramento|beneficio|prisao domiciliar|monitoramento|saida|trabalho externo|suspensao|regime|substituicao)/, "revogação"],
      [/conversao (da pena|das penas) restritiva|converto a pena restritiva|reconversao/, "conversão da PRD"],
      [/falta grave|falta disciplinar de natureza grave/, "falta grave"],
      [/perda (dos dias|de ate 1\/3|da remicao|de 1\/3)|declaro a perda/, "perda de dias remidos"],
    ];
    const achados = riscos.filter(([re]) => re.test(n)).map(([, r]) => r);
    if (achados.length) add("alto", "Risco: " + achados.join(", "));
    if (/justificativa|justificar|justifique|audiencia de justificacao|audiencia de justificativa/.test(n)) add("alto", "Justificativa da defesa");
    // audiência com data
    const aud = /audiencia[^.]{0,120}?(?:dia|data de|para o dia|para|em)\s+(\d{1,2}\/\d{1,2}\/\d{2,4})(?:[^.\d]{0,20}(\d{1,2})[:h](\d{2}))?/.exec(n);
    if (aud) add("alto", "Audiência " + aud[1] + (aud[2] ? " às " + aud[2].padStart(2, "0") + ":" + aud[3] : ""));
    else if (/designo audiencia|audiencia (designada|admonitoria|de justificacao|de justificativa|admonitoria)|designada audiencia/.test(n)) add("medio", "Audiência designada");
    // sentido da decisão
    if (/\bindefiro\b|\bindeferido\b|\bindeferida\b|\bnego\b|nao conheco|rejeito|julgo improcedente|deixo de (conceder|acolher|homologar)|nao (concedo|acolho|reconheco)|mantenho a decisao|homologo a falta|reconheco a (pratica da )?falta/.test(n)) add("alto", "Indeferimento ou decisão contrária – conferir agravo em execução");
    if (/\bdefiro\b|\bdeferido\b|\bconcedo\b|julgo procedente|declaro extinta|julgo extinta|extingo a pena|declaro (cumprida|extinta)|homologo (o calculo|a remicao|os dias)|acolho o pedido/.test(n)) add("info", "Deferimento ou concessão");
    if (/manifeste-se|manifestar-se|manifestacao da defesa|vista a defesa|vistas a defesa|intime-se a defesa|intime-se a defensoria|diga a defesa|ouca-se a defesa|ouvida a defesa/.test(n)) add("medio", "Pede manifestação da defesa");
    if (/calculo|atestado de pena|liquidacao de pena|retificacao do calculo/.test(n)) add("medio", "Cálculo/atestado de pena");
    const prz = /(?:no prazo de|em ate|prazo de|dentro de)\s+(\d{1,3}|[a-z]+)\s*(?:\([a-z ]+\)\s*)?dias?(\s+uteis)?/.exec(n);
    const prazoNum = prz ? (/^\d+$/.test(prz[1]) ? Number(prz[1]) : NUM_EXT[prz[1]] || 0) : 0;
    if (prazoNum) add("medio", "Prazo no texto: " + prazoNum + " dia" + (prazoNum > 1 ? "s" : "") + (prz[2] ? " úteis" : ""));
    if (/com urgencia|urgente|com a maxima urgencia/.test(n)) add("alto", "Urgente");
    const temas = [];
    const T = [
      [/progressao/, "progressão"], [/livramento condicional|\blivramento\b/, "livramento"], [/indulto/, "indulto"], [/comutacao/, "comutação"],
      [/remicao/, "remição"], [/prescricao/, "prescrição"], [/saida temporaria|saidas temporarias/, "saída temporária"], [/trabalho externo/, "trabalho externo"],
      [/monitoramento eletronico|tornozeleira|monitoracao eletronica/, "monitoramento"], [/prisao domiciliar/, "prisão domiciliar"],
      [/prestacao de servicos|prestacao pecuniaria|pena restritiva|\bprd\b/, "PRD"], [/\bmulta\b/, "multa"], [/unificacao|soma das penas/, "unificação"],
      [/detracao/, "detração"], [/medida de seguranca/, "medida de segurança"], [/transferencia|recambiamento/, "transferência"],
      [/extincao da punibilidade|extincao da pena|declaro extinta|julgo extinta/, "extinção"], [/falta grave|procedimento disciplinar|\bpad\b/, "falta disciplinar"],
      [/exame criminologico/, "exame criminológico"], [/regime aberto|regime semiaberto|regime fechado/, "regime"],
    ];
    for (const [re, nome] of T) if (re.test(n) && !temas.includes(nome)) temas.push(nome);
    return { alertas, temas, prazo: prazoNum };
  }

  // um documento lido: {carimbo, corpo, resumo, dispositivo, alertas, temas, semTexto}
  function lerDocumento(t) {
    const bruto = String(t || "");
    if (bruto.replace(/\s/g, "").length < 40) return { carimbo: null, corpo: "", resumo: "", dispositivo: "", alertas: [], temas: [], prazo: 0, semTexto: true };
    const corpo = corpoDoDocumento(bruto);
    const cert = /certifico[\s\S]*/i.exec(corpo);
    const disp = dispositivo(cert ? cert[0] : corpo);
    const an = analisarTexto(corpo);
    return { carimbo: carimbo(bruto), corpo, resumo: resumir(disp, 480), dispositivo: disp, alertas: an.alertas, temas: an.temas, prazo: an.prazo, semTexto: false };
  }

  // ---------------------------------------------------------------- providência sugerida
  // a partir da aba (Ciência/Manifestação), do motivo e da última decisão já lidos: {texto, tipo, urgente}
  function providencia(a, aba) {
    if (!a) return null;
    const usavel = (d) => d && !d.erro && !d.semTexto && !d.semArquivo;
    const md = a.motivo && a.motivo.doc, dd = a.decisao && a.decisao.doc;
    const docMot = a.mesma ? dd : md;
    const nMot = normal(usavel(docMot) ? docMot.corpo : "");
    const alMot = (usavel(docMot) ? docMot.alertas : []) || [];
    const tem = (lista, re) => lista.find((x) => re.test(x.txt));
    const risco = tem(alMot, /^Risco:/);
    const riscoTxt = risco ? " – sob pena de " + risco.txt.replace(/^Risco:\s*/, "") : "";
    const prazoTxt = usavel(docMot) && docMot.prazo ? ` (prazo no texto: ${docMot.prazo} dia${docMot.prazo > 1 ? "s" : ""})` : "";
    const ciencia = /^ci[eê]ncia/i.test((a.pendencia && a.pendencia.juntar) || "") || (!(a.pendencia && a.pendencia.juntar) && /ci[eê]ncia/i.test(aba || ""));
    const decisaoNoMotivo = a.mesma || /despacho|decis|senten/i.test((a.motivo && a.motivo.nome) || "");
    const indeferiu = decisaoNoMotivo ? tem(alMot, /^Indeferimento/) : null;
    const dataDec = a.decisao ? a.decisao.data : "";
    const r = (texto, tipo, urgente) => ({ texto, tipo, urgente: !!urgente });
    if (ciencia) {
      if (indeferiu) return r(`Avaliar agravo em execução contra a decisão de ${dataDec}; depois dar ciência`, "Agravo", true);
      if (risco) return r("Dar ciência e avisar o assistido" + riscoTxt, "Ciência", true);
      return r("Dar ciência", "Ciência", false);
    }
    const aud = tem(alMot, /^Audiência \d/);
    // a Defensoria, em regra, não justifica sem ouvir o assistido: pede a intimação pessoal dele
    if (tem(alMot, /^Justificativa/)) return r("Requerer a intimação pessoal do sentenciado para justificar" + riscoTxt + prazoTxt, "Intimação pessoal", true);
    if (aud) return r(`Preparar a ${aud.txt.toLowerCase()} (contato com o assistido)`, "Audiência", true);
    if (indeferiu) return r(`Avaliar agravo em execução contra a decisão de ${dataDec}`, "Agravo", true);
    if (tem(alMot, /^Audiência designada/)) return r("Preparar a audiência designada (contato com o assistido)", "Audiência", true);
    if (tem(alMot, /^Cálculo/)) return r("Conferir o cálculo/atestado de pena e manifestar concordância ou impugnação" + prazoTxt, "Cálculo", !!risco);
    const tipo = tipoDoMotivo(a.pendencia ? a.pendencia.movimento : (a.motivo && a.motivo.nome) || "");
    if (tipo === "Certidão") {
      if (/nao compareceu|deixou de comparecer|nao comparecimento|ausencia (de|do) comparecimento|descumpri|nao (assinou|recolheu|cumpriu|apresentou)|inadimpl|violac/.test(nMot)) return r("Requerer a intimação pessoal do sentenciado sobre o descumprimento noticiado na certidão" + prazoTxt, "Intimação pessoal", true);
      if (/nao (foi )?localizad|nao encontrad|endereco (incorreto|inexistente|desatualizado)|mudou-se|paradeiro/.test(nMot)) return r("Informar o endereço atualizado do assistido", "Certidão", true);
      if (/fuga|evadi|evasao|foragido/.test(nMot)) return r("Manifestar sobre a fuga/evasão noticiada na certidão", "Certidão", true);
      if (/condenatoria|nova condenacao|transitad|outra execucao|outro processo|guia de recolhimento|sem gr|unifica/.test(nMot)) return r("Manifestar sobre a nova condenação/guia noticiada na certidão (unificação, regime)", "Certidão", false);
      if (/prisao|preso|recolhido|flagrante/.test(nMot)) return r("Manifestar sobre a prisão noticiada na certidão", "Certidão", true);
      return r("Manifestar sobre a certidão" + prazoTxt, "Certidão", !!risco);
    }
    if (tipo === "Manifestação" && /minist/i.test((a.motivo && a.motivo.cargo) || "")) return r("Manifestar sobre o parecer do MP" + prazoTxt, "Parecer do MP", !!risco);
    if (tipo === "Laudo/exame") return r("Manifestar sobre o laudo/exame" + prazoTxt, "Laudo", !!risco);
    if (tipo === "Documento/ofício") return r("Manifestar sobre o documento juntado" + riscoTxt + prazoTxt, "Documento", !!risco);
    if (decisaoNoMotivo && tem(alMot, /^Deferimento/)) return r("Ciência da decisão favorável; conferir o cumprimento", "Ciência", false);
    if (tem(alMot, /^Pede manifestação/) || !nMot) return r("Manifestar" + (a.motivo ? " sobre o " + a.motivo.nome.toLowerCase() : "") + riscoTxt + prazoTxt, "Manifestação", !!risco);
    return r("Ler o documento e manifestar" + riscoTxt + prazoTxt, "Manifestação", !!risco);
  }

  // ---------------------------------------------------------------- prioridade da linha
  // 0 = mais urgente. Alerta alto > último dia mais próximo > alerta médio
  function urgencia(linha, analise, hoje) {
    const h = hoje ? dataNum(hoje) : 0;
    const alto = analise && (analise.providencia ? analise.providencia.urgente : (analise.alertas || []).some((a) => a.nivel === "alto"));
    const medio = analise && (analise.alertas || []).some((a) => a.nivel === "medio");
    const ud = dataNum(linha.ultimoDia);
    return (alto ? 0 : 1) * 1e9 + (ud || 99999999) - (medio ? 0.5 : 0) + (h && ud && ud < h ? -5e8 : 0);
  }

  // ---------------------------------------------------------------- planilha (xlsx, sem biblioteca)
  let TAB_CRC = null;
  function crc32(bytes) {
    if (!TAB_CRC) {
      TAB_CRC = new Uint32Array(256);
      for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; TAB_CRC[i] = c >>> 0; }
    }
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = TAB_CRC[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  // zip sem compressão: [{nome, dados:Uint8Array}] -> Uint8Array
  function zip(arquivos) {
    const enc = new TextEncoder();
    const partes = [], central = [];
    let pos = 0;
    const u16 = (v) => [v & 0xff, (v >>> 8) & 0xff];
    const u32 = (v) => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
    for (const a of arquivos) {
      const nome = enc.encode(a.nome), dados = a.dados, crc = crc32(dados);
      const loc = Uint8Array.from([].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(dados.length), u32(dados.length), u16(nome.length), u16(0)));
      partes.push(loc, nome, dados);
      central.push(Uint8Array.from([].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(dados.length), u32(dados.length),
        u16(nome.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(pos))), nome);
      pos += loc.length + nome.length + dados.length;
    }
    const tamCentral = central.reduce((s, x) => s + x.length, 0);
    const fim = Uint8Array.from([].concat(u32(0x06054b50), u16(0), u16(0), u16(arquivos.length), u16(arquivos.length), u32(tamCentral), u32(pos), u16(0)));
    const tudo = partes.concat(central, [fim]);
    const r = new Uint8Array(tudo.reduce((s, x) => s + x.length, 0));
    let o = 0;
    for (const x of tudo) { r.set(x, o); o += x.length; }
    return r;
  }
  function xmlEsc(s) {
    return String(s == null ? "" : s).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g, "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").slice(0, 32000);
  }
  function colunaLetra(i) {
    let s = "";
    i++;
    while (i > 0) { const r = (i - 1) % 26; s = String.fromCharCode(65 + r) + s; i = Math.floor((i - 1) / 26); }
    return s;
  }
  // linhas: [[cabeçalho...], [valores...], ...]; larguras: [nº de caracteres por coluna]
  function xlsx(linhas, larguras, nomeAba) {
    const enc = new TextEncoder();
    const ult = colunaLetra(Math.max(0, (linhas[0] || []).length - 1)) + Math.max(1, linhas.length);
    const cols = (larguras || []).map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join("");
    const rows = linhas.map((l, r) => `<row r="${r + 1}">` + l.map((v, c) => {
      const ref = colunaLetra(c) + (r + 1);
      const est = r === 0 ? 1 : 2;
      if (typeof v === "number" && isFinite(v)) return `<c r="${ref}" s="${est}"><v>${v}</v></c>`;
      return `<c r="${ref}" s="${est}" t="inlineStr"><is><t xml:space="preserve">${xmlEsc(v)}</t></is></c>`;
    }).join("") + "</row>").join("");
    const sheet = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">` +
      `<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>` +
      (cols ? `<cols>${cols}</cols>` : "") + `<sheetData>${rows}</sheetData><autoFilter ref="A1:${ult}"/></worksheet>`;
    const nome = xmlEsc(String(nomeAba || "Triagem").replace(/[\\/?*[\]:]/g, " ").slice(0, 31));
    const f = (n, s) => ({ nome: n, dados: enc.encode(s) });
    return zip([
      f("[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>`),
      f("_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`),
      f("xl/workbook.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${nome}" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'${nome.replace(/'/g, "''")}'!$A$1:$${ult.replace(/(\D+)(\d+)/, "$1$$$2")}</definedName></definedNames></workbook>`),
      f("xl/_rels/workbook.xml.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`),
      f("xl/styles.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1D5A3B"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`),
      f("xl/worksheets/sheet1.xml", sheet),
    ]);
  }

  const api = {
    ABAS, SITUACOES, entidades, texto, normal, cnj, finalDoNumero, absoluto, dataNum, faixasFinal, faixaTexto,
    lerMesa, lerPendencias, lerMovimentos, lerProcesso, paginaDeLogin, lerArquivos, arquivoPrincipal,
    ehAtoDoJuiz, ehMeroExpediente, pendenciaDaAba, movimentoDaPendencia, escolher, tipoDoMotivo,
    itensParaTexto, carimbo, corpoDoDocumento, dispositivo, resumir, analisarTexto, lerDocumento, providencia, urgencia,
    crc32, zip, xlsx, colunaLetra,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.TRIAGEM = api;
})(typeof self !== "undefined" ? self : this);
