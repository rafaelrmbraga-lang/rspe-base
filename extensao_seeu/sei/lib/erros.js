// Erros da extensao. Cada um tem um codigo estavel (usado na interface e nos logs; nunca com conteudo).
export class ErroNuspen extends Error {
  constructor(mensagem, codigo) {
    super(mensagem);
    this.codigo = codigo;
  }
}
export class SessaoAusente extends ErroNuspen {
  constructor(m = "sem sessão ativa no SEI") { super(m, "sessao_ausente"); }
}
export class SessaoExpirada extends ErroNuspen {
  constructor(m = "a sessão no SEI expirou durante a leitura") { super(m, "sessao_expirada"); }
}
export class Interrompido extends ErroNuspen {
  constructor(m = "interrompido") { super(m, "interrompido"); }
}
export class Cancelado extends ErroNuspen {
  constructor(m = "leitura cancelada pelo usuário") { super(m, "cancelado"); }
}
export class EscritaProibida extends ErroNuspen {
  constructor(m = "endereço fora da lista de leitura") { super(m, "fora_da_lista"); }
}
export class EstruturaInesperada extends ErroNuspen {
  constructor(m = "a página do SEI não tem a estrutura esperada") { super(m, "estrutura_inesperada"); }
}
export class RespostaInesperada extends ErroNuspen {
  constructor(m = "respostas inesperadas do SEI") { super(m, "resposta_inesperada"); }
}
export class AdaptadorDesligado extends ErroNuspen {
  constructor(m = "o adaptador do SEI real está desligado") { super(m, "adaptador_desligado"); }
}
export class AppIndisponivel extends ErroNuspen {
  constructor(m = "APTO indisponível") { super(m, "app_indisponivel"); }
}
export class NaoPareado extends ErroNuspen {
  constructor(m = "código de pareamento ausente ou inválido") { super(m, "nao_pareado"); }
}
