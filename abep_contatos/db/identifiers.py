"""
Este arquivo cuida de um detalhe tecnico importante e um pouco chato: como o
usuario pode criar tabelas e campos com QUALQUER nome (pela tela de
"Configurar campos"), o programa precisa colocar esses nomes dentro dos
comandos SQL de um jeito seguro -- senao alguem poderia, sem querer ou de
proposito, digitar um nome de campo que "quebra" o banco de dados ou apaga
dados (isso se chama "injecao de SQL").

Regra geral usada no resto do programa: um VALOR (o conteudo de um campo,
tipo "Joao da Silva") sempre e enviado separado do comando SQL (o sqlite3 do
Python faz isso sozinho quando usamos "?" no lugar do valor). Ja um NOME de
tabela ou coluna (que o SQL nao deixa passar como "?") precisa ser validado
aqui e depois cercado de aspas duplas, com qualquer aspas dupla dentro dele
duplicada -- e assim que o proprio SQL espera que nomes "esquisitos" sejam
escritos.
"""
from __future__ import annotations

# Nenhuma tabela/coluna criada pelo usuario pode comecar com "app_" -- esse
# prefixo e reservado pras tabelas internas do proprio programa (log de
# alteracoes, configuracoes, etc.), pra nunca dar conflito com uma tabela que
# o usuario decida criar com um nome parecido.
_RESERVED_PREFIXES = ("app_", "sqlite_")
_MAX_IDENT_LEN = 64


def validar_identificador(nome: str, tipo: str = "nome") -> str:
    """Confere se `nome` e um nome de tabela/coluna aceitavel.

    Se nao for (vazio, gigante, ou tentando usar um prefixo reservado), o
    programa interrompe a acao com uma mensagem de erro em portugues, pronta
    pra ser mostrada na tela pro usuario entender o que aconteceu.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError(f"Informe um {tipo}.")
    if len(nome) > _MAX_IDENT_LEN:
        raise ValueError(f"{tipo} muito longo (max. {_MAX_IDENT_LEN} caracteres).")
    if "\x00" in nome:
        # Um caractere nulo no meio do nome nao tem uso legitimo nenhum aqui --
        # so apareceria numa tentativa de burlar o banco de dados.
        raise ValueError(f"{tipo} invalido.")
    if nome.lower().startswith(_RESERVED_PREFIXES):
        raise ValueError(f'{tipo} nao pode comecar com "app_" (reservado internamente).')
    return nome


def quote_ident(nome: str) -> str:
    """Coloca `nome` entre aspas duplas, do jeito que o SQL exige pra usar
    como nome de tabela/coluna (em vez de como um valor comum).

    IMPORTANTE: so chame esta funcao depois de validar_identificador() --
    ela so cuida de "escapar" o nome, nao de validar se ele e seguro.
    """
    # Se o proprio nome tiver uma aspas dupla dentro dele, dobramos ela
    # (" vira ""), que e a forma padrao do SQL de dizer "essa aspas faz parte
    # do nome, nao é o fim dele".
    return '"' + nome.replace('"', '""') + '"'
