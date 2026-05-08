@echo off
chcp 65001 > nul
echo.
echo ========================================
echo    LINKEDIN BOT - EXECUÇÃO AUTOMÁTICA
echo ========================================
echo.

REM Verifica Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python não encontrado!
    echo Instale Python 3.x e adicione ao PATH.
    pause
    exit /b 1
)

REM Executa o bot automático
echo [*] Iniciando bot totalmente automático...
echo [*] Nenhuma confirmação será solicitada.
echo.

python bot_auto.py

echo.
echo [*] Execução concluída.
echo [*] Pressione qualquer tecla para fechar...
pause > nul