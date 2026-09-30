from db import categorias, exporter, importer_planilha, records
from db.tables import get_schema


def test_linha_com_id_em_branco_cria_registro_novo(conn):
    columns = ["ID", "NOME"]
    rows = [{"ID": "", "NOME": "Ana"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.criados == 1
    assert resumo.atualizados == 0
    todos = records.get_records(conn, "PESSOAS")
    assert len(todos) == 1
    assert todos[0]["NOME"] == "Ana"


def test_linha_com_id_existente_atualiza_em_vez_de_duplicar(conn):
    id_ana = records.create_record(conn, "PESSOAS", {"NOME": "Ana", "EMAIL": "ana@old.com"})
    columns = ["ID", "NOME", "EMAIL"]
    rows = [{"ID": str(id_ana), "NOME": "Ana Silva", "EMAIL": "ana@novo.com"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.criados == 0
    assert resumo.atualizados == 1
    todos = records.get_records(conn, "PESSOAS")
    assert len(todos) == 1
    assert todos[0]["NOME"] == "Ana Silva"
    assert todos[0]["EMAIL"] == "ana@novo.com"


def test_linha_com_id_em_formato_decimal_do_excel_atualiza_em_vez_de_duplicar(conn):
    """Excel/openpyxl pode devolver o ID como float (ex.: 12.0) se a celula
    estiver formatada como numero geral/decimal -- isso nao pode fazer o
    programa achar que a linha "nao tem ID" e duplicar o contato."""
    id_ana = records.create_record(conn, "PESSOAS", {"NOME": "Ana"})
    columns = ["ID", "NOME"]
    rows = [{"ID": f"{id_ana}.0", "NOME": "Ana Silva"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.criados == 0
    assert resumo.atualizados == 1
    todos = records.get_records(conn, "PESSOAS")
    assert len(todos) == 1
    assert todos[0]["NOME"] == "Ana Silva"


def test_linha_com_id_que_nao_existe_mais_cria_novo_e_avisa(conn):
    columns = ["ID", "NOME"]
    rows = [{"ID": "999", "NOME": "Bia"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.criados == 1
    assert resumo.atualizados == 0
    assert any("999" in aviso for aviso in resumo.avisos)
    todos = records.get_records(conn, "PESSOAS")
    assert len(todos) == 1
    assert todos[0]["NOME"] == "Bia"
    assert todos[0]["ID"] != 999


def test_celula_em_branco_ao_atualizar_apaga_valor_existente(conn):
    id_ana = records.create_record(conn, "PESSOAS", {"NOME": "Ana", "EMAIL": "ana@old.com"})
    columns = ["ID", "NOME", "EMAIL"]
    rows = [{"ID": str(id_ana), "NOME": "Ana", "EMAIL": ""}]

    importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    atualizada = records.get_record(conn, "PESSOAS", id_ana)
    assert atualizada["EMAIL"] in ("", None)


def test_coluna_nao_incluida_no_arquivo_permanece_intocada(conn):
    """So as colunas que vieram no arquivo devem ser tocadas -- uma coluna
    que o usuario desmarcou na exportacao (e portanto nao aparece no
    cabecalho) precisa continuar como estava no banco."""
    id_ana = records.create_record(conn, "PESSOAS", {"NOME": "Ana", "EMAIL": "ana@old.com", "WHATSAPP": "123"})
    columns = ["ID", "NOME", "EMAIL"]  # WHATSAPP nao entrou no arquivo
    rows = [{"ID": str(id_ana), "NOME": "Ana", "EMAIL": "ana@novo.com"}]

    importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    atualizada = records.get_record(conn, "PESSOAS", id_ana)
    assert atualizada["WHATSAPP"] == "123"


def test_coluna_desconhecida_no_arquivo_e_criada_automaticamente(conn):
    columns = ["ID", "NOME", "OBSERVACAO"]
    rows = [{"ID": "", "NOME": "Carla", "OBSERVACAO": "Vegetariana"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert "OBSERVACAO" in get_schema(conn, "PESSOAS")
    assert resumo.colunas_novas == ["OBSERVACAO"]
    registro = records.get_records(conn, "PESSOAS")[0]
    assert registro["OBSERVACAO"] == "Vegetariana"


def test_empresa_existente_e_resolvida_por_sigla_empresa(conn):
    id_empresa = records.create_record(
        conn, "EMPRESAS", {"SIGLA": "RJ", "SIGLA_EMPRESA": "PRODERJ", "EMPRESA": "Proderj"}
    )
    columns = ["ID", "NOME", "SIGLA", "SIGLA_EMPRESA", "EMPRESA"]
    rows = [{"ID": "", "NOME": "Duda", "SIGLA": "RJ", "SIGLA_EMPRESA": "PRODERJ", "EMPRESA": "Proderj"}]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.empresas_criadas == 0
    pessoas = records.get_records(conn, "PESSOAS")
    assert len(pessoas) == 1
    assert pessoas[0]["ID_EMPRESA"] == id_empresa
    assert len(records.get_records(conn, "EMPRESAS")) == 1


def test_empresa_sem_correspondencia_e_criada_e_reaproveitada_na_mesma_importacao(conn):
    columns = ["ID", "NOME", "SIGLA", "SIGLA_EMPRESA", "EMPRESA"]
    rows = [
        {"ID": "", "NOME": "Duda", "SIGLA": "RJ", "SIGLA_EMPRESA": "PRODERJ", "EMPRESA": "Proderj"},
        {"ID": "", "NOME": "Elis", "SIGLA": "RJ", "SIGLA_EMPRESA": "PRODERJ", "EMPRESA": "Proderj"},
    ]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.empresas_criadas == 1
    empresas = records.get_records(conn, "EMPRESAS")
    assert len(empresas) == 1
    pessoas = records.get_records(conn, "PESSOAS")
    assert pessoas[0]["ID_EMPRESA"] == pessoas[1]["ID_EMPRESA"] == empresas[0]["ID"]


def test_linha_sem_empresa_preenchida_nao_cria_empresa_vazia(conn):
    """Uma pessoa sem empresa vinculada exporta SIGLA/SIGLA_EMPRESA/EMPRESA
    em branco -- reimportar isso sem editar nao pode criar uma empresa "vazia"
    do nada (bug de round-trip: toda pessoa sem empresa viraria dona de uma
    empresa fantasma em comum)."""
    columns = ["ID", "NOME", "SIGLA", "SIGLA_EMPRESA", "EMPRESA"]
    rows = [
        {"ID": "", "NOME": "Duda", "SIGLA": "", "SIGLA_EMPRESA": "", "EMPRESA": ""},
        {"ID": "", "NOME": "Elis", "SIGLA": "", "SIGLA_EMPRESA": "", "EMPRESA": ""},
    ]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert resumo.empresas_criadas == 0
    assert records.get_records(conn, "EMPRESAS") == []
    pessoas = records.get_records(conn, "PESSOAS")
    assert pessoas[0]["ID_EMPRESA"] is None
    assert pessoas[1]["ID_EMPRESA"] is None


def test_categoria_com_lista_separada_por_virgula_vincula_categorias(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    categorias.adicionar_categoria(conn, "Diretores Tecnicos")
    columns = ["ID", "NOME", "CATEGORIA"]
    rows = [{"ID": "", "NOME": "Fabio", "CATEGORIA": "Presidentes, Diretores Tecnicos"}]

    importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    id_fabio = records.get_records(conn, "PESSOAS")[0]["ID"]
    assert set(categorias.categorias_da_pessoa(conn, id_fabio)) == {"Presidentes", "Diretores Tecnicos"}


def test_categoria_em_branco_ao_atualizar_remove_todas_categorias(conn):
    categorias.adicionar_categoria(conn, "Presidentes")
    id_fabio = records.create_record(conn, "PESSOAS", {"NOME": "Fabio"})
    categorias.definir_categorias_da_pessoa(conn, id_fabio, ["Presidentes"])
    columns = ["ID", "NOME", "CATEGORIA"]
    rows = [{"ID": str(id_fabio), "NOME": "Fabio", "CATEGORIA": ""}]

    importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows)

    assert categorias.categorias_da_pessoa(conn, id_fabio) == []


def test_aplicar_falso_nao_grava_nada_no_banco(conn):
    id_ana = records.create_record(conn, "PESSOAS", {"NOME": "Ana", "EMAIL": "ana@old.com"})
    colunas_antes = set(get_schema(conn, "PESSOAS"))
    columns = ["ID", "NOME", "EMAIL", "OBSERVACAO"]
    rows = [
        {"ID": "", "NOME": "Carla", "EMAIL": "carla@x.com", "OBSERVACAO": "nova"},
        {"ID": str(id_ana), "NOME": "Ana Silva", "EMAIL": "ana@novo.com", "OBSERVACAO": ""},
    ]

    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", columns, rows, aplicar=False)

    assert resumo.criados == 1
    assert resumo.atualizados == 1
    assert resumo.colunas_novas == ["OBSERVACAO"]
    # nada foi escrito de verdade
    assert set(get_schema(conn, "PESSOAS")) == colunas_antes
    pessoas = records.get_records(conn, "PESSOAS")
    assert len(pessoas) == 1
    assert pessoas[0]["NOME"] == "Ana"
    assert pessoas[0]["EMAIL"] == "ana@old.com"


def test_round_trip_exportar_e_reimportar_sem_editar_nao_muda_nada(conn, tmp_path):
    id_empresa = records.create_record(conn, "EMPRESAS", {"SIGLA": "RJ", "SIGLA_EMPRESA": "PRODERJ", "EMPRESA": "Proderj"})
    records.create_record(conn, "PESSOAS", {"ID_EMPRESA": id_empresa, "NOME": "Ana", "EMAIL": "ana@x.com", "CARGO": "Diretora"})

    colunas, linhas = exporter.montar_exportacao_simples(conn, "PESSOAS")
    caminho = tmp_path / "export.csv"
    exporter.exportar_csv(colunas, linhas, str(caminho))

    lidas_colunas, lidas_linhas = importer_planilha.ler_planilha(str(caminho))
    resumo = importer_planilha.importar_planilha(conn, "PESSOAS", lidas_colunas, lidas_linhas)

    assert resumo.criados == 0
    assert resumo.atualizados == 1
    assert resumo.empresas_criadas == 0
    pessoas = records.get_records(conn, "PESSOAS")
    assert len(pessoas) == 1
    assert pessoas[0]["NOME"] == "Ana"
    assert pessoas[0]["EMAIL"] == "ana@x.com"
    assert len(records.get_records(conn, "EMPRESAS")) == 1


def test_ler_planilha_csv_com_cabecalho_duplicado_nao_perde_a_primeira_coluna(tmp_path):
    """Duas colunas com o mesmo nome (arquivo editado a mao, ou juntando
    duas exportacoes) nao podem fazer a segunda apagar silenciosamente o
    valor da primeira -- mesma protecao que db/importer.py::_ler_cabecalho
    ja tem pro formato antigo."""
    caminho = tmp_path / "duplicado.csv"
    caminho.write_text("NOME,TELEFONE,TELEFONE\nAna,1111,2222\n", encoding="utf-8-sig")

    colunas, linhas = importer_planilha.ler_planilha(str(caminho))

    assert colunas == ["NOME", "TELEFONE", "TELEFONE (2)"]
    assert linhas[0]["TELEFONE"] == "1111"
    assert linhas[0]["TELEFONE (2)"] == "2222"
