"""
Este arquivo guarda ANOTACOES LIVRES por registro -- um bloco de texto que
quem estiver usando o programa pode escrever sobre um contato/empresa
especifico (ex.: "prefere ser contatado por WhatsApp", "confirmar presenca
no evento de outubro"), sem misturar isso com os campos "de verdade" do
cadastro.

Fica numa tabela PROPRIA (app_anotacoes), separada da tabela de dados (ex.:
PESSOAS) -- assim funciona pra QUALQUER tabela, sem precisar adicionar uma
coluna "ANOTACOES" em cada uma (o que obrigaria mexer no schema de tabelas
que o usuario ja criou).
"""
from __future__ import annotations

import sqlite3

from .schema import APP_ANOTACOES


def obter_anotacao(conn: sqlite3.Connection, tabela: str, registro_id: int) -> str:
    row = conn.execute(
        f"SELECT texto FROM {APP_ANOTACOES} WHERE tabela = ? AND registro_id = ?", (tabela, registro_id)
    ).fetchone()
    return (row[0] if row else "") or ""


def salvar_anotacao(conn: sqlite3.Connection, tabela: str, registro_id: int, texto: str) -> None:
    texto = (texto or "").strip()
    if not texto:
        # Nada escrito -- nao precisa guardar uma linha vazia no banco.
        conn.execute(f"DELETE FROM {APP_ANOTACOES} WHERE tabela = ? AND registro_id = ?", (tabela, registro_id))
    else:
        conn.execute(
            f"""INSERT INTO {APP_ANOTACOES} (tabela, registro_id, texto) VALUES (?, ?, ?)
                ON CONFLICT(tabela, registro_id) DO UPDATE SET texto = excluded.texto""",
            (tabela, registro_id, texto),
        )
    conn.commit()
