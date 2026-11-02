#!/usr/bin/env python3
"""Apaga um filiado a pedido, ou CONFERE se um apagamento terminou.

LGPD art. 18, VI. O caminho normal é o painel do sindicato; esta ferramenta
existe para duas coisas que o painel não cobre:

1. **Retomar.** Apagar toca banco e disco, e não há transação que cubra os
   dois. Se o processo morrer no meio, o tombstone já está gravado e sobra
   coisa — esta ferramenta termina o serviço. Rodar de novo é seguro.

2. **Conferir.** `--conferir` só mede e imprime, sem apagar nada. Serve
   para responder "aquele pedido foi atendido?" sem acreditar em ninguém.

SAI COM CÓDIGO 1 SE SOBROU VESTÍGIO, para servir dentro de script.

    python3 ferramentas/apagar_filiado.py --entidade sindicato-x \\
        --cpf 529.982.247-25 --motivo "pedido do titular" \\
        --pedido-por gestor@sindicato-x.org.br

    python3 ferramentas/apagar_filiado.py --entidade sindicato-x \\
        --cpf 529.982.247-25 --conferir

NUNCA IMPRIME O CPF. A pessoa pediu para sair, e um diagnóstico com o CPF
dela é um segundo lugar com dado pessoal.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

RAIZ_DO_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_REPO))

from servidor import (  # noqa: E402
    acesso,
    apagamento,
    entidades,
    validacao,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entidade", required=True, help="apelido da entidade")
    p.add_argument("--cpf", required=True, help="o CPF de quem pediu")
    p.add_argument("--raiz", default=os.environ.get("PROTOCOL_RAIZ",
                                                    "dados_portal"),
                   help="raiz dos dados (padrão: PROTOCOL_RAIZ)")
    p.add_argument("--banco", default=os.environ.get("PROTOCOL_DATABASE_URL",
                                                     ""),
                   help="URL do banco (padrão: PROTOCOL_DATABASE_URL)")
    p.add_argument("--motivo", default="", help="por que, para o registro")
    p.add_argument("--pedido-por", default="", dest="pedido_por",
                   help="quem pediu, para o registro")
    p.add_argument("--conferir", action="store_true",
                   help="só mede e imprime; não apaga nada")
    args = p.parse_args()

    cpf = validacao.so_digitos(args.cpf)
    if not validacao.cpf_valido(cpf):
        print("CPF inválido", file=sys.stderr)
        return 2
    if not args.banco:
        print("sem --banco (ou PROTOCOL_DATABASE_URL) não há onde gravar o "
              "tombstone, e sem tombstone o apagamento não é retomável nem "
              "impede a próxima planilha de recriar a pessoa",
              file=sys.stderr)
        return 2

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2

    segredo = os.environ.get("PROTOCOL_SEGREDO", "").strip()
    if not segredo:
        print("PROTOCOL_SEGREDO não está definida. O tombstone é marcado com "
              "HMAC desse segredo, e sem ele não dá para reconhecer nem "
              "gravar quem foi apagado.", file=sys.stderr)
        return 2
    portao = acesso.Portao(raiz / ".portao-ferramenta", segredo)

    if args.conferir:
        sobrou = apagamento.vestigios(args.banco, ent, raiz, cpf, portao=portao)
        if not sobrou:
            print("nada sobrou desta pessoa nesta entidade.")
            return 0
        print(f"SOBRARAM {len(sobrou)} vestígio(s):")
        for v in sobrou:
            print(f"  - {v}")
        return 1

    saida = apagamento.apagar(args.banco, ent, raiz, cpf,
                              motivo=args.motivo,
                              pedido_por=args.pedido_por,
                              portao=portao)
    print(f"marcador: {saida['marcador']}")
    print(f"  diário    {saida['diario']} envio(s) redigido(s)")
    print(f"  arquivos  {saida['arquivos']} apagado(s) do disco")
    print(f"  rol       {saida['rol']} linha(s)")
    print(f"  acervo    {saida['acervo']} ingestão(ões)")
    for tabela, quantas in sorted(saida["banco"].items()):
        print(f"  banco     {quantas} em {tabela}")

    if saida["vestigios"]:
        print(f"\nAINDA SOBRA COISA ({len(saida['vestigios'])}):",
              file=sys.stderr)
        for v in saida["vestigios"]:
            print(f"  - {v}", file=sys.stderr)
        print("\nRode de novo: o tombstone já está gravado e repetir é "
              "seguro.", file=sys.stderr)
        return 1

    print("\nnada sobrou. O tombstone fica, e a próxima planilha do "
          "sindicato não recria esta pessoa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
