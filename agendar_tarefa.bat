@echo off
REM ─────────────────────────────────────────────────────────────────
REM  agendar_tarefa.bat
REM  Execute este arquivo UMA VEZ como Administrador para agendar
REM  o bot todo dia às 12:00.
REM
REM  Como executar:
REM  1. Clique com botão direito no arquivo
REM  2. "Executar como administrador"
REM ─────────────────────────────────────────────────────────────────

SET TASK_NAME=LinkedInBot
SET HORA=12:00
SET PASTA=%~dp0
SET PYTHON=python

REM Remove tarefa antiga se existir
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Cria a tarefa agendada
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%PASTA%linkedin_bot.py\"" ^
  /sc DAILY ^
  /st %HORA% ^
  /ru "%USERNAME%" ^
  /f

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo  Tarefa agendada com sucesso!
    echo  Nome: %TASK_NAME%
    echo  Horario: todo dia as %HORA%
    echo  Pasta: %PASTA%
    echo.
    echo  Para ver: Agendador de Tarefas ^> Biblioteca
    echo  Para remover: schtasks /delete /tn "%TASK_NAME%" /f
) ELSE (
    echo.
    echo  ERRO ao agendar. Tente executar como Administrador.
)

pause
