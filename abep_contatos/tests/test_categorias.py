import pytest

from db import categorias, records
from db.schema import PESSOAS


def test_lista_vazia_quando_nao_ha_dados_nem_configuracao(conn):
    assert categorias.listar_categorias(conn) == []


def test_lista_e_semeada_pelos_valores_ja_usados_nos_contatos(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CATEGORIA": "Presidentes"})
    records.create_record(conn, PESSOAS, {"NOME": "Ciclana", "CATEGORIA": "Diretores Técnicos"})

    assert categorias.listar_categorias(conn) == ["Diretores Técnicos", "Presidentes"]


def test_adicionar_categoria_nova(conn):
    categorias.adicionar_categoria(conn, "Presidentes", usuario="maria")
    categorias.adicionar_categoria(conn, "Diretores Técnicos", usuario="maria")

    assert categorias.listar_categorias(conn) == ["Presidentes", "Diretores Técnicos"]


def test_adicionar_categoria_duplicada_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    with pytest.raises(ValueError):
        categorias.adicionar_categoria(conn, "presidentes")  # sem diferenciar maiusculas/minusculas


def test_adicionar_categoria_vazia_da_erro(conn):
    with pytest.raises(ValueError):
        categorias.adicionar_categoria(conn, "   ")


def test_renomear_categoria_atualiza_lista_e_contatos_existentes(conn):
    id1 = records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CATEGORIA": "Presidentes"})
    id2 = records.create_record(conn, PESSOAS, {"NOME": "Ciclana", "CATEGORIA": "Presidentes"})
    records.create_record(conn, PESSOAS, {"NOME": "Outro", "CATEGORIA": "Diretores Técnicos"})

    afetados = categorias.renomear_categoria(conn, "Presidentes", "Presidência", usuario="maria")

    assert afetados == 2
    assert "Presidência" in categorias.listar_categorias(conn)
    assert "Presidentes" not in categorias.listar_categorias(conn)
    assert records.get_record(conn, PESSOAS, id1)["CATEGORIA"] == "Presidência"
    assert records.get_record(conn, PESSOAS, id2)["CATEGORIA"] == "Presidência"


def test_renomear_categoria_inexistente_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    with pytest.raises(ValueError):
        categorias.renomear_categoria(conn, "Não Existe", "Novo Nome")


def test_renomear_para_nome_ja_usado_da_erro(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Técnicos")
    with pytest.raises(ValueError):
        categorias.renomear_categoria(conn, "Presidentes", "Diretores Técnicos")


def test_excluir_categoria_limpa_campo_dos_contatos_sem_apagar_o_contato(conn):
    id_pessoa = records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CATEGORIA": "Presidentes"})

    # "Presidentes" ainda nao foi configurada explicitamente -- listar_categorias()
    # a encontra pelo fallback (valor ja usado por um contato de verdade).
    afetados = categorias.excluir_categoria(conn, "Presidentes", usuario="maria")

    assert afetados == 1
    assert "Presidentes" not in categorias.listar_categorias(conn)
    registro = records.get_record(conn, PESSOAS, id_pessoa)
    assert registro["CATEGORIA"] is None
    assert registro["NOME"] == "Fulano"  # o contato continua existindo


def test_contar_uso(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Fulano", "CATEGORIA": "Presidentes"})
    records.create_record(conn, PESSOAS, {"NOME": "Ciclana", "CATEGORIA": "Presidentes"})
    records.create_record(conn, PESSOAS, {"NOME": "Outro", "CATEGORIA": "Diretores Técnicos"})

    assert categorias.contar_uso(conn, "Presidentes") == 2
    assert categorias.contar_uso(conn, "Diretores Técnicos") == 1
    assert categorias.contar_uso(conn, "Não Usada") == 0
