"""Testes do fluxo de abertura de banco em main.py, com foco no bloqueio por
trava (db/lock.py) quando outra sessao ja esta com o banco aberto -- ver
ui/dialogs.py::banco_em_uso_dialog. Nao mexe em Qt de verdade: troca
LauncherDialog e banco_em_uso_dialog por versoes falsas que devolvem
respostas pre-definidas, em vez de esperar clique de alguem."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from PySide6.QtWidgets import QDialog

import main as main_mod
from db.lock import InfoLock
from ui.dialogs import CANCELAR, FORCAR_ABERTURA, TENTAR_NOVAMENTE
from ui.launcher_dialog import MODO_ABRIR


def _info_lock():
    return InfoLock(
        maquina="PC-OUTRO",
        usuario_os="fulano",
        aberto_em="2024-01-01T00:00:00+00:00",
        ultima_atividade="2024-01-01T00:00:00+00:00",
    )


class _AdquirirStub:
    """Substitui lock.adquirir: devolve as respostas informadas, em ordem,
    uma por chamada, e guarda se cada chamada pediu `forcar=True`."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas_forcar = []

    def __call__(self, caminho, forcar=False):
        self.chamadas_forcar.append(forcar)
        return self.respostas.pop(0)


def _launcher_factory(specs):
    """Substitui a classe LauncherDialog: cada instanciacao consome o
    proximo item de `specs` (aceitar?, caminho_escolhido)."""
    fila = list(specs)

    def factory(*args, **kwargs):
        aceitar, caminho = fila.pop(0)
        return SimpleNamespace(
            exec=lambda: QDialog.Accepted if aceitar else QDialog.Rejected,
            modo=MODO_ABRIR,
            caminho_escolhido=caminho,
        )

    return factory


def _preparar(monkeypatch, launcher_specs, respostas_lock, respostas_dialogo=None):
    monkeypatch.setattr(main_mod, "LauncherDialog", _launcher_factory(launcher_specs))
    monkeypatch.setattr(main_mod.connection, "conectar", lambda caminho: sqlite3.connect(":memory:"))
    monkeypatch.setattr(main_mod.app_config, "registrar_recente", lambda caminho: None)

    stub_adquirir = _AdquirirStub(respostas_lock)
    monkeypatch.setattr(main_mod.lock, "adquirir", stub_adquirir)

    chamadas_dialogo = []
    if respostas_dialogo is not None:
        fila_dialogo = list(respostas_dialogo)

        def fake_dialogo(parent, info):
            chamadas_dialogo.append(info)
            return fila_dialogo.pop(0)

        monkeypatch.setattr(main_mod, "banco_em_uso_dialog", fake_dialogo)

    return stub_adquirir, chamadas_dialogo


def test_abre_direto_quando_trava_esta_livre(monkeypatch, tmp_path):
    caminho = str(tmp_path / "teste.abepdb")
    _stub, chamadas_dialogo = _preparar(
        monkeypatch, launcher_specs=[(True, caminho)], respostas_lock=[None],
    )

    conn, caminho_devolvido, eh_novo = main_mod._escolher_e_abrir_banco()

    assert conn is not None
    assert caminho_devolvido == caminho
    assert eh_novo is False
    assert chamadas_dialogo == []  # trava livre -- nunca precisou mostrar o dialogo
    conn.close()


def test_cancelar_fecha_conexao_e_nao_abre(monkeypatch, tmp_path):
    caminho = str(tmp_path / "teste.abepdb")
    _stub, chamadas_dialogo = _preparar(
        monkeypatch,
        launcher_specs=[(True, caminho), (False, None)],  # 2a vez: desiste da tela inicial
        respostas_lock=[_info_lock()],
        respostas_dialogo=[CANCELAR],
    )

    conn, caminho_devolvido, eh_novo = main_mod._escolher_e_abrir_banco()

    assert conn is None
    assert caminho_devolvido is None
    assert len(chamadas_dialogo) == 1


def test_tentar_novamente_reconsulta_trava_ate_ficar_livre(monkeypatch, tmp_path):
    caminho = str(tmp_path / "teste.abepdb")
    stub, chamadas_dialogo = _preparar(
        monkeypatch,
        launcher_specs=[(True, caminho)],
        respostas_lock=[_info_lock(), None],  # 1a chamada: em uso; 2a: livre
        respostas_dialogo=[TENTAR_NOVAMENTE],
    )

    conn, caminho_devolvido, eh_novo = main_mod._escolher_e_abrir_banco()

    assert conn is not None
    assert len(chamadas_dialogo) == 1
    assert stub.chamadas_forcar == [False, False]  # nunca forcou
    conn.close()


def test_forcar_abertura_chama_adquirir_com_forcar_true(monkeypatch, tmp_path):
    caminho = str(tmp_path / "teste.abepdb")
    stub, chamadas_dialogo = _preparar(
        monkeypatch,
        launcher_specs=[(True, caminho)],
        respostas_lock=[_info_lock(), None],
        respostas_dialogo=[FORCAR_ABERTURA],
    )

    conn, caminho_devolvido, eh_novo = main_mod._escolher_e_abrir_banco()

    assert conn is not None
    assert len(chamadas_dialogo) == 1
    assert stub.chamadas_forcar == [False, True]  # a 2a chamada forcou de verdade
    conn.close()
