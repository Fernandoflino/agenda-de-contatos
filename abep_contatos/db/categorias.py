"""
Este arquivo cuida da LISTA DE CATEGORIAS dos contatos (campo CATEGORIA da
tabela PESSOAS -- ex.: "Presidentes", "Diretores Tecnicos", "Diretores Adm.
Financeiros"). Essas sao as opcoes que aparecem no menu suspenso do
formulario de contato e no filtro por categoria da lista.

A lista fica guardada em app_field_types -- a mesma tabela usada por
ui/field_types.py pra guardar o TIPO de qualquer campo (aqui, o campo
CATEGORIA de PESSOAS e sempre do tipo "selecao", com a lista de categorias
guardada como as "opcoes" dele). Ou seja: mexer aqui e o mesmo que configurar
esse campo pela tela generica de "Tabelas e campos" -- so que com uma tela
dedicada (o CRUD de categorias, aberto pela barra lateral) que tambem cuida
de renomear/limpar o valor nos contatos que ja usam aquela categoria, coisa
que a tela generica de campos nao faz.
"""
from __future__ import annotations

import json
import sqlite3

from db import log
from db.schema import APP_FIELD_TYPES, PESSOAS

_TABELA = PESSOAS
_COLUNA = "CATEGORIA"
_TIPO_SELECAO = "selecao"


def listar_categorias(conn: sqlite3.Connection) -> list[str]:
    """A lista de categorias configuradas ate agora.

    Se ainda ninguem configurou essa lista (banco recem-criado, ou um banco
    antigo de antes dessa tela existir), "semeia" a lista com os valores que
    JA aparecem de verdade nos contatos cadastrados -- assim quem ja tinha
    dados nao perde nenhuma categoria em uso ao passar a usar a lista
    suspensa em vez de texto livre.
    """
    row = conn.execute(
        f"SELECT opcoes FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = ?", (_TABELA, _COLUNA)
    ).fetchone()
    if row and row[0]:
        try:
            opcoes = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            opcoes = None
        if isinstance(opcoes, list):
            return opcoes
    return _valores_em_uso(conn)


def _valores_em_uso(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        f'SELECT DISTINCT "{_COLUNA}" FROM "{_TABELA}" WHERE "{_COLUNA}" IS NOT NULL AND "{_COLUNA}" != \'\''
    )
    return sorted({str(r[0]) for r in cur.fetchall()})


def _salvar_lista(conn: sqlite3.Connection, categorias: list[str]) -> None:
    opcoes_json = json.dumps(categorias, ensure_ascii=False)
    conn.execute(
        f"""INSERT INTO {APP_FIELD_TYPES} (tabela, coluna, tipo, opcoes) VALUES (?, ?, ?, ?)
            ON CONFLICT(tabela, coluna) DO UPDATE SET tipo = excluded.tipo, opcoes = excluded.opcoes""",
        (_TABELA, _COLUNA, _TIPO_SELECAO, opcoes_json),
    )
    conn.commit()


def contar_uso(conn: sqlite3.Connection, nome: str) -> int:
    """Quantos contatos usam essa categoria hoje -- usado pra avisar antes
    de renomear ou excluir."""
    cur = conn.execute(f'SELECT COUNT(*) FROM "{_TABELA}" WHERE "{_COLUNA}" = ?', (nome,))
    return cur.fetchone()[0]


def adicionar_categoria(conn: sqlite3.Connection, nome: str, usuario: str = "sistema") -> None:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe um nome para a categoria.")
    categorias = listar_categorias(conn)
    if any(c.lower() == nome.lower() for c in categorias):
        raise ValueError(f'A categoria "{nome}" já existe.')
    categorias.append(nome)
    _salvar_lista(conn, categorias)
    log.log_change(conn, usuario, _TABELA, "Adicionar categoria", nome)


def renomear_categoria(conn: sqlite3.Connection, nome_atual: str, nome_novo: str, usuario: str = "sistema") -> int:
    """Renomeia uma categoria na lista de opcoes E em todos os contatos que
    ja usam esse valor (senao os contatos ficariam com um valor "orfao", que
    nao aparece mais na lista suspensa). Devolve quantos contatos foram
    atualizados."""
    nome_novo = (nome_novo or "").strip()
    if not nome_novo:
        raise ValueError("Informe um nome para a categoria.")
    categorias = listar_categorias(conn)
    if nome_atual not in categorias:
        raise ValueError(f'Categoria "{nome_atual}" não encontrada.')
    if nome_novo.lower() != nome_atual.lower() and any(c.lower() == nome_novo.lower() for c in categorias):
        raise ValueError(f'A categoria "{nome_novo}" já existe.')

    categorias = [nome_novo if c == nome_atual else c for c in categorias]
    _salvar_lista(conn, categorias)

    cursor = conn.execute(f'UPDATE "{_TABELA}" SET "{_COLUNA}" = ? WHERE "{_COLUNA}" = ?', (nome_novo, nome_atual))
    conn.commit()
    log.log_change(conn, usuario, _TABELA, "Renomear categoria", f"{nome_atual} -> {nome_novo}")
    return cursor.rowcount


def excluir_categoria(conn: sqlite3.Connection, nome: str, usuario: str = "sistema") -> int:
    """Remove uma categoria da lista de opcoes e LIMPA o campo CATEGORIA dos
    contatos que usavam ela (o contato continua existindo, so fica sem
    categoria). Devolve quantos contatos foram afetados."""
    categorias = [c for c in listar_categorias(conn) if c != nome]
    _salvar_lista(conn, categorias)

    cursor = conn.execute(f'UPDATE "{_TABELA}" SET "{_COLUNA}" = NULL WHERE "{_COLUNA}" = ?', (nome,))
    conn.commit()
    log.log_change(conn, usuario, _TABELA, "Excluir categoria", nome)
    return cursor.rowcount
