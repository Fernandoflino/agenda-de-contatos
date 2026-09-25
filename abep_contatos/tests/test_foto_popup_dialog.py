from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QPixmap

from ui.foto_popup_dialog import FotoPopupDialog


def _png_bytes(qapp) -> bytes:
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.red)
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


def test_foto_popup_dialog_constroi_com_foto(qapp):
    registro = {"NOME": "Fulano de Tal", "FOTO": _png_bytes(qapp)}
    dialogo = FotoPopupDialog(registro)
    assert dialogo.windowTitle() == "Fulano de Tal"


def test_foto_popup_dialog_baixar_grava_arquivo(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    dados = _png_bytes(qapp)
    registro = {"NOME": "Fulano de Tal", "_EMPRESA_SIGLA": "TO", "FOTO": dados}
    dialogo = FotoPopupDialog(registro)

    destino = tmp_path / "saida.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))
    dialogo._baixar()

    assert destino.read_bytes() == dados
