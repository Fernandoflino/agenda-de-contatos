@echo off
REM Arquivo para abrir o Painel de Contatos durante o desenvolvimento, sem
REM precisar digitar nenhum comando: basta dar dois cliques nele.
REM Ele usa o Python que ja foi instalado dentro da pasta ".venv" (ver
REM README.md), entao nao precisa ter Python instalado "de verdade" no
REM Windows para isso funcionar.
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
