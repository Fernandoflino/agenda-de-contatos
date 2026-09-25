"""
Helpers de IMAGEM compartilhados entre telas que lidam com foto (o
logotipo do painel em ui/settings_dialog.py, e a foto de um contato em
ui/record_form_dialog.py / ui/avatar.py / ui/lista_registros_view.py).

Tudo aqui usa so PySide6 (QPixmap/QPainter/QBuffer) -- o projeto nao tem
Pillow instalado, e redimensionar/recortar/serializar imagem em PNG da pra
fazer inteiramente com Qt, sem precisar de uma dependencia nova.
"""
from __future__ import annotations

import re
import zipfile

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget

from ui.dialogs import mostrar_erro, mostrar_info

_CARACTERES_INVALIDOS_ARQUIVO = re.compile(r'[<>:"/\\|?*]')


def pixmap_para_bytes_png(pixmap: QPixmap, tamanho_max: int) -> bytes:
    """Redimensiona um QPixmap (se for maior que `tamanho_max`) e devolve
    os bytes prontos no formato PNG, pra gravar direto numa coluna BLOB do
    banco de dados."""
    if pixmap.width() > tamanho_max or pixmap.height() > tamanho_max:
        pixmap = pixmap.scaled(tamanho_max, tamanho_max, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(dados)


def redimensionar_para_bytes_png(caminho_imagem: str, tamanho_max: int) -> bytes | None:
    """Le um arquivo de imagem do disco e devolve os bytes redimensionados
    em PNG (ver pixmap_para_bytes_png) -- devolve None se o arquivo nao for
    uma imagem valida."""
    pixmap = QPixmap(caminho_imagem)
    if pixmap.isNull():
        return None
    return pixmap_para_bytes_png(pixmap, tamanho_max)


def pixmap_circular(dados_png: bytes, tamanho: int) -> QPixmap | None:
    """Carrega os bytes de uma imagem e devolve um QPixmap quadrado
    (`tamanho x tamanho`), cobrindo o quadrado inteiro (corta o excesso do
    centro) e recortado em circulo -- usado tanto no avatar pequeno quanto
    no preview do formulario de contato. Devolve None se os bytes nao forem
    uma imagem valida."""
    original = QPixmap()
    if not original.loadFromData(dados_png):
        return None

    cobertura = original.scaled(tamanho, tamanho, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (cobertura.width() - tamanho) // 2
    y = (cobertura.height() - tamanho) // 2
    recortado = cobertura.copy(x, y, tamanho, tamanho)

    resultado = QPixmap(tamanho, tamanho)
    resultado.fill(Qt.transparent)
    pintor = QPainter(resultado)
    pintor.setRenderHint(QPainter.Antialiasing)
    caminho = QPainterPath()
    caminho.addEllipse(QRectF(0, 0, tamanho, tamanho))
    pintor.setClipPath(caminho)
    pintor.drawPixmap(0, 0, recortado)
    pintor.end()
    return resultado


def nome_arquivo_foto(registro: dict) -> str:
    """Monta o nome de arquivo padrao pra baixar a foto de um contato:
    "{Nome} - {SIGLA_EMPRESA}-{UF}.png" -- se faltar a sigla da empresa ou a
    UF (empresa sem essas colunas preenchidas), omite so esse pedaco em vez
    de escrever "None" no nome."""
    nome = str(registro.get("NOME") or "Sem nome").strip()
    sigla_empresa = str(registro.get("_EMPRESA_SIGLA_EMPRESA") or "").strip()
    uf = str(registro.get("_EMPRESA_SIGLA") or "").strip()

    sufixo = "-".join(p for p in (sigla_empresa, uf) if p)
    base = f"{nome} - {sufixo}" if sufixo else nome
    base = _CARACTERES_INVALIDOS_ARQUIVO.sub(" ", base).strip()
    return f"{base}.png"


def _evitar_duplicata(nome: str, usados: dict[str, int]) -> str:
    contagem = usados.get(nome, 0) + 1
    usados[nome] = contagem
    if contagem == 1:
        return nome
    base, ponto, extensao = nome.rpartition(".")
    return f"{base} ({contagem}).{extensao}" if ponto else f"{nome} ({contagem})"


def salvar_fotos_via_dialogo(parent: QWidget, registros: list[dict]) -> None:
    """Baixa as fotos dos `registros` informados que TEM foto -- um arquivo
    .png direto se for so 1, ou um .zip se for mais de 1. Usado tanto pela
    acao em massa "Baixar fotos" (so os selecionados) quanto pelo botao de
    fotos na tela de Exportacao (todas, ou por categoria)."""
    com_foto = [r for r in registros if r.get("FOTO")]
    if not com_foto:
        mostrar_erro(parent, "Nenhum dos registros tem foto cadastrada.")
        return

    usados: dict[str, int] = {}
    arquivos = [(_evitar_duplicata(nome_arquivo_foto(r), usados), r["FOTO"]) for r in com_foto]

    try:
        if len(arquivos) == 1:
            nome_sugerido, dados = arquivos[0]
            caminho, _ = QFileDialog.getSaveFileName(parent, "Salvar foto como", nome_sugerido, "Imagem PNG (*.png)")
            if not caminho:
                return
            with open(caminho, "wb") as arquivo:
                arquivo.write(dados)
        else:
            caminho, _ = QFileDialog.getSaveFileName(parent, "Salvar fotos como", "fotos.zip", "Arquivo ZIP (*.zip)")
            if not caminho:
                return
            with zipfile.ZipFile(caminho, "w") as zf:
                for nome, dados in arquivos:
                    zf.writestr(nome, dados)
    except OSError as erro:
        mostrar_erro(parent, str(erro))
        return

    mostrar_info(parent, f"{len(arquivos)} foto(s) salva(s).")
