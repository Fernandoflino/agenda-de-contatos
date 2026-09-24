"""
Pecas de interface pequenas e reutilizaveis, que nao se encaixam em nenhuma
tela especifica: o campo de senha com a opcao de "mostrar/ocultar", e dois
widgets de selecao MULTIPLA (marcar varios itens de uma lista fixa) usados
pelas categorias de contato, que agora podem ser mais de uma por pessoa.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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


class ComboMultiSelecao(QComboBox):
    """Um combo (dropdown) onde cada item da lista tem uma caixinha de
    marcar, permitindo escolher VARIOS valores sem precisar de uma lista
    grande sempre visivel -- usado no filtro por categoria da tela de
    contatos, que agora pode ter mais de um valor marcado ao mesmo tempo.

    O texto mostrado no combo (quando fechado) resume a selecao: "(todas)"
    quando nada esta marcado, o nome sozinho quando so um item esta
    marcado, ou "N categorias selecionadas" caso contrario.
    """

    selecaoMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        # O campo de texto interno (criado por setEditable) cobre quase toda
        # a largura da caixa e "engole" o clique do mouse antes dele chegar
        # no combo -- sem isso, so a setinha da direita abriria o popup (o
        # bug relatado: clicar no meio da caixa larga nao fazia nada).
        self.lineEdit().installEventFilter(self)
        self.view().pressed.connect(self._alternar_item)
        self._fechar_popup = True
        self._atualizar_texto()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.lineEdit() and event.type() == QEvent.MouseButtonPress:
            # Chamar showPopup() direto aqui abriria o popup ainda com o
            # botao do mouse fisicamente pressionado (estamos dentro do
            # proprio evento de clique) -- o popup "herda" esse pressionar
            # em andamento como se fosse um menu do tipo "segura, arrasta,
            # solta pra escolher": soltar o botao localizado sobre um item
            # (o que acontece na maioria dos cliques normais, ja que o
            # popup abre bem embaixo do cursor) fecha tudo na hora,
            # dando a impressao de que so funciona "segurando". Adiar a
            # chamada pro proximo laco de eventos garante que o clique
            # original ja tenha terminado (botao solto) antes do popup
            # abrir, evitando essa confusao.
            QTimer.singleShot(0, self.showPopup)
            return True
        return super().eventFilter(watched, event)

    def definir_opcoes(self, opcoes: list[str], marcados: list[str] | None = None) -> None:
        marcados_set = set(marcados if marcados is not None else self.selecionados())
        modelo = self.model()
        modelo.clear()
        for nome in opcoes:
            item = QStandardItem(nome)
            item.setCheckable(True)
            item.setCheckState(Qt.Checked if nome in marcados_set else Qt.Unchecked)
            modelo.appendRow(item)
        self._atualizar_texto()

    def selecionados(self) -> list[str]:
        modelo = self.model()
        return [
            modelo.item(i).text()
            for i in range(modelo.rowCount())
            if modelo.item(i).checkState() == Qt.Checked
        ]

    def _alternar_item(self, index) -> None:
        item = self.model().itemFromIndex(index)
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        self._atualizar_texto()
        self._fechar_popup = False
        self.selecaoMudou.emit()

    def _atualizar_texto(self) -> None:
        marcados = self.selecionados()
        if not marcados:
            texto = "(todas)"
        elif len(marcados) == 1:
            texto = marcados[0]
        else:
            texto = f"{len(marcados)} categorias selecionadas"
        self.lineEdit().setText(texto)

    def hidePopup(self) -> None:
        # Sem isso, o Qt fecharia o dropdown a cada clique num item -- essa
        # flag deixa o popup aberto exatamente quando o motivo de chamar
        # hidePopup() foi o clique que acabou de marcar/desmarcar um item.
        if self._fechar_popup:
            super().hidePopup()
        self._fechar_popup = True
