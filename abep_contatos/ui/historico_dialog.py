"""
Janela simples que mostra o HISTORICO DE ALTERACOES do banco de dados atual
-- quem criou/editou/excluiu o que, e quando. Substitui a antiga aba
"CONFIGURACOES" do sistema em planilha (que guardava esse mesmo tipo de
informacao numa aba escondida).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QDialog, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from db import log
from ui.field_types import formatar_data_exibicao


class HistoricoDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Histórico de alterações")
        self.resize(700, 450)

        layout = QVBoxLayout(self)
        self.tabela = QTableWidget()
        colunas = ["Data/hora", "Usuario", "Tabela", "Acao", "Detalhes"]
        self.tabela.setColumnCount(len(colunas))
        self.tabela.setHorizontalHeaderLabels(colunas)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabela)

        botao_fechar = QPushButton("Fechar")
        botao_fechar.clicked.connect(self.accept)
        layout.addWidget(botao_fechar)

        self._carregar()

    def _carregar(self) -> None:
        registros = log.historico(self.conn)
        self.tabela.setRowCount(len(registros))
        for linha, item in enumerate(registros):
            # A data e guardada em formato tecnico (ISO, com hora em UTC) --
            # aqui mostramos so a parte da data no formato brasileiro; quem
            # quiser o horario exato ainda pode ver o valor tecnico completo
            # passando o mouse em cima (tooltip).
            data_exibida = formatar_data_exibicao(item["data_hora"][:10]) + item["data_hora"][10:19].replace("T", " ")
            valores = [data_exibida, item["usuario"], item["tabela"], item["acao"], item["detalhes"] or ""]
            for coluna, valor in enumerate(valores):
                celula = QTableWidgetItem(str(valor))
                celula.setToolTip(item["data_hora"])
                self.tabela.setItem(linha, coluna, celula)
        self.tabela.resizeColumnsToContents()
