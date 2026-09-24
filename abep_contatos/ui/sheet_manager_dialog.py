"""
Esta e a tela de "Gerenciar tabelas e campos" -- e aqui que mora o ESQUEMA
DINAMICO do programa: o usuario pode criar uma tabela nova do zero (ou
copiando a estrutura de outra), renomear ou excluir uma tabela, e dentro de
cada tabela pode adicionar, renomear, remover e escolher o TIPO de cada
campo (texto comum, e-mail, telefone, CPF, data, ou uma lista fechada de
opcoes).

Do lado esquerdo fica a lista de tabelas; do lado direito, os campos da
tabela selecionada. Toda alteracao aqui chama diretamente as funcoes de
db/tables.py e ui/field_types.py, que ja cuidam de validar os nomes e
registrar cada mudanca no historico (db/log.py).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from db import settings, tables
from ui import field_types
from ui.dialogs import confirmar_exclusao, mostrar_erro
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela


class SheetManagerDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, usuario_logado: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario_logado = usuario_logado
        self.setWindowTitle("Gerenciar tabelas e campos")
        preparar_janela(self, 820, 560)
        self._montar_tela()
        self._recarregar_tabelas()

    # -- montagem ------------------------------------------------------

    def _montar_tela(self) -> None:
        layout_geral = QVBoxLayout(self)
        layout_geral.setContentsMargins(16, 16, 16, 16)
        layout_geral.setSpacing(12)

        divisor = QSplitter()
        divisor.setChildrenCollapsible(False)

        # -- coluna da esquerda: lista de tabelas --
        self.grupo_tabelas = QGroupBox("Tabelas")
        layout_tabelas = QVBoxLayout(self.grupo_tabelas)
        layout_tabelas.setSpacing(10)
        self.lista_tabelas = QListWidget()
        self.lista_tabelas.currentTextChanged.connect(self._ao_selecionar_tabela)
        layout_tabelas.addWidget(self.lista_tabelas)

        botoes_tabela = QHBoxLayout()
        botoes_tabela.setSpacing(8)
        for texto, funcao, variante in (
            ("Nova...", self._nova_tabela, None),
            ("Renomear...", self._renomear_tabela, "secundario"),
            ("Rotulo de exibicao...", self._definir_rotulo, "secundario"),
            ("Mover para cima", lambda: self._mover_tabela(-1), "secundario"),
            ("Mover para baixo", lambda: self._mover_tabela(1), "secundario"),
            ("Excluir", self._excluir_tabela, "perigo"),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(funcao)
            if variante:
                marcar_variante(botao, variante)
            botoes_tabela.addWidget(botao)
        layout_tabelas.addLayout(botoes_tabela)
        divisor.addWidget(self.grupo_tabelas)

        # -- coluna da direita: campos da tabela selecionada --
        self.grupo_campos = QGroupBox("Campos")
        layout_campos = QVBoxLayout(self.grupo_campos)
        layout_campos.setSpacing(10)
        self.lista_campos = QListWidget()
        layout_campos.addWidget(self.lista_campos)

        botoes_campo = QHBoxLayout()
        botoes_campo.setSpacing(8)
        for texto, funcao, variante in (
            ("Adicionar...", self._adicionar_campo, None),
            ("Renomear...", self._renomear_campo, "secundario"),
            ("Tipo...", self._configurar_tipo_campo, "secundario"),
            ("Mover para cima", lambda: self._mover_campo(-1), "secundario"),
            ("Mover para baixo", lambda: self._mover_campo(1), "secundario"),
            ("Remover", self._remover_campo, "perigo"),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(funcao)
            if variante:
                marcar_variante(botao, variante)
            botoes_campo.addWidget(botao)
        layout_campos.addLayout(botoes_campo)
        divisor.addWidget(self.grupo_campos)

        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 2)
        layout_geral.addWidget(divisor, stretch=1)

        rodape = QHBoxLayout()
        rodape.addStretch()
        botao_fechar = QPushButton("Fechar")
        marcar_variante(botao_fechar, "secundario")
        botao_fechar.clicked.connect(self.accept)
        rodape.addWidget(botao_fechar)
        layout_geral.addLayout(rodape)

    # -- carregamento ----------------------------------------------------

    def _recarregar_tabelas(self, selecionar: str | None = None) -> None:
        self.lista_tabelas.blockSignals(True)
        self.lista_tabelas.clear()
        self.lista_tabelas.addItems(tables.get_table_order(self.conn))
        self.lista_tabelas.blockSignals(False)
        if self.lista_tabelas.count():
            indice = 0
            if selecionar:
                for i in range(self.lista_tabelas.count()):
                    if self.lista_tabelas.item(i).text() == selecionar:
                        indice = i
                        break
            self.lista_tabelas.setCurrentRow(indice)
        else:
            self._recarregar_campos()

    def _tabela_selecionada(self) -> str | None:
        item = self.lista_tabelas.currentItem()
        return item.text() if item else None

    def _ao_selecionar_tabela(self, nome: str) -> None:
        self._recarregar_campos()

    def _recarregar_campos(self) -> None:
        self.lista_campos.clear()
        tabela = self._tabela_selecionada()
        self.grupo_campos.setTitle(f"Campos de {tabela}" if tabela else "Campos")
        if not tabela:
            return
        for coluna in tables.get_column_order(self.conn, tabela):
            if coluna == "ID":
                continue
            tipo, _ = field_types.tipo_do_campo(self.conn, tabela, coluna)
            item_texto = f"{coluna}  —  {tipo}"
            self.lista_campos.addItem(item_texto)
            # Guarda o nome "puro" do campo junto do item da lista (o texto
            # visivel tem o " — tipo" a mais, que nao faz parte do nome real).
            self.lista_campos.item(self.lista_campos.count() - 1).setData(Qt.UserRole, coluna)

    def _campo_selecionado(self) -> str | None:
        item = self.lista_campos.currentItem()
        return item.data(Qt.UserRole) if item else None

    # -- acoes de tabela ---------------------------------------------------

    def _nova_tabela(self) -> None:
        nome, ok = QInputDialog.getText(self, "Nova tabela", "Nome da nova tabela:")
        if not ok or not nome.strip():
            return

        copiar_de = None
        existentes = tables.list_data_sheets(self.conn)
        if existentes:
            resposta = QMessageBox.question(
                self, "Copiar estrutura?",
                "Deseja comecar copiando os campos de uma tabela ja existente?",
            )
            if resposta == QMessageBox.Yes:
                origem, ok2 = QInputDialog.getItem(self, "Copiar de qual tabela?", "Tabela de origem:", existentes, editable=False)
                if ok2:
                    copiar_de = origem

        try:
            tables.create_data_sheet(self.conn, nome.strip(), copiar_de=copiar_de, usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_tabelas(selecionar=nome.strip())

    def _renomear_tabela(self) -> None:
        atual = self._tabela_selecionada()
        if not atual:
            return
        novo, ok = QInputDialog.getText(self, "Renomear tabela", "Novo nome:", text=atual)
        if not ok or not novo.strip():
            return
        try:
            tables.rename_data_sheet(self.conn, atual, novo.strip(), usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_tabelas(selecionar=novo.strip())

    def _definir_rotulo(self) -> None:
        """Muda so o NOME DE EXIBICAO da tabela no menu lateral (nao mexe no
        nome real dela no banco) -- e o jeito de dar outro nome pra EMPRESAS/
        PESSOAS/USUARIOS (que nao podem ser renomeadas de verdade). Pra
        controlar a ORDEM das tabelas no menu, use os botoes "Mover para
        cima"/"Mover para baixo" logo abaixo da lista."""
        atual = self._tabela_selecionada()
        if not atual:
            return
        rotulo_atual = settings.obter_rotulo_tabela(self.conn, atual)
        novo_rotulo, ok = QInputDialog.getText(
            self, "Rotulo de exibicao",
            f'Como "{atual}" deve aparecer no menu lateral?\n(deixe em branco para usar o nome padrao)',
            text=rotulo_atual,
        )
        if not ok:
            return
        settings.definir_rotulo_tabela(self.conn, atual, novo_rotulo)

    def _mover_tabela(self, direcao: int) -> None:
        """Troca a tabela selecionada de posicao com a vizinha (direcao -1 =
        pra cima, +1 = pra baixo) e salva a nova ordem."""
        indice_atual = self.lista_tabelas.currentRow()
        novo_indice = indice_atual + direcao
        if indice_atual < 0 or not (0 <= novo_indice < self.lista_tabelas.count()):
            return

        ordem = [self.lista_tabelas.item(i).text() for i in range(self.lista_tabelas.count())]
        ordem[indice_atual], ordem[novo_indice] = ordem[novo_indice], ordem[indice_atual]
        tables.set_table_order(self.conn, ordem)
        self._recarregar_tabelas(selecionar=ordem[novo_indice])

    def _excluir_tabela(self) -> None:
        atual = self._tabela_selecionada()
        if not atual:
            return
        if not confirmar_exclusao(self, atual, tipo="tabela (com todos os registros dela)"):
            return
        try:
            tables.delete_data_sheet(self.conn, atual, usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_tabelas()

    # -- acoes de campo ------------------------------------------------------

    def _adicionar_campo(self) -> None:
        tabela = self._tabela_selecionada()
        if not tabela:
            return
        nome, ok = QInputDialog.getText(self, "Novo campo", "Nome do campo:")
        if not ok or not nome.strip():
            return

        tipo, ok2 = QInputDialog.getItem(
            self, "Tipo do campo", "Como esse campo deve se comportar no formulario?",
            list(field_types.TIPOS_VALIDOS), editable=False,
        )
        if not ok2:
            tipo = field_types.TEXTO

        opcoes = None
        if tipo == field_types.SELECAO:
            texto_opcoes, ok3 = QInputDialog.getMultiLineText(
                self, "Opcoes da lista", "Uma opcao por linha:",
            )
            if ok3:
                opcoes = [linha.strip() for linha in texto_opcoes.splitlines() if linha.strip()]

        try:
            tables.add_column(self.conn, tabela, nome.strip(), usuario=self.usuario_logado)
            field_types.definir_tipo_campo(self.conn, tabela, nome.strip(), tipo, opcoes)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_campos()

    def _renomear_campo(self) -> None:
        tabela = self._tabela_selecionada()
        atual = self._campo_selecionado()
        if not tabela or not atual:
            return
        novo, ok = QInputDialog.getText(self, "Renomear campo", "Novo nome:", text=atual)
        if not ok or not novo.strip():
            return
        try:
            tables.rename_column(self.conn, tabela, atual, novo.strip(), usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_campos()

    def _configurar_tipo_campo(self) -> None:
        tabela = self._tabela_selecionada()
        campo = self._campo_selecionado()
        if not tabela or not campo:
            return
        tipo_atual, opcoes_atuais = field_types.tipo_do_campo(self.conn, tabela, campo)
        tipos = list(field_types.TIPOS_VALIDOS)
        tipo, ok = QInputDialog.getItem(
            self, "Tipo do campo", f'Tipo de "{campo}":', tipos, tipos.index(tipo_atual), editable=False,
        )
        if not ok:
            return
        opcoes = opcoes_atuais
        if tipo == field_types.SELECAO:
            texto_inicial = "\n".join(opcoes_atuais or [])
            texto_opcoes, ok2 = QInputDialog.getMultiLineText(self, "Opcoes da lista", "Uma opcao por linha:", texto_inicial)
            if ok2:
                opcoes = [linha.strip() for linha in texto_opcoes.splitlines() if linha.strip()]
        else:
            opcoes = None

        field_types.definir_tipo_campo(self.conn, tabela, campo, tipo, opcoes)
        self._recarregar_campos()

    def _mover_campo(self, direcao: int) -> None:
        """Troca o campo selecionado de posicao com o vizinho (direcao -1 =
        pra cima, +1 = pra baixo) e salva a nova ordem de exibicao."""
        tabela = self._tabela_selecionada()
        if not tabela:
            return
        indice_atual = self.lista_campos.currentRow()
        novo_indice = indice_atual + direcao
        if indice_atual < 0 or not (0 <= novo_indice < self.lista_campos.count()):
            return

        ordem = [self.lista_campos.item(i).data(Qt.UserRole) for i in range(self.lista_campos.count())]
        campo_movido = ordem[indice_atual]
        ordem[indice_atual], ordem[novo_indice] = ordem[novo_indice], ordem[indice_atual]
        tables.set_column_order(self.conn, tabela, ordem)
        self._recarregar_campos()
        for i in range(self.lista_campos.count()):
            if self.lista_campos.item(i).data(Qt.UserRole) == campo_movido:
                self.lista_campos.setCurrentRow(i)
                break

    def _remover_campo(self) -> None:
        tabela = self._tabela_selecionada()
        campo = self._campo_selecionado()
        if not tabela or not campo:
            return
        if not confirmar_exclusao(self, campo, tipo="campo (com os dados que estao nele)"):
            return
        try:
            tables.drop_column(self.conn, tabela, campo, usuario=self.usuario_logado)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._recarregar_campos()
