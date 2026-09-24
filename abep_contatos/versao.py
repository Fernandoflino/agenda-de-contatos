"""
Guarda o numero da versao do programa -- mostrado no rodape da tela inicial
e da janela principal (ver ui/launcher_dialog.py e ui/main_window.py).

Pra que serve: como o programa ainda roda direto do codigo-fonte (nao
empacotado num instalador), o Python NAO recarrega os arquivos sozinho
enquanto o programa esta aberto -- se voce editar o codigo com o programa
ja aberto, ele continua rodando a versao ANTIGA ate ser fechado e aberto de
novo. Mostrar a versao na tela ajuda a confirmar rapidinho se a janela
aberta ja e a mais recente ou se precisa reiniciar o programa.

Bump manual: aumente este numero (e o comentario de VERSAO_DATA) toda vez
que um conjunto de mudancas relevante for concluido.
"""
VERSAO = "0.11.0"
VERSAO_DATA = "2026-09-22"
