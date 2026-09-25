import json
import sqlite3

from db import schema


def _banco_antigo() -> sqlite3.Connection:
    """Simula um banco de ANTES da relacao N:N de categorias existir (sem
    app_categorias/app_pessoas_categorias), com o minimo de tabelas internas
    que migrar_schema_se_necessario espera encontrar."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE app_metadata (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE app_field_types (
            tabela TEXT NOT NULL, coluna TEXT NOT NULL, tipo TEXT NOT NULL, opcoes TEXT,
            PRIMARY KEY (tabela, coluna)
        );
        CREATE TABLE app_branding (id INTEGER PRIMARY KEY CHECK (id = 1), nome TEXT, cor_destaque TEXT, tema TEXT);
        CREATE TABLE "EMPRESAS" ("ID" INTEGER PRIMARY KEY, "SIGLA" TEXT, "EMPRESA" TEXT);
        CREATE TABLE "PESSOAS" (
            "ID" INTEGER PRIMARY KEY,
            "ID_EMPRESA" INTEGER REFERENCES "EMPRESAS"("ID"),
            "CATEGORIA" TEXT,
            "NOME" TEXT
        );
    """)
    conn.execute("INSERT INTO app_branding (id, nome, cor_destaque, tema) VALUES (1, NULL, NULL, 'claro')")
    conn.commit()
    return conn


def test_migracao_cria_tabelas_de_categoria():
    conn = _banco_antigo()
    schema.migrar_schema_se_necessario(conn)
    tabelas = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "app_categorias" in tabelas
    assert "app_pessoas_categorias" in tabelas
    conn.close()


def test_migracao_sem_json_ordena_por_primeira_aparicao_nao_alfabetica():
    """Regressao: quando o banco antigo nunca teve app_field_types.opcoes
    configurado pra CATEGORIA (cenario real de um banco corrigido na mao por
    scripts_manutencao/corrigir_bancos_existentes.py), a migracao NAO pode
    cair em ordem alfabetica -- "Diretores Adm. Financeiros" viria antes de
    "Diretores Técnicos", que e a ordem errada. A ordem certa e a de
    PRIMEIRA APARICAO por ID (replica a ordem real de cadastro/importacao)."""
    conn = _banco_antigo()
    id_empresa = conn.execute('INSERT INTO "EMPRESAS" ("SIGLA", "EMPRESA") VALUES (?, ?)', ("ABC", "Empresa ABC")).lastrowid
    # Faixas de ID em ordem de cadastro: Presidentes primeiro, depois
    # Diretores Tecnicos, depois Diretores Adm. Financeiros -- igual ao
    # cenario real do usuario (_FAIXAS_CATEGORIA em corrigir_bancos_existentes.py).
    for categoria in ["Presidentes"] * 3 + ["Diretores Técnicos"] * 3 + ["Diretores Adm. Financeiros"] * 3:
        conn.execute(
            'INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)',
            (id_empresa, categoria, "Fulano"),
        )
    conn.commit()

    schema.migrar_schema_se_necessario(conn)

    ordenadas = [r[0] for r in conn.execute('SELECT "NOME" FROM app_categorias ORDER BY "ORDEM"')]
    assert ordenadas == ["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"]
    conn.close()


def test_migracao_com_json_usa_ordem_configurada():
    """Quando app_field_types.opcoes JA tem uma lista configurada, essa
    ordem tem prioridade sobre a ordem de aparicao em PESSOAS."""
    conn = _banco_antigo()
    conn.execute(
        "INSERT INTO app_field_types (tabela, coluna, tipo, opcoes) VALUES (?, ?, ?, ?)",
        ("PESSOAS", "CATEGORIA", "selecao", json.dumps(["Zebra", "Abelha"])),
    )
    id_empresa = conn.execute('INSERT INTO "EMPRESAS" ("SIGLA", "EMPRESA") VALUES (?, ?)', ("ABC", "Empresa ABC")).lastrowid
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)', (id_empresa, "Abelha", "Ana"))
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)', (id_empresa, "Zebra", "Bia"))
    conn.commit()

    schema.migrar_schema_se_necessario(conn)

    ordenadas = [r[0] for r in conn.execute('SELECT "NOME" FROM app_categorias ORDER BY "ORDEM"')]
    assert ordenadas == ["Zebra", "Abelha"]  # ordem do JSON, nao a de aparicao/alfabetica
    conn.close()


def test_migracao_vincula_pessoas_as_categorias_ignorando_diferenca_de_caixa():
    conn = _banco_antigo()
    id_empresa = conn.execute('INSERT INTO "EMPRESAS" ("SIGLA", "EMPRESA") VALUES (?, ?)', ("ABC", "Empresa ABC")).lastrowid
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)', (id_empresa, "Presidentes", "Ana"))
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)', (id_empresa, "presidentes", "Bruno"))
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "NOME") VALUES (?, ?)', (id_empresa, "Carla"))  # sem categoria
    conn.commit()

    schema.migrar_schema_se_necessario(conn)

    assert [r[0] for r in conn.execute('SELECT "NOME" FROM app_categorias')] == ["Presidentes"]
    vinculos = conn.execute("SELECT COUNT(*) FROM app_pessoas_categorias").fetchone()[0]
    assert vinculos == 2  # Ana e Bruno, ambos ligados a mesma categoria "Presidentes"
    conn.close()


def test_migracao_cria_colunas_de_foto():
    conn = _banco_antigo()
    schema.migrar_schema_se_necessario(conn)
    schema.migrar_schema_se_necessario(conn)  # roda 2x: nao pode dar erro de "coluna ja existe"
    colunas = {row[1] for row in conn.execute('PRAGMA table_info("PESSOAS")')}
    assert "FOTO" in colunas
    assert "FOTO_MIME" in colunas
    conn.close()


def test_migracao_cria_tabelas_da_lixeira():
    conn = _banco_antigo()
    schema.migrar_schema_se_necessario(conn)
    schema.migrar_schema_se_necessario(conn)  # roda 2x: nao pode dar erro de "tabela ja existe"
    tabelas = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "app_lixeira_registros" in tabelas
    assert "app_lixeira_tabelas" in tabelas
    assert "app_lixeira_campos" in tabelas
    conn.close()


def test_migracao_e_idempotente():
    conn = _banco_antigo()
    id_empresa = conn.execute('INSERT INTO "EMPRESAS" ("SIGLA", "EMPRESA") VALUES (?, ?)', ("ABC", "Empresa ABC")).lastrowid
    conn.execute('INSERT INTO "PESSOAS" ("ID_EMPRESA", "CATEGORIA", "NOME") VALUES (?, ?, ?)', (id_empresa, "Presidentes", "Ana"))
    conn.commit()

    schema.migrar_schema_se_necessario(conn)
    schema.migrar_schema_se_necessario(conn)

    assert conn.execute("SELECT COUNT(*) FROM app_categorias").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM app_pessoas_categorias").fetchone()[0] == 1
    conn.close()
