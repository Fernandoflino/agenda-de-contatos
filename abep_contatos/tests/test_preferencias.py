from db import preferencias


def test_preferencias_padrao_quando_nao_configurado(conn):
    prefs = preferencias.obter_preferencias(conn, "fernando", "PESSOAS")
    assert prefs.filtros == []
    assert prefs.largura_painel is None
    assert prefs.itens_por_pagina is None


def test_salvar_e_obter_preferencias(conn):
    prefs = preferencias.PreferenciasTabela(
        filtros=[{"campo": "CATEGORIA", "valor": "Presidente"}],
        largura_painel=[700, 400],
        itens_por_pagina=50,
    )
    preferencias.salvar_preferencias(conn, "fernando", "PESSOAS", prefs)

    lidas = preferencias.obter_preferencias(conn, "fernando", "PESSOAS")
    assert lidas.filtros == [{"campo": "CATEGORIA", "valor": "Presidente"}]
    assert lidas.largura_painel == [700, 400]
    assert lidas.itens_por_pagina == 50


def test_preferencias_sao_isoladas_por_usuario_e_por_tabela(conn):
    preferencias.salvar_preferencias(
        conn, "fernando", "PESSOAS", preferencias.PreferenciasTabela(itens_por_pagina=10)
    )
    preferencias.salvar_preferencias(
        conn, "diego", "PESSOAS", preferencias.PreferenciasTabela(itens_por_pagina=100)
    )
    preferencias.salvar_preferencias(
        conn, "fernando", "EMPRESAS", preferencias.PreferenciasTabela(itens_por_pagina=20)
    )

    assert preferencias.obter_preferencias(conn, "fernando", "PESSOAS").itens_por_pagina == 10
    assert preferencias.obter_preferencias(conn, "diego", "PESSOAS").itens_por_pagina == 100
    assert preferencias.obter_preferencias(conn, "fernando", "EMPRESAS").itens_por_pagina == 20


def test_salvar_preferencias_substitui_a_anterior(conn):
    preferencias.salvar_preferencias(
        conn, "fernando", "PESSOAS", preferencias.PreferenciasTabela(itens_por_pagina=10)
    )
    preferencias.salvar_preferencias(
        conn, "fernando", "PESSOAS", preferencias.PreferenciasTabela(itens_por_pagina=100)
    )
    assert preferencias.obter_preferencias(conn, "fernando", "PESSOAS").itens_por_pagina == 100


def test_dados_corrompidos_no_banco_voltam_ao_padrao(conn):
    """Se o valor gravado nao for um JSON valido (ex.: banco mexido na mao,
    ou um formato de uma versao futura incompativel), a leitura nao pode
    quebrar -- so ignora e devolve as preferencias padrao (vazias)."""
    from db.schema import APP_USER_PREFS

    conn.execute(f"INSERT INTO {APP_USER_PREFS} (usuario, tabela, dados) VALUES (?, ?, ?)", ("fernando", "PESSOAS", "{nao e json"))
    conn.commit()

    prefs = preferencias.obter_preferencias(conn, "fernando", "PESSOAS")
    assert prefs.filtros == []
    assert prefs.largura_painel is None
