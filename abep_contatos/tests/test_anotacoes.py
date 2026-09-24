from db import anotacoes, records
from db.schema import EMPRESAS, PESSOAS


def test_anotacao_comeca_vazia(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    assert anotacoes.obter_anotacao(conn, PESSOAS, id_pessoa) == ""


def test_salvar_e_ler_anotacao(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "Prefere contato por WhatsApp.")
    assert anotacoes.obter_anotacao(conn, PESSOAS, id_pessoa) == "Prefere contato por WhatsApp."

    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "Texto atualizado.")
    assert anotacoes.obter_anotacao(conn, PESSOAS, id_pessoa) == "Texto atualizado."


def test_salvar_anotacao_vazia_remove_registro(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "Alguma coisa.")
    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "   ")
    assert anotacoes.obter_anotacao(conn, PESSOAS, id_pessoa) == ""


def test_anotacoes_sao_independentes_por_tabela_e_registro(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    anotacoes.salvar_anotacao(conn, EMPRESAS, id_empresa, "Nota da empresa")
    anotacoes.salvar_anotacao(conn, PESSOAS, id_pessoa, "Nota da pessoa")

    assert anotacoes.obter_anotacao(conn, EMPRESAS, id_empresa) == "Nota da empresa"
    assert anotacoes.obter_anotacao(conn, PESSOAS, id_pessoa) == "Nota da pessoa"
