from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPixmap

from ui.ajustar_foto_dialog import _TAMANHO_PALCO, AjustarFotoDialog, _PalcoAjusteFoto


def _pixmap(largura: int, altura: int, cor=Qt.red) -> QPixmap:
    pixmap = QPixmap(largura, altura)
    pixmap.fill(QColor(cor))
    return pixmap


# ============================================================================
# _PalcoAjusteFoto -- geometria
# ============================================================================

def test_zoom_minimo_cobre_o_palco_pelo_lado_menor(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))  # paisagem: lado menor = altura (400)
    assert palco.zoom_minimo() == _TAMANHO_PALCO / 400


def test_zoom_minimo_para_imagem_vertical(qapp):
    palco = _PalcoAjusteFoto(_pixmap(400, 800))  # retrato: lado menor = largura (400)
    assert palco.zoom_minimo() == _TAMANHO_PALCO / 400


def test_definir_imagem_comeca_com_zoom_minimo_e_centralizado(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))
    assert palco.zoom_atual() == palco.zoom_minimo()
    resultado = palco.resultado()
    assert resultado.width() == _TAMANHO_PALCO
    assert resultado.height() == _TAMANHO_PALCO


def test_girar_troca_largura_e_altura_e_reseta_zoom(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))
    zoom_antes = palco.zoom_minimo()  # baseado no lado menor = 400

    palco.girar(90)

    # depois de girar 90, a imagem fica 400x800 -- o lado menor continua
    # 400, entao o zoom minimo NAO muda nesse caso especifico, mas o
    # importante e que o zoom atual volta a ser o minimo (novo) sempre.
    assert palco.zoom_atual() == palco.zoom_minimo()
    assert palco._imagem.width() == 400
    assert palco._imagem.height() == 800
    assert zoom_antes == palco.zoom_minimo()  # 800x400 girado vira 400x800, lado menor continua 400


def test_mover_dentro_do_limite_desloca_livremente(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))  # zoom minimo: largura exibida = 800*(320/400) = 640
    antes = QPointF(palco._deslocamento)
    palco.mover(QPointF(-10, 0))
    assert palco._deslocamento.x() == antes.x() - 10


def test_mover_alem_do_limite_fica_grudado_na_borda(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))
    palco.mover(QPointF(-10_000, 0))  # arrasta bem mais que o possivel
    largura_exibida = palco._imagem.width() * palco.zoom_atual()
    assert palco._deslocamento.x() == _TAMANHO_PALCO - largura_exibida  # colado na borda direita

    palco.mover(QPointF(10_000, 0))  # arrasta de volta, bem alem do outro lado
    assert palco._deslocamento.x() == 0.0  # colado na borda esquerda


def test_definir_zoom_respeita_limites(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))
    palco.definir_zoom(palco.zoom_minimo() - 1)
    assert palco.zoom_atual() == palco.zoom_minimo()

    palco.definir_zoom(palco.zoom_maximo() + 1)
    assert palco.zoom_atual() == palco.zoom_maximo()


def test_definir_zoom_mantem_deslocamento_dentro_dos_limites(qapp):
    palco = _PalcoAjusteFoto(_pixmap(800, 400))
    palco.definir_zoom(palco.zoom_maximo())
    largura_exibida = palco._imagem.width() * palco.zoom_atual()
    altura_exibida = palco._imagem.height() * palco.zoom_atual()
    assert _TAMANHO_PALCO - largura_exibida <= palco._deslocamento.x() <= 0
    assert _TAMANHO_PALCO - altura_exibida <= palco._deslocamento.y() <= 0


# ============================================================================
# AjustarFotoDialog
# ============================================================================

def test_ajustar_foto_dialog_constroi(qapp):
    dialogo = AjustarFotoDialog(_pixmap(800, 400))
    assert dialogo.palco.zoom_atual() == dialogo.palco.zoom_minimo()


def test_ajustar_foto_dialog_girar_reseta_slider(qapp):
    dialogo = AjustarFotoDialog(_pixmap(800, 400))
    dialogo.slider_zoom.setValue(500)
    dialogo._girar(90)
    assert dialogo.slider_zoom.value() == 0


def test_ajustar_foto_dialog_slider_ajusta_zoom_do_palco(qapp):
    dialogo = AjustarFotoDialog(_pixmap(800, 400))
    dialogo.slider_zoom.setValue(dialogo.slider_zoom.maximum())
    assert dialogo.palco.zoom_atual() == dialogo.palco.zoom_maximo()


def test_ajustar_foto_dialog_resultado_e_quadrado(qapp):
    dialogo = AjustarFotoDialog(_pixmap(800, 400))
    resultado = dialogo.resultado()
    assert resultado.width() == _TAMANHO_PALCO
    assert resultado.height() == _TAMANHO_PALCO
