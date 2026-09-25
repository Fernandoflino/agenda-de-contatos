"""
Tela de CONFIGURACOES: e aqui que o "tudo tem que ser personalizavel" pedido
pelo usuario vira controles concretos na tela --

- Categorias, tabelas e campos, e historico (abrem os dialogos dedicados de
  cada um, so que agora tudo agrupado numa aba so em vez de espalhado pela
  sidebar).
- Nome do painel e logotipo (aparecem na tela de login e na janela principal).
- Cor de destaque (usada nos botoes principais e itens selecionados) e o
  modo claro/escuro.
- Quais campos aparecem resumidos na lista/grade de cada tabela.

Tudo isso e lido/gravado por db/settings.py, dentro do proprio arquivo de
banco de dados -- ou seja, essas escolhas viajam junto se o arquivo for
copiado pra outro computador.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from db import settings
from db.tables import get_column_order, list_data_sheets
from ui import field_types
from ui.categorias_dialog import CategoriasDialog
from ui.historico_dialog import HistoricoDialog
from ui.lixeira_dialog import LixeiraDialog
from ui.sheet_manager_dialog import SheetManagerDialog
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela

# Campos de empresa "brutos" (ver db/settings.py -> campos_disponiveis_para_layout,
# que ja nao existe mais) que uma configuracao ANTIGA pode ter salvo como
# campo extra -- todos mapeiam pro mesmo sentinela "_EMPRESA_RESUMO" que
# ui/lista_registros_view.py entende (mostra "SIGLA - NOME" numa coluna so).
_CAMPOS_EMPRESA_BRUTOS = {"_EMPRESA_SIGLA", "_EMPRESA_SIGLA_EMPRESA", "_EMPRESA_NOME"}
_SENTINELA_EMPRESA = "_EMPRESA_RESUMO"

_TAMANHO_MAX_LOGO = 256  # pixels -- evita gravar imagens gigantes dentro do banco

_ROTULO_TEMA_CLARO = "Claro"
_ROTULO_TEMA_ESCURO = "Escuro"


def _redimensionar_para_bytes_png(caminho_imagem: str) -> bytes | None:
    """Le um arquivo de imagem do disco, redimensiona (se for maior que
    _TAMANHO_MAX_LOGO) e devolve os bytes prontos no formato PNG, pra gravar
    direto na coluna BLOB do banco de dados."""
    pixmap = QPixmap(caminho_imagem)
    if pixmap.isNull():
        return None
    if pixmap.width() > _TAMANHO_MAX_LOGO or pixmap.height() > _TAMANHO_MAX_LOGO:
        pixmap = pixmap.scaled(_TAMANHO_MAX_LOGO, _TAMANHO_MAX_LOGO, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


class SettingsDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, usuario: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario = usuario
        self._novo_logo_bytes: bytes | None = None
        self._logo_removido = False

        self.setWindowTitle("Configurações")
        preparar_janela(self, 620, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        abas = QTabWidget()
        abas.addTab(self._criar_aba_gerenciamento(), "Gerenciamento")
        abas.addTab(self._criar_aba_identidade(), "Identidade e tema")
        abas.addTab(self._criar_aba_campos_resumo(), "Campos da lista")
        layout.addWidget(abas, stretch=1)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        marcar_variante(botoes.button(QDialogButtonBox.Cancel), "secundario")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

        self._carregar_identidade_atual()

    # -- aba Gerenciamento (categorias, tabelas e campos, historico) ---------

    def _criar_aba_gerenciamento(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(10)

        explicacao = QLabel(
            "Gerencie as categorias, as tabelas e campos do banco de dados, "
            "e veja o histórico de alterações."
        )
        explicacao.setProperty("papel", "subtitulo")
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)

        for texto, funcao in (
            ("Categorias...", self._abrir_categorias),
            ("Tabelas e campos...", self._abrir_gerenciador_tabelas),
            ("Histórico...", self._abrir_historico),
            ("Lixeira...", self._abrir_lixeira),
        ):
            botao = QPushButton(texto)
            marcar_variante(botao, "secundario")
            botao.clicked.connect(funcao)
            layout.addWidget(botao)

        layout.addStretch()
        return pagina

    def _abrir_categorias(self) -> None:
        CategoriasDialog(self.conn, self.usuario, parent=self).exec()

    def _abrir_gerenciador_tabelas(self) -> None:
        SheetManagerDialog(self.conn, self.usuario, parent=self).exec()
        # a tabela usada na aba "Campos da lista" pode ter mudado
        self.combo_tabela_resumo.clear()
        self.combo_tabela_resumo.addItems(list_data_sheets(self.conn))
        if self.combo_tabela_resumo.count():
            self._recarregar_campos_resumo(self.combo_tabela_resumo.currentText())

    def _abrir_historico(self) -> None:
        HistoricoDialog(self.conn, parent=self).exec()

    def _abrir_lixeira(self) -> None:
        LixeiraDialog(self.conn, self.usuario, parent=self).exec()
        # tabelas restauradas da lixeira podem precisar aparecer nesta lista
        self.combo_tabela_resumo.clear()
        self.combo_tabela_resumo.addItems(list_data_sheets(self.conn))
        if self.combo_tabela_resumo.count():
            self._recarregar_campos_resumo(self.combo_tabela_resumo.currentText())

    # -- aba Identidade (nome, cor, tema, logotipo) --------------------------

    def _criar_aba_identidade(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(14)

        grupo_geral = QGroupBox("Nome e cor")
        form = QFormLayout(grupo_geral)
        form.setSpacing(10)

        self.campo_nome = QLineEdit()
        form.addRow("Nome do painel:", self.campo_nome)

        linha_cor = QHBoxLayout()
        linha_cor.setSpacing(10)
        self.rotulo_cor = QLabel()
        self.rotulo_cor.setFixedSize(28, 28)
        self._cor_atual = settings.COR_PADRAO
        botao_cor = QPushButton("Escolher cor...")
        marcar_variante(botao_cor, "secundario")
        botao_cor.clicked.connect(self._escolher_cor)
        linha_cor.addWidget(self.rotulo_cor)
        linha_cor.addWidget(botao_cor)
        linha_cor.addStretch()
        form.addRow("Cor de destaque:", linha_cor)

        self.combo_tema = QComboBox()
        self.combo_tema.addItem(_ROTULO_TEMA_CLARO, settings.TEMA_CLARO)
        self.combo_tema.addItem(_ROTULO_TEMA_ESCURO, settings.TEMA_ESCURO)
        form.addRow("Tema:", self.combo_tema)

        layout.addWidget(grupo_geral)

        grupo_logo = QGroupBox("Logotipo")
        layout_logo = QHBoxLayout(grupo_logo)
        layout_logo.setSpacing(14)

        self.rotulo_logo = QLabel("(sem logotipo)")
        self.rotulo_logo.setFixedSize(_TAMANHO_MAX_LOGO // 2, _TAMANHO_MAX_LOGO // 2)
        self.rotulo_logo.setAlignment(Qt.AlignCenter)
        self.rotulo_logo.setProperty("papel", "subtitulo")
        layout_logo.addWidget(self.rotulo_logo)

        botoes_logo = QVBoxLayout()
        botoes_logo.setSpacing(8)
        botao_escolher_logo = QPushButton("Escolher imagem...")
        botao_escolher_logo.clicked.connect(self._escolher_logo)
        botao_remover_logo = QPushButton("Remover logotipo")
        marcar_variante(botao_remover_logo, "secundario")
        botao_remover_logo.clicked.connect(self._remover_logo)
        botoes_logo.addWidget(botao_escolher_logo)
        botoes_logo.addWidget(botao_remover_logo)
        botoes_logo.addStretch()
        layout_logo.addLayout(botoes_logo)
        layout_logo.addStretch()

        layout.addWidget(grupo_logo)
        layout.addStretch()
        return pagina

    def _carregar_identidade_atual(self) -> None:
        branding = settings.obter_branding(self.conn)
        self.campo_nome.setText(branding.nome)
        self._definir_cor(branding.cor_destaque)
        indice_tema = self.combo_tema.findData(branding.tema)
        self.combo_tema.setCurrentIndex(indice_tema if indice_tema >= 0 else 0)
        if branding.logo:
            pixmap = QPixmap()
            pixmap.loadFromData(branding.logo)
            self.rotulo_logo.setPixmap(pixmap.scaled(
                self.rotulo_logo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

    def _definir_cor(self, cor_hex: str) -> None:
        self._cor_atual = cor_hex
        self.rotulo_cor.setStyleSheet(f"background-color: {cor_hex}; border: 1px solid #888; border-radius: 6px;")

    def _escolher_cor(self) -> None:
        cor = QColorDialog.getColor(QColor(self._cor_atual), self, "Escolher cor de destaque")
        if cor.isValid():
            self._definir_cor(cor.name())

    def _escolher_logo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Escolher logotipo", "", "Imagens (*.png *.jpg *.jpeg *.bmp)")
        if not caminho:
            return
        dados_png = _redimensionar_para_bytes_png(caminho)
        if not dados_png:
            return
        self._novo_logo_bytes = dados_png
        self._logo_removido = False
        pixmap = QPixmap()
        pixmap.loadFromData(dados_png)
        self.rotulo_logo.setPixmap(pixmap.scaled(self.rotulo_logo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _remover_logo(self) -> None:
        self._novo_logo_bytes = None
        self._logo_removido = True
        self.rotulo_logo.setPixmap(QPixmap())
        self.rotulo_logo.setText("(sem logotipo)")

    # -- aba Campos da lista -------------------------------------------------

    def _criar_aba_campos_resumo(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(12)

        explicacao = QLabel(
            "Escolha quais campos extras aparecem, ao lado do nome, na lista "
            "de registros dessa tabela -- cada um vira uma coluna, na ordem "
            "escolhida (arraste na lista da direita pra reordenar). O painel "
            "de detalhes (ao clicar num registro) já mostra todos os outros "
            "campos preenchidos, então só é preciso escolher esses aqui."
        )
        explicacao.setProperty("papel", "subtitulo")
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)

        linha_tabela = QHBoxLayout()
        linha_tabela.setSpacing(8)
        linha_tabela.addWidget(QLabel("Tabela:"))
        self.combo_tabela_resumo = QComboBox()
        self.combo_tabela_resumo.addItems(list_data_sheets(self.conn))
        self.combo_tabela_resumo.currentTextChanged.connect(self._recarregar_campos_resumo)
        linha_tabela.addWidget(self.combo_tabela_resumo, stretch=1)
        layout.addLayout(linha_tabela)

        linha_listas = QHBoxLayout()
        linha_listas.setSpacing(8)

        coluna_disponiveis = QVBoxLayout()
        coluna_disponiveis.addWidget(QLabel("Campos disponíveis:"))
        self.lista_campos_disponiveis = QListWidget()
        self.lista_campos_disponiveis.itemDoubleClicked.connect(self._adicionar_campo_escolhido)
        coluna_disponiveis.addWidget(self.lista_campos_disponiveis)
        linha_listas.addLayout(coluna_disponiveis, stretch=1)

        coluna_botoes = QVBoxLayout()
        coluna_botoes.setSpacing(8)
        coluna_botoes.addStretch()
        botao_adicionar = QPushButton("Adicionar →")
        botao_adicionar.clicked.connect(self._adicionar_campo_escolhido)
        coluna_botoes.addWidget(botao_adicionar)
        botao_remover = QPushButton("← Remover")
        marcar_variante(botao_remover, "secundario")
        botao_remover.clicked.connect(self._remover_campo_escolhido)
        coluna_botoes.addWidget(botao_remover)
        coluna_botoes.addStretch()
        linha_listas.addLayout(coluna_botoes)

        coluna_escolhidos = QVBoxLayout()
        coluna_escolhidos.addWidget(QLabel("Campos escolhidos (nesta ordem):"))
        self.lista_campos_escolhidos = QListWidget()
        self.lista_campos_escolhidos.setDragDropMode(QAbstractItemView.InternalMove)
        self.lista_campos_escolhidos.itemDoubleClicked.connect(self._remover_campo_escolhido)
        coluna_escolhidos.addWidget(self.lista_campos_escolhidos)
        linha_listas.addLayout(coluna_escolhidos, stretch=1)

        layout.addLayout(linha_listas, stretch=1)

        if self.combo_tabela_resumo.count():
            self._recarregar_campos_resumo(self.combo_tabela_resumo.currentText())
        return pagina

    def _adicionar_campo_escolhido(self) -> None:
        item = self.lista_campos_disponiveis.currentItem()
        if item is None:
            return
        novo = QListWidgetItem(item.text())
        novo.setData(Qt.UserRole, item.data(Qt.UserRole))
        self.lista_campos_escolhidos.addItem(novo)
        self.lista_campos_disponiveis.takeItem(self.lista_campos_disponiveis.row(item))

    def _remover_campo_escolhido(self) -> None:
        item = self.lista_campos_escolhidos.currentItem()
        if item is None:
            return
        novo = QListWidgetItem(item.text())
        novo.setData(Qt.UserRole, item.data(Qt.UserRole))
        self.lista_campos_disponiveis.addItem(novo)
        self.lista_campos_escolhidos.takeItem(self.lista_campos_escolhidos.row(item))

    def _opcoes_campo_extra(self, colunas: list[str]) -> list[tuple[str, str]]:
        """As opcoes do combo "Campo extra na lista": qualquer coluna de
        verdade (menos ID), com ID_EMPRESA virando uma unica opcao "Empresa"
        -- e assim que ui/lista_registros_view.py trata esse campo tambem
        (ver _colunas_extra_tabela la), entao nao faz sentido oferecer os 3
        pedacos da empresa (UF/sigla/nome) como 3 escolhas separadas aqui."""
        opcoes = [("Empresa", _SENTINELA_EMPRESA)] if "ID_EMPRESA" in colunas else []
        for coluna in colunas:
            if coluna in ("ID", "ID_EMPRESA"):
                continue
            opcoes.append((field_types.rotulo_amigavel(coluna), coluna))
        return opcoes

    def _campos_extra_atuais(self, layout_resumo: list[list[str]]) -> list[str]:
        """Os campos extras configurados ATE AGORA pra essa tabela, na ordem
        em que foram salvos, convertendo os campos "brutos" de empresa pro
        mesmo sentinela usado hoje (sem repetir a empresa mais de uma vez)."""
        campos: list[str] = []
        for linha in layout_resumo:
            for campo in linha:
                chave = _SENTINELA_EMPRESA if campo in _CAMPOS_EMPRESA_BRUTOS else campo
                if chave not in campos:
                    campos.append(chave)
        return campos

    def _recarregar_campos_resumo(self, tabela: str) -> None:
        if not tabela:
            return
        colunas = get_column_order(self.conn, tabela)
        padrao = settings.sugerir_layout_resumo(colunas)
        layout_atual = settings.obter_campos_resumo(self.conn, tabela, padrao)
        campos_atuais = self._campos_extra_atuais(layout_atual)

        rotulos_por_campo = {campo: rotulo for rotulo, campo in self._opcoes_campo_extra(colunas)}

        self.lista_campos_escolhidos.clear()
        self.lista_campos_disponiveis.clear()

        for campo in campos_atuais:
            rotulo = rotulos_por_campo.pop(campo, None)
            if rotulo is None:
                continue
            item = QListWidgetItem(rotulo)
            item.setData(Qt.UserRole, campo)
            self.lista_campos_escolhidos.addItem(item)

        for rotulo, campo in self._opcoes_campo_extra(colunas):
            if campo in campos_atuais:
                continue
            item = QListWidgetItem(rotulo)
            item.setData(Qt.UserRole, campo)
            self.lista_campos_disponiveis.addItem(item)

    # -- salvar --------------------------------------------------------------

    def _salvar(self) -> None:
        settings.salvar_branding(
            self.conn,
            nome=self.campo_nome.text().strip() or settings.NOME_PADRAO,
            cor_destaque=self._cor_atual,
            logo=self._novo_logo_bytes,
            logo_mime="image/png" if self._novo_logo_bytes else None,
            limpar_logo=self._logo_removido,
            tema=self.combo_tema.currentData(),
        )

        tabela = self.combo_tabela_resumo.currentText()
        if tabela:
            campos_extra = [
                self.lista_campos_escolhidos.item(indice).data(Qt.UserRole)
                for indice in range(self.lista_campos_escolhidos.count())
            ]
            # [[]] (uma linha vazia), nao [] -- obter_campos_resumo() trata
            # uma lista TOTALMENTE vazia como "nada configurado ainda" e
            # volta a sugestao automatica; [[]] e um valor "de verdade"
            # (uma linha sem nenhum campo), que representa "nenhum campo
            # extra" sem cair nesse fallback.
            settings.salvar_campos_resumo(
                self.conn, tabela, [[campo] for campo in campos_extra] if campos_extra else [[]]
            )

        self.accept()
