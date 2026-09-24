"""
Este arquivo cuida da LISTA DE CATEGORIAS dos contatos e de quais categorias
cada pessoa tem (um contato pode ter VARIAS categorias ao mesmo tempo --
ex.: "Presidentes" e "Diretores Tecnicos" -- diferente do campo CARGO, que e
texto livre).

A lista mestre fica em app_categorias (nome + ordem de exibicao), e o
vinculo entre cada pessoa e suas categorias fica em app_pessoas_categorias
(tabela de relacao N:N -- ver db/schema.py). As opcoes que aparecem no
formulario de contato e no filtro por categoria da lista vem daqui.
"""
from __future__ import annotations

import sqlite3

from db import log
from db.schema import APP_CATEGORIAS, APP_PESSOAS_CATEGORIAS, PESSOAS


def listar_categorias(conn: sqlite3.Connection) -> list[str]:
    """A lista de categorias configuradas, na ordem de exibicao escolhida."""
    cur = conn.execute(f'SELECT "NOME" FROM {APP_CATEGORIAS} ORDER BY "ORDEM"')
    return [r[0] for r in cur.fetchall()]


def mover_categoria(conn: sqlite3.Connection, nome: str, direcao: int) -> None:
    """Move uma categoria uma posicao na ordem de exibicao, trocando de
    lugar com a vizinha -- direcao=-1 sobe, direcao=+1 desce. Nao faz nada
    se a categoria ja estiver na ponta (primeira/ultima) nessa direcao."""
    ordenadas = conn.execute(f'SELECT "ID", "NOME", "ORDEM" FROM {APP_CATEGORIAS} ORDER BY "ORDEM"').fetchall()
    indice = next((i for i, linha in enumerate(ordenadas) if linha[1] == nome), None)
    if indice is None:
        return
    indice_vizinho = indice + direcao
    if indice_vizinho < 0 or indice_vizinho >= len(ordenadas):
        return
    id_atual, _, ordem_atual = ordenadas[indice]
    id_vizinho, _, ordem_vizinho = ordenadas[indice_vizinho]
    conn.execute(f'UPDATE {APP_CATEGORIAS} SET "ORDEM" = ? WHERE "ID" = ?', (ordem_vizinho, id_atual))
    conn.execute(f'UPDATE {APP_CATEGORIAS} SET "ORDEM" = ? WHERE "ID" = ?', (ordem_atual, id_vizinho))
    conn.commit()


def contar_uso(conn: sqlite3.Connection, nome: str) -> int:
    """Quantos contatos usam essa categoria hoje -- usado pra avisar antes
    de renomear ou excluir."""
    cur = conn.execute(f"""
        SELECT COUNT(*) FROM {APP_PESSOAS_CATEGORIAS} pc
        JOIN {APP_CATEGORIAS} c ON c."ID" = pc."CATEGORIA_ID"
        WHERE c."NOME" = ?
    """, (nome,))
    return cur.fetchone()[0]


def adicionar_categoria(conn: sqlite3.Connection, nome: str, usuario: str = "sistema") -> None:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe um nome para a categoria.")
    existentes = listar_categorias(conn)
    if any(c.lower() == nome.lower() for c in existentes):
        raise ValueError(f'A categoria "{nome}" já existe.')
    proxima_ordem = conn.execute(f'SELECT COALESCE(MAX("ORDEM"), -1) FROM {APP_CATEGORIAS}').fetchone()[0] + 1
    conn.execute(f'INSERT INTO {APP_CATEGORIAS} ("NOME", "ORDEM") VALUES (?, ?)', (nome, proxima_ordem))
    conn.commit()
    log.log_change(conn, usuario, PESSOAS, "Adicionar categoria", nome)


def renomear_categoria(conn: sqlite3.Connection, nome_atual: str, nome_novo: str, usuario: str = "sistema") -> int:
    """Renomeia uma categoria -- como o vinculo com cada pessoa e pelo ID da
    categoria (nao pelo texto), isso NAO precisa tocar em nenhum contato:
    quem tinha essa categoria continua com ela, so o nome exibido muda.
    Devolve quantos contatos usam essa categoria (so informativo)."""
    nome_novo = (nome_novo or "").strip()
    if not nome_novo:
        raise ValueError("Informe um nome para a categoria.")
    existentes = listar_categorias(conn)
    if nome_atual not in existentes:
        raise ValueError(f'Categoria "{nome_atual}" não encontrada.')
    if nome_novo.lower() != nome_atual.lower() and any(c.lower() == nome_novo.lower() for c in existentes):
        raise ValueError(f'A categoria "{nome_novo}" já existe.')

    conn.execute(f'UPDATE {APP_CATEGORIAS} SET "NOME" = ? WHERE "NOME" = ?', (nome_novo, nome_atual))
    conn.commit()
    log.log_change(conn, usuario, PESSOAS, "Renomear categoria", f"{nome_atual} -> {nome_novo}")
    return contar_uso(conn, nome_novo)


def excluir_categoria(conn: sqlite3.Connection, nome: str, usuario: str = "sistema") -> int:
    """Remove uma categoria da lista mestre -- os vinculos dela com contatos
    somem junto (ON DELETE CASCADE), mas cada contato continua com as
    OUTRAS categorias que tiver. Devolve quantos contatos foram afetados."""
    afetados = contar_uso(conn, nome)
    conn.execute(f'DELETE FROM {APP_CATEGORIAS} WHERE "NOME" = ?', (nome,))
    conn.commit()
    log.log_change(conn, usuario, PESSOAS, "Excluir categoria", nome)
    return afetados


def categorias_da_pessoa(conn: sqlite3.Connection, pessoa_id: int) -> list[str]:
    """As categorias de UM contato especifico, na ordem de exibicao."""
    cur = conn.execute(f"""
        SELECT c."NOME" FROM {APP_PESSOAS_CATEGORIAS} pc
        JOIN {APP_CATEGORIAS} c ON c."ID" = pc."CATEGORIA_ID"
        WHERE pc."PESSOA_ID" = ?
        ORDER BY c."ORDEM"
    """, (pessoa_id,))
    return [r[0] for r in cur.fetchall()]


def definir_categorias_da_pessoa(conn: sqlite3.Connection, pessoa_id: int, nomes: list[str]) -> None:
    """Substitui TODOS os vinculos de categoria dessa pessoa pelos nomes
    informados (lista vazia = pessoa fica sem categoria nenhuma). Nomes que
    nao existem mais na lista mestre (ex.: categoria excluida por outra
    pessoa enquanto o formulario estava aberto) sao ignorados em silencio."""
    conn.execute(f'DELETE FROM {APP_PESSOAS_CATEGORIAS} WHERE "PESSOA_ID" = ?', (pessoa_id,))
    nomes_unicos = list(dict.fromkeys(n.strip() for n in nomes if n and n.strip()))
    if nomes_unicos:
        marcadores = ",".join("?" for _ in nomes_unicos)
        cur = conn.execute(
            f'SELECT "ID" FROM {APP_CATEGORIAS} WHERE "NOME" IN ({marcadores})', nomes_unicos
        )
        ids = [row[0] for row in cur.fetchall()]
        conn.executemany(
            f'INSERT INTO {APP_PESSOAS_CATEGORIAS} ("PESSOA_ID", "CATEGORIA_ID") VALUES (?, ?)',
            [(pessoa_id, categoria_id) for categoria_id in ids],
        )
    conn.commit()
