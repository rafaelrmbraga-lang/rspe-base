#!/bin/bash
# Prepara a sessão do Claude Code na nuvem: instala as dependências para rodar testes e lint.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# pywebview (janela) e pyinstaller (.exe) só servem no Windows; ficam de fora no Linux da nuvem.
grep -v -i -E '^\s*(#|$|pywebview|pyinstaller)' requirements.txt > /tmp/rspe-requirements.txt
python3 -m pip install --quiet --disable-pip-version-check -r /tmp/rspe-requirements.txt pyflakes

echo 'export PYTHONPATH="$CLAUDE_PROJECT_DIR"' >> "$CLAUDE_ENV_FILE"
