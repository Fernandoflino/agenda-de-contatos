"""
Checagem e instalacao de novas versoes do programa, direto pela tela inicial.

Pra que serve: o programa e distribuido como um instalador (.exe) que cada
usuario baixa e roda na mao -- sem isso, ninguem descobre que existe uma
versao nova a nao ser que alguem avise. Este arquivo consulta a pagina de
"Releases" do projeto no GitHub (publica, de graca, sem precisar de servidor
proprio) pra saber se a versao publicada la e mais nova do que a VERSAO
deste computador -- e, se for, baixa o instalador novo e abre ele.

A logica de rede fica separada da tela (ui/dialogs.py) pra poder ser testada
sem precisar de conexao de verdade nem da interface grafica rodando -- ver
tests/test_atualizacao.py.
"""
from __future__ import annotations

import json
import re
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from versao import VERSAO

REPOSITORIO = "Fernandoflino/agenda-de-contatos"
URL_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
TIMEOUT_CHECAGEM_SEGUNDOS = 5
TIMEOUT_DOWNLOAD_SEGUNDOS = 30
TAMANHO_BLOCO = 256 * 1024

_CABECALHOS = {
    "User-Agent": "PainelDeContatosABEPTIC",
    "Accept": "application/vnd.github+json",
}


def _versao_para_tupla(versao: str) -> tuple[int, ...]:
    numeros = re.findall(r"\d+", versao)
    return tuple(int(n) for n in numeros) if numeros else (0,)


def versao_e_mais_nova(atual: str, remota: str) -> bool:
    """Compara duas strings de versao tipo "0.11.0" -- devolve True se
    `remota` for maior que `atual`."""
    return _versao_para_tupla(remota) > _versao_para_tupla(atual)


def buscar_info_atualizacao() -> Optional[dict]:
    """Consulta a ultima release publicada no GitHub. Devolve um dicionario
    com "versao", "notas" e "url_download" se ela for mais nova que a VERSAO
    atual, ou None em qualquer outro caso (sem internet, API fora do ar,
    resposta inesperada, ou a versao remota nao ser mais nova).

    Nunca levanta excecao -- a checagem tem que falhar em silencio, sem
    atrapalhar quem esta abrindo o programa offline.
    """
    req = urllib.request.Request(URL_ULTIMA_RELEASE, headers=_CABECALHOS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_CHECAGEM_SEGUNDOS) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    if not isinstance(dados, dict):
        return None

    tag = dados.get("tag_name") or ""
    versao_remota = tag.lstrip("vV")
    if not versao_remota or not versao_e_mais_nova(VERSAO, versao_remota):
        return None

    assets = dados.get("assets") or []
    url_download = next(
        (a.get("browser_download_url") for a in assets if str(a.get("name", "")).lower().endswith(".exe")),
        None,
    )
    if not url_download:
        return None

    return {
        "versao": versao_remota,
        "notas": dados.get("body") or "",
        "url_download": url_download,
    }


def baixar_instalador(url: str, ao_progresso: Optional[Callable[[int, int], None]] = None) -> Path:
    """Baixa o instalador em blocos pra uma pasta temporaria, chamando
    `ao_progresso(bytes_lidos, bytes_totais)` a cada bloco (bytes_totais
    pode vir 0 se o servidor nao informar o tamanho). Devolve o caminho do
    arquivo baixado."""
    destino = Path(tempfile.gettempdir()) / "PainelDeContatosSetup.exe"
    req = urllib.request.Request(url, headers=_CABECALHOS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_DOWNLOAD_SEGUNDOS) as resp:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        lido = 0
        with open(destino, "wb") as arquivo:
            while True:
                bloco = resp.read(TAMANHO_BLOCO)
                if not bloco:
                    break
                arquivo.write(bloco)
                lido += len(bloco)
                if ao_progresso:
                    ao_progresso(lido, total)
    return destino


class VerificadorAtualizacao(QObject):
    """Roda `buscar_info_atualizacao()` numa thread separada (pra nao travar
    a interface) e emite `encontrada` na thread principal, ja que sinais do
    Qt sao seguros de emitir entre threads."""

    encontrada = Signal(dict)

    def iniciar(self) -> None:
        threading.Thread(target=self._verificar, daemon=True).start()

    def _verificar(self) -> None:
        info = buscar_info_atualizacao()
        if info:
            self.encontrada.emit(info)


class BaixadorAtualizacao(QObject):
    """Baixa o instalador numa thread separada, reportando progresso e
    resultado pra thread principal via sinais."""

    progresso = Signal(int, int)
    concluido = Signal(str)
    falhou = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def iniciar(self) -> None:
        threading.Thread(target=self._baixar, daemon=True).start()

    def _baixar(self) -> None:
        try:
            caminho = baixar_instalador(self._url, ao_progresso=lambda lido, total: self.progresso.emit(lido, total))
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            self.falhou.emit(str(erro))
            return
        self.concluido.emit(str(caminho))
