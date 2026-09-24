"""
Pecas de interface pequenas e reutilizaveis, que nao se encaixam em nenhuma
tela especifica -- por enquanto, so o campo de senha com a opcao de
"mostrar/ocultar" (pedido explicito do usuario), pra poder conferir o que
foi digitado antes de confirmar um login ou cadastrar uma senha nova.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QWidget


class CampoSenha(QWidget):
    """Uma caixa de texto de senha (comeca escondendo o que foi digitado,
    com bolinhas no lugar das letras) + uma caixinha de marcar "Mostrar
    senha" do lado, bem visivel -- marcar ela troca pra mostrar o texto de
    verdade, pra a pessoa conferir se digitou certo antes de confirmar.

    Por fora, este widget se comporta como um campo de texto comum: tem
    .text(), .setText(), .clear(), .setFocus() e o sinal .returnPressed
    (disparado ao apertar Enter dentro do campo) -- assim, quem usa esta
    classe (telas de login, criar usuario, formularios) nao precisa saber
    que por dentro existem, na verdade, dois widgets (o campo + a
    caixinha).
    """

    returnPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._campo = QLineEdit()
        self._campo.setEchoMode(QLineEdit.Password)
        self._campo.returnPressed.connect(self.returnPressed.emit)
        layout.addWidget(self._campo, stretch=1)

        self._caixinha_mostrar = QCheckBox("Mostrar senha")
        self._caixinha_mostrar.toggled.connect(self._alternar_visibilidade)
        layout.addWidget(self._caixinha_mostrar)

    def _alternar_visibilidade(self, mostrar: bool) -> None:
        self._campo.setEchoMode(QLineEdit.Normal if mostrar else QLineEdit.Password)

    # -- "fachada": faz este widget se comportar como um QLineEdit comum --

    def text(self) -> str:
        return self._campo.text()

    def setText(self, texto: str) -> None:
        self._campo.setText(texto)

    def clear(self) -> None:
        self._campo.clear()

    def setFocus(self) -> None:  # noqa: A003 (mesmo nome do metodo original do Qt, de proposito)
        self._campo.setFocus()
