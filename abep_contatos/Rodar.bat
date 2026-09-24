@echo off
REM Arquivo para abrir o Painel de Contatos durante o desenvolvimento, sem
REM precisar digitar nenhum comando: basta dar dois cliques nele.
REM Ele usa o Python que ja foi instalado dentro da pasta ".venv" (ver
REM README.md), entao nao precisa ter Python instalado "de verdade" no
REM Windows para isso funcionar.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primeira vez rodando aqui: preparando o ambiente...
    py -m venv .venv
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente. Verifique se o Python esta instalado.
        pause
        exit /b 1
    )
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo Falha ao instalar as dependencias.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
