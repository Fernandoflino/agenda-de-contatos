import pytest

from db import tables


def test_list_data_sheets_filtra_internas(conn):
    nomes = tables.list_data_sheets(conn)
    assert "EMPRESAS" in nomes
    assert "PESSOAS" in nomes
    assert "USUARIOS" in nomes
    assert "app_metadata" not in nomes
    assert "app_log" not in nomes


def test_create_rename_delete_data_sheet(conn):
    tables.create_data_sheet(conn, "CONTATOS EXTRAS")
    assert "CONTATOS EXTRAS" in tables.list_data_sheets(conn)

    tables.rename_data_sheet(conn, "CONTATOS EXTRAS", "FORNECEDORES")
    nomes = tables.list_data_sheets(conn)
    assert "FORNECEDORES" in nomes
    assert "CONTATOS EXTRAS" not in nomes

    tables.delete_data_sheet(conn, "FORNECEDORES")
    assert "FORNECEDORES" not in tables.list_data_sheets(conn)


def test_create_data_sheet_nome_duplicado(conn):
    with pytest.raises(ValueError):
        tables.create_data_sheet(conn, "EMPRESAS")


def test_create_data_sheet_copiando_estrutura(conn):
    tables.add_column(conn, "EMPRESAS", "OBSERVACAO")
    tables.create_data_sheet(conn, "EMPRESAS_BACKUP", copiar_de="EMPRESAS")
    assert tables.get_schema(conn, "EMPRESAS_BACKUP") == tables.get_schema(conn, "EMPRESAS")


def test_nao_deleta_ultima_tabela(conn):
    # So sobra 1 tabela de dados se ela nao for uma das 3 protegidas --
    # cria uma tabela extra pra testar essa regra sem esbarrar na protecao.
    tables.create_data_sheet(conn, "UNICA_EXTRA")
    for nome in tables.list_data_sheets(conn):
        if nome not in ("UNICA_EXTRA", "EMPRESAS", "PESSOAS", "USUARIOS"):
            tables.delete_data_sheet(conn, nome)
    for nome in ("EMPRESAS", "PESSOAS", "USUARIOS"):
        with pytest.raises(ValueError):
            tables.delete_data_sheet(conn, nome)


def test_tabelas_essenciais_nao_podem_ser_renomeadas_ou_excluidas(conn):
    """EMPRESAS, PESSOAS e USUARIOS sao usadas pelo nome exato em varias
    partes do programa (login, resolucao de empresa, a tela de Contatos) --
    renomear ou excluir uma delas pela tela de "Gerenciar tabelas" quebraria
    o programa de um jeito que a interface nao consegue explicar direito."""
    for nome in ("EMPRESAS", "PESSOAS", "USUARIOS"):
        with pytest.raises(ValueError):
            tables.rename_data_sheet(conn, nome, "OUTRO_NOME")
        with pytest.raises(ValueError):
            tables.delete_data_sheet(conn, nome)


def test_renomear_so_a_caixa_de_uma_tabela_funciona(conn):
    """Corrigir soh a capitalizacao de um nome (ex.: 'Fornecedores' ->
    'FORNECEDORES') precisa funcionar, mesmo o SQLite tratando os dois nomes
    como 'o mesmo' -- foi um bug real: renomear uma tabela pra ela mesma com
    outra caixa dava erro de 'nome duplicado'."""
    tables.create_data_sheet(conn, "Fornecedores")
    tables.rename_data_sheet(conn, "Fornecedores", "FORNECEDORES")
    assert "FORNECEDORES" in tables.list_data_sheets(conn)


def test_add_rename_drop_column(conn):
    tables.add_column(conn, "PESSOAS", "LINKEDIN")
    assert "LINKEDIN" in tables.get_schema(conn, "PESSOAS")

    tables.rename_column(conn, "PESSOAS", "LINKEDIN", "LINKEDIN_URL")
    schema_atual = tables.get_schema(conn, "PESSOAS")
    assert "LINKEDIN_URL" in schema_atual
    assert "LINKEDIN" not in schema_atual

    tables.drop_column(conn, "PESSOAS", "LINKEDIN_URL")
    assert "LINKEDIN_URL" not in tables.get_schema(conn, "PESSOAS")


def test_nao_remove_coluna_id(conn):
    with pytest.raises(ValueError):
        tables.drop_column(conn, "PESSOAS", "ID")


def test_column_order_configuravel(conn):
    schema_fisico = tables.get_schema(conn, "PESSOAS")
    ordem_custom = list(reversed(schema_fisico))
    tables.set_column_order(conn, "PESSOAS", ordem_custom)
    assert tables.get_column_order(conn, "PESSOAS") == ordem_custom

    # coluna nova sem posicao configurada cai no final
    tables.add_column(conn, "PESSOAS", "NOVO_CAMPO")
    ordem = tables.get_column_order(conn, "PESSOAS")
    assert ordem[-1] == "NOVO_CAMPO"
