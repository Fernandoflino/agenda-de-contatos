"""
Tela de "Categorias de contato" -- o CRUD (criar, renomear, excluir) da
lista de opcoes que aparece no campo "Categoria" do formulario de contato e
no filtro "Categoria" da lista de Contatos (ver ui/record_form_dialog.py e
ui/lista_registros_view.py).

Um contato pode ter mais de uma categoria ao mesmo tempo. Renomear uma
categoria aqui so muda o nome exibido (quem ja tinha ela continua tendo);
excluir remove essa etiqueta dos contatos que a usavam, sem mexer nas
outras categorias que eles tiverem -- ver db/categorias.py pros detalhes.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from db import categorias
from ui.dialogs import confirmar_exclusao, mostrar_erro
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela


class CategoriasDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, usuario_logado: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario_logado = usuario_logado
        self.setWindowTitle("Categorias de contato")
        preparar_janela(self, 420, 480)
        self._montar_tela()
        self._recarregar()

    def _montar_tela(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        descricao = QLabel(
            'Estas são as opções de "Categorias" no formulário de contato e no '
            "filtro da lista de Contatos -- um contato pode ter mais de uma ao mesmo "
            "tempo. Excluir uma categoria não apaga os contatos, só remove essa "
            "etiqueta deles (as outras categorias que já tiverem continuam)."
        )
        descricao.setWordWrap(True)
        descricao.setProperty("papel", "subtitulo")
        layout.addWidget(descricao)

        self.lista = QListWidget()
        layout.addWidget(self.lista, stretch=1)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        for texto, funcao, variante in (
            ("Adicionar...", self._adicionar, None),
            ("Renomear...", self._renomear, "secundario"),
            ("Mover para cima", lambda: self._mover(-1), "secundario"),
            ("Mover para baixo", lambda: self._mover(1), "secundario"),
            ("Excluir", self._excluir, "perigo"),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(funcao)
            if variante:
                marcar_variante(botao, variante)
            botoes.addWidget(botao)
        layout.addLayout(botoes)

        rodape = QHBoxLayout()
        rodape.addStretch()
        botao_fechar = QPushButton("Fechar")
        marcar_variante(botao_fechar, "secundario")
        botao_fechar.clicked.connect(self.accept)
        rodape.addWidget(botao_fechar)
        layout.addLayout(rodape)

    def _recarregar(self, selecionar: str | None = None) -> None:
        self.lista.clear()
        for nome in categorias.listar_categorias(self.conn):
            uso = categorias.contar_uso(self.conn, nome)
            sufixo = "1 contato" if uso == 1 else f"{uso} contatos"
            item = QListWidgetItem(f"{nome}  —  {sufixo}")
            item.setData(Qt.UserRole, nome)
            self.lista.addItem(item)
        if selecionar:
            for i in range(self.lista.count()):
                if self.lista.item(i).data(Qt.UserRole) == selecionar:
                    self.lista.setCurrentRow(i)
                    break
        elif self.lista.count():
            self.lista.setCurrentRow(0)

    def _categoria_selecionada(self) -> str | None:
        item = self.lista.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _adicionar(self) -> None:
        nome, ok = QInputDialog.getText(self, "Nova categoria", "Nome da categoria:")
        if not ok or not nome.strip():
            return
        try:
            categorias.adicionar_categoria(self.conn, nome, usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar(selecionar=nome.strip())

    def _mover(self, direcao: int) -> None:
        atual = self._categoria_selecionada()
        if not atual:
            return
        categorias.mover_categoria(self.conn, atual, direcao)
        self._recarregar(selecionar=atual)

    def _renomear(self) -> None:
        atual = self._categoria_selecionada()
        if not atual:
            return
        novo, ok = QInputDialog.getText(self, "Renomear categoria", "Novo nome:", text=atual)
        if not ok or not novo.strip():
            return
        try:
            categorias.renomear_categoria(self.conn, atual, novo, usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar(selecionar=novo.strip())

    def _excluir(self) -> None:
        atual = self._categoria_selecionada()
        if not atual:
            return
        uso = categorias.contar_uso(self.conn, atual)
        if uso:
            sufixo = "1 contato" if uso == 1 else f"{uso} contatos"
            tipo_msg = f"categoria (usada por {sufixo} -- essa categoria será removida desses contatos)"
        else:
            tipo_msg = "categoria"
        if not confirmar_exclusao(self, atual, tipo=tipo_msg):
            return
        categorias.excluir_categoria(self.conn, atual, usuario=self.usuario_logado)
        self._recarregar()
