import pytest

from db.identifiers import quote_ident, validar_identificador


def test_aceita_acentos_e_espacos():
    assert validar_identificador("DIRETORES TÉCNICOS") == "DIRETORES TÉCNICOS"


def test_rejeita_vazio():
    with pytest.raises(ValueError):
        validar_identificador("   ")


def test_rejeita_prefixo_reservado():
    with pytest.raises(ValueError):
        validar_identificador("app_hackeado")


def test_rejeita_muito_longo():
    with pytest.raises(ValueError):
        validar_identificador("x" * 100)


def test_rejeita_byte_nulo():
    with pytest.raises(ValueError):
        validar_identificador("nome\x00malicioso")


def test_quote_ident_escapa_aspas():
    assert quote_ident('nome "com" aspas') == '"nome ""com"" aspas"'


def test_quote_ident_tentativa_injecao():
    # o valor entre aspas eh so um identificador de uma coluna/tabela --
    # mesmo contendo SQL, fica encapsulado como um unico nome quotado.
    malicioso = 'x"; DROP TABLE USUARIOS; --'
    resultado = quote_ident(malicioso)
    assert resultado == '"x""; DROP TABLE USUARIOS; --"'
