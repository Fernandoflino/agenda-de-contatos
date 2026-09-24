"""
Este arquivo cuida das PREFERENCIAS PERSONALIZAVEIS que ficam guardadas
DENTRO do proprio arquivo .abepdb -- ou seja, se o usuario mudar o nome do
painel, o logotipo, a cor de destaque, ou quais campos aparecem resumidos na
lista de contatos, tudo isso viaja junto quando o arquivo e copiado ou movido
pra outro computador (assim como o pepper de senha em db/auth.py).

Isso segue o pedido do usuario de que "tudo tem que ser personalizavel": em
vez de deixar essas escolhas fixas no codigo do programa, elas ficam salvas
como dado, e uma tela de Configuracoes (ui/settings_dialog.py) deixa o
usuario mudar cada uma delas.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from .schema import APP_BRANDING, APP_LIST_DISPLAY, APP_TABLE_LABELS, PESSOAS

# Valores usados enquanto o usuario ainda nao personalizou nada.
NOME_PADRAO = "Painel de Contatos"
COR_PADRAO = "#2563eb"  # um azul neutro, usado como cor de destaque padrao
TEMA_CLARO = "claro"
TEMA_ESCURO = "escuro"
TEMA_PADRAO = TEMA_CLARO

# --- Sugestao automatica de quais campos resumir numa lista/card ---
# (usada como PONTO DE PARTIDA em obter_campos_resumo(), antes do usuario
# configurar algo manualmente na tela de Configuracoes)
#
# Campos "de baixo valor" pra aparecer resumido -- sao dados tecnicos ou
# sensiveis (ID interno, CPF, data, campos extras tipo CP1/CP2...) que fazem
# mais sentido so na ficha completa do que numa lista rapida de contatos.
_PADROES_SECUNDARIOS = [
    re.compile(r"^ID$", re.IGNORECASE),
    # ID_EMPRESA nunca precisa ser sugerido como campo-resumo "comum" -- a
    # tela de lista (ui/lista_registros_view.py) ja sempre mostra a empresa
    # numa linha propria, separada dos campos-resumo escolhidos aqui.
    re.compile(r"^ID_EMPRESA$", re.IGNORECASE),
    re.compile(r"^CPF$", re.IGNORECASE),
    re.compile(r"^SEXO$", re.IGNORECASE),
    re.compile(r"^DATA", re.IGNORECASE),
    re.compile(r"^CP\d+$", re.IGNORECASE),
    # SENHA_HASH nunca deve ser sugerido -- o valor ja e removido dos dados
    # antes de chegar na tela (ver db/records.py), entao mostrar isso como
    # opcao de campo-resumo so confundiria/preocuparia sem necessidade.
    re.compile(r"^SENHA", re.IGNORECASE),
]

# Palavras que costumam identificar, so de bater o olho, do que se trata um
# registro -- em ordem de prioridade (a primeira que aparecer no nome de uma
# coluna "ganha" um lugar no resumo primeiro).
_PALAVRAS_CHAVE_RESUMO = [
    "NOME DE GUERRA", "NOME", "CATEGORIA", "CARGO", "TRATAMENTO", "EMPRESA", "SIGLA",
    "EMAIL", "WHATSAPP", "TELEFONE", "FONE",
]


@dataclass
class Branding:
    """Agrupa nome, cor, logotipo e tema configurados -- devolvido por obter_branding()."""
    nome: str
    cor_destaque: str
    logo: bytes | None       # bytes "crus" da imagem (formato PNG), ou None se nao configurado
    logo_mime: str | None    # tipo da imagem (ex.: "image/png"), pra saber como exibi-la
    tema: str                # TEMA_CLARO ou TEMA_ESCURO


def obter_branding(conn: sqlite3.Connection) -> Branding:
    """Le a identidade visual configurada neste banco (nome/cor/logotipo/tema).

    Se nada foi configurado ainda, devolve os valores padrao -- assim a tela
    de login e a janela principal sempre tem algo pra mostrar.
    """
    row = conn.execute(
        f"SELECT nome, cor_destaque, logo, logo_mime, tema FROM {APP_BRANDING} WHERE id = 1"
    ).fetchone()
    if not row:
        return Branding(nome=NOME_PADRAO, cor_destaque=COR_PADRAO, logo=None, logo_mime=None, tema=TEMA_PADRAO)
    nome, cor, logo, logo_mime, tema = row
    tema = tema if tema in (TEMA_CLARO, TEMA_ESCURO) else TEMA_PADRAO
    return Branding(nome=nome or NOME_PADRAO, cor_destaque=cor or COR_PADRAO, logo=logo, logo_mime=logo_mime, tema=tema)


def salvar_branding(conn: sqlite3.Connection, nome: str | None = None, cor_destaque: str | None = None,
                     logo: bytes | None = None, logo_mime: str | None = None,
                     limpar_logo: bool = False, tema: str | None = None) -> None:
    """Atualiza a identidade visual. So muda o que for passado -- por exemplo,
    salvar_branding(conn, nome="ABEP-TIC") muda so o nome, mantendo a cor, o
    logotipo e o tema como estavam antes.
    """
    atual = obter_branding(conn)
    novo_nome = nome if nome is not None else atual.nome
    nova_cor = cor_destaque if cor_destaque is not None else atual.cor_destaque
    novo_tema = tema if tema in (TEMA_CLARO, TEMA_ESCURO) else atual.tema
    if limpar_logo:
        novo_logo, novo_mime = None, None
    elif logo is not None:
        novo_logo, novo_mime = logo, logo_mime
    else:
        novo_logo, novo_mime = atual.logo, atual.logo_mime

    # "ON CONFLICT ... DO UPDATE" e o jeito do SQL de dizer: "se essa linha ja
    # existir, so atualiza ela em vez de dar erro por duplicidade".
    conn.execute(
        f"""INSERT INTO {APP_BRANDING} (id, nome, cor_destaque, logo, logo_mime, tema) VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, cor_destaque = excluded.cor_destaque,
                logo = excluded.logo, logo_mime = excluded.logo_mime, tema = excluded.tema""",
        (novo_nome, nova_cor, novo_logo, novo_mime, novo_tema),
    )
    conn.commit()


def obter_campos_resumo(conn: sqlite3.Connection, tabela: str, padrao: list[list[str]]) -> list[list[str]]:
    """O "layout" do cartao de um registro nessa tabela: uma LISTA DE LINHAS,
    cada linha sendo uma lista dos campos que aparecem juntos nela (ex.:
    [["NOME"], ["CATEGORIA", "CARGO"]] = 2 linhas, a segunda com 2 campos
    separados por " · "). Configurado na tela de Configuracoes -> "Campos da
    lista" (editor de arrastar-e-soltar, ver ui/settings_dialog.py).

    Se o usuario ainda nao escolheu nada, usa o `padrao` (calculado
    automaticamente -- veja sugerir_layout_resumo() logo abaixo).
    """
    row = conn.execute(
        f"SELECT campos_resumo FROM {APP_LIST_DISPLAY} WHERE tabela = ?", (tabela,)
    ).fetchone()
    if not row or not row[0]:
        return padrao
    try:
        campos = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return padrao

    if not isinstance(campos, list) or not campos:
        return padrao

    if isinstance(campos[0], str):
        # Formato ANTIGO (de antes de existir a nocao de "linhas"): uma
        # lista simples de campos, tipo ["NOME", "CARGO", "EMAIL"]. Convertida
        # aqui pro formato novo -- cada campo antigo vira sua propria linha,
        # preservando a ordem que a pessoa ja tinha escolhido.
        return [[c] for c in campos]

    return campos


def sugerir_layout_resumo(colunas: list[str], max_campos: int = 5) -> list[list[str]]:
    """Calcula um layout de cartao automatico, so olhando os NOMES das
    colunas disponiveis -- sem precisar de nenhuma configuracao manual.

    O resultado tenta parecer com o que o programa sempre mostrou por
    padrao: 1 linha com a empresa (quando a tabela tiver ID_EMPRESA), 1 linha
    so com o campo mais "identificador" (NOME, de preferencia), e 1 ultima
    linha juntando os proximos campos mais uteis (cargo, e-mail, whatsapp...).
    Isso e so o PONTO DE PARTIDA -- o usuario pode reorganizar tudo (inclusive
    o numero de linhas) na tela de Configuracoes.
    """
    tem_empresa = "ID_EMPRESA" in colunas
    candidatos = [c for c in colunas if not any(p.search(c) for p in _PADROES_SECUNDARIOS)]
    if not candidatos:
        candidatos = [c for c in colunas if c not in ("ID", "ID_EMPRESA")]

    escolhidos: list[str] = []
    for palavra in _PALAVRAS_CHAVE_RESUMO:
        if len(escolhidos) >= max_campos:
            break
        achado = next((c for c in candidatos if palavra in c.upper() and c not in escolhidos), None)
        if achado:
            escolhidos.append(achado)

    for c in candidatos:
        if len(escolhidos) >= max_campos:
            break
        if c not in escolhidos:
            escolhidos.append(c)

    if not escolhidos:
        escolhidos = list(candidatos[:max_campos]) or list(colunas[:max_campos])

    linhas: list[list[str]] = []
    if tem_empresa:
        linhas.append(["_EMPRESA_SIGLA", "_EMPRESA_SIGLA_EMPRESA", "_EMPRESA_NOME"])
    if escolhidos:
        linhas.append([escolhidos[0]])
    if len(escolhidos) > 1:
        linhas.append(escolhidos[1:])

    return linhas


def salvar_campos_resumo(conn: sqlite3.Connection, tabela: str, linhas: list[list[str]]) -> None:
    """Grava o layout de cartao (lista de linhas) escolhido pro usuario pra
    essa tabela."""
    conn.execute(
        f"""INSERT INTO {APP_LIST_DISPLAY} (tabela, campos_resumo) VALUES (?, ?)
            ON CONFLICT(tabela) DO UPDATE SET campos_resumo = excluded.campos_resumo""",
        (tabela, json.dumps(linhas, ensure_ascii=False)),
    )
    conn.commit()


# --- Rotulo de exibicao de cada tabela (separado do nome real no banco) ---
#
# EMPRESAS, PESSOAS e USUARIOS nao podem ser RENOMEADAS de verdade (varias
# partes do programa contam com esse nome exato -- ver db/tables.py) -- mas
# o usuario ainda pode querer que o menu lateral mostre outro nome, ou
# controlar a ORDEM das tabelas ali (ex.: prefixando com numeros, tipo
# "01 - Contatos", "02 - Empresas"). O rotulo resolve isso sem mexer na
# estrutura real da tabela.

_ROTULO_PADRAO_PESSOAS = "Contatos"


def obter_rotulo_tabela(conn: sqlite3.Connection, tabela: str) -> str:
    """Nome de exibicao de uma tabela no menu lateral. Se nada foi
    configurado, PESSOAS aparece como "Contatos" (comportamento de sempre) e
    qualquer outra tabela aparece com o proprio nome dela."""
    row = conn.execute(f"SELECT rotulo FROM {APP_TABLE_LABELS} WHERE tabela = ?", (tabela,)).fetchone()
    if row and row[0]:
        return row[0]
    return _ROTULO_PADRAO_PESSOAS if tabela == PESSOAS else tabela


def definir_rotulo_tabela(conn: sqlite3.Connection, tabela: str, rotulo: str) -> None:
    """Define um apelido de exibicao pra tabela. Passar `rotulo` vazio volta
    a usar o padrao (nome da propria tabela, ou "Contatos" pra PESSOAS)."""
    rotulo = (rotulo or "").strip()
    if not rotulo:
        conn.execute(f"DELETE FROM {APP_TABLE_LABELS} WHERE tabela = ?", (tabela,))
    else:
        conn.execute(
            f"""INSERT INTO {APP_TABLE_LABELS} (tabela, rotulo) VALUES (?, ?)
                ON CONFLICT(tabela) DO UPDATE SET rotulo = excluded.rotulo""",
            (tabela, rotulo),
        )
    conn.commit()
