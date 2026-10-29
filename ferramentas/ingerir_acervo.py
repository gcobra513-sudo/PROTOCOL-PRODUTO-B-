#!/usr/bin/env python3
"""
Ingere o acervo que o sindicato mandou, e diz em voz alta o que ele tem.

A PRIMEIRA COISA QUE O SINDICATO VÊ DO PRODUTO. Não é "quem tem direito" —
é o estado da base dele, que é informação que ele não tem hoje e que sai do
arquivo que ele mesmo mandou.

    python3 ferramentas/ingerir_acervo.py --acervo base.csv --entidade demo-sindicato
    python3 ferramentas/ingerir_acervo.py --acervo base.csv            # só relata

Sem `--entidade` nada é gravado: dá para passar o arquivo e ver o diagnóstico
antes de decidir ingerir. Com `--entidade`, grava `acervo.jsonl` append-only
na pasta da entidade, pela mesma disciplina do diário de cadastro — uma linha
por ingestão, nunca reescrito, e o retrato é derivado dele.

SAI COM CÓDIGO != 0 se o ARQUIVO for impossível de ler. Linha ruim NÃO é
motivo de código de erro: linha ruim é o produto.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import acervo, completude, deposito, entidades  # noqa: E402

ARQUIVO = "acervo.jsonl"


def imprimir(r: completude.Retrato, pessoas: list[acervo.Pessoa],
             limite: int) -> None:
    nome_de = {
        p.cpf or f"linha-{p.linha_no_arquivo}":
            p.campos.get("nome_completo") or "(sem nome no acervo)"
        for p in pessoas
    }
    print("=" * 66)
    print("ACERVO DO SINDICATO")
    print("=" * 66)
    print(f"\n  {r.manchete()}")
    print(f"\n  linhas lidas ................. {r.linhas}")
    print(f"  pessoas distintas ............ {r.total}")
    print(f"  alcançáveis .................. {r.alcancaveis}")
    print(f"  inalcançáveis ................ {r.inalcancaveis}")
    print(f"  linhas divergentes ........... {r.divergentes}")
    print(f"  cadastradas no portal ........ {r.cadastrados}")
    print(f"  sem cadastro ................. {r.sem_cadastro}")
    if r.fora_do_acervo:
        print(f"  cadastradas e FORA do acervo . {r.fora_do_acervo}")
    if r.acompanhando:
        print(f"  acompanhando processo ........ {r.acompanhando} "
              f"({r.processos_acompanhados} processos)")
        print(f"  querem aviso por e-mail ...... {r.querem_aviso}")

    if r.falta_por_campo:
        print("\n  o que falta, por campo:")
        for coluna, quantos in r.falta_por_campo.items():
            print(f"    {coluna:.<28} {quantos}")

    if r.inalcancaveis_por_cpf:
        print(f"\n  quem o sindicato não alcança (primeiros {limite}):")
        for chave, motivo in list(r.inalcancaveis_por_cpf.items())[:limite]:
            print(f"    {nome_de.get(chave, chave)[:40]:<40} {motivo}")
        se_mais = len(r.inalcancaveis_por_cpf) - limite
        if se_mais > 0:
            print(f"    ... e outros {se_mais}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--acervo", required=True, help="a planilha que o sindicato mandou")
    p.add_argument("--entidade", default="",
                   help="apelido da entidade. Sem isto, nada é gravado")
    p.add_argument("--raiz", default="dados", help="raiz dos dados (padrão: dados)")
    p.add_argument("--mostrar", type=int, default=20,
                   help="quantos inalcançáveis listar por nome")
    args = p.parse_args()

    pessoas, problemas = acervo.ler(args.acervo)
    if problemas:
        print("O ARQUIVO NÃO PÔDE SER USADO:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 2

    retrato = completude.retratar(pessoas)
    imprimir(retrato, pessoas, args.mostrar)

    if not args.entidade:
        print("\n  (nada gravado — passe --entidade para ingerir)")
        return 0

    raiz = pathlib.Path(args.raiz)
    cadastro = entidades.Cadastro(raiz)
    try:
        ent = cadastro.resolver(args.entidade)
    except LookupError:
        print(f"\nentidade {args.entidade!r} não existe em {raiz}", file=sys.stderr)
        return 2

    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    agora = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    deposito.anexar_com_fsync(
        pasta / ARQUIVO,
        json.dumps(
            {
                "ingerido_em": agora,
                "origem": str(pathlib.Path(args.acervo).name),
                "retrato": dataclasses.asdict(retrato),
                "pessoas": [
                    {
                        "cpf": p.cpf,
                        "linha_no_arquivo": p.linha_no_arquivo,
                        "campos": p.campos,
                        "achados": [
                            {"coluna": a.coluna, "estado": a.estado,
                             "detalhe": a.detalhe}
                            for a in p.achados
                        ],
                    }
                    for p in pessoas
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n",
    )
    print(f"\n  gravado em {pasta / ARQUIVO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
