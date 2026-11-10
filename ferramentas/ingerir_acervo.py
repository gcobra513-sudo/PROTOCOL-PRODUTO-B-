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
import os
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
    p.add_argument(
        "--banco", default=os.environ.get("PROTOCOL_DATABASE_URL", ""),
        help="URL do banco. Sem ela a planilha vira só arquivo, e o motor "
             "não responde pela base — ver o aviso no fim da execução",
    )
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
    # O retrato é RECALCULADO depois do filtro de tombstone, mais abaixo.
    # Este aqui é só para imprimir o que o ARQUIVO traz, antes de saber
    # quem pediu para sair.

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

    # O MIOLO MORA EM `servidor/ingestao.py`, e é o MESMO que a rota da web
    # chama: tirar quem pediu para sair, recalcular o retrato sobre o que
    # sobra, gravar o arquivo e projetar no banco. Dois caminhos para a
    # mesma coisa divergem; o que esta ferramenta tem de seu é imprimir.
    from servidor import acesso, ingestao

    # O SEGREDO VEM DO AMBIENTE, não de `config.carregar()`: aquela função
    # exige SMTP configurado, e uma ferramenta de ingestão não tem nada a
    # ver com entregar e-mail.
    segredo = os.environ.get("PROTOCOL_SEGREDO", "").strip()

    def marcador_de(cpf: str) -> str:
        if not segredo:
            raise RuntimeError(
                "PROTOCOL_SEGREDO não está definida, e sem ela não dá para "
                "reconhecer o marcador de quem foi apagado"
            )
        return acesso.marcador_de_cpf(segredo, cpf)

    try:
        pessoas, apagadas = ingestao.sem_apagados(
            pessoas, banco_url=args.banco, apelido=ent.apelido,
            marcador_de=marcador_de)
    except ingestao.IngestaoRecusada as e:
        print(f"\nNÃO DEU PARA CONFERIR QUEM FOI APAGADO A PEDIDO: {e}",
              file=sys.stderr)
        print("  nada gravado. Sem esta conferência a ingestão pode "
              "recriar quem pediu para sair.", file=sys.stderr)
        return 2

    if apagadas:
        # NUNCA IMPRIME O CPF — a pessoa pediu para sair. E relata, em vez de
        # pular calado: sem o aviso o sindicato reenviaria o mesmo CPF para
        # sempre sem saber que precisa corrigir a FONTE.
        print(f"\n  {apagadas} pessoa(s) da planilha foram apagada(s) a "
              f"pedido e NÃO foram gravada(s).")
        print("  Tire-as do arquivo: enquanto estiverem nele, toda ingestão "
              "vai pulá-las de novo.")

    try:
        feito = ingestao.gravar_planilha(ent, raiz, pessoas,
                                         origem=args.acervo,
                                         banco_url=args.banco,
                                         marcador_de=marcador_de)
    except ingestao.IngestaoRecusada as e:
        print(f"\nNADA GRAVADO: {e}", file=sys.stderr)
        return 2
    print(f"\n  gravado em {pasta / ARQUIVO}")

    # O ACESSO. A MESMA regra da web, porque é a mesma função: quem é novo
    # passa a receber código; e-mail diferente de quem JÁ entra não vale —
    # fica pedido, inclusive quando quem roda isto somos nós.
    portao = feito["portao"]
    print(f"  acesso: {len(portao.novos)} pessoa(s) nova(s) já recebem "
          f"código de acesso")
    if portao.sem_email:
        print(f"  acesso: {portao.sem_email} nova(s) sem e-mail que sirva — "
              f"estão na base e não têm como entrar")
    if portao.divergentes:
        print(f"  acesso: {portao.divergentes} com dois e-mails diferentes "
              f"na planilha — nenhum foi escolhido")
    if portao.trocas:
        print(f"  acesso: {len(portao.trocas)} TROCA(S) DE E-MAIL pedida(s), "
              f"que NÃO valem ainda.\n"
              f"          python3 ferramentas/trocas_de_email.py "
              f"--entidade {ent.apelido} listar")
    if portao.recusadas:
        print(f"  acesso: {portao.recusadas} troca(s) já recusada(s) "
              f"continuam na planilha")
    if portao.fora_da_planilha:
        print(f"  acesso: {portao.fora_da_planilha} pessoa(s) estão no "
              f"acesso e fora desta planilha — CONTINUAM entrando")
    if args.banco:
        print(f"  banco: {feito['projetadas']} pessoa(s) projetada(s) em "
              f"{ent.apelido}")
    else:
        print(
            "\n  AVISO: sem --banco (ou PROTOCOL_DATABASE_URL), esta planilha\n"
            "  fica só em arquivo. O painel mostra o retrato da base, mas o\n"
            "  motor NÃO responde por quem não se cadastrou no portal."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
