"""Testes dos widgets reutilizaveis de selecao multipla (ui/widgets.py)."""
from ui.widgets import SelecaoMultiplaLista


def test_selecao_multipla_lista_inicia_com_marcados_e_preserva_orfaos():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos"], marcados=["Presidentes", "Categoria Removida"])
    assert lista.count() == 3  # 2 opcoes + 1 orfa
    assert set(lista.selecionados()) == {"Presidentes", "Categoria Removida"}


def test_selecao_multipla_lista_respeita_a_ordem_das_opcoes_recebidas():
    lista = SelecaoMultiplaLista(["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"])
    textos = [lista.item(i).text() for i in range(lista.count())]
    assert textos == ["Presidentes", "Diretores Técnicos", "Diretores Adm. Financeiros"]
