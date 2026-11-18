# APTO com funções (7.19 a 7.21): como as peças se ligam

A barra fixa do topo (`ui.html`, `ui.FUNCOES`) troca de função sem fechar nada: **Atendimentos · Execução · SEEU · SEI · Quadro · Relatório**.
Execução é o APTO das bases, sem mudança. As outras funções usam a **base do gabinete** (`gabinete.sqlite`, ao lado da pasta `bases`, com uma
cópia por dia em `copias\gabinete`), porque não pertencem a uma comarca.

```
navegador (sessão da pessoa)                         APTO (este computador)
 SAP  ── atd_sap.js ─┐                               servidor 127.0.0.1:47321 (rspe_app._extensao_servidor)
 SEEU ── triagem.html ┼─ background.js ── POST/GET ─▶  /atd/...  /seeu/triagem  /api/sync/...  /sei/token
 SEI  ── sei/painel.html (leitor do NUSPEN) ────────▶  rspe_gabinete_api (mistura da Api) ─ rspe_gabinete / rspe_sei
                                                      tela: ui.html (+ moldura atendimentos/painel.html via ponte.js)
```

| Função | Lê (extensão, só leitura) | Guarda | Tela |
|---|---|---|---|
| Atendimentos | `atd_sap.js`: fila "Assistidos em Espera" e Fato Narrado | `rspe_gabinete` (atendimentos, pecas, ajustes, frases) | painel da antiga extensão APTO Atendimentos, numa moldura (`atendimentos/`) |
| SEEU | `triagem.js`: Mesa do Defensor (já existia) | `kv seeu_triagem` (última triagem) | `ui.seeuPintar` |
| SEI | `sei/` (leitor do NUSPEN, `lib/nucleo.js` + adaptadores) | `rspe_sei` (sessões, itens, processos, documentos, obrigações) | `ui.seiPintar` |
| Quadro | — | `pecas` (pendências; origem atendimento, sei, seeu) | moldura, aba Pendências |
| Relatório | — | contagens do mês + pedidos da Execução (opcional) | moldura, aba Controle |

**Regras do servidor local:** só 127.0.0.1; POST só com origem de extensão (`chrome-extension://`, `moz-extension://`) e JSON; o token do SEI
só é entregue a extensões e é renovado a cada abertura do APTO; pedidos da tela ao SAP (Chamar, Ver no SAP, Ler a fila) entram numa fila que a
extensão consulta a cada 2 s, só enquanto a aba da fila está aberta (`rspe_gabinete.Comandos`).

**Vindo do NUSPEN (rafhaels1/nuspen-sei), sem mudança de regra:** `nuspen_regras/` (obrigações, prazo expresso, rodapé, tipo documental, com os
testes originais em `nuspen_regras/testes`), `extensao_seeu/sei/lib` e `extensao_seeu/sei/teste` (leitor só leitura e contrato dos
adaptadores), `ferramentas/sei_ficticio` (SEI fictício do laboratório). Princípios mantidos: tudo é sugestão com fonte até a validação humana;
o prazo expresso não ganha vencimento (o termo inicial não é presumido); nada se apaga (versão anterior fica como substituída); o leitor do SEI
real continua **desligado** (`sei/lib/config.js`) até ser calibrado e testado.

**Testes:** `teste_atendimentos_apto.py`, `teste_atd_sap.py` (SAP fictício), `teste_ui_atendimentos.py`, `teste_nuspen_regras.py`,
`teste_sei_apto.py` (ponta a ponta com o SEI fictício), `teste_ui_sei_seeu.py`, `teste_ui_funcoes.py`. Os de tela precisam de node e Playwright
(sem eles, avisam e não falham).
