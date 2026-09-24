"""
Este arquivo implementa o "esquema dinamico" do programa: a possibilidade de
criar, renomear e apagar TABELAS (que na tela aparecem como "abas" de dados,
igual no sistema antigo de planilha) e CAMPOS (colunas) a qualquer momento,
pela propria interface -- sem precisar mexer no codigo do programa.

Isso e o que permite, por exemplo, o usuario criar uma tabela nova chamada
"FORNECEDORES" com os campos que ele quiser, do jeito que ele quiser, e o
programa passa a saber lidar com ela automaticamente (listar, editar,
exportar etc.) do mesmo jeito que lida com EMPRESAS e PESSOAS.
"""
from __future__ import annotations

import sqlite3

from . import log
from .identifiers import quote_ident, validar_identificador
from .schema import APP_COLUMN_ORDER, APP_FIELD_TYPES, APP_TABLE_ORDER, RESERVED_TABLES, TABELAS_PROTEGIDAS


def list_data_sheets(conn: sqlite3.Connection) -> list[str]:
    """Lista os nomes de todas as tabelas de DADOS (ou seja, tudo que nao e
    uma tabela interna do programa como app_log, app_metadata etc.)."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    nomes = [r[0] for r in cur.fetchall()]
    return [n for n in nomes if n not in RESERVED_TABLES]


def get_schema(conn: sqlite3.Connection, tabela: str) -> list[str]:
    """Lista os nomes das colunas de uma tabela, na ordem fisica em que
    foram criadas (essa NAO e necessariamente a ordem de exibicao na tela --
    veja get_column_order() mais abaixo pra isso)."""
    tabela = validar_identificador(tabela, "tabela")
    # PRAGMA table_info e o comando do SQLite pra "perguntar" quais colunas
    # uma tabela tem -- e como olhar a "receita" de uma tabela ja existente.
    cur = conn.execute(f"PRAGMA table_info({quote_ident(tabela)})")
    return [row[1] for row in cur.fetchall()]


def _tabela_existe(conn: sqlite3.Connection, nome: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND LOWER(name) = LOWER(?)", (nome,)
    ).fetchone()
    return row is not None


def create_data_sheet(conn: sqlite3.Connection, nome: str, copiar_de: str | None = None,
                       usuario: str = "sistema") -> str:
    """Cria uma tabela de dados nova.

    Se `copiar_de` for informado, a tabela nova nasce com as MESMAS colunas
    de outra tabela ja existente (mas sem copiar os dados/linhas dela) --
    util pra criar, por exemplo, uma segunda tabela de pessoas parecida com
    PESSOAS. Se nao, a tabela nasce so com a coluna "ID", e o usuario adiciona
    os campos que quiser depois, pela tela de configuracao de campos.
    """
    nome = validar_identificador(nome, "nome da tabela")
    if _tabela_existe(conn, nome):
        raise ValueError(f'Ja existe uma tabela com o nome "{nome}".')

    if copiar_de:
        copiar_de = validar_identificador(copiar_de, "tabela de origem")
        if not _tabela_existe(conn, copiar_de):
            raise ValueError(f'Tabela de origem "{copiar_de}" nao encontrada.')
        # "WHERE 0" e um truque pra copiar a ESTRUTURA (colunas) sem copiar
        # nenhuma linha -- a condicao nunca e verdadeira, entao nada e trazido.
        conn.execute(
            f'CREATE TABLE {quote_ident(nome)} AS SELECT * FROM {quote_ident(copiar_de)} WHERE 0'
        )
        detalhes = f"estrutura copiada de {copiar_de}"
    else:
        conn.execute(f'CREATE TABLE {quote_ident(nome)} ("ID" INTEGER PRIMARY KEY)')
        detalhes = "tabela em branco"

    conn.commit()
    log.log_change(conn, usuario, nome, "Criar tabela", detalhes)
    return nome


def rename_data_sheet(conn: sqlite3.Connection, nome_atual: str, novo_nome: str, usuario: str = "sistema") -> str:
    """Renomeia uma tabela de dados, e atualiza as configuracoes que
    guardavam referencia ao nome antigo (ordem de colunas, tipos de campo)."""
    nome_atual = validar_identificador(nome_atual, "tabela")
    novo_nome = validar_identificador(novo_nome, "novo nome da tabela")
    # Comparacao EXATA (nao ignora maiusculas/minusculas) de proposito: assim
    # ainda e possivel corrigir uma tabela que ficou com o nome errado (ex.:
    # "Pessoas" em vez de "PESSOAS") renomeando ela de volta pro nome certo --
    # so bloqueia renomear a tabela que JA ESTA com o nome canonico exato.
    if nome_atual in TABELAS_PROTEGIDAS:
        raise ValueError(
            f'A tabela "{nome_atual}" e essencial pro funcionamento do programa e nao pode ser renomeada '
            f'(login, contatos e empresas dependem desse nome exato). Use o "rotulo de exibicao" se quiser '
            f'que ela apareca com outro nome no menu lateral.'
        )
    if not _tabela_existe(conn, nome_atual):
        raise ValueError(f'Tabela "{nome_atual}" nao encontrada.')
    # So bloqueia por conflito se for uma tabela DIFERENTE com esse nome --
    # renomear so a caixa (ex.: "Pessoas" -> "PESSOAS") tem que continuar
    # funcionando, mesmo o SQLite tratando os dois nomes como "iguais" pra
    # fins de existencia.
    eh_so_troca_de_caixa = nome_atual != novo_nome and nome_atual.lower() == novo_nome.lower()
    if not eh_so_troca_de_caixa and _tabela_existe(conn, novo_nome):
        raise ValueError(f'Ja existe uma tabela com o nome "{novo_nome}".')

    nome_fisico_atual = nome_atual
    if eh_so_troca_de_caixa:
        # O proprio SQLite recusa "ALTER TABLE x RENAME TO X" direto (trata
        # os dois nomes como o mesmo e acusa conflito) -- passa por um nome
        # intermediario que nao colide com nenhum dos dois, transparente
        # pra quem chamou esta funcao. `nome_atual` (usado mais abaixo pra
        # atualizar app_column_order/app_field_types) continua sendo o nome
        # ORIGINAL, que e o que essas tabelas de configuracao tem guardado.
        nome_fisico_atual = f"{nome_atual}_tmp_{id(object())}"
        conn.execute(f"ALTER TABLE {quote_ident(nome_atual)} RENAME TO {quote_ident(nome_fisico_atual)}")

    conn.execute(f"ALTER TABLE {quote_ident(nome_fisico_atual)} RENAME TO {quote_ident(novo_nome)}")
    conn.execute(f"UPDATE {APP_COLUMN_ORDER} SET tabela = ? WHERE tabela = ?", (novo_nome, nome_atual))
    conn.execute(f"UPDATE {APP_FIELD_TYPES} SET tabela = ? WHERE tabela = ?", (novo_nome, nome_atual))
    conn.execute(f"UPDATE {APP_TABLE_ORDER} SET tabela = ? WHERE tabela = ?", (novo_nome, nome_atual))
    conn.commit()
    log.log_change(conn, usuario, novo_nome, "Renomear tabela", f"antes: {nome_atual}")
    return novo_nome


def delete_data_sheet(conn: sqlite3.Connection, nome: str, usuario: str = "sistema") -> None:
    """Apaga uma tabela de dados inteira (com todas as linhas dela).

    Nunca deixa apagar a UNICA tabela de dados que sobrou -- o programa
    sempre precisa ter pelo menos uma tabela pra mostrar alguma coisa na tela.
    """
    nome = validar_identificador(nome, "tabela")
    if nome in TABELAS_PROTEGIDAS:
        raise ValueError(
            f'A tabela "{nome}" e essencial pro funcionamento do programa e nao pode ser excluida.'
        )
    if not _tabela_existe(conn, nome):
        raise ValueError(f'Tabela "{nome}" nao encontrada.')
    if len(list_data_sheets(conn)) <= 1:
        raise ValueError("Nao e possivel excluir a unica tabela de dados.")

    conn.execute(f"DROP TABLE {quote_ident(nome)}")
    conn.execute(f"DELETE FROM {APP_COLUMN_ORDER} WHERE tabela = ?", (nome,))
    conn.execute(f"DELETE FROM {APP_FIELD_TYPES} WHERE tabela = ?", (nome,))
    conn.execute(f"DELETE FROM {APP_TABLE_ORDER} WHERE tabela = ?", (nome,))
    conn.commit()
    log.log_change(conn, usuario, nome, "Excluir tabela")


def add_column(conn: sqlite3.Connection, tabela: str, coluna: str, tipo_sql: str = "TEXT",
               usuario: str = "sistema") -> None:
    """Adiciona um campo (coluna) novo numa tabela existente.

    `tipo_sql` quase sempre fica "TEXT" (texto livre) -- o "tipo" que aparece
    pro usuario na tela (email, telefone, data, selecao...) e uma coisa
    diferente, guardada em app_field_types e usada so pela interface pra
    decidir que tipo de campo mostrar no formulario (veja ui/field_types.py).
    """
    tabela = validar_identificador(tabela, "tabela")
    coluna = validar_identificador(coluna, "campo")
    if coluna in get_schema(conn, tabela):
        raise ValueError(f'A tabela "{tabela}" ja tem um campo "{coluna}".')

    conn.execute(f"ALTER TABLE {quote_ident(tabela)} ADD COLUMN {quote_ident(coluna)} {tipo_sql}")
    conn.commit()
    log.log_change(conn, usuario, tabela, "Adicionar campo", coluna)


def rename_column(conn: sqlite3.Connection, tabela: str, atual: str, novo: str, usuario: str = "sistema") -> None:
    """Renomeia um campo, atualizando tambem as configuracoes que
    referenciavam o nome antigo dele (ordem de exibicao, tipo configurado)."""
    tabela = validar_identificador(tabela, "tabela")
    atual = validar_identificador(atual, "campo")
    novo = validar_identificador(novo, "novo nome do campo")

    conn.execute(f"ALTER TABLE {quote_ident(tabela)} RENAME COLUMN {quote_ident(atual)} TO {quote_ident(novo)}")
    conn.execute(
        f"UPDATE {APP_COLUMN_ORDER} SET coluna = ? WHERE tabela = ? AND coluna = ?", (novo, tabela, atual)
    )
    conn.execute(
        f"UPDATE {APP_FIELD_TYPES} SET coluna = ? WHERE tabela = ? AND coluna = ?", (novo, tabela, atual)
    )
    conn.commit()
    log.log_change(conn, usuario, tabela, "Renomear campo", f"{atual} -> {novo}")


def drop_column(conn: sqlite3.Connection, tabela: str, coluna: str, usuario: str = "sistema") -> None:
    """Remove um campo de uma tabela (e os dados que estavam nele, pra
    sempre). O campo "ID" nunca pode ser removido -- e ele que identifica
    cada linha de forma unica dentro do programa."""
    tabela = validar_identificador(tabela, "tabela")
    coluna = validar_identificador(coluna, "campo")
    if coluna == "ID":
        raise ValueError('O campo "ID" nao pode ser removido.')

    conn.execute(f"ALTER TABLE {quote_ident(tabela)} DROP COLUMN {quote_ident(coluna)}")
    conn.execute(f"DELETE FROM {APP_COLUMN_ORDER} WHERE tabela = ? AND coluna = ?", (tabela, coluna))
    conn.execute(f"DELETE FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = ?", (tabela, coluna))
    conn.commit()
    log.log_change(conn, usuario, tabela, "Remover campo", coluna)


def get_column_order(conn: sqlite3.Connection, tabela: str) -> list[str]:
    """Em que ordem as colunas dessa tabela devem aparecer na tela.

    Isso e so uma preferencia "de exibicao" -- nao muda a estrutura real da
    tabela no banco de dados. Colunas que o usuario ainda nao reordenou
    aparecem no final, na ordem em que foram criadas.
    """
    schema_fisico = get_schema(conn, tabela)
    cur = conn.execute(
        f"SELECT coluna FROM {APP_COLUMN_ORDER} WHERE tabela = ? ORDER BY posicao", (tabela,)
    )
    configuradas = [r[0] for r in cur.fetchall() if r[0] in schema_fisico]
    resto = [c for c in schema_fisico if c not in configuradas]
    return configuradas + resto


def set_column_order(conn: sqlite3.Connection, tabela: str, colunas_em_ordem: list[str]) -> None:
    """Salva a ordem de exibicao escolhida pelo usuario pra essa tabela."""
    conn.execute(f"DELETE FROM {APP_COLUMN_ORDER} WHERE tabela = ?", (tabela,))
    conn.executemany(
        f"INSERT INTO {APP_COLUMN_ORDER} (tabela, coluna, posicao) VALUES (?, ?, ?)",
        [(tabela, coluna, i) for i, coluna in enumerate(colunas_em_ordem)],
    )
    conn.commit()


def get_table_order(conn: sqlite3.Connection) -> list[str]:
    """Em que ordem as tabelas de dados devem aparecer (sidebar e a tela de
    "Gerenciar tabelas e campos"). Mesma logica de get_column_order(): tabelas
    que o usuario ainda nao reordenou aparecem no final, em ordem alfabetica."""
    tabelas_existentes = list_data_sheets(conn)
    cur = conn.execute(f"SELECT tabela FROM {APP_TABLE_ORDER} ORDER BY posicao")
    configuradas = [r[0] for r in cur.fetchall() if r[0] in tabelas_existentes]
    resto = [t for t in tabelas_existentes if t not in configuradas]
    return configuradas + resto


def set_table_order(conn: sqlite3.Connection, tabelas_em_ordem: list[str]) -> None:
    """Salva a ordem de exibicao das tabelas escolhida pelo usuario."""
    conn.execute(f"DELETE FROM {APP_TABLE_ORDER}")
    conn.executemany(
        f"INSERT INTO {APP_TABLE_ORDER} (tabela, posicao) VALUES (?, ?)",
        [(tabela, i) for i, tabela in enumerate(tabelas_em_ordem)],
    )
    conn.commit()
