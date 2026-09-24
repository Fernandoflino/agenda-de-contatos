"""
Este arquivo calcula os numeros e listas mostrados no PAINEL (dashboard) --
a primeira tela que aparece depois do login, com um resumo rapido da
situacao dos contatos: quantos tem cadastrados, quem faz aniversario em
breve, e alguns pontos que podem precisar de atencao (empresa sem nenhum
contato, contato sem e-mail...).

Cada funcao aqui devolve so DADOS (numeros, listas, dicionarios) -- quem
decide como desenhar isso na tela e ui/dashboard_view.py. Separar assim (uma
"camada de dados" sem nada de tela) e o que permite testar tudo isso com
pytest, sem precisar abrir nenhuma janela de verdade.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from . import records
from .schema import EMPRESAS, PESSOAS


def total_contatos(conn: sqlite3.Connection) -> int:
    return len(records.get_records(conn, PESSOAS))


def total_empresas(conn: sqlite3.Connection) -> int:
    return len(records.get_records(conn, EMPRESAS))


@dataclass
class Aniversariante:
    nome: str
    empresa: str
    data_nascimento: str  # formato ISO ('AAAA-MM-DD'), como fica guardado no banco
    dias_ate: int         # 0 = hoje, 1 = amanha, etc.
    idade_ao_completar: int


def _proximo_aniversario(data_nascimento_iso: str, hoje: date) -> tuple[int, int] | None:
    """A partir de uma data de nascimento (formato ISO), calcula quantos
    dias faltam pro proximo aniversario e que idade a pessoa vai completar.

    Devolve None se o texto guardado nao for uma data valida -- protege
    contra dados antigos digitados errado (ja apareceu no banco um nome de
    pessoa gravado por engano nesse campo, em vez de uma data)."""
    try:
        nascimento = date.fromisoformat((data_nascimento_iso or "")[:10])
    except ValueError:
        return None

    try:
        proximo = nascimento.replace(year=hoje.year)
    except ValueError:
        # Nasceu em 29 de fevereiro, e o ano atual nao e bissexto -- o Brasil
        # costuma comemorar no dia 1 de marco nesse caso.
        proximo = date(hoje.year, 3, 1)

    if proximo < hoje:
        try:
            proximo = proximo.replace(year=hoje.year + 1)
        except ValueError:
            proximo = date(hoje.year + 1, 3, 1)

    dias_ate = (proximo - hoje).days
    idade_ao_completar = proximo.year - nascimento.year
    return dias_ate, idade_ao_completar


def proximos_aniversarios(conn: sqlite3.Connection, limite: int = 8, hoje: date | None = None) -> list[Aniversariante]:
    """Os proximos aniversariantes, do mais perto pro mais distante --
    ignora silenciosamente quem nao tem uma data de nascimento valida
    cadastrada. `hoje` so existe como parametro pra facilitar testar (no uso
    normal do programa, e sempre a data de hoje de verdade)."""
    hoje = hoje or date.today()

    encontrados = []
    for pessoa in records.get_records(conn, PESSOAS):
        resultado = _proximo_aniversario(str(pessoa.get("DATA DE NASCIMENTO") or ""), hoje)
        if resultado is None:
            continue
        dias_ate, idade = resultado
        encontrados.append(Aniversariante(
            nome=pessoa.get("NOME") or pessoa.get("NOME DE GUERRA") or f'Contato #{pessoa["ID"]}',
            empresa=pessoa.get("_EMPRESA_SIGLA") or "",
            data_nascimento=pessoa.get("DATA DE NASCIMENTO"),
            dias_ate=dias_ate,
            idade_ao_completar=idade,
        ))

    encontrados.sort(key=lambda a: a.dias_ate)
    return encontrados[:limite]


def empresas_sem_contato(conn: sqlite3.Connection) -> list[str]:
    """Empresas que ainda nao tem NENHUM contato cadastrado -- um jeito
    rapido de achar quem ainda precisa ser preenchido. Devolve uma lista de
    textos prontos pra mostrar ("SIGLA - Nome da empresa")."""
    empresas = records.get_records(conn, EMPRESAS)
    pessoas = records.get_records(conn, PESSOAS)
    ids_com_contato = {p.get("ID_EMPRESA") for p in pessoas if p.get("ID_EMPRESA") is not None}

    faltantes = []
    for empresa in empresas:
        if empresa["ID"] in ids_com_contato:
            continue
        texto = " - ".join(p for p in (empresa.get("SIGLA"), empresa.get("EMPRESA")) if p)
        faltantes.append(texto or f'Empresa #{empresa["ID"]}')
    return sorted(faltantes)


def contatos_incompletos(conn: sqlite3.Connection) -> dict[str, int]:
    """Quantos contatos estao sem e-mail, sem WhatsApp, ou sem data de
    nascimento preenchida -- um jeito rapido de ver o que falta completar
    no cadastro (nao e um erro, so um indicador de dado ausente)."""
    pessoas = records.get_records(conn, PESSOAS)
    return {
        "sem_email": sum(1 for p in pessoas if not str(p.get("EMAIL") or "").strip()),
        "sem_whatsapp": sum(1 for p in pessoas if not str(p.get("WHATSAPP") or "").strip()),
        "sem_data_nascimento": sum(1 for p in pessoas if not str(p.get("DATA DE NASCIMENTO") or "").strip()),
    }
