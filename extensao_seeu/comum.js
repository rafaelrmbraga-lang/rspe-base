// Funções puras, usadas pelo service worker e pelos testes (node). Sem acesso ao Chrome aqui.
(function (raiz) {
  "use strict";

  const RE_CNJ = /\b(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})\b/;
  const RE_RSPE = /processoExecucaoPenal\.do/i;
  const ACAO_RSPE = "emitirRelatorioSituacaoProcessualExecutoria";

  // nº CNJ no formato do SEEU (NNNNNNN-DD.AAAA.J.TR.OOOO) ou ''
  function cnj(texto) {
    const m = RE_CNJ.exec(String(texto || ""));
    return m ? `${m[1]}-${m[2]}.${m[3]}.${m[4]}.${m[5]}.${m[6]}` : "";
  }

  // nome de pasta seguro no Windows: sem \ / : * ? " < > |, sem ponto ou espaço no fim, sem nomes reservados
  function pastaSegura(nome) {
    let s = String(nome || "").replace(/[\\/:*?"<>|\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim().replace(/^[. ]+|[. ]+$/g, "");
    if (/^(con|prn|aux|nul|com\d|lpt\d)$/i.test(s)) s = "_" + s;
    return s.slice(0, 80);
  }

  // data local AAAA-MM-DD
  function hojeISO(d) {
    d = d || new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  // caminho relativo a Downloads: <raiz>/<base>/<processo>_<data>.pdf (sem base: <raiz>/<processo>_<data>.pdf)
  function caminhoArquivo(cfg, processo, data) {
    const raizP = pastaSegura(cfg && cfg.raiz) || "APTO";
    const base = pastaSegura(cfg && cfg.base);
    const nome = (cnj(processo) || "RSPE_sem_numero") + "_" + (data || hojeISO()) + ".pdf";
    return base ? `${raizP}/${base}/${nome}` : `${raizP}/${nome}`;
  }

  // só aceita o endereço do RSPE ("Situação Carcerária") no próprio SEEU, por https:
  // /seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&...
  function urlRspeValida(url) {
    try {
      const u = new URL(url);
      return u.protocol === "https:" && u.hostname === "seeu.pje.jus.br" && RE_RSPE.test(u.pathname) &&
        u.searchParams.get("actionType") === ACAO_RSPE && /^\d+$/.test(u.searchParams.get("idProcessoExecucaoPenal") || "");
    } catch (e) {
      return false;
    }
  }

  // endereço do RSPE montado a partir do id interno do processo no SEEU (idProcessoExecucaoPenal)
  function urlRspeDoId(id, report) {
    return "https://seeu.pje.jus.br/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=" + ACAO_RSPE +
      "&report=" + encodeURIComponent(report || "relatorioSituacaoProcessualExecutoriaV2") + "&idProcessoExecucaoPenal=" + id;
  }

  // no HTML da página do processo (o link fica dentro do script gerarResa / gerarResaQuadroAcoes): {id, report} ou null
  function rspeNoHtml(html) {
    html = String(html || "");
    let m = /processoExecucaoPenal\.do\?actionType=emitirRelatorioSituacaoProcessualExecutoria([^'"\s<>]*)/.exec(html);
    if (!m) return null;
    const resto = m[1];
    const rep = /[?&]report=([\w.-]+)/.exec(resto);
    let id = /idProcessoExecucaoPenal=(\d+)/.exec(resto);
    if (!id) {
      // forma "... idProcessoExecucaoPenal=" + idProcessoExecucaoPenal: o id vem da variável do script
      id = /idProcessoExecucaoPenal\s*=\s*(\d{6,})/.exec(html);
    }
    return id ? { id: id[1], report: rep ? rep[1] : "" } : null;
  }

  // os primeiros bytes são de um PDF?
  function ehPdf(bytes) {
    return bytes && bytes.length > 4 && bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46;
  }

  // chave de "já baixado hoje" (um RSPE por processo, base e dia)
  function chaveDia(cfg, processo, data) {
    return `${cnj(processo)}|${pastaSegura(cfg && cfg.base)}|${data || hojeISO()}`;
  }

  const api = { RE_CNJ, RE_RSPE, ACAO_RSPE, cnj, pastaSegura, hojeISO, caminhoArquivo, urlRspeValida, urlRspeDoId, rspeNoHtml, ehPdf, chaveDia };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.APTO = api;
})(typeof self !== "undefined" ? self : this);
