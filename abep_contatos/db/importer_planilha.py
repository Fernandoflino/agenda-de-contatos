"""
Este arquivo cuida de IMPORTAR uma planilha .xlsx/.csv no MESMO formato que o
programa exporta (modo "Simples" de db/exporter.py -- uma linha por
registro) de volta pro banco, adicionando quem e novo e atualizando quem ja
existe.

Diferente de db/importer.py (que resolve um problema diferente: trazer uma
planilha antiga de mala direta, com uma aba por cargo, pra dentro de um
banco novo -- sempre criando, nunca atualizando), aqui a decisao de
"criar ou atualizar" e feita pela coluna ID que a propria exportacao ja
inclui: linha com ID em branco vira registro novo; linha com ID que already
existe no banco atualiza esse registro; linha com ID que nao existe mais
(ex.: foi apagado depois da exportacao) tambem vira um registro novo, com um
aviso no resumo final.

Celula em branco ao atualizar APAGA o valor que ja existia -- a planilha
reimportada vale como fonte da verdade pras colunas que ela contem.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import sqlite3
from dataclasses import dataclass, field

import openpyxl

from . import categorias, records, tables
from .schema import EMPRESAS, PESSOAS

_CAMPOS_EMPRESA = ["SIGLA", "SIGLA_EMPRESA", "EMPRESA"]


def _valor_celula(v):
    """Converte o valor "cru" de uma celula (vindo do openpyxl) pro formato
    que o banco espera -- mesma regra de db/importer.py::_valor_celula."""
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.date().isoformat() if isinstance(v, _dt.datetime) else v.isoformat()
    if isinstance(v, str):
        return v.strip()
    if v is None:
        return ""
    return v


def _ler_xlsx(caminho: str) -> tuple[list[str], list[dict]]:
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        ws = wb.active
        linhas_brutas = ws.iter_rows(values_only=True)
        cabecalho = [str(v).strip() if v is not None else "" for v in next(linhas_brutas, ())]
        linhas = []
        for linha_bruta in linhas_brutas:
            registro = {c: _valor_celula(v) for c, v in zip(cabecalho, linha_bruta) if c}
            if any(v not in (None, "") for v in registro.values()):
                linhas.append(registro)
        return cabecalho, linhas
    finally:
        wb.close()


def _ler_csv(caminho: str) -> tuple[list[str], list[dict]]:
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        leitor = csv.reader(f)
        cabecalho = [c.strip() for c in next(leitor, [])]
        linhas = []
        for linha_bruta in leitor:
            registro = {c: v.strip() for c, v in zip(cabecalho, linha_bruta) if c}
            if any(v not in (None, "") for v in registro.values()):
                linhas.append(registro)
        return cabecalho, linhas


def ler_planilha(caminho: str) -> tuple[list[str], list[dict]]:
    """Le um arquivo .xlsx ou .csv (pela extensao) e devolve (cabecalho,
    linhas), no mesmo formato que importar_planilha() espera."""
    extensao = os.path.splitext(caminho)[1].lower()
    if extensao == ".xlsx":
        return _ler_xlsx(caminho)
    if extensao == ".csv":
        return _ler_csv(caminho)
    raise ValueError(f'Formato de arquivo nao suportado: "{extensao}". Use .xlsx ou .csv.')


@dataclass
class ResumoImportacaoPlanilha:
    """Resultado de uma importacao, pra mostrar um resumo pro usuario."""
    criados: int = 0
    atualizados: int = 0
    empresas_criadas: int = 0
    colunas_novas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _chave_empresa(linha: dict, campos_empresa: list[str]) -> tuple:
    return tuple(str(linha.get(c) or "").strip().lower() for c in campos_empresa)


def importar_planilha(conn: sqlite3.Connection, tabela: str, columns: list[str], rows: list[dict],
                       usuario: str = "sistema", aplicar: bool = True) -> ResumoImportacaoPlanilha:
    resumo = ResumoImportacaoPlanilha()

    existentes = set(tables.get_schema(conn, tabela))
    tem_empresa = tabela != EMPRESAS and "ID_EMPRESA" in existentes
    campos_empresa = [c for c in _CAMPOS_EMPRESA if c in columns] if tem_empresa else []
    tem_categoria = tabela == PESSOAS and "CATEGORIA" in columns

    for coluna in columns:
        if coluna and coluna != "ID" and coluna not in campos_empresa and coluna not in existentes:
            resumo.colunas_novas.append(coluna)
            if aplicar:
                tables.add_column(conn, tabela, coluna, usuario=usuario)
            existentes.add(coluna)

    # Cache empresa (nova ou ja existente) resolvida a partir de
    # SIGLA/SIGLA_EMPRESA/EMPRESA -> ID_EMPRESA, pra nao criar a mesma
    # empresa nova duas vezes dentro da mesma importacao.
    cache_empresas: dict[tuple, int | None] = {}
    if campos_empresa:
        for id_empresa, info in records.resolver_empresas(conn).items():
            mapa = {"SIGLA": info["sigla"], "SIGLA_EMPRESA": info["sigla_empresa"], "EMPRESA": info["empresa"]}
            chave = tuple(str(mapa[c] or "").strip().lower() for c in campos_empresa)
            cache_empresas[chave] = id_empresa

    for linha in rows:
        id_bruto = str(linha.get("ID") or "").strip()
        campos_excluidos_de_dados = set(campos_empresa)
        if tem_categoria:
            campos_excluidos_de_dados.add("CATEGORIA")
        dados = {c: linha.get(c, "") for c in columns if c != "ID" and c not in campos_excluidos_de_dados}

        if campos_empresa:
            chave = _chave_empresa(linha, campos_empresa)
            if chave not in cache_empresas:
                resumo.empresas_criadas += 1
                novo_id = None
                if aplicar:
                    dados_empresa = {c: linha.get(c, "") for c in campos_empresa}
                    novo_id = records.create_record(conn, EMPRESAS, dados_empresa, usuario=usuario)
                cache_empresas[chave] = novo_id
            id_empresa = cache_empresas[chave]
            if id_empresa is not None:
                dados["ID_EMPRESA"] = id_empresa

        id_valor = int(id_bruto) if id_bruto.isdigit() else None
        registro_existente = records.get_record(conn, tabela, id_valor) if id_valor is not None else None

        if registro_existente is not None:
            id_final = id_valor
            if aplicar:
                records.update_record(conn, tabela, id_valor, dados, usuario=usuario)
            resumo.atualizados += 1
        else:
            if id_valor is not None:
                resumo.avisos.append(f'ID "{id_valor}" não encontrado -- linha criada como registro novo.')
            id_final = None
            if aplicar:
                id_final = records.create_record(conn, tabela, dados, usuario=usuario)
            resumo.criados += 1

        if tem_categoria and aplicar and id_final is not None:
            nomes = [n.strip() for n in str(linha.get("CATEGORIA") or "").split(",") if n.strip()]
            categorias.definir_categorias_da_pessoa(conn, id_final, nomes)

    return resumo
