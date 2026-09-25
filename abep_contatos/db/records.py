"""
Este arquivo tem as operacoes basicas de "mexer nos dados" que qualquer
tabela precisa: criar uma linha nova, listar as linhas, editar uma linha
existente e apagar uma linha -- sempre identificando a linha pelo seu "ID"
(um numero unico que cada linha ganha automaticamente quando e criada).

Duas coisas especiais acontecem aqui, alem do CRUD basico (Criar, Ler,
Atualizar, Apagar):

1. Sempre que uma tabela tem uma coluna ID_EMPRESA (como PESSOAS tem), o
   programa automaticamente "traduz" esse numero pro nome/sigla da empresa
   correspondente, guardando em campos extras (_EMPRESA_SIGLA, _EMPRESA_NOME)
   que so existem na hora de EXIBIR os dados -- nao sao gravados no banco.

2. A tabela USUARIOS tem uma regra de seguranca especial: a senha de
   verdade (SENHA_HASH) nunca e devolvida pra tela, e quando alguem cria ou
   edita um usuario, o campo "SENHA" (digitado em texto puro) e convertido
   pro hash de seguranca ANTES de ser salvo -- ver db/auth.py pra entender
   como esse hash funciona.
"""
from __future__ import annotations

import sqlite3

from . import auth, lixeira, log
from .identifiers import quote_ident, validar_identificador
from .schema import APP_CATEGORIAS, APP_PESSOAS_CATEGORIAS, EMPRESAS, PESSOAS, USUARIOS
from .tables import get_schema


def resolver_empresas(conn: sqlite3.Connection) -> dict[int, dict]:
    """Monta um "dicionario" (tabela de consulta rapida) ID da empresa ->
    {sigla, sigla_empresa, empresa}, pra nao precisar consultar o banco de
    novo pra cada pessoa na hora de mostrar a empresa dela na tela.

    Repara que SIGLA e SIGLA_EMPRESA sao coisas DIFERENTES nos dados reais:
    SIGLA e a UF do estado (ex.: "RJ"), SIGLA_EMPRESA e a sigla da propria
    empresa (ex.: "PRODERJ") -- os dois sao uteis separadamente pra filtrar.
    """
    colunas = get_schema(conn, EMPRESAS)
    tem_sigla_empresa = "SIGLA_EMPRESA" in colunas
    campos_sql = '"ID", "SIGLA", "EMPRESA"' + (', "SIGLA_EMPRESA"' if tem_sigla_empresa else "")
    cur = conn.execute(f'SELECT {campos_sql} FROM "{EMPRESAS}"')
    resultado = {}
    for row in cur.fetchall():
        id_empresa, sigla, empresa = row[0], row[1], row[2]
        sigla_empresa = row[3] if tem_sigla_empresa else None
        resultado[id_empresa] = {"sigla": sigla, "sigla_empresa": sigla_empresa, "empresa": empresa}
    return resultado


def get_records(conn: sqlite3.Connection, tabela: str) -> list[dict]:
    """Devolve TODAS as linhas de uma tabela, cada uma como um dicionario
    {nome_da_coluna: valor} -- formato facil de usar tanto na tela quanto na
    exportacao.
    """
    tabela = validar_identificador(tabela, "tabela")
    colunas = get_schema(conn, tabela)
    if not colunas:
        return []

    cur = conn.execute(f"SELECT * FROM {quote_ident(tabela)}")
    registros = [dict(zip(colunas, linha)) for linha in cur.fetchall()]

    # Se a tabela tem ID_EMPRESA (e nao e a propria tabela EMPRESAS), busca o
    # nome/sigla de cada empresa e anexa nos dados, so pra exibicao.
    #
    # _EMPRESA_BUSCA junta sigla + nome num texto so -- e o campo usado pra
    # FILTRAR e ORDENAR por empresa na tela (ver ui/lista_registros_view.py):
    # filtrar pelo numero interno ID_EMPRESA nao faria sentido pra quem esta
    # usando o programa, que pensa em termos da sigla/nome da empresa.
    if "ID_EMPRESA" in colunas and tabela != EMPRESAS:
        empresas = resolver_empresas(conn)
        for r in registros:
            info = empresas.get(r.get("ID_EMPRESA"))
            if info:
                r["_EMPRESA_SIGLA"] = info["sigla"]
                r["_EMPRESA_SIGLA_EMPRESA"] = info["sigla_empresa"]
                r["_EMPRESA_NOME"] = info["empresa"]
                r["_EMPRESA_BUSCA"] = " ".join(
                    filter(None, [info["sigla"], info["sigla_empresa"], info["empresa"]])
                )

    # PESSOAS pode ter VARIAS categorias (relacao N:N -- ver db/categorias.py).
    # Busca todos os vinculos de uma vez so (1 JOIN, nao 1 consulta por
    # pessoa) e anexa em cada registro:
    # - CATEGORIAS: lista de nomes, fonte de verdade pro formulario/filtro/
    #   exportacao mesclada.
    # - CATEGORIA: as mesmas, juntas numa string "A, B" -- mantido so pra
    #   compatibilidade com os lugares que ainda leem esse campo como texto
    #   simples (coluna extra da tabela, exportacao simples, ordenacao).
    if tabela == PESSOAS:
        mapa_categorias: dict[int, list[str]] = {}
        cur_cat = conn.execute(f"""
            SELECT pc."PESSOA_ID", c."NOME"
            FROM {APP_PESSOAS_CATEGORIAS} pc
            JOIN {APP_CATEGORIAS} c ON c."ID" = pc."CATEGORIA_ID"
            ORDER BY c."ORDEM"
        """)
        for pessoa_id, nome in cur_cat.fetchall():
            mapa_categorias.setdefault(pessoa_id, []).append(nome)
        for r in registros:
            nomes = mapa_categorias.get(r.get("ID"), [])
            r["CATEGORIAS"] = nomes
            r["CATEGORIA"] = ", ".join(nomes)

    # Regra de seguranca: a senha (mesmo em hash) nunca deve chegar na tela.
    if tabela == USUARIOS:
        for r in registros:
            r.pop("SENHA_HASH", None)

    return registros


def get_record(conn: sqlite3.Connection, tabela: str, id_valor: int) -> dict | None:
    """Busca uma unica linha pelo ID. Devolve None se nao encontrar."""
    for r in get_records(conn, tabela):
        if r.get("ID") == id_valor:
            return r
    return None


def _preparar_dados_usuarios(conn: sqlite3.Connection, data: dict) -> dict:
    """Troca o campo "SENHA" (texto puro, vindo do formulario) pelo hash de
    seguranca "SENHA_HASH" antes de gravar -- e garante que ninguem consiga
    gravar um SENHA_HASH "na mao" vindo de fora."""
    data = dict(data)
    senha = data.pop("SENHA", None)
    data.pop("SENHA_HASH", None)
    if senha:
        pepper = auth.obter_pepper(conn)
        data["SENHA_HASH"] = auth.hash_senha(senha, pepper)
    return data


def create_record(conn: sqlite3.Connection, tabela: str, data: dict, usuario: str = "sistema") -> int:
    """Cria uma linha nova. `data` e um dicionario {nome_do_campo: valor} --
    campos que nao vierem em `data` ficam em branco. Devolve o ID que o
    SQLite gerou automaticamente pra essa linha nova (proximo numero livre).
    """
    tabela = validar_identificador(tabela, "tabela")
    colunas = get_schema(conn, tabela)
    if not colunas:
        raise ValueError(f'Tabela "{tabela}" nao encontrada.')

    if tabela == USUARIOS:
        if not data.get("USUARIO") or not (data.get("SENHA")):
            raise ValueError("Informe USUARIO e SENHA.")
        data = _preparar_dados_usuarios(conn, data)

    # Nunca inserimos o campo "ID" na mao -- o SQLite gera o proximo numero
    # livre sozinho, porque a coluna ID foi criada como INTEGER PRIMARY KEY.
    campos = [c for c in colunas if c != "ID" and c in data]
    valores = [data[c] for c in campos]
    placeholders = ", ".join("?" for _ in campos)
    campos_sql = ", ".join(quote_ident(c) for c in campos)

    if campos:
        cur = conn.execute(
            f"INSERT INTO {quote_ident(tabela)} ({campos_sql}) VALUES ({placeholders})", valores
        )
    else:
        cur = conn.execute(f"INSERT INTO {quote_ident(tabela)} DEFAULT VALUES")
    conn.commit()

    novo_id = cur.lastrowid
    rotulo = data.get("NOME") or data.get("EMPRESA") or str(novo_id)
    # O "(ID N)" no final permite achar essa linha do historico depois, na
    # tela de detalhes de UM registro especifico -- ver db/log.py ->
    # historico_do_registro().
    log.log_change(conn, usuario, tabela, "Criar registro", f"{rotulo} (ID {novo_id})")
    return novo_id


def update_record(conn: sqlite3.Connection, tabela: str, id_valor: int, data: dict, usuario: str = "sistema") -> None:
    """Atualiza os campos informados em `data` de uma linha ja existente
    (identificada pelo ID). Campos que nao aparecem em `data` permanecem
    como estavam -- ou seja, e uma atualizacao "parcial", nao precisa mandar
    a linha inteira de novo."""
    tabela = validar_identificador(tabela, "tabela")
    colunas = get_schema(conn, tabela)
    if not colunas:
        raise ValueError(f'Tabela "{tabela}" nao encontrada.')

    if tabela == USUARIOS:
        data = _preparar_dados_usuarios(conn, data)

    campos = [c for c in colunas if c != "ID" and c in data]
    if not campos:
        return
    set_sql = ", ".join(f"{quote_ident(c)} = ?" for c in campos)
    valores = [data[c] for c in campos] + [id_valor]

    cur = conn.execute(f'UPDATE {quote_ident(tabela)} SET {set_sql} WHERE "ID" = ?', valores)
    if cur.rowcount == 0:
        raise ValueError(f'Registro com ID "{id_valor}" nao encontrado em "{tabela}".')
    conn.commit()
    log.log_change(conn, usuario, tabela, "Editar registro", f"ID {id_valor}")


def delete_record(conn: sqlite3.Connection, tabela: str, id_valor: int, usuario: str = "sistema") -> None:
    """Manda uma linha pra lixeira e so entao apaga ela de verdade -- ver
    db/lixeira.py::capturar_registro (guarda a "foto" antes do DELETE) e a
    tela de Configuracoes -> Lixeira (pra restaurar)."""
    tabela = validar_identificador(tabela, "tabela")
    lixeira.capturar_registro(conn, tabela, id_valor, usuario)
    cur = conn.execute(f'DELETE FROM {quote_ident(tabela)} WHERE "ID" = ?', (id_valor,))
    if cur.rowcount == 0:
        raise ValueError(f'Registro com ID "{id_valor}" nao encontrado em "{tabela}".')
    conn.commit()
    log.log_change(conn, usuario, tabela, "Excluir registro", f"ID {id_valor}")


def filtrar_registros(registros: list[dict], busca: str = "", campo: str | None = None,
                       valor: str = "") -> list[dict]:
    """Filtra uma lista de registros JA CARREGADA (nao faz nova consulta ao
    banco) -- e assim que a busca da lista de contatos e a exportacao filtram
    os dados, porque a quantidade de registros e pequena o suficiente pra
    isso ser instantaneo.

    - `busca`: procura o texto em QUALQUER campo do registro (busca livre).
    - `campo` + `valor`: restringe so aos registros onde aquele campo
      especifico contem o texto procurado (ex.: CARGO contem "Diretor").

    Os dois filtros podem ser usados ao mesmo tempo (um registro so passa se
    bater nos dois).
    """
    resultado = registros

    if campo and valor:
        alvo = str(valor).strip().lower()
        resultado = [r for r in resultado if alvo in str(r.get(campo, "") or "").lower()]

    if busca:
        alvo = busca.strip().lower()
        if alvo:
            # "not k.startswith('_')" ignora os campos calculados (tipo
            # _EMPRESA_SIGLA) que ja sao so uma copia de outra informacao.
            resultado = [
                r for r in resultado
                if any(alvo in str(v or "").lower() for k, v in r.items() if not k.startswith("_"))
            ]

    return resultado
