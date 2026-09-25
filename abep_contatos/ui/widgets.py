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
    QMenu,
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
        self.redefinir(opcoes, marcados)

    def redefinir(self, opcoes: list[str], marcados: list[str] | None = None) -> None:
        """Troca a lista de opcoes mostradas, preservando quais delas
        continuam marcadas -- usado quando as opcoes disponiveis podem ter
        mudado (ex.: categoria nova criada) sem perder a selecao atual."""
        marcados_set = set(marcados if marcados is not None else self.selecionados())
        self.clear()

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


class FiltroMultiplaEscolha(QToolButton):
    """Botao que abre um popup com uma SelecaoMultiplaLista -- usado em
    filtros que precisam aceitar mais de um valor marcado ao mesmo tempo
    (ex.: filtrar Contatos por Categoria, onde um registro deve aparecer se
    tiver QUALQUER UMA das categorias marcadas). O texto do botao resume
    quantas opcoes estao marcadas."""

    mudou = Signal()

    def __init__(self, rotulo_base: str, opcoes: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._rotulo_base = rotulo_base
        self._opcoes = list(opcoes or [])
        self.setPopupMode(QToolButton.InstantPopup)

        self.lista = SelecaoMultiplaLista(self._opcoes)
        self.lista.itemChanged.connect(self._ao_mudar_selecao)

        menu = QMenu(self)
        acao = QWidgetAction(menu)
        acao.setDefaultWidget(self.lista)
        menu.addAction(acao)
        self.setMenu(menu)

        self._atualizar_texto()

    def selecionados(self) -> list[str]:
        return self.lista.selecionados()

    def redefinir_opcoes(self, opcoes: list[str]) -> None:
        # redefinir() nao dispara itemChanged (os itens novos ja nascem com
        # o estado marcado/desmarcado certo, antes de entrar na lista) --
        # entao isso nao conta como o usuario "mudando o filtro", igual
        # recarregar o combo de Empresa tambem nao conta (ver
        # _atualizar_widget_valor_linha).
        self._opcoes = list(opcoes)
        self.lista.redefinir(self._opcoes)
        self._atualizar_texto()

    def marcar(self, valores: list[str]) -> None:
        """Marca exatamente esses valores (usado ao restaurar um filtro
        salvo) -- os demais ficam desmarcados. Ao contrario de
        redefinir_opcoes(), isso conta como uma mudanca de verdade no
        filtro (emite `mudou`), igual restaurar o combo de Empresa tambem
        dispara currentIndexChanged."""
        self.lista.redefinir(self._opcoes, marcados=list(valores))
        self._atualizar_texto()
        self.mudou.emit()

    def _ao_mudar_selecao(self, _item: QListWidgetItem) -> None:
        self._atualizar_texto()
        self.mudou.emit()

    def _atualizar_texto(self) -> None:
        quantidade = len(self.selecionados())
        if quantidade == 0:
            self.setText(self._rotulo_base)
        elif quantidade == 1:
            self.setText(f"{self._rotulo_base} (1)")
        else:
            self.setText(f"{self._rotulo_base} ({quantidade})")
