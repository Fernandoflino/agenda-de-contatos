import pytest

from db import auth, records


def _criar_empresa(conn, sigla="ABC", empresa="Empresa ABC"):
    return records.create_record(conn, "EMPRESAS", {"SIGLA": sigla, "EMPRESA": empresa})


def test_create_gera_id_sequencial(conn):
    id1 = records.create_record(conn, "EMPRESAS", {"SIGLA": "A"})
    id2 = records.create_record(conn, "EMPRESAS", {"SIGLA": "B"})
    assert id2 == id1 + 1


def test_get_records_resolve_empresa(conn):
    id_empresa = _criar_empresa(conn)
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_empresa, "CARGO": "Presidente", "NOME": "Fulano"})

    pessoas = records.get_records(conn, "PESSOAS")
    assert len(pessoas) == 1
    assert pessoas[0]["_EMPRESA_SIGLA"] == "ABC"
    assert pessoas[0]["_EMPRESA_NOME"] == "Empresa ABC"


def test_update_e_delete_por_id(conn):
    id_empresa = _criar_empresa(conn)
    id_pessoa = records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})

    records.update_record(conn, "PESSOAS", id_pessoa, {"NOME": "Fulano Editado"})
    assert records.get_record(conn, "PESSOAS", id_pessoa)["NOME"] == "Fulano Editado"

    records.delete_record(conn, "PESSOAS", id_pessoa)
    assert records.get_record(conn, "PESSOAS", id_pessoa) is None


def test_update_id_inexistente_leva_erro(conn):
    with pytest.raises(ValueError):
        records.update_record(conn, "PESSOAS", 9999, {"NOME": "X"})


def test_usuarios_nunca_expoe_senha_hash(conn):
    records.create_record(conn, "USUARIOS", {"USUARIO": "admin", "SENHA": "segredo123", "NOME": "Administrador"})
    usuarios = records.get_records(conn, "USUARIOS")
    assert len(usuarios) == 1
    assert "SENHA_HASH" not in usuarios[0]
    assert "SENHA" not in usuarios[0]


def test_usuarios_login_funciona_apos_create_record(conn):
    records.create_record(conn, "USUARIOS", {"USUARIO": "admin", "SENHA": "segredo123", "NOME": "Administrador"})
    usuario_logado = auth.login(conn, "admin", "segredo123")
    assert usuario_logado.usuario == "admin"

    with pytest.raises(auth.ErroLogin):
        auth.login(conn, "admin", "senha-errada")


def test_filtrar_registros_busca_livre_e_por_campo():
    registros = [
        {"NOME": "Ana", "CARGO": "Presidente", "_EMPRESA_SIGLA": "ABC"},
        {"NOME": "Bruno", "CARGO": "Diretor Técnico", "_EMPRESA_SIGLA": "XYZ"},
    ]
    assert len(records.filtrar_registros(registros, busca="ana")) == 1
    assert len(records.filtrar_registros(registros, campo="CARGO", valor="Diretor")) == 1
    assert len(records.filtrar_registros(registros, busca="bruno", campo="CARGO", valor="Presidente")) == 0
