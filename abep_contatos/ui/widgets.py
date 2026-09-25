"""
Pecas de interface pequenas e reutilizaveis, que nao se encaixam em nenhuma
tela especifica: o campo de senha com a opcao de "mostrar/ocultar", e uma
lista de selecao MULTIPLA (marcar varios itens de uma lista fixa) usada no
formulario de contato pra escolher as categorias de uma pessoa (que agora
podem ser mais de uma).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ui.ajustar_foto_dialog import AjustarFotoDialog
from ui.avatar import criar_avatar
from ui import imagens
from ui.imagens import pixmap_para_bytes_png

_TAMANHO_MAX_FOTO = 512  # pixels -- um pouco maior que o logo (256): a foto e vista ampliada no popup


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


class WidgetFoto(QWidget):
    """Campo de upload de foto no formulario de contato: preview circular
    (a foto atual, ou o avatar de iniciais de sempre enquanto nao tem foto)
    + botoes "Escolher imagem...", "Editar foto..." e "Remover foto". Mesmo
    padrao ja usado pro logotipo do painel (ui/settings_dialog.py), so que
    reutilizavel.

    Guarda DOIS conjuntos de bytes: `_foto_bytes` (o recorte circular,
    enquadrado/girado -- so pra exibir o avatar na tela, com tamanho
    limitado) e `_foto_original_bytes` (o arquivo escolhido, intacto, sem
    nenhum recorte/redimensionamento -- e o que sai quando alguem BAIXA a
    foto depois, pra nunca perder qualidade nem enquadramento do arquivo
    de verdade)."""

    _TAMANHO_PREVIEW = 72

    def __init__(
        self,
        nome_pessoa: str,
        foto_atual: bytes | None,
        foto_original_atual: bytes | None = None,
        foto_original_mime_atual: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._nome_pessoa = nome_pessoa
        self._foto_bytes: bytes | None = foto_atual
        self._foto_original_bytes: bytes | None = foto_original_atual
        self._foto_original_mime: str | None = foto_original_mime_atual

        layout_geral = QVBoxLayout(self)
        layout_geral.setContentsMargins(0, 0, 0, 0)
        layout_geral.setSpacing(4)

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self._rotulo_preview = QLabel()
        layout.addWidget(self._rotulo_preview)

        botoes = QVBoxLayout()
        botoes.setSpacing(4)
        botao_escolher = QPushButton("Escolher imagem...")
        botao_escolher.clicked.connect(self._escolher_imagem)
        botoes.addWidget(botao_escolher)
        self._botao_editar = QPushButton("Editar foto...")
        self._botao_editar.clicked.connect(self._editar_foto)
        botoes.addWidget(self._botao_editar)
        self._botao_remover = QPushButton("Remover foto")
        self._botao_remover.clicked.connect(self._remover_foto)
        botoes.addWidget(self._botao_remover)
        layout.addLayout(botoes)
        layout.addStretch()
        layout_geral.addLayout(layout)

        # So aparece pra fotos cadastradas ANTES do arquivo original passar
        # a ser guardado separado -- pra essas, so sobrou o recorte antigo
        # (sem esse aviso, quem baixasse/editasse essa foto acharia que o
        # programa ainda estava recortando o arquivo original de verdade).
        self._aviso_sem_original = QLabel(
            "Esta foto foi cadastrada antes do arquivo original passar a ser guardado -- "
            "escolha a imagem de novo pra manter o original ao baixar/editar depois."
        )
        self._aviso_sem_original.setProperty("papel", "subtitulo")
        self._aviso_sem_original.setWordWrap(True)
        layout_geral.addWidget(self._aviso_sem_original)

        self._atualizar_preview()

    def _atualizar_preview(self) -> None:
        # criar_avatar() ja resolve foto-de-verdade vs. iniciais -- pra nao
        # duplicar essa logica aqui, so "capturamos" o widget pronto
        # (funciona igual pros dois casos: pixmap de foto, ou o QSS colorido
        # das iniciais) e usamos como preview.
        avatar = criar_avatar(self._nome_pessoa, tamanho=self._TAMANHO_PREVIEW, foto_bytes=self._foto_bytes)
        self._rotulo_preview.setFixedSize(self._TAMANHO_PREVIEW, self._TAMANHO_PREVIEW)
        self._rotulo_preview.setPixmap(avatar.grab())
        self._botao_editar.setEnabled(bool(self._foto_bytes))
        self._botao_remover.setEnabled(bool(self._foto_bytes))
        self._aviso_sem_original.setVisible(bool(self._foto_bytes) and not self._foto_original_bytes)

    def _escolher_imagem(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher foto", "", "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        if not caminho:
            return
        pixmap_original = QPixmap(caminho)
        if pixmap_original.isNull():
            return
        dados_originais, mime_original = imagens.ler_bytes_originais(caminho)
        self._ajustar_e_salvar(pixmap_original, novo_original=(dados_originais, mime_original))

    def _editar_foto(self) -> None:
        """Reabre o editor de enquadrar/girar -- a partir do arquivo
        ORIGINAL, quando tiver (pra nao perder qualidade recortando um
        recorte de novo); em registro antigo, de antes do original ser
        guardado separado, usa o recorte mesmo como ponto de partida (e o
        unico dado que sobrou pra esses)."""
        fonte = self._foto_original_bytes or self._foto_bytes
        if not fonte:
            return
        pixmap_fonte = QPixmap()
        if not pixmap_fonte.loadFromData(fonte):
            return
        self._ajustar_e_salvar(pixmap_fonte)

    def _ajustar_e_salvar(self, pixmap_original: QPixmap, novo_original: tuple[bytes, str] | None = None) -> None:
        recorte = self._abrir_ajuste(pixmap_original)
        if recorte is None:
            return  # cancelou o ajuste -- mantem a foto que ja estava
        self._foto_bytes = pixmap_para_bytes_png(recorte, _TAMANHO_MAX_FOTO)
        if novo_original is not None:
            self._foto_original_bytes, self._foto_original_mime = novo_original
        self._atualizar_preview()

    def _abrir_ajuste(self, pixmap_original: QPixmap) -> QPixmap | None:
        dialogo = AjustarFotoDialog(pixmap_original, parent=self)
        if dialogo.exec() != QDialog.Accepted:
            return None
        return dialogo.resultado()

    def _remover_foto(self) -> None:
        self._foto_bytes = None
        self._foto_original_bytes = None
        self._foto_original_mime = None
        self._atualizar_preview()

    def foto_bytes(self) -> bytes | None:
        return self._foto_bytes

    def foto_mime(self) -> str | None:
        return "image/png" if self._foto_bytes else None

    def foto_original_bytes(self) -> bytes | None:
        return self._foto_original_bytes

    def foto_original_mime(self) -> str | None:
        return self._foto_original_mime
