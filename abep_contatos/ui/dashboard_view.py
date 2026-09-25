"""
Esta e a tela do PAINEL (dashboard) -- a primeira coisa que aparece na
janela principal depois do login. Da um resumo rapido da situacao dos
contatos, sem precisar entrar em cada tabela pra descobrir:

- Alguns "cartoes de numero" (quantos contatos, quantas empresas, quantos
  cadastros incompletos).
- Os proximos aniversariantes, do mais perto pro mais distante, organizados
  em colunas (nome, quando, data, idade) em vez de um texto so.
- Empresas que ainda nao tem nenhum contato cadastrado.

Toda a CONTA (quantos, quem, quando) e feita em db/dashboard.py -- este
arquivo so pega esses numeros/listas prontos e desenha na tela.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from db import categorias, dashboard, preferencias, records
from db.records import resolver_empresas
from db.schema import CAMPOS_FOTO_OCULTOS, PESSOAS
from db.tables import get_column_order
from ui import field_types, icons
from ui.avatar import criar_avatar
from ui.field_types import formatar_data_exibicao
from ui.theme import cor_texto_mutado, marcar_variante
from ui.widgets import FiltroMultiplaEscolha
from ui.window_utils import limpar_layout

# Chave "de tabela" sintetica usada so pra guardar/restaurar o filtro do
# Painel em app_user_prefs (db/preferencias.py) -- o Painel nao e uma tabela
# de dados de verdade, mas reaproveita a mesma estrutura usuario+tabela+dados.
_CHAVE_PREFS_PAINEL = "_PAINEL"


def _criar_cartao_estatistica(valor: str, rotulo: str, alerta: bool = False) -> QFrame:
    """Um "cartao" pequeno com um numero grande em destaque e uma legenda
    por baixo -- usado pros indicadores do topo do painel (quantos
    contatos, quantas empresas etc.).

    `alerta=True` marca um cartao que aponta um dado FALTANDO (ex.: "sem
    e-mail") -- ganha uma cor separada da cor de destaque (ver propriedade
    "alerta" em resources/style.qss), pra chamar atencao sem depender da
    cor que a pessoa escolheu em Configuracoes."""
    cartao = QFrame()
    cartao.setObjectName("CartaoEstatistica")
    cartao.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    if alerta:
        cartao.setProperty("alerta", "true")

    layout = QVBoxLayout(cartao)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(2)

    rotulo_valor = QLabel(valor)
    rotulo_valor.setProperty("papel", "numero-grande")
    if alerta:
        rotulo_valor.setProperty("estado", "alerta")
    rotulo_valor.setAlignment(Qt.AlignCenter)
    layout.addWidget(rotulo_valor)

    rotulo_legenda = QLabel(rotulo)
    rotulo_legenda.setProperty("papel", "subtitulo")
    rotulo_legenda.setAlignment(Qt.AlignCenter)
    rotulo_legenda.setWordWrap(True)
    layout.addWidget(rotulo_legenda)

    return cartao


def _texto_dias(dias_ate: int) -> str:
    if dias_ate == 0:
        return "Hoje!"
    if dias_ate == 1:
        return "Amanhã"
    return f"Em {dias_ate} dias"


def _rotulo_coluna(texto: str) -> QLabel:
    """Cabecalho pequeno e discreto de uma coluna da tabela de aniversarios."""
    rotulo = QLabel(texto)
    rotulo.setProperty("papel", "subtitulo")
    return rotulo


def _celula_nome_aniversario(pessoa) -> QWidget:
    """Avatar + nome (e empresa, se tiver) de um aniversariante -- o mesmo
    "avatar com iniciais" usado na lista de registros, pra reconhecer quem
    e quem igual nas duas telas."""
    texto_nome = pessoa.nome + (f"  ({pessoa.empresa})" if pessoa.empresa else "")
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(criar_avatar(pessoa.nome, tamanho=26, foto_bytes=pessoa.foto))
    layout.addWidget(QLabel(texto_nome), stretch=1)
    return container


class DashboardView(QWidget):
    def __init__(self, conn: sqlite3.Connection, usuario_logado: str = "sistema", parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario_logado = usuario_logado
        self._linhas_filtro_painel: list[QWidget] = []
        self._suprimir_salvamento_prefs_painel = False

        # A tela toda fica dentro de uma area rolavel -- numa janela
        # pequena (ou com muitas empresas sem contato, por exemplo), o
        # conteudo pode ficar mais alto do que cabe na tela.
        area_rolavel = QScrollArea()
        area_rolavel.setWidgetResizable(True)
        area_rolavel.setFrameShape(QFrame.NoFrame)

        conteudo = QWidget()
        self._layout = QVBoxLayout(conteudo)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(18)

        titulo = QLabel("Painel")
        titulo.setProperty("papel", "titulo")
        self._layout.addWidget(titulo)

        self._linha_cartoes = QHBoxLayout()
        self._linha_cartoes.setSpacing(14)
        self._layout.addLayout(self._linha_cartoes)

        self._grupo_aniversarios = QGroupBox("Próximos aniversários")
        layout_grupo_aniversarios = QVBoxLayout(self._grupo_aniversarios)
        # A area de filtro fica FORA do que e limpo/reconstruido a cada
        # carregar_dados() (self._layout_aniversarios abaixo) -- senao as
        # linhas de filtro (e a selecao que a pessoa fez nelas) seriam
        # destruidas toda vez que a tela recarrega os numeros.
        layout_grupo_aniversarios.addLayout(self._montar_area_filtro_painel())
        self._layout_aniversarios = QVBoxLayout()
        layout_grupo_aniversarios.addLayout(self._layout_aniversarios)
        self._layout.addWidget(self._grupo_aniversarios)

        self._grupo_empresas_sem_contato = QGroupBox("Empresas sem nenhum contato cadastrado")
        self._layout_empresas_sem_contato = QVBoxLayout(self._grupo_empresas_sem_contato)
        self._layout.addWidget(self._grupo_empresas_sem_contato)

        self._layout.addStretch()

        area_rolavel.setWidget(conteudo)
        layout_geral = QVBoxLayout(self)
        layout_geral.setContentsMargins(0, 0, 0, 0)
        layout_geral.addWidget(area_rolavel)

        self.carregar_dados()
        self._restaurar_preferencias_painel()

    def carregar_dados(self) -> None:
        """Recalcula tudo a partir do banco -- chamado ao abrir o painel e
        toda vez que o usuario volta pra essa tela (os numeros podem ter
        mudado: um contato novo, uma data de nascimento corrigida etc.)."""
        limpar_layout(self._linha_cartoes)
        limpar_layout(self._layout_aniversarios)
        limpar_layout(self._layout_empresas_sem_contato)

        self._popular_cartoes()
        self._popular_aniversarios()
        self._popular_empresas_sem_contato()

    # -- filtro da lista de aniversariantes -----------------------------------
    # So afeta "Proximos aniversarios" -- os cartoes de numero e "Empresas
    # sem contato" continuam mostrando o total geral (decisao confirmada com
    # o usuario). Mesmo mecanismo de linhas (campo + valor, "E" entre
    # linhas) da tela de Contatos (ui/lista_registros_view.py), reaproveitando
    # os mesmos componentes de campo (FiltroMultiplaEscolha pra Categoria) --
    # so a montagem das linhas e mais simples aqui, sem as outras
    # preferencias (largura de painel, itens por pagina etc.) que a tela de
    # Contatos tambem guarda.

    def _montar_area_filtro_painel(self) -> QVBoxLayout:
        container = QVBoxLayout()
        container.setSpacing(8)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)
        rotulo_icone = QLabel()
        rotulo_icone.setPixmap(icons.icone("filtro", cor_texto_mutado(self.conn)).pixmap(16, 16))
        cabecalho.addWidget(rotulo_icone)
        cabecalho.addWidget(QLabel("Filtrar aniversariantes"))
        cabecalho.addStretch()
        botao_adicionar = QPushButton("+ Adicionar filtro")
        marcar_variante(botao_adicionar, "secundario")
        botao_adicionar.clicked.connect(self._adicionar_linha_filtro_painel)
        cabecalho.addWidget(botao_adicionar)
        container.addLayout(cabecalho)

        self._layout_linhas_filtro_painel = QVBoxLayout()
        self._layout_linhas_filtro_painel.setSpacing(6)
        container.addLayout(self._layout_linhas_filtro_painel)
        return container

    def _opcoes_de_campo_painel(self) -> list[tuple[str, str]]:
        colunas = [c for c in get_column_order(self.conn, PESSOAS) if c != "ID"]
        opcoes = []
        for coluna in colunas:
            if coluna in CAMPOS_FOTO_OCULTOS:
                continue  # nao faz sentido "filtrar por foto" digitando texto
            if coluna == "ID_EMPRESA":
                opcoes.append(("Empresa", "_EMPRESA_BUSCA"))
            else:
                opcoes.append((field_types.rotulo_amigavel(coluna), coluna))
        return opcoes

    def _adicionar_linha_filtro_painel(self) -> None:
        opcoes = self._opcoes_de_campo_painel()
        if not opcoes:
            return

        linha = QWidget()
        layout_linha = QHBoxLayout(linha)
        layout_linha.setContentsMargins(0, 0, 0, 0)
        layout_linha.setSpacing(8)

        combo_campo = QComboBox()
        for rotulo, campo in opcoes:
            combo_campo.addItem(rotulo, campo)
        combo_campo.currentIndexChanged.connect(lambda _=None, w=linha: self._trocar_campo_linha_painel(w))
        layout_linha.addWidget(combo_campo)

        layout_valor = QHBoxLayout()
        layout_valor.setContentsMargins(0, 0, 0, 0)
        layout_linha.addLayout(layout_valor, stretch=1)

        botao_remover = QToolButton()
        botao_remover.setIcon(icons.icone("fechar", cor_texto_mutado(self.conn)))
        botao_remover.setAutoRaise(True)
        botao_remover.setToolTip("Remover este filtro")
        botao_remover.clicked.connect(lambda _=None, w=linha: self._remover_linha_filtro_painel(w))
        layout_linha.addWidget(botao_remover)

        linha.combo_campo = combo_campo
        linha.layout_valor = layout_valor
        linha.widget_valor = None

        self._linhas_filtro_painel.append(linha)
        self._layout_linhas_filtro_painel.addWidget(linha)
        self._construir_widget_valor_painel(linha)
        self._ao_mudar_filtro_painel()

    def _remover_linha_filtro_painel(self, linha: QWidget) -> None:
        self._linhas_filtro_painel.remove(linha)
        self._layout_linhas_filtro_painel.removeWidget(linha)
        linha.deleteLater()
        self._ao_mudar_filtro_painel()

    def _trocar_campo_linha_painel(self, linha: QWidget) -> None:
        self._construir_widget_valor_painel(linha)
        self._ao_mudar_filtro_painel()

    def _construir_widget_valor_painel(self, linha: QWidget) -> None:
        while linha.layout_valor.count():
            item = linha.layout_valor.takeAt(0)
            widget_antigo = item.widget()
            if widget_antigo is not None:
                widget_antigo.deleteLater()

        campo = linha.combo_campo.currentData()
        if campo == "_EMPRESA_BUSCA":
            widget = QComboBox()
            widget.addItem("(todas)", None)
            for id_empresa, info in sorted(resolver_empresas(self.conn).items(), key=lambda item: str(item[1]["sigla"])):
                partes = [info["sigla"], info.get("sigla_empresa"), info["empresa"]]
                widget.addItem(" - ".join(p for p in partes if p), id_empresa)
            widget.currentIndexChanged.connect(self._ao_mudar_filtro_painel)
        elif campo == "CATEGORIA":
            widget = FiltroMultiplaEscolha("Categoria", categorias.listar_categorias(self.conn))
            widget.mudou.connect(self._ao_mudar_filtro_painel)
        else:
            widget = QLineEdit()
            widget.setPlaceholderText("valor do filtro...")
            widget.setClearButtonEnabled(True)
            widget.textChanged.connect(self._ao_mudar_filtro_painel)

        linha.layout_valor.addWidget(widget)
        linha.widget_valor = widget

    def _pessoas_filtradas(self) -> list[dict]:
        pessoas = records.get_records(self.conn, PESSOAS)
        for linha in self._linhas_filtro_painel:
            campo = linha.combo_campo.currentData()
            if not campo:
                continue
            if campo == "_EMPRESA_BUSCA":
                id_empresa = linha.widget_valor.currentData()
                if id_empresa is not None:
                    pessoas = [p for p in pessoas if p.get("ID_EMPRESA") == id_empresa]
            elif campo == "CATEGORIA":
                marcadas = set(linha.widget_valor.selecionados())
                if marcadas:
                    pessoas = [p for p in pessoas if marcadas & set(p.get("CATEGORIAS") or [])]
            else:
                texto = linha.widget_valor.text()
                if texto:
                    pessoas = records.filtrar_registros(pessoas, campo=campo, valor=texto)
        return pessoas

    def _ao_mudar_filtro_painel(self) -> None:
        limpar_layout(self._layout_aniversarios)
        self._popular_aniversarios()
        self._salvar_preferencias_painel()

    def _salvar_preferencias_painel(self) -> None:
        if self._suprimir_salvamento_prefs_painel:
            return
        filtros = []
        for linha in self._linhas_filtro_painel:
            campo = linha.combo_campo.currentData()
            if not campo:
                continue
            if isinstance(linha.widget_valor, FiltroMultiplaEscolha):
                valor = linha.widget_valor.selecionados()
            elif isinstance(linha.widget_valor, QComboBox):
                valor = linha.widget_valor.currentData()
            else:
                valor = linha.widget_valor.text()
            if not valor:
                continue
            filtros.append({"campo": campo, "valor": valor})

        prefs = preferencias.obter_preferencias(self.conn, self.usuario_logado, _CHAVE_PREFS_PAINEL)
        prefs.filtros = filtros
        preferencias.salvar_preferencias(self.conn, self.usuario_logado, _CHAVE_PREFS_PAINEL, prefs)

    def _restaurar_preferencias_painel(self) -> None:
        filtros_salvos = preferencias.obter_preferencias(self.conn, self.usuario_logado, _CHAVE_PREFS_PAINEL).filtros
        if not filtros_salvos:
            return

        campos_validos = {campo for _, campo in self._opcoes_de_campo_painel()}
        self._suprimir_salvamento_prefs_painel = True
        try:
            for item in filtros_salvos:
                campo, valor = item.get("campo"), item.get("valor")
                if campo not in campos_validos or not valor:
                    continue

                self._adicionar_linha_filtro_painel()
                linha = self._linhas_filtro_painel[-1]
                indice_campo = linha.combo_campo.findData(campo)
                if indice_campo < 0:
                    continue
                linha.combo_campo.blockSignals(True)
                linha.combo_campo.setCurrentIndex(indice_campo)
                linha.combo_campo.blockSignals(False)
                self._construir_widget_valor_painel(linha)

                if isinstance(linha.widget_valor, FiltroMultiplaEscolha):
                    linha.widget_valor.marcar(valor if isinstance(valor, list) else [valor])
                elif isinstance(linha.widget_valor, QComboBox):
                    indice_valor = linha.widget_valor.findData(valor)
                    if indice_valor >= 0:
                        linha.widget_valor.setCurrentIndex(indice_valor)
                else:
                    linha.widget_valor.setText(str(valor))
        finally:
            self._suprimir_salvamento_prefs_painel = False

        limpar_layout(self._layout_aniversarios)
        self._popular_aniversarios()

    # -- cartoes de numero ---------------------------------------------------

    def _popular_cartoes(self) -> None:
        incompletos = dashboard.contatos_incompletos(self.conn)
        cartoes = [
            (str(dashboard.total_contatos(self.conn)), "Contatos cadastrados", False),
            (str(dashboard.total_empresas(self.conn)), "Empresas associadas", False),
            (str(incompletos["sem_email"]), "Contatos sem e-mail", True),
            (str(incompletos["sem_data_nascimento"]), "Sem data de nascimento", True),
        ]
        for valor, rotulo, alerta in cartoes:
            self._linha_cartoes.addWidget(_criar_cartao_estatistica(valor, rotulo, alerta))

    # -- proximos aniversarios ------------------------------------------------

    def _popular_aniversarios(self) -> None:
        aniversariantes = dashboard.proximos_aniversarios(self.conn, limite=8, registros=self._pessoas_filtradas())
        if not aniversariantes:
            rotulo = QLabel("Nenhum contato tem uma data de nascimento cadastrada ainda.")
            rotulo.setProperty("papel", "subtitulo")
            rotulo.setWordWrap(True)
            self._layout_aniversarios.addWidget(rotulo)
            return

        # Uma tabela de verdade (colunas separadas), em vez de um texto so
        # concatenado -- cada informacao (nome, quando, data, idade) fica no
        # seu proprio lugar, sempre alinhada com a linha de cima/baixo.
        grade = QGridLayout()
        grade.setHorizontalSpacing(24)
        grade.setVerticalSpacing(10)

        for coluna, texto in enumerate(("Nome", "Quando", "Data", "Idade")):
            grade.addWidget(_rotulo_coluna(texto), 0, coluna)

        for linha, pessoa in enumerate(aniversariantes, start=1):
            grade.addWidget(_celula_nome_aniversario(pessoa), linha, 0)

            rotulo_quando = QLabel(_texto_dias(pessoa.dias_ate))
            if pessoa.dias_ate <= 1:
                # Hoje/amanha merece destaque -- e a informacao mais
                # acionavel da lista inteira.
                fonte = rotulo_quando.font()
                fonte.setBold(True)
                rotulo_quando.setFont(fonte)
            grade.addWidget(rotulo_quando, linha, 1)

            rotulo_data = QLabel(formatar_data_exibicao(pessoa.data_nascimento))
            rotulo_data.setProperty("papel", "subtitulo")
            grade.addWidget(rotulo_data, linha, 2)

            rotulo_idade = QLabel(f"completa {pessoa.idade_ao_completar}")
            rotulo_idade.setProperty("papel", "subtitulo")
            grade.addWidget(rotulo_idade, linha, 3)

        grade.setColumnStretch(0, 1)
        self._layout_aniversarios.addLayout(grade)

    # -- empresas sem contato --------------------------------------------------

    def _popular_empresas_sem_contato(self) -> None:
        faltantes = dashboard.empresas_sem_contato(self.conn)
        if not faltantes:
            rotulo = QLabel("Todas as empresas já têm pelo menos um contato cadastrado.")
            rotulo.setProperty("papel", "subtitulo")
            self._layout_empresas_sem_contato.addWidget(rotulo)
            return

        texto = "  ·  ".join(faltantes)
        rotulo = QLabel(texto)
        rotulo.setWordWrap(True)
        self._layout_empresas_sem_contato.addWidget(rotulo)
