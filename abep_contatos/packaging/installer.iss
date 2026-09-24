; ============================================================================
; Script do INSTALADOR do Painel de Contatos, para o programa Inno Setup.
; ----------------------------------------------------------------------------
; Inno Setup e um programa gratuito que le este arquivo de texto e gera um
; unico "Setup.exe" -- o instalador de verdade, do jeito que qualquer
; programa de computador costuma ser distribuido (com tela de boas-vindas,
; escolha de pasta, atalhos, e um "Desinstalar" que aparece no Painel de
; Controle do Windows).
;
; PRE-REQUISITO (so pra QUEM VAI GERAR o instalador, nao pra quem vai usar o
; programa depois): instalar o Inno Setup em https://jrsoftware.org/isinfo.php
; (e gratuito). Depois disso, para gerar o instalador:
;
;   1. Rode o PyInstaller primeiro, pra criar a pasta dist/PainelDeContatos/
;      com o programa ja empacotado (veja packaging/PainelDeContatos.spec):
;         pyinstaller packaging/PainelDeContatos.spec
;   2. Compile este script com o Inno Setup:
;         ISCC packaging/installer.iss
;      (ou abra este arquivo com o programa "Inno Setup Compiler" e clique
;      em "Compile")
;   3. O instalador final aparece em
;      packaging/saida/PainelDeContatosSetup-X.Y.Z.exe (com o numero da
;      versao no nome) -- esse E o arquivo que se distribui pros usuarios
;      finais. Ele ja leva tudo que o programa precisa (nao exige Python
;      instalado no computador de quem for usar).
;
; NOTA IMPORTANTE sobre o aviso do Windows: como este instalador nao tem uma
; "assinatura digital" (um certificado pago, comprado de uma empresa
; especializada), o Windows SmartScreen pode mostrar um aviso de "Editor
; desconhecido" na primeira execucao -- isso e normal para programas
; internos/pequenos e nao indica nenhum problema no instalador em si. Se
; quiser eliminar esse aviso, e preciso comprar um certificado de assinatura
; de codigo e assinar o .exe final -- isso fica fora do escopo deste script.
; ============================================================================

#define MyAppName "Painel de Contatos"
; Precisa ser atualizado junto com VERSAO em versao.py e com a tag da
; Release publicada no GitHub (ex.: v0.12.0) -- e essa tag que o aviso de
; atualizacao dentro do programa usa pra saber se ha uma versao mais nova.
#define MyAppVersion "0.11.3"
#define MyAppPublisher "ABEP-TIC"
#define MyAppExeName "PainelDeContatos.exe"
#define MyAppAssocExt ".abepdb"
#define MyAppAssocKey "PainelDeContatosArquivo"

[Setup]
; Este numero (AppId) identifica o programa de forma unica para o Windows --
; NUNCA mude ele depois que o programa ja estiver instalado em algum
; computador, senao uma atualizacao futura seria tratada como um programa
; diferente em vez de uma atualizacao do mesmo programa.
AppId={{415D359C-6E3B-4268-AD6A-8C8B29FB513A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Icone do proprio Setup.exe (o instalador) -- o mesmo usado no programa.
SetupIconFile=..\resources\icone.ico
; A pasta onde o instalador final (o Setup.exe) e salvo depois de compilado.
; O numero da versao entra no NOME do arquivo (ex.: PainelDeContatosSetup-
; 0.11.0.exe) pra nao sobrescrever o instalador de uma versao anterior e pra
; ficar claro, so de olhar o nome do arquivo, qual versao ele instala.
OutputDir=saida
OutputBaseFilename=PainelDeContatosSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
; So funciona em Windows 64 bits, que e o que o Python/PySide6 usados pra
; gerar o programa tambem sao.
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
; Uma caixinha opcional na tela do instalador, pra criar (ou nao) um atalho
; na Area de Trabalho, alem do atalho que sempre vai pro Menu Iniciar.
Name: "desktopicon"; Description: "Criar um atalho na Area de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
; Copia TODA a pasta que o PyInstaller gerou (dist/PainelDeContatos/) pra
; dentro da pasta de instalacao escolhida pelo usuario -- isso inclui o
; .exe, o Python empacotado, o PySide6, o openpyxl, tudo que o programa
; precisa pra rodar sozinho, sem depender de mais nada no computador.
Source: "..\dist\PainelDeContatos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Associa a extensao .abepdb ao programa -- depois de instalado, dar um
; duplo clique num arquivo .abepdb (em qualquer pasta do computador, pen
; drive ou pasta de rede) abre ele direto no Painel de Contatos, do mesmo
; jeito que um duplo clique num .docx abre o Word.
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "Banco de dados do Painel de Contatos"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
; Depois de instalar, oferece abrir o programa na hora (caixinha marcada por
; padrao, mas a pessoa pode desmarcar antes de clicar em "Concluir").
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
