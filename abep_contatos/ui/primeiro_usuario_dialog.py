"""
Esta janela aparece SO uma vez, logo depois de criar um banco de dados novo
(ou ao reabrir um banco que por algum motivo ficou sem nenhum usuario): como
o banco nasce sem nenhum usuario cadastrado, e obrigatorio criar o primeiro
administrador aqui -- senao ninguem conseguiria fazer login depois.

No sistema antigo (Google Apps Script), esse primeiro usuario era criado "na
mao" por quem programava, rodando uma funcao especial no editor de codigo.
Aqui isso vira uma tela normal, que qualquer pessoa consegue usar sem saber
nada de programacao.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
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

from db import auth
from ui.dialogs import mostrar_erro
from ui.widgets import CampoSenha
from ui.window_utils import preparar_janela


class PrimeiroUsuarioDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Criar o primeiro usuário")
        self.setModal(True)
        preparar_janela(self)
        # Sem botao de fechar no "X" nem tecla Esc -- criar o primeiro
        # usuario nao e opcional, o banco precisaria de alguem que consiga
        # entrar depois (ver reject() sobrescrito no final da classe).
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        cartao = QWidget()
        cartao.setFixedWidth(380)
        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setSpacing(14)

        titulo = QLabel("Criar o primeiro usuário")
        titulo.setProperty("papel", "titulo")
        titulo.setAlignment(Qt.AlignCenter)
        layout_cartao.addWidget(titulo)

        aviso = QLabel(
            "Este banco de dados ainda nao tem nenhum usuario.\n"
            "Crie o primeiro login administrativo para continuar."
        )
        aviso.setProperty("papel", "subtitulo")
        aviso.setWordWrap(True)
        aviso.setAlignment(Qt.AlignCenter)
        layout_cartao.addWidget(aviso)

        form = QFormLayout()
        form.setSpacing(10)
        self.campo_nome = QLineEdit()
        self.campo_usuario = QLineEdit()
        self.campo_senha = CampoSenha()
        self.campo_confirmar = CampoSenha()
        form.addRow("Nome:", self.campo_nome)
        form.addRow("Usuario:", self.campo_usuario)
        form.addRow("Senha:", self.campo_senha)
        form.addRow("Confirmar senha:", self.campo_confirmar)
        layout_cartao.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok)
        botoes.button(QDialogButtonBox.Ok).setText("Criar usuário")
        botoes.accepted.connect(self._criar)
        layout_cartao.addWidget(botoes)

        linha_central = QHBoxLayout()
        linha_central.addStretch()
        linha_central.addWidget(cartao)
        linha_central.addStretch()

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addLayout(linha_central)
        layout.addStretch()

    def _criar(self) -> None:
        usuario = self.campo_usuario.text().strip()
        senha = self.campo_senha.text()
        confirmar = self.campo_confirmar.text()
        nome = self.campo_nome.text().strip() or usuario

        if not usuario or not senha:
            mostrar_erro(self, "Informe usuário e senha.")
            return
        if senha != confirmar:
            mostrar_erro(self, "As senhas digitadas não são iguais.")
            return

        try:
            auth.criar_usuario(self.conn, usuario, senha, nome, usuario_logado=usuario)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return

        self.accept()

    def reject(self) -> None:
        # Bloqueia o Esc/fechar a janela -- ver comentario no __init__.
        pass
