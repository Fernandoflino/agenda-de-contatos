"""
Popup de "ajustar foto" -- aberto ao escolher uma imagem nova no formulario
de contato (ver ui/widgets.py::WidgetFoto), antes de gravar de vez. Deixa a
pessoa POSICIONAR a foto (arrastando) e dar ZOOM dentro de um circulo-guia
(a mesma area que vai aparecer no avatar depois), alem de GIRAR a imagem em
passos de 90 graus -- sem isso, o corte automatico (sempre o centro da
foto) podia cortar a cabeca de alguem numa foto vertical, por exemplo.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.theme import marcar_variante

_TAMANHO_PALCO = 320
_FATOR_ZOOM_MAXIMO = 3.0
_PASSOS_SLIDER = 1000  # QSlider so trabalha com inteiros -- zoom vira uma fracao desses passos


class _PalcoAjusteFoto(QWidget):
    """A area quadrada onde a foto aparece, arrastavel, com o circulo-guia
    desenhado por cima. Guarda toda a geometria (imagem atual, zoom,
    deslocamento) -- o dialogo em volta so acrescenta os controles
    (slider de zoom, botoes de girar, OK/Cancelar)."""

    mudou = Signal()

    def __init__(self, pixmap_original: QPixmap, parent=None):
        super().__init__(parent)
        self.setFixedSize(_TAMANHO_PALCO, _TAMANHO_PALCO)
        self.setCursor(Qt.OpenHandCursor)
        self._arrastando = False
        self._ultima_pos: QPointF | None = None
        self.definir_imagem(pixmap_original)

    # -- geometria -----------------------------------------------------------

    def definir_imagem(self, pixmap: QPixmap) -> None:
        self._imagem = pixmap
        self._zoom = self.zoom_minimo()
        self._deslocamento = QPointF(0, 0)
        self._centralizar()
        self.update()

    def zoom_minimo(self) -> float:
        """O zoom mais baixo em que a imagem ainda cobre o palco inteiro
        (o lado MENOR da imagem, nesse zoom, fica do tamanho do palco)."""
        menor_lado = min(self._imagem.width(), self._imagem.height())
        return _TAMANHO_PALCO / menor_lado if menor_lado else 1.0

    def zoom_maximo(self) -> float:
        return self.zoom_minimo() * _FATOR_ZOOM_MAXIMO

    def girar(self, graus: int) -> None:
        self._imagem = self._imagem.transformed(QTransform().rotate(graus), Qt.SmoothTransformation)
        self._zoom = self.zoom_minimo()
        self._centralizar()
        self.update()
        self.mudou.emit()

    def definir_zoom(self, zoom: float) -> None:
        """Muda o zoom mantendo fixo o PONTO da imagem que esta no centro
        do palco (senao a imagem "pularia" pro canto a cada ajuste de
        zoom, em vez de crescer/encolher a partir do meio)."""
        zoom = max(self.zoom_minimo(), min(self.zoom_maximo(), zoom))
        centro_palco = QPointF(_TAMANHO_PALCO / 2, _TAMANHO_PALCO / 2)
        ponto_imagem = (centro_palco - self._deslocamento) / self._zoom
        self._zoom = zoom
        self._deslocamento = centro_palco - ponto_imagem * zoom
        self._clampear_deslocamento()
        self.update()

    def zoom_atual(self) -> float:
        return self._zoom

    def _centralizar(self) -> None:
        largura_exibida = self._imagem.width() * self._zoom
        altura_exibida = self._imagem.height() * self._zoom
        self._deslocamento = QPointF(
            (_TAMANHO_PALCO - largura_exibida) / 2, (_TAMANHO_PALCO - altura_exibida) / 2
        )

    def mover(self, delta: QPointF) -> None:
        self._deslocamento += delta
        self._clampear_deslocamento()
        self.update()

    def _clampear_deslocamento(self) -> None:
        largura_exibida = self._imagem.width() * self._zoom
        altura_exibida = self._imagem.height() * self._zoom
        x = min(0.0, max(_TAMANHO_PALCO - largura_exibida, self._deslocamento.x()))
        y = min(0.0, max(_TAMANHO_PALCO - altura_exibida, self._deslocamento.y()))
        self._deslocamento = QPointF(x, y)

    def resultado(self) -> QPixmap:
        """O recorte final -- a REGIAO da imagem original que esta visivel
        dentro do palco agora, recortada na resolucao NATIVA da imagem (um
        QPixmap.copy() pixel-a-pixel, sem reamostrar pra baixo) -- nao pode
        perder qualidade, so a area visivel e que muda."""
        origem = QRectF(
            -self._deslocamento.x() / self._zoom,
            -self._deslocamento.y() / self._zoom,
            _TAMANHO_PALCO / self._zoom,
            _TAMANHO_PALCO / self._zoom,
        )
        return self._imagem.copy(origem.toAlignedRect())

    # -- desenho / interacao ---------------------------------------------------

    def _desenhar_imagem(self, pintor: QPainter) -> None:
        largura_exibida = self._imagem.width() * self._zoom
        altura_exibida = self._imagem.height() * self._zoom
        destino = QRectF(self._deslocamento.x(), self._deslocamento.y(), largura_exibida, altura_exibida)
        pintor.drawPixmap(destino, self._imagem, QRectF(self._imagem.rect()))

    def paintEvent(self, evento) -> None:  # noqa: N802 (nome do metodo original do Qt)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.SmoothPixmapTransform)
        pintor.setRenderHint(QPainter.Antialiasing)
        self._desenhar_imagem(pintor)

        # Escurece tudo fora do circulo-guia, pra deixar claro o que vai
        # ficar de fora do avatar final.
        caminho_fora = QPainterPath()
        caminho_fora.addRect(QRectF(0, 0, _TAMANHO_PALCO, _TAMANHO_PALCO))
        caminho_circulo = QPainterPath()
        caminho_circulo.addEllipse(QRectF(0, 0, _TAMANHO_PALCO, _TAMANHO_PALCO))
        caminho_fora = caminho_fora.subtracted(caminho_circulo)
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QBrush(QColor(0, 0, 0, 140)))
        pintor.drawPath(caminho_fora)

        pintor.setPen(QPen(QColor(255, 255, 255, 200), 2))
        pintor.setBrush(Qt.NoBrush)
        pintor.drawEllipse(QRectF(1, 1, _TAMANHO_PALCO - 2, _TAMANHO_PALCO - 2))
        pintor.end()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        self._arrastando = True
        self._ultima_pos = evento.position()
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if not self._arrastando or self._ultima_pos is None:
            return
        nova_pos = evento.position()
        self.mover(nova_pos - self._ultima_pos)
        self._ultima_pos = nova_pos

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        self._arrastando = False
        self._ultima_pos = None
        self.setCursor(Qt.OpenHandCursor)


class AjustarFotoDialog(QDialog):
    def __init__(self, pixmap_original: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar foto")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        instrucao = QLabel("Arraste a foto pra posicionar e use o controle abaixo pra dar zoom.")
        instrucao.setProperty("papel", "subtitulo")
        instrucao.setWordWrap(True)
        layout.addWidget(instrucao)

        self.palco = _PalcoAjusteFoto(pixmap_original)
        linha_palco = QHBoxLayout()
        linha_palco.addStretch()
        linha_palco.addWidget(self.palco)
        linha_palco.addStretch()
        layout.addLayout(linha_palco)

        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(0, _PASSOS_SLIDER)
        self.slider_zoom.valueChanged.connect(self._ao_mudar_slider)
        layout.addWidget(self.slider_zoom)
        self._sincronizar_slider()

        linha_girar = QHBoxLayout()
        linha_girar.addStretch()
        botao_girar_esquerda = QPushButton("Girar ↺")
        botao_girar_esquerda.clicked.connect(lambda: self._girar(-90))
        linha_girar.addWidget(botao_girar_esquerda)
        botao_girar_direita = QPushButton("Girar ↻")
        botao_girar_direita.clicked.connect(lambda: self._girar(90))
        linha_girar.addWidget(botao_girar_direita)
        linha_girar.addStretch()
        layout.addLayout(linha_girar)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        marcar_variante(botoes.button(QDialogButtonBox.Cancel), "secundario")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _ao_mudar_slider(self, valor: int) -> None:
        proporcao = valor / _PASSOS_SLIDER
        zoom = self.palco.zoom_minimo() + proporcao * (self.palco.zoom_maximo() - self.palco.zoom_minimo())
        self.palco.definir_zoom(zoom)

    def _girar(self, graus: int) -> None:
        self.palco.girar(graus)
        self._sincronizar_slider()

    def _sincronizar_slider(self) -> None:
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(0)  # girar()/definir_imagem() sempre volta pro zoom minimo
        self.slider_zoom.blockSignals(False)

    def resultado(self) -> QPixmap:
        """O recorte final escolhido -- so tem sentido chamar depois de
        `exec()` devolver Accepted."""
        return self.palco.resultado()
