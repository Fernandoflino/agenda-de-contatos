# Instruções para o Claude Code neste repositório

Este repositório contém o **Painel de Contatos** (ABEP-TIC), dentro da pasta
`abep_contatos/`. Documentação completa de desenvolvimento e build está em
[abep_contatos/README.md](abep_contatos/README.md).

## Hook automático: bump de versão + instalador a cada `git push`

Existe um hook `pre-push` instalado em `.git/hooks/pre-push` (não versionado
pelo Git, então não aparece num `git clone` novo -- se o repositório for
clonado de novo em outra máquina, reinstale-o) que roda sozinho a cada
`git push` feito localmente, sem precisar pedir pra mim:

1. **Aumenta a versão** (`VERSAO`/`VERSAO_DATA` em `abep_contatos/versao.py`
   e `MyAppVersion` em `abep_contatos/packaging/installer.iss`, incrementando
   o número de patch, ex.: `0.11.0` -> `0.11.1`) e commita isso sozinho como
   `Bump versao para X.Y.Z`.
2. Como o Git já decide o que vai mandar *antes* de rodar o hook, esse commit
   novo não entra no push que acabou de ser disparado -- o hook cancela esse
   primeiro push de propósito (mensagem `push CANCELADO de proposito`) e
   pede pra rodar `git push` de novo. Da segunda vez, ele reconhece que o
   commit no topo já é o de bump e pula direto pro passo 3.
3. **Gera o instalador** (PyInstaller + Inno Setup) com o número da versão
   já atualizado no nome do arquivo, e deixa o push seguir. Se o build
   falhar (ex.: `.venv` ou Inno Setup ausentes nesta máquina), só avisa e
   deixa o push continuar mesmo assim -- nunca bloqueia por causa disso.

Ou seja: **um `git push` normal, feito pelo usuário direto no terminal,
sempre precisa ser digitado duas vezes na prática** (a primeira é
cancelada pelo bump de versão). Se isso confundir o usuário, explique esse
comportamento -- não é um erro.

Se _eu_ (Claude) for quem está dando o push numa sessão, não preciso rodar
os passos manuais abaixo -- o hook já cuida disso sozinho quando eu rodar
`git push`. Os passos manuais servem pra gerar o instalador sem precisar
fazer push (ex.: só pra testar), ou caso o hook não exista/falhe:

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
uma ação pública que normalmente pediria confirmação antes de criar/publicar,
como qualquer outra ação que afeta um repositório remoto -- **mas o usuário
já autorizou isso como padrão**: sempre que eu (Claude) fizer um `git push`
nesse repositório, depois que o push for concluído eu devo criar a tag
`vX.Y.Z` correspondente à versão que acabou de subir, gerar o instalador (se
ainda não tiver sido gerado pelo hook) e publicar a Release no GitHub com
esse instalador como asset -- sem perguntar de novo a cada vez. As notas da
release devem resumir o que mudou desde a release anterior (ver releases
anteriores como referência de formato).
