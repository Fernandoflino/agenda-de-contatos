"""
Este arquivo e a "planta baixa" do banco de dados: define, em SQL, quais
tabelas existem logo quando um arquivo de banco (.abepdb) e criado pela
primeira vez, e quais colunas cada uma tem.

Pensa assim: um banco de dados SQLite e um unico arquivo no seu computador
que guarda varias "planilhas" (aqui chamadas de tabelas), cada uma com linhas
e colunas, igual Excel -- so que com regras mais rigidas, o que evita erros.

Duas categorias de tabela:
1. Tabelas internas do programa (comecam com "app_" ou sao USUARIOS) -- guardam
   configuracao, senha, log de alteracoes etc. Nunca aparecem como "tabela de
   dados" pro usuario mexer diretamente.
2. Tabelas de dados (EMPRESAS, PESSOAS, e qualquer outra que o usuario criar
   depois pela tela de "Gerenciar tabelas") -- essas sim aparecem na interface.
"""
from __future__ import annotations

# Nomes das tabelas, guardados em constantes pra nao espalhar strings soltas
# (e escritas erradas) pelo resto do codigo.
APP_METADATA = "app_metadata"           # guarda "segredos"/config tecnica (ex: a chave usada no hash de senha)
APP_LOG = "app_log"                     # historico de tudo que foi criado/editado/excluido
APP_LOGIN_ATTEMPTS = "app_login_attempts"  # controla tentativas de login erradas (protecao contra forca bruta)
APP_COLUMN_ORDER = "app_column_order"   # em que ordem as colunas de cada tabela aparecem na tela
APP_FIELD_TYPES = "app_field_types"     # que "tipo" cada campo tem (email, telefone, data, etc.)
APP_LIST_DISPLAY = "app_list_display"   # quais campos aparecem resumidos na lista de contatos
APP_BRANDING = "app_branding"           # nome do painel, logotipo e cor escolhidos pelo usuario
APP_TABLE_LABELS = "app_table_labels"   # apelido de exibicao de cada tabela (ver mais abaixo)
APP_ANOTACOES = "app_anotacoes"         # anotacoes livres por registro (ver db/anotacoes.py)
APP_USER_PREFS = "app_user_prefs"       # filtros/larguras que CADA USUARIO deixou numa tabela (ver db/preferencias.py)
USUARIOS = "USUARIOS"                   # quem pode fazer login no programa
EMPRESAS = "EMPRESAS"                   # as empresas associadas (a tabela "mae")
PESSOAS = "PESSOAS"                     # os contatos (presidentes, diretores etc.), ligados a uma empresa

# Todas as tabelas internas do programa -- a tela "Gerenciar tabelas" nunca
# deve mostrar essas pro usuario, so as tabelas de dados de verdade.
RESERVED_TABLES = {
    APP_METADATA,
    APP_LOG,
    APP_LOGIN_ATTEMPTS,
    APP_COLUMN_ORDER,
    APP_FIELD_TYPES,
    APP_LIST_DISPLAY,
    APP_BRANDING,
    APP_TABLE_LABELS,
    APP_ANOTACOES,
    APP_USER_PREFS,
}

# Estas 3 tabelas sao "especiais": boa parte do programa (login, resolucao de
# empresa por ID_EMPRESA, importacao, a tela de Contatos) conta com elas
# existindo com ESSE NOME EXATO -- diferente de uma tabela qualquer que o
# usuario crie, elas NAO PODEM ser renomeadas nem excluidas pela tela de
# "Gerenciar tabelas" (ver db/tables.py). Quem quiser um nome diferente
# aparecendo no menu lateral pode usar o "rotulo de exibicao" (app_table_labels)
# em vez de renomear a tabela de verdade.
TABELAS_PROTEGIDAS = {EMPRESAS, PESSOAS, USUARIOS}

# Se um dia o formato interno do banco precisar mudar de um jeito que exija
# "consertar" bancos antigos automaticamente, este numero e o que vamos
# comparar pra saber se e preciso rodar alguma migracao (ver
# migrar_schema_se_necessario() no final deste arquivo).
SCHEMA_VERSION = 5

# --- Tabelas internas do programa (configuracao, seguranca, historico) ---
_DDL_INTERNAS = f"""
CREATE TABLE {APP_METADATA} (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE {APP_LOG} (
    id INTEGER PRIMARY KEY,
    data_hora TEXT NOT NULL,
    usuario TEXT NOT NULL,
    tabela TEXT NOT NULL,
    acao TEXT NOT NULL,
    detalhes TEXT
);

CREATE TABLE {APP_LOGIN_ATTEMPTS} (
    usuario_chave TEXT PRIMARY KEY,
    falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT
);

CREATE TABLE {APP_COLUMN_ORDER} (
    tabela TEXT NOT NULL,
    coluna TEXT NOT NULL,
    posicao INTEGER NOT NULL,
    PRIMARY KEY (tabela, coluna)
);

CREATE TABLE {APP_FIELD_TYPES} (
    tabela TEXT NOT NULL,
    coluna TEXT NOT NULL,
    tipo TEXT NOT NULL,
    opcoes TEXT,
    PRIMARY KEY (tabela, coluna)
);

CREATE TABLE {APP_LIST_DISPLAY} (
    tabela TEXT PRIMARY KEY,
    campos_resumo TEXT
);

CREATE TABLE {APP_BRANDING} (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nome TEXT,
    cor_destaque TEXT,
    logo BLOB,
    logo_mime TEXT,
    tema TEXT
);

CREATE TABLE {APP_TABLE_LABELS} (
    tabela TEXT PRIMARY KEY,
    rotulo TEXT NOT NULL
);

CREATE TABLE {APP_ANOTACOES} (
    tabela TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    texto TEXT,
    PRIMARY KEY (tabela, registro_id)
);

CREATE TABLE {APP_USER_PREFS} (
    usuario TEXT NOT NULL,
    tabela TEXT NOT NULL,
    dados TEXT,
    PRIMARY KEY (usuario, tabela)
);

CREATE TABLE "{USUARIOS}" (
    "ID" INTEGER PRIMARY KEY,
    "USUARIO" TEXT UNIQUE NOT NULL,
    "SENHA_HASH" TEXT NOT NULL,
    "NOME" TEXT
);
"""

# --- Tabela EMPRESAS: cada linha e uma empresa associada ---
_DDL_EMPRESAS = f"""
CREATE TABLE "{EMPRESAS}" (
    "ID" INTEGER PRIMARY KEY,
    "SIGLA" TEXT,
    "SIGLA_EMPRESA" TEXT,
    "EMPRESA" TEXT,
    "EMPRESA_MINUSCULA" TEXT,
    "ÍNDICE ABEP" TEXT
);
"""

# --- Tabela PESSOAS: cada linha e um contato (presidente, diretor etc.) ---
# ligado a uma empresa pela coluna ID_EMPRESA. Uma empresa pode ter quantas
# pessoas quiser, em qualquer cargo -- nao existe mais uma tabela separada
# por cargo como no sistema antigo.
#
# CATEGORIA e diferente de CARGO: CARGO e o titulo/cargo escrito livremente
# (ex.: "Secretario de Estado...", "Coordenador-Geral") e pode variar MUITO
# de pessoa pra pessoa, mesmo dentro do mesmo "tipo" de contato. CATEGORIA e
# uma etiqueta fixa e mais generica (ex.: "Presidente", "Diretor Tecnico",
# "Diretor Adm. Financeiro") -- e o que a planilha antiga separava em ABAS
# diferentes, e o campo usado pra "mala direta" (juntar os contatos de uma
# mesma empresa numa linha so, um por categoria -- ver db/exporter.py).
_DDL_PESSOAS = f"""
CREATE TABLE "{PESSOAS}" (
    "ID" INTEGER PRIMARY KEY,
    "ID_EMPRESA" INTEGER REFERENCES "{EMPRESAS}"("ID"),
    "CATEGORIA" TEXT,
    "CARGO" TEXT,
    "CARGO2" TEXT,
    "TRATAMENTO" TEXT,
    "NOME DE GUERRA" TEXT,
    "NOME" TEXT,
    "EMAIL" TEXT,
    "WHATSAPP" TEXT,
    "SEXO" TEXT,
    "CPF" TEXT,
    "DATA DE NASCIMENTO" TEXT,
    "ASSESSOR(A)" TEXT,
    "WHATSAPP ASSESSOR" TEXT,
    "CP1" TEXT, "CP2" TEXT, "CP3" TEXT, "CP4" TEXT, "CP5" TEXT,
    "CP6" TEXT, "CP7" TEXT, "CP8" TEXT, "CP9" TEXT
);
"""


def criar_schema_inicial(conn) -> None:
    """Executa todo o SQL acima de uma vez, criando um banco novo do zero.

    `conn` e a conexao aberta com o arquivo .abepdb (veja db/connection.py).
    Isso e chamado uma unica vez, no momento em que o usuario escolhe
    "Novo banco de dados" na tela inicial do programa.
    """
    conn.executescript(_DDL_INTERNAS)
    conn.executescript(_DDL_EMPRESAS)
    conn.executescript(_DDL_PESSOAS)

    # Guarda a versao do schema, pra o programa saber no futuro se esse
    # arquivo precisa de algum ajuste automatico antes de ser aberto.
    conn.execute(
        f"INSERT INTO {APP_METADATA} (chave, valor) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    # Linha unica de configuracao visual (nome/cor/logotipo), comecando vazia
    # -- o programa usa valores padrao ate o usuario configurar algo na tela
    # de Configuracoes.
    conn.execute(f"INSERT INTO {APP_BRANDING} (id, nome, cor_destaque, tema) VALUES (1, NULL, NULL, NULL)")
    conn.commit()


def migrar_schema_se_necessario(conn) -> None:
    """Atualiza um banco de dados ANTIGO (criado por uma versao anterior do
    programa) pra ele ganhar as tabelas/colunas novas, sem apagar nada do
    que ja existia. Chamado toda vez que um arquivo .abepdb e aberto (ver
    db/connection.py) -- se o banco ja estiver atualizado, isso nao faz nada.

    Pensa nisso como uma "reforma": o arquivo continua o mesmo, so ganha
    comodos novos que a planta baixa mais recente do programa passou a ter.
    """
    colunas_branding = {row[1] for row in conn.execute(f"PRAGMA table_info({APP_BRANDING})")}
    mudou = False

    if "tema" not in colunas_branding:
        # Bancos criados antes da opcao de modo claro/escuro existir --
        # adiciona a coluna faltante, com o modo claro (o unico que existia
        # ate entao) como padrao pra quem ja estava usando o programa.
        conn.execute(f"ALTER TABLE {APP_BRANDING} ADD COLUMN tema TEXT")
        conn.execute(f"UPDATE {APP_BRANDING} SET tema = 'claro' WHERE tema IS NULL")
        mudou = True

    tabelas_existentes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    if APP_TABLE_LABELS not in tabelas_existentes:
        # Bancos criados antes de existir "rotulo de exibicao" pra tabela --
        # sem essa tabela, so cria ela vazia (comeca sem nenhum apelido
        # configurado, o que e um estado normal e valido).
        conn.execute(f"""
            CREATE TABLE {APP_TABLE_LABELS} (
                tabela TEXT PRIMARY KEY,
                rotulo TEXT NOT NULL
            )
        """)
        mudou = True

    if APP_ANOTACOES not in tabelas_existentes:
        # Bancos criados antes de existir "anotacoes" por registro -- so
        # cria a tabela vazia (comeca sem nenhuma anotacao, estado normal).
        conn.execute(f"""
            CREATE TABLE {APP_ANOTACOES} (
                tabela TEXT NOT NULL,
                registro_id INTEGER NOT NULL,
                texto TEXT,
                PRIMARY KEY (tabela, registro_id)
            )
        """)
        mudou = True

    if APP_USER_PREFS not in tabelas_existentes:
        # Bancos criados antes de existir "preferencias por usuario" (filtros
        # salvos, largura do painel de detalhes) -- so cria a tabela vazia
        # (comeca sem nenhuma preferencia guardada, estado normal).
        conn.execute(f"""
            CREATE TABLE {APP_USER_PREFS} (
                usuario TEXT NOT NULL,
                tabela TEXT NOT NULL,
                dados TEXT,
                PRIMARY KEY (usuario, tabela)
            )
        """)
        mudou = True

    # A tabela PESSOAS pode nem existir mais nesse nome exato se algum banco
    # muito antigo (de antes das tabelas ficarem protegidas) tiver sido
    # renomeado -- so mexe se ela ainda existir com o nome original.
    if PESSOAS in tabelas_existentes:
        colunas_pessoas = {row[1] for row in conn.execute(f'PRAGMA table_info("{PESSOAS}")')}
        if "CATEGORIA" not in colunas_pessoas:
            # Bancos criados antes do campo CATEGORIA existir -- adiciona a
            # coluna faltante (fica em branco pros registros que ja existiam;
            # nao da pra saber retroativamente "de qual aba" cada um veio).
            conn.execute(f'ALTER TABLE "{PESSOAS}" ADD COLUMN "CATEGORIA" TEXT')
            mudou = True

    if mudou:
        conn.commit()
