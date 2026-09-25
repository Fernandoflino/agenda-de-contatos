"""
Esta e a JANELA PRINCIPAL do programa -- o que aparece depois que o usuario
escolheu/criou um banco de dados e fez login com sucesso.

O layout segue um padrao bem comum em programas atuais: uma barra lateral
fixa (a "sidebar") do lado esquerdo, com o logotipo/nome no topo e a
navegacao entre as telas logo abaixo, e a area de conteudo ocupando o resto
da janela, trocando de tela conforme o usuario clica na sidebar.

A navegacao e montada DINAMICAMENTE a partir das tabelas que existem no
banco (db.tables.list_data_sheets) -- ou seja, se o usuario criar uma tabela
nova pela tela de "Gerenciar tabelas", ela aparece na sidebar sem precisar
mudar nada no codigo. TODAS as tabelas (Contatos, Empresas, Usuarios, ou
qualquer outra) usam a MESMA tela de lista (ui/lista_registros_view.py) --
a tabela PESSOAS so ganha um nome mais amigavel na sidebar ("Contatos").
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from atualizacao import VerificadorAtualizacao
from config import app_config
from db import auth, lock, settings
from db.schema import PESSOAS
from db.tables import get_table_order
from ui.dashboard_view import DashboardView
from ui.dialogs import baixar_e_instalar_atualizacao, mostrar_info, perguntar_atualizacao
from ui.export_dialog import ExportDialog
from ui.lista_registros_view import ListaRegistrosView
from ui.settings_dialog import SettingsDialog
from ui.theme import aplicar_tema, marcar_variante
from versao import VERSAO

_TEXTO_BOTAO_VERIFICAR = "Verificar atualizações..."

# Valor especial guardado no item de navegacao do Painel (dashboard) -- pra
# diferenciar ele das tabelas de verdade, que usam o proprio nome da tabela
# como valor (ver _ao_trocar_pagina() mais abaixo).
_ITEM_PAINEL = "__PAINEL__"


class MainWindow(QMainWindow):
    trocar_banco_solicitado = Signal()

    def __init__(self, conn: sqlite3.Connection, usuario_logado: auth.Usuario, caminho_banco: str, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.usuario_logado = usuario_logado
        self.caminho_banco = caminho_banco
        self._paginas_tabelas: dict[str, ListaRegistrosView] = {}
        self._pagina_dashboard: DashboardView | None = None

        self.resize(1100, 720)
        self._montar_barra_superior()
        self._montar_janela()
        self._atualizar_identidade()
        self._atualizar_navegacao()

        # Mantem a trava cooperativa do banco (db/lock.py) "viva" enquanto
        # esta janela estiver aberta -- sem isso, ela seria considerada
        # abandonada depois de LIMITE_INATIVIDADE e outra maquina poderia
        # assumir o banco sem aviso nenhum.
        self._temporizador_lock = QTimer(self)
        self._temporizador_lock.timeout.connect(lambda: lock.atualizar_atividade(self.caminho_banco))
        self._temporizador_lock.start(60_000)

    # -- montagem ----------------------------------------------------------

    def _montar_barra_superior(self) -> None:
        """Barra fininha no topo da janela, FORA da sidebar -- e onde fica o
        botao de expandir/recolher o menu lateral. Fica fora de proposito:
        assim o botao continua acessivel mesmo com a sidebar escondida."""
        barra = self.addToolBar("Principal")
        barra.setMovable(False)
        barra.setFloatable(False)
        self._acao_alternar_sidebar = barra.addAction("☰  Menu")
        self._acao_alternar_sidebar.triggered.connect(self._alternar_sidebar)

    def _montar_janela(self) -> None:
        central = QWidget()
        layout_geral = QHBoxLayout(central)
        layout_geral.setContentsMargins(0, 0, 0, 0)
        layout_geral.setSpacing(0)

        self.sidebar = self._montar_sidebar()
        layout_geral.addWidget(self.sidebar)

        self.paginas = QStackedWidget()
        layout_geral.addWidget(self.paginas, stretch=1)

        self.setCentralWidget(central)

    def _alternar_sidebar(self) -> None:
        """Mostra/esconde a barra lateral -- util pra ganhar espaco de tela
        pra grade/lista quando a janela nao esta maximizada, ou so por
        preferencia de quem esta usando."""
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _montar_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        self.rotulo_logo = QLabel()
        self.rotulo_logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rotulo_logo)

        self.rotulo_nome_painel = QLabel()
        self.rotulo_nome_painel.setObjectName("TituloPainel")
        self.rotulo_nome_painel.setAlignment(Qt.AlignCenter)
        self.rotulo_nome_painel.setWordWrap(True)
        layout.addWidget(self.rotulo_nome_painel)

        layout.addSpacing(8)

        self.lista_navegacao = QListWidget()
        self.lista_navegacao.setObjectName("ListaNavegacao")
        self.lista_navegacao.currentItemChanged.connect(self._ao_trocar_pagina)
        layout.addWidget(self.lista_navegacao, stretch=1)

        # Acoes utilitarias (nao sao a navegacao principal) -- ficam com o
        # estilo "secundario" (neutro), reservando a cor de destaque so pra
        # onde ela realmente chama atencao (item selecionado, acoes
        # primarias dentro de cada tela).
        layout_utilitarios = QVBoxLayout()
        layout_utilitarios.setContentsMargins(12, 8, 12, 0)
        layout_utilitarios.setSpacing(6)
        for texto, funcao in (
            ("Exportar...", self._abrir_exportar),
            ("Configurações...", self._abrir_configuracoes),
        ):
            botao = QPushButton(texto)
            marcar_variante(botao, "secundario")
            botao.clicked.connect(funcao)
            layout_utilitarios.addWidget(botao)
        layout.addLayout(layout_utilitarios)

        layout.addSpacing(8)

        rodape = QVBoxLayout()
        rodape.setContentsMargins(12, 0, 12, 0)
        rodape.setSpacing(6)
        rotulo_usuario = QLabel(f"Logado como: {self.usuario_logado.nome}")
        rotulo_usuario.setProperty("papel", "subtitulo")
        rotulo_usuario.setObjectName("RodapeSidebar")
        rodape.addWidget(rotulo_usuario)
        botao_trocar = QPushButton("Trocar de banco de dados")
        marcar_variante(botao_trocar, "secundario")
        botao_trocar.clicked.connect(self.trocar_banco_solicitado.emit)
        rodape.addWidget(botao_trocar)

        # Alem da checagem automatica e silenciosa que roda ao abrir o
        # programa (ver main.py), este botao deixa checar na hora, por
        # pedido explicito -- util pra confirmar que realmente nao ha nada
        # novo, sem precisar fechar e abrir o programa de novo.
        self.botao_verificar_atualizacoes = QPushButton(_TEXTO_BOTAO_VERIFICAR)
        marcar_variante(self.botao_verificar_atualizacoes, "secundario")
        self.botao_verificar_atualizacoes.clicked.connect(self._verificar_atualizacoes)
        rodape.addWidget(self.botao_verificar_atualizacoes)

        # Mostra a versao rodando -- se voce editou o codigo e a janela
        # ainda mostra a versao antiga, feche e abra o programa de novo (o
        # Python nao recarrega os arquivos sozinho com o programa aberto).
        rotulo_versao = QLabel(f"Versão {VERSAO}")
        rotulo_versao.setProperty("papel", "subtitulo")
        rodape.addWidget(rotulo_versao)

        layout.addLayout(rodape)

        return sidebar

    # -- identidade visual (nome/logo/cor) ----------------------------------

    def _atualizar_identidade(self) -> None:
        branding = settings.obter_branding(self.conn)
        self.setWindowTitle(f"{branding.nome} — {self.caminho_banco}")
        self.rotulo_nome_painel.setText(branding.nome)
        if branding.logo:
            pixmap = QPixmap()
            pixmap.loadFromData(branding.logo)
            self.rotulo_logo.setPixmap(pixmap.scaledToWidth(120, Qt.SmoothTransformation))
        else:
            self.rotulo_logo.clear()

        aplicar_tema(QApplication.instance(), self.conn)

    # -- navegacao entre tabelas ---------------------------------------------

    def _atualizar_navegacao(self) -> None:
        """Reconstroi a lista de navegacao da sidebar a partir das tabelas
        que existem HOJE no banco -- chamado ao abrir a janela e de novo
        toda vez que o usuario mexe em "Tabelas e campos". O item "Painel"
        fica sempre fixo no topo, antes das tabelas."""
        item_atual = self.lista_navegacao.currentItem()
        nome_atual = item_atual.data(Qt.UserRole) if item_atual else None

        self.lista_navegacao.blockSignals(True)
        self.lista_navegacao.clear()

        item_painel = QListWidgetItem("Painel")
        item_painel.setData(Qt.UserRole, _ITEM_PAINEL)
        self.lista_navegacao.addItem(item_painel)

        # A ordem no menu segue a ordem manual configurada na tela de
        # "Gerenciar tabelas" (botoes "Mover para cima"/"Mover para baixo") --
        # tabelas que ninguem reordenou ainda aparecem no final, em ordem
        # alfabetica do ROTULO exibido (nao do nome real da tabela -- PESSOAS
        # mostra "Contatos" por padrao ate alguem configurar outro rotulo, ver
        # db/settings.py -> obter_rotulo_tabela, e e por ESSE texto que a
        # ordem alfabetica deve seguir, senao a posicao na sidebar nao bate
        # com o texto que a pessoa esta vendo).
        tabelas = get_table_order(
            self.conn, chave_ordenacao=lambda t: settings.obter_rotulo_tabela(self.conn, t).lower()
        )
        for tabela in tabelas:
            item = QListWidgetItem(settings.obter_rotulo_tabela(self.conn, tabela))
            item.setData(Qt.UserRole, tabela)
            self.lista_navegacao.addItem(item)

        self.lista_navegacao.blockSignals(False)

        # tabelas removidas nao devem continuar guardadas em cache
        for tabela in list(self._paginas_tabelas):
            if tabela not in tabelas:
                pagina = self._paginas_tabelas.pop(tabela)
                self.paginas.removeWidget(pagina)
                pagina.deleteLater()

        indice_restaurar = 0  # Painel, se nao houver nada mais especifico pra restaurar
        if nome_atual == _ITEM_PAINEL:
            indice_restaurar = 0
        elif nome_atual and nome_atual in tabelas:
            indice_restaurar = 1 + tabelas.index(nome_atual)
        if self.lista_navegacao.count():
            self.lista_navegacao.setCurrentRow(indice_restaurar)

    def _ao_trocar_pagina(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        tabela = item.data(Qt.UserRole)

        if tabela == _ITEM_PAINEL:
            if self._pagina_dashboard is None:
                self._pagina_dashboard = DashboardView(self.conn, self.usuario_logado.usuario)
                self.paginas.addWidget(self._pagina_dashboard)
            elif self._pagina_dashboard.dados_sujos:
                self._pagina_dashboard.carregar_dados()
            self.paginas.setCurrentWidget(self._pagina_dashboard)
            return
        pagina = self._paginas_tabelas.get(tabela)
        if pagina is None:
            pagina = ListaRegistrosView(
                self.conn,
                tabela,
                self.usuario_logado.usuario,
                ao_alterar_dados=self._marcar_outras_paginas_sujas(tabela),
            )
            self._paginas_tabelas[tabela] = pagina
            self.paginas.addWidget(pagina)
        elif pagina.dados_sujos:
            pagina.carregar_dados()
        self.paginas.setCurrentWidget(pagina)

    def _marcar_outras_paginas_sujas(self, tabela_origem: str) -> Callable[[], None]:
        """Callback passado a cada ListaRegistrosView (ver ao_alterar_dados):
        criar/editar/excluir um registro numa tabela pode afetar o Painel
        (que agrega todas) e outras tabelas em cache (ex.: nome de empresa
        resolvido na tela de Contatos) -- marca todas como sujas, exceto a
        propria origem, que ja se recarrega sozinha. Invalidacao
        deliberadamente grosseira/global: mais simples e sempre segura (nunca
        mostra dado desatualizado), ao custo de recarregar de vez em quando
        uma aba que talvez nao precisasse."""

        def _callback() -> None:
            if self._pagina_dashboard is not None:
                self._pagina_dashboard.marcar_dados_sujos()
            for outra_tabela, outra_pagina in self._paginas_tabelas.items():
                if outra_tabela != tabela_origem:
                    outra_pagina.marcar_dados_sujos()

        return _callback

    # -- janelas auxiliares --------------------------------------------------

    def _abrir_exportar(self) -> None:
        item = self.lista_navegacao.currentItem()
        tabela_selecionada = item.data(Qt.UserRole) if item else None
        # O Painel nao e uma tabela de verdade -- se for a tela atual, usa
        # PESSOAS como sugestao padrao de exportacao, igual quando nenhuma
        # tabela esta selecionada.
        tabela_padrao = tabela_selecionada if tabela_selecionada and tabela_selecionada != _ITEM_PAINEL else PESSOAS
        ExportDialog(self.conn, tabela_padrao=tabela_padrao, parent=self).exec()

    def _abrir_configuracoes(self) -> None:
        dialogo = SettingsDialog(self.conn, self.usuario_logado.usuario, parent=self)
        aceito = dialogo.exec()
        if aceito:
            self._atualizar_identidade()
        # Dentro de Configuracoes da pra mexer em categorias e em tabelas e
        # campos tambem -- entao atualiza a navegacao e a pagina visivel
        # sempre, mesmo se o dialogo tiver sido cancelado (o que foi feito
        # nas telas internas ja ficou gravado no banco de qualquer jeito).
        self._atualizar_navegacao()

        # Configuracoes pode mudar ordem de coluna, campos de resumo,
        # categorias etc. -- coisas que afetam QUALQUER tabela em cache, nao
        # so a que esta visivel agora, entao marca todas como sujas (a
        # visivel recarrega ja, abaixo, e isso zera a flag dela).
        if self._pagina_dashboard is not None:
            self._pagina_dashboard.marcar_dados_sujos()
        for pagina in self._paginas_tabelas.values():
            pagina.marcar_dados_sujos()

        pagina_atual = self.paginas.currentWidget()
        if pagina_atual is not None and hasattr(pagina_atual, "carregar_dados"):
            pagina_atual.carregar_dados()

    # -- verificacao manual de atualizacoes -----------------------------------

    def _verificar_atualizacoes(self) -> None:
        """Chamado ao clicar em "Verificar atualizações..." -- dispara a
        mesma checagem que roda escondida ao abrir o programa (ver
        atualizacao.py), mas por ser um pedido explicito, sempre mostra
        algum resultado pro usuario (achou versao nova, ou confirma que a
        instalada ja e a mais recente), em vez de falhar em silencio."""
        self.botao_verificar_atualizacoes.setEnabled(False)
        self.botao_verificar_atualizacoes.setText("Verificando...")

        # precisa continuar existindo ate a checagem terminar, por isso fica
        # guardado numa referencia da janela (nao descartado ao sair do
        # metodo).
        self._verificador_manual = VerificadorAtualizacao()
        self._verificador_manual.encontrada.connect(self._ao_verificacao_manual_achar)
        self._verificador_manual.nao_encontrada.connect(self._ao_verificacao_manual_nao_achar)
        self._verificador_manual.iniciar()

    def _restaurar_botao_verificar_atualizacoes(self) -> None:
        self.botao_verificar_atualizacoes.setEnabled(True)
        self.botao_verificar_atualizacoes.setText(_TEXTO_BOTAO_VERIFICAR)

    def _ao_verificacao_manual_nao_achar(self) -> None:
        self._restaurar_botao_verificar_atualizacoes()
        mostrar_info(self, f"Você já está com a versão mais recente instalada (Versão {VERSAO}).")

    def _ao_verificacao_manual_achar(self, info: dict) -> None:
        self._restaurar_botao_verificar_atualizacoes()
        # pedido explicito -- pergunta de novo mesmo que essa versao tenha
        # sido marcada como "nao perguntar de novo" na checagem automatica.
        quer_atualizar, ignorar = perguntar_atualizacao(self, VERSAO, info["versao"], info["notas"])
        if quer_atualizar:
            baixar_e_instalar_atualizacao(QApplication.instance(), info["url_download"], parent=self)
        elif ignorar:
            app_config.definir_versao_ignorada(info["versao"])
