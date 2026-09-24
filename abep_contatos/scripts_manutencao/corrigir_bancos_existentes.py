"""
Script de manutencao UNICO -- usado uma unica vez pra corrigir os dois
bancos de dados que ja existiam ANTES das seguintes melhorias:

1. Campo CATEGORIA (etiqueta com a aba de origem de cada pessoa).
2. Nomes de pessoa/empresa normalizados (so a primeira letra maiuscula).

Como esses dois bancos foram criados pela importacao original (com as 3
abas de pessoas entrando na ordem Presidentes/Diretores Tecnicos/Diretores
Adm. Financeiros, 27 linhas cada), da pra recuperar a categoria de cada
pessoa OLHANDO A FAIXA DE ID dela -- e o mesmo intervalo que a importacao
gerou na epoca. Isso so funciona porque conferimos antes que os dois bancos
ainda tem exatamente os IDs 1 a 81 sem buracos nem pessoas extras nessa
faixa (nenhuma foi excluida ou criada por fora da importacao original).

NAO faz parte do programa (nao e chamado por nenhuma tela) -- e so um
utilitario de linha de comando, rodado uma vez, pra este caso especifico.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import connection, records  # noqa: E402
from db.normalizacao import normalizar_nome_proprio  # noqa: E402
from db.schema import EMPRESAS, PESSOAS  # noqa: E402
from db.tables import get_schema  # noqa: E402

_FAIXAS_CATEGORIA = [
    (1, 27, "Presidentes"),
    (28, 54, "Diretores Técnicos"),
    (55, 81, "Diretores Adm. Financeiros"),
]

_CARGOS_FALLBACK_ANTIGOS = {"PRESIDENTES", "DIRETORES TÉCNICOS", "DIRETORES ADM. FINANCEIROS"}


def _categoria_por_id(id_pessoa: int) -> str | None:
    for inicio, fim, categoria in _FAIXAS_CATEGORIA:
        if inicio <= id_pessoa <= fim:
            return categoria
    return None


def corrigir_arquivo(caminho: str) -> None:
    print(f"\n== {caminho} ==")
    conn = connection.conectar(caminho)  # ja roda a migracao de schema (adiciona CATEGORIA se faltar)

    colunas_pessoas = set(get_schema(conn, PESSOAS))
    pessoas_corrigidas = 0
    for pessoa in records.get_records(conn, PESSOAS):
        categoria = _categoria_por_id(pessoa["ID"])
        alteracoes = {}

        if categoria and not pessoa.get("CATEGORIA"):
            alteracoes["CATEGORIA"] = categoria

        # CARGO tinha virado o nome da aba (em CAIXA ALTA) quando a planilha
        # original nao trazia um cargo pra aquela pessoa -- agora que existe
        # CATEGORIA pra isso, deixamos o CARGO com a mesma capitalizacao.
        if categoria and str(pessoa.get("CARGO", "")).strip().upper() in _CARGOS_FALLBACK_ANTIGOS:
            alteracoes["CARGO"] = categoria

        for campo in ("NOME", "NOME DE GUERRA", "ASSESSOR(A)"):
            if campo in colunas_pessoas and pessoa.get(campo):
                normalizado = normalizar_nome_proprio(pessoa[campo])
                if normalizado != pessoa[campo]:
                    alteracoes[campo] = normalizado

        if alteracoes:
            records.update_record(conn, PESSOAS, pessoa["ID"], alteracoes, usuario="sistema")
            pessoas_corrigidas += 1

    empresas_corrigidas = 0
    for empresa in records.get_records(conn, EMPRESAS):
        nome_corrigido = empresa.get("EMPRESA_MINUSCULA") or normalizar_nome_proprio(empresa.get("EMPRESA"))
        if nome_corrigido and nome_corrigido != empresa.get("EMPRESA"):
            records.update_record(conn, EMPRESAS, empresa["ID"], {"EMPRESA": nome_corrigido}, usuario="sistema")
            empresas_corrigidas += 1

    conn.close()
    print(f"  Pessoas corrigidas: {pessoas_corrigidas}")
    print(f"  Empresas corrigidas: {empresas_corrigidas}")


if __name__ == "__main__":
    for caminho_arquivo in sys.argv[1:]:
        corrigir_arquivo(caminho_arquivo)
