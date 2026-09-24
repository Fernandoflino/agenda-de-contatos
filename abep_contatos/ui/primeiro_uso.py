"""
Funcoes chamadas logo depois de CRIAR um banco de dados novo (nunca ao abrir
um ja existente): oferecer importar uma planilha .xlsx e, ao final, exigir a
criacao do primeiro usuario administrativo (ver primeiro_usuario_dialog.py).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from db import auth, importer
from ui.dialogs import mostrar_erro, mostrar_info
from ui.primeiro_usuario_dialog import PrimeiroUsuarioDialog


def oferecer_importacao_inicial(conn: sqlite3.Connection, parent: QWidget) -> None:
    resposta = QMessageBox.question(
        parent,
        "Importar dados existentes?",
        "Este é um banco novo. Deseja importar dados de uma planilha .xlsx agora\n"
        '(por exemplo, o arquivo "Presidentes - Mailing.xlsx")?',
    )
    if resposta != QMessageBox.Yes:
        return

    caminho, _ = QFileDialog.getOpenFileName(parent, "Escolher planilha para importar", "", "Planilhas Excel (*.xlsx)")
    if not caminho:
        return

    try:
        resumo = importer.importar_xlsx(conn, caminho, usuario="sistema")
    except Exception as erro:  # a planilha pode vir de qualquer lugar -- qualquer formato inesperado vira aviso, nao crash
        mostrar_erro(parent, f"Nao foi possivel importar essa planilha:\n{erro}")
        return

    linhas = "\n".join(f"- {aba}: {qtd} linha(s)" for aba, qtd in resumo.linhas_por_aba.items())
    mensagem = f"Importação concluída:\n\n{linhas}" if linhas else "Nenhum dado foi encontrado para importar."
    if resumo.avisos:
        mensagem += "\n\nAvisos:\n" + "\n".join(f"- {a}" for a in resumo.avisos)
    mostrar_info(parent, mensagem)


def exigir_primeiro_usuario(conn: sqlite3.Connection, parent: QWidget) -> None:
    if auth.existe_algum_usuario(conn):
        return
    dialogo = PrimeiroUsuarioDialog(conn, parent=parent)
    dialogo.exec()
