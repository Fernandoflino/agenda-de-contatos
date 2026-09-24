"""
Este arquivo decide, pra cada CAMPO de um formulario (por exemplo, o campo
EMAIL de uma pessoa), que tipo de "caixinha" mostrar na tela: um campo de
texto comum, um campo com mascara de CPF, um seletor de data, uma lista de
opcoes (tipo Masculino/Feminino), etc. Isso faz o formulario ficar mais facil
de preencher certo (por exemplo, evita digitar uma data num formato errado).

Como o programa "adivinha" o tipo de um campo
-----------------------------------------------
Por padrao, ele usa uma lista de regras simples baseada no NOME do campo:
se o nome tiver "EMAIL" em algum lugar, vira campo de e-mail; se tiver
"CPF", vira campo de CPF; e assim por diante (veja a lista `_REGRAS` abaixo).
Isso e so um "chute inteligente" -- funciona bem na maioria dos casos sem
exigir nada do usuario.

Mas o usuario pode "corrigir" esse chute a qualquer momento, pela tela de
Configurar Campos: essa escolha manual fica guardada na tabela
app_field_types do banco de dados, e sempre tem prioridade sobre o chute
automatico (veja tipo_do_campo() abaixo).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date

from db.schema import APP_FIELD_TYPES

# Nomes dos tipos de campo que o programa entende. Sao usados tanto aqui
# quanto na tela de "Configurar Campos".
TEXTO = "texto"      # campo de texto comum, sem regra especial
EMAIL = "email"       # endereco de e-mail
TEL = "tel"           # telefone/WhatsApp, com mascara tipo (11) 91234-5678
CPF = "cpf"           # CPF, com mascara tipo 000.000.000-00
DATA = "data"         # data, mostrada com um calendario e formato dd/mm/aaaa
SELECAO = "selecao"   # lista fechada de opcoes (ex.: Masculino/Feminino)

TIPOS_VALIDOS = (TEXTO, EMAIL, TEL, CPF, DATA, SELECAO)

# Cada regra e (um padrao de texto a procurar no nome do campo, o tipo que
# isso sugere). A ordem importa: a primeira regra que "bater" e usada.
_REGRAS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^SEXO$", re.IGNORECASE), SELECAO),
    (re.compile(r"CPF", re.IGNORECASE), CPF),
    (re.compile(r"EMAIL", re.IGNORECASE), EMAIL),
    (re.compile(r"DATA", re.IGNORECASE), DATA),
    (re.compile(r"WHATSAPP|TELEFONE|FONE|CELULAR", re.IGNORECASE), TEL),
]

OPCOES_PADRAO_SEXO = ["Feminino", "Masculino"]

# Rotulos mais amigaveis pra campos conhecidos -- sem isso, o formulario
# mostraria o nome tecnico da coluna direto (ex.: "ID_EMPRESA"), que nao
# significa nada pra quem esta preenchendo o formulario.
_ROTULOS_CONHECIDOS = {
    "ID_EMPRESA": "Empresa",
    "SIGLA": "UF",
    "NOME DE GUERRA": "Nome de Guerra",
    "ASSESSOR(A)": "Assessor(a)",
    "WHATSAPP ASSESSOR": "WhatsApp do(a) Assessor(a)",
    "DATA DE NASCIMENTO": "Data de Nascimento",
    "CARGO2": "Cargo (2)",
    "SIGLA_EMPRESA": "Sigla da Empresa",
    "EMPRESA_MINUSCULA": "Empresa (por extenso)",
    "ÍNDICE ABEP": "Índice ABEP",
    "WHATSAPP": "WhatsApp",
    "CPF": "CPF",
    "EMAIL": "E-mail",
    # Campos "virtuais" que db/records.py calcula na hora de ler os dados
    # (nao sao colunas de verdade no banco) -- aparecem, por exemplo, na
    # tela de Configuracoes -> "Campos da lista" pra montar o cartao de um
    # jeito que mostre a empresa sem precisar decorar o numero do ID_EMPRESA.
    "_EMPRESA_SIGLA": "UF da Empresa",
    "_EMPRESA_SIGLA_EMPRESA": "Sigla da Empresa",
    "_EMPRESA_NOME": "Nome da Empresa",
    "_EMPRESA_BUSCA": "Empresa (busca)",
}

_CONECTORES_MINUSCULOS = {"de", "da", "do", "das", "dos", "e"}


def rotulo_amigavel(coluna: str) -> str:
    """Transforma o nome tecnico de uma coluna (ex.: "ID_EMPRESA", "NOME
    DE GUERRA") num rotulo mais natural pra mostrar num formulario.

    Campos conhecidos usam um rotulo escolhido a mao (_ROTULOS_CONHECIDOS);
    qualquer outro campo (incluindo os que o usuario criar depois) recebe um
    tratamento generico: troca "_" por espaco e capitaliza cada palavra,
    mantendo em minusculo os conectores comuns em portugues ("de", "da"...).
    """
    if coluna in _ROTULOS_CONHECIDOS:
        return _ROTULOS_CONHECIDOS[coluna]

    palavras = coluna.replace("_", " ").split()
    resultado = []
    for i, palavra in enumerate(palavras):
        minuscula = palavra.lower()
        if i > 0 and minuscula in _CONECTORES_MINUSCULOS:
            resultado.append(minuscula)
        else:
            resultado.append(palavra.title())
    return " ".join(resultado) if resultado else coluna


def mapear_tipo_campo(nome_coluna: str) -> str:
    """O "chute automatico": olha o nome do campo e devolve o tipo mais
    provavel, usando as regras de cima. Se nenhuma regra bater, o campo vira
    texto comum."""
    for padrao, tipo in _REGRAS:
        if padrao.search(nome_coluna):
            return tipo
    return TEXTO


def tipo_do_campo(conn: sqlite3.Connection, tabela: str, coluna: str) -> tuple[str, list[str] | None]:
    """Descobre o tipo EFETIVO de um campo: primeiro olha se o usuario
    configurou algo manualmente na tela de Configurar Campos (tabela
    app_field_types); se nao, usa o chute automatico por nome.

    Devolve (tipo, opcoes) -- `opcoes` so tem valor quando o tipo e SELECAO
    (a lista de opcoes que aparecem no menu suspenso).
    """
    row = conn.execute(
        f"SELECT tipo, opcoes FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = ?", (tabela, coluna)
    ).fetchone()
    if row:
        tipo, opcoes_json = row
        opcoes = None
        if opcoes_json:
            try:
                opcoes = json.loads(opcoes_json)
            except (json.JSONDecodeError, TypeError):
                opcoes = None
        return tipo, opcoes

    tipo = mapear_tipo_campo(coluna)
    opcoes = OPCOES_PADRAO_SEXO if tipo == SELECAO and coluna.upper() == "SEXO" else None
    return tipo, opcoes


def definir_tipo_campo(conn: sqlite3.Connection, tabela: str, coluna: str, tipo: str,
                        opcoes: list[str] | None = None) -> None:
    """Usado pela tela de Configurar Campos pra FORCAR um tipo especifico
    num campo, sobrescrevendo o chute automatico. `opcoes` so faz sentido
    quando `tipo` e SELECAO."""
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f'Tipo de campo inválido: "{tipo}".')
    opcoes_json = json.dumps(opcoes, ensure_ascii=False) if opcoes else None
    conn.execute(
        f"""INSERT INTO {APP_FIELD_TYPES} (tabela, coluna, tipo, opcoes) VALUES (?, ?, ?, ?)
            ON CONFLICT(tabela, coluna) DO UPDATE SET tipo = excluded.tipo, opcoes = excluded.opcoes""",
        (tabela, coluna, tipo, opcoes_json),
    )
    conn.commit()


def remover_tipo_campo(conn: sqlite3.Connection, tabela: str, coluna: str) -> None:
    """Desfaz uma configuracao manual, fazendo o campo voltar a usar o
    chute automatico por nome."""
    conn.execute(f"DELETE FROM {APP_FIELD_TYPES} WHERE tabela = ? AND coluna = ?", (tabela, coluna))
    conn.commit()


def mask_cpf(valor: str) -> str:
    """Formata um CPF progressivamente enquanto a pessoa digita, no padrao
    000.000.000-00 (ex.: "12345678900" vira "123.456.789-00")."""
    digitos = re.sub(r"\D", "", valor or "")[:11]  # \D = tudo que NAO e digito, ou seja, tira letras/simbolos
    partes = [digitos[0:3], digitos[3:6], digitos[6:9]]
    resultado = ".".join(p for p in partes if p)
    if len(digitos) > 9:
        resultado += "-" + digitos[9:11]
    return resultado


def formatar_data_exibicao(valor_iso: str | None) -> str:
    """Converte uma data guardada no banco (formato 'AAAA-MM-DD', que
    ordena certinho) pro formato que as pessoas no Brasil estao acostumadas
    a ler: 'DD/MM/AAAA'. Se o valor nao for uma data valida, devolve ele do
    jeito que veio, sem quebrar a tela."""
    if not valor_iso:
        return ""
    try:
        return date.fromisoformat(str(valor_iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(valor_iso)


def converter_data_para_iso(valor_exibido: str | None) -> str:
    """O caminho inverso de formatar_data_exibicao(): pega o que a pessoa
    digitou/escolheu na tela ('DD/MM/AAAA') e converte pro formato que o
    banco de dados guarda ('AAAA-MM-DD')."""
    if not valor_exibido:
        return ""
    valor_exibido = valor_exibido.strip()
    try:
        dia, mes, ano = valor_exibido.split("/")
        return date(int(ano), int(mes), int(dia)).isoformat()
    except (ValueError, IndexError):
        return valor_exibido


def mask_telefone(valor: str) -> str:
    """Formata um telefone/WhatsApp progressivamente enquanto a pessoa
    digita, no padrao brasileiro: (11) 91234-5678 (celular, 11 digitos) ou
    (11) 1234-5678 (fixo, 10 digitos)."""
    digitos = re.sub(r"\D", "", valor or "")[:11]
    if not digitos:
        return ""
    resultado = "(" + digitos[0:2]
    if len(digitos) > 2:
        resultado += ") " + digitos[2:7] if len(digitos) > 10 else ") " + digitos[2:6]
    if len(digitos) > 10:
        resultado += "-" + digitos[7:11]
    elif len(digitos) > 6:
        resultado += "-" + digitos[6:10]
    return resultado
