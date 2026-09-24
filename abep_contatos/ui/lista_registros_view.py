"""
Esta e a tela usada pra mostrar QUALQUER tabela do programa (Contatos,
Empresas, Usuarios, ou uma tabela nova que o usuario tenha criado) -- todas
no mesmo formato de painel: uma TABELA com avatar/checkbox/acoes, busca e
filtro, paginacao, e um PAINEL DE DETALHES lateral que abre ao clicar num
registro (com informacoes completas, historico de alteracoes DESSE
registro, e um campo de anotacoes livres).

Nada aqui e fixo pra uma tabela especifica -- as colunas mostradas vem do
mesmo "layout de resumo" configurado em Configuracoes -> "Campos da lista"
(ver db/settings.py), e-mail/telefone no painel de detalhes sao achados
automaticamente pelo TIPO do campo (ui/field_types.py), e a empresa
relacionada (quando a tabela tem ID_EMPRESA) e resolvida automaticamente.

Formas de restringir o que aparece na tabela, que podem ser usadas juntas
(um registro so aparece se bater em TODAS ao mesmo tempo):
- Busca livre: procura o texto digitado em QUALQUER campo do registro.
- Filtros por campo: 0 ou mais linhas, cada uma escolhendo UM campo (ex.:
  CATEGORIA) e um valor -- "+ Adicionar filtro" acrescenta outra linha,
  permitindo combinar varios campos ao mesmo tempo (ex.: Categoria = X E
  Empresa = Y).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from db import anotacoes, categorias, log, preferencias, records, settings
from db.schema import PESSOAS
from db.tables import get_column_order
from ui import field_types, icons
from ui.avatar import criar_avatar as _criar_avatar
from ui.dialogs import confirmar_exclusao, mostrar_erro, mostrar_info
from ui.record_form_dialog import RecordFormDialog
from ui.theme import cor_texto_mutado, marcar_variante
from ui.window_utils import limpar_layout

_ITENS_POR_PAGINA_PADRAO = 20
_OPCOES_ITENS_POR_PAGINA = (10, 20, 50, 100)


class ListaRegistrosView(QWidget):
    def __init__(self, conn: sqlite3.Connection, tabela: str, usuario_logado: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.tabela = tabela
        self.usuario_logado = usuario_logado

        self._todos_registros: list[dict] = []
        self._registros_filtrados: list[dict] = []
        self._layout_resumo: list[list[str]] = []
        self._campo_titulo = "ID"
        self._linhas_filtro: list[QWidget] = []
        self._pagina_atual = 0
        self._itens_por_pagina = _ITENS_POR_PAGINA_PADRAO
        # Coluna em que a pessoa clicou pra ordenar a tabela (None = ordem
        # padrao, pelo campo-titulo) -- ver _ao_clicar_cabecalho_coluna().
        self._campo_ordenacao: str | None = None
        self._ordenacao_reversa = False
        self._mapa_colunas_ordenaveis: dict[int, str] = {}
        self._ids_selecionados: set[int] = set()
        self._registro_detalhe: dict | None = None
        self._email_atual: str | None = None
        self._telefone_atual: str | None = None
        # Enquanto True, _salvar_preferencias() nao grava nada -- usado so
        # durante _restaurar_preferencias(), pra montar as linhas de filtro
        # salvas sem que os sinais disparados NO MEIO do processo (uma linha
        # comeca com um campo/valor provisorio, so depois corrigido) acabem
        # sobrescrevendo a preferencia de verdade com um estado incompleto.
        self._suprimir_salvamento_prefs = False

        self._montar_tela()
        self.carregar_dados()
        self._restaurar_preferencias()

    # -- montagem da tela ---------------------------------------------------

    def _montar_tela(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addLayout(self._montar_cabecalho())
        layout.addLayout(self._montar_barra_ferramentas())
        layout.addLayout(self._montar_area_filtros())

        self.divisor = QSplitter()
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._montar_painel_lista())
        self.painel_detalhe = self._montar_painel_detalhe()
        self.painel_detalhe.hide()
        self.divisor.addWidget(self.painel_detalhe)
        self.divisor.setStretchFactor(0, 1)
        self.divisor.setStretchFactor(1, 0)
        # Tamanho inicial do painel de detalhes (340px) -- so um PONTO DE
        # PARTIDA: como o painel tem largura minima/maxima (nao mais fixa),
        # a pessoa pode arrastar a divisoria pra deixar mais larga ou mais
        # estreita, do jeito que preferir.
        self.divisor.setSizes([760, 340])
        # Lembra a largura escolhida (por USUARIO, ver db/preferencias.py) --
        # assim, se a pessoa arrastar a divisoria uma vez, o programa abre do
        # mesmo jeito da proxima vez que ela entrar nessa tabela.
        self.divisor.splitterMoved.connect(lambda *_: self._salvar_preferencias())
        layout.addWidget(self.divisor, stretch=1)

    def _montar_cabecalho(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(12)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.rotulo_titulo = QLabel()
        self.rotulo_titulo.setProperty("papel", "titulo")
        textos.addWidget(self.rotulo_titulo)
        subtitulo = QLabel("Gerencie os registros desta tabela de forma simples e organizada.")
        subtitulo.setProperty("papel", "subtitulo")
        textos.addWidget(subtitulo)
        linha.addLayout(textos)
        linha.addStretch()

        self.rotulo_pilula = QLabel()
        self.rotulo_pilula.setProperty("papel", "pilula")
        linha.addWidget(self.rotulo_pilula, alignment=Qt.AlignTop)
        return linha

    def _montar_barra_ferramentas(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(8)

        cor_icone = cor_texto_mutado(self.conn)

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar por nome, e-mail, cargo ou palavra-chave...")
        self.campo_busca.setClearButtonEnabled(True)  # "x" pra limpar o texto digitado, de graca via o Qt
        self.campo_busca.addAction(icons.icone("busca", cor_icone), QLineEdit.LeadingPosition)
        self.campo_busca.textChanged.connect(self._ao_mudar_filtro)
        linha.addWidget(self.campo_busca, stretch=1)

        self.botao_excluir_selecionados = QPushButton("Excluir selecionados")
        marcar_variante(self.botao_excluir_selecionados, "perigo")
        self.botao_excluir_selecionados.clicked.connect(self._excluir_selecionados)
        self.botao_excluir_selecionados.hide()
        linha.addWidget(self.botao_excluir_selecionados)

        botao_novo = QPushButton("+ Novo")
        botao_novo.clicked.connect(self._criar_registro)
        linha.addWidget(botao_novo)
        return linha

    def _montar_area_filtros(self) -> QVBoxLayout:
        """A area de FILTROS POR CAMPO, embaixo da busca livre -- comeca
        vazia (so o cabecalho com o botao "+ Adicionar filtro") e cada clique
        acrescenta uma LINHA nova (campo + valor + botao de remover). Varias
        linhas ao mesmo tempo se combinam com "E" (um registro so aparece se
        bater em TODAS elas ao mesmo tempo) -- ver _aplicar_filtro().
        """
        container = QVBoxLayout()
        container.setSpacing(8)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)
        rotulo_filtro_icone = QLabel()
        rotulo_filtro_icone.setPixmap(icons.icone("filtro", cor_texto_mutado(self.conn)).pixmap(16, 16))
        cabecalho.addWidget(rotulo_filtro_icone)
        cabecalho.addWidget(QLabel("Filtros"))
        cabecalho.addStretch()
        botao_adicionar_filtro = QPushButton("+ Adicionar filtro")
        marcar_variante(botao_adicionar_filtro, "secundario")
        botao_adicionar_filtro.clicked.connect(self._adicionar_linha_filtro)
        cabecalho.addWidget(botao_adicionar_filtro)
        container.addLayout(cabecalho)

        # Onde as linhas de filtro (uma por filtro ativo) entram, uma abaixo
        # da outra -- comeca vazio (sem filtro nenhum ativo, so busca livre).
        self._layout_linhas_filtro = QVBoxLayout()
        self._layout_linhas_filtro.setSpacing(6)
        container.addLayout(self._layout_linhas_filtro)

        return container

    # -- linhas de filtro (uma por campo filtrado) ----------------------------

    def _adicionar_linha_filtro(self) -> None:
        colunas = [c for c in get_column_order(self.conn, self.tabela) if c != "ID"]
        opcoes = self._opcoes_de_campo(colunas)
        if not opcoes:
            return

        linha = QWidget()
        layout_linha = QHBoxLayout(linha)
        layout_linha.setContentsMargins(0, 0, 0, 0)
        layout_linha.setSpacing(8)

        combo_campo = QComboBox()
        for rotulo, campo in opcoes:
            combo_campo.addItem(rotulo, campo)
        combo_campo.currentIndexChanged.connect(lambda _=None, w=linha: self._ao_trocar_campo_da_linha(w))
        layout_linha.addWidget(combo_campo)

        layout_valor = QHBoxLayout()
        layout_valor.setContentsMargins(0, 0, 0, 0)
        layout_linha.addLayout(layout_valor, stretch=1)

        botao_remover = QToolButton()
        botao_remover.setIcon(icons.icone("fechar", cor_texto_mutado(self.conn)))
        botao_remover.setAutoRaise(True)
        botao_remover.setToolTip("Remover este filtro")
        botao_remover.clicked.connect(lambda _=None, w=linha: self._remover_linha_filtro(w))
        layout_linha.addWidget(botao_remover)

        # Guarda as pecas dessa linha nela mesma (o widget Python aceita
        # atributos extras normalmente) -- mais simples do que manter um
        # dicionario paralelo pra achar "qual combo pertence a qual linha".
        linha.combo_campo = combo_campo
        linha.layout_valor = layout_valor
        linha.widget_valor = None

        self._linhas_filtro.append(linha)
        self._layout_linhas_filtro.addWidget(linha)
        self._construir_widget_valor(linha)
        self._ao_mudar_filtro()

    def _remover_linha_filtro(self, linha: QWidget) -> None:
        self._linhas_filtro.remove(linha)
        self._layout_linhas_filtro.removeWidget(linha)
        linha.deleteLater()
        self._ao_mudar_filtro()

    def _ao_trocar_campo_da_linha(self, linha: QWidget) -> None:
        self._construir_widget_valor(linha)
        self._ao_mudar_filtro()

    def _construir_widget_valor(self, linha: QWidget) -> None:
        """Monta a caixinha de VALOR certa pro campo escolhido nessa linha --
        texto livre pra maioria dos campos, ou uma LISTA de valores exatos
        pra Empresa/Categoria (ver _popular_valor_combo_empresa/categoria
        pro motivo: texto livre comparava so um PEDACO do valor, trazendo
        resultado errado quando esse pedaco aparecia em outro registro por
        coincidencia)."""
        while linha.layout_valor.count():
            item = linha.layout_valor.takeAt(0)
            widget_antigo = item.widget()
            if widget_antigo is not None:
                widget_antigo.deleteLater()

        campo = linha.combo_campo.currentData()
        if campo == "_EMPRESA_BUSCA":
            widget = QComboBox()
            self._popular_valor_combo_empresa(widget)
            widget.currentIndexChanged.connect(self._ao_mudar_filtro)
        elif campo == "CATEGORIA" and self.tabela == PESSOAS:
            widget = QComboBox()
            self._popular_valor_combo_categoria(widget)
            widget.currentIndexChanged.connect(self._ao_mudar_filtro)
        else:
            widget = QLineEdit()
            widget.setPlaceholderText("valor do filtro...")
            widget.setClearButtonEnabled(True)
            widget.textChanged.connect(self._ao_mudar_filtro)

        linha.layout_valor.addWidget(widget)
        linha.widget_valor = widget

    def _popular_valor_combo_empresa(self, combo: QComboBox) -> None:
        atual = combo.currentData()
        empresas: dict[int, str] = {}
        for registro in self._todos_registros:
            id_empresa = registro.get("ID_EMPRESA")
            if id_empresa is None or id_empresa in empresas:
                continue
            rotulo = " - ".join(p for p in (registro.get("_EMPRESA_SIGLA"), registro.get("_EMPRESA_NOME")) if p)
            empresas[id_empresa] = rotulo or f"#{id_empresa}"

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(todas)", None)
        for id_empresa, rotulo in sorted(empresas.items(), key=lambda item: item[1].lower()):
            combo.addItem(rotulo, id_empresa)
        indice = combo.findData(atual) if atual else -1
        combo.setCurrentIndex(indice if indice >= 0 else 0)
        combo.blockSignals(False)

    def _popular_valor_combo_categoria(self, combo: QComboBox) -> None:
        atual = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(todas)", None)
        for nome in categorias.listar_categorias(self.conn):
            combo.addItem(nome, nome)
        indice = combo.findData(atual) if atual else -1
        combo.setCurrentIndex(indice if indice >= 0 else 0)
        combo.blockSignals(False)

    def _atualizar_combo_campo_linha(self, linha: QWidget, opcoes: list[tuple[str, str]]) -> None:
        """Reconstroi as OPCOES de campo de uma linha (o esquema pode ter
        mudado -- um campo pode ter sido renomeado/removido pela tela de
        "Tabelas e campos"), preservando a selecao atual quando ela ainda
        existe."""
        atual = linha.combo_campo.currentData()
        linha.combo_campo.blockSignals(True)
        linha.combo_campo.clear()
        for rotulo, campo in opcoes:
            linha.combo_campo.addItem(rotulo, campo)
        indice = linha.combo_campo.findData(atual)
        linha.combo_campo.setCurrentIndex(indice if indice >= 0 else 0)
        linha.combo_campo.blockSignals(False)

    def _atualizar_widget_valor_linha(self, linha: QWidget) -> None:
        """Atualiza as OPCOES da caixinha de valor (empresas/categorias
        podem ter mudado) sem trocar de widget nem perder a selecao atual --
        diferente de _construir_widget_valor(), que troca o TIPO do widget
        (chamado so quando o CAMPO da linha muda)."""
        campo = linha.combo_campo.currentData()
        if campo == "_EMPRESA_BUSCA" and isinstance(linha.widget_valor, QComboBox):
            self._popular_valor_combo_empresa(linha.widget_valor)
        elif campo == "CATEGORIA" and self.tabela == PESSOAS and isinstance(linha.widget_valor, QComboBox):
            self._popular_valor_combo_categoria(linha.widget_valor)

    # -- preferencias do usuario (filtros salvos, largura do painel) --------

    def _restaurar_preferencias(self) -> None:
        """Reaplica o que ESTA PESSOA deixou configurado da ultima vez que
        abriu esta tabela (ver db/preferencias.py) -- chamado uma unica vez,
        logo depois do primeiro carregar_dados(). Se nunca configurou nada,
        os campos vem todos vazios e a tela fica exatamente como sempre foi
        (comportamento padrao, sem filtro nenhum)."""
        prefs = preferencias.obter_preferencias(self.conn, self.usuario_logado, self.tabela)

        self._suprimir_salvamento_prefs = True
        try:
            if prefs.itens_por_pagina in _OPCOES_ITENS_POR_PAGINA:
                self._itens_por_pagina = prefs.itens_por_pagina
                indice = _OPCOES_ITENS_POR_PAGINA.index(prefs.itens_por_pagina)
                self.combo_itens_pagina.blockSignals(True)
                self.combo_itens_pagina.setCurrentIndex(indice)
                self.combo_itens_pagina.blockSignals(False)

            if prefs.largura_painel:
                self.divisor.setSizes(prefs.largura_painel)

            if prefs.filtros:
                self._restaurar_filtros_salvos(prefs.filtros)
            else:
                self._aplicar_filtro()
        finally:
            self._suprimir_salvamento_prefs = False

    def _restaurar_filtros_salvos(self, filtros_salvos: list[dict]) -> None:
        colunas = [c for c in get_column_order(self.conn, self.tabela) if c != "ID"]
        campos_validos = {campo for _, campo in self._opcoes_de_campo(colunas)}

        for item in filtros_salvos:
            campo, valor = item.get("campo"), item.get("valor")
            # Ignora silenciosamente um filtro salvo que nao faz mais sentido
            # (ex.: o campo foi removido em "Tabelas e campos" desde a ultima
            # vez) -- em vez de dar erro, a tela so abre sem essa linha.
            if campo not in campos_validos or valor in (None, ""):
                continue

            self._adicionar_linha_filtro()
            linha = self._linhas_filtro[-1]
            indice_campo = linha.combo_campo.findData(campo)
            if indice_campo < 0:
                continue
            linha.combo_campo.blockSignals(True)
            linha.combo_campo.setCurrentIndex(indice_campo)
            linha.combo_campo.blockSignals(False)
            self._construir_widget_valor(linha)

            if isinstance(linha.widget_valor, QComboBox):
                indice_valor = linha.widget_valor.findData(valor)
                if indice_valor >= 0:
                    linha.widget_valor.setCurrentIndex(indice_valor)
            else:
                linha.widget_valor.setText(str(valor))

        self._aplicar_filtro()

    def _salvar_preferencias(self) -> None:
        if self._suprimir_salvamento_prefs:
            return
        filtros = []
        for linha in self._linhas_filtro:
            campo = linha.combo_campo.currentData()
            if not campo:
                continue
            valor = linha.widget_valor.currentData() if isinstance(linha.widget_valor, QComboBox) else linha.widget_valor.text()
            if valor in (None, ""):
                continue
            filtros.append({"campo": campo, "valor": valor})

        prefs = preferencias.PreferenciasTabela(
            filtros=filtros,
            largura_painel=self.divisor.sizes(),
            itens_por_pagina=self._itens_por_pagina,
        )
        preferencias.salvar_preferencias(self.conn, self.usuario_logado, self.tabela, prefs)

    def _montar_painel_lista(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.tabela_widget = QTableWidget()
        self.tabela_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        # Sem quebra de linha: um valor longo corta com "..." (o tooltip da
        # celula mostra o texto inteiro) em vez de quebrar em varias linhas
        # e ficar cortado verticalmente -- a altura da linha e fixa (46px).
        self.tabela_widget.setWordWrap(False)
        self.tabela_widget.verticalHeader().hide()
        self.tabela_widget.cellClicked.connect(self._ao_clicar_celula)
        # Clicar num cabecalho de coluna ordena a tabela por ela (de novo no
        # mesmo cabecalho inverte a direcao) -- ver _ao_clicar_cabecalho_coluna().
        cabecalho_tabela = self.tabela_widget.horizontalHeader()
        cabecalho_tabela.setSectionsClickable(True)
        cabecalho_tabela.setSortIndicatorShown(True)
        cabecalho_tabela.sectionClicked.connect(self._ao_clicar_cabecalho_coluna)
        layout.addWidget(self.tabela_widget, stretch=1)

        layout.addLayout(self._montar_barra_paginacao())
        return container

    def _montar_barra_paginacao(self) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(10)

        self.rotulo_paginacao = QLabel()
        self.rotulo_paginacao.setProperty("papel", "subtitulo")
        linha.addWidget(self.rotulo_paginacao)
        linha.addStretch()

        self.botao_pagina_anterior = QPushButton("<")
        marcar_variante(self.botao_pagina_anterior, "secundario")
        self.botao_pagina_anterior.setFixedWidth(36)
        self.botao_pagina_anterior.clicked.connect(lambda: self._mudar_pagina(-1))
        linha.addWidget(self.botao_pagina_anterior)

        self.rotulo_pagina_atual = QLabel()
        self.rotulo_pagina_atual.setProperty("papel", "subtitulo")
        linha.addWidget(self.rotulo_pagina_atual)

        self.botao_proxima_pagina = QPushButton(">")
        marcar_variante(self.botao_proxima_pagina, "secundario")
        self.botao_proxima_pagina.setFixedWidth(36)
        self.botao_proxima_pagina.clicked.connect(lambda: self._mudar_pagina(1))
        linha.addWidget(self.botao_proxima_pagina)

        linha.addWidget(QLabel("Itens por página:"))
        self.combo_itens_pagina = QComboBox()
        for valor in _OPCOES_ITENS_POR_PAGINA:
            self.combo_itens_pagina.addItem(str(valor), valor)
        self.combo_itens_pagina.setCurrentIndex(_OPCOES_ITENS_POR_PAGINA.index(_ITENS_POR_PAGINA_PADRAO))
        self.combo_itens_pagina.currentIndexChanged.connect(self._ao_mudar_itens_por_pagina)
        linha.addWidget(self.combo_itens_pagina)
        return linha

    def _montar_painel_detalhe(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("PainelDetalhe")
        # Largura MINIMA/MAXIMA (nao fixa) -- deixa a divisoria do QSplitter
        # arrastavel de verdade, em vez de travada num tamanho so.
        painel.setMinimumWidth(300)
        painel.setMaximumWidth(520)
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        linha_fechar = QHBoxLayout()
        linha_fechar.addStretch()
        botao_fechar = QPushButton()
        botao_fechar.setIcon(icons.icone("fechar", cor_texto_mutado(self.conn)))
        marcar_variante(botao_fechar, "secundario")
        botao_fechar.setFixedSize(28, 28)
        botao_fechar.clicked.connect(self._fechar_detalhe)
        linha_fechar.addWidget(botao_fechar)
        layout.addLayout(linha_fechar)

        self._layout_cabecalho_detalhe = QVBoxLayout()
        self._layout_cabecalho_detalhe.setSpacing(10)
        layout.addLayout(self._layout_cabecalho_detalhe)

        self._layout_info_rapida = QVBoxLayout()
        self._layout_info_rapida.setSpacing(6)
        layout.addLayout(self._layout_info_rapida)

        self.abas_detalhe = QTabWidget()

        self._layout_informacoes = self._nova_aba_rolavel("Informações")
        self._layout_historico = self._nova_aba_rolavel("Histórico")

        aba_anotacoes = QWidget()
        layout_anotacoes = QVBoxLayout(aba_anotacoes)
        self.campo_anotacoes = QTextEdit()
        self.campo_anotacoes.setPlaceholderText("Escreva uma anotação sobre este registro...")
        layout_anotacoes.addWidget(self.campo_anotacoes)
        botao_salvar_anotacao = QPushButton("Salvar anotação")
        botao_salvar_anotacao.clicked.connect(self._salvar_anotacao)
        layout_anotacoes.addWidget(botao_salvar_anotacao)
        self.abas_detalhe.addTab(aba_anotacoes, "Anotações")

        layout.addWidget(self.abas_detalhe, stretch=1)

        botao_editar = QPushButton("Editar registro")
        botao_editar.clicked.connect(self._editar_registro_detalhe)
        layout.addWidget(botao_editar)

        return painel

    def _nova_aba_rolavel(self, titulo: str) -> QVBoxLayout:
        """Cria uma aba do painel de detalhes cujo conteudo pode rolar
        (Informacoes/Historico podem ter mais linhas do que cabem na
        largura fixa do painel). Devolve o layout onde o CONTEUDO da aba
        deve ser colocado."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        layout_conteudo = QVBoxLayout(conteudo)
        area.setWidget(conteudo)
        self.abas_detalhe.addTab(area, titulo)
        return layout_conteudo

    # -- opcoes de filtro -----------------------------------------------------

    def _opcoes_de_campo(self, colunas: list[str]) -> list[tuple[str, str]]:
        """Monta a lista (rotulo bonito, campo interno) usada no filtro.
        ID_EMPRESA vira "Empresa" e passa a filtrar pelo campo calculado
        _EMPRESA_BUSCA (sigla + nome) -- filtrar pelo numero interno da
        empresa nao faria sentido nenhum pra quem esta usando o programa."""
        opcoes = []
        for coluna in colunas:
            if coluna == "ID_EMPRESA":
                opcoes.append(("Empresa", "_EMPRESA_BUSCA"))
            else:
                opcoes.append((field_types.rotulo_amigavel(coluna), coluna))
        return opcoes

    # -- carregamento, filtragem e paginacao ----------------------------------

    def carregar_dados(self) -> None:
        """Busca todos os registros no banco de novo -- chamado ao abrir a
        tela e depois de qualquer criacao/edicao/exclusao."""
        self.rotulo_titulo.setText(settings.obter_rotulo_tabela(self.conn, self.tabela))

        colunas = [c for c in get_column_order(self.conn, self.tabela) if c != "ID"]
        opcoes_campo = self._opcoes_de_campo(colunas)
        for linha in self._linhas_filtro:
            self._atualizar_combo_campo_linha(linha, opcoes_campo)

        self._todos_registros = records.get_records(self.conn, self.tabela)
        self._ids_selecionados.clear()
        self._atualizar_botao_excluir_selecionados()

        # As opcoes de Empresa/Categoria de cada linha de filtro dependem
        # dos dados (quais empresas/categorias existem de verdade) -- podem
        # ter mudado desde a ultima vez (por isso atualiza de novo aqui, e
        # nao so quando a linha e criada).
        for linha in self._linhas_filtro:
            self._atualizar_widget_valor_linha(linha)

        self._aplicar_filtro()

        # Se o painel de detalhes estava aberto, atualiza com os dados
        # novos (ou fecha, se o registro foi excluido).
        if self._registro_detalhe is not None:
            id_atual = self._registro_detalhe.get("ID")
            atualizado = next((r for r in self._todos_registros if r.get("ID") == id_atual), None)
            if atualizado is not None:
                self._mostrar_detalhe(atualizado)
            else:
                self._fechar_detalhe()

    def _ao_mudar_filtro(self) -> None:
        self._pagina_atual = 0
        self._aplicar_filtro()
        self._salvar_preferencias()

    def _determinar_campo_titulo(self, colunas: list[str]) -> str:
        """O campo mais "identificador" DO PROPRIO REGISTRO -- vira o texto
        ao lado do avatar, a ordenacao da lista e o titulo do painel de
        detalhes. Monta uma lista de candidatos (os campos do layout
        configurado em Configuracoes, IGNORANDO os de empresa -- ID_EMPRESA
        e os _EMPRESA_* calculados identificam a EMPRESA relacionada, nao o
        registro em si; usar um deles aqui faria a tabela inteira mostrar o
        nome da empresa repetido, sem dar pra saber quem e quem) e entao
        escolhe o PRIMEIRO candidato que realmente tem valor preenchido na
        maioria dos registros.

        Alem de preenchido, o campo tambem precisa ter valores VARIADOS
        entre os registros -- um campo tipo TRATAMENTO ("Senhor"/"Senhora")
        ou CATEGORIA pode estar preenchido em quase todo mundo, mas repete
        o MESMO valor pra varias pessoas diferentes, entao usa-lo aqui
        deixaria a tabela cheia de gente com o titulo identico (bug ja
        visto: virou "Senhor" pra todo mundo). Um NOME de verdade e quase
        sempre diferente de pessoa pra pessoa -- e essa variedade que
        identifica "quem e quem" numa lista.
        """
        candidatos: list[str] = []
        for linha_layout in self._layout_resumo:
            for campo in linha_layout:
                if campo == "ID_EMPRESA" or campo.startswith("_EMPRESA"):
                    continue
                if campo not in candidatos:
                    candidatos.append(campo)
        if "NOME" in colunas and "NOME" not in candidatos:
            candidatos.append("NOME")
        candidatos += [c for c in colunas if c != "ID_EMPRESA" and c not in candidatos]

        if not candidatos:
            return "ID"

        total = len(self._todos_registros) or 1

        def taxa_preenchimento(campo: str) -> float:
            return sum(1 for r in self._todos_registros if r.get(campo)) / total

        def taxa_variedade(campo: str) -> float:
            valores = [r.get(campo) for r in self._todos_registros if r.get(campo)]
            return (len(set(valores)) / len(valores)) if valores else 0.0

        # 1a passada: exige preenchido E variado (um nome de verdade passa
        # aqui; TRATAMENTO/CATEGORIA nao, por terem poucos valores diferentes).
        for campo in candidatos:
            if taxa_preenchimento(campo) >= 0.5 and taxa_variedade(campo) >= 0.5:
                return campo
        # 2a passada (recuo): sem exigir variedade, so estar preenchido --
        # cobre tabelas onde genuinamente nao existe nenhum campo "unico".
        for campo in candidatos:
            if taxa_preenchimento(campo) >= 0.5:
                return campo
        return candidatos[0]

    def _titulo_do_registro(self, registro: dict) -> str:
        """O texto de identificacao de UM registro especifico -- normalmente
        o campo escolhido por _determinar_campo_titulo(), mas com uma
        cadeia de reservas pros casos em que ESSE registro em particular
        nao tem esse campo preenchido (ex.: um cargo ainda vago na planilha
        original, sem pessoa nomeada -- nesse caso, mostrar o CARGO
        ["Diretor Tecnico"] identifica a linha muito melhor do que so um
        numero de ID)."""
        valor = registro.get(self._campo_titulo)
        if valor:
            return str(valor)
        if self._campo_titulo != "NOME" and registro.get("NOME"):
            return str(registro["NOME"])
        if registro.get("CARGO"):
            return str(registro["CARGO"])
        return f'#{registro.get("ID")}'

    def _colunas_extra_tabela(self) -> list[str]:
        """Os campos extras (alem do titulo) escolhidos em Configuracoes ->
        "Campos da lista" -- na ordem em que a pessoa os colocou la --,
        virando, cada um, uma coluna na tabela.

        Os 3 campos de empresa (_EMPRESA_SIGLA / _EMPRESA_SIGLA_EMPRESA /
        _EMPRESA_NOME) sempre contam como uma UNICA coluna ("_EMPRESA_RESUMO",
        tratada especialmente em _valor_exibicao) -- nunca as 3 juntas (bug ja
        visto: a tabela de Contatos mostrava so Sigla/UF/Nome da empresa
        repetidos, sem sobrar espaco pra dado da pessoa).
        """
        vistos = {self._campo_titulo, "ID_EMPRESA"}
        campos_empresa = {"_EMPRESA_SIGLA", "_EMPRESA_SIGLA_EMPRESA", "_EMPRESA_NOME", "_EMPRESA_BUSCA"}

        extras: list[str] = []
        empresa_ja_incluida = False
        for linha_layout in self._layout_resumo:
            for campo in linha_layout:
                if campo in vistos:
                    continue
                if campo in campos_empresa:
                    if not empresa_ja_incluida:
                        extras.append("_EMPRESA_RESUMO")
                        empresa_ja_incluida = True
                    continue
                if campo not in extras:
                    extras.append(campo)
        return extras

    def _aplicar_filtro(self) -> None:
        """Aplica a busca livre + TODAS as linhas de filtro ativas ao mesmo
        tempo -- um registro so aparece se bater em CADA UMA delas (filtros
        "E", nao "OU"). Cada linha e aplicada em sequencia, sempre reduzindo
        (nunca ampliando) o resultado da linha anterior."""
        filtrados = self._todos_registros

        for linha in self._linhas_filtro:
            campo = linha.combo_campo.currentData()
            if not campo:
                continue
            if campo == "_EMPRESA_BUSCA":
                # Filtro de empresa e por ID EXATO (escolhido numa lista), nao
                # por texto -- ver _popular_valor_combo_empresa() pro motivo
                # (2 letras de UF batiam em qualquer nome de empresa que
                # tivesse essas letras juntas em outro lugar).
                id_empresa_filtro = linha.widget_valor.currentData()
                if id_empresa_filtro is not None:
                    filtrados = [r for r in filtrados if r.get("ID_EMPRESA") == id_empresa_filtro]
            elif campo == "CATEGORIA" and self.tabela == PESSOAS:
                # Um contato pode ter varias categorias ao mesmo tempo --
                # aparece se tiver a categoria escolhida ENTRE as suas (nao
                # precisa ser a unica). Pra filtrar por mais de uma categoria
                # de uma vez, basta adicionar mais uma linha de filtro
                # "Categoria" (as linhas se combinam com "E" entre si, como
                # qualquer outro filtro desta tela).
                categoria_filtro = linha.widget_valor.currentData()
                if categoria_filtro is not None:
                    filtrados = [r for r in filtrados if categoria_filtro in (r.get("CATEGORIAS") or [])]
            else:
                texto = linha.widget_valor.text()
                if texto:
                    filtrados = records.filtrar_registros(filtrados, campo=campo, valor=texto)

        filtrados = records.filtrar_registros(filtrados, busca=self.campo_busca.text())

        colunas = get_column_order(self.conn, self.tabela)
        padrao = settings.sugerir_layout_resumo(colunas)
        self._layout_resumo = settings.obter_campos_resumo(self.conn, self.tabela, padrao)
        self._campo_titulo = self._determinar_campo_titulo(colunas)

        # Sem coluna escolhida pela pessoa (estado inicial): ordem padrao,
        # pelo campo-titulo. Depois que ela clica num cabecalho, essa
        # escolha manda ate a pessoa clicar em outro cabecalho.
        if self._campo_ordenacao is None:
            self._registros_filtrados = sorted(filtrados, key=lambda r: self._titulo_do_registro(r).lower())
        else:
            self._registros_filtrados = sorted(
                filtrados,
                key=lambda r: self._valor_ordenacao(r, self._campo_ordenacao),
                reverse=self._ordenacao_reversa,
            )

        total_paginas = max(1, -(-len(self._registros_filtrados) // self._itens_por_pagina))
        self._pagina_atual = min(self._pagina_atual, total_paginas - 1)

        self._atualizar_pilula()
        self._popular_tabela()
        self._atualizar_barra_paginacao(total_paginas)

    def _mudar_pagina(self, delta: int) -> None:
        self._pagina_atual += delta
        self._aplicar_filtro()

    def _ao_mudar_itens_por_pagina(self) -> None:
        self._itens_por_pagina = self.combo_itens_pagina.currentData()
        self._pagina_atual = 0
        self._aplicar_filtro()
        self._salvar_preferencias()

    def _atualizar_pilula(self) -> None:
        total = len(self._todos_registros)
        mostrando = len(self._registros_filtrados)
        texto = f"{mostrando} de {total} registros" if mostrando != total else f"{total} registro(s)"
        self.rotulo_pilula.setText(texto)

    def _atualizar_barra_paginacao(self, total_paginas: int) -> None:
        total = len(self._registros_filtrados)
        if total == 0:
            self.rotulo_paginacao.setText("Nenhum registro encontrado.")
        else:
            inicio = self._pagina_atual * self._itens_por_pagina + 1
            fim = min(inicio + self._itens_por_pagina - 1, total)
            self.rotulo_paginacao.setText(f"Mostrando {inicio} a {fim} de {total}")
        self.rotulo_pagina_atual.setText(f"Página {self._pagina_atual + 1} de {total_paginas}")
        self.botao_pagina_anterior.setEnabled(self._pagina_atual > 0)
        self.botao_proxima_pagina.setEnabled(self._pagina_atual < total_paginas - 1)

    # -- tabela --------------------------------------------------------------

    def _eh_campo_data(self, campo: str) -> bool:
        if campo.startswith("_"):
            return False
        return field_types.tipo_do_campo(self.conn, self.tabela, campo)[0] == field_types.DATA

    def _rotulo_coluna_tabela(self, campo: str) -> str:
        if campo == "_EMPRESA_RESUMO":
            return "Empresa"
        return field_types.rotulo_amigavel(campo)

    def _valor_exibicao(self, registro: dict, campo: str) -> str:
        if campo == "_EMPRESA_RESUMO":
            texto = " - ".join(p for p in (registro.get("_EMPRESA_SIGLA"), registro.get("_EMPRESA_NOME")) if p)
            return texto or "—"
        valor = registro.get(campo)
        if not valor:
            return "—"
        return field_types.formatar_data_exibicao(valor) if self._eh_campo_data(campo) else str(valor)

    def _valor_ordenacao(self, registro: dict, campo: str) -> str:
        """Chave de ordenacao pra um campo de coluna -- sempre o valor CRU
        do registro (nunca o texto formatado de _valor_exibicao), pra datas
        (guardadas em ISO aaaa-mm-dd) ordenarem cronologicamente em vez de
        alfabeticamente pelo texto exibido (dd/mm/aaaa)."""
        if campo == "_EMPRESA_RESUMO":
            valor = " - ".join(p for p in (registro.get("_EMPRESA_SIGLA"), registro.get("_EMPRESA_NOME")) if p)
        else:
            valor = registro.get(campo)
        return str(valor).lower() if valor else ""

    def _pagina_atual_de_registros(self) -> list[dict]:
        inicio = self._pagina_atual * self._itens_por_pagina
        return self._registros_filtrados[inicio:inicio + self._itens_por_pagina]

    def _popular_tabela(self) -> None:
        extras = self._colunas_extra_tabela()
        cabecalhos = ["", field_types.rotulo_amigavel(self._campo_titulo)]
        cabecalhos += [self._rotulo_coluna_tabela(c) for c in extras]
        # Coluna INVISIVEL (sem cabecalho, sem conteudo) entre os dados e
        # "Acoes" -- e ela, sozinha, que fica "Stretch" (ver mais abaixo),
        # absorvendo o espaco sobrando pra "Acoes" continuar sempre grudada
        # na borda direita da tabela, mesmo com as colunas de dados no
        # tamanho justo do proprio conteudo (bug ja visto: sem essa coluna,
        # "Acoes" ficava largada logo apos a ultima coluna de dados, com um
        # vao cinza vazio ate a borda de verdade da janela).
        indice_espacador = len(cabecalhos)
        cabecalhos.append("")
        cabecalhos.append("Ações")

        # Quais colunas podem ser ordenadas ao clicar no cabecalho, e qual
        # CAMPO cada uma representa -- o checkbox, a espacadora e "Acoes"
        # ficam de fora (ver _ao_clicar_cabecalho_coluna()).
        self._mapa_colunas_ordenaveis = {1: self._campo_titulo}
        self._mapa_colunas_ordenaveis.update({2 + i: campo for i, campo in enumerate(extras)})

        self.tabela_widget.setRowCount(0)
        self.tabela_widget.setColumnCount(len(cabecalhos))
        self.tabela_widget.setHorizontalHeaderLabels(cabecalhos)

        pagina = self._pagina_atual_de_registros()
        self.tabela_widget.setRowCount(len(pagina))

        for linha, registro in enumerate(pagina):
            id_registro = registro.get("ID")

            caixa_selecao = QCheckBox()
            caixa_selecao.setChecked(id_registro in self._ids_selecionados)
            caixa_selecao.toggled.connect(lambda marcado, rid=id_registro: self._alternar_selecao(rid, marcado))
            container_caixa = QWidget()
            layout_caixa = QHBoxLayout(container_caixa)
            layout_caixa.setContentsMargins(0, 0, 0, 0)
            layout_caixa.setAlignment(Qt.AlignCenter)
            layout_caixa.addWidget(caixa_selecao)
            self.tabela_widget.setCellWidget(linha, 0, container_caixa)

            titulo_valor = self._titulo_do_registro(registro)
            celula_titulo = QWidget()
            layout_titulo = QHBoxLayout(celula_titulo)
            layout_titulo.setContentsMargins(6, 4, 6, 4)
            layout_titulo.setSpacing(8)
            layout_titulo.addWidget(_criar_avatar(titulo_valor, tamanho=30))
            rotulo_titulo_celula = QLabel(titulo_valor)
            rotulo_titulo_celula.setWordWrap(False)
            layout_titulo.addWidget(rotulo_titulo_celula, stretch=1)
            self.tabela_widget.setCellWidget(linha, 1, celula_titulo)

            for indice_extra, campo in enumerate(extras):
                texto_celula = self._valor_exibicao(registro, campo)
                item = QTableWidgetItem(texto_celula)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                # Nomes de empresa longos sao cortados (com "...") pra
                # coluna nao tomar todo o espaco -- o texto completo ainda
                # da pra ver passando o mouse em cima.
                item.setToolTip(texto_celula)
                self.tabela_widget.setItem(linha, 2 + indice_extra, item)

            botao_acoes = QToolButton()
            botao_acoes.setText("⋮")
            botao_acoes.setPopupMode(QToolButton.InstantPopup)
            marcar_variante(botao_acoes, "secundario")
            # O "⋮" ja deixa claro que abre um menu -- sem isso, o Qt
            # desenha TAMBEM uma setinha de dropdown ao lado, apertada
            # demais pra caber bem numa coluna de 44px.
            botao_acoes.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
            menu = QMenu(botao_acoes)
            menu.addAction("Editar", lambda r=registro: self._editar_registro(r))
            menu.addAction("Excluir", lambda r=registro: self._excluir_registro(r))
            botao_acoes.setMenu(menu)
            self.tabela_widget.setCellWidget(linha, len(cabecalhos) - 1, botao_acoes)

            self.tabela_widget.setRowHeight(linha, 46)

        # Colunas de TEXTO (titulo + extras) tem largura BASEADA NO CONTEUDO
        # de cada uma (resizeColumnToContents, igual o Qt calcularia numa
        # coluna normal) -- nao um numero fixo igual pra todas, e nao
        # "Stretch" tambem igual pra todas: o Qt divide o espaco sobrando
        # em PARTES IGUAIS entre colunas "Stretch" (testado à parte), sem
        # ligar pro tamanho de cada uma, entao uma coluna de conteudo curto
        # (ex.: "UF") acabava do mesmo tamanho que uma de texto longo (ex.:
        # "Empresa por extenso"), desperdicando espaco de um lado e cortando
        # texto do outro (bug ja visto, reportado pelo usuario). Cada coluna
        # continua ajustavel a mao (Interactive) se a pessoa quiser mudar.
        # "Acoes" e o checkbox continuam com largura FIXA, sempre visiveis.
        cabecalho = self.tabela_widget.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.Fixed)
        self.tabela_widget.setColumnWidth(0, 40)

        _LARGURA_MIN_COLUNA_TEXTO = 90
        _LARGURA_MAX_COLUNA_TITULO = 480
        _LARGURA_MAX_COLUNA_EXTRA = 320
        for indice in range(1, indice_espacador):
            self.tabela_widget.resizeColumnToContents(indice)
            largura_max = _LARGURA_MAX_COLUNA_TITULO if indice == 1 else _LARGURA_MAX_COLUNA_EXTRA
            largura = max(
                _LARGURA_MIN_COLUNA_TEXTO,
                min(self.tabela_widget.columnWidth(indice) + 16, largura_max),
            )
            self.tabela_widget.setColumnWidth(indice, largura)
            cabecalho.setSectionResizeMode(indice, QHeaderView.Interactive)

        # A coluna espacadora e a UNICA "Stretch" -- sozinha, ela absorve
        # TODO o espaco sobrando (ver comentario la em cima, onde ela e
        # criada), sem competir com nenhuma outra coluna de dados.
        cabecalho.setSectionResizeMode(indice_espacador, QHeaderView.Stretch)

        # A largura da coluna "Acoes" soma um espaco extra do tamanho da
        # PROPRIA barra de rolagem vertical (perguntado ao Qt, nao um
        # numero fixo no chute) -- sem isso, quando a lista tem registros
        # suficientes pra precisar de rolagem, a barra sobrepunha o botao
        # de acoes, cortando ele (bug ja visto).
        largura_barra_rolagem = self.tabela_widget.verticalScrollBar().sizeHint().width()
        cabecalho.setSectionResizeMode(len(cabecalhos) - 1, QHeaderView.Fixed)
        self.tabela_widget.setColumnWidth(len(cabecalhos) - 1, 44 + largura_barra_rolagem)

        # Setinha do cabecalho: mostra em qual coluna a tabela esta ordenada
        # agora, se a pessoa ja clicou em alguma (fora do estado inicial).
        indice_ordenado = next(
            (i for i, campo in self._mapa_colunas_ordenaveis.items() if campo == self._campo_ordenacao), None
        )
        if indice_ordenado is None:
            cabecalho.setSortIndicatorShown(False)
        else:
            cabecalho.setSortIndicatorShown(True)
            ordem = Qt.DescendingOrder if self._ordenacao_reversa else Qt.AscendingOrder
            cabecalho.setSortIndicator(indice_ordenado, ordem)

    def _ao_clicar_cabecalho_coluna(self, coluna: int) -> None:
        """Clicar num cabecalho ordena a tabela por essa coluna -- clicar de
        novo no MESMO cabecalho inverte a direcao (crescente/decrescente).
        O checkbox, a espacadora invisivel e "Acoes" nao tem campo associado
        (ver _mapa_colunas_ordenaveis em _popular_tabela) e ignoram o clique."""
        campo = self._mapa_colunas_ordenaveis.get(coluna)
        if not campo:
            return
        if campo == self._campo_ordenacao:
            self._ordenacao_reversa = not self._ordenacao_reversa
        else:
            self._campo_ordenacao = campo
            self._ordenacao_reversa = False
        self._pagina_atual = 0
        self._aplicar_filtro()

    def _ao_clicar_celula(self, linha: int, coluna: int) -> None:
        # A 1a coluna (checkbox), a penultima (espacadora invisivel, sem
        # conteudo) e a ultima (Acoes, com widget proprio) nao abrem o
        # painel de detalhes -- so o resto da linha faz isso.
        if coluna in (0, self.tabela_widget.columnCount() - 2, self.tabela_widget.columnCount() - 1):
            return
        pagina = self._pagina_atual_de_registros()
        if 0 <= linha < len(pagina):
            self._mostrar_detalhe(pagina[linha])

    def _alternar_selecao(self, id_registro: int, marcado: bool) -> None:
        if marcado:
            self._ids_selecionados.add(id_registro)
        else:
            self._ids_selecionados.discard(id_registro)
        self._atualizar_botao_excluir_selecionados()

    def _atualizar_botao_excluir_selecionados(self) -> None:
        quantidade = len(self._ids_selecionados)
        self.botao_excluir_selecionados.setText(f"Excluir selecionados ({quantidade})")
        self.botao_excluir_selecionados.setVisible(quantidade > 0)

    # -- painel de detalhes ----------------------------------------------------

    def _subtitulo_detalhe(self, registro: dict) -> str | None:
        return str(registro["CARGO"]) if registro.get("CARGO") else None

    def _mostrar_detalhe(self, registro: dict) -> None:
        self._registro_detalhe = registro
        self.painel_detalhe.show()

        limpar_layout(self._layout_cabecalho_detalhe)
        limpar_layout(self._layout_info_rapida)

        titulo_valor = self._titulo_do_registro(registro)

        linha_avatar = QHBoxLayout()
        linha_avatar.setSpacing(10)
        linha_avatar.addWidget(_criar_avatar(titulo_valor, tamanho=56))
        bloco_nome = QVBoxLayout()
        bloco_nome.setSpacing(2)
        rotulo_nome = QLabel(titulo_valor)
        rotulo_nome.setProperty("papel", "titulo")
        rotulo_nome.setWordWrap(True)
        rotulo_nome.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bloco_nome.addWidget(rotulo_nome)
        subtitulo_valor = self._subtitulo_detalhe(registro)
        if subtitulo_valor:
            rotulo_subtitulo = QLabel(subtitulo_valor)
            rotulo_subtitulo.setProperty("papel", "subtitulo")
            rotulo_subtitulo.setTextInteractionFlags(Qt.TextSelectableByMouse)
            bloco_nome.addWidget(rotulo_subtitulo)
        linha_avatar.addLayout(bloco_nome, stretch=1)
        self._layout_cabecalho_detalhe.addLayout(linha_avatar)

        categorias_pessoa = registro.get("CATEGORIAS")
        if categorias_pessoa is None and registro.get("CATEGORIA"):
            categorias_pessoa = [registro["CATEGORIA"]]
        if categorias_pessoa:
            linha_pilulas = QHBoxLayout()
            linha_pilulas.setSpacing(6)
            for nome_categoria in categorias_pessoa:
                rotulo_tag = QLabel(str(nome_categoria))
                rotulo_tag.setProperty("papel", "pilula")
                rotulo_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                linha_pilulas.addWidget(rotulo_tag)
            linha_pilulas.addStretch()
            self._layout_cabecalho_detalhe.addLayout(linha_pilulas)

        colunas = get_column_order(self.conn, self.tabela)
        campo_email = next(
            (c for c in colunas if field_types.tipo_do_campo(self.conn, self.tabela, c)[0] == field_types.EMAIL),
            None,
        )
        campo_tel = next(
            (c for c in colunas if field_types.tipo_do_campo(self.conn, self.tabela, c)[0] == field_types.TEL),
            None,
        )
        self._email_atual = registro.get(campo_email) if campo_email else None
        self._telefone_atual = registro.get(campo_tel) if campo_tel else None

        if registro.get("_EMPRESA_NOME") or registro.get("_EMPRESA_SIGLA"):
            texto_empresa = " - ".join(p for p in (registro.get("_EMPRESA_SIGLA"), registro.get("_EMPRESA_NOME")) if p)
            self._layout_info_rapida.addWidget(self._linha_info("empresa", texto_empresa))
        if self._email_atual:
            self._layout_info_rapida.addWidget(self._linha_info("email", str(self._email_atual)))
        if self._telefone_atual:
            self._layout_info_rapida.addWidget(self._linha_info("telefone", str(self._telefone_atual)))

        self._popular_aba_informacoes(registro, colunas)
        self._popular_aba_historico(registro)
        self._popular_aba_anotacoes(registro)

    def _linha_info(self, nome_icone: str, valor: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        rotulo_icone = QLabel()
        rotulo_icone.setPixmap(icons.icone(nome_icone, cor_texto_mutado(self.conn)).pixmap(16, 16))
        rotulo_icone.setFixedWidth(16)
        layout.addWidget(rotulo_icone, alignment=Qt.AlignTop)

        texto = QLabel(valor)
        texto.setWordWrap(True)
        texto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(texto, stretch=1)
        return container

    def _popular_aba_informacoes(self, registro: dict, colunas: list[str]) -> None:
        limpar_layout(self._layout_informacoes)
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)

        linha = 0
        for campo in colunas:
            if campo in ("ID", "ID_EMPRESA") or not registro.get(campo):
                continue
            rotulo = QLabel(field_types.rotulo_amigavel(campo))
            rotulo.setProperty("papel", "subtitulo")
            grade.addWidget(rotulo, linha, 0)
            valor_label = QLabel(self._valor_exibicao(registro, campo))
            valor_label.setWordWrap(True)
            valor_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grade.addWidget(valor_label, linha, 1)
            linha += 1

        if registro.get("_EMPRESA_NOME"):
            rotulo = QLabel("Empresa")
            rotulo.setProperty("papel", "subtitulo")
            grade.addWidget(rotulo, linha, 0)
            valor_empresa = QLabel(str(registro["_EMPRESA_NOME"]))
            valor_empresa.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grade.addWidget(valor_empresa, linha, 1)

        grade.setColumnStretch(1, 1)
        self._layout_informacoes.addLayout(grade)
        self._layout_informacoes.addStretch()

    def _popular_aba_historico(self, registro: dict) -> None:
        limpar_layout(self._layout_historico)
        historico = log.historico_do_registro(self.conn, self.tabela, registro["ID"])
        if not historico:
            rotulo = QLabel("Nenhuma alteração registrada para este registro ainda.")
            rotulo.setProperty("papel", "subtitulo")
            rotulo.setWordWrap(True)
            self._layout_historico.addWidget(rotulo)
            return

        for item in historico:
            data_exibida = field_types.formatar_data_exibicao(item["data_hora"][:10])
            rotulo = QLabel(f'{data_exibida} · {item["usuario"]} · {item["acao"]}')
            rotulo.setWordWrap(True)
            rotulo.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._layout_historico.addWidget(rotulo)
        self._layout_historico.addStretch()

    def _popular_aba_anotacoes(self, registro: dict) -> None:
        texto = anotacoes.obter_anotacao(self.conn, self.tabela, registro["ID"])
        self.campo_anotacoes.blockSignals(True)
        self.campo_anotacoes.setPlainText(texto)
        self.campo_anotacoes.blockSignals(False)

    def _salvar_anotacao(self) -> None:
        if self._registro_detalhe is None:
            return
        anotacoes.salvar_anotacao(self.conn, self.tabela, self._registro_detalhe["ID"], self.campo_anotacoes.toPlainText())
        mostrar_info(self, "Anotação salva.")

    def _fechar_detalhe(self) -> None:
        self._registro_detalhe = None
        self.painel_detalhe.hide()

    # -- acoes (criar/editar/excluir) ---------------------------------------

    def _criar_registro(self) -> None:
        dialogo = RecordFormDialog(self.conn, self.tabela, registro=None, parent=self)
        if dialogo.exec():
            try:
                novo_id = records.create_record(self.conn, self.tabela, dialogo.resultado(), usuario=self.usuario_logado)
                if self.tabela == PESSOAS:
                    categorias.definir_categorias_da_pessoa(self.conn, novo_id, dialogo.resultado_categorias() or [])
            except (ValueError, sqlite3.Error) as erro:
                mostrar_erro(self, str(erro))
                return
            self.carregar_dados()

    def _editar_registro(self, registro: dict) -> None:
        dialogo = RecordFormDialog(self.conn, self.tabela, registro=registro, parent=self)
        if dialogo.exec():
            try:
                records.update_record(self.conn, self.tabela, registro["ID"], dialogo.resultado(), usuario=self.usuario_logado)
                if self.tabela == PESSOAS:
                    categorias.definir_categorias_da_pessoa(
                        self.conn, registro["ID"], dialogo.resultado_categorias() or []
                    )
            except (ValueError, sqlite3.Error) as erro:
                mostrar_erro(self, str(erro))
                return
            self.carregar_dados()

    def _editar_registro_detalhe(self) -> None:
        if self._registro_detalhe is not None:
            self._editar_registro(self._registro_detalhe)

    def _excluir_registro(self, registro: dict) -> None:
        rotulo = self._titulo_do_registro(registro)
        if not confirmar_exclusao(self, rotulo):
            return
        try:
            records.delete_record(self.conn, self.tabela, registro["ID"], usuario=self.usuario_logado)
        except (ValueError, sqlite3.Error) as erro:
            mostrar_erro(self, str(erro))
            return
        self._ids_selecionados.discard(registro["ID"])
        self.carregar_dados()

    def _excluir_selecionados(self) -> None:
        if not self._ids_selecionados:
            return
        if not confirmar_exclusao(self, f"{len(self._ids_selecionados)} registro(s) selecionado(s)"):
            return
        for id_registro in list(self._ids_selecionados):
            try:
                records.delete_record(self.conn, self.tabela, id_registro, usuario=self.usuario_logado)
            except (ValueError, sqlite3.Error):
                pass
        self._ids_selecionados.clear()
        self.carregar_dados()
