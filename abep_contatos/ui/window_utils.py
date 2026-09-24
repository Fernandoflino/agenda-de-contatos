"""
Pequena funcao auxiliar chamada por TODA janela/tela do programa, pra
garantir duas coisas de uma vez:

1. Todas comecam com um tamanho parecido (em vez de cada tela ter um
   tamanho arbitrario diferente, o que passa uma sensacao "desorganizada").
2. Todas ganham os botoes de MINIMIZAR e MAXIMIZAR no titulo -- por padrao,
   o Qt so coloca o botao de fechar (X) em janelas do tipo "dialogo"
   (QDialog), sem os outros dois; aqui a gente adiciona os que faltavam,
   pra qualquer tela poder ser maximizada como qualquer outro programa do
   Windows.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLayout, QWidget

# Tamanho usado como padrao em todas as janelas do programa (largura, altura),
# em pixels. Quem precisar de mais espaco pode maximizar a janela na hora.
TAMANHO_PADRAO = (640, 520)


def preparar_janela(janela: QWidget, largura: int | None = None, altura: int | None = None) -> None:
    janela.resize(largura or TAMANHO_PADRAO[0], altura or TAMANHO_PADRAO[1])
    janela.setWindowFlags(
        janela.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
    )


def limpar_layout(layout: QLayout) -> None:
    """Esvazia um layout por completo (widgets E sub-layouts dentro dele),
    pra poder repopular ele do zero -- usado sempre que uma tela recalcula
    os dados e precisa "apagar o quadro" antes de desenhar de novo (o
    Painel, e agora tambem a lista de registros)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        sublayout = item.layout()
        if sublayout is not None:
            limpar_layout(sublayout)
