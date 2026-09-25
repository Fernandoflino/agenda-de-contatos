"""
Esta e a janela de FORMULARIO usada tanto pra CRIAR um registro novo quanto
pra EDITAR um ja existente -- em qualquer tabela do programa (PESSOAS,
EMPRESAS, ou uma tabela que o usuario tenha criado). Ela e "dinamica": em vez
de ter um formulario fixo escrito no codigo pra cada tabela, ela MONTA os
campos na hora, olhando quais colunas aquela tabela tem.

Pra cada campo, o formulario decide que tipo de "caixinha" mostrar
consultando ui/field_types.py (campo de data vira um calendario, CPF ganha
mascara automatica, SEXO vira uma lista de opcoes, e assim por diante). Isso
e o que da a sensacao de um formulario "inteligente" sem precisar programar
um formulario especifico pra cada tabela.

Esta janela SO monta e devolve os dados digitados (em resultado()) -- ela nao
grava nada no banco sozinha. Quem chama esta janela (ui/lista_registros_view.py)
e quem decide se chama records.create_record() ou records.update_record() com
o resultado.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from db import categorias
from db.identifiers import quote_ident
from db.records import resolver_empresas
from db.schema import PESSOAS, USUARIOS
from db.tables import get_column_order
from ui import field_types
from ui.theme import marcar_variante
from ui.widgets import CampoSenha, SelecaoMultiplaLista
from ui.window_utils import preparar_janela


def _limitar_largura_combo(combo: QComboBox) -> None:
    """Por padrao, uma QComboBox tenta ficar larga o suficiente pra mostrar
    o item MAIS COMPRIDO da lista sem cortar nada -- com nomes de empresa
    longos (ex.: "AGENCIA DE TECNOLOGIA DA INFORMACAO DO TOCANTINS"), isso
    forcava o formulario inteiro a ficar mais largo que a janela, exigindo
    rolar pro lado pra ver os outros campos (feio e confuso).

    Aqui limitamos a largura do campo FECHADO a um tamanho razoavel (o texto
    comprido ainda aparece completo quando a lista esta ABERTA, via
    setMinimumWidth no "view" -- so o campo fechado nao cresce sem limite).
    """
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(24)
    combo.view().setMinimumWidth(420)


class RecordFormDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, tabela: str, registro: dict | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.tabela = tabela
        self.registro = registro or {}
        self._widgets: dict[str, QWidget] = {}
        self._dados: dict | None = None
        self._widget_categorias: SelecaoMultiplaLista | None = None
        self._categorias_selecionadas: list[str] | None = None

        self.setWindowTitle(f'{"Editar" if registro else "Novo"} registro -- {tabela}')
        preparar_janela(self, 520, 620)
        self._montar_formulario()

    # -- construcao da tela ------------------------------------------------

    def _montar_formulario(self) -> None:
        colunas = [c for c in get_column_order(self.conn, self.tabela) if c != "ID"]
        # A senha ja convertida em hash nunca deve aparecer num formulario --
        # ela e tratada como um campo especial "SENHA" mais abaixo.
        if self.tabela == USUARIOS:
            colunas = [c for c in colunas if c != "SENHA_HASH"]
        # Uma lista de campos pode ser mais alta do que a tela -- por isso o
        # formulario fica dentro de uma area com barra de rolagem.
        area_rolavel = QScrollArea(self)
        area_rolavel.setWidgetResizable(True)
        conteudo = QWidget()
        form = QFormLayout(conteudo)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        for coluna in colunas:
            # CATEGORIA de PESSOAS nao e mais um campo de coluna comum -- e
            # uma relacao N:N (uma pessoa pode ter varias categorias), mas
            # continua ocupando o LUGAR que o usuario configurou pra ela em
            # "Tabelas e campos" (get_column_order), em vez de sempre cair
            # no fim do formulario.
            if coluna == "CATEGORIA" and self.tabela == PESSOAS:
                opcoes_categoria = categorias.listar_categorias(self.conn)
                marcadas = self.registro.get("CATEGORIAS") or []
                self._widget_categorias = SelecaoMultiplaLista(opcoes_categoria, marcadas)
                rotulo_categorias = QLabel("Categorias")
                rotulo_categorias.setBuddy(self._widget_categorias)
                form.addRow(rotulo_categorias, self._widget_categorias)
                continue

            valor_atual = self.registro.get(coluna)
            widget = self._criar_widget_campo(coluna, valor_atual)
            rotulo = QLabel(field_types.rotulo_amigavel(coluna))
            rotulo.setBuddy(widget)  # liga o rotulo ao campo, pra leitores de tela anunciarem o nome certo
            form.addRow(rotulo, widget)
            self._widgets[coluna] = widget

        # Rede de seguranca: se por algum motivo a coluna vestigial CATEGORIA
        # nao apareceu em `colunas` (ex.: alguem removeu esse campo pela tela
        # "Tabelas e campos", sem saber que ele sustenta a lista de
        # categorias), garante que a selecao multipla ainda apareca, mesmo
        # que va parar no fim do formulario em vez do lugar configurado.
        if self.tabela == PESSOAS and self._widget_categorias is None:
            opcoes_categoria = categorias.listar_categorias(self.conn)
            marcadas = self.registro.get("CATEGORIAS") or []
            self._widget_categorias = SelecaoMultiplaLista(opcoes_categoria, marcadas)
            rotulo_categorias = QLabel("Categorias")
            rotulo_categorias.setBuddy(self._widget_categorias)
            form.addRow(rotulo_categorias, self._widget_categorias)

        if self.tabela == USUARIOS:
            campo_senha = CampoSenha()
            texto_rotulo = "Nova senha (deixe em branco p/ manter a atual)" if self.registro else "Senha"
            rotulo_senha = QLabel(texto_rotulo)
            rotulo_senha.setBuddy(campo_senha)
            form.addRow(rotulo_senha, campo_senha)
            self._widgets["SENHA"] = campo_senha

        area_rolavel.setWidget(conteudo)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        marcar_variante(botoes.button(QDialogButtonBox.Cancel), "secundario")
        botoes.accepted.connect(self._ao_salvar)
        botoes.rejected.connect(self.reject)

        layout_geral = QVBoxLayout(self)
        layout_geral.setContentsMargins(16, 16, 16, 16)
        layout_geral.setSpacing(12)
        layout_geral.addWidget(area_rolavel)
        layout_geral.addWidget(botoes)

    def _criar_widget_campo(self, coluna: str, valor_atual) -> QWidget:
        """Escolhe o tipo de campo (data, selecao, texto com mascara...) e
        ja devolve o "widget" (a caixinha da tela) pronto, com o valor atual
        preenchido quando estamos editando um registro existente."""

        # ID_EMPRESA e um caso especial em QUALQUER tabela: em vez de digitar
        # um numero, o usuario escolhe a empresa pelo nome numa lista.
        if coluna == "ID_EMPRESA":
            combo = QComboBox()
            _limitar_largura_combo(combo)
            combo.addItem("(nenhuma)", None)
            empresas = sorted(resolver_empresas(self.conn).items(), key=lambda item: str(item[1]["sigla"]))
            for id_empresa, info in empresas:
                # Mostra UF, sigla da empresa e nome completo juntos -- os
                # dois primeiros sao identificadores curtos DIFERENTES entre
                # si (UF do estado vs. sigla da propria empresa, tipo
                # "PRODERJ"), entao os dois ajudam a achar a empresa certa.
                partes = [info["sigla"], info.get("sigla_empresa"), info["empresa"]]
                combo.addItem(" - ".join(p for p in partes if p), id_empresa)
            if valor_atual is not None:
                indice = combo.findData(valor_atual)
                if indice >= 0:
                    combo.setCurrentIndex(indice)
            return combo

        tipo, opcoes = field_types.tipo_do_campo(self.conn, self.tabela, coluna)

        if tipo == field_types.SELECAO:
            combo = QComboBox()
            _limitar_largura_combo(combo)
            combo.addItems(opcoes or [])
            if valor_atual:
                indice = combo.findText(str(valor_atual), Qt.MatchFixedString)
                if indice < 0:
                    # O valor ja guardado nao bate com nenhuma das opcoes
                    # cadastradas (ex.: abreviacao como "M"/"F" em vez de
                    # "Masculino"/"Feminino", ou um valor antigo/diferente).
                    # Em vez de deixar o combo cair silenciosamente no
                    # primeiro item da lista -- o que mostraria um valor
                    # ERRADO na tela e poderia sobrescrever o dado real ao
                    # salvar sem ninguem perceber -- adiciona o valor bruto
                    # como item extra e seleciona ele, preservando o dado ate
                    # alguem corrigir na mao escolhendo a opcao certa.
                    combo.addItem(str(valor_atual))
                    indice = combo.count() - 1
                combo.setCurrentIndex(indice)
            return combo

        if tipo == field_types.DATA:
            data_qt = QDate.fromString(str(valor_atual), "yyyy-MM-dd") if valor_atual else QDate()
            if valor_atual and not data_qt.isValid():
                # O valor ja guardado nesse campo NAO e uma data valida --
                # acontece com dados antigos digitados errado (ex.: um nome
                # de pessoa por engano no campo de data de nascimento).
                # Em vez de trocar isso silenciosamente por "hoje" no
                # calendario (o que apagaria essa informacao sem avisar
                # ninguem), mostramos como texto simples, preservando
                # exatamente o que ja estava la ate alguem corrigir na mao.
                campo_texto_invalido = QLineEdit(str(valor_atual))
                campo_texto_invalido.setPlaceholderText("dd/mm/aaaa")
                campo_texto_invalido.setToolTip(
                    'Este campo e do tipo "data", mas o valor guardado nao esta '
                    "num formato de data valido -- corrija manualmente se necessario."
                )
                return campo_texto_invalido

            campo_data = QDateEdit()
            campo_data.setCalendarPopup(True)
            campo_data.setDisplayFormat("dd/MM/yyyy")
            if data_qt.isValid():
                campo_data.setDate(data_qt)
            else:
                # Campo de data VAZIO (nunca preenchido): mostra a data de
                # hoje so como ponto de partida no calendario, mas marca o
                # campo como "ainda vazio" -- se a pessoa nao mexer nele, o
                # valor salvo continua em branco, em vez de gravar "hoje"
                # sem ninguem ter escolhido essa data de verdade.
                campo_data.setDate(QDate.currentDate())
                campo_data.setProperty("comecou_vazio", True)
                campo_data.dateChanged.connect(
                    lambda _novo, w=campo_data: w.setProperty("comecou_vazio", False)
                )
            return campo_data

        campo_texto = QLineEdit(str(valor_atual) if valor_atual not in (None, "") else "")

        if tipo == field_types.CPF:
            campo_texto.setPlaceholderText("000.000.000-00")
            campo_texto.textEdited.connect(lambda texto, w=campo_texto: w.setText(field_types.mask_cpf(texto)))
        elif tipo == field_types.TEL:
            campo_texto.setPlaceholderText("(00) 00000-0000")
            campo_texto.textEdited.connect(lambda texto, w=campo_texto: w.setText(field_types.mask_telefone(texto)))
        elif coluna.upper() == "CARGO":
            # CARGO e texto livre (decisao do usuario), mas sugerimos os
            # valores ja usados antes, pra facilitar digitar de novo o mesmo
            # cargo sem risco de escrever diferente por engano.
            sugestoes = self._valores_existentes("CARGO")
            if sugestoes:
                completador = QCompleter(sugestoes, campo_texto)
                completador.setCaseSensitivity(Qt.CaseInsensitive)
                campo_texto.setCompleter(completador)

        return campo_texto

    def _valores_existentes(self, coluna: str) -> list[str]:
        try:
            cur = self.conn.execute(
                f'SELECT DISTINCT {quote_ident(coluna)} FROM {quote_ident(self.tabela)} '
                f'WHERE {quote_ident(coluna)} IS NOT NULL AND {quote_ident(coluna)} != \'\''
            )
            return sorted({str(r[0]) for r in cur.fetchall()})
        except sqlite3.Error:
            return []

    # -- leitura do que foi preenchido --------------------------------------

    def _valor_do_widget(self, coluna: str, widget: QWidget):
        if isinstance(widget, QComboBox):
            usa_dado_interno = coluna == "ID_EMPRESA"
            return widget.currentData() if usa_dado_interno else widget.currentText()
        if isinstance(widget, QDateEdit):
            if widget.property("comecou_vazio"):
                return None  # ninguem escolheu uma data de verdade -- mantem em branco
            return widget.date().toString("yyyy-MM-dd")
        if isinstance(widget, (QLineEdit, CampoSenha)):
            return widget.text().strip()
        return None

    def _ao_salvar(self) -> None:
        dados = {}
        for coluna, widget in self._widgets.items():
            valor = self._valor_do_widget(coluna, widget)
            if coluna == "SENHA" and not valor:
                continue  # senha em branco ao editar = "nao mudar a senha"
            dados[coluna] = valor
        self._dados = dados
        if self._widget_categorias is not None:
            self._categorias_selecionadas = self._widget_categorias.selecionados()
        self.accept()

    def resultado(self) -> dict | None:
        """Devolve o dicionario {campo: valor} preenchido, depois que o
        dialogo foi aceito (Salvar). None se o usuario cancelou."""
        return self._dados

    def resultado_categorias(self) -> list[str] | None:
        """Categorias marcadas na tela (so existe pra PESSOAS) -- None se a
        tabela nao tiver esse campo ou se o dialogo foi cancelado."""
        return self._categorias_selecionadas
