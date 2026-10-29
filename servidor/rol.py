"""
O rol de filiados que a entidade entrega, e por que ele é obrigatório.

O PORTÃO SÓ É PORTÃO SE O E-MAIL NÃO FOR ESCOLHIDO POR QUEM ENTRA.

A tentação é pedir CPF e e-mail na tela e mandar o código para o e-mail
digitado. Isso não confere nada: eu digito o CPF de outra pessoa, ponho o meu
e-mail, recebo o código e entrego os meus documentos no nome dela — ou, pior,
vejo o cadastro dela. O código viraria enfeite.

Então o código vai para o e-mail **que o sindicato tem em cadastro**. Quem não
está no rol não entra, e isso é resposta certa: o portal atende filiados de uma
entidade que contratou o serviço, não o público. É o que o modelo por sindicato
dá de graça, e é por isso que ele é mais seguro, não só mais defensável.

CONSEQUÊNCIA ASSUMIDA: sem `filiados.csv` a entidade não emite código nenhum.
O servidor diz isso com todas as letras em vez de deixar passar. Um portão que
abre para todos é pior que um portão fechado, porque parece que existe.

FORMATO, de propósito o mais simples que o sindicato consegue exportar:

    cpf,email
    526.018.159-06,fulano@exemplo.org

Colunas a mais são ignoradas (a exportação do sindicato vem cheia delas);
`cpf` e `email` são exigidas.
"""

from __future__ import annotations

import csv
import io
import pathlib
from dataclasses import dataclass

from .validacao import cpf_valido, so_digitos

ARQUIVO = "filiados.csv"

#: O rol de GESTORES, mesmo formato e mesmo portão.
#:
#: Existe porque o gerente do sindicato não é necessariamente filiado: se o
#: código só fosse para quem está em `filiados.csv`, não haveria como ele
#: entrar no painel. E ele passa pelo MESMO portão — código de seis dígitos
#: no e-mail que a entidade cadastrou, sem senha — porque inventar um login
#: de gestor seria inventar uma senha para guardar.
#:
#: Ausência deste arquivo NÃO é erro: é sindicato que ainda não configurou
#: painel. Ausência de `filiados.csv` é erro, porque sem ele o portão abriria
#: para todos.
ARQUIVO_GESTORES = "gestores.csv"


class RolAusente(FileNotFoundError):
    """A entidade não entregou o rol. Não há como conferir ninguém."""


@dataclass(frozen=True)
class Rol:
    caminho: pathlib.Path
    por_cpf: dict[str, str]
    recusados: tuple[str, ...]

    def email_de(self, cpf: str) -> str | None:
        return self.por_cpf.get(so_digitos(cpf))


def carregar(pasta_entidade: pathlib.Path) -> Rol:
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        raise RolAusente(str(caminho))
    return _carregar(caminho)


def carregar_gestores(pasta_entidade: pathlib.Path) -> Rol:
    """Os gestores da entidade. Vazio quando o arquivo não existe.

    Fail-closed na prática: rol de gestores vazio significa que NINGUÉM abre
    o painel, que é o certo — um painel que abre para qualquer um é pior que
    painel nenhum, porque parece seguro.
    """
    caminho = pasta_entidade / ARQUIVO_GESTORES
    if not caminho.is_file():
        return Rol(caminho=caminho, por_cpf={}, recusados=())
    return _carregar(caminho)


def _carregar(caminho: pathlib.Path) -> Rol:
    por_cpf: dict[str, str] = {}
    recusados: list[str] = []
    # O MESMO arquivo que `acervo.py` lê, do mesmo Excel. Abrir só em
    # utf-8-sig derrubava o portão INTEIRO quando a exportação vinha em
    # latin-1: UnicodeDecodeError é ValueError, o servidor loga ROL INVÁLIDO e
    # devolve 202 para todo mundo. O sindicato veria o painel acender e o
    # portal recusar silenciosamente cada filiado.
    #
    # E o separador também: a exportação de Excel em português usa ';'.
    from . import acervo

    texto = acervo._decodificar(caminho.read_bytes())
    primeira = texto.splitlines()[0] if texto.strip() else ""
    with io.StringIO(texto, newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=acervo._separador(primeira))
        colunas = {(c or "").strip().lower() for c in (leitor.fieldnames or [])}
        if not {"cpf", "email"} <= colunas:
            raise ValueError(
                f"{caminho} precisa das colunas cpf e email; "
                f"tem {sorted(colunas)}"
            )
        for numero, registro in enumerate(leitor, start=2):
            bruto = {
                (k or "").strip().lower(): (v or "").strip()
                for k, v in registro.items()
            }
            digitos = so_digitos(bruto.get("cpf", ""))
            email = bruto.get("email", "")
            if not cpf_valido(digitos):
                recusados.append(f"linha {numero}: CPF inválido")
                continue
            if "@" not in email:
                recusados.append(f"linha {numero}: e-mail inválido")
                continue
            por_cpf[digitos] = email
    return Rol(caminho=caminho, por_cpf=por_cpf, recusados=tuple(recusados))
