// Adaptador do SEI REAL — DESLIGADO por padrao (ativo: false).
//
// NADA aqui e inventado: a estrutura das paginas do SEI da instituicao NAO e conhecida pelo
// projeto. Cada ponto marcado "calibrar" precisa ser preenchido a partir da ESTRUTURA
// SANITIZADA (modo "coleta de estrutura", lib/estrutura.js), revisada pelo usuario, e testado com
// fixtures SINTETICAS no mesmo contrato do adaptador ficticio (teste/contrato.test.mjs).
//
// Enquanto estiver desligado, TODA funcao lanca AdaptadorDesligado e permitido() devolve false:
// o leitor nao faz nenhuma requisicao ao SEI real.
import { AdaptadorDesligado } from "./erros.js";

const desligado = () => { throw new AdaptadorDesligado(); };

export const adaptadorSeiReal = {
  nome: "sei-real",
  versao: "0.0-nao-calibrado",
  temVersao: false, // calibrar: o SEI informa a versao/data de atualizacao do documento? Sem saber, usa hash
  ativo: false, // so muda para true depois de calibrado e testado, por decisao do usuario
  permitido: () => false, // calibrar: lista FIXA de caminhos e acoes de leitura (nunca escrita)
  urlLista: desligado, // calibrar: pagina de lista de processos e sua paginacao
  ehLogin: () => false, // calibrar: como reconhecer a pagina de login
  listarProcessos: desligado, // calibrar
  lerProcesso: desligado, // calibrar
  listarDocumentos: desligado, // calibrar (inclui anexos PDF e imagens, hoje nao tratados)
  lerDocumento: desligado, // calibrar
};
