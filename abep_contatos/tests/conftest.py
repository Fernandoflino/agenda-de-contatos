import os
import sqlite3

import pytest

# Faz o Qt desenhar as janelas "no vazio" (sem monitor) -- precisa ser
# definido ANTES de qualquer import do PySide6, senao nao tem efeito.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from db import schema


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def sem_caixas_de_dialogo_bloqueantes(monkeypatch):
    """Impede que uma janela de aviso/erro real (QMessageBox) trave um teste
    esperando por um clique que nunca vai acontecer -- sem uma pessoa de
    verdade na tela (rodando em modo "offscreen"), essas janelas ficariam
    penduradas pra sempre. Os testes que chamam codigo que pode abrir uma
    dessas janelas continuam funcionando normalmente; so nao ficam
    esperando confirmacao alguma."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))


@pytest.fixture()
def conn():
    """Banco SQLite em memoria com o schema inicial ja criado."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    schema.criar_schema_inicial(c)
    yield c
    c.close()
