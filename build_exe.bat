@echo off
REM ============================================================
REM  Gera o APTO.exe - Windows 10/11 (usa o WebView2 do sistema).
REM  Requisito: Python 3.9+ instalado com "Add python to PATH".
REM  Rode com duplo clique. O .exe sai em dist\APTO.exe
REM  Petições (.docx) desativadas: bibliotecas do Word fora do .exe.
REM  Para reativar, veja requirements.txt e MODELOS_ATIVOS em ui.html.
REM ============================================================
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
REM testes de regressão: se algum falhar, o .exe não é gerado
python testes.py
if errorlevel 1 (
    echo.
    echo TESTES FALHARAM - o .exe nao foi gerado.
    pause
    exit /b 1
)
python -m PyInstaller --onefile --windowed --clean --name APTO ^
    --icon rspe.ico --add-data "rspe.ico;." --add-data "apto_selo.png;." --add-data "logo_defensoria.png;." --add-data "fontes;fontes" --add-data "ui.html;." --add-data "atendimentos;atendimentos" --add-data "base_juridica.json;." --add-data "teses_auto.bin;." --add-data "monitor_juris.bin;." ^
    --collect-data pdfminer --collect-data pdfplumber --collect-data reportlab --hidden-import reportlab.graphics.shapes --hidden-import rspe_relatorio --hidden-import rspe_remicao --hidden-import rspe_legislacao --hidden-import rspe_monitor --hidden-import rspe_gabinete --hidden-import rspe_gabinete_api --hidden-import rspe_sei --hidden-import rspe_seeu --hidden-import rspe_nuspen --hidden-import nuspen_regras.leitura --hidden-import nuspen_regras.segmentacao ^
    --collect-all webview --collect-all pypdfium2 --collect-all pypdfium2_raw ^
    --exclude-module docxtpl --exclude-module docx --exclude-module docx2pdf ^
    rspe_app.py
echo.
REM OCR embutido (opcional no build local): com o Tesseract instalado neste computador, copia para dist\tesseract e baixa só o português
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" (
    xcopy /E /I /Y /Q "%ProgramFiles%\Tesseract-OCR" dist\tesseract >nul
    del /Q dist\tesseract\tessdata\*.traineddata
    powershell -NoProfile -Command "Invoke-WebRequest 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/por.traineddata' -OutFile 'dist\tesseract\tessdata\por.traineddata'"
    echo OCR: dist\tesseract (deixe a pasta ao lado do APTO.exe)
)
echo Pronto: dist\APTO.exe
pause
