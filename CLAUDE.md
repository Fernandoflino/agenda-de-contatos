# Instruções para o Claude Code neste repositório

Este repositório contém o **Painel de Contatos** (ABEP-TIC), dentro da pasta
`abep_contatos/`. Documentação completa de desenvolvimento e build está em
[abep_contatos/README.md](abep_contatos/README.md).

## Gerar instalador antes de cada `git push`

Sempre que for feito um `git push` neste repositório, gere um instalador
novo antes (ou logo depois) do push, com o número da versão no nome do
arquivo -- não pule esse passo por conta própria, mas lembre o usuário dele
se ele pedir para dar push sem mencionar o instalador.

Passos (dentro de `abep_contatos/`):

```bat
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pyinstaller packaging\PainelDeContatos.spec
"<caminho do ISCC.exe>" packaging\installer.iss
```

O `ISCC.exe` (compilador do Inno Setup) pode estar em
`C:\Program Files (x86)\Inno Setup 6\ISCC.exe` ou, se instalado por usuário
(via winget), em `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` -- confira
qual dos dois existe antes de rodar.

O resultado aparece em
`abep_contatos\packaging\saida\PainelDeContatosSetup-X.Y.Z.exe` -- o `X.Y.Z`
vem de `MyAppVersion` em `abep_contatos/packaging/installer.iss`, que deve
estar sincronizado com `VERSAO` em `abep_contatos/versao.py` (ver comentário
no topo desse arquivo).

Publicar o instalador como asset de uma Release no GitHub (tag `vX.Y.Z`) é
uma ação pública -- confirme com o usuário antes de criar/publicar a Release,
como em qualquer outra ação que afeta um repositório remoto.
