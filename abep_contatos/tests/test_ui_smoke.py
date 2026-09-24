"""
Testes de "fumaca" (smoke tests) da interface grafica: nao clicam de
verdade na tela (isso exigiria uma pessoa ou uma ferramenta de automacao
bem mais pesada), mas constroem cada janela do jeito que o programa
constroi de verdade, contra um banco de dados real -- pra pegar erros de
importacao, nomes errados de widgets etc. antes de um usuario encontrar.

Rodam com QT_QPA_PLATFORM=offscreen (configurado em conftest.py), que faz o
Qt desenhar as janelas "no vazio", sem precisar de um monitor -- essencial
pra rodar em ambientes automatizados como este.
"""
import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox

from db import auth, categorias, connection, importer, records
from db.schema import EMPRESAS, PESSOAS
from ui.dashboard_view import DashboardView
from ui.export_dialog import ExportDialog
from ui.historico_dialog import HistoricoDialog
from ui.launcher_dialog import LauncherDialog
from ui.lista_registros_view import ListaRegistrosView
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.record_form_dialog import RecordFormDialog
from ui.settings_dialog import SettingsDialog
from ui.sheet_manager_dialog import SheetManagerDialog
from versao import VERSAO

_XLSX_REAL = os.path.join(os.path.dirname(__file__), "..", "..", "Presidentes - Mailing.xlsx")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def banco_com_dados(tmp_path, qapp):
    caminho = str(tmp_path / "teste.abepdb")
    conn = connection.criar_novo(caminho)
    if os.path.isfile(_XLSX_REAL):
        importer.importar_xlsx(conn, _XLSX_REAL)
    auth.criar_usuario(conn, "admin", "senha123", "Administrador")
    yield conn
    conn.close()


def test_launcher_dialog_constroi(qapp):
    dialogo = LauncherDialog()
    assert dialogo.windowTitle()


def test_login_dialog_constroi_e_rejeita_senha_errada(banco_com_dados):
    dialogo = LoginDialog(banco_com_dados)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_senha.setText("senha-errada")
    dialogo._tentar_login()
    assert dialogo.usuario_logado is None


def test_login_dialog_aceita_senha_certa(banco_com_dados):
    dialogo = LoginDialog(banco_com_dados)
    dialogo.campo_usuario.setText("admin")
    dialogo.campo_senha.setText("senha123")
    dialogo._tentar_login()
    assert dialogo.usuario_logado is not None
    assert dialogo.usuario_logado.usuario == "admin"


def test_lista_registros_view_carrega_pessoas_importadas(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    total = len(records.get_records(banco_com_dados, PESSOAS))
    assert view.tabela_widget.rowCount() == min(total, view._itens_por_pagina)
    assert str(total) in view.rotulo_pilula.text()


def test_lista_registros_view_empresas(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, EMPRESAS, "admin")
    total = len(records.get_records(banco_com_dados, EMPRESAS))
    assert view.tabela_widget.rowCount() == min(total, view._itens_por_pagina)


def test_lista_registros_view_tabela_sem_registros_nao_quebra(banco_com_dados):
    """USUARIOS pode estar vazia (so o admin de teste existe, mas SENHA_HASH
    e removida e nenhum outro campo obriga preenchimento) -- a tela precisa
    aguentar uma tabela com zero linhas sem lancar excecao."""
    from db.schema import USUARIOS

    view = ListaRegistrosView(banco_com_dados, USUARIOS, "admin")
    assert view.tabela_widget.rowCount() >= 0
    assert "Nenhum registro" in view.rotulo_paginacao.text() or view.tabela_widget.rowCount() > 0


def test_lista_registros_view_filtro_por_empresa_usa_lista_nao_texto(banco_com_dados):
    """Regressao: filtrar PESSOAS por Empresa digitando texto (ex.: a UF
    "CE") comparava contra o NOME INTEIRO da empresa -- "CE" batia tambem
    com qualquer empresa que tivesse essas 2 letras juntas em outro lugar
    do nome (ex.: "Processamento", "Centro..."), trazendo empresas de
    outros estados junto (parecia um filtro quebrado). Agora o campo de
    valor vira uma LISTA das empresas de verdade, e o filtro compara o ID,
    nao um pedaco de texto -- so pode dar exatamente as pessoas daquela
    empresa, nunca de outra."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._adicionar_linha_filtro()
    linha = view._linhas_filtro[0]

    indice = linha.combo_campo.findText("Empresa")
    assert indice >= 0
    linha.combo_campo.setCurrentIndex(indice)
    assert linha.combo_campo.currentData() == "_EMPRESA_BUSCA"

    # Trocar pra "Empresa" troca a caixinha de valor pra uma lista (combo),
    # nao mais um campo de texto livre.
    assert isinstance(linha.widget_valor, QComboBox)
    assert linha.widget_valor.count() > 1  # "(todas)" + pelo menos 1 empresa de verdade

    primeira_pessoa = records.get_records(banco_com_dados, PESSOAS)[0]
    id_empresa = primeira_pessoa["ID_EMPRESA"]
    indice_empresa = linha.widget_valor.findData(id_empresa)
    assert indice_empresa >= 0
    linha.widget_valor.setCurrentIndex(indice_empresa)

    ids_filtrados = {r["ID"] for r in view._registros_filtrados}
    assert primeira_pessoa["ID"] in ids_filtrados
    # TODOS os filtrados sao da MESMA empresa -- nenhuma de outro estado/nome
    # parecido entrou junto (o bug que motivou essa mudanca).
    assert all(r.get("ID_EMPRESA") == id_empresa for r in view._registros_filtrados)


def test_lista_registros_view_varios_filtros_combinam_com_e(banco_com_dados):
    """Pedido do usuario: os filtros tem que permitir combinar MAIS DE UM ao
    mesmo tempo (ex.: Categoria = X E Empresa = Y), nao so um por vez -- cada
    linha de filtro adicionada estreita ainda mais o resultado da anterior."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    todas = records.get_records(banco_com_dados, PESSOAS)
    primeira_pessoa = next(p for p in todas if p.get("CATEGORIAS"))
    id_empresa = primeira_pessoa["ID_EMPRESA"]
    categoria = primeira_pessoa["CATEGORIAS"][0]

    # 1a linha: filtra por Empresa.
    view._adicionar_linha_filtro()
    linha_empresa = view._linhas_filtro[0]
    linha_empresa.combo_campo.setCurrentIndex(linha_empresa.combo_campo.findText("Empresa"))
    linha_empresa.widget_valor.setCurrentIndex(linha_empresa.widget_valor.findData(id_empresa))
    so_empresa = {r["ID"] for r in view._registros_filtrados}
    assert primeira_pessoa["ID"] in so_empresa

    # 2a linha: filtra tambem por Categoria (o combo de categoria agora deixa
    # marcar mais de um valor ao mesmo tempo -- aqui marcamos so um) --
    # resultado so pode ENCOLHER (ou ficar igual), nunca trazer gente de fora
    # do filtro de empresa.
    view._adicionar_linha_filtro()
    linha_categoria = view._linhas_filtro[1]
    linha_categoria.combo_campo.setCurrentIndex(linha_categoria.combo_campo.findText("Categoria"))
    linha_categoria.widget_valor.definir_opcoes(categorias.listar_categorias(banco_com_dados), [categoria])
    view._aplicar_filtro()

    combinado = view._registros_filtrados
    ids_combinado = {r["ID"] for r in combinado}
    assert ids_combinado <= so_empresa
    assert primeira_pessoa["ID"] in ids_combinado
    assert all(
        r.get("ID_EMPRESA") == id_empresa and categoria in (r.get("CATEGORIAS") or [])
        for r in combinado
    )

    # Remover a 1a linha volta a filtrar so por Categoria.
    view._remover_linha_filtro(linha_empresa)
    assert view._linhas_filtro == [linha_categoria]
    assert all(categoria in (r.get("CATEGORIAS") or []) for r in view._registros_filtrados)


def test_lista_registros_view_restaura_filtro_largura_e_itens_por_pagina(banco_com_dados):
    """Preferencias por usuario (ver db/preferencias.py): o filtro montado, a
    largura escolhida pro painel de detalhes e os itens por pagina precisam
    sobreviver a fechar e abrir a tela de novo -- reabrir a MESMA tabela como
    o MESMO usuario deve devolver tudo do jeito que a pessoa deixou."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    primeira_pessoa = records.get_records(banco_com_dados, PESSOAS)[0]
    id_empresa = primeira_pessoa["ID_EMPRESA"]

    view._adicionar_linha_filtro()
    linha = view._linhas_filtro[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Empresa"))
    linha.widget_valor.setCurrentIndex(linha.widget_valor.findData(id_empresa))

    view.combo_itens_pagina.setCurrentIndex(view.combo_itens_pagina.findData(100))
    view.divisor.setSizes([600, 500])
    view._salvar_preferencias()  # splitterMoved so dispara com arraste de mouse de verdade

    view_reaberta = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert len(view_reaberta._linhas_filtro) == 1
    linha_restaurada = view_reaberta._linhas_filtro[0]
    assert linha_restaurada.combo_campo.currentData() == "_EMPRESA_BUSCA"
    assert linha_restaurada.widget_valor.currentData() == id_empresa
    assert view_reaberta._itens_por_pagina == 100
    assert all(r.get("ID_EMPRESA") == id_empresa for r in view_reaberta._registros_filtrados)


def test_lista_registros_view_preferencias_nao_vazam_entre_usuarios(banco_com_dados):
    """Cada pessoa que faz login ve so os PROPRIOS filtros salvos -- Fernando
    e Diego usando o mesmo banco nao podem ver o filtro um do outro."""
    auth.criar_usuario(banco_com_dados, "outra_pessoa", "senha123", "Outra Pessoa")
    pessoa_com_categoria = next(p for p in records.get_records(banco_com_dados, PESSOAS) if p.get("CATEGORIAS"))
    categoria = pessoa_com_categoria["CATEGORIAS"][0]

    view_admin = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view_admin._adicionar_linha_filtro()
    linha = view_admin._linhas_filtro[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Categoria"))
    linha.widget_valor.definir_opcoes(categorias.listar_categorias(banco_com_dados), [categoria])
    view_admin._salvar_preferencias()

    view_outra_pessoa = ListaRegistrosView(banco_com_dados, PESSOAS, "outra_pessoa")
    assert view_outra_pessoa._linhas_filtro == []

    view_admin_de_novo = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert len(view_admin_de_novo._linhas_filtro) == 1


def test_lista_registros_view_titulo_varia_entre_pessoas_diferentes(banco_com_dados):
    """Regressao: o campo "titulo" (ao lado do avatar, usado tambem pra
    ordenar e nomear o registro no painel de detalhes) tinha virado um
    campo de EMPRESA (ex.: "Sigla da Empresa"), porque o layout padrao
    coloca os campos de empresa na 1a linha -- a tabela inteira de
    Contatos mostrava a empresa repetida em vez do nome de cada pessoa."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert view._campo_titulo != "ID_EMPRESA"
    assert not view._campo_titulo.startswith("_EMPRESA")

    titulos = {p.get(view._campo_titulo) for p in view._todos_registros}
    # Nomes de pessoas sao quase todos diferentes; um campo de empresa NAO
    # seria (varias pessoas da mesma empresa repetiriam o mesmo valor).
    assert len(titulos) > 10


def test_lista_registros_view_colunas_extra_consolidam_empresa_numa_so(banco_com_dados):
    """Os 3 campos de empresa (_EMPRESA_SIGLA/_EMPRESA_SIGLA_EMPRESA/
    _EMPRESA_NOME) nunca podem aparecer, cada um, como uma coluna extra --
    isso tomaria as 2 vagas disponiveis so com dados de empresa repetidos,
    sem sobrar espaco pra nenhum dado que fale da PESSOA."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    extras = view._colunas_extra_tabela()
    campos_empresa_brutos = {"_EMPRESA_SIGLA", "_EMPRESA_SIGLA_EMPRESA", "_EMPRESA_NOME", "_EMPRESA_BUSCA"}
    assert not (campos_empresa_brutos & set(extras))
    assert extras.count("_EMPRESA_RESUMO") <= 1


def test_lista_registros_view_paginacao_muda_pagina(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    total = len(records.get_records(banco_com_dados, PESSOAS))
    assert total > view._itens_por_pagina  # a planilha real tem 81 pessoas, mais que 1 pagina de 20

    primeira_pagina = [r["ID"] for r in view._pagina_atual_de_registros()]
    view._mudar_pagina(1)
    segunda_pagina = [r["ID"] for r in view._pagina_atual_de_registros()]
    assert primeira_pagina != segunda_pagina
    assert "Página 2" in view.rotulo_pagina_atual.text()


def test_lista_registros_view_ordena_por_coluna_ao_clicar_cabecalho(conn, qapp):
    auth.criar_usuario(conn, "admin", "senha123", "Administrador")
    for nome in ("Carlos", "Ana", "Bruno"):
        conn.execute('INSERT INTO PESSOAS ("NOME") VALUES (?)', (nome,))
    conn.commit()

    view = ListaRegistrosView(conn, PESSOAS, "admin")
    assert view._campo_ordenacao is None  # estado inicial: ordem padrao pelo campo-titulo

    view._ao_clicar_cabecalho_coluna(1)  # coluna 1 e sempre o campo-titulo
    assert view._campo_ordenacao == view._campo_titulo
    crescente = [r["ID"] for r in view._pagina_atual_de_registros()]

    view._ao_clicar_cabecalho_coluna(1)  # clicar de novo no mesmo cabecalho inverte a direcao
    decrescente = [r["ID"] for r in view._pagina_atual_de_registros()]
    assert decrescente == list(reversed(crescente))

    # clicar num cabecalho sem campo associado (checkbox) nao muda nada
    view._ao_clicar_cabecalho_coluna(0)
    assert [r["ID"] for r in view._pagina_atual_de_registros()] == decrescente


def test_lista_registros_view_selecionar_registro_abre_painel_detalhe(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    primeira_pessoa = view._pagina_atual_de_registros()[0]

    assert view.painel_detalhe.isHidden() or not view._registro_detalhe
    view._mostrar_detalhe(primeira_pessoa)
    assert view._registro_detalhe["ID"] == primeira_pessoa["ID"]
    assert not view.painel_detalhe.isHidden()

    view._fechar_detalhe()
    assert view._registro_detalhe is None
    assert view.painel_detalhe.isHidden()


def test_lista_registros_view_painel_detalhe_acha_email_e_telefone(banco_com_dados):
    """O painel de detalhes acha o campo de e-mail/telefone pelo TIPO do
    campo (nao por um nome fixo tipo "EMAIL") -- generico pra qualquer
    tabela que tenha algum campo desses dois tipos. Mostrado so como
    informacao (rotulo "E-mail: ...") -- sem botao de acao."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    pessoa_com_email = next(p for p in records.get_records(banco_com_dados, PESSOAS) if p.get("EMAIL"))

    view._mostrar_detalhe(pessoa_com_email)
    assert view._email_atual == pessoa_com_email["EMAIL"]


def test_lista_registros_view_bulk_selecao_mostra_botao_excluir(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert view.botao_excluir_selecionados.isHidden()

    primeiro_id = view._pagina_atual_de_registros()[0]["ID"]
    view._alternar_selecao(primeiro_id, True)
    assert not view.botao_excluir_selecionados.isHidden()
    assert "1" in view.botao_excluir_selecionados.text()

    view._alternar_selecao(primeiro_id, False)
    assert view.botao_excluir_selecionados.isHidden()


def test_lista_registros_view_anotacao_salva_e_recarrega(banco_com_dados):
    from db import anotacoes

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    pessoa = view._pagina_atual_de_registros()[0]
    view._mostrar_detalhe(pessoa)

    view.campo_anotacoes.setPlainText("Prefere ser contatado por WhatsApp.")
    view._salvar_anotacao()
    assert anotacoes.obter_anotacao(banco_com_dados, PESSOAS, pessoa["ID"]) == "Prefere ser contatado por WhatsApp."

    # reabrir o mesmo registro carrega a anotacao salva de volta no campo
    view._fechar_detalhe()
    view._mostrar_detalhe(pessoa)
    assert view.campo_anotacoes.toPlainText() == "Prefere ser contatado por WhatsApp."


def test_lista_registros_view_historico_do_registro_aparece_no_painel(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    pessoa = view._pagina_atual_de_registros()[0]

    records.update_record(banco_com_dados, PESSOAS, pessoa["ID"], {"NOME": "Nome Editado Para Teste"})
    view.carregar_dados()
    pessoa_atualizada = records.get_record(banco_com_dados, PESSOAS, pessoa["ID"])
    view._mostrar_detalhe(pessoa_atualizada)

    assert view._layout_historico.count() > 0


def test_record_form_dialog_criar_e_editar(banco_com_dados):
    dialogo_novo = RecordFormDialog(banco_com_dados, EMPRESAS, registro=None)
    assert "SIGLA" in dialogo_novo._widgets

    empresa = records.get_records(banco_com_dados, EMPRESAS)[0]
    dialogo_editar = RecordFormDialog(banco_com_dados, EMPRESAS, registro=empresa)
    assert dialogo_editar._widgets["SIGLA"].text() == (empresa.get("SIGLA") or "")


def test_record_form_dialog_categorias_respeita_ordem_configurada_das_colunas(qapp, conn):
    """Regressao: a linha "Categorias" (selecao multipla) sempre ia parar no
    FIM do formulario, ignorando a posicao que o usuario configurou pra
    coluna CATEGORIA (vestigial, mas ainda usada como "marcador de posicao")
    na tela "Tabelas e campos". Precisa aparecer onde CATEGORIA foi
    configurada -- aqui, logo apos "ID_EMPRESA"."""
    from db import tables

    ordem = tables.get_column_order(conn, PESSOAS)
    nova_ordem = ["ID_EMPRESA", "CATEGORIA"] + [c for c in ordem if c not in ("ID_EMPRESA", "CATEGORIA", "ID")]
    tables.set_column_order(conn, PESSOAS, nova_ordem)

    dialogo = RecordFormDialog(conn, PESSOAS, registro=None)
    assert dialogo._widget_categorias is not None
    # A linha de Categorias deve vir logo depois de ID_EMPRESA no QFormLayout
    # -- percorre as linhas do form contando rotulos ate achar "Categorias".
    from PySide6.QtWidgets import QFormLayout, QScrollArea

    area = dialogo.findChild(QScrollArea)
    form = area.widget().layout()
    assert isinstance(form, QFormLayout)
    rotulos = [form.itemAt(i, QFormLayout.LabelRole).widget().text() for i in range(form.rowCount())]
    assert rotulos.index("Categorias") == 1  # posicao 0 = Empresa, posicao 1 = Categorias


def test_record_form_dialog_categorias_aparece_mesmo_se_coluna_foi_removida(qapp, conn):
    """Rede de seguranca: se a coluna vestigial CATEGORIA for removida da
    tabela (ex.: usuario usou "Remover campo" sem saber que ela sustenta a
    lista de categorias), a selecao multipla ainda precisa aparecer no
    formulario -- so nao respeita mais a posicao configurada."""
    from db import tables

    tables.drop_column(conn, PESSOAS, "CATEGORIA")
    dialogo = RecordFormDialog(conn, PESSOAS, registro=None)
    assert dialogo._widget_categorias is not None


def test_record_form_dialog_preserva_data_invalida_de_dado_antigo(banco_com_dados):
    """Um campo do tipo 'data' cujo valor JA GRAVADO nao e uma data valida
    (dado antigo digitado errado, ex.: um nome de pessoa por engano) nao
    pode virar silenciosamente 'hoje' num QDateEdit -- isso apagaria a
    informacao original sem o usuario perceber. Precisa continuar
    aparecendo como texto simples, com o valor original intacto."""
    from PySide6.QtWidgets import QDateEdit, QLineEdit

    from db import records as records_mod

    pessoa = next(p for p in records_mod.get_records(banco_com_dados, PESSOAS) if p["ID"] == 1)
    records_mod.update_record(banco_com_dados, PESSOAS, pessoa["ID"], {"DATA DE NASCIMENTO": "Cláudia"})

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=records_mod.get_record(banco_com_dados, PESSOAS, pessoa["ID"]))
    widget = dialogo._widgets["DATA DE NASCIMENTO"]
    assert isinstance(widget, QLineEdit)
    assert not isinstance(widget, QDateEdit)
    assert widget.text() == "Cláudia"


def test_record_form_dialog_nao_preenche_data_vazia_com_hoje_ao_salvar(banco_com_dados):
    """Um campo de data que NUNCA foi preenchido mostra 'hoje' no calendario
    so como ponto de partida visual -- mas se a pessoa salvar sem mexer
    nesse campo, o valor gravado tem que continuar vazio, nao virar a data
    de hoje por engano (isso inventaria uma informacao que ninguem digitou)."""
    from db import records as records_mod

    id_empresa = records_mod.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records_mod.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})
    pessoa = records_mod.get_record(banco_com_dados, PESSOAS, id_pessoa)
    assert not pessoa.get("DATA DE NASCIMENTO")

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    dialogo._ao_salvar()
    assert not dialogo.resultado()["DATA DE NASCIMENTO"]


def test_sheet_manager_dialog_constroi(banco_com_dados):
    dialogo = SheetManagerDialog(banco_com_dados, "admin")
    assert dialogo.lista_tabelas.count() > 0


def test_sheet_manager_dialog_mover_campo_troca_ordem_e_persiste(banco_com_dados):
    from db.schema import PESSOAS
    from db.tables import get_column_order

    dialogo = SheetManagerDialog(banco_com_dados, "admin")
    indice_pessoas = dialogo.lista_tabelas.findItems(PESSOAS, Qt.MatchExactly)
    dialogo.lista_tabelas.setCurrentItem(indice_pessoas[0])

    primeiro_campo = dialogo.lista_campos.item(0).data(Qt.UserRole)
    segundo_campo = dialogo.lista_campos.item(1).data(Qt.UserRole)

    dialogo.lista_campos.setCurrentRow(0)
    dialogo._mover_campo(1)

    assert dialogo.lista_campos.item(0).data(Qt.UserRole) == segundo_campo
    assert dialogo.lista_campos.item(1).data(Qt.UserRole) == primeiro_campo
    assert get_column_order(banco_com_dados, PESSOAS)[:2] == [segundo_campo, primeiro_campo]


def test_sheet_manager_dialog_mover_tabela_troca_ordem_e_persiste(banco_com_dados):
    from db.tables import get_table_order

    dialogo = SheetManagerDialog(banco_com_dados, "admin")
    primeira_tabela = dialogo.lista_tabelas.item(0).text()
    segunda_tabela = dialogo.lista_tabelas.item(1).text()

    dialogo.lista_tabelas.setCurrentRow(0)
    dialogo._mover_tabela(1)

    assert dialogo.lista_tabelas.item(0).text() == segunda_tabela
    assert dialogo.lista_tabelas.item(1).text() == primeira_tabela
    assert get_table_order(banco_com_dados)[:2] == [segunda_tabela, primeira_tabela]


def test_export_dialog_constroi(banco_com_dados):
    dialogo = ExportDialog(banco_com_dados, tabela_padrao=PESSOAS)
    assert dialogo.combo_tabela.count() > 0


def test_settings_dialog_constroi(banco_com_dados):
    dialogo = SettingsDialog(banco_com_dados, "admin")
    assert dialogo.campo_nome.text()


def _rotulos_lista(lista_widget) -> list[str]:
    return [lista_widget.item(i).text() for i in range(lista_widget.count())]


def _dados_lista(lista_widget) -> list[str]:
    return [lista_widget.item(i).data(Qt.UserRole) for i in range(lista_widget.count())]


def test_settings_dialog_campo_extra_carrega_sugestao_padrao(banco_com_dados):
    """Sem nenhuma configuracao manual ainda, a lista "Campos escolhidos"
    vem pre-preenchida com a sugestao automatica (os mesmos campos que
    ui/lista_registros_view.py usaria como colunas extras) -- pra PESSOAS
    (que tem ID_EMPRESA), a primeira delas e "Empresa"."""
    dialogo = SettingsDialog(banco_com_dados, "admin")
    dialogo.combo_tabela_resumo.setCurrentText(PESSOAS)

    assert dialogo.lista_campos_disponiveis.count() > 0
    escolhidos = _dados_lista(dialogo.lista_campos_escolhidos)
    assert escolhidos[0] == "_EMPRESA_RESUMO"
    assert dialogo.lista_campos_escolhidos.item(0).text() == "Empresa"


def _esvaziar_escolhidos(dialogo) -> None:
    """Move todo mundo de volta pra "disponiveis", deixando "escolhidos"
    vazia -- pra montar do zero um cenario determinístico no teste."""
    while dialogo.lista_campos_escolhidos.count():
        dialogo.lista_campos_escolhidos.setCurrentRow(0)
        dialogo._remover_campo_escolhido()


def _escolher_campo(dialogo, rotulo: str) -> None:
    item = dialogo.lista_campos_disponiveis.findItems(rotulo, Qt.MatchExactly)[0]
    dialogo.lista_campos_disponiveis.setCurrentItem(item)
    dialogo._adicionar_campo_escolhido()


def test_settings_dialog_salvar_campo_extra_persiste_no_banco(banco_com_dados):
    from db import settings

    dialogo = SettingsDialog(banco_com_dados, "admin")
    dialogo.combo_tabela_resumo.setCurrentText(PESSOAS)

    _esvaziar_escolhidos(dialogo)
    _escolher_campo(dialogo, "Cargo")

    dialogo._salvar()

    layout_salvo = settings.obter_campos_resumo(banco_com_dados, PESSOAS, padrao=[])
    assert layout_salvo == [["CARGO"]]


def test_settings_dialog_salvar_varios_campos_extra_preserva_ordem(banco_com_dados):
    from db import settings

    dialogo = SettingsDialog(banco_com_dados, "admin")
    dialogo.combo_tabela_resumo.setCurrentText(PESSOAS)
    _esvaziar_escolhidos(dialogo)

    _escolher_campo(dialogo, "E-mail")
    _escolher_campo(dialogo, "Cargo")

    dialogo._salvar()

    layout_salvo = settings.obter_campos_resumo(banco_com_dados, PESSOAS, padrao=[])
    assert layout_salvo == [["EMAIL"], ["CARGO"]]


def test_settings_dialog_salvar_campo_extra_nenhum_limpa_configuracao(banco_com_dados):
    from db import settings

    settings.salvar_campos_resumo(banco_com_dados, PESSOAS, [["CARGO"]])

    dialogo = SettingsDialog(banco_com_dados, "admin")
    dialogo.combo_tabela_resumo.setCurrentText(PESSOAS)
    assert _dados_lista(dialogo.lista_campos_escolhidos) == ["CARGO"]

    dialogo.lista_campos_escolhidos.clear()
    dialogo._salvar()

    # [[]] (uma linha vazia) e o valor que representa "nenhum campo extra"
    # sem cair no fallback pra sugestao automatica -- ver comentario em
    # SettingsDialog._salvar().
    assert settings.obter_campos_resumo(banco_com_dados, PESSOAS, padrao=[["X"]]) == [[]]


def test_dashboard_view_constroi_e_mostra_contagens(banco_com_dados):
    from PySide6.QtWidgets import QLabel

    view = DashboardView(banco_com_dados)
    total_pessoas = len(records.get_records(banco_com_dados, PESSOAS))

    # O 1o cartao (contatos cadastrados) mostra o mesmo total da tabela PESSOAS.
    primeiro_cartao = view._linha_cartoes.itemAt(0).widget()
    textos = [lbl.text() for lbl in primeiro_cartao.findChildren(QLabel)]
    assert str(total_pessoas) in textos


def test_dashboard_view_recarregar_atualiza_apos_novo_contato(banco_com_dados):
    from PySide6.QtWidgets import QLabel

    view = DashboardView(banco_com_dados)
    total_antes = len(records.get_records(banco_com_dados, PESSOAS))

    records.create_record(banco_com_dados, PESSOAS, {"NOME": "Recem Criado"})
    view.carregar_dados()

    primeiro_cartao = view._linha_cartoes.itemAt(0).widget()
    textos = [lbl.text() for lbl in primeiro_cartao.findChildren(QLabel)]
    assert str(total_antes + 1) in textos


def test_historico_dialog_mostra_log_da_importacao(banco_com_dados):
    dialogo = HistoricoDialog(banco_com_dados)
    assert dialogo.tabela.rowCount() > 0


def test_main_window_constroi_com_navegacao(banco_com_dados):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")
    assert janela.lista_navegacao.count() >= 3  # Painel + ao menos Contatos + Empresas
    assert janela.paginas.currentWidget() is not None


def test_main_window_abre_no_painel_por_padrao(banco_com_dados):
    """O Painel (dashboard) e a tela inicial da janela principal -- fica
    fixo no topo do menu, antes das tabelas."""
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")
    assert janela.lista_navegacao.item(0).text() == "Painel"
    assert isinstance(janela.paginas.currentWidget(), DashboardView)


def test_main_window_troca_entre_painel_e_tabela_e_volta(banco_com_dados):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")

    janela.lista_navegacao.setCurrentRow(1)  # primeira tabela de dados
    assert isinstance(janela.paginas.currentWidget(), ListaRegistrosView)

    janela.lista_navegacao.setCurrentRow(0)  # de volta pro Painel
    assert isinstance(janela.paginas.currentWidget(), DashboardView)


def test_main_window_sidebar_segue_ordem_manual_das_tabelas(banco_com_dados):
    """A ordem das tabelas no menu lateral segue a ordem manual configurada
    pela tela de "Gerenciar tabelas" (botoes mover pra cima/baixo), nao mais
    a ordem alfabetica do rotulo."""
    from db.tables import set_table_order

    set_table_order(banco_com_dados, ["USUARIOS", "PESSOAS", "EMPRESAS"])

    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")

    nomes_em_ordem = [janela.lista_navegacao.item(i).data(Qt.UserRole) for i in range(1, janela.lista_navegacao.count())]
    assert nomes_em_ordem == ["USUARIOS", PESSOAS, EMPRESAS]


def test_main_window_tem_botao_verificar_atualizacoes(banco_com_dados):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")
    assert janela.botao_verificar_atualizacoes.text() == "Verificar atualizações..."


def test_main_window_verificar_atualizacoes_desabilita_botao_durante_checagem(banco_com_dados, monkeypatch):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")
    # nao dispara a thread de verdade -- so queremos ver o estado do botao
    # mudar assim que o clique acontece, antes de qualquer resposta chegar
    monkeypatch.setattr("ui.main_window.VerificadorAtualizacao.iniciar", lambda self: None)

    janela._verificar_atualizacoes()

    assert not janela.botao_verificar_atualizacoes.isEnabled()
    assert janela.botao_verificar_atualizacoes.text() == "Verificando..."


def test_main_window_verificacao_manual_sem_novidade_avisa_e_restaura_botao(banco_com_dados, monkeypatch):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")
    janela.botao_verificar_atualizacoes.setEnabled(False)
    janela.botao_verificar_atualizacoes.setText("Verificando...")

    avisos = []
    monkeypatch.setattr("ui.main_window.mostrar_info", lambda parent, mensagem: avisos.append(mensagem))

    janela._ao_verificacao_manual_nao_achar()

    assert len(avisos) == 1
    assert VERSAO in avisos[0]
    assert janela.botao_verificar_atualizacoes.isEnabled()
    assert janela.botao_verificar_atualizacoes.text() == "Verificar atualizações..."


def test_main_window_verificacao_manual_com_novidade_pergunta_e_ignora_ao_recusar(banco_com_dados, monkeypatch):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")

    chamadas_pergunta = []
    monkeypatch.setattr(
        "ui.main_window.perguntar_atualizacao",
        lambda parent, atual, nova, notas: chamadas_pergunta.append((atual, nova, notas)) or (False, False),
    )
    chamadas_download = []
    monkeypatch.setattr(
        "ui.main_window.baixar_e_instalar_atualizacao",
        lambda app, url, parent=None: chamadas_download.append(url),
    )

    janela._ao_verificacao_manual_achar({"versao": "99.0.0", "notas": "Notas da release", "url_download": "https://x"})

    assert chamadas_pergunta == [(VERSAO, "99.0.0", "Notas da release")]
    assert chamadas_download == []  # recusou -- nao deve baixar nada
    assert janela.botao_verificar_atualizacoes.isEnabled()


def test_main_window_verificacao_manual_com_novidade_baixa_ao_aceitar(banco_com_dados, monkeypatch):
    usuario = auth.login(banco_com_dados, "admin", "senha123")
    janela = MainWindow(banco_com_dados, usuario, "teste.abepdb")

    monkeypatch.setattr("ui.main_window.perguntar_atualizacao", lambda parent, atual, nova, notas: (True, False))
    chamadas_download = []
    monkeypatch.setattr(
        "ui.main_window.baixar_e_instalar_atualizacao",
        lambda app, url, parent=None: chamadas_download.append(url),
    )

    janela._ao_verificacao_manual_achar({"versao": "99.0.0", "notas": "", "url_download": "https://exemplo/Setup.exe"})

    assert chamadas_download == ["https://exemplo/Setup.exe"]
