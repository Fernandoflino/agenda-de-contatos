"""
Este arquivo arruma a "capitalizacao" de nomes proprios (pessoas, empresas)
que vem em CAIXA ALTA da planilha original (ex.: "ALÍRIO FÉLIX MARTINS
BARROS") pra um formato mais facil de ler: so a primeira letra de cada
palavra maiuscula (ex.: "Alírio Félix Martins Barros") -- pedido explicito
do usuario, que tambem pediu pra manter a acentuacao correta.

Sobre a acentuacao: o Python ja lida certo com letras acentuadas nas
funcoes de maiusculo/minusculo (por exemplo, "ÍNDICE".title() vira
"Índice", sem perder o acento) -- entao normalizar a capitalizacao aqui
tambem preserva os acentos automaticamente, sem precisar de nenhum
tratamento especial.
"""
from __future__ import annotations

# Conectores em portugues que ficam em minusculo no meio de um nome (ex.:
# "Agência de Tecnologia da Informação do Tocantins"), exceto quando sao a
# primeira palavra do texto.
_CONECTORES_MINUSCULOS = {"de", "da", "do", "das", "dos", "e"}


def normalizar_nome_proprio(texto: str | None) -> str | None:
    """Recebe um texto (nome de pessoa, empresa etc.) e devolve ele com
    capitalizacao de nome proprio: primeira letra de cada palavra maiuscula,
    resto minusculo -- exceto conectores como "de"/"da"/"do", que ficam em
    minusculo (a nao ser que sejam a primeira palavra).

    Valores vazios (None, string vazia) voltam do jeito que vieram -- nao ha
    nada pra normalizar.
    """
    if not texto:
        return texto

    palavras = texto.strip().split()
    resultado = []
    for indice, palavra in enumerate(palavras):
        # .title() capitaliza depois de QUALQUER caractere que nao seja
        # letra (espaco, hifen, parenteses...) -- por isso "MARIA-JOSÉ"
        # vira "Maria-José" corretamente, e nao "Maria-josé".
        minuscula = palavra.lower()
        if indice > 0 and minuscula in _CONECTORES_MINUSCULOS:
            resultado.append(minuscula)
        else:
            resultado.append(palavra.title())
    return " ".join(resultado)
