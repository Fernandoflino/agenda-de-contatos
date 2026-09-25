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

import json

# Nomes das tabelas, guardados em constantes pra nao espalhar strings soltas
# (e escritas erradas) pelo resto do codigo.
APP_METADATA = "app_metadata"           # guarda "segredos"/config tecnica (ex: a chave usada no hash de senha)
APP_LOG = "app_log"                     # historico de tudo que foi criado/editado/excluido
APP_LOGIN_ATTEMPTS = "app_login_attempts"  # controla tentativas de login erradas (protecao contra forca bruta)
APP_COLUMN_ORDER = "app_column_order"   # em que ordem as colunas de cada tabela aparecem na tela
APP_TABLE_ORDER = "app_table_order"     # em que ordem as tabelas aparecem na sidebar/na tela de "Gerenciar tabelas"
APP_FIELD_TYPES = "app_field_types"     # que "tipo" cada campo tem (email, telefone, data, etc.)
APP_LIST_DISPLAY = "app_list_display"   # quais campos aparecem resumidos na lista de contatos
APP_BRANDING = "app_branding"           # nome do painel, logotipo e cor escolhidos pelo usuario
APP_TABLE_LABELS = "app_table_labels"   # apelido de exibicao de cada tabela (ver mais abaixo)
APP_ANOTACOES = "app_anotacoes"         # anotacoes livres por registro (ver db/anotacoes.py)
APP_USER_PREFS = "app_user_prefs"       # filtros/larguras que CADA USUARIO deixou numa tabela (ver db/preferencias.py)
APP_CATEGORIAS = "app_categorias"       # lista mestre de categorias de PESSOAS (ver db/categorias.py)
APP_PESSOAS_CATEGORIAS = "app_pessoas_categorias"  # vinculo N:N entre PESSOAS e app_categorias
APP_LIXEIRA_REGISTROS = "app_lixeira_registros"  # registros excluidos (ver db/lixeira.py)
APP_LIXEIRA_TABELAS = "app_lixeira_tabelas"      # tabelas inteiras excluidas
APP_LIXEIRA_CAMPOS = "app_lixeira_campos"        # campos/colunas excluidos
USUARIOS = "USUARIOS"                   # quem pode fazer login no programa
EMPRESAS = "EMPRESAS"                   # as empresas associadas (a tabela "mae")
PESSOAS = "PESSOAS"                     # os contatos (presidentes, diretores etc.), ligados a uma empresa

# As 4 colunas de foto de PESSOAS (ver comentario acima de _DDL_PESSOAS) sao
# BLOB/metadados internos -- nunca fazem sentido como "campo de texto"
# generico (exportacao em planilha, aba de informacoes, filtro por campo,
# configuracao de "campos extra" da lista). Usado por todos esses lugares
# pra nao precisar repetir essa lista em cada um.
CAMPOS_FOTO_OCULTOS = {"FOTO", "FOTO_MIME", "FOTO_ORIGINAL", "FOTO_ORIGINAL_MIME"}

# Todas as tabelas internas do programa -- a tela "Gerenciar tabelas" nunca
# deve mostrar essas pro usuario, so as tabelas de dados de verdade.
RESERVED_TABLES = {
    APP_METADATA,
    APP_LOG,
    APP_LOGIN_ATTEMPTS,
    APP_COLUMN_ORDER,
    APP_TABLE_ORDER,
    APP_FIELD_TYPES,
    APP_LIST_DISPLAY,
    APP_BRANDING,
    APP_TABLE_LABELS,
    APP_ANOTACOES,
    APP_USER_PREFS,
    APP_CATEGORIAS,
    APP_PESSOAS_CATEGORIAS,
    APP_LIXEIRA_REGISTROS,
    APP_LIXEIRA_TABELAS,
    APP_LIXEIRA_CAMPOS,
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
SCHEMA_VERSION = 6

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

CREATE TABLE {APP_TABLE_ORDER} (
    tabela TEXT PRIMARY KEY,
    posicao INTEGER NOT NULL
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
#
# FOTO/FOTO_MIME guardam o recorte circular (enquadrado/girado pelo usuario
# em ui/ajustar_foto_dialog.py) usado SO pra exibir o avatar na tela.
# FOTO_ORIGINAL/FOTO_ORIGINAL_MIME guardam o arquivo exatamente como foi
# escolhido (sem nenhum recorte/redimensionamento) -- e o que e devolvido
# quando alguem BAIXA a foto de um contato (ver ui/imagens.py), pra nunca
# perder qualidade nem enquadramento do arquivo original.
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
    "CP6" TEXT, "CP7" TEXT, "CP8" TEXT, "CP9" TEXT,
    "FOTO" BLOB,
    "FOTO_MIME" TEXT,
    "FOTO_ORIGINAL" BLOB,
    "FOTO_ORIGINAL_MIME" TEXT
);
"""

# --- Categorias de PESSOAS: relacao N:N (uma pessoa pode ter varias) ---
# app_categorias e a lista mestre (nome + ordem de exibicao); app_pessoas_categorias
# e so a tabela de vinculo, ligando cada pessoa as categorias que ela tem.
# A antiga coluna PESSOAS.CATEGORIA (TEXT, uma so por pessoa) continua existindo
# no banco por compatibilidade/seguranca, mas fica vestigial -- ninguem mais
# le nem escreve nela; ver migrar_schema_se_necessario() pra migracao dos
# dados antigos.
_DDL_CATEGORIAS = f"""
CREATE TABLE {APP_CATEGORIAS} (
    "ID" INTEGER PRIMARY KEY,
    "NOME" TEXT NOT NULL UNIQUE,
    "ORDEM" INTEGER NOT NULL
);

CREATE TABLE {APP_PESSOAS_CATEGORIAS} (
    "PESSOA_ID" INTEGER NOT NULL REFERENCES "{PESSOAS}"("ID") ON DELETE CASCADE,
    "CATEGORIA_ID" INTEGER NOT NULL REFERENCES {APP_CATEGORIAS}("ID") ON DELETE CASCADE,
    PRIMARY KEY ("PESSOA_ID", "CATEGORIA_ID")
);
"""

# --- Lixeira: guarda uma "foto" de tudo que foi excluido (registros,
# tabelas inteiras, campos/colunas), pra dar pra restaurar depois em vez de
# perder pra sempre -- ver db/lixeira.py. Cada JSON guarda o suficiente pra
# reconstruir o que foi apagado (linha completa, ou schema+dados inteiros de
# uma tabela, ou os valores de uma coluna em cada registro que tinha algo
# nela).
_DDL_LIXEIRA = f"""
CREATE TABLE {APP_LIXEIRA_REGISTROS} (
    "ID" INTEGER PRIMARY KEY,
    "TABELA" TEXT NOT NULL,
    "REGISTRO_ID_ORIGINAL" INTEGER NOT NULL,
    "DADOS_JSON" TEXT NOT NULL,
    "CATEGORIAS_JSON" TEXT,
    "ANOTACAO_TEXTO" TEXT,
    "EXCLUIDO_POR" TEXT,
    "EXCLUIDO_EM" TEXT NOT NULL
);

CREATE TABLE {APP_LIXEIRA_TABELAS} (
    "ID" INTEGER PRIMARY KEY,
    "TABELA" TEXT NOT NULL,
    "SCHEMA_JSON" TEXT NOT NULL,
    "DADOS_JSON" TEXT NOT NULL,
    "ANOTACOES_JSON" TEXT,
    "EXCLUIDO_POR" TEXT,
    "EXCLUIDO_EM" TEXT NOT NULL
);

CREATE TABLE {APP_LIXEIRA_CAMPOS} (
    "ID" INTEGER PRIMARY KEY,
    "TABELA" TEXT NOT NULL,
    "COLUNA" TEXT NOT NULL,
    "TIPO_SQL_ORIGINAL" TEXT NOT NULL,
    "TIPO_CAMPO_JSON" TEXT,
    "ORDEM_ORIGINAL" INTEGER,
    "VALORES_JSON" TEXT NOT NULL,
    "EXCLUIDO_POR" TEXT,
    "EXCLUIDO_EM" TEXT NOT NULL
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
    conn.executescript(_DDL_CATEGORIAS)
    conn.executescript(_DDL_LIXEIRA)

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

    if APP_TABLE_ORDER not in tabelas_existentes:
        # Bancos criados antes de existir "ordem manual" das tabelas -- so
        # cria a tabela vazia (sem nenhuma posicao configurada ainda, as
        # tabelas continuam aparecendo em ordem alfabetica ate o usuario
        # reordenar alguma pela tela de "Gerenciar tabelas").
        conn.execute(f"""
            CREATE TABLE {APP_TABLE_ORDER} (
                tabela TEXT PRIMARY KEY,
                posicao INTEGER NOT NULL
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

    if APP_CATEGORIAS not in tabelas_existentes:
        # Bancos criados antes de categoria virar uma relacao N:N -- cria as
        # duas tabelas novas e, so nesse momento (nunca mais de novo depois),
        # migra os dados que ja existiam: a lista configurada em
        # app_field_types e os valores ja usados na coluna PESSOAS.CATEGORIA
        # (que continua existindo no banco, so que vestigial a partir daqui).
        conn.execute(f"""
            CREATE TABLE {APP_CATEGORIAS} (
                "ID" INTEGER PRIMARY KEY,
                "NOME" TEXT NOT NULL UNIQUE,
                "ORDEM" INTEGER NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE TABLE {APP_PESSOAS_CATEGORIAS} (
                "PESSOA_ID" INTEGER NOT NULL REFERENCES "{PESSOAS}"("ID") ON DELETE CASCADE,
                "CATEGORIA_ID" INTEGER NOT NULL REFERENCES {APP_CATEGORIAS}("ID") ON DELETE CASCADE,
                PRIMARY KEY ("PESSOA_ID", "CATEGORIA_ID")
            )
        """)
        mudou = True

        # 1) Junta os nomes de categoria do JSON configurado (opcoes) com os
        # valores distintos que ja apareciam nos contatos -- sem diferenciar
        # maiuscula/minuscula, pra "Presidente" e "presidente" nao virarem
        # duas categorias separadas (fica a grafia que apareceu primeiro).
        nomes_categoria: list[str] = []
        vistos_lower: set[str] = set()

        row_opcoes = conn.execute(
            f"SELECT opcoes FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = 'CATEGORIA'", (PESSOAS,)
        ).fetchone()
        if row_opcoes and row_opcoes[0]:
            try:
                opcoes = json.loads(row_opcoes[0])
            except (json.JSONDecodeError, TypeError):
                opcoes = None
            if isinstance(opcoes, list):
                for opcao in opcoes:
                    nome = str(opcao).strip()
                    if nome and nome.lower() not in vistos_lower:
                        nomes_categoria.append(nome)
                        vistos_lower.add(nome.lower())

        if PESSOAS in tabelas_existentes:
            colunas_pessoas_atuais = {row[1] for row in conn.execute(f'PRAGMA table_info("{PESSOAS}")')}
            if "CATEGORIA" in colunas_pessoas_atuais:
                # Ordem alfabetica nao tem nenhum significado real aqui --
                # ordena pela PRIMEIRA vez que cada categoria apareceu (menor
                # ID de pessoa), o que reproduz a ordem real de cadastro/
                # importacao (ex.: todo mundo importado como "Presidentes"
                # tinha ID menor que "Diretores Tecnicos" na planilha antiga).
                cur = conn.execute(
                    f'SELECT "CATEGORIA", MIN("ID") FROM "{PESSOAS}" '
                    f'WHERE "CATEGORIA" IS NOT NULL AND "CATEGORIA" != \'\' '
                    f'GROUP BY "CATEGORIA" ORDER BY MIN("ID")'
                )
                for valor, _primeiro_id in cur.fetchall():
                    nome = str(valor).strip()
                    if nome and nome.lower() not in vistos_lower:
                        nomes_categoria.append(nome)
                        vistos_lower.add(nome.lower())

        # 2) Cria cada categoria (preservando a ordem acima) e guarda o ID
        # gerado, indexado por nome em minusculo pra resolver o vinculo de
        # cada pessoa no passo seguinte independente de diferenca de caixa.
        ids_por_nome_lower: dict[str, int] = {}
        for posicao, nome in enumerate(nomes_categoria):
            cur = conn.execute(
                f'INSERT INTO {APP_CATEGORIAS} ("NOME", "ORDEM") VALUES (?, ?)', (nome, posicao)
            )
            ids_por_nome_lower[nome.lower()] = cur.lastrowid

        # 3) Vincula cada pessoa que ja tinha uma CATEGORIA preenchida a essa
        # categoria mestre correspondente.
        if PESSOAS in tabelas_existentes and ids_por_nome_lower:
            colunas_pessoas_atuais = {row[1] for row in conn.execute(f'PRAGMA table_info("{PESSOAS}")')}
            if "CATEGORIA" in colunas_pessoas_atuais:
                cur = conn.execute(
                    f'SELECT "ID", "CATEGORIA" FROM "{PESSOAS}" '
                    f'WHERE "CATEGORIA" IS NOT NULL AND "CATEGORIA" != \'\''
                )
                vinculos = [
                    (pessoa_id, ids_por_nome_lower[str(categoria).strip().lower()])
                    for pessoa_id, categoria in cur.fetchall()
                    if str(categoria).strip().lower() in ids_por_nome_lower
                ]
                conn.executemany(
                    f'INSERT OR IGNORE INTO {APP_PESSOAS_CATEGORIAS} ("PESSOA_ID", "CATEGORIA_ID") VALUES (?, ?)',
                    vinculos,
                )

    if PESSOAS in tabelas_existentes:
        colunas_pessoas_atuais = {row[1] for row in conn.execute(f'PRAGMA table_info("{PESSOAS}")')}
        if "FOTO" not in colunas_pessoas_atuais:
            # Bancos criados antes de existir foto de contato -- adiciona as
            # 2 colunas faltantes (comecam vazias pra todo mundo, estado
            # normal; ninguem tinha foto cadastrada antes dessa versao).
            conn.execute(f'ALTER TABLE "{PESSOAS}" ADD COLUMN "FOTO" BLOB')
            conn.execute(f'ALTER TABLE "{PESSOAS}" ADD COLUMN "FOTO_MIME" TEXT')
            mudou = True
        if "FOTO_ORIGINAL" not in colunas_pessoas_atuais:
            # Bancos criados antes de existir o arquivo original separado
            # do recorte (ver comentario acima de _DDL_PESSOAS) -- idem,
            # comeca vazio pra todo mundo.
            conn.execute(f'ALTER TABLE "{PESSOAS}" ADD COLUMN "FOTO_ORIGINAL" BLOB')
            conn.execute(f'ALTER TABLE "{PESSOAS}" ADD COLUMN "FOTO_ORIGINAL_MIME" TEXT')
            mudou = True

    if APP_LIXEIRA_REGISTROS not in tabelas_existentes:
        # Bancos criados antes de existir a Lixeira -- so cria as 3 tabelas
        # vazias (comecam sem nenhum item, estado normal; nada do que ja foi
        # excluido ANTES dessa versao pode ser recuperado retroativamente).
        conn.executescript(_DDL_LIXEIRA)
        mudou = True

    if mudou:
        conn.commit()
