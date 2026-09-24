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
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from db import dashboard
from ui.avatar import criar_avatar
from ui.field_types import formatar_data_exibicao
from ui.window_utils import limpar_layout


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
    layout.addWidget(criar_avatar(pessoa.nome, tamanho=26))
    layout.addWidget(QLabel(texto_nome), stretch=1)
    return container


class DashboardView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn

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
        self._layout_aniversarios = QVBoxLayout(self._grupo_aniversarios)
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
        aniversariantes = dashboard.proximos_aniversarios(self.conn, limite=8)
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
