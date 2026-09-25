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

Esta VERSAO tambem e o que o aviso de atualizacao (ver atualizacao.py)
compara com a versao publicada no GitHub pra saber se deve avisar o
usuario. Pra publicar uma versao nova de verdade (nao so editar este
arquivo), sao 3 passos: 1) aumentar VERSAO aqui, 2) aumentar MyAppVersion
em packaging/installer.iss pro mesmo numero, 3) gerar o instalador (ver
README.md) e publicar uma Release no GitHub com tag "vX.Y.Z" (mesmo
numero) e o instalador anexado como asset -- sem esse ultimo passo,
ninguem recebe aviso nenhum.
"""
VERSAO = "0.11.11"
VERSAO_DATA = "2026-09-25"
