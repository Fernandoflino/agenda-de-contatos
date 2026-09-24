"""
Esta e a primeira tela que aparece quando o programa abre (antes de ter
qualquer banco de dados carregado) -- e o equivalente ao "abrir um arquivo"
de programas como o MMEX: aqui o usuario escolhe ONDE guardar (ou onde ja
guardou) o arquivo .abepdb com os dados.

Tres opcoes, bem parecidas com "Novo/Abrir/Recentes" de qualquer editor:

1. "Novo banco de dados": pede um lugar pra SALVAR um arquivo novo (o
   programa cria e ja prepara as tabelas iniciais nele).
2. "Abrir banco de dados existente": pede pra escolher um arquivo .abepdb
   ja existente, em qualquer pasta do computador (ou de uma pasta de rede).
3. "Bancos recentes": lista rapida dos ultimos arquivos abertos com sucesso
   (lembrada em config/app_config.py).

Ao final, esta janela devolve o CAMINHO do arquivo escolhido/criado -- quem
chamou (main.py) e quem realmente abre a conexao com o banco.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from config import app_config
from db.connection import EXTENSAO_PADRAO
from ui.dialogs import mostrar_erro
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela
from versao import VERSAO

# Modos possiveis que esta tela pode devolver pra main.py decidir o que fazer:
MODO_NOVO = "novo"
MODO_ABRIR = "abrir"


class LauncherDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Painel de Contatos")
        preparar_janela(self)

        self.modo: str | None = None
        self.caminho_escolhido: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        titulo = QLabel("Painel de Contatos")
        titulo.setProperty("papel", "titulo")
        titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(titulo)

        subtitulo = QLabel("Escolha um banco de dados para começar (um arquivo que você pode guardar em qualquer pasta).")
        subtitulo.setProperty("papel", "subtitulo")
        subtitulo.setWordWrap(True)
        subtitulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitulo)

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(10)
        botao_novo = QPushButton("Novo banco de dados...")
        botao_novo.clicked.connect(self._novo_banco)
        botao_abrir = QPushButton("Abrir banco existente...")
        botao_abrir.clicked.connect(self._abrir_banco)
        linha_botoes.addWidget(botao_novo)
        linha_botoes.addWidget(botao_abrir)
        layout.addLayout(linha_botoes)

        grupo_recentes = QGroupBox("Bancos recentes")
        layout_recentes = QVBoxLayout(grupo_recentes)
        layout_recentes.setSpacing(10)

        self.lista_recentes = QListWidget()
        for caminho in app_config.bancos_recentes():
            item = QListWidgetItem(os.path.basename(caminho))
            item.setToolTip(caminho)
            item.setData(Qt.UserRole, caminho)
            self.lista_recentes.addItem(item)
        self.lista_recentes.itemDoubleClicked.connect(self._abrir_recente)
        layout_recentes.addWidget(self.lista_recentes)

        linha_recentes = QHBoxLayout()
        linha_recentes.setSpacing(8)
        botao_abrir_recente = QPushButton("Abrir selecionado")
        botao_abrir_recente.clicked.connect(self._abrir_recente_selecionado)
        botao_remover_recente = QPushButton("Remover da lista")
        marcar_variante(botao_remover_recente, "secundario")
        botao_remover_recente.clicked.connect(self._remover_recente_selecionado)
        linha_recentes.addWidget(botao_abrir_recente)
        linha_recentes.addWidget(botao_remover_recente)
        layout_recentes.addLayout(linha_recentes)

        layout.addWidget(grupo_recentes, stretch=1)

        # Mostra a versao rodando -- ajuda a confirmar se o programa aberto
        # ja e a versao mais nova do codigo (ver versao.py).
        rotulo_versao = QLabel(f"Versão {VERSAO}")
        rotulo_versao.setProperty("papel", "subtitulo")
        rotulo_versao.setAlignment(Qt.AlignCenter)
        layout.addWidget(rotulo_versao)

    # -- acoes -----------------------------------------------------------

    def _novo_banco(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Criar novo banco de dados", f"contatos{EXTENSAO_PADRAO}",
            f"Banco de dados ({'*' + EXTENSAO_PADRAO})",
        )
        if not caminho:
            return
        if not caminho.lower().endswith(EXTENSAO_PADRAO):
            caminho += EXTENSAO_PADRAO
        self.modo = MODO_NOVO
        self.caminho_escolhido = caminho
        self.accept()

    def _abrir_banco(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir banco de dados", "", f"Banco de dados ({'*' + EXTENSAO_PADRAO});;Todos os arquivos (*)",
        )
        if not caminho:
            return
        self.modo = MODO_ABRIR
        self.caminho_escolhido = caminho
        self.accept()

    def _abrir_recente(self, item: QListWidgetItem) -> None:
        self._escolher_recente(item)

    def _abrir_recente_selecionado(self) -> None:
        item = self.lista_recentes.currentItem()
        if item:
            self._escolher_recente(item)

    def _escolher_recente(self, item: QListWidgetItem) -> None:
        caminho = item.data(Qt.UserRole)
        if not os.path.isfile(caminho):
            mostrar_erro(self, f'O arquivo "{caminho}" não foi encontrado (pode ter sido movido ou apagado).')
            app_config.remover_recente(caminho)
            return
        self.modo = MODO_ABRIR
        self.caminho_escolhido = caminho
        self.accept()

    def _remover_recente_selecionado(self) -> None:
        item = self.lista_recentes.currentItem()
        if not item:
            return
        app_config.remover_recente(item.data(Qt.UserRole))
        self.lista_recentes.takeItem(self.lista_recentes.row(item))
