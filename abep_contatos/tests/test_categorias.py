import pytest

from db import categorias, records
from db.schema import PESSOAS


def test_lista_vazia_quando_nao_ha_categorias(conn):
    assert categorias.listar_categorias(conn) == []


def test_adicionar_categoria_nova(conn):
    categorias.adicionar_categoria(conn, "Presidentes", usuario="maria")
    categorias.adicionar_categoria(conn, "Diretores Técnicos", usuario="maria")

    assert categorias.listar_categorias(conn) == ["Presidentes", "Diretores Técnicos"]


def test_mover_categoria_sobe_e_desce(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    categorias.adicionar_categoria(conn, "Diretores Adm. Financeiros")

    categorias.mover_categoria(conn, "Diretores Adm. Financeiros", -1)
    assert categorias.listar_categorias(conn) == [
        "Presidentes", "Diretores Adm. Financeiros", "Diretores Técnicos",
    ]

    categorias.mover_categoria(conn, "Diretores Adm. Financeiros", -1)
    assert categorias.listar_categorias(conn) == [
        "Diretores Adm. Financeiros", "Presidentes", "Diretores Técnicos",
    ]

    categorias.mover_categoria(conn, "Diretores Adm. Financeiros", 1)
    assert categorias.listar_categorias(conn) == [
        "Presidentes", "Diretores Adm. Financeiros", "Diretores Técnicos",
    ]


def test_mover_categoria_na_ponta_nao_faz_nada(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")

    categorias.mover_categoria(conn, "Presidentes", -1)  # ja e a primeira
    assert categorias.listar_categorias(conn) == ["Presidentes", "Diretores Técnicos"]

    categorias.mover_categoria(conn, "Diretores Técnicos", 1)  # ja e a ultima
    assert categorias.listar_categorias(conn) == ["Presidentes", "Diretores Técnicos"]


def test_mover_categoria_inexistente_nao_faz_nada(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.mover_categoria(conn, "Não Existe", -1)
    assert categorias.listar_categorias(conn) == ["Presidentes"]


def test_adicionar_categoria_duplicada_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    with pytest.raises(ValueError):
        categorias.adicionar_categoria(conn, "presidentes")  # sem diferenciar maiusculas/minusculas


def test_adicionar_categoria_vazia_da_erro(conn):
    with pytest.raises(ValueError):
        categorias.adicionar_categoria(conn, "   ")


def test_definir_categorias_da_pessoa_aceita_varias_ao_mesmo_tempo(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})

    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Diretores Técnicos"])

    assert categorias.categorias_da_pessoa(conn, id_pessoa) == ["Presidentes", "Diretores Técnicos"]
    registro = records.get_record(conn, PESSOAS, id_pessoa)
    assert registro["CATEGORIAS"] == ["Presidentes", "Diretores Técnicos"]
    assert registro["CATEGORIA"] == "Presidentes, Diretores Técnicos"


def test_definir_categorias_da_pessoa_substitui_vinculos_antigos(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Diretores Técnicos"])

    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Diretores Técnicos"])

    assert categorias.categorias_da_pessoa(conn, id_pessoa) == ["Diretores Técnicos"]


def test_definir_categorias_da_pessoa_com_lista_vazia_remove_tudo(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes"])

    categorias.definir_categorias_da_pessoa(conn, id_pessoa, [])

    assert categorias.categorias_da_pessoa(conn, id_pessoa) == []


def test_definir_categorias_da_pessoa_ignora_nome_que_nao_existe_mais(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})

    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Categoria Excluída"])

    assert categorias.categorias_da_pessoa(conn, id_pessoa) == ["Presidentes"]


def test_renomear_categoria_nao_precisa_mexer_nos_vinculos(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id1 = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    id2 = records.create_record(conn, PESSOAS, {"NOME": "Ciclana"})
    categorias.definir_categorias_da_pessoa(conn, id1, ["Presidentes"])
    categorias.definir_categorias_da_pessoa(conn, id2, ["Presidentes", "Diretores Técnicos"])

    categorias.renomear_categoria(conn, "Presidentes", "Presidência", usuario="maria")

    assert "Presidência" in categorias.listar_categorias(conn)
    assert "Presidentes" not in categorias.listar_categorias(conn)
    assert categorias.categorias_da_pessoa(conn, id1) == ["Presidência"]
    assert categorias.categorias_da_pessoa(conn, id2) == ["Presidência", "Diretores Técnicos"]


def test_renomear_categoria_inexistente_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    with pytest.raises(ValueError):
        categorias.renomear_categoria(conn, "Não Existe", "Novo Nome")


def test_renomear_para_nome_ja_usado_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    with pytest.raises(ValueError):
        categorias.renomear_categoria(conn, "Presidentes", "Diretores Técnicos")


def test_excluir_categoria_remove_so_essa_etiqueta_sem_apagar_o_contato(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Diretores Técnicos"])

    afetados = categorias.excluir_categoria(conn, "Presidentes", usuario="maria")

    assert afetados == 1
    assert "Presidentes" not in categorias.listar_categorias(conn)
    registro = records.get_record(conn, PESSOAS, id_pessoa)
    assert registro["CATEGORIAS"] == ["Diretores Técnicos"]  # a outra categoria continua
    assert registro["NOME"] == "Fulano"  # o contato continua existindo


def test_contar_uso(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    id1 = records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    id2 = records.create_record(conn, PESSOAS, {"NOME": "Ciclana"})
    records.create_record(conn, PESSOAS, {"NOME": "Outro"})
    categorias.definir_categorias_da_pessoa(conn, id1, ["Presidentes"])
    categorias.definir_categorias_da_pessoa(conn, id2, ["Presidentes"])

    assert categorias.contar_uso(conn, "Presidentes") == 2
    assert categorias.contar_uso(conn, "Diretores Técnicos") == 0
