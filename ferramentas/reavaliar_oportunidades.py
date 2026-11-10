#!/usr/bin/env python3
"""Reavalia a base e GUARDA o veredicto, com a prova de qual catálogo o produziu.

POR QUE ISTO EXISTE. O motor sempre soube responder "o que esta pessoa pode
fazer". O que não existia era a resposta GUARDADA — e sem ela não há como
dizer o que mudou quando um tema é julgado. A tabela `oportunidade` estava no
esquema desde o checkpoint 9 e ninguém escrevia nela.

A PRIMEIRA TRANSIÇÃO DE VERDADE VAI SER A HOMOLOGAÇÃO. Hoje nada está
homologado, então o motor emite `FALTA` e `NAO_PODE` e nenhum `PODE` — o que
está correto. No dia em que um advogado marcar `homologado = "S"` e subir a
`versao` do catálogo, esta ferramenta vai mostrar `FALTA → PODE` para todo
mundo que a tese alcança. É por isso que ela vem ANTES da homologação: sem o
veredicto anterior guardado, o efeito passa e ninguém consegue provar qual
catálogo produziu o quê.

    python3 ferramentas/reavaliar_oportunidades.py --entidade sind-x

CÓDIGOS DE SAÍDA:

    0  reavaliou
    2  falta pré-requisito (sem banco, entidade inexistente)
    3  O CATÁLOGO MENTIU: o conteúdo mudou e a `versao` não.

O 3 é código PRÓPRIO, e eu escrevi aqui primeiro que era "porque o
agendador trata 1 como sucesso". ERA FALSO, e ler o `agenda.tarefas_padrao`
inteiro mostra: ele levanta para qualquer coisa fora de 0 **e também para o
1**, com um segundo `if` logo abaixo do primeiro. Só o 0 é sucesso.

O 3 serve a outra coisa, que continua valendo: DISTINGUIR. O 1 das outras
ferramentas significa "rodou, mas algo ficou de fora" — estado em que o
trabalho andou. Catálogo mentindo é o contrário: nada andou, e ninguém deve
tentar de novo até alguém subir a `versao` do arquivo. Dois estados
diferentes com o mesmo código fariam quem lê o registro tratar os dois do
mesmo jeito.

NUNCA IMPRIME CPF. O relatório é de contagens; quem precisa saber de quem é
cada mudança abre o painel, com sessão de gestor.

Spec: `docs/superpowers/specs/2026-11-02-oportunidade-persistida-design.md`
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

RAIZ_DO_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_REPO))

from nucleo import entendimentos, motor, panorama  # noqa: E402
from servidor import banco, entidades  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entidade", required=True)
    p.add_argument("--raiz", default=os.environ.get("PROTOCOL_RAIZ",
                                                    "dados_portal"))
    p.add_argument("--banco", default=os.environ.get("PROTOCOL_DATABASE_URL",
                                                     ""))
    p.add_argument("--catalogos", default=str(entendimentos.PASTA_PADRAO),
                   help="pasta dos catálogos de categoria")
    args = p.parse_args()

    if not args.banco:
        print("sem --banco (ou PROTOCOL_DATABASE_URL) não há onde guardar o "
              "veredicto, e guardar é o ponto desta ferramenta",
              file=sys.stderr)
        return 2

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2

    catalogo = entendimentos.carregar_categorias(
        args.catalogos, tuple(ent.categorias)
    )
    if not catalogo.assinatura:
        # Entidade sem categoria contratada não tem o que avaliar, e isto é
        # estado legítimo — não há ação nem entendimento dela aqui dentro.
        # Inventar uma assinatura vazia gravaria linha dizendo que o
        # veredicto saiu de catálogo nenhum.
        print(f"{ent.apelido} não declarou categoria contratada: nada a "
              f"avaliar. Nada foi gravado.")
        return 0

    pessoas = panorama.ultimo_envio_por_cpf(banco.base(args.banco,
                                                       ent.apelido))
    gravadas = 0
    try:
        for cpf, envio in pessoas.items():
            fatos = panorama.fatos_do_cadastro(envio["linha"],
                                               envio["entregues"])
            oportunidades = motor.avaliar(fatos, catalogo)
            gravadas += banco.registrar_oportunidades(
                args.banco, ent.apelido, cpf, oportunidades,
                assinatura=catalogo.assinatura,
                digest=catalogo.digest,
            )
    except banco.CatalogoIncoerente as e:
        print(f"RECUSADO: {e}", file=sys.stderr)
        print("Nada foi gravado nesta rodada.", file=sys.stderr)
        return 3

    mudou = banco.mudancas(args.banco, ent.apelido,
                           assinatura=catalogo.assinatura)
    print(f"catálogo {catalogo.assinatura} "
          f"(impressão {catalogo.digest[:12]})")
    print(f"  {len(pessoas)} pessoa(s) na base")
    print(f"  {gravadas} veredicto(s) guardado(s)")
    if not mudou:
        print("  nenhuma mudou de veredicto neste catálogo")
        return 0

    # POR REFERÊNCIA, NUNCA POR PESSOA. Quem precisa saber de quem é cada
    # mudança abre o painel, com sessão de gestor; este relatório vai para o
    # log do agendador.
    print(f"  {len(mudou)} MUDARAM de veredicto:")
    por_referencia: dict[tuple[str, str, str], int] = {}
    for m in mudou:
        chave = (m["referencia"], m["de"], m["para"])
        por_referencia[chave] = por_referencia.get(chave, 0) + 1
    for (referencia, de, para), quantas in sorted(por_referencia.items()):
        print(f"    {referencia}: {de} -> {para} ({quantas} pessoa(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
