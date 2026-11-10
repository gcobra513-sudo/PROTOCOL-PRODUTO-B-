#!/usr/bin/env python3
"""
As trocas de e-mail que a planilha do sindicato pediu, e a decisão sobre elas.

A planilha que o gestor envia põe gente NOVA no acesso na hora. O que ela não
faz é trocar o e-mail de quem já entra: isso fica pedido, e só vale depois
que alguém AQUI confere — por telefone, por e-mail ao endereço antigo, pelo
que o contrato com o sindicato combinar. O motivo está em `servidor/trocas.py`:
se a troca valesse sozinha, uma conta de gestor comprometida viraria todas as
contas.

    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato listar
    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato aprovar 11144477735
    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato recusar 11144477735

`aprovar` e `recusar` aceitam vários CPFs. A recusa fica guardada: a mesma
planilha, reenviada, não recria o pedido.

SAI COM CÓDIGO != 0 se algum CPF não tinha troca pedida — e os outros, que
tinham, são decididos assim mesmo; a saída diz qual foi qual.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import entidades, trocas  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entidade", required=True, help="apelido da entidade")
    p.add_argument("--raiz", default="dados",
                   help="raiz dos dados (padrão: dados)")
    p.add_argument("acao", choices=("listar", "aprovar", "recusar"))
    p.add_argument("cpfs", nargs="*", help="CPFs a decidir")
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2
    pasta = ent.pasta(raiz)

    if args.acao == "listar":
        pendentes = trocas.estado(pasta).pendentes
        if not pendentes:
            print("nenhuma troca de e-mail esperando")
            return 0
        print(f"{len(pendentes)} troca(s) de e-mail esperando em "
              f"{ent.apelido}:\n")
        for cpf, pedido in sorted(pendentes.items()):
            # O e-mail de HOJE, lido do portão agora — não o que valia
            # quando a planilha chegou.
            hoje = trocas.destino_atual(pasta, cpf) or "(fora do acesso)"
            print(f"  {cpf}  {hoje}  ->  {pedido['para']}"
                  f"   (pedida em {pedido['quando']})")
        return 0

    if not args.cpfs:
        print(f"{args.acao}: diga o CPF", file=sys.stderr)
        return 2
    faltou = False
    for cpf in args.cpfs:
        try:
            if args.acao == "aprovar":
                feito = trocas.aprovar(pasta, cpf)
                print(f"aprovada: {cpf}  {feito['de']}  ->  {feito['para']}")
            else:
                feito = trocas.recusar(pasta, cpf)
                print(f"recusada: {cpf}  (continua como estava; "
                      f"{feito['para']} não será pedido de novo)")
        except trocas.SemPedido as e:
            faltou = True
            print(f"sem troca pedida para {cpf}: nada foi feito ({e})",
                  file=sys.stderr)
    return 1 if faltou else 0


if __name__ == "__main__":
    raise SystemExit(main())
