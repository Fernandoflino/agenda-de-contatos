"""
Este arquivo tem "caixinhas de dialogo" pequenas e reaproveitaveis, usadas em
varias telas do programa: confirmar uma exclusao, mostrar uma mensagem de
erro, mostrar um aviso simples. Em vez de escrever esse codigo repetido em
cada tela, ele fica centralizado aqui.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QProgressDialog, QWidget

from atualizacao import BaixadorAtualizacao, abrir_instalador
from db.lock import InfoLock

# Pagina de releases no GitHub -- alternativa pra quem preferir baixar e
# instalar o .exe manualmente, em vez do download automatico daqui de dentro
# (ver botao "Baixar manualmente..." em perguntar_atualizacao()).
_URL_RELEASES = "https://github.com/Fernandoflino/agenda-de-contatos/releases"


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


TENTAR_NOVAMENTE = "tentar_novamente"
CANCELAR = "cancelar"
FORCAR_ABERTURA = "forcar_abertura"


def banco_em_uso_dialog(parent: QWidget, info: InfoLock) -> str:
    """Avisa que este banco esta aberto em outra sessao (mesma trava .lock
    ainda "viva", ver db/lock.py) e BLOQUEIA a abertura por padrao -- ao
    contrario de um simples aviso, nao existe um jeito casual de "abrir
    mesmo assim".

    Isso existe porque o banco costuma ficar numa pasta do OneDrive (nao
    numa pasta de rede de verdade): se duas pessoas escreverem nele ao mesmo
    tempo, o OneDrive nao sabe fazer o merge de um arquivo binario e cria
    copias duplicadas com o nome do computador (ex.: "contatos-PC-X.abepdb").
    Bloquear a abertura evita que isso aconteca -- so uma pessoa mexe no
    banco por vez.

    Devolve TENTAR_NOVAMENTE, CANCELAR ou FORCAR_ABERTURA (esta ultima so
    depois de uma segunda confirmacao explicita, pra emergencias tipo uma
    trava presa por bug)."""
    try:
        desde = datetime.fromisoformat(info.aberto_em).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        desde = "algum momento recente"

    caixa = QMessageBox(parent)
    caixa.setIcon(QMessageBox.Warning)
    caixa.setWindowTitle("Banco em uso")
    caixa.setText(
        f'Este banco está sendo usado agora no computador "{info.maquina}" '
        f'(usuário "{info.usuario_os}") desde {desde}.\n\n'
        "Pra evitar duplicar o arquivo no OneDrive, espere essa pessoa "
        "terminar e feche o programa dela antes de tentar de novo."
    )
    botao_tentar = caixa.addButton("Tentar novamente", QMessageBox.AcceptRole)
    caixa.addButton("Cancelar", QMessageBox.RejectRole)
    botao_forcar = caixa.addButton("Forçar abertura...", QMessageBox.DestructiveRole)
    caixa.setDefaultButton(botao_tentar)
    caixa.exec()

    if caixa.clickedButton() is botao_forcar:
        confirmacao = QMessageBox.warning(
            parent,
            "Forçar abertura",
            (
                "Se a outra pessoa realmente ainda estiver com esse banco "
                "aberto, forçar a abertura agora pode fazer o OneDrive "
                "duplicar o arquivo (cada um salvando numa cópia diferente, "
                "sem juntar as alterações depois).\n\n"
                "Só continue se tiver certeza de que a outra sessão travou "
                "ou foi encerrada sem fechar direito. Forçar mesmo assim?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmacao == QMessageBox.Yes:
            return FORCAR_ABERTURA
        return CANCELAR

    if caixa.clickedButton() is botao_tentar:
        return TENTAR_NOVAMENTE
    return CANCELAR


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
    botao_manual = caixa.addButton("Baixar manualmente...", QMessageBox.ActionRole)
    caixa.addButton("Agora não", QMessageBox.RejectRole)
    caixa.setDefaultButton(botao_atualizar)

    caixa.exec()
    if caixa.clickedButton() is botao_manual:
        # Abre a pagina de releases no navegador -- quem preferir baixar e
        # rodar o instalador na mao (em vez do download automatico daqui de
        # dentro) fica livre pra fazer isso, sem depender da rede/HTTP do
        # proprio programa.
        QDesktopServices.openUrl(QUrl(_URL_RELEASES))
    return caixa.clickedButton() is botao_atualizar, checkbox.isChecked()


def baixar_e_instalar_atualizacao(app: QApplication, url_download: str, parent: QWidget = None) -> None:
    """Baixa o instalador da nova versao mostrando uma barra de progresso e,
    ao terminar, abre o instalador e fecha o programa (precisa fechar antes
    porque o instalador nao consegue sobrescrever os arquivos enquanto o
    programa ainda esta rodando)."""
    progresso = QProgressDialog("Baixando atualização...", "", 0, 0, parent)
    progresso.setWindowTitle("Atualizando")
    progresso.setCancelButton(None)
    progresso.setMinimumDuration(0)

    baixador = BaixadorAtualizacao(url_download)

    def _ao_progredir(lido: int, total: int) -> None:
        progresso.setMaximum(total)
        progresso.setValue(lido)

    def _ao_concluir(caminho_instalador: str) -> None:
        progresso.close()
        try:
            abrir_instalador(caminho_instalador)
        except OSError as erro:
            mostrar_erro(
                parent,
                "O instalador foi baixado, mas não foi possível abri-lo "
                f"({erro}).\n\n"
                "Isso costuma acontecer quando o antivírus bloqueia ou remove "
                "o arquivo baixado por ele não ter assinatura digital -- "
                "confira a quarentena/histórico do seu antivírus.",
            )
            return
        app.quit()

    def _ao_falhar(mensagem: str) -> None:
        progresso.close()
        mostrar_erro(parent, f"Não foi possível baixar a atualização:\n{mensagem}")

    baixador.progresso.connect(_ao_progredir)
    baixador.concluido.connect(_ao_concluir)
    baixador.falhou.connect(_ao_falhar)
    baixador.iniciar()
    progresso.exec()
