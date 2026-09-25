"""
Popup simples que mostra a foto de um contato AMPLIADA (aberto ao clicar
num avatar que tem foto de verdade -- ver ui/avatar.py::AvatarClicavel),
com um botao pra baixar essa foto (ja renomeada no padrao usado em
ui/imagens.py::nome_arquivo_foto).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.dialogs import mostrar_erro
from ui.imagens import nome_arquivo_foto
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela

_TAMANHO_PREVIEW = 420


class FotoPopupDialog(QDialog):
    def __init__(self, registro: dict, parent=None):
        super().__init__(parent)
        self.registro = registro
        self.setWindowTitle(str(registro.get("NOME") or "Foto"))
        preparar_janela(self, _TAMANHO_PREVIEW + 40, _TAMANHO_PREVIEW + 100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        rotulo_nome = QLabel(str(registro.get("NOME") or ""))
        rotulo_nome.setProperty("papel", "titulo")
        rotulo_nome.setAlignment(Qt.AlignCenter)
        layout.addWidget(rotulo_nome)

        rotulo_foto = QLabel()
        rotulo_foto.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap()
        pixmap.loadFromData(registro.get("FOTO") or b"")
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                _TAMANHO_PREVIEW, _TAMANHO_PREVIEW, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            rotulo_foto.setPixmap(pixmap)
        layout.addWidget(rotulo_foto, stretch=1)

        botoes = QHBoxLayout()
        botoes.addStretch()
        botao_baixar = QPushButton("Baixar...")
        botao_baixar.clicked.connect(self._baixar)
        botoes.addWidget(botao_baixar)
        botao_fechar = QPushButton("Fechar")
        marcar_variante(botao_fechar, "secundario")
        botao_fechar.clicked.connect(self.accept)
        botoes.addWidget(botao_fechar)
        layout.addLayout(botoes)

    def _baixar(self) -> None:
        nome_sugerido = nome_arquivo_foto(self.registro)
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar foto como", nome_sugerido, "Imagem PNG (*.png)")
        if not caminho:
            return
        try:
            with open(caminho, "wb") as arquivo:
                arquivo.write(self.registro.get("FOTO") or b"")
        except OSError as erro:
            mostrar_erro(self, str(erro))
