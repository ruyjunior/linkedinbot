@echo off
echo Fechando Chrome existente...
taskkill /F /IM chrome.exe > nul 2>&1
timeout /t 2 /nobreak > nul

echo Iniciando Chrome com porta de debugging aberta...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\Users\ruyju\AppData\Local\Google\Chrome\User Data" ^
  --profile-directory=Default ^
  https://www.linkedin.com

echo Chrome iniciado. Aguarde 5 segundos...
timeout /t 5 /nobreak > nul
echo Execute: python linkedin_bot.py