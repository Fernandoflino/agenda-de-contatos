"""
Tela de EXPORTACAO: gera um arquivo .xlsx (Excel) ou .csv com os dados de
uma tabela, pra usar fora do programa (mala direta, planilhas de apoio etc.).

Tem duas abas (duas formas de exportar -- ver db/exporter.py pra entender a
logica por tras de cada uma):

- "Simples": escolhe uma tabela, filtra (opcional) e marca quais colunas
  entram -- uma linha por registro. Serve pra quase todo caso de uso.
- "Exportar Mala Direta": so faz sentido pra tabela PESSOAS. Gera uma linha
  por EMPRESA, com um bloco de colunas pra cada cargo escolhido (ex.:
  Presidente, Diretor Tecnico) -- reconstroi o antigo formato de "mala
  direta" onde cada papel da empresa vira uma coluna diferente.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from db import categorias, exporter, records
from db.schema import PESSOAS
from db.tables import list_data_sheets
from ui import imagens
from ui.dialogs import mostrar_erro, mostrar_info
from ui.window_utils import preparar_janela

_CATEGORIA_TODAS = "(todas)"
_CAMPO_FILTRO_NENHUM = "(nenhum)"


def _lista_marcavel(itens: list[str], marcados: set[str] | None = None) -> QListWidget:
    """Cria uma lista onde cada item tem uma caixinha de marcar do lado --
    usada tanto pra escolher colunas quanto pra escolher cargos."""
    lista = QListWidget()
    marcados = marcados or set(itens)
    for texto in itens:
        item = QListWidgetItem(texto)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if texto in marcados else Qt.Unchecked)
        lista.addItem(item)
    return lista


def _itens_marcados(lista: QListWidget) -> list[str]:
    return [lista.item(i).text() for i in range(lista.count()) if lista.item(i).checkState() == Qt.Checked]


class ExportDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, tabela_padrao: str = PESSOAS, parent=None,
                 ids_selecionados: set[int] | None = None):
        super().__init__(parent)
        self.conn = conn
        self.ids_selecionados = ids_selecionados
        self.setWindowTitle("Exportar dados")
        preparar_janela(self, 640, 560)

        self.combo_tabela = QComboBox()
        self.combo_tabela.addItems(list_data_sheets(conn))
        indice_padrao = self.combo_tabela.findText(tabela_padrao)
        if indice_padrao >= 0:
            self.combo_tabela.setCurrentIndex(indice_padrao)
        self.combo_tabela.currentTextChanged.connect(self._recarregar_colunas_simples)
        if ids_selecionados is not None:
            # Os IDs marcados so fazem sentido pra tabela de onde vieram --
            # trocar de tabela aqui invalidaria a selecao, entao a escolha
            # de tabela fica travada nessa (o titulo ja deixa claro o porque).
            self.combo_tabela.setEnabled(False)
            self.setWindowTitle(f"Exportar {len(ids_selecionados)} selecionado(s)")

        self.abas = QTabWidget()
        self.abas.addTab(self._criar_aba_simples(), "Simples")
        self.abas.addTab(self._criar_aba_mesclada(), "Exportar Mala Direta")
        self.abas.addTab(self._criar_aba_emails(), "Copiar e-mails")
        self.abas.currentChanged.connect(self._ao_trocar_aba)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        linha_tabela = QHBoxLayout()
        linha_tabela.setSpacing(8)
        linha_tabela.addWidget(QLabel("Tabela:"))
        linha_tabela.addWidget(self.combo_tabela, stretch=1)
        layout.addLayout(linha_tabela)
        layout.addWidget(self._criar_secao_fotos())
        layout.addWidget(self.abas, stretch=1)

        self.widget_botoes = QWidget()
        botoes = QHBoxLayout(self.widget_botoes)
        botoes.setContentsMargins(0, 0, 0, 0)
        botoes.setSpacing(8)
        botao_xlsx = QPushButton("Exportar XLSX...")
        botao_xlsx.clicked.connect(lambda: self._exportar("xlsx"))
        botao_csv = QPushButton("Exportar CSV...")
        botao_csv.clicked.connect(lambda: self._exportar("csv"))
        botoes.addStretch()
        botoes.addWidget(botao_xlsx)
        botoes.addWidget(botao_csv)
        layout.addWidget(self.widget_botoes)

        self._recarregar_colunas_simples(self.combo_tabela.currentText())

    # -- fotos (so PESSOAS) -----------------------------------------------

    def _criar_secao_fotos(self) -> QWidget:
        self.grupo_fotos = QGroupBox("Fotos")
        layout = QHBoxLayout(self.grupo_fotos)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Categoria:"))
        self.combo_categoria_fotos = QComboBox()
        layout.addWidget(self.combo_categoria_fotos, stretch=1)

        botao_baixar_fotos = QPushButton("Baixar fotos...")
        botao_baixar_fotos.clicked.connect(self._baixar_fotos)
        layout.addWidget(botao_baixar_fotos)

        self.grupo_fotos.setVisible(False)
        return self.grupo_fotos

    def _recarregar_secao_fotos(self, tabela: str) -> None:
        eh_pessoas = tabela == PESSOAS
        self.grupo_fotos.setVisible(eh_pessoas)
        if not eh_pessoas:
            return
        atual = self.combo_categoria_fotos.currentText()
        self.combo_categoria_fotos.blockSignals(True)
        self.combo_categoria_fotos.clear()
        self.combo_categoria_fotos.addItem(_CATEGORIA_TODAS)
        self.combo_categoria_fotos.addItems(categorias.listar_categorias(self.conn))
        indice = self.combo_categoria_fotos.findText(atual)
        self.combo_categoria_fotos.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_categoria_fotos.blockSignals(False)

    def _baixar_fotos(self) -> None:
        categoria = self.combo_categoria_fotos.currentText()
        registros = records.get_records(self.conn, PESSOAS)
        if categoria and categoria != _CATEGORIA_TODAS:
            registros = [r for r in registros if categoria in (r.get("CATEGORIAS") or [])]
        imagens.salvar_fotos_via_dialogo(self, registros)

    # -- aba "Copiar e-mails" (so PESSOAS) ----------------------------------

    def _criar_aba_emails(self) -> QWidget:
        """Escolhe a categoria e mostra, em duas caixas, os e-mails prontos
        pra colar no programa de e-mail: "Para" (campo EMAIL) e "Copia"
        (campos CP1 a CP9)."""
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(8)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Categoria:"))
        self.combo_categoria_emails = QComboBox()
        self.combo_categoria_emails.currentIndexChanged.connect(self._atualizar_emails)
        linha.addWidget(self.combo_categoria_emails, stretch=1)
        layout.addLayout(linha)

        self.caixa_para, self.rotulo_para = self._adicionar_bloco_emails(layout, "Para (EMAIL)")
        self.caixa_copia, self.rotulo_copia = self._adicionar_bloco_emails(layout, "Cópia (CP1 a CP9)")
        return pagina

    def _adicionar_bloco_emails(self, layout: QVBoxLayout, titulo: str) -> tuple[QPlainTextEdit, QLabel]:
        cabecalho = QHBoxLayout()
        rotulo = QLabel(titulo)
        cabecalho.addWidget(rotulo, stretch=1)
        botao = QPushButton("Copiar")
        cabecalho.addWidget(botao)
        layout.addLayout(cabecalho)

        caixa = QPlainTextEdit()
        caixa.setReadOnly(True)
        layout.addWidget(caixa, stretch=1)

        def copiar() -> None:
            QApplication.clipboard().setText(caixa.toPlainText())
            QToolTip.showText(botao.mapToGlobal(botao.rect().bottomLeft()), "Copiado!", botao)

        botao.clicked.connect(copiar)
        return caixa, rotulo

    def _recarregar_secao_emails(self, tabela: str) -> None:
        """A aba so existe pra PESSOAS (e-mails ficam nessa tabela)."""
        eh_pessoas = tabela == PESSOAS
        indice_aba = self.abas.count() - 1
        self.abas.setTabVisible(indice_aba, eh_pessoas)
        if not eh_pessoas:
            return
        atual = self.combo_categoria_emails.currentText()
        self.combo_categoria_emails.blockSignals(True)
        self.combo_categoria_emails.clear()
        self.combo_categoria_emails.addItem(_CATEGORIA_TODAS)
        self.combo_categoria_emails.addItems(categorias.listar_categorias(self.conn))
        indice = self.combo_categoria_emails.findText(atual)
        self.combo_categoria_emails.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_categoria_emails.blockSignals(False)
        self._atualizar_emails()

    def _atualizar_emails(self) -> None:
        categoria = self.combo_categoria_emails.currentText()
        registros = records.get_records(self.conn, PESSOAS)
        if categoria and categoria != _CATEGORIA_TODAS:
            registros = [r for r in registros if categoria in (r.get("CATEGORIAS") or [])]
        para, copia = exporter.montar_listas_email(registros)
        self.caixa_para.setPlainText("; ".join(para))
        self.caixa_copia.setPlainText("; ".join(copia))
        self.rotulo_para.setText(f"Para (EMAIL) — {len(para)} e-mail(s)")
        self.rotulo_copia.setText(f"Cópia (CP1 a CP9) — {len(copia)} e-mail(s)")

    def _ao_trocar_aba(self, indice: int) -> None:
        # Nessa aba nao ha arquivo pra exportar: esconde os botoes de baixo.
        self.widget_botoes.setVisible(indice != self.abas.count() - 1)

    # -- aba "Simples" -------------------------------------------------

    def _criar_aba_simples(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)

        linha_filtro = QHBoxLayout()
        self.campo_filtro_campo = QComboBox()
        self.campo_filtro_campo.currentTextChanged.connect(self._recarregar_valores_filtro)
        self.campo_filtro_valor = QComboBox()
        self.campo_filtro_valor.setEditable(True)
        self.campo_filtro_valor.setInsertPolicy(QComboBox.NoInsert)
        self.campo_filtro_valor.lineEdit().setPlaceholderText("valor a filtrar (opcional)")
        linha_filtro.addWidget(QLabel("Filtro:"))
        linha_filtro.addWidget(self.campo_filtro_campo)
        linha_filtro.addWidget(self.campo_filtro_valor)
        layout.addLayout(linha_filtro)

        layout.addWidget(QLabel("Colunas a exportar:"))
        self.lista_colunas_simples = QListWidget()
        layout.addWidget(self.lista_colunas_simples)
        return pagina

    def _recarregar_colunas_simples(self, tabela: str) -> None:
        if not tabela:
            return
        self._recarregar_secao_fotos(tabela)
        self._recarregar_secao_emails(tabela)
        colunas, _ = exporter.colunas_exportaveis(self.conn, tabela)
        self.lista_colunas_simples.clear()
        for texto in colunas:
            item = QListWidgetItem(texto)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.lista_colunas_simples.addItem(item)

        atual = self.campo_filtro_campo.currentText()
        self.campo_filtro_campo.blockSignals(True)
        self.campo_filtro_campo.clear()
        self.campo_filtro_campo.addItem(_CAMPO_FILTRO_NENHUM)
        self.campo_filtro_campo.addItems(colunas)
        indice = self.campo_filtro_campo.findText(atual)
        self.campo_filtro_campo.setCurrentIndex(indice if indice >= 0 else 0)
        self.campo_filtro_campo.blockSignals(False)
        self._recarregar_valores_filtro(self.campo_filtro_campo.currentText())

        self._recarregar_cargos_disponiveis()

    def _recarregar_valores_filtro(self, campo: str) -> None:
        """Preenche a caixa "valor a filtrar" com os valores ja existentes
        pro campo escolhido acima -- so pra sugerir, o campo continua
        editavel pra permitir filtrar por um texto parcial."""
        atual = self.campo_filtro_valor.currentText()
        self.campo_filtro_valor.blockSignals(True)
        self.campo_filtro_valor.clear()
        tabela = self.combo_tabela.currentText()
        if campo and campo != _CAMPO_FILTRO_NENHUM and tabela:
            registros = records.get_records(self.conn, tabela)
            valores = sorted({str(r[campo]) for r in registros if r.get(campo)}, key=str.lower)
            self.campo_filtro_valor.addItems(valores)
        self.campo_filtro_valor.setCurrentText(atual)
        self.campo_filtro_valor.blockSignals(False)

    # -- aba "Exportar Mala Direta" -------------------------------------

    def _criar_aba_mesclada(self) -> QWidget:
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setSpacing(10)
        layout.addWidget(QLabel(
            "Gera uma linha por empresa, com um bloco de colunas para cada\n"
            "valor marcado abaixo (na ordem em que aparecem na lista)."
        ))

        linha_agrupador = QHBoxLayout()
        linha_agrupador.setSpacing(8)
        linha_agrupador.addWidget(QLabel("Agrupar por:"))
        self.combo_agrupador = QComboBox()
        self.combo_agrupador.currentTextChanged.connect(self._recarregar_valores_agrupador)
        linha_agrupador.addWidget(self.combo_agrupador)
        linha_agrupador.addStretch()
        layout.addLayout(linha_agrupador)

        self.lista_cargos = QListWidget()
        self.lista_cargos.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.lista_cargos)

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(8)
        botao_subir = QPushButton("Subir")
        botao_subir.clicked.connect(lambda: self._mover_cargo(-1))
        botao_descer = QPushButton("Descer")
        botao_descer.clicked.connect(lambda: self._mover_cargo(1))
        linha_botoes.addWidget(botao_subir)
        linha_botoes.addWidget(botao_descer)
        linha_botoes.addStretch()
        layout.addLayout(linha_botoes)
        return pagina

    def _recarregar_combo_agrupador(self) -> None:
        """Preenche o "Agrupar por" com os campos existentes em PESSOAS,
        preferindo CATEGORIA (mais confiavel, valores fixos) como padrao."""
        self.combo_agrupador.blockSignals(True)
        self.combo_agrupador.clear()
        if self.combo_tabela.currentText() == PESSOAS:
            colunas, _ = exporter.colunas_exportaveis(self.conn, PESSOAS)
            self.combo_agrupador.addItems([c for c in colunas if c != "ID"])
            indice = self.combo_agrupador.findText("CATEGORIA")
            self.combo_agrupador.setCurrentIndex(indice if indice >= 0 else 0)
        self.combo_agrupador.blockSignals(False)

    def _recarregar_cargos_disponiveis(self) -> None:
        self._recarregar_combo_agrupador()
        self._recarregar_valores_agrupador(self.combo_agrupador.currentText())

    def _recarregar_valores_agrupador(self, campo: str) -> None:
        self.lista_cargos.clear()
        if self.combo_tabela.currentText() != PESSOAS or not campo:
            return
        if campo == "CATEGORIA":
            # CATEGORIA agora pode ter varios valores por pessoa (campo
            # CATEGORIAS, uma lista) -- usar a lista mestre de categorias
            # (nomes individuais, na ordem configurada) em vez de derivar
            # dos registros, que traria o texto ja "A, B" juntado como se
            # fosse um encaixe so.
            valores = categorias.listar_categorias(self.conn)
        else:
            pessoas = records.get_records(self.conn, PESSOAS)
            valores = sorted({str(p.get(campo)) for p in pessoas if p.get(campo)})
        for valor in valores:
            item = QListWidgetItem(valor)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.lista_cargos.addItem(item)

    def _mover_cargo(self, direcao: int) -> None:
        linha = self.lista_cargos.currentRow()
        nova_linha = linha + direcao
        if linha < 0 or not (0 <= nova_linha < self.lista_cargos.count()):
            return
        item = self.lista_cargos.takeItem(linha)
        self.lista_cargos.insertItem(nova_linha, item)
        self.lista_cargos.setCurrentRow(nova_linha)

    # -- exportar --------------------------------------------------------

    def _exportar(self, formato: str) -> None:
        tabela = self.combo_tabela.currentText()
        if self.abas.currentIndex() == 0:
            colunas = _itens_marcados(self.lista_colunas_simples)
            campo_filtro = self.campo_filtro_campo.currentText()
            colunas_disponiveis, linhas = exporter.montar_exportacao_simples(
                self.conn, tabela,
                campos_selecionados=colunas or None,
                filtro_campo=campo_filtro if campo_filtro and campo_filtro != _CAMPO_FILTRO_NENHUM else None,
                filtro_valor=self.campo_filtro_valor.currentText().strip(),
                ids_permitidos=self.ids_selecionados,
            )
        else:
            cargos = _itens_marcados(self.lista_cargos)
            if not cargos:
                mostrar_erro(self, "Marque ao menos um cargo para o modo mesclado.")
                return
            colunas_disponiveis, linhas = exporter.montar_exportacao_mesclada(
                self.conn, tabela, cargos, ids_permitidos=self.ids_selecionados
            )

        if not linhas:
            mostrar_erro(self, "Nenhum registro encontrado com esses filtros.")
            return

        filtro_arquivo = "Planilha Excel (*.xlsx)" if formato == "xlsx" else "Arquivo CSV (*.csv)"
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar exportacao como", f"exportacao.{formato}", filtro_arquivo)
        if not caminho:
            return

        try:
            if formato == "xlsx":
                exporter.exportar_xlsx(colunas_disponiveis, linhas, caminho)
            else:
                exporter.exportar_csv(colunas_disponiveis, linhas, caminho)
        except (ValueError, OSError) as erro:
            mostrar_erro(self, str(erro))
            return

        mostrar_info(self, f"{len(linhas)} registro(s) exportado(s) para:\n{caminho}")
