"""
Este arquivo cuida de EXPORTAR dados pra um arquivo .xlsx (Excel) ou .csv,
pra uso fora do programa (mala direta, planilhas de apoio etc.).

Existem dois "modos" de exportacao:

1. Modo SIMPLES: uma linha por registro (por pessoa, por empresa, etc.),
   podendo filtrar e escolher quais colunas entram. E o caso de uso mais
   comum -- por exemplo, "so os Diretores Tecnicos, com nome/email/telefone".

2. Modo MESCLADO POR EMPRESA: recria o antigo formato de "uma linha por
   empresa, com Presidente e Diretor lado a lado em colunas diferentes" --
   so que agora, em vez de escolher ABAS pra juntar (que nao existem mais
   separadas), o usuario escolhe VALORES DE CARGO como "encaixes" (ex.:
   "Presidente", "Diretor Tecnico"). Se uma empresa tiver mais de uma pessoa
   no mesmo cargo escolhido, a linha da empresa se repete uma vez pra cada
   combinacao possivel, em vez de perder gente por causa do layout fixo de
   colunas -- foi exatamente esse problema (uma empresa com 2 diretores
   tecnicos) que motivou abandonar as 3 tabelas fixas por cargo.
"""
from __future__ import annotations

import csv
import itertools
import sqlite3

import openpyxl

from .records import filtrar_registros, get_records, resolver_empresas
from .schema import EMPRESAS
from .tables import get_column_order, get_schema

# ID_EMPRESA e um numero interno do banco -- nao significa nada num arquivo
# exportado (mala direta, planilha de apoio). Em toda exportacao ele e
# trocado pelas colunas de verdade da empresa (SIGLA e EMPRESA), na mesma
# posicao em que ID_EMPRESA apareceria -- assim quem abrir o Excel ve o nome
# da empresa, nao um numero sem sentido. SIGLA (UF do estado) e SIGLA_EMPRESA
# (sigla da propria empresa, ex.: "PRODERJ") sao coisas diferentes -- as duas
# entram separadas, pra poder filtrar/organizar por qualquer uma delas.
_MAPA_CAMPO_EMPRESA = {
    "SIGLA": "_EMPRESA_SIGLA",
    "SIGLA_EMPRESA": "_EMPRESA_SIGLA_EMPRESA",
    "EMPRESA": "_EMPRESA_NOME",
}


def _valor_celula(valor):
    """Converte um valor pro formato de uma celula de planilha -- uma lista
    (ex.: CATEGORIAS, que uma pessoa pode ter varias) vira texto juntando os
    itens com virgula, em vez de ser escrita "crua" numa celula."""
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor)
    return valor


def colunas_exportaveis(conn: sqlite3.Connection, tabela: str) -> tuple[list[str], dict[str, str]]:
    """Lista de colunas oferecidas pra exportacao, na ordem de exibicao --
    com ID_EMPRESA ja trocado por SIGLA/EMPRESA quando a tabela tiver essa
    ligacao. Usada tanto aqui (pra montar as linhas exportadas) quanto pela
    tela de exportacao (pra montar a lista de checkboxes de colunas).

    Devolve (lista_de_colunas, mapa_fonte) -- mapa_fonte so tem entrada pras
    colunas que sao SUBSTITUTAS de ID_EMPRESA (diz de qual campo calculado,
    tipo "_EMPRESA_SIGLA", tirar o valor de verdade). Isso evita confundir
    essas colunas substitutas com uma coluna "SIGLA"/"EMPRESA" DE VERDADE que
    a propria tabela EMPRESAS ja tem (nesse caso, o valor vem dela mesma).
    """
    schema_ordenado = get_column_order(conn, tabela)
    tem_empresa = "ID_EMPRESA" in get_schema(conn, tabela) and tabela != EMPRESAS

    disponiveis = []
    mapa_fonte = {}
    for coluna in schema_ordenado:
        if coluna == "ID_EMPRESA":
            if tem_empresa:
                for nome_coluna, campo_fonte in _MAPA_CAMPO_EMPRESA.items():
                    if nome_coluna not in disponiveis:
                        disponiveis.append(nome_coluna)
                        mapa_fonte[nome_coluna] = campo_fonte
            continue
        if coluna in ("FOTO", "FOTO_MIME"):
            # Foto e um BLOB -- nao faz sentido nenhum numa celula de
            # planilha (viraria bytes crus ou quebraria o arquivo gerado).
            continue
        disponiveis.append(coluna)
    return disponiveis, mapa_fonte


def montar_exportacao_simples(conn: sqlite3.Connection, tabela: str,
                               campos_selecionados: list[str] | None = None,
                               filtro_campo: str | None = None,
                               filtro_valor: str = "",
                               busca: str = "",
                               ids_permitidos: set[int] | None = None) -> tuple[list[str], list[dict]]:
    """Prepara os dados do modo SIMPLES: devolve (colunas, linhas), ja
    filtrados e com so as colunas escolhidas -- pronto pra passar direto pra
    exportar_xlsx()/exportar_csv() logo abaixo.

    `ids_permitidos`, quando informado, restringe a exportacao a SO esses
    IDs (ex.: "Exportar selecionados" na lista de registros) -- os outros
    filtros (busca, filtro_campo/filtro_valor) continuam valendo junto.
    """
    registros = get_records(conn, tabela)
    if ids_permitidos is not None:
        registros = [r for r in registros if r["ID"] in ids_permitidos]
    registros = filtrar_registros(registros, busca=busca, campo=filtro_campo, valor=filtro_valor)

    disponiveis, mapa_fonte = colunas_exportaveis(conn, tabela)
    columns = campos_selecionados if campos_selecionados else disponiveis
    columns = [c for c in columns if c in disponiveis]  # ignora nomes invalidos, por seguranca

    rows = []
    for r in registros:
        linha = {}
        for c in columns:
            campo_fonte = mapa_fonte.get(c, c)
            linha[c] = _valor_celula(r.get(campo_fonte, ""))
        rows.append(linha)
    return columns, rows


def montar_exportacao_mesclada(conn: sqlite3.Connection, tabela_pessoas: str,
                                valores_agrupador: list[str],
                                campo_agrupador: str = "CATEGORIA",
                                campos_por_valor: dict[str, list[str]] | None = None,
                                campos_empresa: list[str] | None = None,
                                filtro_campo: str | None = None,
                                filtro_valor: str = "",
                                ids_permitidos: set[int] | None = None) -> tuple[list[str], list[dict]]:
    """Prepara os dados do modo MESCLADO: uma linha por empresa, com um
    "bloco" de colunas pra cada "encaixe" escolhido em `valores_agrupador`
    (na ordem dada), recriando o antigo formato de mala direta por aba.

    `campo_agrupador` decide QUAL campo define os encaixes -- o padrao e
    CATEGORIA (a etiqueta que diz de qual aba da planilha antiga a pessoa
    veio: "Presidentes", "Diretores Tecnicos" etc.), mas pode ser trocado
    por CARGO ou qualquer outro campo, se fizer mais sentido pro caso de uso.
    `campos_por_valor` deixa escolher quais campos de cada pessoa entram em
    cada encaixe (se nao informado, usa todos os campos disponiveis).
    """
    campos_empresa = campos_empresa if campos_empresa is not None else ["SIGLA", "SIGLA_EMPRESA", "EMPRESA"]
    registros = get_records(conn, tabela_pessoas)
    if ids_permitidos is not None:
        registros = [r for r in registros if r["ID"] in ids_permitidos]
    registros = filtrar_registros(registros, campo=filtro_campo, valor=filtro_valor)
    empresas = resolver_empresas(conn)
    empresas_completas = {r["ID"]: r for r in get_records(conn, EMPRESAS)}

    def _campos_do_valor(valor: str) -> list[str]:
        campos = campos_por_valor.get(valor) if campos_por_valor else None
        if not campos:
            campos = [c for c in registros[0].keys() if not c.startswith("_")] if registros else []
        # Campos cujo valor e uma LISTA (ex.: CATEGORIAS, ja que uma pessoa
        # pode ter varias) nao entram automaticamente num bloco de encaixe --
        # escreve-los exigiria juntar o valor primeiro (ver _valor_celula),
        # e nao fazem sentido repetidos em cada bloco de qualquer forma.
        return [
            c for c in campos
            if c not in ("ID_EMPRESA", campo_agrupador)
            and not isinstance((registros[0] if registros else {}).get(c), list)
        ]

    # So entram na exportacao as empresas que realmente tem pelo menos uma
    # pessoa entre os registros filtrados (mesma logica do sistema antigo).
    empresas_presentes = []
    vistos = set()
    for r in registros:
        eid = r.get("ID_EMPRESA")
        if eid is not None and eid not in vistos and eid in empresas:
            vistos.add(eid)
            empresas_presentes.append(eid)

    # Monta a lista de colunas final: primeiro os dados da empresa, depois
    # um bloco "NomeDoEncaixe - Campo" pra cada valor escolhido.
    columns = list(campos_empresa)
    for valor in valores_agrupador:
        for campo in _campos_do_valor(valor):
            columns.append(f"{valor} - {campo}")

    rows: list[dict] = []
    for eid in empresas_presentes:
        # Pra cada encaixe escolhido, junta a lista de pessoas dessa empresa
        # que batem com aquele valor. Se nao tiver ninguem, usamos [None]
        # pra ainda assim gerar uma linha (com aquele bloco em branco).
        listas_por_slot = []
        for valor in valores_agrupador:
            if campo_agrupador == "CATEGORIA":
                # Uma pessoa pode ter VARIAS categorias agora -- ela entra em
                # TODOS os encaixes que bater, nao só num (diferente de
                # CARGO ou outro agrupador, que continua comparando um valor
                # escalar so).
                alvo = valor.strip().lower()
                pessoas_do_slot = [
                    r for r in registros
                    if r.get("ID_EMPRESA") == eid
                    and alvo in {str(c).strip().lower() for c in (r.get("CATEGORIAS") or [])}
                ]
            else:
                pessoas_do_slot = [
                    r for r in registros
                    if r.get("ID_EMPRESA") == eid
                    and str(r.get(campo_agrupador, "") or "").strip().lower() == valor.strip().lower()
                ]
            listas_por_slot.append(pessoas_do_slot or [None])

        # itertools.product gera todas as combinacoes possiveis entre os
        # encaixes -- por exemplo, se uma empresa tem 1 presidente e 2
        # diretores tecnicos, isso gera 2 linhas (presidente + diretor 1,
        # presidente + diretor 2), garantindo que ninguem fique de fora.
        for combinacao in itertools.product(*listas_por_slot):
            linha = {}
            empresa_row = empresas_completas.get(eid, {})
            for campo in campos_empresa:
                linha[campo] = empresa_row.get(campo, "")

            for valor, pessoa in zip(valores_agrupador, combinacao):
                for campo in _campos_do_valor(valor):
                    linha[f"{valor} - {campo}"] = _valor_celula((pessoa or {}).get(campo, ""))

            rows.append(linha)

    return columns, rows


def exportar_xlsx(columns: list[str], rows: list[dict], caminho: str) -> None:
    """Grava (colunas, linhas) num arquivo .xlsx de verdade, pronto pra abrir
    no Excel/LibreOffice -- a primeira linha do arquivo vira o cabecalho."""
    if not rows:
        raise ValueError("Nenhum registro para exportar.")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(columns)
    for r in rows:
        ws.append([r.get(c, "") for c in columns])
    wb.save(caminho)


def exportar_csv(columns: list[str], rows: list[dict], caminho: str) -> None:
    """Grava (colunas, linhas) num arquivo .csv (texto separado por virgulas),
    formato simples e aceito por praticamente qualquer programa de planilha."""
    if not rows:
        raise ValueError("Nenhum registro para exportar.")
    # "utf-8-sig" adiciona uma marca no inicio do arquivo que faz o Excel
    # reconhecer acentos corretamente ao abrir o CSV no Windows.
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(columns)
        for r in rows:
            writer.writerow([r.get(c, "") for c in columns])
