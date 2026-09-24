"""
Pecas de interface pequenas e reutilizaveis, que nao se encaixam em nenhuma
tela especifica: o campo de senha com a opcao de "mostrar/ocultar", e uma
lista de selecao MULTIPLA (marcar varios itens de uma lista fixa) usada no
formulario de contato pra escolher as categorias de uma pessoa (que agora
podem ser mais de uma).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)


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


class SelecaoMultiplaLista(QListWidget):
    """Uma lista onde cada item tem uma caixinha de marcar do lado, em vez
    de so uma linha "selecionada" -- usada no formulario de contato pra
    escolher VARIAS categorias ao mesmo tempo (o combo de escolha unica de
    antes so deixava marcar uma).

    Valores marcados que nao estao mais entre `opcoes` (ex.: uma categoria
    que essa pessoa tinha e que foi excluida da lista mestre depois) ficam
    visiveis mesmo assim, com um aviso no texto -- pra nao "sumir"
    silenciosamente uma informacao que so seria perdida de verdade se
    alguem salvasse o formulario sem reparar.
    """

    def __init__(self, opcoes: list[str], marcados: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setMaximumHeight(150)

        marcados_set = set(marcados or [])
        for nome in opcoes:
            item = QListWidgetItem(nome)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if nome in marcados_set else Qt.Unchecked)
            self.addItem(item)

        for nome in marcados_set:
            if not self.findItems(nome, Qt.MatchExactly):
                item = QListWidgetItem(f"{nome} (categoria removida)")
                item.setData(Qt.UserRole, nome)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.addItem(item)

    def selecionados(self) -> list[str]:
        resultado = []
        for i in range(self.count()):
            item = self.item(i)
            if item.checkState() == Qt.Checked:
                resultado.append(item.data(Qt.UserRole) or item.text())
        return resultado
