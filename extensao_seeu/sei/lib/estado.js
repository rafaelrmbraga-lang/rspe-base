// (No APTO: textos com "APTO" no lugar de "NUSPEN"; a lógica é a do NUSPEN.)
// Logica PURA do painel (sem DOM nem chrome.*): estados de conexao, estimativa, progresso,
// mensagens humanas e resultado. Testavel no Node. Nada aqui inventa numero: sem base conhecida,
// a estimativa diz que e incerta.

export const MODOS_PAINEL = [
  { id: "todos", rotulo: "Todos os processos", ajuda: "Lê todos os processos que você pode ver e traz o que mudou desde a última vez." },
  { id: "novos", rotulo: "Só processos novos", ajuda: "Lê apenas processos que o APTO ainda não conhece." },
  { id: "documentos_novos", rotulo: "Só documentos novos", ajuda: "Nos processos já conhecidos, lê só os documentos novos ou alterados." },
  { id: "selecionados", rotulo: "Processos selecionados", ajuda: "Lê somente os processos cujos números você informar (um por linha)." },
  { id: "um", rotulo: "Um processo", ajuda: "Lê um único processo, o número que você informar." },
];

export function estadoConexao({ appOk, pareado, sessaoSei, destinoFicticio = false }) {
  let app;
  if (!appOk) app = { codigo: "indisponivel", rotulo: "APTO indisponível", tom: "erro", acao: "Abra o aplicativo APTO neste computador e tente de novo." };
  else if (!pareado) app = { codigo: "nao_pareado", rotulo: "APTO encontrado, mas não pareado", tom: "aviso", acao: "O APTO não entregou o código de pareamento: feche e abra o APTO e clique em Verificar de novo." };
  else app = { codigo: "conectado", rotulo: "APTO conectado", tom: "ok", acao: "" };
  let sessao;
  if (sessaoSei === null || sessaoSei === undefined) sessao = { codigo: "verificando", rotulo: "Verificando a sessão no SEI…", tom: "neutro", acao: "" };
  else if (sessaoSei) sessao = { codigo: "detectada", rotulo: "Sessão no SEI detectada", tom: "ok", acao: "" };
  else sessao = { codigo: "nao_detectada", rotulo: "Sessão no SEI não detectada", tom: "aviso", acao: "Entre no SEI com a sua conta, em outra aba, e volte aqui." };
  const pronto = app.codigo === "conectado" && sessao.codigo === "detectada";
  const proxima = [app, sessao].find((x) => x.acao)?.acao ?? "";
  return { app, sessao, pronto, acaoSeguinte: proxima, destinoFicticio: Boolean(destinoFicticio) };
}

export function formatarTempo(segundos) {
  if (segundos === null || segundos === undefined || !Number.isFinite(segundos)) return "—";
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return r ? `${m} min ${r} s` : `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

export function estimativa({ modo, processosConhecidos = 0, tetoProcessos = null, selecionados = 0, pausaMs = 300, limitePorMinuto = 30 }) {
  const porReq = Math.max(pausaMs, 60000 / Math.max(1, limitePorMinuto)) / 1000;
  const paginasLista = Math.max(1, Math.ceil(processosConhecidos / 20));
  let processosMax = null;
  let incerta = false;
  let requisicoes;
  if (modo === "documentos_novos") {
    processosMax = processosConhecidos;
    requisicoes = paginasLista + processosMax * 2;
  } else if (modo === "selecionados" || modo === "um") {
    processosMax = modo === "um" ? 1 : selecionados;
    requisicoes = paginasLista + processosMax * 3;
    incerta = processosConhecidos === 0;
  } else {
    // todos / novos: o total real so e conhecido durante a leitura
    if (processosConhecidos > 0 && modo === "todos") { processosMax = processosConhecidos; requisicoes = paginasLista + processosMax * 2; incerta = true; }
    else { processosMax = tetoProcessos; requisicoes = null; incerta = true; }
  }
  if (tetoProcessos !== null && processosMax !== null) {
    processosMax = Math.min(processosMax, tetoProcessos);
    requisicoes = paginasLista + processosMax * (modo === "selecionados" || modo === "um" ? 3 : 2);
  } else if (tetoProcessos !== null && processosMax === null) {
    processosMax = tetoProcessos;
    requisicoes = paginasLista + tetoProcessos * 3;
  }
  const segundos = requisicoes === null ? null : requisicoes * porReq;
  let texto;
  if (requisicoes === null) texto = "Não dá para saber o total antes de começar: é a primeira leitura. A leitura é progressiva (ritmo controlado, pausável e retomável) e segue até concluir todos os processos que você pode ver.";
  else {
    texto = `Até ${processosMax} processo${processosMax === 1 ? "" : "s"}, cerca de ${requisicoes} requisições, em torno de ${formatarTempo(segundos)}.`;
    if (incerta) texto += " É uma estimativa: processos com muitos documentos novos levam mais.";
  }
  return { processosMax, requisicoes, segundos, incerta, texto };
}

export function fasePainel(snap) {
  if (!snap || !snap.fase) return "ocioso";
  if (snap.erro) return "erro";
  if (snap.pausado) return "pausado";
  if (snap.fase === "lendo" || snap.fase === "iniciando") return "lendo";
  if (snap.fase === "parada") return "parada";
  if (snap.fase === "concluida") return (snap.falhas || 0) + (snap.indisponiveis || 0) > 0 ? "concluida_com_falhas" : "concluida";
  return "ocioso";
}

export function percentual(snap, totalConhecido) {
  if (!totalConhecido) return null;
  const feitos = (snap.processos || 0) + (snap.processosPulados || 0);
  return Math.min(100, Math.round((100 * feitos) / totalConhecido));
}

export function tempoRestante(snap, totalConhecido) {
  const feitos = (snap.processos || 0) + (snap.processosPulados || 0);
  if (!totalConhecido || feitos < 2 || !snap.decorridoMs) return null;
  const porProc = snap.decorridoMs / 1000 / feitos;
  return Math.max(0, (totalConhecido - feitos) * porProc);
}

const MENSAGENS = {
  sessao_ausente: ["Você não está logado no SEI", "Entre no SEI com a sua conta e inicie a leitura de novo."],
  sessao_expirada: ["A sessão do SEI expirou durante a leitura", "Entre no SEI de novo e use Retomar: o que já foi lido está guardado."],
  app_indisponivel: ["O APTO não respondeu", "Abra o APTO e use Retomar. Nada foi perdido."],
  nao_pareado: ["O código de pareamento não vale mais", "Feche e abra o APTO de novo (o código é renovado sozinho) e clique em Verificar de novo."],
  estrutura_inesperada: ["O SEI mudou e a extensão não entendeu a página", "A leitura parou para não gravar dados incompletos. Avise quem mantém a extensão; o que já foi lido está correto."],
  resposta_inesperada: ["O SEI respondeu de um jeito inesperado", "A leitura parou por segurança (ritmo, erros repetidos ou resposta estranha). Espere alguns minutos e use Retomar."],
  fora_da_lista: ["Um endereço fora da lista de leitura foi barrado", "Nada foi lido nem alterado. Avise quem mantém a extensão."],
  adaptador_desligado: ["O leitor do SEI real está desligado", "Ele só é ligado depois de calibrado e testado. Use o ambiente de laboratório."],
  cancelado: ["Leitura cancelada", "O que já foi lido ficou guardado no APTO."],
  teto: ["Teto opcional de processos atingido", "Você definiu um teto para esta rodada. Zere o teto (0 = sem teto) e inicie de novo para continuar."],
  interrompido: ["Leitura interrompida", "Use Retomar para continuar de onde parou."],
};

export function mensagemErro(codigo) {
  const [titulo, oQueFazer] = MENSAGENS[codigo] || ["Algo inesperado aconteceu", "Tente de novo. Se repetir, avise quem mantém a extensão (informe só o código do erro)."];
  return { codigo: codigo || "desconhecido", titulo, oQueFazer };
}

export function textoResultado(snap) {
  const partes = [
    `${snap.processos || 0} processo(s) lido(s)`,
    `${snap.documentosLidos || 0} documento(s) lido(s)`,
    `${snap.novos || 0} novo(s)`,
    `${snap.modificados || 0} modificado(s)`,
    `${snap.documentosPulados || 0} já conhecido(s)`,
  ];
  const problemas = [];
  if (snap.falhas) problemas.push(`${snap.falhas} com falha`);
  if (snap.indisponiveis) problemas.push(`${snap.indisponiveis} inacessível(is)`);
  return { resumo: partes.join(" · "), problemas: problemas.join(" · "), retomavel: snap.parada && snap.parada !== "teto" };
}
