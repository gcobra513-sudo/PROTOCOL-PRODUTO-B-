#!/usr/bin/env python3
"""
Lembra quem opera de que há pedido de acesso esperando decisão.

A planilha do sindicato pode deixar dois tipos de pedido que só valem depois
de conferidos por nós: a troca de e-mail de quem já entra no portal, e a
entrada de gente nova com um e-mail que outra pessoa usa (`servidor/trocas.py`).
O servidor avisa na hora em que o pedido nasce — mas esse e-mail pode se
perder, e o endereço pode nem estar configurado ainda. Esta ferramenta é o
que impede o pedido de ficar esquecido: o agendador a roda todo dia, e ela
repete o aviso ENQUANTO houver pedido esperando.

    PROTOCOL_EMAIL_DE_QUEM_OPERA=nos@exemplo.org \\
        python3 ferramentas/avisar_pedidos.py --entidade demo-sindicato

O e-mail leva só contagens — nunca CPF nem e-mail de filiado.

CÓDIGOS DE SAÍDA, que é o que o agendador lê:

    0  não há pedido esperando, ou o lembrete saiu
    1  há pedido esperando e NÃO deu para avisar ninguém: falta
       PROTOCOL_EMAIL_DE_QUEM_OPERA, ou o correio falhou. O agendador
       registra falha, e a falha aparece em /saude — que é o ponto: pedido
       esperando sem ninguém saber não pode parecer um dia normal.
    2  a entidade não existe
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import entidades, remetente, trocas  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entidade", required=True)
    p.add_argument("--raiz", default="dados")
    p.add_argument(
        "--para",
        default=os.environ.get("PROTOCOL_EMAIL_DE_QUEM_OPERA", "").strip(),
        help="quem recebe o lembrete (padrão: PROTOCOL_EMAIL_DE_QUEM_OPERA)")
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2
    pasta = ent.pasta(raiz)

    esperando = len(trocas.estado(pasta).pendentes)
    if not esperando:
        print("nenhum pedido esperando")
        return 0

    # QUANTOS, nunca quem: esta saída vai para o log do agendador.
    if not args.para:
        print(f"{esperando} pedido(s) esperando em {ent.apelido} e NINGUÉM "
              f"a avisar: defina PROTOCOL_EMAIL_DE_QUEM_OPERA",
              file=sys.stderr)
        return 1
    try:
        trocas.avisar_quem_opera(
            pasta, apelido=ent.apelido, nome=ent.nome, raiz=raiz,
            correio=remetente.pelo_ambiente(raiz), destino=args.para)
    except Exception as e:  # noqa: BLE001
        print(f"{esperando} pedido(s) esperando em {ent.apelido} e o "
              f"lembrete NÃO saiu: {type(e).__name__}", file=sys.stderr)
        return 1
    print(f"{esperando} pedido(s) esperando em {ent.apelido}: lembrete "
          f"enviado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
