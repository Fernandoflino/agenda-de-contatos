"""
PONTO DE PARTIDA do programa -- e este arquivo que roda quando alguem abre o
"Painel de Contatos" (seja digitando "python main.py" durante o
desenvolvimento, seja clicando no atalho criado pelo instalador).

O fluxo geral, do inicio ao fim, e:

1. Mostra a tela inicial (LauncherDialog) pra escolher/criar um arquivo de
   banco de dados (.abepdb).
2. Se o banco acabou de ser CRIADO agora, oferece importar uma planilha
   .xlsx. Depois disso -- e tambem ao ABRIR um banco ja existente que por
   algum motivo ainda nao tenha nenhum usuario cadastrado (por exemplo, se
   o programa foi fechado no meio da criacao do primeiro usuario da vez
   anterior) -- obriga a criar o primeiro usuario administrativo antes de
   continuar. Isso garante que nunca se chega na tela de login sem
   nenhum jeito de entrar no banco.
3. Mostra a tela de login.
4. Se o login der certo, abre a janela principal do programa.
5. Se o usuario clicar em "Trocar de banco de dados" dentro da janela
   principal, o programa fecha essa janela e volta pro passo 1 -- sem
   precisar reabrir o programa inteiro.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from atualizacao import VerificadorAtualizacao
from config import app_config
from db import connection, lock
from ui import primeiro_uso
from ui.dialogs import (
    baixar_e_instalar_atualizacao,
    confirmar_abrir_banco_em_uso,
    mostrar_erro,
    perguntar_atualizacao,
)
from ui.launcher_dialog import MODO_NOVO, LauncherDialog
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.theme import aplicar_tema
from versao import VERSAO


def _escolher_e_abrir_banco():
    """Mostra a tela inicial ate o usuario conseguir abrir/criar um banco
    com sucesso, ou desistir (fechando a tela). Devolve (conexao, caminho,
    eh_banco_novo) -- ou (None, None, False) se o usuario desistiu."""
    while True:
        launcher = LauncherDialog()
        if launcher.exec() != QDialog.Accepted:
            return None, None, False

        caminho = launcher.caminho_escolhido
        try:
            if launcher.modo == MODO_NOVO:
                conn = connection.criar_novo(caminho)
                eh_novo = True
            else:
                conn = connection.conectar(caminho)
                eh_novo = False
        except (FileNotFoundError, FileExistsError, OSError) as erro:
            mostrar_erro(None, str(erro), titulo="Nao foi possivel abrir o banco")
            continue  # volta pra tela inicial e deixa tentar de novo

        app_config.registrar_recente(caminho)

        # Avisa se outra sessao parece estar com esse banco aberto agora
        # (ver db/lock.py) -- so um aviso de "melhor esforco", nao impede
        # nada se o usuario decidir continuar mesmo assim.
        info_lock = lock.adquirir(caminho)
        if info_lock is not None:
            if not confirmar_abrir_banco_em_uso(None, info_lock):
                conn.close()
                continue
            lock.adquirir(caminho, forcar=True)

        return conn, caminho, eh_novo


def _tratar_atualizacao_disponivel(app: QApplication, info: dict) -> None:
    """Chamado quando o VerificadorAtualizacao acha uma versao mais nova --
    pergunta pro usuario se quer atualizar agora, respeitando a escolha de
    "nao perguntar de novo" salva na ultima vez."""
    if app_config.versao_ignorada() == info["versao"]:
        return

    quer_atualizar, ignorar = perguntar_atualizacao(None, VERSAO, info["versao"], info["notas"])
    if quer_atualizar:
        baixar_e_instalar_atualizacao(app, info["url_download"])
    elif ignorar:
        app_config.definir_versao_ignorada(info["versao"])


def main() -> int:
    app = QApplication(sys.argv)
    # "Fusion" e um estilo visual do Qt que parece bem mais atual do que o
    # padrao do Windows antigo -- e o ponto de partida sobre o qual o nosso
    # style.qss (ui/theme.py) desenha o resto da aparencia personalizada.
    app.setStyle("Fusion")

    # Checa se ha uma versao mais nova publicada no GitHub em paralelo com o
    # resto da abertura do programa (tela inicial, login etc.) -- sem
    # atrasar nada disso. `verificador` precisa continuar existindo ate a
    # checagem terminar, por isso fica guardado aqui (nao descartado).
    verificador = VerificadorAtualizacao()
    verificador.encontrada.connect(lambda info: _tratar_atualizacao_disponivel(app, info))
    verificador.iniciar()

    while True:
        conn, caminho, eh_novo = _escolher_e_abrir_banco()
        if conn is None:
            return 0  # usuario fechou a tela inicial sem escolher nada -- encerra o programa

        # A cor de destaque e o logotipo sao especificos de CADA banco de
        # dados (moram dentro do arquivo .abepdb) -- por isso o tema visual
        # e reaplicado toda vez que um banco diferente e aberto.
        aplicar_tema(app, conn)

        if eh_novo:
            primeiro_uso.oferecer_importacao_inicial(conn, None)

        # Chamado SEMPRE (nao so quando "eh_novo"): exigir_primeiro_usuario
        # nao faz nada se ja existir algum usuario, mas cria essa "rede de
        # seguranca" pra bancos que ficaram sem nenhum usuario por algum
        # imprevisto (ex.: o programa foi fechado no meio da criacao do
        # primeiro usuario) -- sem isso, o programa cairia direto na tela de
        # login sem ninguem conseguir entrar, sem nenhuma forma de perceber
        # ou corrigir isso pela propria interface.
        primeiro_uso.exigir_primeiro_usuario(conn, None)

        login = LoginDialog(conn)
        if login.exec() != QDialog.Accepted:
            conn.close()
            lock.liberar(caminho)
            continue  # usuario cancelou o login -- volta pra tela inicial

        janela = MainWindow(conn, login.usuario_logado, caminho)

        # "Trocar de banco de dados" fecha a janela principal SEM encerrar o
        # programa -- o loop de fora (este while) detecta isso e volta pra
        # tela inicial, como se o programa tivesse acabado de abrir.
        estado = {"trocar_banco": False}

        def _ao_pedir_troca():
            estado["trocar_banco"] = True
            janela.close()

        janela.trocar_banco_solicitado.connect(_ao_pedir_troca)
        janela.show()
        app.exec()

        conn.close()
        lock.liberar(caminho)
        if not estado["trocar_banco"]:
            return 0  # janela principal foi fechada normalmente -- encerra o programa


if __name__ == "__main__":
    sys.exit(main())
