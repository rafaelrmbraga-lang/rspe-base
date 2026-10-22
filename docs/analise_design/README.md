# Análise de design do APTO (7.14.4)

Este é um diagnóstico e uma proposta. **Nenhum arquivo do sistema foi alterado**: tudo o que está aqui é documentação, capturas, protótipos estáticos e scripts de análise. Todas as capturas usam dados fictícios ("Simulado Caso NNN").

| arquivo | conteúdo |
|---|---|
| [01_resumo_executivo.md](01_resumo_executivo.md) | as 10 mudanças de maior impacto, para quem não é designer |
| [02_achados.md](02_achados.md) | conferência dos indícios + 70 achados (app, PDF, Excel, extensão, conversor, identidade e petições) |
| [03_sistema_de_design.md](03_sistema_de_design.md) | tokens de cor (claro e escuro), situação com forma, tipografia, espaço, raio, sombra e inventário de componentes |
| [antes_depois/index.html](antes_depois/index.html) | antes e depois de 5 telas, lado a lado (abre offline no navegador) |
| [04_tarefas_reais.md](04_tarefas_reais.md) | as 9 tarefas: cliques, dúvidas, onde o olho se perde, e o desempenho com 720 assistidos |
| [05_roteiro.md](05_roteiro.md) | fases (ganhos rápidos, médias, estruturais), com arquivos e risco |
| [06_perguntas.md](06_perguntas.md) | decisões que dependem de você e da equipe |
| [anexos/](anexos/) | relatórios detalhados de PDF/Excel e de extensão/conversor/identidade/petições |
| [capturas/](capturas/) | 117 capturas: `app_*`, `pdf_*`, `excel_*`, `extensao_*`, `conversor_*`, `identidade_*`, `peticao_*`, `depois_*` |
| [ferramentas/](ferramentas/) | scripts para reproduzir tudo (`monta_pdf.py` gera o PDF único) |
| [APTO_analise_de_design.pdf](APTO_analise_de_design.pdf) | tudo isto num PDF só, para circular |

## Como a tela foi executada

Usei o `ui.html` real no Chromium (Playwright), com o `window.__mockApi` ligado à **classe `Api` real do `rspe_app.py`**, no mesmo processo. Detalhes da montagem:

- o módulo `webview` é substituído por um falso, e os diálogos de arquivo devolvem caminhos fixos;
- a data é fixada em 12/10/2026, a mesma de `casos_simulados/roda_casos.py`;
- a rede fica bloqueada, como no uso offline. Sem esse bloqueio, a aba Dados prisionais trava tentando baixar o Geopresídios.

**Por que não rodar o app real sob Xvfb:** o pywebview no Linux precisaria de GTK/WebKit, que não é o motor do Windows (o WebView2 é Chromium). O Chromium com a `Api` real reproduz o motor do Windows e todos os dados reais da tela, e ainda permite medir o tempo de desenho e simular a escala de 125 % e 150 % (`device_scale_factor`).

Bases fictícias:
- **144 assistidos**, os casos de `casos_simulados/casos.json`;
- **720 assistidos**, os mesmos casos replicados 5 vezes, com outro nº de execução, outro nome, outro CPF e outra mãe.

Reproduzir (com Python, Playwright e Chromium):

```
cd docs/analise_design/ferramentas
python monta_base.py /caminho/Comarca_Ficticia.sqlite 1
python monta_base.py /caminho/Base_Grande_Ficticia.sqlite 5
python roteiro.py abas  /caminho/Comarca_Ficticia.sqlite     # também: ficha, modais, estados, tamanhos, vazia
python roteiro.py grande /caminho/Base_Grande_Ficticia.sqlite
python cor.py                                                # contrastes e daltonismo (Machado 2009)
```

A variável `APTO_TRABALHO` indica a pasta de trabalho dos scripts de PDF, Excel e extensão. Os `.sqlite` gerados ficam fora do repositório, como manda o `.gitignore`.

## Limites desta análise

- As medidas de tempo são de um Chromium em servidor. Num computador de repartição, conte 2 a 4 vezes mais.
- O Conversor rodou com tema Linux e a ffmpeg simulada; a disposição dos elementos vale, o acabamento no Windows difere.
- Os `confirm()` e `prompt()` nativos não aparecem nas capturas: foram avaliados pelo código.
- O SEEU real não foi acessado. O aviso da extensão foi capturado sobre uma página fictícia que imita o SEEU.
- Nos protótipos de "depois", os textos de situação e jurídicos são os do programa. No protótipo da ficha, o 3º passo do "por quê" é ilustrativo.
