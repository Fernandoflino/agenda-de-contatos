import zipfile

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QPixmap

from ui import imagens


def _png_bytes(qapp, largura: int = 20, altura: int = 20, cor=Qt.red) -> bytes:
    pixmap = QPixmap(largura, altura)
    pixmap.fill(QColor(cor))
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


# ============================================================================
# nome_arquivo_foto
# ============================================================================

def test_nome_arquivo_foto_com_sigla_empresa_e_uf():
    registro = {"NOME": "Alírio Félix Martins Barros", "_EMPRESA_SIGLA_EMPRESA": "ATI", "_EMPRESA_SIGLA": "TO"}
    assert imagens.nome_arquivo_foto(registro) == "Alírio Félix Martins Barros - ATI-TO.png"


def test_nome_arquivo_foto_sem_sigla_empresa():
    registro = {"NOME": "Fulano", "_EMPRESA_SIGLA": "TO"}
    assert imagens.nome_arquivo_foto(registro) == "Fulano - TO.png"


def test_nome_arquivo_foto_sem_uf():
    registro = {"NOME": "Fulano", "_EMPRESA_SIGLA_EMPRESA": "ATI"}
    assert imagens.nome_arquivo_foto(registro) == "Fulano - ATI.png"


def test_nome_arquivo_foto_sem_empresa_nenhuma():
    registro = {"NOME": "Fulano"}
    assert imagens.nome_arquivo_foto(registro) == "Fulano.png"


def test_nome_arquivo_foto_sanitiza_caracteres_invalidos():
    registro = {"NOME": 'Fulano: "Teste"/Silva', "_EMPRESA_SIGLA": "TO"}
    nome = imagens.nome_arquivo_foto(registro)
    assert '"' not in nome
    assert ":" not in nome
    assert "/" not in nome
    assert nome.endswith(".png")


# ============================================================================
# redimensionar_para_bytes_png
# ============================================================================

def test_redimensionar_para_bytes_png_reduz_quando_maior_que_limite(qapp, tmp_path):
    pixmap = QPixmap(800, 600)
    pixmap.fill(Qt.blue)
    caminho = tmp_path / "grande.png"
    pixmap.save(str(caminho), "PNG")

    resultado = imagens.redimensionar_para_bytes_png(str(caminho), tamanho_max=256)
    assert resultado is not None
    reduzido = QPixmap()
    reduzido.loadFromData(resultado)
    assert reduzido.width() <= 256
    assert reduzido.height() <= 256


def test_redimensionar_para_bytes_png_mantem_quando_menor_que_limite(qapp, tmp_path):
    pixmap = QPixmap(50, 50)
    pixmap.fill(Qt.green)
    caminho = tmp_path / "pequena.png"
    pixmap.save(str(caminho), "PNG")

    resultado = imagens.redimensionar_para_bytes_png(str(caminho), tamanho_max=256)
    reduzido = QPixmap()
    reduzido.loadFromData(resultado)
    assert reduzido.width() == 50
    assert reduzido.height() == 50


def test_redimensionar_para_bytes_png_arquivo_invalido_devolve_none(qapp, tmp_path):
    caminho = tmp_path / "nao_e_imagem.txt"
    caminho.write_text("isso nao e uma imagem")
    assert imagens.redimensionar_para_bytes_png(str(caminho), tamanho_max=256) is None


# ============================================================================
# pixmap_circular
# ============================================================================

def test_pixmap_circular_devolve_pixmap_do_tamanho_pedido(qapp):
    dados = _png_bytes(qapp, 40, 40)
    resultado = imagens.pixmap_circular(dados, tamanho=30)
    assert resultado is not None
    assert resultado.width() == 30
    assert resultado.height() == 30


def test_pixmap_circular_bytes_invalidos_devolve_none(qapp):
    assert imagens.pixmap_circular(b"isso nao e um png", tamanho=30) is None


# ============================================================================
# salvar_fotos_via_dialogo
# ============================================================================

def test_salvar_fotos_via_dialogo_sem_ninguem_com_foto_mostra_erro(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox, QWidget

    chamou = {}
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: chamou.setdefault("erro", True) or QMessageBox.Ok))
    imagens.salvar_fotos_via_dialogo(QWidget(), [{"NOME": "Sem Foto"}])
    assert chamou.get("erro") is True


def test_salvar_fotos_via_dialogo_uma_foto_grava_arquivo_unico(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QWidget

    dados = _png_bytes(qapp)
    destino = tmp_path / "saida.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    imagens.salvar_fotos_via_dialogo(QWidget(), [{"NOME": "Fulano", "FOTO": dados}])
    assert destino.read_bytes() == dados


def test_salvar_fotos_via_dialogo_varias_fotos_grava_zip(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QWidget

    dados_a = _png_bytes(qapp, cor=Qt.red)
    dados_b = _png_bytes(qapp, cor=Qt.blue)
    destino = tmp_path / "saida.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    registros = [
        {"NOME": "Ana", "_EMPRESA_SIGLA": "TO", "FOTO": dados_a},
        {"NOME": "Bruno", "_EMPRESA_SIGLA": "RJ", "FOTO": dados_b},
        {"NOME": "Sem Foto"},
    ]
    imagens.salvar_fotos_via_dialogo(QWidget(), registros)

    with zipfile.ZipFile(destino) as zf:
        nomes = zf.namelist()
        assert "Ana - TO.png" in nomes
        assert "Bruno - RJ.png" in nomes
        assert len(nomes) == 2
        assert zf.read("Ana - TO.png") == dados_a


def test_salvar_fotos_via_dialogo_nomes_duplicados_nao_colidem(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QWidget

    dados_a = _png_bytes(qapp, cor=Qt.red)
    dados_b = _png_bytes(qapp, cor=Qt.blue)
    destino = tmp_path / "saida.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    registros = [
        {"NOME": "Fulano", "_EMPRESA_SIGLA": "TO", "FOTO": dados_a},
        {"NOME": "Fulano", "_EMPRESA_SIGLA": "TO", "FOTO": dados_b},
    ]
    imagens.salvar_fotos_via_dialogo(QWidget(), registros)

    with zipfile.ZipFile(destino) as zf:
        nomes = sorted(zf.namelist())
        assert nomes == ["Fulano - TO (2).png", "Fulano - TO.png"]
