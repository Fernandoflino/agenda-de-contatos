"""
A "bolinha com iniciais" (avatar) usada pra representar uma pessoa ou empresa
-- na tabela de registros, no painel de detalhes, e no Painel (proximos
aniversarios). Fica num arquivo proprio porque mais de uma tela usa: antes
so existia dentro de ui/lista_registros_view.py, e o Painel (ui/dashboard_view.py)
tambem passou a usar pra manter a mesma "cara" nas duas telas.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

from ui.imagens import pixmap_circular

# Paleta fixa -- a mesma pessoa/empresa sempre cai na mesma cor (calculada a
# partir do nome dela), e as cores sao escolhidas a mao pra ficarem legiveis
# com o texto branco em cima, nunca geradas ao acaso (o que poderia sair uma
# cor lavada ou dificil de ler).
_PALETA_AVATAR = (
    "#2563eb", "#7c3aed", "#db2777", "#dc2626",
    "#d97706", "#059669", "#0891b2", "#4f46e5",
)


def _cor_avatar(texto: str) -> str:
    if not texto:
        return _PALETA_AVATAR[0]
    return _PALETA_AVATAR[sum(ord(c) for c in texto) % len(_PALETA_AVATAR)]


def _iniciais(texto: str) -> str:
    palavras = [p for p in (texto or "").split() if p]
    if not palavras:
        return "?"
    if len(palavras) == 1:
        return palavras[0][:2].upper()
    return (palavras[0][0] + palavras[-1][0]).upper()


class AvatarClicavel(QLabel):
    """Um avatar (com foto de verdade, nunca de iniciais) que reage a
    clique -- usado pra abrir o popup de "ver foto maior" (ver
    ui/foto_popup_dialog.py). So existe essa versao clicavel quando ha
    FOTO de verdade; o avatar de iniciais nunca abre popup."""

    clicado = Signal()

    def mousePressEvent(self, evento) -> None:  # noqa: N802 (nome do metodo original do Qt)
        self.clicado.emit()
        evento.accept()


def criar_avatar(texto: str, tamanho: int = 36, foto_bytes: bytes | None = None, clicavel: bool = False) -> QLabel:
    """Devolve o avatar de uma pessoa/empresa: a foto de verdade (recortada
    em circulo), quando `foto_bytes` vier preenchido e for uma imagem
    valida, ou a "bolinha com iniciais" de sempre quando nao tiver foto --
    quem nunca teve foto continua vendo exatamente o mesmo avatar de
    antes. `clicavel=True` so tem efeito quando HA foto: devolve um
    AvatarClicavel (com o sinal `clicado`) em vez de um QLabel comum."""
    pixmap = pixmap_circular(foto_bytes, tamanho) if foto_bytes else None
    if pixmap is not None:
        avatar = AvatarClicavel() if clicavel else QLabel()
        avatar.setPixmap(pixmap)
        avatar.setFixedSize(tamanho, tamanho)
        avatar.setAlignment(Qt.AlignCenter)
        if clicavel:
            avatar.setCursor(Qt.PointingHandCursor)
        return avatar

    avatar = QLabel(_iniciais(texto))
    avatar.setObjectName("AvatarIniciais")
    avatar.setFixedSize(tamanho, tamanho)
    avatar.setAlignment(Qt.AlignCenter)
    fonte = avatar.font()
    fonte.setPointSize(max(8, tamanho // 3))
    avatar.setFont(fonte)
    avatar.setStyleSheet(
        f"background-color: {_cor_avatar(texto)}; border-radius: {tamanho // 2}px; color: white; font-weight: 700;"
    )
    return avatar
