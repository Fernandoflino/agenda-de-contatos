"""
Preferencias PESSOAIS de quem faz login no programa: os filtros que a pessoa
deixou montados numa tabela, a largura que ela escolheu pro painel de
detalhes (arrastando a divisoria) e quantos itens por pagina ela prefere ver.

Fica guardado dentro do proprio arquivo .abepdb (mesma ideia de
db/settings.py -- viaja junto se o arquivo for copiado pra outro computador),
mas com uma diferenca importante: aqui e por PESSOA (usuario logado), nao pro
banco inteiro -- assim, se duas pessoas usarem o mesmo banco (no mesmo
computador ou em computadores diferentes), cada uma ve os proprios
filtros/larguras, sem misturar com os da outra.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from .schema import APP_USER_PREFS


@dataclass
class PreferenciasTabela:
    """O que e lembrado por (usuario, tabela). Qualquer campo pode vir vazio
    -- por exemplo, quem nunca mexeu num filtro simplesmente tem `filtros`
    como lista vazia, e a tela usa os valores padrao de sempre."""
    filtros: list[dict] = field(default_factory=list)
    largura_painel: list[int] | None = None
    itens_por_pagina: int | None = None


def obter_preferencias(conn: sqlite3.Connection, usuario: str, tabela: str) -> PreferenciasTabela:
    row = conn.execute(
        f"SELECT dados FROM {APP_USER_PREFS} WHERE usuario = ? AND tabela = ?", (usuario, tabela)
    ).fetchone()
    if not row or not row[0]:
        return PreferenciasTabela()
    try:
        dados = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return PreferenciasTabela()
    if not isinstance(dados, dict):
        return PreferenciasTabela()

    filtros = dados.get("filtros")
    largura = dados.get("largura_painel")
    itens = dados.get("itens_por_pagina")
    return PreferenciasTabela(
        filtros=filtros if isinstance(filtros, list) else [],
        largura_painel=largura if isinstance(largura, list) and len(largura) == 2 else None,
        itens_por_pagina=itens if isinstance(itens, int) else None,
    )


def salvar_preferencias(conn: sqlite3.Connection, usuario: str, tabela: str, prefs: PreferenciasTabela) -> None:
    dados = {
        "filtros": prefs.filtros,
        "largura_painel": prefs.largura_painel,
        "itens_por_pagina": prefs.itens_por_pagina,
    }
    conn.execute(
        f"""INSERT INTO {APP_USER_PREFS} (usuario, tabela, dados) VALUES (?, ?, ?)
            ON CONFLICT(usuario, tabela) DO UPDATE SET dados = excluded.dados""",
        (usuario, tabela, json.dumps(dados, ensure_ascii=False)),
    )
    conn.commit()
