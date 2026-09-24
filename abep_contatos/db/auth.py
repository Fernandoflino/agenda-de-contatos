"""
Este arquivo cuida do LOGIN: conferir usuario/senha, e bloquear temporariamente
quem errar a senha muitas vezes seguidas (protecao contra "forca bruta", ou
seja, alguem tentando adivinhar a senha testando varias vezes rapidinho).

Como as senhas sao guardadas com seguranca (hash + pepper)
-----------------------------------------------------------
O programa NUNCA guarda a senha digitada pelo usuario "em texto puro" (do
jeito que a pessoa digitou). Em vez disso, ele guarda o resultado de uma
formula matematica de "hash" (SHA-256) aplicada a senha + uma palavra secreta
extra chamada "pepper". Hash e uma via de mao unica: da pra transformar a
senha no hash, mas NAO da pra transformar o hash de volta na senha original.
Assim, mesmo que alguem consiga abrir o arquivo do banco de dados direto, nao
consegue descobrir as senhas de verdade.

O "pepper" (uma sequencia aleatoria gerada uma unica vez) fica guardado
DENTRO do proprio arquivo .abepdb -- isso e proposital: se o usuario copiar o
arquivo pra outro computador, o login continua funcionando normalmente, porque
o pepper viaja junto com o banco.

Diferente do sistema antigo (que rodava na internet), aqui nao existe
"sessao" nem "token" -- o programa e local, entao um login bem-sucedido so
precisa ser lembrado enquanto o programa estiver aberto na tela.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import log
from .schema import APP_LOGIN_ATTEMPTS, APP_METADATA, USUARIOS

_PEPPER_KEY = "auth_pepper"
LOGIN_MAX_TENTATIVAS = 5
LOGIN_BLOQUEIO_MINUTOS = 15


class ErroLogin(Exception):
    """Erro "esperado" de login (senha errada, bloqueado etc.) -- a mensagem
    dele e sempre segura de mostrar direto pro usuario na tela."""
    pass


@dataclass
class Usuario:
    """Representa quem esta logado no programa neste momento (guardado so na
    memoria do programa, nunca salvo em disco)."""
    id: int
    usuario: str
    nome: str


def obter_pepper(conn: sqlite3.Connection) -> str:
    """Devolve o "pepper" deste banco de dados, criando um novo (aleatorio e
    bem grande) na primeira vez que for chamado, se ainda nao existir um."""
    row = conn.execute(f"SELECT valor FROM {APP_METADATA} WHERE chave = ?", (_PEPPER_KEY,)).fetchone()
    if row:
        return row[0]
    pepper = secrets.token_hex(32)  # 32 bytes aleatorios == praticamente impossivel de adivinhar
    conn.execute(f"INSERT INTO {APP_METADATA} (chave, valor) VALUES (?, ?)", (_PEPPER_KEY, pepper))
    conn.commit()
    return pepper


def hash_senha(senha: str, pepper: str) -> str:
    """Transforma uma senha em texto puro no seu hash (irreversivel), pra
    poder comparar ou guardar sem nunca lidar com a senha de verdade."""
    return hashlib.sha256((senha + pepper).encode("utf-8")).hexdigest()


def _chave(usuario: str) -> str:
    """Normaliza o nome de usuario (sem espacos, minusculo) pra comparar
    "Maria", " maria " e "MARIA" como sendo a mesma pessoa."""
    return usuario.strip().lower()


def _checar_bloqueio(conn: sqlite3.Connection, chave: str) -> None:
    """Antes de conferir a senha, ve se esse usuario esta temporariamente
    bloqueado por ter errado a senha muitas vezes seguidas."""
    row = conn.execute(
        f"SELECT bloqueado_ate FROM {APP_LOGIN_ATTEMPTS} WHERE usuario_chave = ?", (chave,)
    ).fetchone()
    if row and row[0]:
        bloqueado_ate = datetime.fromisoformat(row[0])
        agora = datetime.now(timezone.utc)
        if bloqueado_ate > agora:
            minutos = max(1, int((bloqueado_ate - agora).total_seconds() // 60) + 1)
            raise ErroLogin(f"Muitas tentativas erradas. Tente de novo em {minutos} minuto(s).")


def _registrar_falha(conn: sqlite3.Connection, chave: str) -> None:
    """Soma mais uma tentativa errada; ao chegar em LOGIN_MAX_TENTATIVAS
    seguidas, bloqueia esse usuario por LOGIN_BLOQUEIO_MINUTOS."""
    row = conn.execute(
        f"SELECT falhas FROM {APP_LOGIN_ATTEMPTS} WHERE usuario_chave = ?", (chave,)
    ).fetchone()
    falhas = (row[0] if row else 0) + 1
    bloqueado_ate = None
    if falhas >= LOGIN_MAX_TENTATIVAS:
        bloqueado_ate = (datetime.now(timezone.utc) + timedelta(minutes=LOGIN_BLOQUEIO_MINUTOS)).isoformat()
        falhas = 0  # zera o contador -- o bloqueio em si e que vale a partir de agora
    conn.execute(
        f"""INSERT INTO {APP_LOGIN_ATTEMPTS} (usuario_chave, falhas, bloqueado_ate) VALUES (?, ?, ?)
            ON CONFLICT(usuario_chave) DO UPDATE SET falhas = excluded.falhas, bloqueado_ate = excluded.bloqueado_ate""",
        (chave, falhas, bloqueado_ate),
    )
    conn.commit()


def _limpar_falhas(conn: sqlite3.Connection, chave: str) -> None:
    """Zera o historico de tentativas erradas depois de um login com sucesso."""
    conn.execute(f"DELETE FROM {APP_LOGIN_ATTEMPTS} WHERE usuario_chave = ?", (chave,))
    conn.commit()


def login(conn: sqlite3.Connection, usuario_informado: str, senha_informada: str) -> Usuario:
    """Tenta logar com o usuario/senha digitados na tela.

    Devolve um objeto Usuario se der certo, ou levanta ErroLogin (com uma
    mensagem pronta pra mostrar na tela) se der errado -- seja por senha
    incorreta, seja por bloqueio de tentativas.
    """
    usuario_informado = (usuario_informado or "").strip()
    senha_informada = senha_informada or ""
    if not usuario_informado or not senha_informada:
        raise ErroLogin("Informe usuario e senha.")

    chave = _chave(usuario_informado)
    _checar_bloqueio(conn, chave)

    pepper = obter_pepper(conn)
    hash_informado = hash_senha(senha_informada, pepper)

    # Busca o usuario ignorando maiusculas/minusculas e espacos nas pontas.
    row = conn.execute(
        f'SELECT "ID", "USUARIO", "SENHA_HASH", "NOME" FROM "{USUARIOS}" WHERE LOWER(TRIM("USUARIO")) = ?',
        (chave,),
    ).fetchone()

    if row and row[2] == hash_informado:
        _limpar_falhas(conn, chave)
        return Usuario(id=row[0], usuario=row[1], nome=row[3] or row[1])

    # Nao dizemos se o erro foi "usuario nao existe" ou "senha errada" -- essa
    # ambiguidade proposital dificulta que alguem descubra quais usuarios
    # existem so tentando logins.
    _registrar_falha(conn, chave)
    raise ErroLogin("Usuario ou senha invalidos.")


def existe_algum_usuario(conn: sqlite3.Connection) -> bool:
    """Usado ao criar um banco novo: se ainda nao existe nenhum usuario, o
    programa obriga a criar o primeiro administrador antes de liberar o uso."""
    row = conn.execute(f'SELECT 1 FROM "{USUARIOS}" LIMIT 1').fetchone()
    return row is not None


def criar_usuario(conn: sqlite3.Connection, usuario: str, senha: str, nome: str, usuario_logado: str = "sistema") -> int:
    """Cria um novo usuario que podera fazer login. A senha entra em texto
    puro aqui, e e imediatamente transformada em hash antes de ser gravada."""
    usuario = (usuario or "").strip()
    senha = senha or ""
    if not usuario or not senha:
        raise ValueError("Informe usuario e senha.")
    pepper = obter_pepper(conn)
    cur = conn.execute(
        f'INSERT INTO "{USUARIOS}" ("USUARIO", "SENHA_HASH", "NOME") VALUES (?, ?, ?)',
        (usuario, hash_senha(senha, pepper), nome or usuario),
    )
    conn.commit()
    log.log_change(conn, usuario_logado, USUARIOS, "Criar usuario", usuario)
    return cur.lastrowid
