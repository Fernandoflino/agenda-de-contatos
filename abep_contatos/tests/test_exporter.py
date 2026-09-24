from db import categorias, exporter, records


def _preparar(conn):
    id_abc = records.create_record(conn, "EMPRESAS", {"SIGLA": "ABC", "EMPRESA": "Empresa ABC"})
    id_xyz = records.create_record(conn, "EMPRESAS", {"SIGLA": "XYZ", "EMPRESA": "Empresa XYZ"})

    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_abc, "CARGO": "Presidente", "NOME": "Ana"})
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_abc, "CARGO": "Diretor Técnico", "NOME": "Carla"})
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_xyz, "CARGO": "Presidente", "NOME": "Bruno"})
    # empresa XYZ tem 2 diretores tecnicos -- caso que motivou abandonar as 3 tabelas fixas
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_xyz, "CARGO": "Diretor Técnico", "NOME": "Duda"})
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_xyz, "CARGO": "Diretor Técnico", "NOME": "Elis"})
    return id_abc, id_xyz


def test_exportacao_simples_filtra_por_cargo(conn):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_simples(
        conn, "PESSOAS", filtro_campo="CARGO", filtro_valor="Diretor Técnico"
    )
    assert len(rows) == 3
    assert all(r["CARGO"] == "Diretor Técnico" for r in rows)
    assert "NOME" in columns


def test_exportacao_simples_mostra_empresa_em_vez_de_id(conn):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_simples(conn, "PESSOAS")
    assert "ID_EMPRESA" not in columns
    assert "SIGLA" in columns
    assert "EMPRESA" in columns
    assert {r["SIGLA"] for r in rows} == {"ABC", "XYZ"}
    assert {r["EMPRESA"] for r in rows} == {"Empresa ABC", "Empresa XYZ"}


def test_exportacao_simples_empresas_mantem_suas_proprias_colunas(conn):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_simples(conn, "EMPRESAS")
    assert "SIGLA" in columns
    assert "EMPRESA" in columns
    siglas = {r["SIGLA"] for r in rows}
    assert siglas == {"ABC", "XYZ"}


def test_exportacao_mesclada_uma_linha_por_empresa_simples(conn):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_mesclada(
        conn, "PESSOAS", valores_agrupador=["Presidente"], campo_agrupador="CARGO",
        campos_por_valor={"Presidente": ["NOME"]},
    )
    # so 1 presidente por empresa -> 1 linha por empresa, 2 empresas
    assert len(rows) == 2
    nomes_presidentes = {r["Presidente - NOME"] for r in rows}
    assert nomes_presidentes == {"Ana", "Bruno"}


def test_exportacao_mesclada_repete_linha_quando_ha_mais_de_uma_pessoa_no_cargo(conn):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_mesclada(
        conn, "PESSOAS", campo_agrupador="CARGO",
        valores_agrupador=["Presidente", "Diretor Técnico"],
        campos_por_valor={"Presidente": ["NOME"], "Diretor Técnico": ["NOME"]},
    )
    # ABC: 1 presidente x 1 diretor = 1 linha. XYZ: 1 presidente x 2 diretores = 2 linhas.
    assert len(rows) == 3
    nomes_diretores_xyz = {
        r["Diretor Técnico - NOME"] for r in rows if r["Presidente - NOME"] == "Bruno"
    }
    assert nomes_diretores_xyz == {"Duda", "Elis"}


def test_exportacao_mesclada_usa_categoria_por_padrao(conn):
    """A categoria (etiqueta que guarda de qual aba antiga a pessoa veio) e
    o agrupador padrao -- diferente do CARGO (texto livre), ela tem sempre
    os mesmos valores conhecidos, o que a torna mais confiavel pra montar a
    mala direta."""
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Tecnicos")
    id_abc = records.create_record(conn, "EMPRESAS", {"SIGLA": "QQQ", "EMPRESA": "Empresa QQQ"})
    id_fabio = records.create_record(conn, "PESSOAS", {
        "ID_EMPRESA": id_abc, "CARGO": "Presidente Executivo", "NOME": "Fabio",
    })
    id_gina = records.create_record(conn, "PESSOAS", {
        "ID_EMPRESA": id_abc, "CARGO": "Coordenador-Geral", "NOME": "Gina",
    })
    categorias.definir_categorias_da_pessoa(conn, id_fabio, ["Presidentes"])
    categorias.definir_categorias_da_pessoa(conn, id_gina, ["Diretores Tecnicos"])

    columns, rows = exporter.montar_exportacao_mesclada(
        conn, "PESSOAS", valores_agrupador=["Presidentes", "Diretores Tecnicos"],
        campos_por_valor={"Presidentes": ["NOME"], "Diretores Tecnicos": ["NOME"]},
    )
    assert len(rows) == 1
    assert rows[0]["Presidentes - NOME"] == "Fabio"
    assert rows[0]["Diretores Tecnicos - NOME"] == "Gina"


def test_exportacao_mesclada_pessoa_com_varias_categorias_aparece_em_todos_os_blocos(conn):
    """Um contato pode ter mais de uma categoria ao mesmo tempo -- ele deve
    aparecer em CADA bloco correspondente, nao so num."""
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Tecnicos")
    id_empresa = records.create_record(conn, "EMPRESAS", {"SIGLA": "QQQ", "EMPRESA": "Empresa QQQ"})
    id_fabio = records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_empresa, "NOME": "Fabio"})
    categorias.definir_categorias_da_pessoa(conn, id_fabio, ["Presidentes", "Diretores Tecnicos"])

    columns, rows = exporter.montar_exportacao_mesclada(
        conn, "PESSOAS", valores_agrupador=["Presidentes", "Diretores Tecnicos"],
        campos_por_valor={"Presidentes": ["NOME"], "Diretores Tecnicos": ["NOME"]},
    )
    assert len(rows) == 1
    assert rows[0]["Presidentes - NOME"] == "Fabio"
    assert rows[0]["Diretores Tecnicos - NOME"] == "Fabio"


def test_exportacao_simples_junta_varias_categorias_com_virgula(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Tecnicos")
    id_pessoa = records.create_record(conn, "PESSOAS", {"NOME": "Fabio"})
    categorias.definir_categorias_da_pessoa(conn, id_pessoa, ["Presidentes", "Diretores Tecnicos"])

    columns, rows = exporter.montar_exportacao_simples(conn, "PESSOAS")

    assert "CATEGORIA" in columns
    linha = next(r for r in rows if r["NOME"] == "Fabio")
    assert linha["CATEGORIA"] == "Presidentes, Diretores Tecnicos"


def test_exportar_xlsx_e_csv(conn, tmp_path):
    _preparar(conn)
    columns, rows = exporter.montar_exportacao_simples(conn, "PESSOAS")

    caminho_xlsx = tmp_path / "export.xlsx"
    exporter.exportar_xlsx(columns, rows, str(caminho_xlsx))
    assert caminho_xlsx.is_file()

    caminho_csv = tmp_path / "export.csv"
    exporter.exportar_csv(columns, rows, str(caminho_csv))
    conteudo = caminho_csv.read_text(encoding="utf-8-sig")
    assert "Ana" in conteudo
