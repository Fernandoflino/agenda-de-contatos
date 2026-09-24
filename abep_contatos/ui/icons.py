"""
Um punhado de ICONES pequenos, desenhados aqui mesmo em SVG (linhas
simples, sem preenchimento) -- usados na busca, nos filtros e no painel de
detalhes (empresa/e-mail/telefone).

Por que desenhar em vez de usar emoji: um emoji (tipo "🔍" ou "📧") vem de
uma fonte de IMAGENS COLORIDAS do proprio Windows, que muda de estilo
dependendo da versao do sistema e destoa do resto do visual do programa
(foi rejeitado antes por causa disso -- ver auditoria de UX). Um SVG
desenhado aqui sai sempre igual, e a cor e escolhida na hora pra combinar
com o tema claro/escuro.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TRACO = 'fill="none" stroke="{cor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'

_SVGS = {
    "busca": f'<svg viewBox="0 0 24 24" {_TRACO}><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "filtro": f'<svg viewBox="0 0 24 24" {_TRACO}><polygon points="4,4 20,4 14,12 14,20 10,20 10,12"/></svg>',
    "empresa": f'<svg viewBox="0 0 24 24" {_TRACO}><rect x="4" y="3" width="9" height="18"/><rect x="15" y="9" width="5" height="12"/><line x1="7.5" y1="7.5" x2="7.5" y2="7.6"/><line x1="7.5" y1="12" x2="7.5" y2="12.1"/><line x1="7.5" y1="16.5" x2="7.5" y2="16.6"/></svg>',
    "email": f'<svg viewBox="0 0 24 24" {_TRACO}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>',
    "telefone": f'<svg viewBox="0 0 24 24" {_TRACO}><path d="M6.5 3.5h3l1.5 4-2 1.5a10 10 0 0 0 5.5 5.5l1.5-2 4 1.5v3a1.5 1.5 0 0 1-1.6 1.5A15.5 15.5 0 0 1 5 6.1 1.5 1.5 0 0 1 6.5 3.5z"/></svg>',
    "fechar": f'<svg viewBox="0 0 24 24" fill="none" stroke="{{cor}}" stroke-width="2.5" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>',
}

_cache: dict[tuple[str, str, int], QIcon] = {}


def icone(nome: str, cor: str = "#64748b", tamanho: int = 18) -> QIcon:
    """Devolve o icone `nome` (ver _SVGS acima) desenhado na cor pedida.
    Guarda em cache (mesmo nome+cor+tamanho nao e redesenhado de novo)."""
    chave = (nome, cor, tamanho)
    if chave in _cache:
        return _cache[chave]

    svg = _SVGS[nome].format(cor=cor)
    renderizador = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.transparent)
    pintor = QPainter(pixmap)
    renderizador.render(pintor)
    pintor.end()

    resultado = QIcon(pixmap)
    _cache[chave] = resultado
    return resultado
