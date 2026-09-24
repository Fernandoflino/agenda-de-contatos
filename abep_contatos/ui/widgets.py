"""
Pecas de interface pequenas e reutilizaveis, que nao se encaixam em nenhuma
tela especifica: o campo de senha com a opcao de "mostrar/ocultar", e dois
widgets de selecao MULTIPLA (marcar varios itens de uma lista fixa) usados
pelas categorias de contato, que agora podem ser mais de uma por pessoa.
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
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
    QWidgetAction,
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


class ComboMultiSelecao(QToolButton):
    """Um botao que abre uma lista onde da pra marcar VARIOS itens ao mesmo
    tempo (cada clique so destaca a linha, sem caixinha de checkbox --
    igual a lista de Empresa) -- usado no filtro por categoria da tela de
    contatos, que agora pode ter mais de um valor marcado ao mesmo tempo.

    Implementado com QMenu + QWidgetAction em vez de um QComboBox
    "customizado" pra aceitar varias marcacoes: um popup de combobox tem
    uma porcao de comportamento interno de clique/arrastar/soltar dificil
    de replicar sem bugs (varias tentativas anteriores esbarraram nisso --
    ou o popup nao abria com um clique normal, ou so ficava aberto
    segurando o botao do mouse). Um QMenu com um widget dentro (via
    QWidgetAction) e o jeito padrao do Qt de fazer um "dropdown" que so
    fecha ao clicar fora dele ou apertar Esc -- igual qualquer outro menu
    do programa, sem hack nenhum.

    O texto mostrado no botao (fechado) resume a selecao: "(todas)" quando
    nada esta marcado, o nome sozinho quando so um item esta marcado, ou
    "N categorias selecionadas" caso contrario.
    """

    selecaoMudou = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("comboMultiSelecao")
        self.setPopupMode(QToolButton.InstantPopup)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._lista = QListWidget()
        self._lista.setObjectName("comboMultiSelecaoLista")
        self._lista.setSelectionMode(QAbstractItemView.MultiSelection)
        self._lista.setMinimumWidth(260)
        self._lista.itemSelectionChanged.connect(self._ao_mudar_selecao)

        menu = QMenu(self)
        acao = QWidgetAction(menu)
        acao.setDefaultWidget(self._lista)
        menu.addAction(acao)
        self.setMenu(menu)

        self._atualizar_texto()

    def definir_opcoes(self, opcoes: list[str], marcados: list[str] | None = None) -> None:
        marcados_set = set(marcados if marcados is not None else self.selecionados())
        self._lista.blockSignals(True)
        self._lista.clear()
        for nome in opcoes:
            item = QListWidgetItem(nome)
            self._lista.addItem(item)
            item.setSelected(nome in marcados_set)
        self._lista.blockSignals(False)
        self._atualizar_texto()

    def selecionados(self) -> list[str]:
        return [item.text() for item in self._lista.selectedItems()]

    def _ao_mudar_selecao(self) -> None:
        self._atualizar_texto()
        self.selecaoMudou.emit()

    def _atualizar_texto(self) -> None:
        marcados = self.selecionados()
        if not marcados:
            texto = "(todas)"
        elif len(marcados) == 1:
            texto = marcados[0]
        else:
            texto = f"{len(marcados)} categorias selecionadas"
        self.setText(texto)
