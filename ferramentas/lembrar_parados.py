#!/usr/bin/env python3
"""
Lembra os escritórios dos casos que o sindicato encaminhou e eles ainda não
confirmaram.

O e-mail que avisa na hora do encaminhamento pode se perder, e o caso fica
esperando sem ninguém saber: o filiado vê "o escritório ainda não confirmou"
e liga para a sede. Esta ferramenta é o que impede isso de durar. O
agendador a roda todo dia; ela lembra o escritório dos casos parados há mais
de sete dias, uma vez por semana por caso, e anota no histórico de cada um.

    python3 ferramentas/lembrar_parados.py --entidade demo-sindicato

O e-mail leva só contagens — nunca nome nem CPF de filiado. A saída desta
ferramenta também.

CÓDIGOS DE SAÍDA, que é o que o agendador lê:

    0  não havia o que lembrar, ou os lembretes saíram
    1  havia caso parado e o lembrete de algum escritório NÃO saiu. O
       agendador registra falha, e a falha aparece em /saude
    2  a entidade não existe
"""
from __future__ import annotations

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import entidades, escritorios, remetente  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entidade", required=True)
    p.add_argument("--raiz", default="dados")
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2
    pasta = ent.pasta(raiz)
    if not escritorios.parados_a_lembrar(pasta):
        print("nenhum caso parado a lembrar")
        return 0

    r = escritorios.lembrar_parados(
        pasta, sindicato=ent.nome, correio=remetente.pelo_ambiente(raiz))
    casos = "1 caso parado" if r["casos"] == 1 else f"{r['casos']} casos parados"
    print(f"{casos} em {ent.apelido}: {r['escritorios']} escritório(s) "
          f"lembrado(s)")
    if r["falharam"]:
        print(f"o lembrete de {r['falharam']} escritório(s) NÃO saiu em "
              f"{ent.apelido}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
