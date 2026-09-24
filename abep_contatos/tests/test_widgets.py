"""Testes dos widgets reutilizaveis de selecao multipla (ui/widgets.py)."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout

from ui.widgets import ComboMultiSelecao, SelecaoMultiplaLista


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _combo_numa_janela_larga(qapp, opcoes=("A", "B", "C")):
    """Monta o combo dentro de uma janela .show()-ada e bem larga, igual ao
    caso real (a caixa de valor do filtro ocupa quase a linha inteira) --
    testar so com showPopup() direto nao pega bugs de clique do mouse."""
    janela = QDialog()
    layout = QVBoxLayout(janela)
    combo = ComboMultiSelecao()
    combo.definir_opcoes(list(opcoes))
    layout.addWidget(combo)
    janela.resize(600, 80)
    janela.show()
    return janela, combo


def test_combo_multi_selecao_abre_popup_com_clique_no_meio_da_caixa(qapp):
    """Regressao: o combo e "editavel" (pra mostrar texto resumido tipo
    "(todas)"), e o campo de texto interno criado por setEditable() cobre
    quase toda a largura da caixa -- um clique real do usuario cai NESSE
    campo de texto, nao no QComboBox em si, entao o clique precisa ser
    simulado no lineEdit() (o widget que realmente fica embaixo do cursor
    na tela), nao no combo diretamente -- senao o teste passaria mesmo com
    o bug presente (o bug so aparece com um clique de verdade)."""
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        assert not combo.view().isVisible()
        le = combo.lineEdit()
        QTest.mouseClick(le, Qt.LeftButton, pos=QPoint(min(150, le.width() - 5), le.height() // 2))
        qapp.processEvents()  # o popup abre num QTimer.singleShot(0, ...), nao na hora do clique
        assert combo.view().isVisible()
    finally:
        janela.close()


def test_combo_multi_selecao_popup_continua_aberto_apos_soltar_o_clique(qapp):
    """Regressao: abrir o popup DENTRO do proprio evento de clique (com o
    botao do mouse ainda fisicamente pressionado) faz o popup "herdar" esse
    pressionar como se fosse um menu do tipo segura-arrasta-solta -- soltar
    o botao localizado sobre um item (o caso comum, ja que o popup abre bem
    embaixo do cursor) fechava tudo na hora, dando a impressao de que so
    funcionava segurando o clique. O popup precisa continuar aberto depois
    de um clique normal (pressionar e soltar rapido, sem segurar)."""
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        le = combo.lineEdit()
        ponto = QPoint(min(150, le.width() - 5), le.height() // 2)
        QTest.mousePress(le, Qt.LeftButton, pos=ponto)
        QTest.mouseRelease(le, Qt.LeftButton, pos=ponto)  # solta logo em seguida, sem segurar
        qapp.processEvents()
        assert combo.view().isVisible()
    finally:
        janela.close()


def test_combo_multi_selecao_abre_popup_com_clique_na_seta(qapp):
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        QTest.mouseClick(combo, Qt.LeftButton, pos=QPoint(combo.width() - 5, combo.height() // 2))
        assert combo.view().isVisible()
    finally:
        janela.close()


def test_combo_multi_selecao_clicar_em_item_do_popup_marca_e_atualiza_texto(qapp):
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        combo.showPopup()
        indice = combo.model().index(0, 0)
        retangulo = combo.view().visualRect(indice)
        QTest.mouseClick(combo.view().viewport(), Qt.LeftButton, pos=retangulo.center())

        assert combo.selecionados() == ["A"]
        assert combo.lineEdit().text() == "A"
    finally:
        janela.close()


def test_combo_multi_selecao_definir_opcoes_preserva_selecao_atual():
    combo = ComboMultiSelecao()
    combo.definir_opcoes(["A", "B", "C"], marcados=["B"])
    assert combo.selecionados() == ["B"]

    combo.definir_opcoes(["A", "B", "C"])  # recarrega sem passar `marcados`
    assert combo.selecionados() == ["B"]  # continua marcado


def test_combo_multi_selecao_texto_resumo_varia_com_quantidade_marcada():
    combo = ComboMultiSelecao()
    assert combo.lineEdit().text() == "(todas)"

    combo.definir_opcoes(["A", "B", "C"], marcados=["A"])
    assert combo.lineEdit().text() == "A"

    combo.definir_opcoes(["A", "B", "C"], marcados=["A", "B"])
    assert combo.lineEdit().text() == "2 categorias selecionadas"


def test_selecao_multipla_lista_inicia_com_marcados_e_preserva_orfaos():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos"], marcados=["Presidentes", "Categoria Removida"])
    assert lista.count() == 3  # 2 opcoes + 1 orfa
    assert set(lista.selecionados()) == {"Presidentes", "Categoria Removida"}


def test_selecao_multipla_lista_respeita_a_ordem_das_opcoes_recebidas():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"])
    textos = [lista.item(i).text() for i in range(lista.count())]
    assert textos == ["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"]
