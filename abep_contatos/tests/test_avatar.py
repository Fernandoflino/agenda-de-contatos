from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from ui.avatar import AvatarClicavel, criar_avatar


def _png_bytes(qapp) -> bytes:
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.red)
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


def test_criar_avatar_sem_foto_mostra_iniciais(qapp):
    avatar = criar_avatar("Fulano de Tal", tamanho=30)
    assert avatar.objectName() == "AvatarIniciais"
    assert avatar.text() == "FT"
    assert not isinstance(avatar, AvatarClicavel)


def test_criar_avatar_com_foto_mostra_pixmap(qapp):
    foto = _png_bytes(qapp)
    avatar = criar_avatar("Fulano de Tal", tamanho=30, foto_bytes=foto)
    assert avatar.pixmap() is not None
    assert not avatar.pixmap().isNull()
    assert avatar.size().width() == 30


def test_criar_avatar_com_foto_invalida_cai_pras_iniciais(qapp):
    avatar = criar_avatar("Fulano de Tal", tamanho=30, foto_bytes=b"nao e uma imagem")
    assert avatar.objectName() == "AvatarIniciais"


def test_criar_avatar_clicavel_so_com_foto(qapp):
    foto = _png_bytes(qapp)
    avatar_sem_foto = criar_avatar("Fulano", tamanho=30, clicavel=True)
    assert not isinstance(avatar_sem_foto, AvatarClicavel)

    avatar_com_foto = criar_avatar("Fulano", tamanho=30, foto_bytes=foto, clicavel=True)
    assert isinstance(avatar_com_foto, AvatarClicavel)


def test_avatar_clicavel_emite_sinal_ao_clicar(qapp):
    foto = _png_bytes(qapp)
    avatar = criar_avatar("Fulano", tamanho=30, foto_bytes=foto, clicavel=True)

    recebido = []
    avatar.clicado.connect(lambda: recebido.append(True))

    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent

    evento = QMouseEvent(
        QEvent.MouseButtonPress, QPointF(5, 5), QPointF(5, 5), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
    )
    avatar.mousePressEvent(evento)
    assert recebido == [True]
