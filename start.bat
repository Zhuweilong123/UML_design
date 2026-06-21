@chcp 65001 >nul 2>&1
@echo off

start "UML-Backend" cmd /k "taskkill /F /IM python.exe >nul 2>&1 & cd /d D:\AI_tools\uml_designer\backend & set PYTHONUTF8=1 & python -m app.main"
ping -n 3 127.0.0.1 >nul
start "UML-Frontend" cmd /k "cd /d D:\AI_tools\uml_designer\frontend & npx vite --port 3000"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
