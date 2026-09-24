"""
Este arquivo cuida de ABRIR e CRIAR o arquivo de banco de dados (.abepdb).

Pensa no arquivo .abepdb como se fosse um arquivo do Word ou do Excel: ele
fica salvo no computador, em qualquer pasta que o usuario escolher (pen
drive, pasta de rede, OneDrive etc.), e o programa so precisa saber o
"caminho" (endereco) desse arquivo pra conseguir abrir ele. Por baixo dos
panos, e um banco de dados SQLite -- um formato de arquivo unico, sem precisar
de nenhum servidor rodando por tras.
"""
from __future__ import annotations

import os
import sqlite3

from . import schema

EXTENSAO_PADRAO = ".abepdb"


def _aplicar_pragmas(conn: sqlite3.Connection) -> None:
    """Ajustes de comportamento do SQLite aplicados em toda conexao aberta.

    "PRAGMA" e o jeito do SQLite de configurar como ele proprio se comporta.
    Aqui usamos dois:
    - busy_timeout: se dois processos tentarem mexer no arquivo ao mesmo
      tempo (ex.: o arquivo esta numa pasta de rede e duas pessoas abriram o
      programa), o SQLite espera ate 5 segundos antes de desistir, em vez de
      falhar na hora com "banco de dados travado".
    - foreign_keys: liga a checagem de que, por exemplo, o ID_EMPRESA de uma
      pessoa realmente aponta pra uma empresa que existe.

    Note que NAO ativamos o modo "WAL" (um jeito mais rapido de o SQLite
    gravar mudancas) porque ele nao funciona de forma confiavel quando o
    arquivo esta numa pasta compartilhada de rede -- e exatamente o cenario
    que este programa precisa suportar (banco compartilhado entre pessoas).
    """
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")


def conectar(caminho: str) -> sqlite3.Connection:
    """Abre um arquivo .abepdb que ja existe. Da erro se o arquivo nao existir."""
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f'Arquivo de banco nao encontrado: "{caminho}"')
    conn = sqlite3.connect(caminho)
    _aplicar_pragmas(conn)
    # Bancos criados por uma versao mais antiga do programa podem estar
    # "desatualizados" (faltando uma tabela/coluna nova) -- isso conserta
    # automaticamente, sem precisar de nenhuma acao do usuario.
    schema.migrar_schema_se_necessario(conn)
    return conn


def criar_novo(caminho: str) -> sqlite3.Connection:
    """Cria um arquivo .abepdb NOVO, ja com todas as tabelas iniciais dentro.

    Se algo der errado no meio da criacao (por exemplo, falta de espaco em
    disco), o arquivo parcialmente criado e apagado automaticamente -- assim
    nunca sobra um banco "pela metade" e corrompido no lugar que o usuario
    escolheu.
    """
    if os.path.exists(caminho):
        raise FileExistsError(f'Ja existe um arquivo em "{caminho}".')

    conn = sqlite3.connect(caminho)
    try:
        _aplicar_pragmas(conn)
        schema.criar_schema_inicial(conn)
    except Exception:
        conn.close()
        if os.path.exists(caminho):
            os.remove(caminho)
        raise
    return conn
