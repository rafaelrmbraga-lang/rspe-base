# RSPE Base

Lê em lote os Relatórios da Situação Processual Executória (RSPE) do SEEU e organiza, por assistido,
progressão, livramento, indulto/comutação, prescrição, extinção, ficha disciplinar e auditoria.

## Baixar o programa

Aba **Releases** (à direita) → última versão → `RSPE_Base_vX.Y.Z.zip`. Extraia e rode `RSPE_Base.exe`
(Windows 10/11, não precisa de Python).

## Como o .exe é gerado

A cada envio para a branch `main`, o GitHub Actions compila o `.exe` num Windows na nuvem
(`.github/workflows/build.yml`) e publica em Releases. Para gerar de novo sem mudar nada:
aba **Actions** → "Gerar RSPE_Base.exe" → **Run workflow**. A versão vem de `VERSAO` em `rspe_app.py`.

Compilação local (opcional): `build_exe.bat` num PC com Python.

## Dados

Nenhum RSPE, ficha ou base de assistidos é versionado (ver `.gitignore`).
