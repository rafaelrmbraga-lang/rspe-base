@echo off
REM Abre o Conversor de Audio sem gerar .exe (precisa de Python instalado com "Add python to PATH").
cd /d "%~dp0"
python -m pip install --quiet imageio-ffmpeg
start "" pythonw conversor.py
