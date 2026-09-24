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


def _abrir_menu(combo: ComboMultiSelecao) -> None:
    """Abre o menu do combo sem passar pelo clique nativo do botao -- no Qt
    offscreen, o clique nativo entra num loop bloqueante esperando o menu
    fechar de verdade, travando o teste. `popup()` e o mesmo caminho
    nao-bloqueante que o QToolButton usa por baixo dos panos."""
    combo.menu().popup(combo.mapToGlobal(QPoint(0, combo.height())))


def test_combo_multi_selecao_menu_continua_aberto_ao_marcar_varios_itens(qapp):
    """O ponto central do redesenho: ao contrario do QComboBox "hackeado"
    de antes (que em rodadas anteriores ora nao abria com um clique normal,
    ora fechava sozinho), um QMenu com a lista dentro via QWidgetAction so
    fecha ao clicar fora dele -- clicar nos itens (marcando varios, um atras
    do outro) nao deve fechar nada."""
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        _abrir_menu(combo)
        menu = combo.menu()
        assert menu.isVisible()

        lista = combo._lista
        for indice in (0, 1):
            retangulo = lista.visualItemRect(lista.item(indice))
            QTest.mouseClick(lista.viewport(), Qt.LeftButton, pos=retangulo.center())
            assert menu.isVisible()  # continua aberto apos CADA clique

        assert set(combo.selecionados()) == {"A", "B"}
        assert combo.text() == "2 categorias selecionadas"

        menu.close()
        assert not menu.isVisible()
    finally:
        janela.close()


def test_combo_multi_selecao_clicar_de_novo_no_item_desmarca(qapp):
    janela, combo = _combo_numa_janela_larga(qapp)
    try:
        _abrir_menu(combo)
        lista = combo._lista
        retangulo = lista.visualItemRect(lista.item(0))
        QTest.mouseClick(lista.viewport(), Qt.LeftButton, pos=retangulo.center())
        assert combo.selecionados() == ["A"]

        QTest.mouseClick(lista.viewport(), Qt.LeftButton, pos=retangulo.center())
        assert combo.selecionados() == []
        assert combo.text() == "(todas)"
    finally:
        janela.close()


def test_combo_multi_selecao_itens_nao_tem_checkbox(qapp):
    """Pedido explicito: a lista precisa aparecer como uma lista simples
    (igual o filtro de Empresa), sem icone de caixinha de marcar -- a
    selecao e so o destaque/realce da linha (QAbstractItemView.MultiSelection).
    QListWidgetItem e "checkable" por padrao (flag do Qt), mas o delegate so
    desenha a caixinha quando um CheckStateRole de verdade foi atribuido ao
    item -- nunca chamamos setCheckState(), entao nada e desenhado."""
    combo = ComboMultiSelecao()
    combo.definir_opcoes(["A", "B"])
    item = combo._lista.item(0)
    assert item.data(Qt.CheckStateRole) is None
    assert combo._lista.selectionMode() == combo._lista.SelectionMode.MultiSelection


def test_combo_multi_selecao_definir_opcoes_preserva_selecao_atual():
    combo = ComboMultiSelecao()
    combo.definir_opcoes(["A", "B", "C"], marcados=["B"])
    assert combo.selecionados() == ["B"]

    combo.definir_opcoes(["A", "B", "C"])  # recarrega sem passar `marcados`
    assert combo.selecionados() == ["B"]  # continua marcado


def test_combo_multi_selecao_texto_resumo_varia_com_quantidade_marcada():
    combo = ComboMultiSelecao()
    assert combo.text() == "(todas)"

    combo.definir_opcoes(["A", "B", "C"], marcados=["A"])
    assert combo.text() == "A"

    combo.definir_opcoes(["A", "B", "C"], marcados=["A", "B"])
    assert combo.text() == "2 categorias selecionadas"


def test_selecao_multipla_lista_inicia_com_marcados_e_preserva_orfaos():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos"], marcados=["Presidentes", "Categoria Removida"])
    assert lista.count() == 3  # 2 opcoes + 1 orfa
    assert set(lista.selecionados()) == {"Presidentes", "Categoria Removida"}


def test_selecao_multipla_lista_respeita_a_ordem_das_opcoes_recebidas():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"])
    textos = [lista.item(i).text() for i in range(lista.count())]
    assert textos == ["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"]
