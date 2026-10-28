// Gera instalar_robo_saj.html: a página com o botão para arrastar para a barra de favoritos.
// Uso: node gerar_instalador.js   (rodar de novo sempre que robo_saj.js mudar)
"use strict";
const fs = require("fs");
const path = require("path");

const fonte = fs.readFileSync(path.join(__dirname, "robo_saj.js"), "utf8");
// tira só as linhas que são comentário inteiro; as quebras de linha ficam (%0A), então nada se emenda
const codigo = fonte.split("\n").filter((l) => !/^\s*\/\//.test(l)).join("\n").trim();
const versao = (fonte.match(/const VERSAO = "([^"]+)"/) || [])[1] || "?";
const favorito = "javascript:" + encodeURIComponent(codigo);
const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

const html = `<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robô SAJ - instalar</title>
<style>
 body{font:15px/1.5 Segoe UI,Arial,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#1d2433;background:#fff}
 h1{font-size:22px;color:#03508D}
 a.fav{display:inline-block;background:#03508D;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600;cursor:grab}
 .box{background:#eef4fa;border-left:4px solid #03508D;padding:10px 14px;margin:16px 0}
 .alerta{background:#fdf3e1;border-left-color:#c77700}
 textarea{width:100%;height:90px;font:12px monospace}
 li{margin:4px 0}
</style></head><body>
<h1>Robô do SAJ Defensorias · versão ${versao}</h1>
<div class="box alerta"><b>Esta versão só confere.</b> Ela abre cada tarefa da fila "Para peticionar › Intimação", lê a peça e as Propriedades,
diz se peticionaria ou por que pularia, e fecha o editor. Não peticiona, não altera campo, não marca nem desmarca caixa e não salva nada.</div>
<h2>Instalar (uma vez)</h2>
<ol>
 <li>Mostre a barra de favoritos: <b>Ctrl+Shift+B</b>.</li>
 <li>Arraste este botão para a barra de favoritos: <a class="fav" href="${esc(favorito)}" title="Arraste para a barra de favoritos">Robô SAJ ${versao}</a></li>
 <li>Se o Chrome/Edge não deixar arrastar: clique com o botão direito na barra de favoritos › <b>Adicionar página</b>; Nome: <i>Robô SAJ</i>;
  em URL, cole o código abaixo (botão "Copiar código").</li>
</ol>
<textarea id="cod" readonly>${esc(favorito)}</textarea>
<p><button onclick="navigator.clipboard.writeText(document.getElementById('cod').value).then(()=>this.textContent='Copiado')">Copiar código</button></p>
<h2>Usar</h2>
<ol>
 <li>No SAJ (painel-saj.ms.def.br), abra o Painel de Tarefas › <b>Para peticionar › Intimação</b>. Não deixe nenhuma tarefa aberta.</li>
 <li>Clique no favorito <b>Robô SAJ</b>. Abre um painel azul no canto direito, que confirma se a fila está certa.</li>
 <li>Escolha quantas tarefas (até 15, que é uma página da fila) e clique em <b>Iniciar</b>. Deixe a aba à vista enquanto ele roda.</li>
 <li>No fim, clique em <b>Copiar relatório</b> e cole na conversa com o Claude.</li>
</ol>
<div class="box">Se aparecer uma pergunta do SAJ que o robô não conhece (ex.: ao fechar o editor), ele para e pede para você resolver.
Saia sempre <b>sem salvar e sem peticionar</b> e depois clique em <b>Continuar a rodada</b>. Copie o texto da pergunta para eu automatizar.</div>
<p style="color:#5b6472;font-size:13px">Atualizou a versão? Apague o favorito antigo e arraste o novo.</p>
</body></html>
`;
fs.writeFileSync(path.join(__dirname, "instalar_robo_saj.html"), html);
console.log(`instalar_robo_saj.html gerado (versão ${versao}, favorito com ${favorito.length} caracteres)`);
