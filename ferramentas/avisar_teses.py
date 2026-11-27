#!/usr/bin/env python3
"""
O aviso da manhã: o que os tribunais julgaram, e quantas pessoas alcança.

Quando o catálogo de uma carreira registra que um tema foi julgado (ou
afetado), o escritório contratado e a diretoria do sindicato recebem um
e-mail: qual tribunal, qual tema, e quantas pessoas da base teriam o caminho
aberto se a tese for conferida por advogado. O agendador roda isto todo dia;
cada novidade é avisada UMA vez.

    python3 ferramentas/avisar_teses.py --entidade demo-sindicato

O e-mail leva só tribunal, tema e contagens — nunca nome nem CPF. A saída
desta ferramenta também. O número é uma SIMULAÇÃO, e o e-mail diz isso.

CÓDIGOS DE SAÍDA, que é o que o agendador lê:

    0  não havia novidade por avisar, ou o aviso saiu para alguém
    1  havia novidade e o aviso não saiu para NINGUÉM, ou saiu para uns e
       falhou para outros. A falha aparece em /saude
    2  a entidade não existe
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import entidades, remetente, vigia  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entidade", required=True)
    p.add_argument("--raiz", default="dados")
    p.add_argument("--banco",
                   default=os.environ.get("PROTOCOL_DATABASE_URL", ""))
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2
    if not ent.categorias:
        print(f"{ent.apelido} não declarou carreira: não há tese a acompanhar")
        return 0

    r = vigia.avisar_novidades(ent, raiz, correio=remetente.pelo_ambiente(raiz),
                               banco_url=args.banco.strip())
    if not r["novas"]:
        print("nenhuma novidade por avisar")
        return 0
    print(f"{r['novas']} novidade(s) em {ent.apelido}: aviso entregue a "
          f"{r['avisados']} endereço(s)")
    if r["falharam"] or not r["avisados"]:
        print(f"o aviso das teses NÃO saiu para {r['falharam']} endereço(s) "
              f"em {ent.apelido}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
