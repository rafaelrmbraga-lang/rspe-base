// APTO Atendimentos - mensagens de WhatsApp (pedido de documentos, padrão e baixa). Só monta o texto;
// quem envia é você (copiar, ou abrir a conversa no WhatsApp com o texto pronto e clicar em enviar).
(function () {
  "use strict";
  const A = self.ATD;

  const ASSINATURA = "Atenciosamente,\nDefensoria Pública do Estado de Mato Grosso do Sul\n3ª Defensoria Pública de Execução Penal – Campo Grande/MS";
  const CANAL = "Ressaltamos que este canal é exclusivo para o envio de documentos. Em caso de dúvidas e/ou necessidade de orientações, solicitamos que agende um atendimento presencial em nossa unidade (Rua Barão de Melgaço, n. 128 em Campo Grande/MS) ou por meio da plataforma: https://plataforma.defensoria.ms.def.br/login";
  const TEXTOS = {
    docsIni: "{saudacao}\nAqui é da 3ª Defensoria Pública de Execução Penal de Campo Grande/MS.",
    docsFim: CANAL + "\n\n" + ASSINATURA,
    padrao: "Olá!\nAqui é da 3ª Defensoria Pública de Execução Penal de Campo Grande/MS.\n\nInformamos que este canal é exclusivo para o envio de documentos.\n\n" +
      "Em caso de dúvidas e/ou necessidade de orientações, o atendimento não é realizado por aqui. Solicitamos que venha até a nossa unidade para agendar atendimento, " +
      "localizada na Rua Barão de Melgaço, n. 128 em Campo Grande/MS, ou agende por meio da plataforma: https://plataforma.defensoria.ms.def.br/login\n" + ASSINATURA,
    baixa: "{saudacao}\nAqui é da 3ª Defensoria Pública de Execução Penal de Campo Grande/MS.\n\nTendo em vista que a documentação solicitada não foi enviada no prazo, " +
      "informamos que o atendimento será baixado. Caso ainda tenha interesse no pedido, será necessário agendar novo atendimento.\n\n" + CANAL + "\n\n" + ASSINATURA,
  };
  // documentos: o texto da lista e as palavras do atendimento que o marcam sozinho
  const DOCS = [
    { id: "emp", texto: "Declaração do empregador constando a jornada de trabalho, com os dias da semana e os horários de entrada e saída, em papel timbrado ou com carimbo e assinatura do responsável",
      gatilho: "declaração de emprego|declaração de trabalho|horário de trabalho|jornada|empregador|flexibiliza" },
    { id: "res", texto: "Comprovante de residência atualizado (dos últimos três meses), em nome próprio ou acompanhado de declaração do titular, se estiver em nome de terceiro",
      gatilho: "residência|endereço|transferência" },
    { id: "hol", texto: "Holerite (contracheque) e comprovantes dos demais gastos mensais", gatilho: "holerite|gastos|parcel" },
    { id: "just", texto: "Declaração com as razões do não comparecimento, assinada pelo assistido", gatilho: "razões|não comparec|não ter comparecido|ausência" },
    { id: "cert", texto: "Certificado de conclusão do curso", gatilho: "certificado|curso" },
    { id: "clin", texto: "Termo de acolhimento da clínica terapêutica", gatilho: "acolhimento|clínica" },
    { id: "med", texto: "Atestado ou laudo médico", gatilho: "médic|cirurgia|laudo" },
  ];

  function saudacao(d) {
    const h = (d || new Date()).getHours();
    return h < 12 ? "Bom dia!" : h < 18 ? "Boa tarde!" : "Boa noite!";
  }
  const aplicar = (t) => String(t || "").replace(/\{saudacao\}/g, saudacao());
  const ddmm = (iso) => (iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : "");

  // textos e documentos guardados (config) ou os originais
  const textos = (cfg) => Object.assign({}, TEXTOS, (cfg && cfg.msgs) || {});
  const docs = (cfg) => (cfg && cfg.docs) || DOCS.map((d) => Object.assign({}, d));

  // documentos que o texto do atendimento sugere
  function sugerirDocs(texto, lista) {
    const t = A.norm(texto);
    return lista.filter((d) => d.gatilho && d.gatilho.split("|").map((g) => A.norm(g)).filter(Boolean).some((g) => t.includes(g))).map((d) => d.id);
  }

  // msg: {tipo: "docs"|"padrao"|"baixa", docs:[ids], outros:[textos], comPrazo, prazo}
  function montar(msg, cfg) {
    const T = textos(cfg);
    if (msg.tipo === "padrao") return aplicar(T.padrao);
    if (msg.tipo === "baixa") return aplicar(T.baixa);
    const lista = docs(cfg);
    const itens = (msg.docs || []).map((id) => (lista.find((d) => d.id === id) || {}).texto).filter(Boolean).concat(msg.outros || []);
    const prazo = msg.comPrazo && msg.prazo ? ` até ${ddmm(msg.prazo)}` : "";
    const corpo = itens.length
      ? `Solicitamos que nos envie${prazo}:\n\n` + itens.map((x, i) => `${i + 1}. ${x.replace(/[.;]\s*$/, "")}${i === itens.length - 1 ? "." : ";"}`).join("\n")
      : `Solicitamos que nos envie${prazo} a documentação necessária.`;
    return aplicar(T.docsIni) + "\n\n" + corpo + "\n\n" + aplicar(T.docsFim);
  }

  // 1º telefone do contato no formato do WhatsApp (55 + DDD + número); sem DDD, assume 67
  const RE_FONE = /\(?(\d{2})\)?\s*(9?\d{4})[-\s.]?(\d{4})/;
  function foneWhats(contato) {
    const m = RE_FONE.exec(String(contato || ""));
    if (m) return "55" + m[1] + m[2] + m[3];
    const d = String(contato || "").replace(/\D/g, "");
    if (d.length === 8 || d.length === 9) return "5567" + d;
    return "";
  }
  const linkWhats = (fone, texto) => `https://wa.me/${fone}?text=${encodeURIComponent(texto)}`;

  self.MSG = { TEXTOS, DOCS, textos, docs, sugerirDocs, montar, foneWhats, linkWhats, saudacao };
})();
