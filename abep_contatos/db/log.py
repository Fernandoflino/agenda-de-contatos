"""
Este arquivo cuida do "historico de alteracoes" do programa: toda vez que
alguem cria, edita ou apaga alguma coisa (um contato, uma empresa, uma
tabela nova, um campo), uma linha e adicionada aqui contando o que aconteceu,
quando e quem fez.

Isso substitui a antiga aba "CONFIGURACOES" do sistema em planilha, so que
agora guardado numa tabela de banco de dados (app_log) em vez de uma aba de
Excel/Google Sheets.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from .schema import APP_LOG


def log_change(conn: sqlite3.Connection, usuario: str, tabela: str, acao: str, detalhes: str = "") -> None:
    """Registra uma linha no historico. Chamado sempre que algo muda no banco.

    Exemplo de uso: log_change(conn, "maria", "PESSOAS", "Criar registro", "Joao da Silva")
    """
    conn.execute(
        f"INSERT INTO {APP_LOG} (data_hora, usuario, tabela, acao, detalhes) VALUES (?, ?, ?, ?, ?)",
        (
            # Guardamos a data/hora em UTC e num formato padrao (ISO 8601)
            # porque isso ordena certinho e nao depende do fuso horario de
            # quem esta olhando -- a tela pode formatar como quiser depois.
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            usuario or "desconhecido",
            tabela,
            acao,
            detalhes or "",
        ),
    )
    conn.commit()


def historico(conn: sqlite3.Connection, limite: int = 200) -> list[dict]:
    """Devolve as ultimas alteracoes (mais recente primeiro), pra mostrar
    numa tela de "Historico" dentro do programa."""
    cur = conn.execute(
        f"SELECT data_hora, usuario, tabela, acao, detalhes FROM {APP_LOG} ORDER BY id DESC LIMIT ?",
        (limite,),
    )
    colunas = [d[0] for d in cur.description]
    return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def historico_do_registro(conn: sqlite3.Connection, tabela: str, registro_id: int, limite: int = 50) -> list[dict]:
    """As alteracoes do historico geral que falam de UM registro especifico
    (por ex., pro painel de detalhes de um contato) -- usada pra tela mostrar
    so "o que aconteceu com ESTE contato", em vez do historico inteiro da
    tabela toda.

    Funciona procurando "ID <numero>" dentro do texto de detalhes que
    update_record()/delete_record() ja gravam -- o "\\b" (borda de palavra)
    evita que "ID 1" bata por engano com "ID 12". Alteracoes muito antigas
    (de antes desse padrao existir) podem nao aparecer aqui; isso nao afeta
    o historico GERAL (log.historico()), que continua mostrando tudo.
    """
    padrao = re.compile(rf"\bID {registro_id}\b")
    cur = conn.execute(
        f"SELECT data_hora, usuario, tabela, acao, detalhes FROM {APP_LOG} WHERE tabela = ? ORDER BY id DESC",
        (tabela,),
    )
    colunas = [d[0] for d in cur.description]

    resultado = []
    for linha in cur.fetchall():
        item = dict(zip(colunas, linha))
        if padrao.search(item.get("detalhes") or ""):
            resultado.append(item)
            if len(resultado) >= limite:
                break
    return resultado
