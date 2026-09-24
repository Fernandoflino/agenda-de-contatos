import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from db import lock


@pytest.fixture()
def caminho_banco(tmp_path):
    caminho = tmp_path / "teste.abepdb"
    caminho.write_text("")
    return str(caminho)


def _caminho_lock(caminho_banco):
    return caminho_banco + ".lock"


def _escrever_lock(caminho_banco, **campos):
    base = {
        "maquina": "OUTRA-MAQUINA",
        "usuario_os": "outra.pessoa",
        "aberto_em": datetime.now(timezone.utc).isoformat(),
        "ultima_atividade": datetime.now(timezone.utc).isoformat(),
    }
    base.update(campos)
    with open(_caminho_lock(caminho_banco), "w", encoding="utf-8") as f:
        json.dump(base, f)
    return base


def test_adquirir_sem_lock_existente_cria_arquivo(caminho_banco):
    resultado = lock.adquirir(caminho_banco)

    assert resultado is None
    assert os.path.isfile(_caminho_lock(caminho_banco))


def test_adquirir_com_lock_ativo_devolve_infolock_sem_sobrescrever(caminho_banco):
    dados = _escrever_lock(caminho_banco)

    resultado = lock.adquirir(caminho_banco)

    assert resultado is not None
    assert resultado.maquina == "OUTRA-MAQUINA"
    assert resultado.usuario_os == "outra.pessoa"
    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        assert json.load(f) == dados


def test_adquirir_com_lock_velho_trata_como_livre(caminho_banco):
    antiga = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    _escrever_lock(caminho_banco, aberto_em=antiga, ultima_atividade=antiga)

    resultado = lock.adquirir(caminho_banco)

    assert resultado is None
    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        novo = json.load(f)
    assert novo["maquina"] != "OUTRA-MAQUINA"


def test_adquirir_forcar_sobrescreve_mesmo_com_lock_ativo(caminho_banco):
    _escrever_lock(caminho_banco)

    resultado = lock.adquirir(caminho_banco, forcar=True)

    assert resultado is None
    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        novo = json.load(f)
    assert novo["maquina"] != "OUTRA-MAQUINA"


def test_liberar_remove_quando_e_nosso(caminho_banco):
    lock.adquirir(caminho_banco)
    assert os.path.isfile(_caminho_lock(caminho_banco))

    lock.liberar(caminho_banco)

    assert not os.path.isfile(_caminho_lock(caminho_banco))


def test_liberar_nao_remove_lock_de_outra_sessao(caminho_banco):
    _escrever_lock(caminho_banco)

    lock.liberar(caminho_banco)

    assert os.path.isfile(_caminho_lock(caminho_banco))


def test_atualizar_atividade_atualiza_so_o_timestamp(caminho_banco):
    lock.adquirir(caminho_banco)
    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        antes = json.load(f)

    lock.atualizar_atividade(caminho_banco)

    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        depois = json.load(f)
    assert depois["maquina"] == antes["maquina"]
    assert depois["usuario_os"] == antes["usuario_os"]
    assert depois["aberto_em"] == antes["aberto_em"]
    assert depois["ultima_atividade"] >= antes["ultima_atividade"]


def test_atualizar_atividade_nao_faz_nada_se_lock_nao_e_nosso(caminho_banco):
    dados = _escrever_lock(caminho_banco)

    lock.atualizar_atividade(caminho_banco)

    with open(_caminho_lock(caminho_banco), "r", encoding="utf-8") as f:
        assert json.load(f) == dados
