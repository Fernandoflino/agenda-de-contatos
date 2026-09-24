"""
Este arquivo tem "caixinhas de dialogo" pequenas e reaproveitaveis, usadas em
varias telas do programa: confirmar uma exclusao, mostrar uma mensagem de
erro, mostrar um aviso simples. Em vez de escrever esse codigo repetido em
cada tela, ele fica centralizado aqui.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QMessageBox, QWidget


def confirmar_exclusao(parent: QWidget, rotulo: str, tipo: str = "registro") -> bool:
    """Pergunta "tem certeza?" antes de excluir alguma coisa, SEMPRE citando
    o nome/identificacao do que sera excluido (em vez de uma mensagem
    generica tipo "Excluir isso?") -- isso deixa claro pro usuario o que
    exatamente vai sumir, evitando exclusoes por engano.

    Devolve True se o usuario confirmou, False se cancelou.
    """
    resposta = QMessageBox.question(
        parent,
        "Confirmar exclusão",
        f'Excluir {tipo} "{rotulo}"? Essa ação não pode ser desfeita.',
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,  # o botao "Nao" comeca selecionado, pra um Enter acidental nao excluir nada
    )
    return resposta == QMessageBox.Yes


def mostrar_erro(parent: QWidget, mensagem: str, titulo: str = "Erro") -> None:
    """Mostra uma janela de erro simples com a mensagem informada."""
    QMessageBox.critical(parent, titulo, mensagem)


def mostrar_info(parent: QWidget, mensagem: str, titulo: str = "Aviso") -> None:
    """Mostra uma janela de aviso/informacao simples."""
    QMessageBox.information(parent, titulo, mensagem)


def perguntar_atualizacao(parent: QWidget, versao_atual: str, versao_nova: str, notas: str) -> tuple[bool, bool]:
    """Mostra o aviso de que ha uma versao nova disponivel, com as notas da
    release escondidas atras de "Detalhes..." e uma caixinha pra nao
    perguntar de novo sobre essa versao especifica.

    Devolve (quer_atualizar, ignorar_esta_versao).
    """
    caixa = QMessageBox(parent)
    caixa.setIcon(QMessageBox.Information)
    caixa.setWindowTitle("Nova versão disponível")
    caixa.setText(
        f"Uma nova versão do Painel de Contatos está disponível: {versao_nova}\n"
        f"(você está usando a versão {versao_atual})."
    )
    if notas:
        caixa.setDetailedText(notas)

    checkbox = QCheckBox("Não perguntar novamente sobre esta versão")
    caixa.setCheckBox(checkbox)

    botao_atualizar = caixa.addButton("Atualizar agora", QMessageBox.AcceptRole)
    caixa.addButton("Agora não", QMessageBox.RejectRole)
    caixa.setDefaultButton(botao_atualizar)

    caixa.exec()
    return caixa.clickedButton() is botao_atualizar, checkbox.isChecked()
