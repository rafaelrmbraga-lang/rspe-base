// Configuracao da extensao. A CHAVE do adaptador real fica DESLIGADA aqui, no codigo: ligar exige
// editar este arquivo depois de calibrar e testar o adaptador (decisao do usuario), nunca um
// botao da tela. Nada aqui e segredo.
export const ADAPTADOR_REAL_LIGADO = false;

export const VERSAO_EXTENSAO = "0.2.0 (no APTO 1.9.0)";

// Padroes: ritmo conservador e SEM limite artificial de processos (decisao do usuario, 08/11/2026)
export const PADROES = {
  baseApp: "http://127.0.0.1:47321", // o APTO aberto neste computador (função SEI)
  baseSei: "",
  tetoProcessos: 0, // 0 = SEM teto (o produto le todos os processos acessiveis, de forma progressiva); teto e opcional
  limitePorMinuto: 30, // 1 requisicao a cada 2 s
  pausaMs: 600,
  maxFalhasSeguidas: 3,
};

export const LIMITES = { limitePorMinutoMax: 120 };
