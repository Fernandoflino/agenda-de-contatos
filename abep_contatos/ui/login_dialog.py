"""
Tela de LOGIN: aparece toda vez que um banco de dados e aberto ou criado.
Diferente do sistema antigo (que rodava na internet e usava um "token" de
sessao com validade de 8 horas), aqui nao existe sessao pra expirar -- um
login bem-sucedido so vale enquanto o programa estiver aberto na tela.

Mostra o logotipo e o nome configurados pelo usuario (ui/settings_dialog.py),
pra dar a sensacao de "esse e o painel da minha organizacao" em vez de um
programa generico.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config import app_config
from db import auth, settings
from ui.dialogs import mostrar_erro
from ui.theme import marcar_variante
from ui.widgets import CampoSenha
from ui.window_utils import preparar_janela


class LoginDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario_logado: auth.Usuario | None = None

        branding = settings.obter_branding(self.conn)
        self.setWindowTitle(branding.nome)
        preparar_janela(self)

        # O formulario de login fica dentro de um "cartao" central de largura
        # fixa -- sem isso, os campos ficariam esticados de ponta a ponta na
        # janela (que agora tem um tamanho padrao bem maior que um login
        # simples precisa), com uma aparencia estranha e vazia nas laterais.
        cartao = QWidget()
        cartao.setFixedWidth(360)
        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setSpacing(14)

        if branding.logo:
            pixmap = QPixmap()
            pixmap.loadFromData(branding.logo)
            rotulo_logo = QLabel()
            rotulo_logo.setPixmap(pixmap.scaledToHeight(96, Qt.SmoothTransformation))
            rotulo_logo.setAlignment(Qt.AlignCenter)
            layout_cartao.addWidget(rotulo_logo)

        titulo = QLabel(branding.nome)
        titulo.setProperty("papel", "titulo")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setWordWrap(True)
        layout_cartao.addWidget(titulo)

        form = QFormLayout()
        form.setSpacing(10)
        self.campo_usuario = QLineEdit(app_config.ultimo_usuario())
        self.campo_senha = CampoSenha()
        self.campo_senha.returnPressed.connect(self._tentar_login)
        form.addRow("Usuario:", self.campo_usuario)
        form.addRow("Senha:", self.campo_senha)
        layout_cartao.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Entrar")
        marcar_variante(botoes.button(QDialogButtonBox.Cancel), "secundario")
        botoes.accepted.connect(self._tentar_login)
        botoes.rejected.connect(self.reject)
        layout_cartao.addWidget(botoes)

        # Centraliza o cartao tanto na horizontal quanto na vertical dentro
        # da janela, usando "elasticos" (stretch) dos dois lados.
        linha_central = QHBoxLayout()
        linha_central.addStretch()
        linha_central.addWidget(cartao)
        linha_central.addStretch()

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addLayout(linha_central)
        layout.addStretch()

        if self.campo_usuario.text():
            self.campo_senha.setFocus()
        else:
            self.campo_usuario.setFocus()

    def _tentar_login(self) -> None:
        usuario = self.campo_usuario.text()
        senha = self.campo_senha.text()
        try:
            self.usuario_logado = auth.login(self.conn, usuario, senha)
        except auth.ErroLogin as erro:
            mostrar_erro(self, str(erro), titulo="Não foi possível entrar")
            self.campo_senha.clear()
            self.campo_senha.setFocus()
            return

        app_config.definir_ultimo_usuario(self.usuario_logado.usuario)
        self.accept()
