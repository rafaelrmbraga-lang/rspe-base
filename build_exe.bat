@echo off
REM ============================================================
REM  Gera o RSPE_Base.exe - Windows 10/11 (usa o WebView2 do sistema).
REM  Requisito: Python 3.9+ instalado com "Add python to PATH".
REM  Rode com duplo clique. O .exe sai em dist\RSPE_Base.exe
REM  Petições (.docx) desativadas: bibliotecas do Word fora do .exe.
REM  Para reativar, veja requirements.txt e MODELOS_ATIVOS em ui.html.
REM ============================================================
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --clean --name RSPE_Base ^
    --icon rspe.ico --add-data "rspe.ico;." --add-data "ui.html;." --add-data "base_juridica.json;." ^
    --collect-data pdfminer --collect-data pdfplumber --collect-data reportlab ^
    --collect-all webview ^
    --exclude-module docxtpl --exclude-module docx --exclude-module docx2pdf ^
    rspe_app.py
echo.
echo Pronto: dist\RSPE_Base.exe
pause
