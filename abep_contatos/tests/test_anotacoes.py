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


def test_ids_com_anotacao_devolve_so_quem_tem_texto_de_verdade(conn):
    id_a = records.create_record(conn, PESSOAS, {"NOME": "Com anotação"})
    id_b = records.create_record(conn, PESSOAS, {"NOME": "Sem anotação"})
    id_c = records.create_record(conn, PESSOAS, {"NOME": "Anotação removida depois"})
    anotacoes.salvar_anotacao(conn, PESSOAS, id_a, "Prefere WhatsApp.")
    anotacoes.salvar_anotacao(conn, PESSOAS, id_c, "Algo")
    anotacoes.salvar_anotacao(conn, PESSOAS, id_c, "   ")  # esvaziar remove o registro

    resultado = anotacoes.ids_com_anotacao(conn, PESSOAS, [id_a, id_b, id_c])
    assert resultado == {id_a}


def test_ids_com_anotacao_lista_vazia_nao_consulta_o_banco(conn):
    assert anotacoes.ids_com_anotacao(conn, PESSOAS, []) == set()


def test_ids_com_anotacao_ignora_registros_de_outra_tabela(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    anotacoes.salvar_anotacao(conn, EMPRESAS, id_empresa, "Nota da empresa")

    # Mesmo se o ID numerico coincidir, so deve valer pra tabela pedida.
    assert anotacoes.ids_com_anotacao(conn, PESSOAS, [id_pessoa, id_empresa]) == set()
