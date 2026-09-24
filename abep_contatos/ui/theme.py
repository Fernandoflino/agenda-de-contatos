"""
Este arquivo aplica o "tema visual" do programa (cores, cantos arredondados,
modo claro/escuro), lendo o modelo em resources/style.qss e trocando os
placeholders (textos como {{accent}}) por cores de verdade -- escolhidas a
partir de duas paletas fixas (CLARA e ESCURA) mais a cor de destaque que o
usuario escolheu na tela de Configuracoes (guardada no banco de dados -- ver
db/settings.py).

Trocar de modo claro/escuro, ou de cor de destaque, so muda QUAL cor entra
em cada placeholder -- a estrutura visual (espacamento, cantos arredondados
etc.) definida no .qss continua a mesma nos dois modos.
"""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from db import settings

_CAMINHO_QSS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "style.qss")

# Paleta usada no modo CLARO -- fundo claro, texto escuro.
_PALETA_CLARA = {
    "bg": "#f8fafc",
    "bg_elevado": "#ffffff",
    "bg_input": "#ffffff",
    "text": "#1e293b",
    "text_muted": "#64748b",
    "borda": "#dbe2ea",
    "hover": "#eef2ff",
    "perigo": "#dc2626",
    "perigo_hover": "#b91c1c",
    # Cor de "falta alguma coisa aqui" (cartoes de dado incompleto no
    # Painel) -- separada da cor de destaque de proposito, pra continuar
    # chamando atencao nao importa qual cor a pessoa escolha em Configuracoes.
    "alerta": "#b45309",
}

# Paleta usada no modo ESCURO -- fundo escuro, texto claro. As mesmas
# "funcoes" de cor da paleta clara, so que invertidas em luminosidade.
_PALETA_ESCURA = {
    "bg": "#0f172a",
    "bg_elevado": "#1e293b",
    "bg_input": "#1e293b",
    "text": "#e2e8f0",
    "text_muted": "#94a3b8",
    "borda": "#334155",
    "hover": "#334155",
    "perigo": "#ef4444",
    "perigo_hover": "#dc2626",
    "alerta": "#f2a93c",
}


def _tom(cor_hex: str, fator: int) -> str:
    """Gera uma variacao mais clara (fator < 100) ou mais escura (fator > 100)
    de uma cor -- usado pros efeitos de hover/pressed dos botoes."""
    cor = QColor(cor_hex)
    if not cor.isValid():
        cor = QColor(settings.COR_PADRAO)
    return (cor.lighter(fator) if fator < 100 else cor.darker(fator)).name()


def _cor_contraste(cor_hex: str) -> str:
    """Decide se o texto EM CIMA da cor de destaque deve ser branco ou
    escuro, calculando o quao clara ou escura a cor de destaque e (formula
    padrao de luminancia). Isso evita, por exemplo, texto branco escrito em
    cima de um amarelo claro escolhido como cor de destaque."""
    cor = QColor(cor_hex)
    if not cor.isValid():
        return "white"
    luminancia = (0.299 * cor.red() + 0.587 * cor.green() + 0.114 * cor.blue()) / 255
    return "#0f172a" if luminancia > 0.6 else "white"


def aplicar_tema(app: QApplication, conn: sqlite3.Connection) -> None:
    branding = settings.obter_branding(conn)
    paleta = _PALETA_ESCURA if branding.tema == settings.TEMA_ESCURO else _PALETA_CLARA

    with open(_CAMINHO_QSS, "r", encoding="utf-8") as f:
        folha = f.read()

    substituicoes = dict(paleta)
    substituicoes["accent"] = branding.cor_destaque
    substituicoes["accent_hover"] = _tom(branding.cor_destaque, 90)
    substituicoes["accent_pressionado"] = _tom(branding.cor_destaque, 80)
    substituicoes["accent_texto"] = _cor_contraste(branding.cor_destaque)

    for chave, valor in substituicoes.items():
        folha = folha.replace("{{" + chave + "}}", valor)

    app.setStyleSheet(folha)


def cor_texto_mutado(conn: sqlite3.Connection) -> str:
    """A cor de texto 'apagado' (rotulos secundarios) do tema ATUAL do
    banco -- usada tambem pelos icones em ui/icons.py, pra eles
    acompanharem o tema claro/escuro em vez de ficar com uma cor fixa que
    poderia ficar sem contraste num dos dois modos."""
    branding = settings.obter_branding(conn)
    paleta = _PALETA_ESCURA if branding.tema == settings.TEMA_ESCURO else _PALETA_CLARA
    return paleta["text_muted"]


def marcar_variante(botao: QPushButton, variante: str) -> None:
    """Marca um botao como "secundario" ou "perigo" (o padrao, sem marcar
    nada, ja e a acao principal/de destaque) -- ver as regras
    QPushButton[variante="..."] em resources/style.qss.

    Precisa ser chamado ANTES do botao aparecer na tela (normalmente logo
    depois de cria-lo) -- se for chamado depois, e necessario "repolir" o
    widget pra o Qt reaplicar o estilo (o unpolish/polish abaixo cobre os
    dois casos, entao esta funcao funciona nos dois momentos).
    """
    botao.setProperty("variante", variante)
    estilo = botao.style()
    estilo.unpolish(botao)
    estilo.polish(botao)
