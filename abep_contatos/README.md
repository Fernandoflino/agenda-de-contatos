# Painel de Contatos (ABEP-TIC)

Aplicativo de computador (Windows), escrito em Python, para gerenciar os
contatos (presidentes, diretores etc.) das empresas associadas — substitui o
sistema antigo baseado em Google Sheets + Google Apps Script.

Os dados ficam guardados num único arquivo `.abepdb` (por baixo, um banco de
dados SQLite comum) que você escolhe onde salvar — pode ficar em qualquer
pasta do computador, num pendrive ou numa pasta de rede compartilhada,
igual ao MMEX (Money Manager Ex). Copiar esse arquivo para outro computador
com o programa instalado é suficiente para continuar usando os mesmos dados.

## Rodar durante o desenvolvimento (sem instalar nada no Windows)

Pré-requisito: Python 3.12 instalado.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python main.py
```

## Rodar os testes automatizados

```bat
.venv\Scripts\python -m pytest tests -v
```

Isso testa a camada de banco de dados (criação de tabelas/campos dinâmicos,
CRUD, importação da planilha real, exportação) e também constrói cada tela
da interface (sem precisar clicar em nada) para pegar erros cedo.

## Gerar o instalador para distribuir (sem exigir Python no PC de quem for usar)

Duas ferramentas são usadas em conjunto:

1. **PyInstaller** — empacota o Python + todas as bibliotecas (PySide6,
   openpyxl) junto com o código do programa, numa pasta só.
2. **Inno Setup** (gratuito, <https://jrsoftware.org/isinfo.php>) — pega essa
   pasta e gera um `Setup.exe` de verdade, com tela de instalação, atalhos no
   Menu Iniciar/Área de Trabalho e um desinstalador que aparece no Painel de
   Controle do Windows.

Passo a passo:

```bat
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pyinstaller packaging\PainelDeContatos.spec
```

Isso cria a pasta `dist\PainelDeContatos\` com o programa já empacotado.
Depois, com o Inno Setup instalado:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

O instalador final aparece em `packaging\saida\PainelDeContatosSetup-X.Y.Z.exe`
(com o número da versão no nome, ex.: `PainelDeContatosSetup-0.11.0.exe`) —
esse é o arquivo para distribuir. Ele já contém tudo que o programa precisa
para rodar, sem exigir Python instalado na máquina de quem for usar.

> **Aviso do Windows na primeira execução**: como o instalador não tem uma
> assinatura digital paga, o SmartScreen do Windows pode avisar "Editor
> desconhecido" — é normal para programas internos e não indica problema.
> Para remover esse aviso seria necessário comprar um certificado de
> assinatura de código (fora do escopo deste projeto).

## Publicar uma nova versão (pra o aviso de atualização funcionar)

Toda vez que o programa é aberto, ele confere sozinho (em segundo plano, sem
travar nada) se existe uma versão mais nova publicada no GitHub e, se
existir, pergunta ao usuário se quer atualizar agora — se ele aceitar, o
programa baixa o instalador novo, abre ele e se fecha sozinho.

Pra isso funcionar, publicar uma versão nova envolve 4 passos:

```bat
REM 1) Aumentar o numero em versao.py (VERSAO e VERSAO_DATA)
REM 2) Aumentar MyAppVersion em packaging\installer.iss pro mesmo numero
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pyinstaller packaging\PainelDeContatos.spec
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

O instalador final aparece em `packaging\saida\PainelDeContatosSetup-X.Y.Z.exe`
(mesmo processo já descrito acima). O último passo é publicar uma
**Release** no GitHub, em
<https://github.com/Fernandoflino/agenda-de-contatos/releases/new>:

- Tag: `vX.Y.Z` — o mesmo número usado em `versao.py` (ex.: `v0.12.0`).
- Anexar o arquivo `PainelDeContatosSetup-X.Y.Z.exe` como asset da release.

Sem esse último passo, o número em `versao.py` até muda no código-fonte,
mas ninguém recebe aviso nenhum — é a Release publicada que o aviso de
atualização (`atualizacao.py`) consulta pra saber se há algo mais novo.
Quem já tem o programa aberto numa versão mais antiga vê o aviso
automaticamente na próxima vez que abrir, sem precisar fazer mais nada.

## Estrutura do projeto

- `db/` — tudo relacionado a banco de dados: schema, criação/edição de
  tabelas e campos em tempo real, CRUD de registros, login/senha,
  importação de planilha `.xlsx`, exportação.
- `ui/` — as telas do programa (PySide6/Qt): login, lista de contatos,
  grade genérica (empresas e tabelas extras), formulários, configurações.
- `config/` — preferências do computador/usuário Windows (lista de bancos
  recentes), guardadas fora do arquivo `.abepdb`.
- `atualizacao.py` — checagem de nova versão via GitHub Releases e download
  do instalador (ver seção acima).
- `packaging/` — arquivos usados para gerar o instalador (`.spec` do
  PyInstaller e `.iss` do Inno Setup).
- `tests/` — testes automatizados (`pytest`).

Cada arquivo `.py` tem, no topo, um comentário explicando em português claro
para que ele serve — a ideia é que alguém sem experiência em programação
consiga acompanhar o que cada parte do programa faz.
