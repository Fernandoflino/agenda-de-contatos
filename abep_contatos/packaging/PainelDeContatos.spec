# -*- mode: python ; coding: utf-8 -*-
#
# Este e o "roteiro" que o PyInstaller segue pra transformar o programa
# Python (main.py e as pastas db/, ui/, config/) num programa .exe que roda
# em qualquer computador Windows -- MESMO SEM Python instalado nele. E como
# "empacotar" o interpretador Python + todas as bibliotecas usadas (PySide6,
# openpyxl) junto com o codigo do programa, numa pasta so.
#
# Como usar: dentro da pasta abep_contatos, com o ambiente virtual (.venv)
# ativado e o pyinstaller instalado, rode:
#   pyinstaller packaging/PainelDeContatos.spec
# O resultado fica em dist/PainelDeContatos/ -- essa pasta inteira e o que
# o instalador do Inno Setup (packaging/installer.iss) empacota depois.

import os

# SPECPATH e uma variavel que o proprio PyInstaller preenche com a pasta
# onde este arquivo .spec esta (packaging/) -- usamos ela pra montar
# caminhos que funcionam nao importa de qual pasta a pessoa rodar o comando.
RAIZ_DO_PROJETO = os.path.join(SPECPATH, "..")

a = Analysis(
    [os.path.join(RAIZ_DO_PROJETO, "main.py")],
    pathex=[RAIZ_DO_PROJETO],
    binaries=[],
    # "datas" sao arquivos que nao sao codigo Python mas que o programa
    # precisa ler em tempo de execucao -- aqui, a folha de estilo visual
    # (ver ui/theme.py). O par (origem, pasta_de_destino_dentro_do_.exe)
    # garante que ui/theme.py continua achando o arquivo em "resources/...".
    datas=[
        (os.path.join(RAIZ_DO_PROJETO, "resources", "style.qss"), "resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PainelDeContatos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=False esconde a janela preta de "terminal" -- o programa e
    # feito pra abrir so a interface grafica, como qualquer app do Windows.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icone proprio do .exe e dos atalhos criados pelo instalador (fonte
    # vetorial em resources/icone.svg -- ver comentario la).
    icon=os.path.join(RAIZ_DO_PROJETO, "resources", "icone.ico"),
)

# COLLECT junta o .exe com TODAS as bibliotecas que ele precisa (Python em
# si, PySide6, openpyxl etc.) numa unica pasta -- essa pasta e o que
# realmente vai ser instalado no computador do usuario final. Usamos o modo
# "pasta" (--onedir) em vez de "arquivo unico" (--onefile) porque abre mais
# rapido e da menos falso-positivo em antivirus.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PainelDeContatos",
)
