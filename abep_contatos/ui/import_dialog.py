"""
Tela de IMPORTACAO: le um arquivo .xlsx (Excel) ou .csv no MESMO formato que
a tela de Exportacao (modo "Simples") gera e aplica no banco -- quem ja
existe (pelo ID) e atualizado, quem nao existe ainda e criado. Ver
db/importer_planilha.py pra entender a logica por tras da decisao de
criar/atualizar/apagar celulas em branco.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from db import importer_planilha
from db.schema import PESSOAS
from db.tables import list_data_sheets
from ui.dialogs import mostrar_erro, mostrar_info
from ui.window_utils import preparar_janela


class ImportDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, usuario: str, tabela_padrao: str = PESSOAS, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario = usuario
        self._caminho: str | None = None
        self._colunas_lidas: list[str] | None = None
        self._linhas_lidas: list[dict] | None = None
        self.setWindowTitle("Importar planilha")
        preparar_janela(self, 560, 460)

        self.combo_tabela = QComboBox()
        self.combo_tabela.addItems(list_data_sheets(conn))
        indice_padrao = self.combo_tabela.findText(tabela_padrao)
        if indice_padrao >= 0:
            self.combo_tabela.setCurrentIndex(indice_padrao)
        self.combo_tabela.currentTextChanged.connect(self._revalidar_previa)

        self.rotulo_arquivo = QLabel("Nenhum arquivo selecionado.")
        botao_selecionar = QPushButton("Selecionar arquivo...")
        botao_selecionar.clicked.connect(self._selecionar_arquivo)

        self.rotulo_resumo = QLabel("")
        self.rotulo_resumo.setWordWrap(True)
        self.lista_avisos = QListWidget()

        self.botao_importar = QPushButton("Importar")
        self.botao_importar.setEnabled(False)
        self.botao_importar.clicked.connect(self._importar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        linha_tabela = QHBoxLayout()
        linha_tabela.addWidget(QLabel("Tabela:"))
        linha_tabela.addWidget(self.combo_tabela, stretch=1)
        layout.addLayout(linha_tabela)

        linha_arquivo = QHBoxLayout()
        linha_arquivo.addWidget(self.rotulo_arquivo, stretch=1)
        linha_arquivo.addWidget(botao_selecionar)
        layout.addLayout(linha_arquivo)

        layout.addWidget(self.rotulo_resumo)
        layout.addWidget(QLabel("Avisos:"))
        layout.addWidget(self.lista_avisos, stretch=1)

        botoes = QHBoxLayout()
        botoes.addStretch()
        botoes.addWidget(self.botao_importar)
        layout.addLayout(botoes)

    # -- selecionar arquivo e pre-visualizar --------------------------------

    def _selecionar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha", "", "Planilha Excel (*.xlsx);;Arquivo CSV (*.csv)"
        )
        if not caminho:
            return

        try:
            colunas, linhas = importer_planilha.ler_planilha(caminho)
        except (ValueError, OSError) as erro:
            mostrar_erro(self, str(erro))
            return

        if not linhas:
            mostrar_erro(self, "Nenhum registro encontrado nesse arquivo.")
            return

        self._caminho = caminho
        self._colunas_lidas = colunas
        self._linhas_lidas = linhas
        self.rotulo_arquivo.setText(caminho)
        self._revalidar_previa()

    def _revalidar_previa(self) -> None:
        if self._colunas_lidas is None or self._linhas_lidas is None:
            return

        tabela = self.combo_tabela.currentText()
        resumo = importer_planilha.importar_planilha(
            self.conn, tabela, self._colunas_lidas, self._linhas_lidas, usuario=self.usuario, aplicar=False
        )
        self._resumo_previa = resumo

        texto = f"{resumo.criados} novo(s), {resumo.atualizados} atualizado(s)"
        if resumo.empresas_criadas:
            texto += f", {resumo.empresas_criadas} empresa(s) nova(s)"
        if resumo.colunas_novas:
            texto += f"\nColunas novas (serão criadas): {', '.join(resumo.colunas_novas)}"
        self.rotulo_resumo.setText(texto)

        self.lista_avisos.clear()
        self.lista_avisos.addItems(resumo.avisos)

        self.botao_importar.setEnabled(True)

    # -- importar -------------------------------------------------------

    def _importar(self) -> None:
        tabela = self.combo_tabela.currentText()
        resumo = importer_planilha.importar_planilha(
            self.conn, tabela, self._colunas_lidas, self._linhas_lidas, usuario=self.usuario, aplicar=True
        )
        mensagem = f"{resumo.criados} registro(s) criado(s), {resumo.atualizados} atualizado(s)."
        if resumo.empresas_criadas:
            mensagem += f"\n{resumo.empresas_criadas} empresa(s) nova(s) criada(s)."
        mostrar_info(self, mensagem)
        self.accept()
