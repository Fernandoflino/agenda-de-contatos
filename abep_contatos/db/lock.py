"""
Trava cooperativa "melhor esforco" contra duas pessoas abrindo o MESMO
arquivo .abepdb ao mesmo tempo em maquinas diferentes.

Isso NAO e um lock de verdade (como um banco cliente-servidor teria) -- e
so um arquivo `<banco>.lock` (JSON) guardado do lado do banco, dizendo
"eu, maquina X, usuario Y, estou com esse banco aberto desde tal hora".
Quando o app abre um banco, primeiro olha se esse arquivo ja existe e
parece "vivo" (atualizado ha pouco tempo); se sim, avisa a pessoa em vez
de deixar ela abrir sem saber que outra maquina tambem esta usando.

Como o banco costuma ficar numa pasta sincronizada (OneDrive etc.), o
proprio arquivo de trava pode demorar pra sincronizar tambem -- por isso
isso reduz a chance do problema (duas pessoas mexendo ao mesmo tempo sem
perceber), mas nao elimina 100% dela.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Se a trava nao for "renovada" (ver atualizar_atividade) por mais tempo
# que isso, ela e considerada abandonada (o programa provavelmente travou
# ou fechou sem dar tempo de limpar) e pode ser assumida por outra sessao
# sem perguntar nada.
LIMITE_INATIVIDADE = timedelta(minutes=5)


@dataclass
class InfoLock:
    """Dados de quem esta com a trava, pra mostrar numa mensagem pro usuario."""

    maquina: str
    usuario_os: str
    aberto_em: str
    ultima_atividade: str


def _caminho_lock(caminho_banco: str) -> str:
    return caminho_banco + ".lock"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _ler(caminho_lock: str) -> dict | None:
    try:
        with open(caminho_lock, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def _escrever(caminho_lock: str, dados: dict) -> None:
    with open(caminho_lock, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _dados_desta_sessao(dados: dict) -> dict:
    """Novo conteudo do arquivo de trava, identificando esta maquina/usuario."""
    agora = _agora().isoformat()
    return {
        "maquina": socket.gethostname(),
        "usuario_os": getpass.getuser(),
        "aberto_em": dados.get("aberto_em", agora) if dados else agora,
        "ultima_atividade": agora,
    }


def _esta_ativo(dados: dict) -> bool:
    try:
        ultima = datetime.fromisoformat(dados["ultima_atividade"])
    except (KeyError, TypeError, ValueError):
        return False
    return _agora() - ultima < LIMITE_INATIVIDADE


def _e_desta_sessao(dados: dict) -> bool:
    return dados.get("maquina") == socket.gethostname() and dados.get("usuario_os") == getpass.getuser()


def adquirir(caminho_banco: str, forcar: bool = False) -> InfoLock | None:
    """Tenta assumir a trava do banco em `caminho_banco`.

    Devolve None se conseguiu (trava livre, abandonada, ou `forcar=True`).
    Devolve um InfoLock com os dados de quem esta usando, SEM mexer no
    arquivo, se a trava esta ativa e `forcar` e False -- quem chamou decide
    o que fazer (ex.: perguntar pro usuario se quer abrir mesmo assim).
    """
    caminho_lock = _caminho_lock(caminho_banco)
    dados = _ler(caminho_lock)

    if dados is not None and not forcar and _esta_ativo(dados):
        return InfoLock(
            maquina=dados.get("maquina", "?"),
            usuario_os=dados.get("usuario_os", "?"),
            aberto_em=dados.get("aberto_em", "?"),
            ultima_atividade=dados.get("ultima_atividade", "?"),
        )

    _escrever(caminho_lock, _dados_desta_sessao(None))
    return None


def atualizar_atividade(caminho_banco: str) -> None:
    """Renova a trava desta sessao, pra ela nao ser considerada abandonada.

    Chamado periodicamente (via timer) enquanto o banco esta aberto. Se a
    trava no disco nao for mais desta sessao (por exemplo, foi apagada ou
    outra maquina assumiu com `forcar=True`), nao faz nada -- nao tenta
    "reconquistar" uma trava que nao e mais nossa."""
    caminho_lock = _caminho_lock(caminho_banco)
    dados = _ler(caminho_lock)
    if dados is None or not _e_desta_sessao(dados):
        return
    dados["ultima_atividade"] = _agora().isoformat()
    _escrever(caminho_lock, dados)


def liberar(caminho_banco: str) -> None:
    """Remove a trava, mas so se ela pertencer a esta sessao (mesma maquina
    e usuario do SO) -- assim nao corre o risco de apagar por engano a
    trava de outra sessao que tenha assumido o banco depois da nossa."""
    caminho_lock = _caminho_lock(caminho_banco)
    dados = _ler(caminho_lock)
    if dados is None or not _e_desta_sessao(dados):
        return
    try:
        os.remove(caminho_lock)
    except OSError:
        pass
