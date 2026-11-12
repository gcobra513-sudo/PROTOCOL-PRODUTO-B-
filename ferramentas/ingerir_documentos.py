#!/usr/bin/env python3
"""
Os documentos que o sindicato já tem, para dentro do produto.

    python3 ferramentas/ingerir_documentos.py \
        --pasta /caminho/dos/pdfs --entidade demo-sindicato

    python3 ferramentas/ingerir_documentos.py \
        --zip acervo.zip --entidade demo-sindicato

Sem `--entidade` nada é gravado: dá para passar a pasta e ver de quem é cada
arquivo antes de decidir. É a mesma disciplina de `ingerir_acervo.py`.

O QUE SAI NA TELA É A PILHA DO QUE NÃO CASOU, não a contagem do que casou:
"3.812 de 4.000" esconde 188 sentenças de gente que vai ficar sem resposta.
Cada sobra aparece com o nome do arquivo e o motivo, para alguém abrir.

CÓDIGOS DE SAÍDA, para o agendador:

    0  tudo casou
    1  casou, mas sobrou arquivo — alguém tem de olhar
    2  não deu para começar (entidade inexistente, nada a ler)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import (  # noqa: E402
    documentos_do_sindicato as lote,
    entidades,
)


def _ler_pasta(pasta: pathlib.Path) -> list[tuple[str, bytes]]:
    return [
        (p.name, p.read_bytes())
        for p in sorted(pasta.rglob("*"))
        if p.is_file() and p.suffix.lower() == ".pdf"
        and not p.name.startswith(".")
    ]


def _cpfs_da_base(url: str, apelido: str, pasta: pathlib.Path) -> set[str]:
    """Mora em `servidor/ingestao.py`, que a rota da web também chama."""
    from servidor import ingestao

    return ingestao.cpfs_da_base(url, apelido, pasta)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    origem = p.add_mutually_exclusive_group(required=True)
    origem.add_argument("--pasta", help="pasta com os PDFs")
    origem.add_argument("--zip", dest="zip_", help="arquivo .zip com os PDFs")
    p.add_argument("--entidade", default="",
                   help="apelido da entidade. Sem isto, nada é gravado")
    p.add_argument("--raiz", default="dados", help="raiz dos dados")
    p.add_argument("--banco", default=os.environ.get("PROTOCOL_DATABASE_URL", ""))
    p.add_argument("--mostrar", type=int, default=30,
                   help="quantas sobras listar (padrão: 30)")
    args = p.parse_args()

    if args.zip_:
        try:
            arquivos = lote.abrir_zip(pathlib.Path(args.zip_).read_bytes())
        except lote.ZipRecusado as e:
            print(f"O ZIP NÃO PÔDE SER ABERTO: {e}", file=sys.stderr)
            return 2
        except OSError as e:
            print(f"não deu para ler {args.zip_}: {e}", file=sys.stderr)
            return 2
    else:
        pasta_origem = pathlib.Path(args.pasta)
        if not pasta_origem.is_dir():
            print(f"{args.pasta} não é uma pasta", file=sys.stderr)
            return 2
        arquivos = _ler_pasta(pasta_origem)

    if not arquivos:
        print("nenhum PDF encontrado", file=sys.stderr)
        return 2

    raiz = pathlib.Path(args.raiz)
    cpfs: set[str] = set()
    ent = None
    if args.entidade:
        try:
            ent = entidades.Cadastro(raiz).resolver(args.entidade)
        except LookupError:
            print(f"entidade {args.entidade!r} não existe em {raiz}",
                  file=sys.stderr)
            return 2
        cpfs = _cpfs_da_base(args.banco, ent.apelido, ent.pasta(raiz))
        if not cpfs:
            print(
                "a base desta entidade está VAZIA: ingira a planilha de "
                "filiados antes, senão nenhum arquivo casa com ninguém",
                file=sys.stderr,
            )
            return 2
    else:
        # Sem entidade é diagnóstico: aceita qualquer CPF que feche, só para
        # mostrar de quem seria cada arquivo.
        from servidor import validacao

        for nome, corpo in arquivos:
            cpfs |= {c for c in lote._cpf_no_nome(nome)}
            try:
                from servidor import documentos as doc

                cpfs |= set(lote._cpfs_no_texto(doc.ler_pdf(corpo)))
            except Exception:  # noqa: BLE001
                pass
        cpfs = {c for c in cpfs if validacao.cpf_valido(c)}

    r = lote.casar(arquivos, cpfs)
    pessoas = len(r.casados)
    documentos_casados = sum(len(v) for v in r.casados.values())

    print("=" * 66)
    print(f"\n  {len(arquivos)} arquivo(s) lidos")
    print(f"  {documentos_casados} casaram com {pessoas} pessoa(s)")
    print(f"  {len(r.sobraram)} NÃO casaram\n")

    for aviso in r.avisos[: args.mostrar]:
        print(f"  ATENÇÃO  {aviso}")
    if r.avisos:
        print()

    if r.sobraram:
        print(f"  o que NÃO casou (primeiros {args.mostrar}):")
        for s in r.sobraram[: args.mostrar]:
            print(f"    {s.arquivo[:44]:46} {s.motivo}")
        if len(r.sobraram) > args.mostrar:
            print(f"    ... e mais {len(r.sobraram) - args.mostrar}")
        print()

    if ent is None:
        print("  (nada gravado — passe --entidade para ingerir)")
        return 1 if r.sobraram else 0

    # A GRAVAÇÃO MORA EM `servidor/ingestao.py`, e é a MESMA que a rota da
    # web chama: bytes para a entrega com o nome do contrato, e no banco
    # `origem = 'sindicato'` com `tem_texto` medido.
    from servidor import ingestao

    entrega = ent.entrega(raiz)
    try:
        feito = ingestao.gravar_documentos(
            ent, raiz, r, args.banco,
            marcador_de=ingestao.marcador_pelo_ambiente())
    except ingestao.IngestaoRecusada as e:
        print(f"\nNADA GRAVADO: {e}", file=sys.stderr)
        return 2

    print(f"  gravado em {entrega}: {feito['gravados']} documento(s) de "
          f"{feito['pessoas']} pessoa(s)")
    if feito["apagadas"]:
        # NUNCA DIZ QUEM — a pessoa pediu para sair.
        print(f"  {feito['apagadas']} pessoa(s) pediram apagamento e os "
              f"documentos delas NÃO foram gravados.")
    if not args.banco:
        print(
            "\n  AVISO: sem --banco, os arquivos ficam no disco e os fatos\n"
            "  lidos deles NÃO são gravados. A tela da pessoa relê o PDF a\n"
            "  cada visita, e o painel do sindicato não os enxerga."
        )
    return 1 if r.sobraram else 0


if __name__ == "__main__":
    raise SystemExit(main())
