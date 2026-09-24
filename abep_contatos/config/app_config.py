"""
Este arquivo guarda uma preferencia que e do COMPUTADOR/USUARIO DO WINDOWS,
nao do banco de dados: a lista de bancos abertos recentemente, pra mostrar
na tela inicial (parecido com o "Documentos recentes" do Word).

Por que isso NAO fica dentro do arquivo .abepdb? Porque cada pessoa que usa
o programa nesse computador pode ter aberto bancos diferentes -- essa lista e
sobre o computador, nao sobre um banco especifico. Ela fica guardada num
arquivo de configuracao simples, numa pasta padrao do Windows pra esse tipo
de dado (a pasta "AppData" do usuario, que normalmente fica escondida).
"""
from __future__ import annotations

import json
import os

MAX_RECENTES = 10


def _pasta_config() -> str:
    """Descobre (e cria, se preciso) a pasta onde o arquivo de configuracao
    deste programa deve ficar guardado."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    pasta = os.path.join(base, "ABEP-TIC", "ContatosABEP")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _arquivo_config() -> str:
    return os.path.join(_pasta_config(), "config.json")


def _carregar() -> dict:
    """Le o arquivo de configuracao do disco. Se ele nao existir ainda (ex.:
    primeira vez que o programa roda nesse computador) ou estiver corrompido,
    devolve uma configuracao vazia em vez de dar erro."""
    caminho = _arquivo_config()
    if not os.path.isfile(caminho):
        return {"recentes": []}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if not isinstance(dados, dict):
                return {"recentes": []}
            dados.setdefault("recentes", [])
            return dados
    except (json.JSONDecodeError, OSError):
        return {"recentes": []}


def _salvar(dados: dict) -> None:
    with open(_arquivo_config(), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def bancos_recentes() -> list[str]:
    """Devolve os caminhos de banco usados recentemente, do mais novo pro
    mais antigo -- ja removendo da lista qualquer arquivo que tenha sido
    apagado ou movido desde a ultima vez (assim a tela inicial nunca mostra
    um atalho quebrado)."""
    dados = _carregar()
    validos = [c for c in dados.get("recentes", []) if os.path.isfile(c)]
    if validos != dados.get("recentes", []):
        dados["recentes"] = validos
        _salvar(dados)
    return validos


def registrar_recente(caminho: str) -> None:
    """Coloca `caminho` no topo da lista de recentes (removendo uma
    ocorrencia antiga dele, se houver) e mantem so os MAX_RECENTES mais
    novos."""
    dados = _carregar()
    recentes = [c for c in dados.get("recentes", []) if c != caminho]
    recentes.insert(0, caminho)
    dados["recentes"] = recentes[:MAX_RECENTES]
    _salvar(dados)


def ultimo_usuario() -> str:
    """Nome de usuario lembrado da ultima vez que alguem fez login com
    sucesso -- so pra pre-preencher o campo na tela de login (achado #10 da
    auditoria de UX). Nao guarda senha nenhuma."""
    return _carregar().get("ultimo_usuario", "")


def definir_ultimo_usuario(usuario: str) -> None:
    dados = _carregar()
    dados["ultimo_usuario"] = usuario
    _salvar(dados)


def versao_ignorada() -> str:
    """Versao que o usuario marcou como "nao perguntar de novo" na caixa de
    aviso de atualizacao -- fica vazia se nunca marcou nenhuma."""
    return _carregar().get("versao_ignorada", "")


def definir_versao_ignorada(versao: str) -> None:
    dados = _carregar()
    dados["versao_ignorada"] = versao
    _salvar(dados)


def remover_recente(caminho: str) -> None:
    """Tira um caminho da lista de recentes (ex.: usuario clicou em "remover
    da lista" na tela inicial)."""
    dados = _carregar()
    dados["recentes"] = [c for c in dados.get("recentes", []) if c != caminho]
    _salvar(dados)
