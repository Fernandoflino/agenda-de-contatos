import json
from unittest.mock import MagicMock, patch

from atualizacao import VerificadorAtualizacao, abrir_instalador, buscar_info_atualizacao, versao_e_mais_nova


def test_versao_remota_mais_nova():
    assert versao_e_mais_nova("0.11.0", "0.12.0") is True


def test_versao_remota_igual():
    assert versao_e_mais_nova("0.11.0", "0.11.0") is False


def test_versao_remota_mais_antiga():
    assert versao_e_mais_nova("0.11.0", "0.10.5") is False


def test_versao_remota_malformada():
    assert versao_e_mais_nova("0.11.0", "sem-numero") is False


def _resposta_falsa(dados: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(dados).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


@patch("atualizacao.urllib.request.urlopen")
@patch("atualizacao.VERSAO", "0.11.0")
def test_acha_atualizacao_com_asset_exe(urlopen_mock):
    urlopen_mock.return_value = _resposta_falsa(
        {
            "tag_name": "v0.12.0",
            "body": "Notas da release",
            "assets": [
                {"name": "codigo-fonte.zip", "browser_download_url": "https://exemplo/codigo-fonte.zip"},
                {"name": "PainelDeContatosSetup.exe", "browser_download_url": "https://exemplo/Setup.exe"},
            ],
        }
    )

    info = buscar_info_atualizacao()

    assert info == {
        "versao": "0.12.0",
        "notas": "Notas da release",
        "url_download": "https://exemplo/Setup.exe",
    }


@patch("atualizacao.urllib.request.urlopen")
@patch("atualizacao.VERSAO", "0.11.0")
def test_nao_acha_atualizacao_quando_versao_remota_nao_e_mais_nova(urlopen_mock):
    urlopen_mock.return_value = _resposta_falsa(
        {
            "tag_name": "v0.11.0",
            "body": "",
            "assets": [{"name": "Setup.exe", "browser_download_url": "https://exemplo/Setup.exe"}],
        }
    )

    assert buscar_info_atualizacao() is None


@patch("atualizacao.urllib.request.urlopen")
@patch("atualizacao.VERSAO", "0.11.0")
def test_nao_acha_atualizacao_sem_asset_exe(urlopen_mock):
    urlopen_mock.return_value = _resposta_falsa(
        {
            "tag_name": "v0.12.0",
            "body": "",
            "assets": [{"name": "codigo-fonte.zip", "browser_download_url": "https://exemplo/codigo-fonte.zip"}],
        }
    )

    assert buscar_info_atualizacao() is None


@patch("atualizacao.urllib.request.urlopen", side_effect=TimeoutError)
def test_falha_de_rede_devolve_none_em_vez_de_propagar(urlopen_mock):
    assert buscar_info_atualizacao() is None


@patch("atualizacao.buscar_info_atualizacao", return_value=None)
def test_verificador_emite_nao_encontrada_quando_nao_ha_versao_nova(mock_buscar):
    verificador = VerificadorAtualizacao()
    recebidos = []
    verificador.nao_encontrada.connect(lambda: recebidos.append(True))

    verificador._verificar()

    assert recebidos == [True]


@patch("atualizacao.buscar_info_atualizacao", return_value={"versao": "9.0.0", "notas": "", "url_download": "https://x"})
def test_verificador_emite_encontrada_quando_ha_versao_nova(mock_buscar):
    verificador = VerificadorAtualizacao()
    recebidos = []
    verificador.encontrada.connect(recebidos.append)

    verificador._verificar()

    assert recebidos == [{"versao": "9.0.0", "notas": "", "url_download": "https://x"}]


@patch("atualizacao.subprocess.Popen")
def test_abrir_instalador_chama_popen_com_o_caminho(popen_mock):
    abrir_instalador("C:/temp/PainelDeContatosSetup.exe")

    popen_mock.assert_called_once_with(["C:/temp/PainelDeContatosSetup.exe"], close_fds=True)


@patch("atualizacao.subprocess.Popen", side_effect=OSError("arquivo bloqueado"))
def test_abrir_instalador_propaga_oserror_quando_nao_consegue_abrir(popen_mock):
    try:
        abrir_instalador("C:/temp/PainelDeContatosSetup.exe")
        assert False, "deveria ter levantado OSError"
    except OSError as erro:
        assert str(erro) == "arquivo bloqueado"
