from db import records
from db.schema import EMPRESAS, PESSOAS
from db import log as log_mod


def test_historico_do_registro_pega_criar_editar_e_excluir(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    records.update_record(conn, PESSOAS, id_pessoa, {"NOME": "Fulano Editado"})

    historico = log_mod.historico_do_registro(conn, PESSOAS, id_pessoa)
    acoes = [item["acao"] for item in historico]
    assert "Criar registro" in acoes
    assert "Editar registro" in acoes

    records.delete_record(conn, PESSOAS, id_pessoa)
    historico_apos_excluir = log_mod.historico_do_registro(conn, PESSOAS, id_pessoa)
    assert "Excluir registro" in [item["acao"] for item in historico_apos_excluir]


def test_historico_do_registro_nao_confunde_ids_parecidos(conn):
    """ID 1 nao pode aparecer no historico do ID 12 (e vice-versa) so porque
    "1" e um pedaco de "12" -- por isso a checagem usa borda de palavra."""
    id_1 = records.create_record(conn, PESSOAS, {"NOME": "Pessoa Um"})
    for _ in range(10):
        records.create_record(conn, PESSOAS, {"NOME": "Enchendo IDs"})
    id_12 = records.create_record(conn, PESSOAS, {"NOME": "Pessoa Doze"})
    assert id_1 == 1
    assert id_12 == 12

    historico_1 = log_mod.historico_do_registro(conn, PESSOAS, id_1)
    assert all("Pessoa Doze" not in (item["detalhes"] or "") for item in historico_1)


def test_historico_do_registro_so_da_tabela_certa(conn):
    id_empresa = records.create_record(conn, EMPRESAS, {"SIGLA": "ABC"})
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})

    historico_empresa = log_mod.historico_do_registro(conn, EMPRESAS, id_empresa)
    assert all(item["tabela"] == EMPRESAS for item in historico_empresa)
    assert len(historico_empresa) >= 1

    historico_pessoa = log_mod.historico_do_registro(conn, PESSOAS, id_pessoa)
    assert all(item["tabela"] == PESSOAS for item in historico_pessoa)
