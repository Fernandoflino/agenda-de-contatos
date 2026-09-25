"""
Tela da LIXEIRA: mostra tudo que foi excluido (registros, tabelas inteiras,
campos/colunas) e ainda nao foi excluido DEFINITIVAMENTE -- toda a logica de
capturar/restaurar/apagar de vez fica em db/lixeira.py, este arquivo so
desenha a lista e os botoes.

Qualquer usuario logado pode restaurar ou esvaziar a lixeira (o programa nao
tem conceito de administrador/usuario comum -- ver decisao no design desta
feature).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from db import lixeira
from ui.dialogs import confirmar_exclusao, mostrar_erro
from ui.field_types import formatar_data_exibicao
from ui.theme import marcar_variante
from ui.window_utils import preparar_janela


def _data_exibida(iso: str) -> str:
    # "AAAA-MM-DDTHH:MM:SS" (ver db/lixeira.py::_agora) -- so a parte da data
    # em formato brasileiro + a hora, sem o "T" tecnico no meio.
    return formatar_data_exibicao(iso[:10]) + iso[10:19].replace("T", " ")


class LixeiraDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, usuario: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario = usuario
        self.setWindowTitle("Lixeira")
        preparar_janela(self, 700, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.abas = QTabWidget()
        self.tabela_registros = self._criar_tabela(["Registro", "Tabela", "Excluído por", "Quando"])
        self.tabela_tabelas = self._criar_tabela(["Tabela", "Registros", "Excluído por", "Quando"])
        self.tabela_campos = self._criar_tabela(["Campo", "Tabela", "Excluído por", "Quando"])
        self.abas.addTab(self._envolver(self.tabela_registros), "Registros")
        self.abas.addTab(self._envolver(self.tabela_tabelas), "Tabelas")
        self.abas.addTab(self._envolver(self.tabela_campos), "Campos")
        layout.addWidget(self.abas, stretch=1)

        botao_fechar = QPushButton("Fechar")
        marcar_variante(botao_fechar, "secundario")
        botao_fechar.clicked.connect(self.accept)
        layout.addWidget(botao_fechar)

        self.carregar_dados()

    def _criar_tabela(self, colunas: list[str]) -> QTableWidget:
        tabela = QTableWidget()
        cabecalhos = colunas + ["Ações"]
        tabela.setColumnCount(len(cabecalhos))
        tabela.setHorizontalHeaderLabels(cabecalhos)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        tabela.verticalHeader().setVisible(False)
        return tabela

    def _envolver(self, tabela: QTableWidget) -> QWidget:
        pagina = QWidget()
        layout_pagina = QVBoxLayout(pagina)
        layout_pagina.setContentsMargins(0, 8, 0, 0)
        layout_pagina.addWidget(tabela)
        return pagina

    def carregar_dados(self) -> None:
        self._popular_registros()
        self._popular_tabelas()
        self._popular_campos()

    # -- registros ------------------------------------------------------------

    def _popular_registros(self) -> None:
        itens = lixeira.listar_registros(self.conn)
        self.tabela_registros.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = [item["rotulo"], item["tabela"], item["excluido_por"] or "", _data_exibida(item["excluido_em"])]
            for coluna, valor in enumerate(valores):
                self.tabela_registros.setItem(linha, coluna, QTableWidgetItem(str(valor)))
            self.tabela_registros.setCellWidget(
                linha, len(valores),
                self._botoes_acao(
                    rotulo=item["rotulo"],
                    ao_restaurar=lambda id_lixeira=item["id_lixeira"]: self._restaurar_registro(id_lixeira),
                    ao_excluir=lambda id_lixeira=item["id_lixeira"]: self._excluir_definitivamente(
                        lixeira.excluir_definitivamente_registro, id_lixeira, self._popular_registros
                    ),
                ),
            )
        self.tabela_registros.resizeColumnsToContents()

    def _restaurar_registro(self, id_lixeira: int) -> None:
        try:
            lixeira.restaurar_registro(self.conn, id_lixeira, usuario=self.usuario)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._popular_registros()

    # -- tabelas ---------------------------------------------------------------

    def _popular_tabelas(self) -> None:
        itens = lixeira.listar_tabelas(self.conn)
        self.tabela_tabelas.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = [
                item["tabela"], str(item["quantidade_registros"]), item["excluido_por"] or "",
                _data_exibida(item["excluido_em"]),
            ]
            for coluna, valor in enumerate(valores):
                self.tabela_tabelas.setItem(linha, coluna, QTableWidgetItem(valor))
            self.tabela_tabelas.setCellWidget(
                linha, len(valores),
                self._botoes_acao(
                    rotulo=f'a tabela "{item["tabela"]}"',
                    ao_restaurar=lambda id_lixeira=item["id_lixeira"]: self._restaurar_tabela(id_lixeira),
                    ao_excluir=lambda id_lixeira=item["id_lixeira"]: self._excluir_definitivamente(
                        lixeira.excluir_definitivamente_tabela, id_lixeira, self._popular_tabelas
                    ),
                ),
            )
        self.tabela_tabelas.resizeColumnsToContents()

    def _restaurar_tabela(self, id_lixeira: int) -> None:
        try:
            lixeira.restaurar_tabela(self.conn, id_lixeira, usuario=self.usuario)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._popular_tabelas()

    # -- campos ------------------------------------------------------------------

    def _popular_campos(self) -> None:
        itens = lixeira.listar_campos(self.conn)
        self.tabela_campos.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = [item["coluna"], item["tabela"], item["excluido_por"] or "", _data_exibida(item["excluido_em"])]
            for coluna, valor in enumerate(valores):
                self.tabela_campos.setItem(linha, coluna, QTableWidgetItem(str(valor)))
            self.tabela_campos.setCellWidget(
                linha, len(valores),
                self._botoes_acao(
                    rotulo=f'o campo "{item["coluna"]}"',
                    ao_restaurar=lambda id_lixeira=item["id_lixeira"]: self._restaurar_campo(id_lixeira),
                    ao_excluir=lambda id_lixeira=item["id_lixeira"]: self._excluir_definitivamente(
                        lixeira.excluir_definitivamente_campo, id_lixeira, self._popular_campos
                    ),
                ),
            )
        self.tabela_campos.resizeColumnsToContents()

    def _restaurar_campo(self, id_lixeira: int) -> None:
        try:
            lixeira.restaurar_campo(self.conn, id_lixeira, usuario=self.usuario)
        except ValueError as erro:
            mostrar_erro(self, str(erro))
            return
        self._popular_campos()

    # -- pecas compartilhadas ----------------------------------------------------

    def _botoes_acao(self, rotulo: str, ao_restaurar, ao_excluir) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        botao_restaurar = QPushButton("Restaurar")
        botao_restaurar.clicked.connect(ao_restaurar)
        layout.addWidget(botao_restaurar)

        botao_excluir = QPushButton("Excluir definitivamente")
        marcar_variante(botao_excluir, "perigo")
        botao_excluir.clicked.connect(lambda: self._confirmar_e_excluir(rotulo, ao_excluir))
        layout.addWidget(botao_excluir)
        return container

    def _confirmar_e_excluir(self, rotulo: str, ao_excluir) -> None:
        # Restaurar sempre foi permitido sem confirmacao extra (e reversivel:
        # da pra excluir nao aparece de novo). Excluir DAQUI e definitivo de
        # verdade -- por isso passa pelo mesmo popup de confirmacao usado em
        # qualquer outra exclusao irreversivel do programa.
        if not confirmar_exclusao(self, rotulo, tipo="item da lixeira (nao da pra desfazer)"):
            return
        ao_excluir()

    def _excluir_definitivamente(self, funcao_excluir, id_lixeira: int, recarregar) -> None:
        funcao_excluir(self.conn, id_lixeira)
        recarregar()
