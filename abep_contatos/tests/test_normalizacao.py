from db.normalizacao import normalizar_nome_proprio


def test_normaliza_nome_simples():
    assert normalizar_nome_proprio("ALÍRIO FÉLIX MARTINS BARROS") == "Alírio Félix Martins Barros"


def test_mantem_conectores_em_minusculo():
    texto = "AGÊNCIA DE TECNOLOGIA DA INFORMAÇÃO DO TOCANTINS"
    assert normalizar_nome_proprio(texto) == "Agência de Tecnologia da Informação do Tocantins"


def test_conector_no_inicio_fica_maiusculo():
    assert normalizar_nome_proprio("DA SILVA") == "Da Silva"


def test_nome_com_hifen():
    assert normalizar_nome_proprio("MARIA-JOSÉ DA SILVA") == "Maria-José da Silva"


def test_valor_vazio_ou_none_passa_direto():
    assert normalizar_nome_proprio(None) is None
    assert normalizar_nome_proprio("") == ""
