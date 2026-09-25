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

from db import anotacoes, auth, categorias, connection, dashboard, importer, lixeira, records
from db.schema import EMPRESAS, PESSOAS
from ui.dashboard_view import DashboardView
from ui.export_dialog import ExportDialog
from ui.historico_dialog import HistoricoDialog
from ui.launcher_dialog import LauncherDialog
from ui.lista_registros_view import ListaRegistrosView
from ui.lixeira_dialog import LixeiraDialog
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.record_form_dialog import RecordFormDialog
from ui.settings_dialog import SettingsDialog
from ui.sheet_manager_dialog import SheetManagerDialog
from versao import VERSAO

_XLSX_REAL = os.path.join(os.path.dirname(__file__), "..", "..", "Presidentes - Mailing.xlsx")


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


def test_lista_registros_view_filtro_categoria_marca_mais_de_uma(banco_com_dados):
    """Pedido do usuario: o filtro de Categoria precisa aceitar marcar mais
    de uma categoria ao mesmo tempo -- um contato aparece se tiver QUALQUER
    UMA das marcadas (uniao, nao intersecao)."""
    from ui.widgets import FiltroMultiplaEscolha

    categorias.adicionar_categoria(banco_com_dados, "Presidentes")
    categorias.adicionar_categoria(banco_com_dados, "Diretores Técnicos")
    categorias.adicionar_categoria(banco_com_dados, "Diretores Financeiros")

    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_presidente = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Presidente"})
    id_diretor = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Diretor"})
    id_financeiro = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Financeiro"})
    categorias.definir_categorias_da_pessoa(banco_com_dados, id_presidente, ["Presidentes"])
    categorias.definir_categorias_da_pessoa(banco_com_dados, id_diretor, ["Diretores Técnicos"])
    categorias.definir_categorias_da_pessoa(banco_com_dados, id_financeiro, ["Diretores Financeiros"])

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._adicionar_linha_filtro()
    linha = view._linhas_filtro[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Categoria"))
    assert isinstance(linha.widget_valor, FiltroMultiplaEscolha)

    linha.widget_valor.marcar(["Presidentes", "Diretores Técnicos"])
    ids_filtrados = {r["ID"] for r in view._registros_filtrados}
    assert ids_filtrados == {id_presidente, id_diretor}
    assert linha.widget_valor.text() == "Categoria (2)"


def test_lista_registros_view_filtro_categoria_salva_e_restaura_varios_valores(banco_com_dados):
    """O filtro de Categoria com varias marcadas precisa sobreviver a
    fechar/abrir a tela de novo, igual qualquer outro filtro salvo."""
    categorias.adicionar_categoria(banco_com_dados, "Presidentes")
    categorias.adicionar_categoria(banco_com_dados, "Diretores Técnicos")

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._adicionar_linha_filtro()
    linha = view._linhas_filtro[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Categoria"))
    linha.widget_valor.marcar(["Presidentes", "Diretores Técnicos"])
    view._salvar_preferencias()

    view_reaberta = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert len(view_reaberta._linhas_filtro) == 1
    linha_restaurada = view_reaberta._linhas_filtro[0]
    assert set(linha_restaurada.widget_valor.selecionados()) == {"Presidentes", "Diretores Técnicos"}


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

    # 2a linha: filtra tambem por Categoria -- resultado so pode ENCOLHER (ou
    # ficar igual), nunca trazer gente de fora do filtro de empresa.
    view._adicionar_linha_filtro()
    linha_categoria = view._linhas_filtro[1]
    linha_categoria.combo_campo.setCurrentIndex(linha_categoria.combo_campo.findText("Categoria"))
    linha_categoria.widget_valor.marcar([categoria])

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
    linha.widget_valor.marcar([categoria])

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


def test_lista_registros_view_aba_informacoes_nao_mostra_foto_como_texto(banco_com_dados):
    """FOTO/FOTO_MIME sao BLOB -- ja aparecem como o avatar grande do
    cabecalho do painel de detalhes, nao podem virar mais uma linha de
    texto (bytes crus) na aba "Informacoes"."""
    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Com Foto", "FOTO": foto})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    pessoa = records.get_record(banco_com_dados, PESSOAS, id_pessoa)
    view._mostrar_detalhe(pessoa)

    rotulos = [
        view._layout_informacoes.itemAt(0).layout().itemAtPosition(i, 0).widget().text()
        for i in range(view._layout_informacoes.itemAt(0).layout().rowCount())
        if view._layout_informacoes.itemAt(0).layout().itemAtPosition(i, 0) is not None
    ]
    assert "Foto" not in rotulos
    assert "Foto Mime" not in rotulos


def test_lista_registros_view_filtro_de_campo_nao_oferece_foto(banco_com_dados):
    from db.tables import get_column_order

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    colunas = [c for c in get_column_order(banco_com_dados, PESSOAS) if c != "ID"]
    rotulos_e_campos = view._opcoes_de_campo(colunas)
    campos = {campo for _, campo in rotulos_e_campos}
    assert "FOTO" not in campos
    assert "FOTO_MIME" not in campos


def test_lista_registros_view_botao_copiar_copia_valor_para_area_de_transferencia(banco_com_dados):
    """O botao de copiar ao lado de um valor no painel de detalhes precisa
    copiar exatamente esse texto (ja formatado, igual aparece na tela) pra
    area de transferencia."""
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    botao = view._botao_copiar("fulano@teste.com")
    botao.click()
    assert QApplication.clipboard().text() == "fulano@teste.com"


def test_lista_registros_view_icone_anotacao_aparece_quando_tem_anotacao(banco_com_dados):
    """O icone de nota ao lado do nome so aparece pra quem TEM anotacao
    salva -- consulta em lote (ids_com_anotacao), nao uma por linha."""
    from PySide6.QtWidgets import QLabel

    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_com_nota = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Com Nota"})
    id_sem_nota = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Sem Nota"})
    anotacoes.salvar_anotacao(banco_com_dados, PESSOAS, id_com_nota, "Alguma anotação.")

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view.carregar_dados()

    def tem_icone_nota(id_registro):
        linha = next(i for i, r in enumerate(view._pagina_atual_de_registros()) if r["ID"] == id_registro)
        celula = view.tabela_widget.cellWidget(linha, 1)
        return any(
            isinstance(w, QLabel) and w.toolTip() == "Este registro tem uma anotação"
            for w in celula.findChildren(QLabel)
        )

    assert tem_icone_nota(id_com_nota)
    assert not tem_icone_nota(id_sem_nota)


def _png_bytes_teste(qapp) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.red)
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


def test_lista_registros_view_avatar_da_linha_e_clicavel_so_quem_tem_foto(banco_com_dados):
    from ui.avatar import AvatarClicavel

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_com_foto = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Com Foto", "FOTO": foto})
    id_sem_foto = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Sem Foto"})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view.carregar_dados()

    def tem_avatar_clicavel(id_registro):
        linha = next(i for i, r in enumerate(view._pagina_atual_de_registros()) if r["ID"] == id_registro)
        celula = view.tabela_widget.cellWidget(linha, 1)
        return any(isinstance(w, AvatarClicavel) for w in celula.findChildren(AvatarClicavel))

    assert tem_avatar_clicavel(id_com_foto)
    assert not tem_avatar_clicavel(id_sem_foto)


def test_lista_registros_view_clicar_avatar_da_linha_abre_popup_sem_mudar_detalhe(banco_com_dados, monkeypatch):
    """Regressao/verificacao: clicar exatamente no avatar (quando tem foto)
    tem que abrir o popup de foto, e NAO tambem disparar
    _ao_clicar_celula/_mostrar_detalhe como o resto da celula faz (o clique
    e consumido pelo AvatarClicavel antes de virar cellClicked da tabela)."""
    from PySide6.QtTest import QTest

    from ui.foto_popup_dialog import FotoPopupDialog

    chamadas = []
    monkeypatch.setattr(FotoPopupDialog, "exec", lambda self: chamadas.append(self.registro["ID"]))

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Com Foto", "FOTO": foto})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view.carregar_dados()
    assert view._registro_detalhe is None

    from ui.avatar import AvatarClicavel

    linha = next(i for i, r in enumerate(view._pagina_atual_de_registros()) if r["ID"] == id_pessoa)
    celula = view.tabela_widget.cellWidget(linha, 1)
    avatar = next(w for w in celula.findChildren(AvatarClicavel))

    QTest.mouseClick(avatar, Qt.LeftButton)

    assert chamadas == [id_pessoa]
    assert view._registro_detalhe is None  # nao mudou so por causa do clique no avatar


def test_lista_registros_view_avatar_do_painel_de_detalhe_e_clicavel_quando_tem_foto(banco_com_dados):
    from ui.avatar import AvatarClicavel

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Com Foto", "FOTO": foto})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    pessoa = records.get_record(banco_com_dados, PESSOAS, id_pessoa)
    view._mostrar_detalhe(pessoa)

    assert view.painel_detalhe.findChildren(AvatarClicavel)


def test_lista_registros_view_bulk_selecao_mostra_botao_excluir(banco_com_dados):
    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert view.botao_excluir_selecionados.isHidden()

    primeiro_id = view._pagina_atual_de_registros()[0]["ID"]
    view._alternar_selecao(primeiro_id, True)
    assert not view.botao_excluir_selecionados.isHidden()
    assert "1" in view.botao_excluir_selecionados.text()

    view._alternar_selecao(primeiro_id, False)
    assert view.botao_excluir_selecionados.isHidden()


def test_lista_registros_view_bulk_selecao_mostra_botao_acoes_massa(banco_com_dados):
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    assert view.botao_acoes_massa.isHidden()

    view._alternar_selecao(id_pessoa, True)
    assert not view.botao_acoes_massa.isHidden()
    assert "1" in view.botao_acoes_massa.text()


def test_lista_registros_view_menu_acoes_massa_tem_mudar_campos_so_para_pessoas(banco_com_dados):
    """"Mudar categoria/empresa/Cargo/Tratamento" so fazem sentido pra
    PESSOAS -- outras tabelas (ex.: Empresas) so oferecem "Exportar
    selecionados"."""
    view_pessoas = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    textos_pessoas = {a.text() for a in view_pessoas.botao_acoes_massa.menu().actions()}
    assert "Mudar categoria..." in textos_pessoas
    assert "Mudar empresa..." in textos_pessoas
    assert "Mudar Cargo..." in textos_pessoas
    assert "Mudar Tratamento..." in textos_pessoas
    assert "Baixar fotos..." in textos_pessoas
    assert "Exportar selecionados..." in textos_pessoas

    view_empresas = ListaRegistrosView(banco_com_dados, EMPRESAS, "admin")
    textos_empresas = {a.text() for a in view_empresas.botao_acoes_massa.menu().actions()}
    assert textos_empresas == {"Exportar selecionados..."}


def test_lista_registros_view_massa_aplicar_categoria_muda_todos_selecionados(banco_com_dados):
    categorias.adicionar_categoria(banco_com_dados, "Diretores Técnicos")
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_a = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "A"})
    id_b = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "B"})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._ids_selecionados = {id_a, id_b}
    view._massa_aplicar_categoria(["Diretores Técnicos"])

    assert categorias.categorias_da_pessoa(banco_com_dados, id_a) == ["Diretores Técnicos"]
    assert categorias.categorias_da_pessoa(banco_com_dados, id_b) == ["Diretores Técnicos"]


def test_lista_registros_view_massa_aplicar_campo_muda_empresa_e_texto(banco_com_dados):
    id_empresa_1 = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "AAA", "EMPRESA": "Empresa AAA"})
    id_empresa_2 = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "BBB", "EMPRESA": "Empresa BBB"})
    id_a = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa_1, "NOME": "A"})
    id_b = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa_1, "NOME": "B"})

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._ids_selecionados = {id_a, id_b}
    view._massa_aplicar_campo("ID_EMPRESA", id_empresa_2)
    view._ids_selecionados = {id_a, id_b}
    view._massa_aplicar_campo("CARGO", "Diretor Financeiro")

    pessoa_a = records.get_record(banco_com_dados, PESSOAS, id_a)
    pessoa_b = records.get_record(banco_com_dados, PESSOAS, id_b)
    assert pessoa_a["ID_EMPRESA"] == id_empresa_2
    assert pessoa_b["ID_EMPRESA"] == id_empresa_2
    assert pessoa_a["CARGO"] == "Diretor Financeiro"
    assert pessoa_b["CARGO"] == "Diretor Financeiro"


def test_lista_registros_view_massa_baixar_fotos_so_dos_selecionados(banco_com_dados, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_selecionado = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Selecionado", "FOTO": foto})
    records.create_record(
        banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Nao Selecionado", "FOTO": _png_bytes_teste(banco_com_dados)}
    )

    view = ListaRegistrosView(banco_com_dados, PESSOAS, "admin")
    view._ids_selecionados = {id_selecionado}

    destino = tmp_path / "saida.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    view._acao_massa_baixar_fotos()
    assert destino.read_bytes() == foto


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


def test_record_form_dialog_foto_novo_registro_comeca_sem_foto(banco_com_dados):
    from ui.widgets import WidgetFoto

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=None)
    assert isinstance(dialogo._widgets["FOTO"], WidgetFoto)
    assert "FOTO_MIME" not in dialogo._widgets  # nunca vira campo proprio

    dialogo._ao_salvar()
    assert dialogo.resultado()["FOTO"] is None
    assert dialogo.resultado()["FOTO_MIME"] is None


def test_record_form_dialog_foto_editar_registro_com_foto_preserva_ao_salvar(banco_com_dados):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.red)
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    foto = bytes(dados)

    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"NOME": "Fulano", "FOTO": foto})
    pessoa = records.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    widget_foto = dialogo._widgets["FOTO"]
    assert widget_foto.foto_bytes() == foto

    dialogo._ao_salvar()
    assert dialogo.resultado()["FOTO"] == foto
    assert dialogo.resultado()["FOTO_MIME"] == "image/png"


def test_record_form_dialog_foto_remover_limpa_ao_salvar(banco_com_dados):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.red)
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    foto = bytes(dados)

    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"NOME": "Fulano", "FOTO": foto})
    pessoa = records.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    dialogo._widgets["FOTO"]._remover_foto()
    dialogo._ao_salvar()

    assert dialogo.resultado()["FOTO"] is None
    assert dialogo.resultado()["FOTO_MIME"] is None


def test_widget_foto_escolher_imagem_abre_ajuste_e_usa_recorte(qapp, monkeypatch, tmp_path):
    """Escolher um arquivo abre o dialogo de ajustar/girar -- o resultado
    salvo no campo e o RECORTE devolvido por esse dialogo, nao o arquivo
    original direto."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QDialog, QFileDialog

    from ui.ajustar_foto_dialog import AjustarFotoDialog
    from ui.widgets import WidgetFoto

    original = QPixmap(400, 300)
    original.fill(QColor("blue"))
    caminho = tmp_path / "original.png"
    original.save(str(caminho), "PNG")

    recorte = QPixmap(320, 320)
    recorte.fill(Qt.red)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(caminho), "")))
    monkeypatch.setattr(AjustarFotoDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(AjustarFotoDialog, "resultado", lambda self: recorte)

    widget = WidgetFoto("Fulano", None)
    widget._escolher_imagem()

    pixmap_salvo = QPixmap()
    pixmap_salvo.loadFromData(widget.foto_bytes())
    assert pixmap_salvo.width() == 320
    assert pixmap_salvo.height() == 320


def test_widget_foto_cancelar_ajuste_mantem_foto_anterior(qapp, monkeypatch, tmp_path):
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QDialog, QFileDialog

    from ui.ajustar_foto_dialog import AjustarFotoDialog
    from ui.widgets import WidgetFoto

    original = QPixmap(400, 300)
    original.fill(QColor("blue"))
    caminho = tmp_path / "original.png"
    original.save(str(caminho), "PNG")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(caminho), "")))
    monkeypatch.setattr(AjustarFotoDialog, "exec", lambda self: QDialog.Rejected)

    foto_anterior = b"foto que ja existia"
    widget = WidgetFoto("Fulano", foto_anterior)
    widget._escolher_imagem()

    assert widget.foto_bytes() == foto_anterior


def test_widget_foto_botao_editar_so_habilitado_quando_ja_tem_foto(qapp):
    from ui.widgets import WidgetFoto

    sem_foto = WidgetFoto("Fulano", None)
    assert not sem_foto._botao_editar.isEnabled()

    dados = _png_bytes_teste(qapp)
    com_foto = WidgetFoto("Fulano", dados)
    assert com_foto._botao_editar.isEnabled()


def test_widget_foto_editar_reabre_ajuste_na_foto_atual(qapp, monkeypatch):
    """"Editar foto..." reabre o mesmo editor de arrastar/zoom/girar, mas
    carregando a foto JA SALVA (sem precisar escolher o arquivo de novo)."""
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QDialog

    from ui.ajustar_foto_dialog import AjustarFotoDialog
    from ui.widgets import WidgetFoto

    foto_atual = _png_bytes_teste(qapp)
    novo_recorte = QPixmap(320, 320)
    novo_recorte.fill(QColor("green"))

    pixmaps_recebidos = []

    def _exec_falso(self):
        pixmaps_recebidos.append(self.palco._imagem)
        return QDialog.Accepted

    monkeypatch.setattr(AjustarFotoDialog, "exec", _exec_falso)
    monkeypatch.setattr(AjustarFotoDialog, "resultado", lambda self: novo_recorte)

    widget = WidgetFoto("Fulano", foto_atual)
    widget._editar_foto()

    # o editor abriu carregando a foto que JA estava salva (nao pediu arquivo)
    pixmap_original_carregado = QPixmap()
    pixmap_original_carregado.loadFromData(foto_atual)
    assert pixmaps_recebidos[0].toImage() == pixmap_original_carregado.toImage()

    pixmap_salvo = QPixmap()
    pixmap_salvo.loadFromData(widget.foto_bytes())
    assert pixmap_salvo.toImage() == novo_recorte.toImage()


def test_widget_foto_editar_sem_foto_nao_faz_nada(qapp, monkeypatch):
    from ui.ajustar_foto_dialog import AjustarFotoDialog
    from ui.widgets import WidgetFoto

    chamou = []
    monkeypatch.setattr(AjustarFotoDialog, "__init__", lambda self, *a, **k: chamou.append(True))

    widget = WidgetFoto("Fulano", None)
    widget._editar_foto()

    assert chamou == []
    assert widget.foto_bytes() is None


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


def test_record_form_dialog_selecao_preserva_valor_nao_cadastrado(banco_com_dados):
    """Regressao: um campo do tipo 'selecao' (ex.: SEXO) cujo valor JA
    GRAVADO nao bate com nenhuma das opcoes da lista (ex.: abreviacao "M" em
    vez de "Masculino") nao pode fazer o combo cair silenciosamente no
    primeiro item ("Feminino") -- isso mostraria um valor ERRADO na tela e,
    se a pessoa salvasse sem mexer no campo, sobrescreveria o dado real sem
    perceber. O valor original precisa continuar selecionado/visivel."""
    from db import records as records_mod

    id_empresa = records_mod.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records_mod.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "SEXO": "M"})
    pessoa = records_mod.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    widget = dialogo._widgets["SEXO"]
    assert isinstance(widget, QComboBox)
    assert widget.currentText() == "M"

    dialogo._ao_salvar()
    assert dialogo.resultado()["SEXO"] == "M"


def test_record_form_dialog_selecao_ignora_diferenca_de_maiusculas(banco_com_dados):
    """Um valor ja gravado que so difere de uma opcao cadastrada por
    maiusculas/minusculas (ex.: 'masculino' vs. 'Masculino') deve selecionar
    a opcao existente, em vez de virar um item extra duplicado."""
    from db import records as records_mod

    id_empresa = records_mod.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records_mod.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "SEXO": "masculino"})
    pessoa = records_mod.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    widget = dialogo._widgets["SEXO"]
    assert isinstance(widget, QComboBox)
    assert widget.currentText() == "Masculino"
    assert widget.count() == 2  # nao deve ter criado um item extra


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


def test_record_form_dialog_botao_limpar_data_permite_salvar_em_branco(banco_com_dados):
    """Regressao: antes, uma vez que o QDateEdit tinha uma data carregada
    (editando um registro que ja tinha data de nascimento), nao existia
    jeito nenhum de voltar pro estado 'em branco' -- nem um botao de limpar
    existia. O botao novo (_limpar_data) devolve o campo pro estado vazio
    mesmo nesse caso, e o valor salvo vira None."""
    from PySide6.QtWidgets import QDateEdit

    from db import records as records_mod

    id_empresa = records_mod.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records_mod.create_record(
        banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "DATA DE NASCIMENTO": "1990-05-20"}
    )
    pessoa = records_mod.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    widget = dialogo._widgets["DATA DE NASCIMENTO"]
    assert isinstance(widget, QDateEdit)

    dialogo._limpar_data(widget)
    dialogo._ao_salvar()
    assert dialogo.resultado()["DATA DE NASCIMENTO"] is None


def test_record_form_dialog_escolher_data_depois_de_limpar_volta_a_salvar(banco_com_dados):
    """Depois de limpar um campo que ja tinha data, escolher uma data NOVA
    de verdade precisa voltar a marcar o campo como preenchido -- antes
    dessa mudanca, o sinal dateChanged so era conectado em campos que
    COMECAVAM vazios, entao um campo que tinha data nunca reagia a essa
    reconexao."""
    from PySide6.QtCore import QDate

    from db import records as records_mod

    id_empresa = records_mod.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records_mod.create_record(
        banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "DATA DE NASCIMENTO": "1990-05-20"}
    )
    pessoa = records_mod.get_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = RecordFormDialog(banco_com_dados, PESSOAS, registro=pessoa)
    widget = dialogo._widgets["DATA DE NASCIMENTO"]

    dialogo._limpar_data(widget)
    widget.setDate(QDate(2000, 1, 1))
    dialogo._ao_salvar()
    assert dialogo.resultado()["DATA DE NASCIMENTO"] == "2000-01-01"


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


def test_export_dialog_secao_fotos_so_aparece_para_pessoas(banco_com_dados):
    dialogo = ExportDialog(banco_com_dados, tabela_padrao=PESSOAS)
    assert not dialogo.grupo_fotos.isHidden()

    dialogo.combo_tabela.setCurrentText(EMPRESAS)
    assert dialogo.grupo_fotos.isHidden()

    dialogo.combo_tabela.setCurrentText(PESSOAS)
    assert not dialogo.grupo_fotos.isHidden()


def test_export_dialog_baixar_fotos_todas(banco_com_dados, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano", "FOTO": foto})

    dialogo = ExportDialog(banco_com_dados, tabela_padrao=PESSOAS)
    destino = tmp_path / "saida.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    dialogo._baixar_fotos()
    assert destino.read_bytes() == foto


def test_export_dialog_baixar_fotos_por_categoria(banco_com_dados, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    categorias.adicionar_categoria(banco_com_dados, "Presidentes")
    categorias.adicionar_categoria(banco_com_dados, "Diretores Técnicos")
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_presidente = records.create_record(
        banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Presidente", "FOTO": _png_bytes_teste(banco_com_dados)}
    )
    id_diretor = records.create_record(
        banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Diretor", "FOTO": _png_bytes_teste(banco_com_dados)}
    )
    categorias.definir_categorias_da_pessoa(banco_com_dados, id_presidente, ["Presidentes"])
    categorias.definir_categorias_da_pessoa(banco_com_dados, id_diretor, ["Diretores Técnicos"])

    dialogo = ExportDialog(banco_com_dados, tabela_padrao=PESSOAS)
    dialogo.combo_categoria_fotos.setCurrentText("Presidentes")

    destino = tmp_path / "saida.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))
    dialogo._baixar_fotos()

    presidente = records.get_record(banco_com_dados, PESSOAS, id_presidente)
    assert destino.read_bytes() == presidente["FOTO"]  # so o presidente, nao o diretor


def test_export_dialog_com_ids_selecionados_trava_tabela(banco_com_dados):
    """Quando aberto a partir de "Exportar selecionados" (acao em massa),
    a escolha de tabela fica travada -- os IDs marcados so fazem sentido
    pra tabela de onde vieram."""
    dialogo = ExportDialog(banco_com_dados, tabela_padrao=PESSOAS, ids_selecionados={1, 2, 3})
    assert not dialogo.combo_tabela.isEnabled()
    assert "3" in dialogo.windowTitle()


def test_settings_dialog_constroi(banco_com_dados):
    dialogo = SettingsDialog(banco_com_dados, "admin")
    assert dialogo.campo_nome.text()


def test_settings_dialog_tem_botao_lixeira(banco_com_dados):
    from PySide6.QtWidgets import QPushButton

    dialogo = SettingsDialog(banco_com_dados, "admin")
    textos = [b.text() for b in dialogo.findChildren(QPushButton)]
    assert "Lixeira..." in textos


def test_lixeira_dialog_mostra_registro_tabela_e_campo_excluidos(banco_com_dados):
    from db.tables import add_column, create_data_sheet, delete_data_sheet, drop_column

    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})
    records.delete_record(banco_com_dados, PESSOAS, id_pessoa)

    create_data_sheet(banco_com_dados, "FORNECEDORES")
    delete_data_sheet(banco_com_dados, "FORNECEDORES")

    add_column(banco_com_dados, EMPRESAS, "OBSERVACAO", "TEXT")
    drop_column(banco_com_dados, EMPRESAS, "OBSERVACAO")

    dialogo = LixeiraDialog(banco_com_dados, "admin")
    assert dialogo.tabela_registros.rowCount() == 1
    assert dialogo.tabela_registros.item(0, 0).text() == "Fulano"
    assert dialogo.tabela_tabelas.rowCount() == 1
    assert dialogo.tabela_tabelas.item(0, 0).text() == "FORNECEDORES"
    assert dialogo.tabela_campos.rowCount() == 1
    assert dialogo.tabela_campos.item(0, 0).text() == "OBSERVACAO"


def test_lixeira_dialog_restaurar_registro_recarrega_lista(banco_com_dados):
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"ID_EMPRESA": id_empresa, "NOME": "Fulano"})
    records.delete_record(banco_com_dados, PESSOAS, id_pessoa)

    dialogo = LixeiraDialog(banco_com_dados, "admin")
    assert dialogo.tabela_registros.rowCount() == 1

    id_lixeira = lixeira.listar_registros(banco_com_dados)[0]["id_lixeira"]
    dialogo._restaurar_registro(id_lixeira)

    assert dialogo.tabela_registros.rowCount() == 0
    assert records.get_records(banco_com_dados, PESSOAS)[0]["NOME"] == "Fulano"


def test_lixeira_dialog_excluir_definitivamente_pede_confirmacao(banco_com_dados, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    id_pessoa = records.create_record(banco_com_dados, PESSOAS, {"NOME": "Fulano"})
    records.delete_record(banco_com_dados, PESSOAS, id_pessoa)
    id_lixeira = lixeira.listar_registros(banco_com_dados)[0]["id_lixeira"]

    dialogo = LixeiraDialog(banco_com_dados, "admin")

    # Por padrao (fixture sem_caixas_de_dialogo_bloqueantes), QMessageBox.question
    # devolve "No" -- ou seja, cancelar a confirmacao tem que MANTER o item.
    dialogo._confirmar_e_excluir(
        "Fulano", lambda: dialogo._excluir_definitivamente(lixeira.excluir_definitivamente_registro, id_lixeira, dialogo._popular_registros)
    )
    assert len(lixeira.listar_registros(banco_com_dados)) == 1

    # Confirmando (Yes), o item some de vez.
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    dialogo._confirmar_e_excluir(
        "Fulano", lambda: dialogo._excluir_definitivamente(lixeira.excluir_definitivamente_registro, id_lixeira, dialogo._popular_registros)
    )
    assert lixeira.listar_registros(banco_com_dados) == []


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


def test_settings_dialog_campo_extra_nao_oferece_foto(banco_com_dados):
    dialogo = SettingsDialog(banco_com_dados, "admin")
    dialogo.combo_tabela_resumo.setCurrentText(PESSOAS)

    disponiveis = set(_dados_lista(dialogo.lista_campos_disponiveis))
    escolhidos = set(_dados_lista(dialogo.lista_campos_escolhidos))
    assert "FOTO" not in disponiveis | escolhidos
    assert "FOTO_MIME" not in disponiveis | escolhidos


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


def test_dashboard_view_filtro_de_campo_nao_oferece_foto(banco_com_dados):
    view = DashboardView(banco_com_dados)
    campos = {campo for _, campo in view._opcoes_de_campo_painel()}
    assert "FOTO" not in campos
    assert "FOTO_MIME" not in campos


def test_dashboard_view_aniversariante_com_foto_mostra_avatar_com_foto(banco_com_dados):
    from PySide6.QtWidgets import QLabel

    from ui.avatar import AvatarClicavel

    foto = _png_bytes_teste(banco_com_dados)
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})
    records.create_record(
        banco_com_dados, PESSOAS,
        {"ID_EMPRESA": id_empresa, "NOME": "Com Foto", "DATA DE NASCIMENTO": "1990-01-01", "FOTO": foto},
    )

    view = DashboardView(banco_com_dados)
    # sem clicavel=True no Dashboard (nao foi pedido popup aqui) -- e so um
    # QLabel comum com a foto, nunca um AvatarClicavel.
    assert not view._grupo_aniversarios.findChildren(AvatarClicavel)
    avatares_com_foto = [
        w for w in view._grupo_aniversarios.findChildren(QLabel)
        if w.objectName() != "AvatarIniciais" and not w.pixmap().isNull()
    ]
    assert avatares_com_foto


def test_dashboard_view_filtro_so_afeta_lista_de_aniversariantes(banco_com_dados):
    """Pedido do usuario: o filtro do Painel filtra SO "Proximos
    aniversarios" -- os cartoes do topo continuam mostrando o total geral,
    sem levar o filtro em conta."""
    from PySide6.QtWidgets import QLabel

    id_empresa_a = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "AAA", "EMPRESA": "Empresa AAA"})
    id_empresa_b = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "BBB", "EMPRESA": "Empresa BBB"})
    records.create_record(
        banco_com_dados, PESSOAS,
        {"ID_EMPRESA": id_empresa_a, "NOME": "Da Empresa A", "DATA DE NASCIMENTO": "1990-01-01"},
    )
    records.create_record(
        banco_com_dados, PESSOAS,
        {"ID_EMPRESA": id_empresa_b, "NOME": "Da Empresa B", "DATA DE NASCIMENTO": "1990-01-02"},
    )

    view = DashboardView(banco_com_dados, "admin")
    view._adicionar_linha_filtro_painel()
    linha = view._linhas_filtro_painel[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Empresa"))
    linha.widget_valor.setCurrentIndex(linha.widget_valor.findData(id_empresa_a))

    nomes = [a.nome for a in dashboard.proximos_aniversarios(banco_com_dados, registros=view._pessoas_filtradas())]
    assert nomes == ["Da Empresa A"]

    # O total de contatos cadastrados continua sendo TODOS, filtro ou nao.
    total_pessoas = len(records.get_records(banco_com_dados, PESSOAS))
    primeiro_cartao = view._linha_cartoes.itemAt(0).widget()
    textos = [lbl.text() for lbl in primeiro_cartao.findChildren(QLabel)]
    assert str(total_pessoas) in textos


def test_dashboard_view_filtro_salva_e_restaura_por_usuario(banco_com_dados):
    id_empresa = records.create_record(banco_com_dados, EMPRESAS, {"SIGLA": "ZZZ", "EMPRESA": "Empresa ZZZ"})

    view = DashboardView(banco_com_dados, "admin")
    view._adicionar_linha_filtro_painel()
    linha = view._linhas_filtro_painel[0]
    linha.combo_campo.setCurrentIndex(linha.combo_campo.findText("Empresa"))
    linha.widget_valor.setCurrentIndex(linha.widget_valor.findData(id_empresa))

    view_reaberta = DashboardView(banco_com_dados, "admin")
    assert len(view_reaberta._linhas_filtro_painel) == 1
    linha_restaurada = view_reaberta._linhas_filtro_painel[0]
    assert linha_restaurada.combo_campo.currentData() == "_EMPRESA_BUSCA"
    assert linha_restaurada.widget_valor.currentData() == id_empresa

    # Outro usuario no mesmo banco nao ve esse filtro.
    auth.criar_usuario(banco_com_dados, "outra_pessoa", "senha123", "Outra Pessoa")
    view_outra_pessoa = DashboardView(banco_com_dados, "outra_pessoa")
    assert view_outra_pessoa._linhas_filtro_painel == []


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
