from datetime import date

from db import dashboard, records
from db.schema import EMPRESAS, PESSOAS


def _criar_empresa(conn, sigla="ABC", empresa="Empresa ABC"):
    return records.create_record(conn, EMPRESAS, {"SIGLA": sigla, "EMPRESA": empresa})


def test_total_contatos_e_empresas(conn):
    _criar_empresa(conn)
    _criar_empresa(conn, sigla="XYZ", empresa="Empresa XYZ")
    assert dashboard.total_empresas(conn) == 2
    assert dashboard.total_contatos(conn) == 0

    records.create_record(conn, PESSOAS, {"NOME": "Fulano"})
    assert dashboard.total_contatos(conn) == 1


def test_proximos_aniversarios_usa_registros_ja_filtrados_quando_informado(conn):
    """O filtro do Painel (ver ui/dashboard_view.py) so afeta essa lista --
    passa uma lista de PESSOAS ja filtrada em vez de deixar buscar tudo do
    banco de novo."""
    hoje = date(2026, 9, 9)
    records.create_record(conn, PESSOAS, {"NOME": "Incluido", "DATA DE NASCIMENTO": "1990-09-29"})
    excluido = records.create_record(conn, PESSOAS, {"NOME": "Excluido pelo filtro", "DATA DE NASCIMENTO": "1985-09-09"})

    todos = records.get_records(conn, PESSOAS)
    so_incluido = [p for p in todos if p["ID"] != excluido]

    lista = dashboard.proximos_aniversarios(conn, hoje=hoje, registros=so_incluido)
    assert [a.nome for a in lista] == ["Incluido"]


def test_proximos_aniversarios_ordena_pelo_mais_perto(conn):
    hoje = date(2026, 9, 9)
    records.create_record(conn, PESSOAS, {"NOME": "Nasce em 20 dias", "DATA DE NASCIMENTO": "1990-09-29"})
    records.create_record(conn, PESSOAS, {"NOME": "Nasce hoje", "DATA DE NASCIMENTO": "1985-09-09"})
    records.create_record(conn, PESSOAS, {"NOME": "Ja passou este ano", "DATA DE NASCIMENTO": "1970-01-15"})
    records.create_record(conn, PESSOAS, {"NOME": "Sem data"})
    records.create_record(conn, PESSOAS, {"NOME": "Data invalida", "DATA DE NASCIMENTO": "Cláudia"})

    lista = dashboard.proximos_aniversarios(conn, hoje=hoje)
    nomes = [a.nome for a in lista]

    assert nomes[0] == "Nasce hoje"
    assert lista[0].dias_ate == 0
    assert lista[0].idade_ao_completar == 41

    assert nomes[1] == "Nasce em 20 dias"
    assert lista[1].dias_ate == 20

    # quem ja fez aniversario esse ano aparece de novo, mas contando pro ANO QUE VEM
    ja_passou = next(a for a in lista if a.nome == "Ja passou este ano")
    assert ja_passou.dias_ate == (date(2027, 1, 15) - hoje).days
    assert ja_passou.idade_ao_completar == 57

    # sem data valida (vazia ou um texto que nao e data) nunca aparece na lista
    assert "Sem data" not in nomes
    assert "Data invalida" not in nomes


def test_proximos_aniversarios_respeita_limite(conn):
    hoje = date(2026, 1, 1)
    for i in range(10):
        records.create_record(conn, PESSOAS, {"NOME": f"Pessoa {i}", "DATA DE NASCIMENTO": f"1990-01-{i + 2:02d}"})
    assert len(dashboard.proximos_aniversarios(conn, limite=5, hoje=hoje)) == 5


def test_aniversario_29_de_fevereiro_cai_em_1_de_marco_em_ano_nao_bissexto(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Nascido em ano bissexto", "DATA DE NASCIMENTO": "1996-02-29"})
    hoje = date(2026, 2, 1)  # 2026 nao e bissexto
    lista = dashboard.proximos_aniversarios(conn, hoje=hoje)
    assert lista[0].dias_ate == (date(2026, 3, 1) - hoje).days


def test_empresas_sem_contato(conn):
    id_com_gente = _criar_empresa(conn, sigla="ABC")
    _criar_empresa(conn, sigla="XYZ", empresa="Empresa XYZ")
    records.create_record(conn, PESSOAS, {"ID_EMPRESA": id_com_gente, "NOME": "Fulano"})

    faltantes = dashboard.empresas_sem_contato(conn)
    assert faltantes == ["XYZ - Empresa XYZ"]


def test_contatos_incompletos_conta_campos_vazios(conn):
    records.create_record(conn, PESSOAS, {"NOME": "Completo", "EMAIL": "a@a.com", "WHATSAPP": "123", "DATA DE NASCIMENTO": "1990-01-01"})
    records.create_record(conn, PESSOAS, {"NOME": "Sem nada"})

    resultado = dashboard.contatos_incompletos(conn)
    assert resultado == {"sem_email": 1, "sem_whatsapp": 1, "sem_data_nascimento": 1}
