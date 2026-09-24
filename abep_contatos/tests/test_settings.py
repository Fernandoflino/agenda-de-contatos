from db import settings


def _campos_planos(layout: list[list[str]]) -> list[str]:
    """Achata uma lista de linhas numa lista de campos so, na ordem em que
    aparecem -- util pra testar 'contem X' sem se importar em qual linha."""
    return [campo for linha in layout for campo in linha]


def test_sugerir_layout_resumo_prioriza_nome_e_ignora_secundarios():
    colunas = ["ID", "ID_EMPRESA", "CARGO", "NOME", "EMAIL", "CPF", "DATA DE NASCIMENTO", "CP1"]
    layout = settings.sugerir_layout_resumo(colunas)
    campos = _campos_planos(layout)
    assert "ID" not in campos
    assert "CPF" not in campos
    assert "CP1" not in campos
    # 1a linha e a empresa (ID_EMPRESA presente); 2a linha e o campo-titulo.
    assert layout[0] == ["_EMPRESA_SIGLA", "_EMPRESA_SIGLA_EMPRESA", "_EMPRESA_NOME"]
    assert layout[1] == ["NOME"]
    assert "CARGO" in campos
    assert "EMAIL" in campos


def test_sugerir_layout_resumo_sem_empresa_nao_tem_linha_de_empresa():
    colunas = ["ID", "NOME", "EMAIL"]
    layout = settings.sugerir_layout_resumo(colunas)
    campos = _campos_planos(layout)
    assert "_EMPRESA_SIGLA" not in campos
    assert layout[0] == ["NOME"]


def test_sugerir_layout_resumo_ignora_id_empresa_bruto_e_inclui_categoria():
    """ID_EMPRESA (o numero interno) nunca deve aparecer como campo do
    cartao -- vira os 3 campos de empresa (UF/sigla/nome) na sua propria
    linha. CATEGORIA deve ser considerada, logo depois de NOME."""
    colunas = ["ID", "ID_EMPRESA", "CATEGORIA", "CARGO", "NOME"]
    layout = settings.sugerir_layout_resumo(colunas)
    campos = _campos_planos(layout)
    assert "ID_EMPRESA" not in campos
    assert "CATEGORIA" in campos
    assert campos.index("CATEGORIA") < campos.index("CARGO")


def test_branding_padrao_quando_nao_configurado(conn):
    b = settings.obter_branding(conn)
    assert b.nome == settings.NOME_PADRAO
    assert b.logo is None


def test_salvar_branding_atualiza_so_o_informado(conn):
    settings.salvar_branding(conn, nome="ABEP-TIC", cor_destaque="#ff0000")
    settings.salvar_branding(conn, nome="Painel ABEP")
    b = settings.obter_branding(conn)
    assert b.nome == "Painel ABEP"
    assert b.cor_destaque == "#ff0000"


def test_campos_resumo_configuravel_com_varias_linhas(conn):
    padrao = [["NOME"], ["EMAIL"]]
    assert settings.obter_campos_resumo(conn, "PESSOAS", padrao) == padrao

    layout_novo = [["NOME"], ["CARGO", "WHATSAPP"], ["EMAIL"]]
    settings.salvar_campos_resumo(conn, "PESSOAS", layout_novo)
    assert settings.obter_campos_resumo(conn, "PESSOAS", padrao) == layout_novo


def test_campos_resumo_converte_formato_antigo_automaticamente(conn):
    """Bancos salvos por uma versao anterior do programa guardavam uma lista
    simples de campos (sem nocao de linha) -- precisa continuar funcionando,
    cada campo antigo virando sua propria linha."""
    import json

    from db.schema import APP_LIST_DISPLAY

    conn.execute(
        f"INSERT INTO {APP_LIST_DISPLAY} (tabela, campos_resumo) VALUES (?, ?)",
        ("PESSOAS", json.dumps(["NOME", "CARGO", "EMAIL"])),
    )
    conn.commit()

    layout = settings.obter_campos_resumo(conn, "PESSOAS", padrao=[["X"]])
    assert layout == [["NOME"], ["CARGO"], ["EMAIL"]]


def test_rotulo_tabela_padrao_pessoas_e_contatos(conn):
    assert settings.obter_rotulo_tabela(conn, "PESSOAS") == "Contatos"
    assert settings.obter_rotulo_tabela(conn, "EMPRESAS") == "EMPRESAS"


def test_rotulo_tabela_configuravel_nao_muda_nome_real(conn):
    from db.tables import list_data_sheets

    settings.definir_rotulo_tabela(conn, "PESSOAS", "01 - Contatos")
    settings.definir_rotulo_tabela(conn, "EMPRESAS", "02 - Empresas")
    assert settings.obter_rotulo_tabela(conn, "PESSOAS") == "01 - Contatos"
    assert settings.obter_rotulo_tabela(conn, "EMPRESAS") == "02 - Empresas"
    # o nome real da tabela no banco continua intocado
    assert "PESSOAS" in list_data_sheets(conn)
    assert "EMPRESAS" in list_data_sheets(conn)


def test_rotulo_tabela_em_branco_volta_ao_padrao(conn):
    settings.definir_rotulo_tabela(conn, "PESSOAS", "01 - Contatos")
    settings.definir_rotulo_tabela(conn, "PESSOAS", "")
    assert settings.obter_rotulo_tabela(conn, "PESSOAS") == "Contatos"
