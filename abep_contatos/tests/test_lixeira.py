import pytest

from db import anotacoes, categorias, lixeira, records
from db.schema import EMPRESAS, PESSOAS
from db.tables import add_column, create_data_sheet, delete_data_sheet, drop_column, get_column_order, get_schema, set_column_order


# ============================================================================
# registros
# ============================================================================

def test_excluir_registro_vai_para_lixeira_e_restaura_com_mesmo_id(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "EMAIL": "fulano@x.com"})

    records.delete_record(conn, PESSOAS, id_pessoa, usuario="admin")

    assert records.get_record(conn, PESSOAS, id_pessoa) is None
    itens = lixeira.listar_registros(conn)
    assert len(itens) == 1
    assert itens[0]["tabela"] == PESSOAS
    assert itens[0]["rotulo"] == "Fulano"
    assert itens[0]["excluido_por"] == "admin"

    novo_id = lixeira.restaurar_registro(conn, itens[0]["id_lixeira"], usuario="admin")
    assert novo_id == id_pessoa  # ID original ainda estava livre
    restaurado = records.get_record(conn, PESSOAS, novo_id)
    assert restaurado["NOME"] == "Fulano"
    assert restaurado["EMAIL"] == "fulano@x.com"
    assert lixeira.listar_registros(conn) == []


def test_restaurar_registro_com_id_ocupado_ganha_novo_id(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Original"})
    records.delete_record(conn, PESSOAS, id_pessoa)

    # Alguem cria outro registro que por acaso reocupa o mesmo ID.
    conn.execute('INSERT INTO "PESSOAS" ("ID", "ID_EMPRESA", "NOME") VALUES (?, ?, ?)', (id_pessoa, id_empresa, "Outro"))
    conn.commit()

    item = lixeira.listar_registros(conn)[0]
    novo_id = lixeira.restaurar_registro(conn, item["id_lixeira"])
    assert novo_id != id_pessoa
    assert records.get_record(conn, PESSOAS, novo_id)["NOME"] == "Original"
    assert records.get_record(conn, PESSOAS, id_pessoa)["NOME"] == "Outro"  # o outro continua intacto


def test_excluir_registro_preserva_categorias_e_anotacao_ao_restaurar(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})
    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Diretores Técnicos"])
    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "Prefere WhatsApp.")

    records.delete_record(conn, PESSOAS, id_pessoa)
    # A exclusao em cascata (ON DELETE CASCADE) ja deve ter limpo o vinculo de categoria.
    assert categorias.categorias_da_pessoa(conn, id_pessoa) == []

    item = lixeira.listar_registros(conn)[0]
    novo_id = lixeira.restaurar_registro(conn, item["id_lixeira"])

    assert set(categorias.categorias_da_pessoa(conn, novo_id)) == {"Presidentes", "Diretores Técnicos"}
    assert anotacoes.obter_anotacao(conn, PESSOAS, novo_id) == "Prefere WhatsApp."


def test_restaurar_registro_com_empresa_ja_excluida_da_erro_amigavel(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})
    records.delete_record(conn, PESSOAS, id_pessoa)

    # A empresa some de vez (nao so vai pra lixeira) -- simula o cenario onde
    # a FK vai falhar ao tentar restaurar a pessoa.
    conn.execute('DELETE FROM "EMPRESAS" WHERE "ID" = ?', (id_empresa,))
    conn.commit()

    item = lixeira.listar_registros(conn)[0]
    with pytest.raises(ValueError):
        lixeira.restaurar_registro(conn, item["id_lixeira"])
    # Continua na lixeira -- a tentativa que falhou nao pode ter perdido a foto.
    assert len(lixeira.listar_registros(conn)) == 1


def test_excluir_definitivamente_registro_remove_da_lixeira_sem_restaurar(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    records.delete_record(conn, PESSOAS, id_pessoa)
    item = lixeira.listar_registros(conn)[0]

    lixeira.excluir_definitivamente_registro(conn, item["id_lixeira"])
    assert lixeira.listar_registros(conn) == []
    assert records.get_records(conn, PESSOAS) == []


# ============================================================================
# tabelas
# ============================================================================

def test_excluir_tabela_vai_para_lixeira_e_restaura_estrutura_e_dados(conn):
    create_data_sheet(conn, "FORNECEDORES")
    add_column(conn, "FORNECEDORES", "NOME", "TEXT")
    add_column(conn, "FORNECEDORES", "TELEFONE", "TEXT")
    set_column_order(conn, "FORNECEDORES", ["NOME", "TELEFONE", "ID"])
    id_1 = records.create_record(conn, "FORNECEDORES", {"NOME": "Fornecedor 1", "TELEFONE": "111"})
    id_2 = records.create_record(conn, "FORNECEDORES", {"NOME": "Fornecedor 2", "TELEFONE": "222"})
    anotacoes.salvar_anotacao(conn, "FORNECEDORES", id_1, "Atrasa entrega")

    # Precisa de outra tabela de dados pra "FORNECEDORES" nao ser a ultima.
    create_data_sheet(conn, "OUTRA")
    delete_data_sheet(conn, "FORNECEDORES", usuario="admin")

    assert "FORNECEDORES" not in [
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    ]
    itens = lixeira.listar_tabelas(conn)
    assert len(itens) == 1
    assert itens[0]["tabela"] == "FORNECEDORES"
    assert itens[0]["quantidade_registros"] == 2

    lixeira.restaurar_tabela(conn, itens[0]["id_lixeira"], usuario="admin")

    assert get_schema(conn, "FORNECEDORES") == ["ID", "NOME", "TELEFONE"]
    assert get_column_order(conn, "FORNECEDORES") == ["NOME", "TELEFONE", "ID"]
    registros = records.get_records(conn, "FORNECEDORES")
    assert {r["NOME"] for r in registros} == {"Fornecedor 1", "Fornecedor 2"}
    assert anotacoes.obter_anotacao(conn, "FORNECEDORES", id_1) == "Atrasa entrega"
    assert lixeira.listar_tabelas(conn) == []


def test_restaurar_tabela_falha_se_ja_existe_tabela_com_esse_nome(conn):
    create_data_sheet(conn, "FORNECEDORES")
    create_data_sheet(conn, "OUTRA")
    delete_data_sheet(conn, "FORNECEDORES")
    item = lixeira.listar_tabelas(conn)[0]

    create_data_sheet(conn, "FORNECEDORES")  # alguem recria com o mesmo nome antes de restaurar
    with pytest.raises(ValueError):
        lixeira.restaurar_tabela(conn, item["id_lixeira"])
    assert len(lixeira.listar_tabelas(conn)) == 1  # continua na lixeira


def test_excluir_definitivamente_tabela_remove_da_lixeira(conn):
    create_data_sheet(conn, "FORNECEDORES")
    create_data_sheet(conn, "OUTRA")
    delete_data_sheet(conn, "FORNECEDORES")
    item = lixeira.listar_tabelas(conn)[0]

    lixeira.excluir_definitivamente_tabela(conn, item["id_lixeira"])
    assert lixeira.listar_tabelas(conn) == []


# ============================================================================
# campos
# ============================================================================

def test_remover_campo_vai_para_lixeira_e_restaura_com_valores(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_1 = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Ana", "CARGO2": "Vice-presidente"})
    id_2 = records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Bruno"})  # sem CARGO2

    drop_column(conn, PESSOAS, "CARGO2", usuario="admin")
    assert "CARGO2" not in get_schema(conn, PESSOAS)

    itens = lixeira.listar_campos(conn)
    assert len(itens) == 1
    assert itens[0]["tabela"] == PESSOAS
    assert itens[0]["coluna"] == "CARGO2"

    lixeira.restaurar_campo(conn, itens[0]["id_lixeira"], usuario="admin")
    assert "CARGO2" in get_schema(conn, PESSOAS)
    assert records.get_record(conn, PESSOAS, id_1)["CARGO2"] == "Vice-presidente"
    assert not records.get_record(conn, PESSOAS, id_2).get("CARGO2")
    assert lixeira.listar_campos(conn) == []


def test_remover_campo_preserva_tipo_configurado_ao_restaurar(conn):
    from ui import field_types

    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    field_types.definir_tipo_campo(conn, PESSOAS, "CARGO2", field_types.SELECAO, ["A", "B"])

    drop_column(conn, PESSOAS, "CARGO2")
    item = lixeira.listar_campos(conn)[0]
    lixeira.restaurar_campo(conn, item["id_lixeira"])

    tipo, opcoes = field_types.tipo_do_campo(conn, PESSOAS, "CARGO2")
    assert tipo == field_types.SELECAO
    assert opcoes == ["A", "B"]


def test_restaurar_campo_falha_se_coluna_ja_existe(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CARGO2": "Diretor"})
    drop_column(conn, PESSOAS, "CARGO2")
    item = lixeira.listar_campos(conn)[0]

    add_column(conn, PESSOAS, "CARGO2", "TEXT")  # alguem recria o campo antes de restaurar
    with pytest.raises(ValueError):
        lixeira.restaurar_campo(conn, item["id_lixeira"])
    assert len(lixeira.listar_campos(conn)) == 1


def test_excluir_definitivamente_campo_remove_da_lixeira(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CARGO2": "Diretor"})
    drop_column(conn, PESSOAS, "CARGO2")
    item = lixeira.listar_campos(conn)[0]

    lixeira.excluir_definitivamente_campo(conn, item["id_lixeira"])
    assert lixeira.listar_campos(conn) == []
