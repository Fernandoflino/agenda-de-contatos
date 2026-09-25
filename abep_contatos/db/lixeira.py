"""
Este arquivo cuida da LIXEIRA: guarda uma "foto" (snapshot) de tudo que e
excluido no programa -- registros de PESSOAS/EMPRESAS/USUARIOS/tabelas
criadas pelo usuario, tabelas inteiras, e campos/colunas -- pra dar pra
RESTAURAR depois em vez de perder pra sempre.

Cada JSON guarda o suficiente pra reconstruir o que foi apagado (ver o
schema das 3 tabelas em db/schema.py: app_lixeira_registros/
app_lixeira_tabelas/app_lixeira_campos). As funcoes "capturar_*" sao
chamadas de dentro de db/records.py e db/tables.py, sempre ANTES da
exclusao de verdade -- elas so FOTOGRAFAM, nunca apagam nada sozinhas.

As funcoes "restaurar_*" fazem o caminho inverso: recriam o registro/
tabela/campo a partir da foto guardada, e so entao removem a foto da
lixeira. Se a restauracao falhar (ex.: FK apontando pra uma empresa que
tambem foi excluida e ainda nao foi restaurada), a foto continua na
lixeira intacta.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from . import log
from .anotacoes import obter_anotacao, salvar_anotacao
from .identifiers import quote_ident, validar_identificador
from .schema import (
    APP_ANOTACOES,
    APP_CATEGORIAS,
    APP_COLUMN_ORDER,
    APP_FIELD_TYPES,
    APP_LIST_DISPLAY,
    APP_LIXEIRA_CAMPOS,
    APP_LIXEIRA_REGISTROS,
    APP_LIXEIRA_TABELAS,
    APP_PESSOAS_CATEGORIAS,
    APP_TABLE_LABELS,
    APP_TABLE_ORDER,
    PESSOAS,
)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _colunas_fisicas(conn: sqlite3.Connection, tabela: str) -> list[dict]:
    """Nome, tipo SQL e se e chave primaria de cada coluna, na ordem FISICA
    (a que PRAGMA table_info devolve) -- diferente de db/tables.py::get_schema
    (que so devolve os nomes), aqui precisamos do tipo pra poder recriar a
    tabela do zero."""
    cur = conn.execute(f"PRAGMA table_info({quote_ident(tabela)})")
    return [{"nome": row[1], "tipo": row[2], "pk": bool(row[5])} for row in cur.fetchall()]


# ============================================================================
# REGISTROS (uma linha de PESSOAS/EMPRESAS/USUARIOS/etc.)
# ============================================================================

def capturar_registro(conn: sqlite3.Connection, tabela: str, id_valor: int, usuario: str) -> None:
    """Guarda uma copia de UM registro (linha crua da tabela, mais
    categorias e anotacao quando fizer sentido) na lixeira. Chamado por
    db/records.py::delete_record logo ANTES do DELETE de verdade."""
    colunas = [c["nome"] for c in _colunas_fisicas(conn, tabela)]
    linha = conn.execute(
        f'SELECT * FROM {quote_ident(tabela)} WHERE "ID" = ?', (id_valor,)
    ).fetchone()
    if linha is None:
        return
    dados = dict(zip(colunas, linha))

    categorias_json = None
    if tabela == PESSOAS:
        nomes = [
            row[0] for row in conn.execute(
                f"""SELECT c."NOME" FROM {APP_PESSOAS_CATEGORIAS} pc
                    JOIN {APP_CATEGORIAS} c ON c."ID" = pc."CATEGORIA_ID"
                    WHERE pc."PESSOA_ID" = ? ORDER BY c."ORDEM\"""",
                (id_valor,),
            ).fetchall()
        ]
        categorias_json = json.dumps(nomes, ensure_ascii=False)

    anotacao = obter_anotacao(conn, tabela, id_valor) or None

    conn.execute(
        f"""INSERT INTO {APP_LIXEIRA_REGISTROS}
            ("TABELA", "REGISTRO_ID_ORIGINAL", "DADOS_JSON", "CATEGORIAS_JSON", "ANOTACAO_TEXTO",
             "EXCLUIDO_POR", "EXCLUIDO_EM")
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tabela, id_valor, json.dumps(dados, ensure_ascii=False), categorias_json, anotacao, usuario, _agora()),
    )


def listar_registros(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        f'SELECT "ID", "TABELA", "REGISTRO_ID_ORIGINAL", "DADOS_JSON", "EXCLUIDO_POR", "EXCLUIDO_EM" '
        f"FROM {APP_LIXEIRA_REGISTROS} ORDER BY \"EXCLUIDO_EM\" DESC"
    )
    resultado = []
    for id_lixeira, tabela, registro_id, dados_json, excluido_por, excluido_em in cur.fetchall():
        try:
            dados = json.loads(dados_json)
        except (json.JSONDecodeError, TypeError):
            dados = {}
        resultado.append({
            "id_lixeira": id_lixeira,
            "tabela": tabela,
            "registro_id_original": registro_id,
            "rotulo": dados.get("NOME") or dados.get("EMPRESA") or dados.get("USUARIO") or f"ID {registro_id}",
            "excluido_por": excluido_por,
            "excluido_em": excluido_em,
        })
    return resultado


def restaurar_registro(conn: sqlite3.Connection, id_lixeira: int, usuario: str = "sistema") -> int:
    """Recria o registro na tabela original, com o MESMO ID de antes quando
    esse ID ainda estiver livre (senao, deixa o SQLite gerar um novo).
    Devolve o ID final do registro restaurado."""
    row = conn.execute(
        f'SELECT "TABELA", "REGISTRO_ID_ORIGINAL", "DADOS_JSON", "CATEGORIAS_JSON", "ANOTACAO_TEXTO" '
        f'FROM {APP_LIXEIRA_REGISTROS} WHERE "ID" = ?', (id_lixeira,)
    ).fetchone()
    if row is None:
        raise ValueError("Este item nao esta mais na lixeira.")
    tabela, registro_id_original, dados_json, categorias_json, anotacao = row
    dados = json.loads(dados_json)

    colunas_atuais = {c["nome"] for c in _colunas_fisicas(conn, tabela)}
    dados = {c: v for c, v in dados.items() if c in colunas_atuais}  # colunas removidas depois da exclusao nao voltam

    id_livre = conn.execute(
        f'SELECT 1 FROM {quote_ident(tabela)} WHERE "ID" = ?', (registro_id_original,)
    ).fetchone() is None
    if not id_livre:
        dados.pop("ID", None)

    colunas = list(dados.keys())
    campos_sql = ", ".join(quote_ident(c) for c in colunas)
    placeholders = ", ".join("?" for _ in colunas)
    try:
        cur = conn.execute(
            f"INSERT INTO {quote_ident(tabela)} ({campos_sql}) VALUES ({placeholders})",
            [dados[c] for c in colunas],
        )
    except sqlite3.IntegrityError as erro:
        raise ValueError(
            f'Nao foi possivel restaurar: {erro} -- restaure primeiro o registro relacionado (ex.: a empresa).'
        ) from erro
    novo_id = cur.lastrowid

    if categorias_json and tabela == PESSOAS:
        nomes = json.loads(categorias_json)
        ids_categoria = {
            nome_atual: id_categoria
            for id_categoria, nome_atual in conn.execute(f'SELECT "ID", "NOME" FROM {APP_CATEGORIAS}').fetchall()
        }
        for nome in nomes:
            id_categoria = ids_categoria.get(nome)
            if id_categoria is not None:
                conn.execute(
                    f'INSERT OR IGNORE INTO {APP_PESSOAS_CATEGORIAS} ("PESSOA_ID", "CATEGORIA_ID") VALUES (?, ?)',
                    (novo_id, id_categoria),
                )

    if anotacao:
        salvar_anotacao(conn, tabela, novo_id, anotacao)

    conn.execute(f'DELETE FROM {APP_LIXEIRA_REGISTROS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()
    log.log_change(conn, usuario, tabela, "Restaurar registro", f"ID {novo_id}")
    return novo_id


def excluir_definitivamente_registro(conn: sqlite3.Connection, id_lixeira: int) -> None:
    conn.execute(f'DELETE FROM {APP_LIXEIRA_REGISTROS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()


# ============================================================================
# TABELAS (uma tabela de dados inteira, com todas as linhas dela)
# ============================================================================

def capturar_tabela(conn: sqlite3.Connection, tabela: str, usuario: str) -> None:
    """Guarda uma copia de uma tabela inteira (estrutura + dados + os
    metadados que dependem dela) na lixeira. Chamado por
    db/tables.py::delete_data_sheet logo ANTES do DROP TABLE de verdade."""
    colunas_fisicas = _colunas_fisicas(conn, tabela)
    nomes_colunas = [c["nome"] for c in colunas_fisicas]

    linhas = conn.execute(f"SELECT * FROM {quote_ident(tabela)}").fetchall()
    dados = [dict(zip(nomes_colunas, linha)) for linha in linhas]

    ordem_colunas = [
        row[0] for row in conn.execute(
            f"SELECT coluna FROM {APP_COLUMN_ORDER} WHERE tabela = ? ORDER BY posicao", (tabela,)
        ).fetchall()
    ]
    tipos_campo = [
        {"coluna": coluna, "tipo": tipo, "opcoes": opcoes}
        for coluna, tipo, opcoes in conn.execute(
            f"SELECT coluna, tipo, opcoes FROM {APP_FIELD_TYPES} WHERE tabela = ?", (tabela,)
        ).fetchall()
    ]
    row_ordem_tabela = conn.execute(f"SELECT posicao FROM {APP_TABLE_ORDER} WHERE tabela = ?", (tabela,)).fetchone()
    row_rotulo = conn.execute(f"SELECT rotulo FROM {APP_TABLE_LABELS} WHERE tabela = ?", (tabela,)).fetchone()
    row_campos_resumo = conn.execute(
        f"SELECT campos_resumo FROM {APP_LIST_DISPLAY} WHERE tabela = ?", (tabela,)
    ).fetchone()

    anotacoes = [
        {"registro_id": registro_id, "texto": texto}
        for registro_id, texto in conn.execute(
            f"SELECT registro_id, texto FROM {APP_ANOTACOES} WHERE tabela = ?", (tabela,)
        ).fetchall()
    ]

    schema_completo = {
        "colunas": colunas_fisicas,
        "ordem_colunas": ordem_colunas,
        "tipos_campo": tipos_campo,
        "ordem_tabela": row_ordem_tabela[0] if row_ordem_tabela else None,
        "rotulo": row_rotulo[0] if row_rotulo else None,
        "campos_resumo": row_campos_resumo[0] if row_campos_resumo else None,
    }

    conn.execute(
        f"""INSERT INTO {APP_LIXEIRA_TABELAS}
            ("TABELA", "SCHEMA_JSON", "DADOS_JSON", "ANOTACOES_JSON", "EXCLUIDO_POR", "EXCLUIDO_EM")
            VALUES (?, ?, ?, ?, ?, ?)""",
        (
            tabela,
            json.dumps(schema_completo, ensure_ascii=False),
            json.dumps(dados, ensure_ascii=False),
            json.dumps(anotacoes, ensure_ascii=False),
            usuario,
            _agora(),
        ),
    )


def listar_tabelas(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        f'SELECT "ID", "TABELA", "DADOS_JSON", "EXCLUIDO_POR", "EXCLUIDO_EM" '
        f"FROM {APP_LIXEIRA_TABELAS} ORDER BY \"EXCLUIDO_EM\" DESC"
    )
    resultado = []
    for id_lixeira, tabela, dados_json, excluido_por, excluido_em in cur.fetchall():
        try:
            quantidade = len(json.loads(dados_json))
        except (json.JSONDecodeError, TypeError):
            quantidade = 0
        resultado.append({
            "id_lixeira": id_lixeira,
            "tabela": tabela,
            "quantidade_registros": quantidade,
            "excluido_por": excluido_por,
            "excluido_em": excluido_em,
        })
    return resultado


def _tabela_existe(conn: sqlite3.Connection, nome: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND LOWER(name) = LOWER(?)", (nome,)
    ).fetchone() is not None


def restaurar_tabela(conn: sqlite3.Connection, id_lixeira: int, usuario: str = "sistema") -> str:
    row = conn.execute(
        f'SELECT "TABELA", "SCHEMA_JSON", "DADOS_JSON", "ANOTACOES_JSON" '
        f'FROM {APP_LIXEIRA_TABELAS} WHERE "ID" = ?', (id_lixeira,)
    ).fetchone()
    if row is None:
        raise ValueError("Este item nao esta mais na lixeira.")
    tabela, schema_json, dados_json, anotacoes_json = row
    tabela = validar_identificador(tabela, "tabela")
    if _tabela_existe(conn, tabela):
        raise ValueError(f'Ja existe uma tabela chamada "{tabela}" -- renomeie ou exclua ela antes de restaurar.')

    schema_completo = json.loads(schema_json)
    dados = json.loads(dados_json)
    anotacoes = json.loads(anotacoes_json) if anotacoes_json else []

    definicoes = []
    for coluna in schema_completo["colunas"]:
        definicao = f'{quote_ident(coluna["nome"])} {coluna["tipo"]}'
        if coluna["pk"]:
            definicao += " PRIMARY KEY"
        definicoes.append(definicao)
    conn.execute(f'CREATE TABLE {quote_ident(tabela)} ({", ".join(definicoes)})')

    if dados:
        nomes_colunas = [c["nome"] for c in schema_completo["colunas"]]
        campos_sql = ", ".join(quote_ident(c) for c in nomes_colunas)
        placeholders = ", ".join("?" for _ in nomes_colunas)
        conn.executemany(
            f"INSERT INTO {quote_ident(tabela)} ({campos_sql}) VALUES ({placeholders})",
            [[linha.get(c) for c in nomes_colunas] for linha in dados],
        )

    if schema_completo.get("ordem_colunas"):
        conn.executemany(
            f"INSERT INTO {APP_COLUMN_ORDER} (tabela, coluna, posicao) VALUES (?, ?, ?)",
            [(tabela, coluna, i) for i, coluna in enumerate(schema_completo["ordem_colunas"])],
        )
    for item in schema_completo.get("tipos_campo") or []:
        conn.execute(
            f"""INSERT INTO {APP_FIELD_TYPES} (tabela, coluna, tipo, opcoes) VALUES (?, ?, ?, ?)
                ON CONFLICT(tabela, coluna) DO UPDATE SET tipo = excluded.tipo, opcoes = excluded.opcoes""",
            (tabela, item["coluna"], item["tipo"], item["opcoes"]),
        )
    if schema_completo.get("ordem_tabela") is not None:
        conn.execute(
            f"""INSERT INTO {APP_TABLE_ORDER} (tabela, posicao) VALUES (?, ?)
                ON CONFLICT(tabela) DO UPDATE SET posicao = excluded.posicao""",
            (tabela, schema_completo["ordem_tabela"]),
        )
    if schema_completo.get("rotulo"):
        conn.execute(
            f"""INSERT INTO {APP_TABLE_LABELS} (tabela, rotulo) VALUES (?, ?)
                ON CONFLICT(tabela) DO UPDATE SET rotulo = excluded.rotulo""",
            (tabela, schema_completo["rotulo"]),
        )
    if schema_completo.get("campos_resumo"):
        conn.execute(
            f"""INSERT INTO {APP_LIST_DISPLAY} (tabela, campos_resumo) VALUES (?, ?)
                ON CONFLICT(tabela) DO UPDATE SET campos_resumo = excluded.campos_resumo""",
            (tabela, schema_completo["campos_resumo"]),
        )
    for item in anotacoes:
        conn.execute(
            f"""INSERT INTO {APP_ANOTACOES} (tabela, registro_id, texto) VALUES (?, ?, ?)
                ON CONFLICT(tabela, registro_id) DO UPDATE SET texto = excluded.texto""",
            (tabela, item["registro_id"], item["texto"]),
        )

    conn.execute(f'DELETE FROM {APP_LIXEIRA_TABELAS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()
    log.log_change(conn, usuario, tabela, "Restaurar tabela")
    return tabela


def excluir_definitivamente_tabela(conn: sqlite3.Connection, id_lixeira: int) -> None:
    conn.execute(f'DELETE FROM {APP_LIXEIRA_TABELAS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()


# ============================================================================
# CAMPOS (uma coluna removida de uma tabela que continua existindo)
# ============================================================================

def capturar_campo(conn: sqlite3.Connection, tabela: str, coluna: str, usuario: str) -> None:
    """Guarda o tipo, a configuracao de campo e os valores (por registro) de
    UMA coluna que esta prestes a ser removida. Chamado por
    db/tables.py::drop_column logo ANTES do ALTER TABLE ... DROP COLUMN."""
    info_coluna = next((c for c in _colunas_fisicas(conn, tabela) if c["nome"] == coluna), None)
    if info_coluna is None:
        return

    valores = {
        str(id_valor): valor
        for id_valor, valor in conn.execute(
            f'SELECT "ID", {quote_ident(coluna)} FROM {quote_ident(tabela)}'
        ).fetchall()
        if valor not in (None, "")
    }

    row_tipo_campo = conn.execute(
        f"SELECT tipo, opcoes FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = ?", (tabela, coluna)
    ).fetchone()
    tipo_campo_json = json.dumps({"tipo": row_tipo_campo[0], "opcoes": row_tipo_campo[1]}) if row_tipo_campo else None

    row_ordem = conn.execute(
        "SELECT posicao FROM {} WHERE tabela = ? AND coluna = ?".format(APP_COLUMN_ORDER), (tabela, coluna)
    ).fetchone()

    conn.execute(
        f"""INSERT INTO {APP_LIXEIRA_CAMPOS}
            ("TABELA", "COLUNA", "TIPO_SQL_ORIGINAL", "TIPO_CAMPO_JSON", "ORDEM_ORIGINAL", "VALORES_JSON",
             "EXCLUIDO_POR", "EXCLUIDO_EM")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tabela,
            coluna,
            info_coluna["tipo"],
            tipo_campo_json,
            row_ordem[0] if row_ordem else None,
            json.dumps(valores, ensure_ascii=False),
            usuario,
            _agora(),
        ),
    )


def listar_campos(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        f'SELECT "ID", "TABELA", "COLUNA", "EXCLUIDO_POR", "EXCLUIDO_EM" '
        f"FROM {APP_LIXEIRA_CAMPOS} ORDER BY \"EXCLUIDO_EM\" DESC"
    )
    return [
        {"id_lixeira": id_lixeira, "tabela": tabela, "coluna": coluna, "excluido_por": excluido_por, "excluido_em": excluido_em}
        for id_lixeira, tabela, coluna, excluido_por, excluido_em in cur.fetchall()
    ]


def restaurar_campo(conn: sqlite3.Connection, id_lixeira: int, usuario: str = "sistema") -> None:
    row = conn.execute(
        f'SELECT "TABELA", "COLUNA", "TIPO_SQL_ORIGINAL", "TIPO_CAMPO_JSON", "ORDEM_ORIGINAL", "VALORES_JSON" '
        f'FROM {APP_LIXEIRA_CAMPOS} WHERE "ID" = ?', (id_lixeira,)
    ).fetchone()
    if row is None:
        raise ValueError("Este item nao esta mais na lixeira.")
    tabela, coluna, tipo_sql, tipo_campo_json, ordem, valores_json = row

    if not _tabela_existe(conn, tabela):
        raise ValueError(f'A tabela "{tabela}" nao existe mais -- restaure a tabela primeiro.')
    colunas_atuais = {c["nome"] for c in _colunas_fisicas(conn, tabela)}
    if coluna in colunas_atuais:
        raise ValueError(f'A tabela "{tabela}" ja tem um campo "{coluna}".')

    conn.execute(f"ALTER TABLE {quote_ident(tabela)} ADD COLUMN {quote_ident(coluna)} {tipo_sql}")

    valores = json.loads(valores_json)
    if valores:
        conn.executemany(
            f'UPDATE {quote_ident(tabela)} SET {quote_ident(coluna)} = ? WHERE "ID" = ?',
            [(valor, int(id_valor)) for id_valor, valor in valores.items()],
        )

    if tipo_campo_json:
        tipo_campo = json.loads(tipo_campo_json)
        conn.execute(
            f"""INSERT INTO {APP_FIELD_TYPES} (tabela, coluna, tipo, opcoes) VALUES (?, ?, ?, ?)
                ON CONFLICT(tabela, coluna) DO UPDATE SET tipo = excluded.tipo, opcoes = excluded.opcoes""",
            (tabela, coluna, tipo_campo["tipo"], tipo_campo["opcoes"]),
        )
    if ordem is not None:
        conn.execute(
            f"""INSERT INTO {APP_COLUMN_ORDER} (tabela, coluna, posicao) VALUES (?, ?, ?)
                ON CONFLICT(tabela, coluna) DO UPDATE SET posicao = excluded.posicao""",
            (tabela, coluna, ordem),
        )

    conn.execute(f'DELETE FROM {APP_LIXEIRA_CAMPOS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()
    log.log_change(conn, usuario, tabela, "Restaurar campo", coluna)


def excluir_definitivamente_campo(conn: sqlite3.Connection, id_lixeira: int) -> None:
    conn.execute(f'DELETE FROM {APP_LIXEIRA_CAMPOS} WHERE "ID" = ?', (id_lixeira,))
    conn.commit()
