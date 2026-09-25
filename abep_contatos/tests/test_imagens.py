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


def test_nome_arquivo_foto_usa_extensao_do_mime():
    registro = {"NOME": "Fulano"}
    assert imagens.nome_arquivo_foto(registro, mime="image/jpeg") == "Fulano.jpg"
    assert imagens.nome_arquivo_foto(registro, mime="image/png") == "Fulano.png"
    assert imagens.nome_arquivo_foto(registro, mime="image/bmp") == "Fulano.bmp"


def test_nome_arquivo_foto_mime_desconhecido_cai_pro_png():
    registro = {"NOME": "Fulano"}
    assert imagens.nome_arquivo_foto(registro, mime="application/octet-stream") == "Fulano.png"
    assert imagens.nome_arquivo_foto(registro, mime=None) == "Fulano.png"


# ============================================================================
# ler_bytes_originais
# ============================================================================

def test_ler_bytes_originais_devolve_bytes_crus_e_mime(qapp, tmp_path):
    dados = _png_bytes(qapp)
    caminho = tmp_path / "foto.png"
    caminho.write_bytes(dados)

    lidos, mime = imagens.ler_bytes_originais(str(caminho))
    assert lidos == dados  # byte a byte, sem nenhum reprocessamento
    assert mime == "image/png"


def test_ler_bytes_originais_reconhece_jpeg(qapp, tmp_path):
    caminho = tmp_path / "foto.jpg"
    caminho.write_bytes(b"conteudo qualquer")  # so o nome do arquivo importa aqui

    _, mime = imagens.ler_bytes_originais(str(caminho))
    assert mime == "image/jpeg"


# ============================================================================
# bytes_originais_do_registro
# ============================================================================

def test_bytes_originais_do_registro_prefere_foto_original(qapp):
    dados_originais = _png_bytes(qapp, cor=Qt.blue)
    dados_recorte = _png_bytes(qapp, cor=Qt.red)
    registro = {
        "FOTO": dados_recorte,
        "FOTO_MIME": "image/png",
        "FOTO_ORIGINAL": dados_originais,
        "FOTO_ORIGINAL_MIME": "image/jpeg",
    }
    dados, mime = imagens.bytes_originais_do_registro(registro)
    assert dados == dados_originais
    assert mime == "image/jpeg"


def test_bytes_originais_do_registro_cai_pro_recorte_em_registro_antigo(qapp):
    """Registro salvo ANTES do arquivo original ser guardado separado --
    so tem FOTO/FOTO_MIME, sem FOTO_ORIGINAL nenhum."""
    dados = _png_bytes(qapp)
    registro = {"FOTO": dados, "FOTO_MIME": "image/png"}
    resultado = imagens.bytes_originais_do_registro(registro)
    assert resultado == (dados, "image/png")


def test_bytes_originais_do_registro_sem_foto_nenhuma_devolve_none():
    assert imagens.bytes_originais_do_registro({"NOME": "Sem Foto"}) is None


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


def test_salvar_fotos_via_dialogo_baixa_o_original_nao_o_recorte(qapp, monkeypatch, tmp_path):
    """O download tem que ser o arquivo ORIGINAL (sem recorte/alteracao),
    nao o recorte circular usado so pra mostrar o avatar na tela."""
    from PySide6.QtWidgets import QFileDialog, QWidget

    dados_originais = b"bytes do arquivo original, sem processar"
    dados_recorte = _png_bytes(qapp)
    destino = tmp_path / "saida.jpg"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), "")))

    registro = {
        "NOME": "Fulano",
        "FOTO": dados_recorte,
        "FOTO_MIME": "image/png",
        "FOTO_ORIGINAL": dados_originais,
        "FOTO_ORIGINAL_MIME": "image/jpeg",
    }
    imagens.salvar_fotos_via_dialogo(QWidget(), [registro])

    assert destino.read_bytes() == dados_originais


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
